"""
dedupe.py - Deduplicates and filters similar stories
"""
from typing import List, Dict, Any
from difflib import SequenceMatcher
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def similarity_ratio(s1: str, s2: str) -> float:
    """
    Calculate similarity ratio between two strings (0 to 1).
    1.0 = identical, 0.0 = completely different
    """
    return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()


def dedupe_articles(articles: List[Dict[str, Any]], 
                   similarity_threshold: float = 0.75) -> List[Dict[str, Any]]:
    """
    Remove duplicate and very similar articles.
    
    Strategy:
    1. Exact title matches → keep RSS over Reddit (more authoritative)
    2. Similar titles (> threshold) → keep the one with longer summary
    3. Check for similar summaries too
    
    Args:
        articles: List of article dicts
        similarity_threshold: Ratio above which articles are considered duplicates (0-1)
    
    Returns:
        Deduplicated list of articles
    """
    if not articles:
        return []
    
    logger.info(f"Starting deduplication on {len(articles)} articles...")
    
    kept_articles = []
    seen_indices = set()
    
    for i, article1 in enumerate(articles):
        if i in seen_indices:
            continue
        
        duplicates = [i]
        
        # Find all similar articles
        for j, article2 in enumerate(articles):
            if i >= j or j in seen_indices:
                continue
            
            title_sim = similarity_ratio(article1['title'], article2['title'])
            summary_sim = similarity_ratio(
                article1.get('summary', ''),
                article2.get('summary', '')
            )
            
            # Mark as duplicate if titles OR summaries are very similar
            if title_sim > similarity_threshold or summary_sim > similarity_threshold:
                duplicates.append(j)
                seen_indices.add(j)
        
        # Choose the best article from duplicates
        best = article1
        for dup_idx in duplicates[1:]:
            dup = articles[dup_idx]
            
            # Prefer RSS (more authoritative)
            if article1['type'] == 'reddit' and dup['type'] == 'rss':
                best = dup
            # For same type, prefer longer summary
            elif len(dup.get('summary', '')) > len(best.get('summary', '')):
                best = dup
            # For Reddit, prefer higher score
            elif article1['type'] == 'reddit' and dup['type'] == 'reddit':
                if dup.get('score', 0) > best.get('score', 0):
                    best = dup
        
        kept_articles.append(best)
        seen_indices.add(i)
    
    logger.info(f"Deduplicated to {len(kept_articles)} unique articles")
    
    if len(kept_articles) < len(articles):
        removed = len(articles) - len(kept_articles)
        logger.info(f"Removed {removed} duplicate/similar articles")
    
    return kept_articles


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


def process_articles(articles: List[Dict[str, Any]], 
                    config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Full dedup and filtering pipeline.
    
    Args:
        articles: Raw articles list
        config: Configuration dict with 'topics_of_interest' and 'max_stories_per_digest'
    
    Returns:
        Processed and filtered articles
    """
    # Step 1: Deduplicate
    deduped = dedupe_articles(articles)
    
    # Step 2: Filter by topics
    topics = config.get('topics_of_interest', [])
    filtered = filter_by_topics(deduped, topics)
    
    # Step 3: Sort by date
    sorted_articles = sort_articles(filtered)
    
    # Step 4: Limit to max stories
    max_stories = config.get('max_stories_per_digest', 10)
    final = sorted_articles[:max_stories]
    
    logger.info(f"Processing complete: {len(articles)} → {len(final)} final articles")
    return final


if __name__ == '__main__':
    # Test dedupe.py standalone
    test_articles = [
        {
            'title': 'OpenAI releases new model',
            'link': 'https://example.com/1',
            'source': 'OpenAI Blog',
            'summary': 'OpenAI announces a powerful new language model',
            'published': '2026-06-19T10:00:00',
            'type': 'rss'
        },
        {
            'title': 'OpenAI releases new model',  # Duplicate
            'link': 'https://reddit.com/1',
            'source': 'r/MachineLearning',
            'summary': 'OpenAI releases a new language model with better performance',
            'published': '2026-06-19T09:00:00',
            'type': 'reddit',
            'score': 5000
        },
        {
            'title': 'New OpenAI model released today',  # Similar
            'link': 'https://techcrunch.com/1',
            'source': 'TechCrunch',
            'summary': 'OpenAI unveils a new model',
            'published': '2026-06-19T11:00:00',
            'type': 'rss'
        },
        {
            'title': 'Anthropic announces breakthrough in AI safety',
            'link': 'https://example.com/2',
            'source': 'Anthropic News',
            'summary': 'Anthropic publishes research on AI safety alignment',
            'published': '2026-06-19T08:00:00',
            'type': 'rss'
        }
    ]
    
    print("Test articles (before):")
    for i, a in enumerate(test_articles, 1):
        print(f"{i}. {a['title']} ({a['source']})")
    
    deduped = dedupe_articles(test_articles)
    print(f"\nAfter deduplication ({len(deduped)} articles):")
    for i, a in enumerate(deduped, 1):
        print(f"{i}. {a['title']} ({a['source']})")
