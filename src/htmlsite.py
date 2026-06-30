"""
htmlsite.py - Generates a static HTML page from the digest, for GitHub Pages.

Writes to docs/index.html, which GitHub Pages can serve directly if you
enable Pages on the `docs/` folder of the main branch (Settings > Pages >
Source: Deploy from a branch > main > /docs). No build step, no JS
framework, no extra dependencies - just one self-contained HTML file.
"""
import os
import html
import logging
from typing import List, Dict, Any
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_BIAS_COLORS = {
    "Left": "#2563eb",
    "Lean Left": "#60a5fa",
    "Center": "#9ca3af",
    "Lean Right": "#f87171",
    "Right": "#dc2626",
    "Unrated": "#d1d5db",
}

_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>News Digest - {date}</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    max-width: 760px;
    margin: 0 auto;
    padding: 24px 16px 64px;
    line-height: 1.5;
    background: #fafafa;
    color: #1a1a1a;
  }}
  @media (prefers-color-scheme: dark) {{
    body {{ background: #111315; color: #e5e7eb; }}
    .story {{ background: #1a1d21 !important; border-color: #2a2d31 !important; }}
    a {{ color: #93c5fd !important; }}
  }}
  h1 {{ font-size: 1.6rem; margin-bottom: 4px; }}
  .summary {{ color: #666; margin-bottom: 24px; font-size: 0.95rem; }}
  .story {{
    background: #fff;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 18px 20px;
    margin-bottom: 16px;
  }}
  .story.blindspot {{ border-left: 4px solid #f59e0b; }}
  .story h2 {{ font-size: 1.1rem; margin: 0 0 8px; }}
  .story h2 a {{ color: inherit; text-decoration: none; }}
  .story h2 a:hover {{ text-decoration: underline; }}
  .meta {{ font-size: 0.85rem; color: #666; margin-bottom: 10px; }}
  .also-covered {{ font-size: 0.85rem; color: #666; margin-bottom: 6px; }}
  .bias-tags {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }}
  .bias-tag {{
    display: inline-block;
    font-size: 0.72rem;
    font-weight: 600;
    color: #fff;
    padding: 2px 8px;
    border-radius: 999px;
  }}
  .blindspot-tag {{
    display: inline-block;
    font-size: 0.72rem;
    font-weight: 600;
    color: #92400e;
    background: #fef3c7;
    padding: 2px 8px;
    border-radius: 999px;
    margin-bottom: 10px;
  }}
  ul {{ margin: 8px 0 0; padding-left: 20px; }}
  li {{ margin-bottom: 4px; }}
  footer {{ margin-top: 32px; font-size: 0.8rem; color: #999; text-align: center; }}
</style>
</head>
<body>
<h1>📰 News Digest</h1>
<div class="summary">{date_full} · {total} stories · {multi_source} with multi-source coverage · {blindspot_count} blindspot{plural}</div>
{stories}
<footer>Generated automatically · sources span the political spectrum (see README for bias methodology)</footer>
</body>
</html>
"""


def _bias_tags_html(bias_breakdown: Dict[str, int]) -> str:
    tags = []
    for label, count in bias_breakdown.items():
        color = _BIAS_COLORS.get(label, "#d1d5db")
        tags.append(f'<span class="bias-tag" style="background:{color}">{html.escape(label)}: {count}</span>')
    return f'<div class="bias-tags">{"".join(tags)}</div>' if tags else ""


def _story_html(article: Dict[str, Any]) -> str:
    title = html.escape(article.get('title', 'No title'))
    link = html.escape(article.get('link', '#'))
    source = html.escape(article.get('source', 'Unknown'))
    bullets = article.get('bullet_points', ['No summary'])
    all_sources = article.get('all_sources', [source])
    bias_counts = article.get('bias_breakdown', {})
    blindspot = article.get('is_blindspot', False)

    parts = [f'<div class="story{" blindspot" if blindspot else ""}">']
    parts.append(f'<h2><a href="{link}" target="_blank" rel="noopener">{title}</a></h2>')
    parts.append(f'<div class="meta">Source: {source}</div>')

    others = [s for s in all_sources if s != article.get('source')]
    if others:
        parts.append(f'<div class="also-covered">Also covered by: {html.escape(", ".join(others))}</div>')

    parts.append(_bias_tags_html(bias_counts))

    if blindspot:
        parts.append('<div class="blindspot-tag">🔍 Blindspot - one-sided coverage</div>')

    parts.append('<ul>')
    for bullet in bullets:
        parts.append(f'<li>{html.escape(bullet)}</li>')
    parts.append('</ul>')

    parts.append('</div>')
    return "\n".join(parts)


def generate_site(articles: List[Dict[str, Any]], output_dir: str = 'docs') -> str:
    """
    Generate a static HTML digest page at {output_dir}/index.html.

    Args:
        articles: List of processed story dicts (same shape as the
            markdown digest uses)
        output_dir: Directory to write index.html into (GitHub Pages
            convention is 'docs' on the main branch)

    Returns:
        Path to the generated file, or "" on failure
    """
    try:
        os.makedirs(output_dir, exist_ok=True)

        total = len(articles)
        multi_source = sum(1 for a in articles if len(a.get('all_sources', [])) > 1)
        blindspot_count = sum(1 for a in articles if a.get('is_blindspot'))

        # Surface blindspots first, same as the markdown digest
        ordered = sorted(articles, key=lambda a: not a.get('is_blindspot', False))
        stories_html = "\n".join(_story_html(a) for a in ordered)

        page = _PAGE_TEMPLATE.format(
            date=datetime.now().strftime('%Y-%m-%d'),
            date_full=datetime.now().strftime('%B %d, %Y'),
            total=total,
            multi_source=multi_source,
            blindspot_count=blindspot_count,
            plural='s' if blindspot_count != 1 else '',
            stories=stories_html,
        )

        output_path = os.path.join(output_dir, 'index.html')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(page)

        logger.info(f"Static site generated at {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"Error generating static site: {e}")
        return ""


if __name__ == '__main__':
    test_articles = [
        {
            'title': 'France confirms first Ebola case',
            'link': 'https://example.com/1',
            'source': 'BBC World',
            'all_sources': ['BBC World', 'NYT World'],
            'bias_breakdown': {'Center': 1, 'Lean Left': 1},
            'is_blindspot': False,
            'bullet_points': ['A doctor was infected after travel to DR Congo.']
        },
        {
            'title': 'Iran loyalists promote wider nationalism',
            'link': 'https://example.com/2',
            'source': 'NYT World',
            'all_sources': ['NYT World'],
            'bias_breakdown': {'Lean Left': 1},
            'is_blindspot': True,
            'bullet_points': ['Government supporters show ties with former dissidents.']
        },
    ]
    path = generate_site(test_articles, output_dir='/tmp/site_test')
    print(f"Wrote {path}")
    with open(path) as f:
        print(f.read()[:500])
