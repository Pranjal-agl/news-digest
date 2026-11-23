"""
fetch.py - Fetches articles from RSS feeds.

No accounts, no API keys, no signup needed - just public RSS feeds.

Feeds are fetched in parallel with a timeout and a retry, every entry in the
feed is read (not just the top 10), publish dates are parsed into real UTC
timestamps, and old items and opinion pieces are dropped. A per-feed health
report is kept so the site can show which sources worked today.
"""
import calendar
import html
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple

import feedparser
import requests

from bias import resolve_outlet

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 20  # seconds
# A normal browser UA: several publishers (e.g. Washington Times) return 403
# to obvious bot user agents.
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36 news-digest")
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.5",
    "Accept-Language": "en-US,en;q=0.9",
}

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_BLOCK_END_RE = re.compile(r"(?<=[A-Za-z0-9’'\")])\s*</(?:p|li|h[1-6]|div|blockquote)>", re.IGNORECASE)
# Boilerplate that feeds append to descriptions
_BOILERPLATE_RE = re.compile(
    r"(Continue reading\.*|Read more\.*|Read Full Article.*|Click here.*|"
    r"The post .{0,200}? appeared first on [^.]{0,80}\.?|\[…\]|\[\.\.\.\]|…\s*$)",
    re.IGNORECASE,
)
_OPINION_URL_RE = re.compile(r"/(opinion|opinions|commentisfree|op-ed|oped|editorial|editorials|columnists?|letters)/",
                             re.IGNORECASE)
_OPINION_TITLE_RE = re.compile(r"^\s*(opinion|op-ed|editorial|column|analysis & opinion|letters?)\s*[:|\-–]",
                               re.IGNORECASE)

# Health report for the latest fetch: {feed name: {...}}
FEED_STATUS: Dict[str, Dict[str, Any]] = {}


def clean_text(text: str) -> str:
    """Strip HTML tags, unescape entities, remove feed boilerplate."""
    # A paragraph/heading break without its own punctuation (e.g. Guardian's
    # standfirst + body) becomes a sentence break, so text doesn't run together.
    text = _BLOCK_END_RE.sub(". ", text or "")
    text = html.unescape(_TAG_RE.sub(" ", text))
    text = _BOILERPLATE_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def _extract_image(entry) -> Optional[str]:
    """
    Best available thumbnail for an RSS entry: media:thumbnail,
    media:content (image), an image enclosure, then the first <img> in the
    summary HTML. Prefers the widest media:content/thumbnail when several
    sizes are offered.
    """
    def _widest(items):
        best, best_w = None, -1
        for m in items or []:
            url = m.get("url") or m.get("href")
            if not url:
                continue
            medium, mime = m.get("medium", ""), m.get("type", "")
            looks_image = (medium == "image" or mime.startswith("image/") or
                           re.search(r"\.(jpe?g|png|webp)(\?|$)", url, re.I))
            if not looks_image and medium:
                continue
            try:
                w = int(m.get("width") or 0)
            except (TypeError, ValueError):
                w = 0
            if w > best_w:
                best, best_w = url, w
        return best

    url = _widest(getattr(entry, "media_content", None)) or _widest(getattr(entry, "media_thumbnail", None))
    if url:
        return url

    for enc in getattr(entry, "enclosures", None) or []:
        if enc.get("type", "").startswith("image/"):
            return enc.get("href") or enc.get("url")

    for field in ("summary", "content"):
        raw = entry.get(field, "")
        if isinstance(raw, list):
            raw = " ".join(c.get("value", "") for c in raw)
        m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', raw or "", re.IGNORECASE)
        if m and m.group(1).startswith("http"):
            return m.group(1)
    return None


def _entry_datetime(entry) -> Optional[datetime]:
    """Publish time as an aware UTC datetime (feedparser normalises to UTC)."""
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        st = entry.get(key)
        if st:
            try:
                return datetime.fromtimestamp(calendar.timegm(st), tz=timezone.utc)
            except (OverflowError, ValueError, TypeError):
                continue
    return None


def is_opinion(link: str, title: str) -> bool:
    return bool(_OPINION_URL_RE.search(link or "") or _OPINION_TITLE_RE.search(title or ""))


def _fetch_feed_bytes(url: str, timeout: int = REQUEST_TIMEOUT, retries: int = 1) -> Tuple[Optional[bytes], str]:
    """Fetch raw feed content. Returns (content or None, error message)."""
    last_err = ""
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, timeout=timeout, allow_redirects=True, headers=HEADERS)
            r.raise_for_status()
            return r.content, ""
        except Exception as e:  # noqa: BLE001 - any failure just skips the feed
            last_err = str(e)[:200]
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    logger.warning(f"GET failed for {url}: {last_err}")
    return None, last_err


