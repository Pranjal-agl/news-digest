# Development Guide

## Local Setup

### Prerequisites
- Python 3.11+
- Git

### 1. Clone and Install

```bash
git clone <repo-url>
cd ai-news-digest-bot
pip install -r requirements.txt
```

### 2. (Optional) Configure Environment

No API keys are required to run the digest. If you'd also like Discord
delivery, copy `.env.example` to `.env` and set `DISCORD_WEBHOOK_URL`:

```bash
cp .env.example .env
```

- **DISCORD_WEBHOOK_URL** (optional): Create in Discord server (Server Settings → Webhooks)

### 3. Update config.yaml

Edit `config.yaml` to customize:
- RSS feed sources (verify URLs are current)
- Topics of interest (leave empty to keep all stories)
- Max stories per digest

### 4. Test Components

Test individual modules before running the full pipeline:

```bash
# Test all components
python test.py

# Or test specific component
python test.py config
python test.py fetch
python test.py dedupe
python test.py summarize
python test.py deliver
python test.py pipeline
```

## Running the Pipeline

### Manual Execution (Local)

```bash
cd src
python main.py
```

This will:
1. Fetch articles from configured RSS sources
2. Deduplicate and filter by topics
3. Summarize locally (free, no API key)
4. Write `latest_digest.md` and archive to `data/archive/`
5. (Optional) Post to Discord if `DISCORD_WEBHOOK_URL` is set

### Via GitHub Actions

The workflow runs automatically at 8 AM UTC daily via [GitHub Actions](.github/workflows/daily-digest.yml),
and commits the updated digest files back to the repo - no secrets required
unless you want Discord delivery too.

To test the workflow manually:
1. Go to **Actions** tab in your GitHub repo
2. Select **Daily News Digest** workflow
3. Click **Run workflow** → **Run workflow**

### Adding GitHub Secrets (optional)

Only needed if you want Discord delivery in addition to the markdown digest:

1. Go to repo **Settings** → **Secrets and variables** → **Actions**
2. Add: `DISCORD_WEBHOOK_URL`

## Project Structure

```
src/
├── fetch.py          # RSS fetching with URL verification
├── dedupe.py         # Deduplication and topic filtering
├── summarize.py      # Free local extractive summarization (no API key)
├── deliver.py        # Markdown digest writer + optional Discord delivery
├── main.py           # Orchestrates the full pipeline
└── __init__.py       # Package initialization

data/
└── archive/          # Daily digest markdown files

latest_digest.md      # Always-current digest, updated every run

.github/
└── workflows/
    └── daily-digest.yml   # GitHub Actions cron job

config.yaml          # Sources, topics, settings
requirements.txt     # Python dependencies
.env.example        # Environment variables template (all optional)
```

## Debugging

### Enable Debug Logging

Add `DEBUG=true` to `.env` for verbose logging.

### Test RSS URLs

Verify an RSS URL manually:
```python
from src.fetch import verify_rss_url
verify_rss_url('https://feeds.bbci.co.uk/news/world/rss.xml')
```

### Simulate Full Run

```bash
python src/main.py
```

Check output for:
- ✓ Articles fetched count
- ✓ Deduplicated count
- ✓ Summarization status
- ✓ Delivery status

### Check Archives

Past digests are saved in `data/archive/` as markdown files with format `digest_YYYY-MM-DD.md`.
The most recent digest is always also available at `latest_digest.md` in the repo root.

## Roadmap

- [x] Repo scaffold
- [x] RSS fetch
- [x] Dedup logic
- [x] Free local summarization (no API key)
- [x] Markdown digest delivery
- [x] GitHub Actions cron
- [ ] Topic-based filtering/scoring (scoring coming next)
- [ ] Weekly rollup report
- [ ] GitHub Pages archive site

## Common Issues

### RSS URLs Not Resolving

News sites occasionally change their RSS paths. Run:
```bash
python test.py fetch
```

to verify current URLs and update `config.yaml` accordingly.

### Discord Webhook Errors

Discord delivery is optional. Verify the webhook URL is valid and hasn't
expired if you've set one up; otherwise just leave `DISCORD_WEBHOOK_URL` unset.

## Contributing

1. Test changes locally: `python test.py`
2. Verify pipeline runs: `cd src && python main.py`
3. Check archives: `ls -la data/archive/`
4. Push changes and let GitHub Actions verify

## License

MIT
