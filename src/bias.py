"""
bias.py - Outlet registry: political lean, ownership and country for every
source, plus the Ground News-style coverage maths (bias bar, blindspots).

Bias labels are AllSides Media Bias Ratings (allsides.com/media-bias/ratings),
checked Nov 2026. They are outlet-level ratings of online news content, not
per-article judgements. If you disagree with one, edit OUTLETS below.

Ownership categories follow Ground News's scheme (ground.news/rating-system):
Media Conglomerate, Private Equity, Individual, Government, Telecom,
Corporation, Independent, Other. The category assignments here are
best-effort and worth double-checking before you rely on them.
"""
from typing import Dict, List, Any, Optional

BIAS_ORDER = ["left", "lean-left", "center", "lean-right", "right"]

LABELS = {
    "left": "Left",
    "lean-left": "Lean Left",
    "center": "Center",
    "lean-right": "Lean Right",
    "right": "Right",
    "unrated": "Unrated",
}

# Which side of the 3-way bias bar each 5-point rating falls on.
SIDE = {
    "left": "left", "lean-left": "left",
    "center": "center",
    "lean-right": "right", "right": "right",
}

# Keyed by outlet name. A config.yaml source either uses one of these names
# directly or points to one with `outlet:` (so several feeds from the same
# outlet - e.g. "BBC World" and "BBC Business" - share one rating).
OUTLETS: Dict[str, Dict[str, str]] = {
    # ── Center ──────────────────────────────────────────────────────────
    "BBC News": {"bias": "center", "owner": "BBC (licence-fee funded public broadcaster)",
                 "ownership": "Government", "country": "UK", "domain": "bbc.co.uk"},
    "Christian Science Monitor": {"bias": "center", "owner": "Christian Science Publishing Society",
                                  "ownership": "Other", "country": "US", "domain": "csmonitor.com"},
    "Deutsche Welle": {"bias": "center", "owner": "German federal government (public broadcaster)",
                       "ownership": "Government", "country": "Germany", "domain": "dw.com"},
    "Wall Street Journal": {"bias": "center", "owner": "News Corp",
                            "ownership": "Media Conglomerate", "country": "US", "domain": "wsj.com"},
    "The Hill": {"bias": "center", "owner": "Nexstar Media Group",
                 "ownership": "Media Conglomerate", "country": "US", "domain": "thehill.com"},
    "Newsweek": {"bias": "center", "owner": "Newsweek Publishing (Dev Pragad, Johnathan Davis)",
                 "ownership": "Individual", "country": "US", "domain": "newsweek.com"},
    # ── Lean Left ───────────────────────────────────────────────────────
    "New York Times": {"bias": "lean-left", "owner": "The New York Times Company",
                       "ownership": "Corporation", "country": "US", "domain": "nytimes.com"},
    "NPR": {"bias": "lean-left", "owner": "National Public Radio (nonprofit)",
            "ownership": "Independent", "country": "US", "domain": "npr.org"},
    "Al Jazeera": {"bias": "lean-left", "owner": "Al Jazeera Media Network (Qatar state-funded)",
                   "ownership": "Government", "country": "Qatar", "domain": "aljazeera.com"},
    "The Guardian": {"bias": "lean-left", "owner": "Scott Trust",
                     "ownership": "Independent", "country": "UK", "domain": "theguardian.com"},
    "CBC News": {"bias": "lean-left", "owner": "Canadian Broadcasting Corporation (public broadcaster)",
                 "ownership": "Government", "country": "Canada", "domain": "cbc.ca"},
    "The Independent": {"bias": "lean-left", "owner": "Independent Digital News & Media",
                        "ownership": "Individual", "country": "UK", "domain": "independent.co.uk"},
    "Sky News": {"bias": "lean-left", "owner": "Comcast",
                 "ownership": "Telecom", "country": "UK", "domain": "news.sky.com"},
    # ── Left ────────────────────────────────────────────────────────────
    "HuffPost": {"bias": "left", "owner": "BuzzFeed Inc.",
                 "ownership": "Corporation", "country": "US", "domain": "huffpost.com"},
    # ── Lean Right ──────────────────────────────────────────────────────
    "New York Post": {"bias": "lean-right", "owner": "News Corp",
                      "ownership": "Media Conglomerate", "country": "US", "domain": "nypost.com"},
    "Washington Times": {"bias": "lean-right", "owner": "Operations Holdings",
                         "ownership": "Other", "country": "US", "domain": "washingtontimes.com"},
    "Washington Examiner": {"bias": "lean-right", "owner": "Clarity Media Group (Philip Anschutz)",
                            "ownership": "Individual", "country": "US", "domain": "washingtonexaminer.com"},
    "Daily Mail": {"bias": "lean-right", "owner": "Daily Mail and General Trust (DMGT)",
                   "ownership": "Media Conglomerate", "country": "UK", "domain": "dailymail.co.uk"},
    # ── Right ───────────────────────────────────────────────────────────
    "Fox News": {"bias": "right", "owner": "Fox Corporation",
                 "ownership": "Media Conglomerate", "country": "US", "domain": "foxnews.com"},
    "Breitbart": {"bias": "right", "owner": "Breitbart News Network",
                  "ownership": "Other", "country": "US", "domain": "breitbart.com"},
}

