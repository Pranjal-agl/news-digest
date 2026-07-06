"""
fetch.py - Fetches articles from RSS feeds.

No accounts, no API keys, no signup needed - just public RSS feeds.
"""
import feedparser
import requests
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10  # seconds


def _extract_image(entry) -> Optional[str]:
    """
    Extract the best available thumbnail/image URL from an RSS entry.
    Checks, in order:
      1. media:thumbnail  (BBC, Guardian, NYT, Fox etc all use this)
      2. media:content with image type
      3. enclosure with image type
      4. first <img> tag embedded in summary HTML (fallback)
    Returns the URL string, or None if nothing found.
    """
    # 1. media:thumbnail
    thumbnails = getattr(entry, 'media_thumbnail', None)
    if thumbnails:
        return thumbnails[0].get('url')

    # 2. media:content flagged as image
    media = getattr(entry, 'media_content', None)
    if media:
        for m in media:
            url = m.get('url', '')
            medium = m.get('medium', '')
            mime = m.get('type', '')
            if medium == 'image' or mime.startswith('image/') or any(
                url.lower().endswith(ext) for ext in ('.jpg', '.jpeg', '.png', '.webp')
            ):
                return url

    # 3. RSS enclosure
    enclosures = getattr(entry, 'enclosures', None)
    if enclosures:
        for enc in enclosures:
            mime = enc.get('type', '')
            if mime.startswith('image/'):
                return enc.get('href') or enc.get('url')

    # 4. Scrape first <img src="..."> from the summary HTML as last resort
    summary = entry.get('summary', '') or ''
    if summary:
        match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', summary, re.IGNORECASE)
        if match:
            url = match.group(1)
            if url.startswith('http'):
                return url

    return None


def _fetch_feed_bytes(url: str) -> Optional[bytes]:
    """Fetch raw feed content with a hard timeout. Returns None on failure."""
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True,
                                 headers={'User-Agent': 'Mozilla/5.0 (news-digest-bot)'})
        response.raise_for_status()
        return response.content
    except Exception as e:
        logger.warning(f"GET failed for {url}: {e}")
        return None


def verify_rss_url(url: str) -> bool:
    """
    Verify that an RSS URL is accessible and returns valid feed data.
    Returns True if valid, False otherwise.
    """
    content = _fetch_feed_bytes(url)
    if content is None:
        logger.error(f"RSS URL failed verification: {url}")
        return False

    feed = feedparser.parse(content)
    if feed.get('entries'):
        logger.info(f"RSS URL verified: {url}")
        return True
    else:
        logger.warning(f"RSS URL has no entries: {url}")
        return False


def fetch_rss_articles(rss_urls: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """
    Fetch articles from RSS feeds.

    Args:
        rss_urls: List of dicts with 'name' and 'url' keys

    Returns:
        List of article dicts with title, link, source, summary, published date
    """
    articles = []

    for feed_config in rss_urls:
        name = feed_config.get('name', 'Unknown')
        url = feed_config.get('url', '')

        if not url:
            logger.warning(f"Skipping RSS feed '{name}' - no URL provided")
            continue

        content = _fetch_feed_bytes(url)
        if content is None:
            logger.warning(f"Skipping RSS feed '{name}' - could not fetch URL")
            continue

        try:
            feed = feedparser.parse(content)

            if not feed.get('entries'):
                logger.warning(f"Skipping RSS feed '{name}' - no entries found")
                continue

            logger.info(f"Fetched {len(feed.entries)} entries from {name}")

            for entry in feed.entries[:10]:  # Limit to 10 per source for now
                article = {
                    'title': entry.get('title', 'No title'),
                    'link': entry.get('link', ''),
                    'source': name,
                    'summary': entry.get('summary', entry.get('description', '')),
                    'published': entry.get('published', datetime.now().isoformat()),
                    'image_url': _extract_image(entry),
                    'type': 'rss'
                }
                articles.append(article)

        except Exception as e:
            logger.error(f"Error parsing RSS from {name}: {e}")

    return articles


def fetch_all_articles(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Orchestrate fetching from all configured RSS sources.

    Note: this does its own fetch+parse per source (and skips sources that
    fail), so there's no need to call verify_rss_url() separately beforehand -
    that would just fetch every URL twice.

    Args:
        config: Configuration dict with 'sources' key

    Returns:
        List of all articles
    """
    rss_sources = config.get('sources', {}).get('rss', [])

    if not rss_sources:
        logger.warning("No RSS sources configured!")
        return []

    logger.info(f"Fetching from {len(rss_sources)} RSS sources...")
    articles = fetch_rss_articles(rss_sources)
    logger.info(f"Total articles fetched: {len(articles)}")
    return articles


if __name__ == '__main__':
    # Test fetch.py standalone
    import yaml

    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    print("Starting article fetch...\n")
    articles = fetch_all_articles(config)

    print(f"\nFetched {len(articles)} total articles:\n")
    for i, article in enumerate(articles[:5], 1):
        print(f"{i}. {article['title']}")
        print(f"   Source: {article['source']}")
        print(f"   Link: {article['link']}")
        print()
