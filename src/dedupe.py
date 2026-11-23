"""
dedupe.py - Groups articles from different outlets into stories, the way
Ground News does, and computes each story's coverage profile.

How grouping works
------------------
1. Every article becomes a TF-IDF vector over its headline (weighted x2,
   proper nouns x1.5) and the opening of its description. IDF is computed
   over today's articles, so words every outlet uses today ("Ukraine",
   "Trump") count less than the specific ones ("Kryvyi Rih", "Isidro").
2. Articles are added one at a time, oldest first, to the story whose
   centroid they are most similar to (cosine >= join_threshold); otherwise
   they start a new story. Comparing against a story's centroid rather than
   any single member avoids the "chaining" that merges unrelated stories.
3. A second pass merges stories whose centroids are very similar.

Each story keeps every article (so the site can compare headlines from the
left, center and right) plus counts, bias bar, blindspot side, ownership mix,
first-reported-by, topic, regions and a ranking score.
"""
import hashlib
import logging
import math
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from bias import (bias_breakdown, bias_bar_data, blindspot_side, outlet_meta,
                  ownership_breakdown, resolve_outlet)
from topics import classify_topic, find_places, primary_region

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_STOPWORDS = set("""
a about above after again against all also am amid among an and any are around as at be because been before being
below between both but by can could did do does doing down during each few for from further had has have having he
her here hers herself him himself his how i if in into is it its itself just me more most my myself new no nor not
now of off on once only or other our ours out over own said same says she should so some such than that the their
theirs them themselves then there these they this those through to too under until up very was we were what when
where which while who whom why will with would you your yours yourself first two one three last year years week day
days today yesterday latest live update updates news report reports reported according told may might must make
makes made get gets got take takes took back like still even since via per across near set sets could amid amidst
know known want wants call calls called see seen says say saying show shows showed people time times way world
""".split())

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-\.]*[A-Za-z]|[A-Za-z]")
_SUMMARY_TOKENS = 60


def _norm_token(w: str) -> str:
    """Lowercase + a light suffix stemmer (captured/captures/capture → captur)."""
    w = w.lower().strip(".'-’").replace(".", "")
    if w.endswith(("'s", "’s")):
        w = w[:-2]
    if w in _STOPWORDS:
        return w
    if len(w) > 5 and w.endswith("ing"):
        w = w[:-3]
    elif len(w) > 4 and w.endswith("ies"):
        w = w[:-3] + "y"
    elif len(w) > 4 and w.endswith(("ed", "es")):
        w = w[:-2]
    elif len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        w = w[:-1]
    if len(w) > 4 and w.endswith("e"):
        w = w[:-1]
    return w


def _split_words(text: str) -> List[str]:
    words = []
    for raw in _WORD_RE.findall(text or ""):
        words.extend(p for p in re.split(r"[-–]", raw) if p)  # Meza-Flores → Meza, Flores
    return words


def _tokens(text: str, limit: Optional[int] = None) -> List[str]:
    out = []
    for raw in _split_words(text):
        if raw.lower() in _STOPWORDS:
            continue
        w = _norm_token(raw)
        if len(w) > 2 and w not in _STOPWORDS:
            out.append(w)
            if limit and len(out) >= limit:
                break
    return out


def _proper_nouns(title: str) -> set:
    words = _split_words(title)
    # skip first word (sentence-case capital) and Title Case / ALL-CAPS headlines
    if sum(1 for w in words if w[:1].isupper()) > 0.8 * max(len(words), 1):
        return set()
    return {_norm_token(w) for w in words[1:] if w[:1].isupper()}


def _term_counts(article: Dict[str, Any]) -> Dict[str, float]:
    title = article.get("title", "")
    counts: Dict[str, float] = {}
    proper = _proper_nouns(title)
    for t in _tokens(title):
        counts[t] = counts.get(t, 0) + (3.0 if t in proper else 2.0)
    for t in _tokens(article.get("summary", ""), limit=_SUMMARY_TOKENS):
        counts[t] = counts.get(t, 0) + 1.0
    return counts


def _vectorize(articles: List[Dict[str, Any]]) -> List[Dict[str, float]]:
    tfs = [_term_counts(a) for a in articles]
    df: Dict[str, int] = {}
    for tf in tfs:
        for t in tf:
            df[t] = df.get(t, 0) + 1
    n = len(articles)
    vecs = []
    for tf in tfs:
        v = {t: (1 + math.log(c)) * (math.log((n + 1) / (df[t] + 1)) + 1) for t, c in tf.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vecs.append({t: x / norm for t, x in v.items()})
    return vecs


def _cos(a: Dict[str, float], b: Dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(t, 0.0) for t, x in a.items())


def _normalize(v: Dict[str, float]) -> Dict[str, float]:
    norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
    return {t: x / norm for t, x in v.items()}


def _parse_time(s: str) -> datetime:
    try:
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)


