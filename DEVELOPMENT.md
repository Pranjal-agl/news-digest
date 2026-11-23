# Development Guide

## Local Setup

### Prerequisites
- Python 3.11+
- Git

### 1. Clone and Install

```bash
git clone <repo-url>
cd news-digest
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

```bash
python test.py        # offline unit tests (also run by CI before every digest)
python test.py live   # fetch every configured feed and report which ones work
```

## Running the Pipeline

### Manual Execution (Local)

```bash
python src/main.py
```

This will:
1. Fetch every configured RSS feed in parallel
2. Group articles into cross-outlet stories and compute bias, blindspots, ownership, topics
3. Summarize locally (free), plus optional AI framing if `ANTHROPIC_API_KEY` is set
4. Write `latest_digest.md` and `data/archive/digest_YYYY-MM-DD.md`
5. Write the site data (`docs/data.json`, `docs/data/*.json`) and copy `web/index.html` to `docs/`
6. Write the weekly rollup and (optionally) post to Discord

### Via GitHub Actions

The workflow runs automatically at 8 AM UTC daily via [GitHub Actions](.github/workflows/daily-digest.yml),
and commits the updated digest files back to the repo - no secrets required
unless you want Discord delivery too.

To test the workflow manually:
1. Go to **Actions** tab in your GitHub repo
2. Select **Daily News Digest** workflow
3. Click **Run workflow** → **Run workflow**

### Enabling GitHub Pages (optional)

The pipeline writes `docs/index.html` every run. To get a live URL for it:

1. Repo **Settings → Pages**
2. **Source:** Deploy from a branch
3. **Branch:** `main`, folder: `/docs`
4. Save

GitHub will publish at `https://<username>.github.io/<repo>/` and update it
automatically every time the workflow commits a new digest.

### Adding GitHub Secrets (optional)

Only needed if you want Discord delivery in addition to the markdown digest:

1. Go to repo **Settings** → **Secrets and variables** → **Actions**
2. Add: `DISCORD_WEBHOOK_URL`

## Project Structure

```
src/
├── fetch.py      # Parallel RSS fetch, date parsing, opinion/age filtering, feed health
├── dedupe.py     # TF-IDF story clustering, coverage stats, ranking
├── bias.py       # Outlet registry (AllSides bias, ownership) + bias bar / blindspot maths
├── topics.py     # Topic and country/region tagging
├── summarize.py  # Multi-source extractive summaries (free, local)
├── llm.py        # Optional Claude headlines/summaries/framing (needs ANTHROPIC_API_KEY)
├── deliver.py    # Markdown digest + optional Discord
├── htmlsite.py   # Writes docs/ data files and copies the site template
├── weekly.py     # Weekly rollup (site + markdown)
└── main.py       # Orchestrates the pipeline

web/index.html    # The site (single file, vanilla JS). Edit this, not docs/index.html
docs/             # Generated GitHub Pages output
data/archive/     # Daily markdown digests
data/weekly/      # Weekly markdown rollups
test.py           # Offline tests; `python test.py live` checks feeds
```

## Debugging

### Test RSS URLs

Check every feed at once:
```bash
python test.py live
```
The site's **Sources** page also shows which feeds failed on the latest run.

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
- [x] Cross-outlet story grouping, blindspots, ownership
- [x] Topic tagging and coverage-based ranking
- [x] Weekly rollup report
- [x] GitHub Pages archive site

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
2. Verify pipeline runs: `python src/main.py`
3. Check archives: `ls -la data/archive/`
4. Push changes and let GitHub Actions verify

## License

MIT
