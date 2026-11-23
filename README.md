# News Digest

A free, self-hosted, Ground News-style daily world news digest. It runs on
GitHub Actions, pulls ~20 RSS feeds from across the political spectrum,
groups each outlet's article into one **story**, and shows each story's
**bias distribution**, its **blindspot** (if one side ignored it), **who owns
the coverage** and **every outlet's headline side by side**. It publishes
a static site to GitHub Pages and a markdown digest to the repo.

No API keys are needed. An optional AI layer adds neutral headlines and
"how each side framed it" summaries if you add an Anthropic API key.

## What you get

**Site (GitHub Pages, `docs/`)**
- **Top stories**, ranked by how many outlets covered them, with a left/center/right bias bar and a topic filter
- **Story page**: summary, a **headlines across the spectrum** comparison (Left | Center | Right),
  all articles filterable by lean, coverage details (source counts, first reported by, last updated),
  an ownership breakdown and related stories
- **Blindspot** feed: stories missed by the left or by the right, using Ground News's published formula
- **This week**: the most widely covered stories of the last 7 days
- **My news bias**: tracks which side the articles you open come from (stored only in your browser)
- **Sources**: every outlet's AllSides rating, owner, ownership type, and whether its feed loaded today
- **Archive** of every past day, plus search, dark mode and a mobile layout

**Repo**
- `latest_digest.md` and `data/archive/digest_YYYY-MM-DD.md` (headlines by outlet, coverage, blindspots)
- `data/weekly/week_YYYY-Www.md` weekly rollup
- Optional Discord post with emoji bias bars

## How it works
1. **Fetch** (`src/fetch.py`): all feeds in parallel, every entry (not just the top 10), real UTC
   timestamps, drops items older than 48h and opinion pieces, strips feed boilerplate, and records feed health.
2. **Group** (`src/dedupe.py`): TF-IDF vectors over headline and description (proper nouns weighted up,
   words every outlet uses today weighted down), then centroid clustering, so paraphrased headlines from
   different outlets land in the same story without unrelated stories chaining together.
3. **Score** each story: unique outlets, bias bar, Ground News blindspot formula, ownership mix, topic,
   places/regions, and a ranking score (coverage, cross-spectrum bonus, recency decay).
4. **Summarize** (`src/summarize.py`): pools sentences from *every* outlet's description and picks the
   3 most central, non-redundant ones. Optionally (`src/llm.py`) Claude writes a neutral headline,
   a summary and a left/center/right framing comparison for the top stories.
5. **Publish**: markdown digest, `docs/data.json` plus per-day archive files, the weekly rollup, and
   `docs/index.html` (copied from `web/index.html` every run).

## Setup
1. `pip install -r requirements.txt`
2. `python test.py` (offline tests) and `python test.py live` (checks every feed)
3. `python src/main.py`
4. **GitHub Pages**: Settings → Pages → Deploy from a branch → `main`, folder `/docs`.

Optional secrets (Settings → Secrets and variables → Actions):
- `ANTHROPIC_API_KEY`: enables AI headlines, summaries and framing for the top 15 stories (`llm:` in `config.yaml`)
- `DISCORD_WEBHOOK_URL`: posts the top 10 stories to Discord

## Sources and ratings
| Lean | Outlets |
|---|---|
| Left | HuffPost |
| Lean Left | NYT, NPR, Al Jazeera, The Guardian, CBC, The Independent, Sky News |
| Center | BBC, Christian Science Monitor, Deutsche Welle, WSJ, The Hill, Newsweek |
| Lean Right | New York Post, Washington Times, Washington Examiner, Daily Mail |
| Right | Fox News, Breitbart |

Ratings are AllSides outlet-level ratings (checked Nov 2026). Ownership categories follow Ground News's
scheme and are best-effort. To add or re-rate an outlet, add the feed to `config.yaml` and the outlet to
`OUTLETS` in `src/bias.py` (a test fails if a configured feed has no rating). The Sources page shows
which feeds failed on the latest run.

## Configuration (`config.yaml`)
- `fetch`: entries per feed, max article age, timeout/retries, opinion filtering
- `clustering.join_threshold` / `merge_threshold`: lower values group more aggressively
- `max_stories_per_digest`, `max_stories_per_source` (caps single-source stories only)
- `topics_of_interest`: keyword filter
- `llm`: optional AI layer
- How often it runs: `cron` in `.github/workflows/daily-digest.yml`

## Roadmap
- [x] Cross-outlet story grouping with bias bar and Ground News blindspot formula
- [x] Story pages with headline comparison, ownership and coverage details
- [x] Topic and region tagging, search, archive site, weekly rollup, My news bias
- [x] Optional AI neutral summaries and framing comparison
- [ ] Factuality ratings (Ground News averages Ad Fontes + MBFC)
- [ ] Track developing stories across days (story timelines)
- [ ] More sources, plus local/regional feeds (e.g. Indian outlets)
- [ ] Email / RSS output of the digest itself

## License
MIT
