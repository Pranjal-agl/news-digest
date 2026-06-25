# Daily News Digest Bot

Automated daily world news digest. Runs on GitHub Actions, fetches news
from RSS feeds, deduplicates similar stories, summarizes each one with a
free local summarizer (no API key needed), and writes the result as a
markdown file right in this repo.

## Status: Phase 0 Complete

## How it works
1. GitHub Actions cron triggers daily at 8 AM
2. Fetches articles from configured RSS feeds (BBC World, Al Jazeera, NPR, NYT)
3. Deduplicates similar stories
4. Summarizes each story into bullet points - locally, for free, no signup
5. Writes `latest_digest.md` (always up to date) and archives a dated copy to `data/archive/`
6. (Optional) Also posts to a Discord webhook if you set one up

## Setup
1. Clone repo
2. `pip install -r requirements.txt`
3. That's it - no API keys or accounts are required.
4. Optional: copy `.env.example` to `.env` and set `DISCORD_WEBHOOK_URL` if you also want Discord delivery.
5. Edit `config.yaml` to change RSS sources or filter by topics of interest.

## Tech stack
- Python 3.11
- `feedparser` - RSS parsing
- A small built-in extractive summarizer (pure Python, no external AI API)
- GitHub Actions - scheduling + auto-commit of the digest back to the repo

## Roadmap
- [x] Repo scaffold
- [x] RSS fetch
- [x] Dedup logic
- [x] Free local summarization (no API key), might change in future
- [x] Markdown digest delivery (committed to repo)
- [x] GitHub Actions cron
- [ ] Topic-based filtering/scoring
- [ ] Weekly rollup report
- [ ] GitHub Pages archive site

## Example output
```
# News Digest - 2026-06-23

## 1. World leaders meet for climate summit

**Source:** [BBC World](https://example.com/1)

- World leaders gathered for an emergency climate summit in Geneva
- Officials are expected to discuss new emissions targets
- The summit concludes Friday with a joint statement
```

## License
MIT