# ── Clustering ───────────────────────────────────────────────────────────────

def cluster_articles(articles: List[Dict[str, Any]], join_threshold: float = 0.27,
                     merge_threshold: float = 0.40) -> List[List[int]]:
    """Return clusters as lists of article indices."""
    if not articles:
        return []
    vecs = _vectorize(articles)
    order = sorted(range(len(articles)), key=lambda i: articles[i].get("published", ""))

    clusters: List[List[int]] = []
    sums: List[Dict[str, float]] = []
    cents: List[Dict[str, float]] = []

    for i in order:
        v = vecs[i]
        best, best_sim = -1, 0.0
        for c, cent in enumerate(cents):
            s = _cos(v, cent)
            if s > best_sim:
                best, best_sim = c, s
        if best >= 0 and best_sim >= join_threshold:
            clusters[best].append(i)
            acc = sums[best]
            for t, x in v.items():
                acc[t] = acc.get(t, 0.0) + x
            cents[best] = _normalize(acc)
        else:
            clusters.append([i])
            sums.append(dict(v))
            cents.append(dict(v))

    # Merge pass: combine stories whose centroids are very close
    merged = True
    while merged:
        merged = False
        for a in range(len(clusters)):
            for b in range(a + 1, len(clusters)):
                if _cos(cents[a], cents[b]) >= merge_threshold:
                    clusters[a].extend(clusters[b])
                    for t, x in sums[b].items():
                        sums[a][t] = sums[a].get(t, 0.0) + x
                    cents[a] = _normalize(sums[a])
                    del clusters[b], sums[b], cents[b]
                    merged = True
                    break
            if merged:
                break

    # Attach centroid similarity for representative choice
    for members, cent in zip(clusters, cents):
        for i in members:
            articles[i]["_centrality"] = _cos(vecs[i], cent)
    return clusters


# ── Story building ───────────────────────────────────────────────────────────

def _story_id(links: List[str]) -> str:
    return hashlib.sha1(min(links).encode("utf-8")).hexdigest()[:10]


def build_story(members: List[Dict[str, Any]], now: Optional[datetime] = None) -> Dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    members = sorted(members, key=lambda a: a.get("published", ""))

    # Representative headline: the most central article, nudging toward
    # center-rated outlets and ones with an image/description.
    def rep_score(a):
        side = outlet_meta(a["source"])["side"]
        return (a.get("_centrality", 0)
                + (0.06 if side == "center" else 0)
                + (0.02 if a.get("image_url") else 0)
                + min(len(a.get("summary", "")), 400) / 20000)
    rep = max(members, key=rep_score)

    outlets = []
    for a in members:
        o = resolve_outlet(a["source"])
        if o not in outlets:
            outlets.append(o)

    articles_out = []
    for a in members:
        meta = outlet_meta(a["source"])
        articles_out.append({
            "source": meta["name"],
            "feed": a.get("feed", a["source"]),
            "title": a.get("title", ""),
            "link": a.get("link", ""),
            "summary": (a.get("summary", "") or "")[:400],
            "published": a.get("published", ""),
            "image_url": a.get("image_url"),
            "bias": meta["bias"],
            "bias_label": meta["bias_label"],
            "side": meta["side"],
            "ownership": meta["ownership"],
            "owner": meta["owner"],
            "country": meta["country"],
        })

    times = [_parse_time(a.get("published", "")) for a in members]
    first_i = min(range(len(members)), key=lambda i: times[i])
    newest = max(times)
    combined_text = " ".join(a.get("summary", "")[:300] for a in members[:6])
    places = find_places(rep.get("title", ""), combined_text)

    image = rep.get("image_url") or next((a.get("image_url") for a in members if a.get("image_url")), None)
    bar = bias_bar_data(outlets)
    blind = blindspot_side(outlets)

    # Ranking: coverage first (unique outlets), a bonus for coverage from
    # more than one side, and decay with age (half-life 18h).
    age_h = max((now - newest).total_seconds() / 3600, 0)
    sides = sum(1 for k in ("left", "center", "right") if bar[k] > 0)
    score = (len(outlets) + 0.25 * len(members) + 0.75 * max(sides - 1, 0)) * (0.5 ** (age_h / 18)) \
        + (0.5 if blind else 0)

    story = {
        "id": _story_id([a.get("link", "") or a.get("title", "") for a in members]),
        "title": rep.get("title", ""),
        "link": rep.get("link", ""),
        "source": resolve_outlet(rep["source"]),
        "summary": rep.get("summary", ""),
        "image_url": image,
        "published": members[first_i].get("published", ""),
        "updated": newest.isoformat(),
        "first_reported": {"source": resolve_outlet(members[first_i]["source"]),
                           "published": members[first_i].get("published", "")},
        "all_sources": outlets,
        "source_count": len(outlets),
        "article_count": len(members),
        "articles": articles_out,
        "bias_breakdown": bias_breakdown(outlets),
        "bias_bar": bar,
        "blindspot": blind,                  # "left" = the LEFT is missing it
        "is_blindspot": blind is not None,
        "ownership_breakdown": ownership_breakdown(outlets),
        "topic": classify_topic(rep.get("title", ""), combined_text),
        "places": places,
        "region": primary_region(places),
        "score": round(score, 3),
        # Each article's text, used by the summarizer, not written to the site
        "_texts": [a.get("summary", "") for a in members],
    }
    return story


