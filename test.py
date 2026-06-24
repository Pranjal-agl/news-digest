#!/usr/bin/env python3
"""
test.py - Test individual components of the AI News Digest Bot
Run this to verify each module works correctly.
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import argparse
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_config():
    """Test configuration loading."""
    print("\n" + "="*60)
    print("Testing: Config Loading")
    print("="*60)
    
    try:
        import yaml
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        print(f"Config loaded successfully")
        print(f"  - RSS sources: {len(config.get('sources', {}).get('rss', []))}")
        print(f"  - Topics tracked: {len(config.get('topics_of_interest', []))}")
        print(f"  - Max stories: {config.get('max_stories_per_digest', 10)}")
        return True
    except Exception as e:
        print(f"Config test failed: {e}")
        return False


def test_fetch():
    """Test article fetching."""
    print("\n" + "="*60)
    print("Testing: Article Fetching")
    print("="*60)
    
    try:
        from fetch import fetch_all_articles, verify_rss_url
        import yaml
        
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        # Verify URLs first
        rss_sources = config.get('sources', {}).get('rss', [])
        print(f"\nVerifying {len(rss_sources)} RSS URLs...")
        
        valid = 0
        for source in rss_sources:
            if verify_rss_url(source['url']):
                valid += 1
        
        print(f"{valid}/{len(rss_sources)} RSS URLs verified")
        
        # Fetch articles
        print("\nFetching articles (RSS only)...")
        articles = fetch_all_articles(config)
        
        if articles:
            print(f"Fetched {len(articles)} articles")
            for i, article in enumerate(articles[:3], 1):
                print(f"  {i}. {article['title'][:60]}")
            return True
        else:
            print("✗ No articles fetched")
            return False
            
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("  Run: pip install -r requirements.txt")
        return False
    except Exception as e:
        print(f"Fetch test failed: {e}")
        return False


def test_dedupe():
    """Test deduplication."""
    print("\n" + "="*60)
    print("Testing: Deduplication")
    print("="*60)
    
    try:
        from dedupe import dedupe_articles, filter_by_topics
        
        # Create test data
        test_articles = [
            {
                'title': 'OpenAI Releases New Model',
                'source': 'OpenAI',
                'summary': 'OpenAI announces a new language model',
                'type': 'rss',
                'link': 'https://example.com/1'
            },
            {
                'title': 'OpenAI Releases New Model',  # Duplicate
                'source': 'Reddit',
                'summary': 'OpenAI releases a new language model',
                'type': 'reddit',
                'link': 'https://reddit.com/1',
                'score': 5000
            },
            {
                'title': 'Anthropic AI Safety Research',
                'source': 'Anthropic',
                'summary': 'New research on AI safety alignment',
                'type': 'rss',
                'link': 'https://example.com/2'
            }
        ]
        
        print(f"\nInput: {len(test_articles)} articles (1 duplicate)")
        
        deduped = dedupe_articles(test_articles)
        print(f"Deduplicated to {len(deduped)} unique articles")
        
        for i, article in enumerate(deduped, 1):
            print(f"  {i}. {article['title'][:50]} ({article['source']})")
        
        return True
        
    except Exception as e:
        print(f"Dedup test failed: {e}")
        return False


def test_summarize():
    """Test the local summarizer (free, no API key needed)."""
    print("\n" + "="*60)
    print("Testing: Local Summarization")
    print("="*60)

    try:
        from summarize import configure_gemini, summarize_article

        configure_gemini()  # no-op, just logs that it's free/local

        # Test with sample article
        test_article = {
            'title': 'Test Article',
            'source': 'Test',
            'summary': 'This is a test article about world news. Global events are unfolding rapidly. '
                       'Analysts say more details will emerge over the coming days.',
            'link': 'https://example.com/test'
        }

        print("\nSummarizing test article...")
        result = summarize_article(test_article)

        print("Summarization successful (no API key needed)")
        print(f"  Bullet points:")
        for point in result.get('bullet_points', []):
            print(f"    - {point}")

        return True

    except Exception as e:
        print(f"Summarize test failed: {e}")
        return False


def test_deliver():
    """Test delivery formatting."""
    print("\n" + "="*60)
    print("Testing: Delivery Formatting")
    print("="*60)
    
    try:
        from deliver import format_digest_text, format_digest_markdown
        
        test_articles = [
            {
                'title': 'Test Article',
                'source': 'Test Source',
                'link': 'https://example.com/1',
                'bullet_points': ['Point 1', 'Point 2']
            }
        ]
        
        print("\nFormatting digest...")
        
        text_format = format_digest_text(test_articles)
        print("Text format generated")
        print(f"  Length: {len(text_format)} chars")
        
        md_format = format_digest_markdown(test_articles)
        print("Markdown format generated")
        print(f"  Length: {len(md_format)} chars")
        
        return True
        
    except Exception as e:
        print(f"Deliver test failed: {e}")
        return False


def test_full_pipeline():
    """Test full pipeline."""
    print("\n" + "="*60)
    print("Testing: Full Pipeline")
    print("="*60)
    
    try:
        from pathlib import Path
        sys.path.insert(0, 'src')
        from main import load_config, verify_rss_urls
        
        config = load_config()
        config = verify_rss_urls(config)
        
        print("Full pipeline setup successful")
        print(f"  Config loaded with {len(config.get('sources', {}).get('rss', []))} valid RSS sources")
        
        return True
        
    except Exception as e:
        print(f"Full pipeline test failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Test AI News Digest Bot components'
    )
    parser.add_argument(
        'test',
        nargs='?',
        default='all',
        choices=['config', 'fetch', 'dedupe', 'summarize', 'deliver', 'pipeline', 'all'],
        help='Which test to run (default: all)'
    )
    
    args = parser.parse_args()
    
    tests = {
        'config': test_config,
        'fetch': test_fetch,
        'dedupe': test_dedupe,
        'summarize': test_summarize,
        'deliver': test_deliver,
        'pipeline': test_full_pipeline,
    }
    
    if args.test == 'all':
        results = {}
        for name, test_func in tests.items():
            try:
                results[name] = test_func()
            except Exception as e:
                print(f"FAIL: {name} test error: {e}")
                results[name] = False
        
        print("\n" + "="*60)
        print("Test Summary")
        print("="*60)
        passed = sum(1 for v in results.values() if v)
        total = len(results)
        print(f"Passed: {passed}/{total}")
        
        for name, result in results.items():
            status = "PASS" if result else "FAIL"
            print(f"  {status}: {name}")
        
        return 0 if passed == total else 1
    else:
        test_func = tests[args.test]
        result = test_func()
        return 0 if result else 1


if __name__ == '__main__':
    exit(main())
