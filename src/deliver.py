"""
deliver.py - Writes the markdown digest (latest_digest.md + a dated copy in
data/archive/) and optionally posts a summary to a Discord webhook.
"""
import html as html_module
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

import requests
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SIDE_NAME = {"left": "Left", "center": "Center", "right": "Right"}


def _clean(text: str) -> str:
    return html_module.unescape(str(text or ""))


def _bar_text(bar: Dict[str, Any]) -> str:
    return f"L {bar.get('left_pct', 0)}% · C {bar.get('center_pct', 0)}% · R {bar.get('right_pct', 0)}%"


def _bar_emoji(bar: Dict[str, Any], width: int = 10) -> str:
    l = round(bar.get("left_pct", 0) / 100 * width)
    r = round(bar.get("right_pct", 0) / 100 * width)
    c = max(width - l - r, 0)
    return "🟦" * l + "⬜" * c + "🟥" * r


def format_digest_markdown(stories: List[Dict[str, Any]], date: str = None) -> str:
    date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    multi = sum(1 for s in stories if s.get("source_count", 1) > 1)
    bl = sum(1 for s in stories if s.get("blindspot") == "left")
    br = sum(1 for s in stories if s.get("blindspot") == "right")

    md = [f"# News Digest - {date}", "",
          f"**{len(stories)} stories** · {multi} covered by 2+ outlets · "
          f"{bl + br} blindspot{'s' if bl + br != 1 else ''} ({bl} missed by the left, {br} missed by the right)",
          "", "Ranked by how widely each story was covered. Bias ratings: AllSides (outlet level).", "", "---", ""]

    for i, s in enumerate(stories, 1):
        title = _clean(s.get("title", "No title"))
        bar = s.get("bias_bar", {})
        md.append(f"## {i}. {'🔍 ' if s.get('blindspot') else ''}{title}")
        md.append("")
        meta = [f"**{s.get('topic', 'World')}**"]
        if s.get("places"):
            meta.append(", ".join(p["name"] for p in s["places"][:3]))
        meta.append(f"{s.get('source_count', 1)} source{'s' if s.get('source_count', 1) != 1 else ''}")
        meta.append(f"Coverage: {_bar_text(bar)}")
        md.append(" · ".join(meta))
        md.append("")
        if s.get("blindspot"):
            md.append(f"**Blindspot for the {SIDE_NAME[s['blindspot']]}:** covered mostly by "
                      f"{'right' if s['blindspot'] == 'left' else 'left'}-leaning outlets.")
            md.append("")
        for b in s.get("bullet_points", []):
            md.append(f"- {_clean(b)}")
        md.append("")
        if s.get("framing"):
            for side in ("left", "center", "right"):
                if s["framing"].get(side):
                    md.append(f"> **{SIDE_NAME[side]}:** {_clean(s['framing'][side])}")
            md.append("")
        arts = s.get("articles") or [{"source": s.get("source"), "title": title, "link": s.get("link"),
                                      "bias_label": ""}]
        if len(arts) > 1:
            md.append("**Headlines by outlet:**")
            md.append("")
            for a in arts:
                label = f" ({a['bias_label']})" if a.get("bias_label") else ""
                md.append(f"- {a['source']}{label}: [{_clean(a['title'])}]({a.get('link', '')})")
        else:
            a = arts[0]
            md.append(f"**Source:** [{a['source']}]({a.get('link', '')})"
                      + (f" ({a['bias_label']})" if a.get("bias_label") else ""))
        md.append("")
    return "\n".join(md)


def format_digest_text(stories: List[Dict[str, Any]], limit: int = 10) -> str:
    """Compact text version (used for Discord)."""
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    out = [f"**News Digest - {today}**", ""]
    for i, s in enumerate(stories[:limit], 1):
        flag = f" 🔍 Blindspot for the {SIDE_NAME[s['blindspot']]}" if s.get("blindspot") else ""
        out.append(f"**{i}. [{_clean(s.get('title'))}](<{s.get('link', '')}>)**")
        out.append(f"{_bar_emoji(s.get('bias_bar', {}))} {s.get('source_count', 1)} sources{flag}")
        out.append("")
    return "\n".join(out)


def archive_digest(stories: List[Dict[str, Any]], archive_dir: str = None) -> str:
    """Write data/archive/digest_YYYY-MM-DD.md (overwrites same-day re-runs)."""
    try:
        archive = Path(archive_dir) if archive_dir else PROJECT_ROOT / "data" / "archive"
        archive.mkdir(parents=True, exist_ok=True)
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = archive / f"digest_{date}.md"
        path.write_text(format_digest_markdown(stories, date), encoding="utf-8")
        logger.info(f"Digest archived to {path}")
        return str(path)
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error archiving digest: {e}")
        return ""


def update_latest_digest(stories: List[Dict[str, Any]], output_path: str = None) -> str:
    try:
        path = Path(output_path) if output_path else PROJECT_ROOT / "latest_digest.md"
        path.write_text(format_digest_markdown(stories), encoding="utf-8")
        logger.info(f"Updated latest digest at {path}")
        return str(path)
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error updating latest digest: {e}")
        return ""


def send_to_discord(stories: List[Dict[str, Any]]) -> bool:
    """Optional: post the top stories to DISCORD_WEBHOOK_URL if it is set."""
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url or "your_discord" in webhook_url:
        return False
    try:
        text = format_digest_text(stories)
        site = os.getenv("SITE_URL")
        if site:
            text += f"\nFull digest: {site}"
        if len(text) > 1990:
            text = text[:1985] + "\n…"
        r = requests.post(webhook_url, json={"content": text}, timeout=10)
        ok = r.status_code in (200, 204)
        (logger.info if ok else logger.error)(f"Discord delivery {'ok' if ok else 'failed: ' + str(r.status_code)}")
        return ok
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error sending to Discord: {e}")
        return False


def deliver_all(stories: List[Dict[str, Any]], archive: bool = True) -> Dict[str, bool]:
    results = {"latest_digest": update_latest_digest(stories) != ""}
    if archive:
        results["archive"] = archive_digest(stories) != ""
    results["discord"] = send_to_discord(stories)
    logger.info(f"Delivery complete: {results}")
    return results
