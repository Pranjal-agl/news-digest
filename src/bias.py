"""
bias.py - Static bias/lean lookup for news sources, Ground News-style.

These ratings are simplified, source-level political-lean labels (not
per-article fact-checks), based on AllSides Media Bias Ratings
(allsides.com/media-bias/ratings) as of mid-2026. They're a rough signal,
not a precise score - if you disagree with a label, just edit this dict.
"""
from typing import Dict, List, Any

# Lean: "left", "lean-left", "center", "lean-right", "right", "unrated"
SOURCE_BIAS: Dict[str, str] = {
    "BBC World": "center",
    "Christian Science Monitor World": "center",
    "Deutsche Welle Top Stories": "center",
    "WSJ World News": "center",
    "NYT World": "lean-left",
    "Al Jazeera": "lean-left",
    "NPR World": "lean-left",
    "The Guardian World": "lean-left",
    "CBC World": "lean-left",
    "New York Post World": "lean-right",
    "Washington Times World": "lean-right",
    "Fox News World": "right",
}

_LABELS = {
    "left": "Left",
    "lean-left": "Lean Left",
    "center": "Center",
    "lean-right": "Lean Right",
    "right": "Right",
    "unrated": "Unrated",
}


def get_bias(source_name: str) -> str:
    """Return the bias category for a source name, defaulting to 'unrated'."""
    return SOURCE_BIAS.get(source_name, "unrated")


def get_bias_label(source_name: str) -> str:
    """Return a human-readable bias label for a source name."""
    return _LABELS.get(get_bias(source_name), "Unrated")


def bias_breakdown(sources: List[str]) -> Dict[str, int]:
    """
    Given a list of source names covering one story, count how many fall
    into each bias category.
    """
    counts = {label: 0 for label in _LABELS.values()}
    for source in sources:
        counts[get_bias_label(source)] += 1
    return {k: v for k, v in counts.items() if v > 0}


def is_blindspot(sources: List[str]) -> bool:
    """
    A simple Ground-News-style blindspot check: True if every source
    covering this story leans the same direction (left-ish or right-ish),
    with no center or opposite-side coverage at all. Needs at least 2
    sources to be meaningful.
    """
    if len(sources) < 2:
        return False

    leans = {get_bias(s) for s in sources}
    left_leaning = {"left", "lean-left"}
    right_leaning = {"right", "lean-right"}

    if leans and leans.issubset(left_leaning):
        return True
    if leans and leans.issubset(right_leaning):
        return True
    return False