def verify_rss_url(url: str) -> bool:
    """True if the URL loads and parses as a feed with entries."""
    content, _ = _fetch_feed_bytes(url, retries=0)
    if content is None:
        return False
    return bool(feedparser.parse(content).get("entries"))


def parse_feed(content: bytes, feed_config: Dict[str, str], *,
               max_entries: int = 50, max_age_hours: float = 48,
               skip_opinion: bool = True, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Turn raw feed bytes into article dicts (pure function, used by tests)."""
    now = now or datetime.now(timezone.utc)
    feed_name = feed_config.get("name", "Unknown")
    outlet = resolve_outlet(feed_config.get("outlet") or feed_name)
    cutoff = now - timedelta(hours=max_age_hours) if max_age_hours else None

    feed = feedparser.parse(content)
    articles, skipped_old, skipped_opinion = [], 0, 0
    for entry in feed.get("entries", [])[:max_entries]:
        title = clean_text(entry.get("title", ""))
        link = entry.get("link", "")
        if not title or not link:
            continue
        if skip_opinion and is_opinion(link, title):
            skipped_opinion += 1
            continue
        published = _entry_datetime(entry)
        if cutoff and published and published < cutoff:
            skipped_old += 1
            continue
        summary = clean_text(entry.get("summary", entry.get("description", "")))
        articles.append({
            "title": title,
            "link": link,
            "source": outlet,          # outlet name, e.g. "BBC News"
            "feed": feed_name,         # feed name, e.g. "BBC World"
            "summary": summary,
            "published": (published or now).isoformat(),
            "has_date": published is not None,
            "image_url": _extract_image(entry),
            "type": "rss",
        })
    if skipped_old or skipped_opinion:
        logger.info(f"{feed_name}: kept {len(articles)}, dropped {skipped_old} old, {skipped_opinion} opinion")
    return articles


def fetch_rss_articles(rss_urls: List[Dict[str, str]], fetch_cfg: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Fetch every configured feed in parallel and return all articles."""
    cfg = fetch_cfg or {}
    timeout = int(cfg.get("timeout_seconds", REQUEST_TIMEOUT))
    retries = int(cfg.get("retries", 1))
    FEED_STATUS.clear()

    def work(feed_config):
        name, url = feed_config.get("name", "Unknown"), feed_config.get("url", "")
        if not url:
            return feed_config, [], "no URL configured"
        content, err = _fetch_feed_bytes(url, timeout=timeout, retries=retries)
        if content is None:
            return feed_config, [], err or "fetch failed"
        try:
            items = parse_feed(content, feed_config,
                               max_entries=int(cfg.get("max_entries_per_feed", 50)),
                               max_age_hours=float(cfg.get("max_age_hours", 48)),
                               skip_opinion=bool(cfg.get("skip_opinion", True)))
        except Exception as e:  # noqa: BLE001
            return feed_config, [], f"parse error: {e}"
        return feed_config, items, ""

    articles: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for feed_config, items, err in pool.map(work, rss_urls):
            name = feed_config.get("name", "Unknown")
            FEED_STATUS[name] = {
                "feed": name,
                "outlet": resolve_outlet(feed_config.get("outlet") or name),
                "url": feed_config.get("url", ""),
                "ok": not err,
                "articles": len(items),
                "error": err,
            }
            if err:
                logger.warning(f"Skipping RSS feed '{name}' - {err}")
            else:
                logger.info(f"Fetched {len(items)} usable entries from {name}")
            articles.extend(items)
    return articles


def fetch_all_articles(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    rss_sources = config.get("sources", {}).get("rss", [])
    if not rss_sources:
        logger.warning("No RSS sources configured!")
        return []
    logger.info(f"Fetching from {len(rss_sources)} RSS sources...")
    articles = fetch_rss_articles(rss_sources, config.get("fetch"))
    ok = sum(1 for s in FEED_STATUS.values() if s["ok"])
    logger.info(f"Total articles fetched: {len(articles)} from {ok}/{len(rss_sources)} feeds")
    return articles


if __name__ == "__main__":
    import yaml
    with open("config.yaml") as f:
        config = yaml.safe_load(f)
    arts = fetch_all_articles(config)
    for name, st in FEED_STATUS.items():
        print(f"{'OK ' if st['ok'] else 'ERR'} {name:35s} {st['articles']:3d} {st['error']}")
    print(f"\n{len(arts)} articles")
