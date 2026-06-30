# Daily News Digest Bot

Automated daily world news digest, inspired by Ground News. Runs on GitHub
Actions, fetches news from 8 RSS feeds spanning the political spectrum,
groups same-story coverage across outlets, flags political-bias
blindspots, summarizes each story with a free local summarizer (no API
key needed), and writes the result as a markdown file right in this repo.

## Status: Ready for Production

## How it works
1. GitHub Actions cron triggers daily at 8 AM
2. Fetches articles from 12 RSS feeds spanning Right to Center to Left:
   - **Right:** Fox News
   - **Lean Right:** New York Post, Washington Times
   - **Center:** BBC, Christian Science Monitor, Deutsche Welle, WSJ World News
   - **Lean Left:** NYT, NPR, Al Jazeera, The Guardian, CBC
3. Groups articles covering the same story across different outlets using
   both string similarity and keyword overlap, so two outlets with
   completely different headline wording about the same event still get
   matched (rather than just deduplicating one away)
4. Tags each story with a bias breakdown (e.g. "Center: 1 · Lean Left: 2")
   and flags "blindspot" stories that only one side of the spectrum covered
5. Summarizes each story into bullet points - locally, for free, no signup
6. Caps each source at 10 stories so no single outlet dominates the digest
7. Writes `latest_digest.md` (always up to date) and archives a dated copy to `data/archive/`
8. Generates a static HTML page at `docs/index.html` for GitHub Pages, with
   color-coded bias tags and blindspots surfaced at the top
9. (Optional) Also posts to a Discord webhook if you set one up

## Viewing the digest as a website
This repo includes a self-contained static site generator (no JS
framework, no build step) that writes `docs/index.html` every run. To turn
that into a live URL:

1. Go to your repo's **Settings → Pages**
2. Under **Source**, choose **Deploy from a branch**
3. Branch: `main`, folder: `/docs`
4. Save - GitHub will give you a URL like `https://<username>.github.io/<repo>/`

After the next pipeline run (manual or scheduled), that URL will show the
latest digest with bias-colored tags and blindspots highlighted.

## Setup
1. Clone repo
2. `pip install -r requirements.txt`
3. That's it - no API keys or accounts are required.
4. Optional: copy `.env.example` to `.env` and set `DISCORD_WEBHOOK_URL` if you also want Discord delivery.
5. Edit `config.yaml` to change RSS sources, the per-source cap, or filter by topics of interest.
6. Edit `src/bias.py` if you disagree with a source's bias label, or add new sources there too.

## Tech stack
- Python 3.11
- `feedparser` - RSS parsing (with hard timeouts so a slow feed can't hang the whole run)
- A small built-in extractive summarizer (pure Python, no external AI API)
- A static AllSides-based bias lookup for source-level political lean
- A keyword-overlap + string-similarity grouping algorithm that catches
  paraphrased headlines about the same story across outlets
- A dependency-free static HTML generator for GitHub Pages
- GitHub Actions - scheduling + auto-commit of the digest back to the repo

## Roadmap
- [x] Repo scaffold
- [x] RSS fetch (8 sources, left/center/right spread)
- [x] Story grouping across sources (Ground News-style) + bias breakdown
- [x] Blindspot detection
- [x] Per-source story cap
- [x] Free local summarization (no API key)
- [x] Markdown digest delivery (committed to repo)
- [x] GitHub Actions cron
- [x] Smarter grouping (keyword overlap, catches paraphrased headlines)
- [x] Static HTML site for GitHub Pages
- [ ] Topic-based filtering/scoring
- [ ] Weekly rollup report
- [ ] GitHub Pages archive site

## Example output
```
# News Digest - 2026-06-29

## 1. France Identifies Its First Case of Ebola

**Source:** [NYT World](https://example.com/1)

**Also covered by:** BBC World

**Bias breakdown:** Lean Left: 1 · Center: 1

- A doctor who had traveled to the Democratic Republic of Congo was infected.
- The authorities said the risk to the wider population was low.
```

## A note on bias ratings
With 12 sources spanning Right, Lean Right, Center, and Lean Left (per
AllSides), this is a meaningfully more balanced spread than free RSS
typically offers by default - Center alone now has 4 outlets (BBC, CSM,
DW, WSJ World News) instead of just one. There's still no pure "Left"
outlet and only one pure "Right" outlet (Fox News), simply because credible
options in those exact categories with free public RSS feeds are scarce.
If you find more, add them to `config.yaml` and `src/bias.py`.

## License
MIT
