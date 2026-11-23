"""
llm.py - Optional AI layer (off unless ANTHROPIC_API_KEY is set).

For the most widely covered stories it asks Claude for:
  - a neutral headline,
  - a 3-bullet summary drawn only from the outlets' own text,
  - a short "how each side framed it" comparison (Ground News's Bias
    Comparison feature), plus what all sides agree on.

Uses the Anthropic Messages API over plain HTTPS (no SDK dependency). Any
failure just leaves the free local summary in place, so the pipeline never
breaks because of this step.
"""
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-haiku-5-5"

_PROMPT = """You are writing for a news aggregator that shows how outlets across the political spectrum cover the same story.

Below are headlines and descriptions from {n} outlets about one story, grouped by the outlet's AllSides bias rating.

{blocks}

Using ONLY the information in these texts (do not add facts), return a JSON object with:
- "headline": a neutral, factual headline of at most 14 words, without loaded words from any one side.
- "summary": an array of 3 short bullet strings stating the key facts.
- "framing": an object with keys "left", "center", "right". For each side that has coverage, 1-2 sentences describing what that side's outlets emphasise or how they frame the story (word choice, which angle leads). Use null for a side with no coverage.
- "common_ground": one sentence on what all covering outlets agree on.

Return only the JSON object."""


def is_enabled(config: Dict[str, Any]) -> bool:
    setting = str((config.get("llm") or {}).get("enabled", "auto")).lower()
    if setting in ("false", "off", "no", "0"):
        return False
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def _blocks(story: Dict[str, Any]) -> str:
    groups = {"left": [], "center": [], "right": []}
    for a in story.get("articles", []):
        side = a.get("side")
        if side in groups and len(groups[side]) < 5:
            text = (a.get("summary") or "")[:300]
            groups[side].append(f"- {a['source']} ({a['bias_label']}): {a['title']}\n  {text}")
    out = []
    for side, label in (("left", "LEFT-LEANING"), ("center", "CENTER"), ("right", "RIGHT-LEANING")):
        out.append(f"## {label} OUTLETS\n" + ("\n".join(groups[side]) if groups[side] else "(no coverage)"))
    return "\n\n".join(out)


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def analyze_story(story: Dict[str, Any], model: str = DEFAULT_MODEL, api_key: Optional[str] = None,
                  timeout: int = 60) -> Optional[Dict[str, Any]]:
    api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    prompt = _PROMPT.format(n=story.get("source_count", 0), blocks=_blocks(story))
    try:
        r = requests.post(
            API_URL,
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": model, "max_tokens": 700, "messages": [{"role": "user", "content": prompt}]},
            timeout=timeout,
        )
        r.raise_for_status()
        text = "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"LLM call failed for '{story.get('title', '')[:50]}': {e}")
        return None
    data = _extract_json(text)
    if not data or not isinstance(data.get("summary"), list):
        logger.warning("LLM returned unparseable output; keeping local summary")
        return None
    return data


def enrich_stories(stories: List[Dict[str, Any]], config: Dict[str, Any]) -> int:
    """Add AI headline/summary/framing to the top multi-source stories. Returns count enriched."""
    if not is_enabled(config):
        logger.info("LLM layer off (no ANTHROPIC_API_KEY) - using local summaries")
        return 0
    cfg = config.get("llm") or {}
    model = cfg.get("model", DEFAULT_MODEL)
    limit = int(cfg.get("max_stories", 15))
    done = 0
    for story in [s for s in stories if s.get("source_count", 0) >= 2][:limit]:
        data = analyze_story(story, model=model)
        if not data:
            continue
        story["original_title"] = story.get("title")
        if data.get("headline"):
            story["title"] = str(data["headline"]).strip()
        story["bullet_points"] = [str(b).strip() for b in data["summary"] if str(b).strip()][:4] or story.get("bullet_points", [])
        framing = data.get("framing") or {}
        story["framing"] = {k: framing.get(k) for k in ("left", "center", "right") if framing.get(k)}
        if data.get("common_ground"):
            story["common_ground"] = str(data["common_ground"]).strip()
        story["ai_summary"] = True
        done += 1
    logger.info(f"LLM enriched {done} stories with {model}")
    return done
