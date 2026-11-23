"""
summarize.py - Free, local, multi-source extractive summaries.

For a story covered by several outlets, sentences are pooled from EVERY
outlet's description, scored by how central they are to the whole story
(how many of the story's key words they contain), and the top 3
non-redundant ones become the bullet points - so the summary reflects the
story, not just one outlet's take. No API key, no downloads.

For AI-written neutral summaries and left/center/right framing, see llm.py
(optional, needs ANTHROPIC_API_KEY).
"""
import re
import logging
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_STOPWORDS = {
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'is', 'are',
    'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those', 'it', 'its', 'as', 'if', 'than',
    'then', 'so', 'such', 'not', 'no', 'also', 'said', 'says', 'their', 'they', 'his', 'her', 'who', 'which',
}

_TAG_RE = re.compile(r'<[^>]+>')
_WORD_RE = re.compile(r"[A-Za-z']+")
# Abbreviations that end in a period but don't end a sentence
_ABBREV_RE = re.compile(r"\b(U\.S|U\.K|U\.N|E\.U|Mr|Mrs|Ms|Dr|St|Jr|Sr|Gen|Lt|Col|Sgt|Rep|Sen|Gov|Prof|Inc|Ltd|Co|"
                        r"No|vs|etc|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|[A-Z])\.", re.UNICODE)
_SENT_SPLIT_RE = re.compile(r'(?<=[.!?…])["”’]?\s+(?=["“‘(]?[A-Z0-9])')
_JUNK_RE = re.compile(r'(continue reading|read more|click here|sign up|subscribe|appeared first on|'
                      r'all rights reserved|getty images|^watch:|^listen:|^video:)', re.I)
_PLACEHOLDER = "⁣"


def _strip_html(text: str) -> str:
    return re.sub(r'\s+', ' ', _TAG_RE.sub(' ', text or '')).strip()


def split_sentences(text: str) -> List[str]:
    """Sentence split that doesn't break on U.S., Dr., single initials etc."""
    protected = _ABBREV_RE.sub(lambda m: m.group(0)[:-1] + _PLACEHOLDER, text)
    parts = _SENT_SPLIT_RE.split(protected)
    return [p.replace(_PLACEHOLDER, '.').strip() for p in parts if p.strip()]


_split_sentences = split_sentences  # old name


def _words(s: str) -> List[str]:
    return [w for w in _WORD_RE.findall(s.lower()) if w not in _STOPWORDS and len(w) > 2]


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def summarize_texts(texts: List[str], title: str = "", max_points: int = 3) -> List[str]:
    """Pick the most central, non-redundant sentences across several texts."""
    pool = []  # (sentence, text_index, position)
    for ti, text in enumerate(texts):
        for pos, s in enumerate(split_sentences(_strip_html(text))):
            if 35 <= len(s) <= 400 and not _JUNK_RE.search(s):
                pool.append((s, ti, pos))
    if not pool:
        return []

    freq: Dict[str, float] = {}
    for s, _, _ in pool:
        for w in set(_words(s)):
            freq[w] = freq.get(w, 0) + 1
    for w in _words(title):          # words in the headline matter more
        freq[w] = freq.get(w, 0) + 2

    scored = []
    for s, ti, pos in pool:
        ws = _words(s)
        if not ws:
            continue
        score = sum(freq.get(w, 0) for w in set(ws)) / (len(ws) ** 0.7)
        score *= 1.15 if pos == 0 else 1.0      # lede sentences are usually the gist
        scored.append((score, s, ti))
    scored.sort(key=lambda x: -x[0])

    chosen, chosen_sets, used_texts = [], [], {}
    for score, s, ti in scored:
        ws = set(_words(s))
        if any(_jaccard(ws, c) > 0.45 for c in chosen_sets):
            continue
        # Spread bullets across outlets when possible
        if used_texts.get(ti, 0) >= 2 and len(texts) > 1:
            continue
        if title and _jaccard(ws, set(_words(title))) > 0.8:
            continue  # just restates the headline
        chosen.append(s)
        chosen_sets.append(ws)
        used_texts[ti] = used_texts.get(ti, 0) + 1
        if len(chosen) >= max_points:
            break
    return chosen


def summarize_article(article: Dict[str, Any], max_points: int = 3) -> Dict[str, Any]:
    """Add 'bullet_points' to a story (or single article) dict."""
    texts = article.get('_texts') or [article.get('summary', '')]
    bullets = summarize_texts(texts, article.get('title', ''), max_points)
    if not bullets:
        raw = _strip_html(article.get('summary', ''))
        bullets = [raw[:240] + ('…' if len(raw) > 240 else '')] if raw else []
    article['bullet_points'] = bullets
    return article


def summarize_articles(articles: List[Dict[str, Any]], rate_limit_delay: float = 0.0) -> List[Dict[str, Any]]:
    for a in articles:
        summarize_article(a)
    logger.info(f"Summarized {len(articles)} stories (local extractive)")
    return articles


def configure_gemini():
    """No-op kept for backwards compatibility."""
    logger.info("Using local extractive summarizer - no API key needed")