def group_articles(articles: List[Dict[str, Any]], similarity_threshold: Optional[float] = None,
                   join_threshold: float = 0.27, merge_threshold: float = 0.40) -> List[Dict[str, Any]]:
    """Cluster articles into stories (see module docstring)."""
    if not articles:
        return []
    if similarity_threshold is not None:  # old call signature
        join_threshold = similarity_threshold * 0.5
    logger.info(f"Grouping {len(articles)} articles into stories...")
    clusters = cluster_articles(articles, join_threshold, merge_threshold)
    now = datetime.now(timezone.utc)
    stories = [build_story([articles[i] for i in c], now) for c in clusters]

    # "Trending" = the most widely covered stories today
    multi = sorted((s["source_count"] for s in stories if s["source_count"] > 1), reverse=True)
    cutoff = max(3, multi[min(len(multi), 8) - 1]) if multi else 99
    for s in stories:
        s["is_trending"] = s["source_count"] >= cutoff

    n_multi = sum(1 for s in stories if s["source_count"] > 1)
    logger.info(f"Grouped into {len(stories)} stories ({n_multi} covered by 2+ outlets)")
    return stories


def filter_by_topics(stories: List[Dict[str, Any]], topics: List[str]) -> List[Dict[str, Any]]:
    """Keep stories mentioning at least one keyword from topics_of_interest."""
    if not topics:
        return stories
    keep = []
    for s in stories:
        text = " ".join([s.get("title", ""), s.get("summary", "")] +
                        [a["title"] for a in s.get("articles", [])]).lower()
        if any(t.lower() in text for t in topics):
            keep.append(s)
    logger.info(f"Topic filter: {len(stories)} → {len(keep)} stories")
    return keep


def sort_articles(stories: List[Dict[str, Any]], by_date: bool = False) -> List[Dict[str, Any]]:
    """Rank by coverage score (default) or by real timestamp, newest first."""
    if by_date:
        return sorted(stories, key=lambda s: _parse_time(s.get("updated") or s.get("published", "")),
                      reverse=True)
    return sorted(stories, key=lambda s: s.get("score", 0), reverse=True)


def cap_per_source(stories: List[Dict[str, Any]], max_per_source: int) -> List[Dict[str, Any]]:
    """
    Limit how many SINGLE-source stories one outlet can contribute, so a
    high-volume feed can't flood the digest. Multi-outlet stories are never
    dropped by this cap.
    """
    if not max_per_source or max_per_source <= 0:
        return stories
    counts: Dict[str, int] = {}
    out = []
    for s in stories:
        if s.get("source_count", len(s.get("all_sources", []))) > 1:
            out.append(s)
            continue
        src = s.get("source", "Unknown")
        if counts.get(src, 0) >= max_per_source:
            continue
        counts[src] = counts.get(src, 0) + 1
        out.append(s)
    if len(out) < len(stories):
        logger.info(f"Source cap ({max_per_source}/source): {len(stories)} → {len(out)} stories")
    return out


def process_articles(articles: List[Dict[str, Any]], config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Group → filter → rank → cap → limit."""
    cl = config.get("clustering", {}) or {}
    stories = group_articles(articles,
                             join_threshold=float(cl.get("join_threshold", 0.27)),
                             merge_threshold=float(cl.get("merge_threshold", 0.40)))
    stories = filter_by_topics(stories, config.get("topics_of_interest", []) or [])
    stories = sort_articles(stories)
    stories = cap_per_source(stories, config.get("max_stories_per_source", 0))
    final = stories[: config.get("max_stories_per_digest", 60)]
    logger.info(f"Processing complete: {len(articles)} articles → {len(final)} stories")
    return final


# Backwards-compatible names
dedupe_articles = group_articles


def similarity_ratio(s1: str, s2: str) -> float:
    from difflib import SequenceMatcher
    return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()


def extract_keywords(text: str) -> set:
    return set(_tokens(text))
