"""
fetch.py - Fetches articles from RSS feeds.

No accounts, no API keys, no signup needed - just public RSS feeds.
"""
import feedparser
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# feedparser.parse() has no built-in timeout, and if it's given a URL it
# will use urllib under the hood, which can hang for minutes on a slow or
# unresponsive server. To avoid that, we always fetch raw bytes ourselves
# with `requests` (which DOES support a timeout) and hand those bytes to
# feedparser instead of letting it fetch the URL itself.
REQUEST_TIMEOUT = 10  # seconds


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
