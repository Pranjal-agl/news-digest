"""
main.py - Runs the News Digest pipeline:

  fetch → group into stories → summarize → (optional AI framing)
        → markdown digest + archive → site data → weekly rollup
"""
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fetch import fetch_all_articles, FEED_STATUS  # noqa: E402
from dedupe import process_articles  # noqa: E402
from summarize import summarize_articles  # noqa: E402
from llm import enrich_stories  # noqa: E402
from deliver import deliver_all  # noqa: E402
from htmlsite import generate_site  # noqa: E402
from weekly import write_weekly  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_config(config_path: str = None) -> dict:
    path = Path(config_path) if config_path else PROJECT_ROOT / "config.yaml"
    try:
        with open(path) as f:
            config = yaml.safe_load(f) or {}
        logger.info(f"Loaded config from {path}")
        return config
    except FileNotFoundError:
        logger.error(f"Config file not found: {path}")
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error loading config: {e}")
    return {}


def run_pipeline(config: dict, articles: list = None) -> bool:
    """Run every step. `articles` can be passed in to skip fetching (tests)."""
    try:
        logger.info(f"Starting News Digest pipeline at {datetime.now(timezone.utc).isoformat()}")

        if articles is None:
            articles = fetch_all_articles(config)
        if not articles:
            logger.error("No articles fetched. Aborting.")
            return False

        stories = process_articles(articles, config)
        if not stories:
            logger.error("No stories after grouping. Aborting.")
            return False

        summarize_articles(stories)
        enrich_stories(stories, config)

        deliver_all(stories, archive=True)

        docs_dir = PROJECT_ROOT / "docs"
        generate_site(stories, output_dir=str(docs_dir), feed_status=dict(FEED_STATUS))
        try:
            write_weekly(str(docs_dir), str(PROJECT_ROOT / "data" / "weekly"))
        except Exception as e:  # noqa: BLE001 - weekly is a nice-to-have
            logger.warning(f"Weekly rollup skipped: {e}")

        logger.info("Pipeline complete")
        return True
    except Exception as e:  # noqa: BLE001
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        return False


def main() -> int:
    config = load_config()
    if not config:
        return 1
    return 0 if run_pipeline(config) else 1


if __name__ == "__main__":
    sys.exit(main())
