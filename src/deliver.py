"""
deliver.py - Formats the digest and saves it as a markdown file in the repo.

No Discord/Telegram setup needed: the digest is written to data/archive/
and a top-level latest_digest.md is updated each run. When run via GitHub
Actions, the workflow commits these files back to the repo automatically -
so "delivery" is just an updated doc you can read on GitHub.
"""
import os
import logging
from typing import List, Dict, Any
import requests
from datetime import datetime
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


def format_digest_text(articles: List[Dict[str, Any]]) -> str:
    """
    Format articles into readable digest text (plain, for logs/console).
    """
    today = datetime.now().strftime('%B %d, %Y')
    digest = f"News Digest - {today}\n\n"

    for i, article in enumerate(articles, 1):
        title = article.get('title', 'No title')
        link = article.get('link', '')
        source = article.get('source', 'Unknown')
        bullets = article.get('bullet_points', ['No summary'])

        digest += f"{i}. [{title}]({link})\n"
        digest += f"   *Source: {source}*\n"

        for bullet in bullets:
            digest += f"   - {bullet}\n"

        digest += "\n"

    return digest


def format_digest_markdown(articles: List[Dict[str, Any]]) -> str:
    """
    Format articles as markdown (for archiving / the latest-digest doc).
    """
    today = datetime.now().strftime('%Y-%m-%d')
    digest = f"# News Digest - {today}\n\n"

    for i, article in enumerate(articles, 1):
        title = article.get('title', 'No title')
        link = article.get('link', '')
        source = article.get('source', 'Unknown')
        bullets = article.get('bullet_points', ['No summary'])

        digest += f"## {i}. {title}\n\n"
        digest += f"**Source:** [{source}]({link})\n\n"

        for bullet in bullets:
            digest += f"- {bullet}\n"

        digest += "\n"

    return digest


def archive_digest(articles: List[Dict[str, Any]],
                  archive_dir: str = 'data/archive') -> str:
    """
    Save digest to a dated markdown file.

    Args:
        articles: List of article dicts
        archive_dir: Directory to save to

    Returns:
        Path to saved file
    """
    try:
        os.makedirs(archive_dir, exist_ok=True)

        today = datetime.now().strftime('%Y-%m-%d')
        filename = f"{archive_dir}/digest_{today}.md"

        # Don't overwrite if already exists
        if os.path.exists(filename):
            logger.info(f"Archive file already exists: {filename}")
            return filename

        digest_md = format_digest_markdown(articles)

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(digest_md)

        logger.info(f"Digest archived to {filename}")
        return filename

    except Exception as e:
        logger.error(f"Error archiving digest: {e}")
        return ""


def update_latest_digest(articles: List[Dict[str, Any]],
                        output_path: str = 'latest_digest.md') -> str:
    """
    Overwrite a top-level "latest digest" markdown file. This is the file
    you'd open on GitHub to see today's news at a glance, rather than
    digging through the dated archive folder.

    Args:
        articles: List of article dicts
        output_path: Path to the latest-digest file (repo root by default)

    Returns:
        Path to the written file, or "" on failure
    """
    try:
        digest_md = format_digest_markdown(articles)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(digest_md)
        logger.info(f"Updated latest digest at {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Error updating latest digest: {e}")
        return ""


def send_to_discord(articles: List[Dict[str, Any]]) -> bool:
    """
    Optional: send digest to a Discord webhook, if DISCORD_WEBHOOK_URL is
    set. This is entirely optional now - the markdown file delivery above
    works with zero setup.
    """
    webhook_url = os.getenv('DISCORD_WEBHOOK_URL')

    if not webhook_url:
        return False

    try:
        digest_text = format_digest_text(articles)

        if len(digest_text) > 1900:
            digest_text = digest_text[:1900] + "\n... (truncated)"

        payload = {"content": digest_text}
        response = requests.post(webhook_url, json=payload, timeout=10)

        if response.status_code in [200, 204]:
            logger.info("Discord delivery successful")
            return True
        else:
            logger.error(f"Discord delivery failed: {response.status_code}")
            return False

    except Exception as e:
        logger.error(f"Error sending to Discord: {e}")
        return False


def deliver_all(articles: List[Dict[str, Any]],
               archive: bool = True) -> Dict[str, bool]:
    """
    Deliver the digest: write the markdown archive + latest-digest doc,
    and optionally post to Discord if a webhook is configured.

    Args:
        articles: List of article dicts
        archive: Whether to save to the dated archive folder

    Returns:
        Dict with delivery status for each channel
    """
    logger.info(f"Starting delivery of {len(articles)} articles...")

    results = {
        'latest_digest': update_latest_digest(articles) != "",
    }

    if archive:
        results['archive'] = archive_digest(articles) != ""

    # Optional, only runs if DISCORD_WEBHOOK_URL is set in the environment
    results['discord'] = send_to_discord(articles)

    logger.info(f"Delivery complete: {results}")
    return results


if __name__ == '__main__':
    # Test deliver.py standalone
    test_articles = [
        {
            'title': 'World leaders meet for climate summit',
            'link': 'https://example.com/1',
            'source': 'BBC World',
            'bullet_points': [
                'World leaders gathered for an emergency climate summit in Geneva',
                'Officials are expected to discuss new emissions targets',
                'The summit concludes Friday with a joint statement'
            ],
            'published': '2026-06-19T10:00:00',
            'type': 'rss'
        },
    ]

    print("Testing digest formatting...\n")
    print(format_digest_text(test_articles))

    print("\n--- Archive Format ---\n")
    print(format_digest_markdown(test_articles))

    print("\n--- Delivery Simulation ---\n")
    results = deliver_all(test_articles, archive=True)
    print(f"Results: {results}")
