"""
dedupe.py - Groups similar stories across sources (Ground News-style)
instead of discarding duplicates. When multiple outlets cover the same
story, we keep all of them together as one digest entry, so you can see
who covered it and from what bias lean - rather than silently picking
one source and throwing the others away.
"""
from typing import List, Dict, Any, Set
from difflib import SequenceMatcher
import re
import logging

from bias import get_bias_label, bias_breakdown, is_blindspot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Common words that don't help identify a specific story - filtered out
# before comparing keyword overlap between titles.
_STOPWORDS = {
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
    'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
    'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that',
    'these', 'those', 'it', 'its', 'as', 'if', 'than', 'then', 'so',
    'such', 'not', 'no', 'also', 'said', 'says', 'new', 'after', 'over',
    'into', 'out', 'up', 'down', 'amid', 'amid', 'his', 'her', 'their',
    'first', 'two', 'one',
}

_WORD_RE = re.compile(r"[A-Za-z0-9']+")


def similarity_ratio(s1: str, s2: str) -> float:
    """
    Calculate similarity ratio between two strings (0 to 1).
    1.0 = identical, 0.0 = completely different
    """
    return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()


def extract_keywords(text: str) -> Set[str]:
    """
    Extract the significant words from a title/summary for keyword-overlap
    comparison - lowercased, stopwords removed, short words dropped.
    Proper nouns (people, places, organizations) tend to survive this
    filter since they're rarely stopwords, which is what lets two
    differently-worded headlines about the same story (e.g. "France
    confirms first Ebola case" vs "Doctor diagnosed with Ebola in France")
    still match on shared keywords like "france" and "ebola".
    """
    words = _WORD_RE.findall(text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def keyword_overlap_ratio(keywords1: Set[str], keywords2: Set[str]) -> float:
    """
    Overlap coefficient between two keyword sets (0 to 1): the fraction of
    the SMALLER set's keywords that also appear in the other set.

    This is deliberately not a Jaccard/union-based ratio - headlines are
    short, so a couple of shared proper nouns (e.g. "france", "ebola")
    can be the entire signal that two differently-worded headlines are
    about the same story, even though the rest of each headline's
    vocabulary differs completely. Jaccard would dilute that signal by
    dividing by the (large, mostly non-overlapping) union instead.
    """
    if not keywords1 or not keywords2:
        return 0.0
    intersection = keywords1 & keywords2
    smaller = min(len(keywords1), len(keywords2))
    return len(intersection) / smaller


def is_same_story(article1: Dict[str, Any], article2: Dict[str, Any],
                 title_threshold: float = 0.6,
                 keyword_threshold: float = 0.3) -> bool:
    """
    Decide whether two articles are covering the same underlying story,
    using two independent signals so paraphrased headlines still match:

    1. Raw title/summary string similarity (catches near-identical wording)
    2. Keyword overlap on title (catches same proper nouns/topic even when
       the wording is completely different)

    Either signal alone is enough to call it a match.
    """
    title_sim = similarity_ratio(article1['title'], article2['title'])
    summary_sim = similarity_ratio(
        article1.get('summary', ''),
        article2.get('summary', '')
    )

    if title_sim > title_threshold or summary_sim > title_threshold:
        return True

    keywords1 = extract_keywords(article1['title'] + ' ' + article1.get('summary', ''))
    keywords2 = extract_keywords(article2['title'] + ' ' + article2.get('summary', ''))
    if keyword_overlap_ratio(keywords1, keywords2) > keyword_threshold:
        return True

    return False


def group_articles(articles: List[Dict[str, Any]],
                  similarity_threshold: float = 0.6) -> List[Dict[str, Any]]:
    """
    Group articles covering the same story across different sources.

    Unlike a pure dedupe step, this keeps every source that covered the
    story - it just merges them into one entry with a list of
    "also_covered_by" sources, a bias breakdown, and a blindspot flag.

    Uses both string similarity and keyword overlap (see is_same_story)
    so two outlets covering the same event with completely different
    headline wording still get grouped together.

    Args:
        articles: List of article dicts
        similarity_threshold: Ratio above which two articles' titles/
            summaries are considered the same underlying story (0-1)

    Returns:
        List of grouped story dicts. Each has all the normal article
        fields (from whichever source had the longest summary) plus:
          - 'all_sources': list of every source name covering this story
          - 'bias_breakdown': dict of bias label -> count of sources
          - 'is_blindspot': True if all covering sources lean the same way
    """
    if not articles:
        return []

    logger.info(f"Grouping {len(articles)} articles into stories...")

    grouped = []
    seen_indices = set()

    for i, article1 in enumerate(articles):
        if i in seen_indices:
            continue

        group = [i]

        for j, article2 in enumerate(articles):
            if i >= j or j in seen_indices:
                continue

            # Don't group two articles from the same source - that's not
            # "multiple outlets covering a story", that's the same outlet
            # publishing twice (or a false-positive title match).
            if article1.get('source') == article2.get('source'):
                continue

            if is_same_story(article1, article2, title_threshold=similarity_threshold):
                group.append(j)
                seen_indices.add(j)

        # Pick the article with the longest summary as the "representative"
        # one (used for title/link/summary/published in the final entry)
        group_articles_list = [articles[idx] for idx in group]
        best = max(group_articles_list, key=lambda a: len(a.get('summary', '')))

        all_sources = [a.get('source', 'Unknown') for a in group_articles_list]

        merged = dict(best)
        merged['all_sources'] = all_sources
        merged['bias_breakdown'] = bias_breakdown(all_sources)
        merged['is_blindspot'] = is_blindspot(all_sources)

        grouped.append(merged)
        seen_indices.add(i)

    logger.info(f"Grouped into {len(grouped)} stories")

    multi_source = sum(1 for g in grouped if len(g['all_sources']) > 1)
    if multi_source:
        logger.info(f"{multi_source} stories have coverage from multiple sources")

    return grouped


def filter_by_topics(articles: List[Dict[str, Any]],
                    topics: List[str]) -> List[Dict[str, Any]]:
    """
    Filter articles that mention topics of interest.

    Args:
        articles: List of article dicts
        topics: List of keywords/topics to filter for

    Returns:
        Filtered list of articles containing at least one topic
    """
    if not topics:
        logger.info("No topics specified, returning all articles")
        return articles

    logger.info(f"Filtering by {len(topics)} topics: {topics}")

    filtered = []
    for article in articles:
        text = (article.get('title', '') + ' ' +
                article.get('summary', '')).lower()

        for topic in topics:
            if topic.lower() in text:
                filtered.append(article)
                break

    logger.info(f"Topic filter: {len(articles)} → {len(filtered)} articles")
    return filtered


def sort_articles(articles: List[Dict[str, Any]],
                 by_date: bool = True) -> List[Dict[str, Any]]:
    """
    Sort articles by date (newest first) and optionally by source.
    """
    if by_date:
        try:
            sorted_articles = sorted(
                articles,
                key=lambda x: x.get('published', ''),
                reverse=True
            )
            return sorted_articles
        except Exception as e:
            logger.warning(f"Could not sort by date: {e}")

    return articles


def cap_per_source(articles: List[Dict[str, Any]], max_per_source: int) -> List[Dict[str, Any]]:
    """
    Limit how many stories any single source can contribute to the final
    digest, so one high-volume feed (e.g. a source that happens to have
    posted a lot today) doesn't crowd out everything else. Assumes
    articles are already sorted by date (newest first) - keeps the
    earliest-seen (newest) ones per source.

    A story's "source" here is its representative/primary source (the one
    whose summary was longest when grouping) - "also_covered_by" sources
    don't count against this cap.
    """
    if not max_per_source or max_per_source <= 0:
        return articles

    capped = []
    counts: Dict[str, int] = {}

    for article in articles:
        source = article.get('source', 'Unknown')
        counts.setdefault(source, 0)
        if counts[source] >= max_per_source:
            continue
        counts[source] += 1
        capped.append(article)

    if len(capped) < len(articles):
        logger.info(f"Source cap ({max_per_source}/source): {len(articles)} → {len(capped)} stories")

    return capped


def process_articles(articles: List[Dict[str, Any]],
                    config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Full grouping and filtering pipeline.

    Args:
        articles: Raw articles list
        config: Configuration dict with 'topics_of_interest',
            'max_stories_per_digest', and 'max_stories_per_source'

    Returns:
        Processed and filtered story groups
    """
    # Step 1: Group same-story articles across sources
    grouped = group_articles(articles)

    # Step 2: Filter by topics
    topics = config.get('topics_of_interest', [])
    filtered = filter_by_topics(grouped, topics)

    # Step 3: Sort by date
    sorted_articles = sort_articles(filtered)

    # Step 4: Cap per-source contribution so one feed can't dominate
    max_per_source = config.get('max_stories_per_source', 0)
    source_capped = cap_per_source(sorted_articles, max_per_source)

    # Step 5: Limit to max stories overall
    max_stories = config.get('max_stories_per_digest', 10)
    final = source_capped[:max_stories]

    logger.info(f"Processing complete: {len(articles)} → {len(final)} final stories")
    return final


# Kept for backwards compatibility - some tests/old code call this name
dedupe_articles = group_articles


if __name__ == '__main__':
    # Test dedupe.py standalone
    test_articles = [
        {
            'title': 'Doctor diagnosed with Ebola after returning from Congo',
            'link': 'https://example.com/1',
            'source': 'NYT World',
            'summary': 'A French doctor has been diagnosed with Ebola.',
            'published': '2026-06-24T10:00:00',
            'type': 'rss'
        },
        {
            'title': 'France confirms first Ebola case',  # Same story, totally different wording
            'link': 'https://example.com/2',
            'source': 'BBC World',
            'summary': 'French health officials confirmed the country has its first Ebola case.',
            'published': '2026-06-24T09:00:00',
            'type': 'rss'
        },
        {
            'title': 'Iran loyalists promote wider nationalism',
            'link': 'https://example.com/3',
            'source': 'NYT World',
            'summary': 'Government supporters are showing off new ties with alleged former dissidents.',
            'published': '2026-06-24T08:00:00',
            'type': 'rss'
        }
    ]

    print("Test articles (before):")
    for i, a in enumerate(test_articles, 1):
        print(f"{i}. {a['title']} ({a['source']})")

    grouped = group_articles(test_articles)
    print(f"\nAfter grouping ({len(grouped)} stories):")
    for i, a in enumerate(grouped, 1):
        print(f"{i}. {a['title']}")
        print(f"   Sources: {a['all_sources']}")
        print(f"   Bias breakdown: {a['bias_breakdown']}")
        print(f"   Blindspot: {a['is_blindspot']}")
