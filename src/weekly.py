"""
weekly.py - Weekly rollup built from the last 7 daily data files.

Writes docs/data/weekly.json (the site's "This week" page) and
data/weekly/week_YYYY-Www.md (a markdown report in the repo). The same
story often appears on several days with different wording, so stories are
de-duplicated by headline/outlet overlap and the day with the widest
coverage is kept.
"""
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)
_WORD = re.compile(r"[a-z]{4,}")


def _words(t: str) -> set:
    return set(_WORD.findall((t or "").lower()))


def _same(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    wa, wb = _words(a["title"]), _words(b["title"])
    if not wa or not wb:
        return False
    return len(wa & wb) / min(len(wa), len(wb)) >= 0.5


def build_weekly(data_dir: Path, days: int = 7, top_n: int = 25, today: datetime = None) -> Dict[str, Any]:
    today = today or datetime.now(timezone.utc)
    start = (today - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    files = [p for p in sorted(data_dir.glob("????-??-??.json")) if p.stem >= start]
    candidates, cov = [], {"left": 0, "center": 0, "right": 0}
    for p in files:
        try:
            day = json.load(open(p, encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for s in day.get("stories", []):
            s = dict(s, date=p.stem)
            s.pop("articles", None)
            candidates.append(s)
        ct = day.get("coverage_today") or {}
        for k in cov:
            cov[k] += ct.get(k, 0)

    candidates.sort(key=lambda s: (-s.get("source_count", 1), s["date"]))
    picked: List[Dict[str, Any]] = []
    for s in candidates:
        if not any(_same(s, p) for p in picked):
            picked.append(s)

    n = sum(cov.values()) or 1
    coverage = {**cov, **{f"{k}_pct": round(v / n * 100) for k, v in cov.items()}}
    return {
        "start": start,
        "end": today.strftime("%Y-%m-%d"),
        "days": len(files),
        "coverage": coverage,
        "stats": {
            "stories": len(picked),
            "blindspots": sum(1 for s in picked if s.get("blindspot")),
            "blindspot_left": sum(1 for s in picked if s.get("blindspot") == "left"),
            "blindspot_right": sum(1 for s in picked if s.get("blindspot") == "right"),
        },
        "stories": picked[:top_n],
    }


def weekly_markdown(w: Dict[str, Any]) -> str:
    md = [f"# Weekly rollup: {w['start']} to {w['end']}", "",
          f"**{w['stats']['stories']} distinct stories** across {w['days']} daily digests. "
          f"Blindspots: {w['stats']['blindspot_left']} missed by the left, "
          f"{w['stats']['blindspot_right']} missed by the right.", "",
          f"Share of the week's articles by outlet lean: Left {w['coverage']['left_pct']}%, "
          f"Center {w['coverage']['center_pct']}%, Right {w['coverage']['right_pct']}%.", "", "---", ""]
    for i, s in enumerate(w["stories"], 1):
        bar = s.get("bias_bar") or {}
        flag = f" — Blindspot for the {s['blindspot'].title()}" if s.get("blindspot") else ""
        md.append(f"## {i}. [{s['title']}]({s.get('link', '')})")
        md.append(f"{s['date']} · {s.get('source_count', 1)} sources · "
                  f"L {bar.get('left_pct', 0)}% / C {bar.get('center_pct', 0)}% / R {bar.get('right_pct', 0)}%{flag}")
        md.append("")
    return "\n".join(md)


def write_weekly(docs_dir: str, archive_dir: str) -> str:
    data_dir = Path(docs_dir) / "data"
    w = build_weekly(data_dir)
    if not w["stories"]:
        return ""
    with open(data_dir / "weekly.json", "w", encoding="utf-8") as f:
        json.dump(w, f, ensure_ascii=False, indent=1)
    iso = datetime.now(timezone.utc).isocalendar()
    md_path = Path(archive_dir) / f"week_{iso[0]}-W{iso[1]:02d}.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(weekly_markdown(w), encoding="utf-8")
    logger.info(f"Weekly rollup: {len(w['stories'])} stories → {md_path}")
    return str(md_path)
