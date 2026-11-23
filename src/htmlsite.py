"""
htmlsite.py - Writes the GitHub Pages site into docs/.

  docs/index.html          the app (copied from web/index.html every run, so
                           design changes in web/ always go live)
  docs/data.json           today's stories, sources and stats
  docs/data/YYYY-MM-DD.json  a copy per day, for the Archive page
  docs/data/index.json     list of archived days
  docs/.nojekyll           tells Pages to serve files as-is

The app is a single self-contained HTML file with vanilla JS: no build step.
"""
import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

from bias import OUTLETS, outlet_meta, bias_bar_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = PROJECT_ROOT / "web" / "index.html"
_PRIVATE_KEYS = {"_texts", "_centrality"}
MAX_ARCHIVE_DAYS = 400


def _public_story(s: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in s.items() if k not in _PRIVATE_KEYS}


def coverage_today(stories: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Left/center/right share of all of today's articles (by outlet lean)."""
    counts = {"left": 0, "center": 0, "right": 0}
    total = 0
    for s in stories:
        for a in s.get("articles", []):
            total += 1
            if a.get("side") in counts:
                counts[a["side"]] += 1
    n = sum(counts.values()) or 1
    out = {f"{k}_pct": round(v / n * 100) for k, v in counts.items()}
    out.update(counts)
    out["articles"] = total
    return out


def sources_report(stories: List[Dict[str, Any]], feed_status: Optional[Dict[str, Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """One row per outlet: metadata + whether its feed(s) loaded + articles used."""
    used: Dict[str, int] = {}
    for s in stories:
        for a in s.get("articles", []):
            used[a["source"]] = used.get(a["source"], 0) + 1

    rows: Dict[str, Dict[str, Any]] = {}
    for fs in (feed_status or {}).values():
        meta = outlet_meta(fs["outlet"])
        row = rows.setdefault(meta["name"], {**meta, "ok": False, "fetched": 0, "error": "", "feeds": []})
        row["feeds"].append(fs["feed"])
        row["ok"] = row["ok"] or fs["ok"]
        row["fetched"] += fs.get("articles", 0)
        if fs.get("error"):
            row["error"] = fs["error"]
    for name in used:
        if name not in rows:
            rows[name] = {**outlet_meta(name), "ok": None, "fetched": None, "error": "", "feeds": []}
    for name, row in rows.items():
        row["articles"] = used.get(name, 0)
        row.pop("domain", None)
    return list(rows.values())


def build_payload(stories: List[Dict[str, Any]], feed_status: Optional[Dict[str, Dict[str, Any]]] = None,
                  now: Optional[datetime] = None) -> Dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    src = sources_report(stories, feed_status)
    feeds_total = len(feed_status or {})
    feeds_ok = sum(1 for f in (feed_status or {}).values() if f["ok"])
    return {
        "date": now.strftime("%Y-%m-%d"),
        "generated_at": now.isoformat(),
        "stats": {
            "total": len(stories),
            "multi_source": sum(1 for s in stories if s.get("source_count", 1) > 1),
            "trending": sum(1 for s in stories if s.get("is_trending")),
            "blindspots": sum(1 for s in stories if s.get("blindspot")),
            "blindspot_left": sum(1 for s in stories if s.get("blindspot") == "left"),
            "blindspot_right": sum(1 for s in stories if s.get("blindspot") == "right"),
            "articles": sum(s.get("article_count", 1) for s in stories),
            "sources_ok": feeds_ok if feeds_total else len(src),
            "sources_total": feeds_total or len(src),
        },
        "coverage_today": coverage_today(stories),
        "sources": src,
        "stories": [_public_story(s) for s in stories],
    }


def _write_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def update_index(data_dir: Path) -> Dict[str, Any]:
    """Rebuild data/index.json from the per-day files present."""
    days = []
    for p in sorted(data_dir.glob("????-??-??.json"), reverse=True)[:MAX_ARCHIVE_DAYS]:
        try:
            with open(p, encoding="utf-8") as f:
                st = json.load(f).get("stats", {})
        except (OSError, json.JSONDecodeError):
            continue
        days.append({"date": p.stem, "total": st.get("total", 0), "blindspots": st.get("blindspots", 0),
                     "multi_source": st.get("multi_source", 0)})
    index = {"updated": datetime.now(timezone.utc).isoformat(), "days": days}
    _write_json(data_dir / "index.json", index)
    return index


def generate_site(articles: List[Dict[str, Any]], output_dir: str = "docs",
                  feed_status: Optional[Dict[str, Dict[str, Any]]] = None) -> str:
    """Write the site. Returns the path to data.json, or "" on failure."""
    try:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        payload = build_payload(articles, feed_status)

        _write_json(out / "data.json", payload)
        _write_json(out / "data" / f"{payload['date']}.json", payload)
        update_index(out / "data")

        (out / ".nojekyll").touch()
        if TEMPLATE.exists():
            shutil.copyfile(TEMPLATE, out / "index.html")
        else:
            logger.warning(f"Site template missing at {TEMPLATE}; leaving docs/index.html unchanged")

        logger.info(f"Site written: {payload['stats']['total']} stories → {out}")
        return str(out / "data.json")
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error generating site: {e}", exc_info=True)
        return ""