# Old feed names (pre-upgrade config/archives) → outlet, so older configs and
# archived data still resolve to a rating.
ALIASES = {
    "BBC World": "BBC News",
    "Christian Science Monitor World": "Christian Science Monitor",
    "Deutsche Welle Top Stories": "Deutsche Welle",
    "WSJ World News": "Wall Street Journal",
    "NYT World": "New York Times",
    "NPR World": "NPR",
    "The Guardian World": "The Guardian",
    "CBC World": "CBC News",
    "New York Post World": "New York Post",
    "Washington Times World": "Washington Times",
    "Fox News World": "Fox News",
}

# Kept for backwards compatibility with code that imported SOURCE_BIAS.
SOURCE_BIAS: Dict[str, str] = {name: meta["bias"] for name, meta in OUTLETS.items()}


def resolve_outlet(name: str) -> str:
    """Map a feed/source name to its canonical outlet name."""
    if name in OUTLETS:
        return name
    return ALIASES.get(name, name)


def outlet_meta(name: str) -> Dict[str, str]:
    """Full metadata for a source (bias, owner, ownership, country...)."""
    outlet = resolve_outlet(name)
    meta = dict(OUTLETS.get(outlet, {}))
    meta.setdefault("bias", "unrated")
    meta.setdefault("owner", "Unknown")
    meta.setdefault("ownership", "Other")
    meta.setdefault("country", "")
    meta["name"] = outlet
    meta["bias_label"] = LABELS.get(meta["bias"], "Unrated")
    meta["side"] = SIDE.get(meta["bias"], "unrated")
    return meta


def get_bias(source_name: str) -> str:
    """Return the 5-point bias category for a source, defaulting to 'unrated'."""
    return outlet_meta(source_name)["bias"]


def get_bias_label(source_name: str) -> str:
    return LABELS.get(get_bias(source_name), "Unrated")


def get_side(source_name: str) -> str:
    """'left' | 'center' | 'right' | 'unrated'."""
    return SIDE.get(get_bias(source_name), "unrated")


def _unique(sources: List[str]) -> List[str]:
    seen, out = set(), []
    for s in sources:
        o = resolve_outlet(s)
        if o not in seen:
            seen.add(o)
            out.append(o)
    return out


def bias_breakdown(sources: List[str]) -> Dict[str, int]:
    """5-point counts of UNIQUE outlets covering a story (Left: 1, Center: 2...)."""
    counts = {LABELS[b]: 0 for b in BIAS_ORDER + ["unrated"]}
    for s in _unique(sources):
        counts[get_bias_label(s)] += 1
    return {k: v for k, v in counts.items() if v > 0}


def bias_bar_data(sources: List[str]) -> Dict[str, Any]:
    """
    Left / Center / Right percentages for the bias bar, Ground News-style:
    computed over unique, *rated* outlets (unrated outlets are left out of
    the bar, as Ground News does), so one outlet publishing three articles
    counts once.
    """
    counts = {"left": 0, "center": 0, "right": 0}
    unrated = 0
    for s in _unique(sources):
        side = get_side(s)
        if side in counts:
            counts[side] += 1
        else:
            unrated += 1
    rated = sum(counts.values())
    denom = rated or 1
    pct = {k: round(v / denom * 100) for k, v in counts.items()}
    # Make rounding add up to exactly 100 for a rated story
    if rated:
        drift = 100 - sum(pct.values())
        biggest = max(pct, key=lambda k: counts[k])
        pct[biggest] += drift
    return {
        "left_pct": pct["left"], "center_pct": pct["center"], "right_pct": pct["right"],
        "left": counts["left"], "center": counts["center"], "right": counts["right"],
        "unrated": unrated,
        "total": rated + unrated,
    }


def blindspot_side(sources: List[str], min_sources: int = 2) -> Optional[str]:
    """
    Ground News Blindspot formula (ground.news/rating-system), applied to
    the 3-way bias bar. A story is a "Blindspot for the Left" when:
      - right-leaning coverage >= 33%, and
      - left-leaning coverage <= (right% - 33) * (30/37)
    and mirrored for the Right. (Ground News also requires fewer than 10
    sources on the missing side, which is always true with this many feeds.)

    Returns "left" if the LEFT is missing the story (covered mostly by the
    right), "right" if the RIGHT is missing it, else None.

    Because this digest has ~20 feeds rather than Ground News's thousands,
    two extra guards stop tiny stories tripping it: at least `min_sources`
    rated outlets, and at least 2 outlets on the side that IS covering it
    (so "one Center + one Lean Left outlet" is not a blindspot).
    """
    bar = bias_bar_data(sources)
    rated = bar["left"] + bar["center"] + bar["right"]
    if rated < min_sources:
        return None
    L, R = bar["left_pct"], bar["right_pct"]
    if bar["right"] >= 2 and R >= 33 and L <= (R - 33) * (30 / 37):
        return "left"
    if bar["left"] >= 2 and L >= 33 and R <= (L - 33) * (30 / 37):
        return "right"
    return None


def is_blindspot(sources: List[str]) -> bool:
    return blindspot_side(sources) is not None


def ownership_breakdown(sources: List[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for s in _unique(sources):
        cat = outlet_meta(s)["ownership"]
        counts[cat] = counts.get(cat, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))
