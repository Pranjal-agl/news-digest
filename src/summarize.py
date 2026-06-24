"""
summarize.py - Summarizes articles into bullet points.

No API key, no signup, no cost, no rate limits: this uses a simple local
extractive summarizer (pure Python, no downloads required) instead of
calling an external AI API. It picks the most representative sentences
from each article's existing summary/description text.

If you ever want to swap in a real LLM later, replace summarize_article()
below - everything else in the pipeline (rate limiting, batching) stays
the same.
"""
import re
import logging
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Common words that don't carry much meaning - used to score sentences
_STOPWORDS = {
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
    'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
    'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that',
    'these', 'those', 'it', 'its', 'as', 'if', 'than', 'then', 'so',
    'such', 'not', 'no', 'also', 'said', 'says',
}

_TAG_RE = re.compile(r'<[^>]+>')
_WORD_RE = re.compile(r"[A-Za-z']+")
_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+')


def _strip_html(text: str) -> str:
    """Remove HTML tags that RSS summaries sometimes include."""
    return _TAG_RE.sub(' ', text or '').strip()


def _split_sentences(text: str) -> List[str]:
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
    return sentences


def _score_sentences(sentences: List[str]) -> List[float]:
    """
    Score each sentence by how many notable (non-stopword) words it shares
    with the rest of the text - a simple, dependency-free stand-in for
    proper TF-IDF/LexRank scoring.
    """
    word_freq: Dict[str, int] = {}
    for sentence in sentences:
        for word in _WORD_RE.findall(sentence.lower()):
            if word not in _STOPWORDS and len(word) > 2:
                word_freq[word] = word_freq.get(word, 0) + 1

    scores = []
    for sentence in sentences:
        words = [w for w in _WORD_RE.findall(sentence.lower())
                 if w not in _STOPWORDS and len(w) > 2]
        if not words:
            scores.append(0.0)
            continue
        score = sum(word_freq.get(w, 0) for w in words) / len(words)
        scores.append(score)
    return scores


def summarize_article(article: Dict[str, Any], max_points: int = 3) -> Dict[str, Any]:
    """
    Summarize a single article by extracting its most representative
    sentences. No external API calls.

    Args:
        article: Dict with title, link, summary, source
        max_points: Maximum number of bullet points to produce

    Returns:
        Article dict with added 'bullet_points' key
    """
    title = article.get('title', '')
    raw_content = _strip_html(article.get('summary', ''))

    if not raw_content:
        logger.warning(f"No content to summarize for: {title}")
        article['bullet_points'] = ['No description available']
        return article

    sentences = _split_sentences(raw_content)

    if not sentences:
        article['bullet_points'] = [raw_content[:200]]
        return article

    if len(sentences) <= max_points:
        article['bullet_points'] = sentences
        return article

    scores = _score_sentences(sentences)
    # Keep top-scoring sentences, but preserve their original order
    ranked_indices = sorted(range(len(sentences)), key=lambda i: scores[i], reverse=True)
    top_indices = sorted(ranked_indices[:max_points])
    article['bullet_points'] = [sentences[i] for i in top_indices]

    logger.info(f"Summarized: {title[:60]}")
    return article


def summarize_articles(articles: List[Dict[str, Any]],
                      rate_limit_delay: float = 0.0) -> List[Dict[str, Any]]:
    """
    Summarize multiple articles.

    Args:
        articles: List of article dicts
        rate_limit_delay: Kept for backwards compatibility with main.py's
            pipeline call signature. Unused since there's no external API
            to rate-limit against anymore.

    Returns:
        Articles with 'bullet_points' added
    """
    summarized = []

    for i, article in enumerate(articles, 1):
        logger.info(f"[{i}/{len(articles)}] Summarizing: {article.get('title', '')[:60]}")
        summarized.append(summarize_article(article))

    logger.info(f"Summarization complete: {len(summarized)}/{len(articles)} articles")
    return summarized


def configure_gemini():
    """
    Kept as a no-op for backwards compatibility with main.py, which calls
    this before summarizing. There's no external API to configure anymore -
    summarization runs fully locally, for free, with no signup.
    """
    logger.info("Using local extractive summarizer - no API key needed")


if __name__ == '__main__':
    # Test summarize.py standalone
    test_articles = [
        {
            'title': 'World leaders meet for climate summit',
            'link': 'https://example.com/1',
            'source': 'BBC World',
            'summary': """
            World leaders gathered today for an emergency climate summit in Geneva.
            The meeting comes after a series of record-breaking heatwaves swept across
            three continents this summer. Officials are expected to discuss new emissions
            targets and funding for developing nations. Several environmental groups have
            criticized the pace of negotiations as too slow. The summit is scheduled to
            conclude on Friday with a joint statement.
            """,
            'published': '2026-06-19T10:00:00',
            'type': 'rss'
        },
    ]

    print("\nSummarizing test articles...\n")
    results = summarize_articles(test_articles)

    print("\n--- Results ---\n")
    for article in results:
        print(f"Title: {article['title']}")
        print(f"Source: {article['source']}")
        print("Summary:")
        for point in article.get('bullet_points', []):
            print(f"  - {point}")
        print()
