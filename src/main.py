"""
main.py - Orchestrates the AI News Digest pipeline
"""
import yaml
import logging
import sys
from pathlib import Path
from datetime import datetime

# Import pipeline modules
from fetch import fetch_all_articles, verify_rss_url
from dedupe import process_articles
from summarize import summarize_articles, configure_gemini
from deliver import deliver_all

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config(config_path: str = None) -> dict:
    """Load configuration from YAML file.

    Resolves config.yaml relative to the project root (one level up from
    this file's src/ directory) by default, so this works whether you run
    `python main.py` from src/ or `python src/main.py` from the repo root.
    """
    if config_path is None:
        project_root = Path(__file__).resolve().parent.parent
        config_path = str(project_root / 'config.yaml')

    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        logger.info(f"Loaded config from {config_path}")
        return config
    except FileNotFoundError:
        logger.error(f"Config file not found: {config_path}")
        return {}
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return {}


def verify_rss_urls(config: dict) -> dict:
    """
    Verify all RSS URLs are accessible.
    Removes invalid URLs from config.
    """
    rss_sources = config.get('sources', {}).get('rss', [])
    
    logger.info(f"Verifying {len(rss_sources)} RSS URLs...")
    
    valid_sources = []
    for source in rss_sources:
        url = source.get('url')
        if verify_rss_url(url):
            valid_sources.append(source)
        else:
            logger.warning(f"Skipping invalid RSS source: {source.get('name')}")
    
    config['sources']['rss'] = valid_sources
    logger.info(f"Valid RSS sources: {len(valid_sources)}/{len(rss_sources)}")
    
    return config


def run_pipeline(config: dict) -> bool:
    """
    Run the complete News Digest pipeline.
    
    Pipeline:
    1. Fetch articles from RSS (verifies/skips bad feeds internally)
    2. Deduplicate and filter by topics
    3. Summarize (local, free, no API key)
    4. Save digest as markdown + (optionally) post to Discord
    
    Returns:
        True if successful, False if failed
    """
    try:
        logger.info("=" * 60)
        logger.info("Starting News Digest Pipeline")
        logger.info(f"Timestamp: {datetime.now().isoformat()}")
        logger.info("=" * 60)
        
        # Step 1: Fetch articles (verification happens per-source inside fetch)
        logger.info("\n[Step 1] Fetching articles...")
        articles = fetch_all_articles(config)
        
        if not articles:
            logger.error("No articles fetched. Aborting.")
            return False
        
        logger.info(f"Fetched {len(articles)} articles")
        
        # Step 2: Deduplicate and filter
        logger.info("\n[Step 2] Deduplicating and filtering...")
        processed = process_articles(articles, config)
        
        if not processed:
            logger.error("No articles after deduplication. Aborting.")
            return False
        
        logger.info(f"Processed to {len(processed)} articles")
        
        # Step 3: Summarize (local, free, no signup needed)
        logger.info("\n[Step 3] Summarizing articles...")
        configure_gemini()  # no-op kept for compatibility; logs that it's free/local
        processed = summarize_articles(processed)
        logger.info(f"Summarized {len(processed)} articles")
        
        # Step 4: Save digest as markdown (+ optional Discord)
        logger.info("\n[Step 4] Delivering digest...")
        results = deliver_all(processed, archive=True)
        
        success_count = sum(1 for v in results.values() if v)
        logger.info(f"Delivered to {success_count}/{len(results)} channels")
        
        logger.info("\n" + "=" * 60)
        logger.info("Pipeline Complete!")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        return False


def main():
    """Main entry point."""
    logger.info("AI News Digest Bot - Main Pipeline")
    
    # Load config
    config = load_config()
    
    if not config:
        logger.error("Failed to load configuration. Exiting.")
        return 1
    
    # Run pipeline
    success = run_pipeline(config)
    
    return 0 if success else 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
