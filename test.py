#!/usr/bin/env python3
"""
test.py - Tests for the News Digest pipeline.

  python test.py          offline unit tests (no network; also run in CI)
  python test.py live     also fetch every configured feed and report health
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import logging  # noqa: E402
logging.disable(logging.WARNING)

from bias import bias_bar_data, blindspot_side, resolve_outlet, outlet_meta, OUTLETS  # noqa: E402
from fetch import parse_feed, clean_text, is_opinion  # noqa: E402
from dedupe import group_articles, sort_articles, cap_per_source, process_articles  # noqa: E402
from summarize import split_sentences, summarize_article  # noqa: E402
from topics import classify_topic, find_places  # noqa: E402
from deliver import format_digest_markdown  # noqa: E402
from htmlsite import generate_site  # noqa: E402
from weekly import build_weekly  # noqa: E402

NOW = datetime(2026, 11, 22, 12, 0, tzinfo=timezone.utc)


def art(title, source, summary="", hours_ago=1.0, link=None):
    return {"title": title, "source": source, "feed": source, "summary": summary,
            "link": link or f"https://example.com/{abs(hash((title, source)))}",
            "published": (NOW - timedelta(hours=hours_ago)).isoformat(), "image_url": None}


FIXTURE = [
    art("FBI Ten Most Wanted cartel leader 'Chapo Isidro' captured by Mexico's elite forces", "Fox News",
        "Fausto Isidro Meza-Flores, alias Chapo Isidro, was captured in Guasave, Mexico, sparking a gun battle.", 3),
    art("FBI's 'Most Wanted' cartel kingpin 'Chapo Isidro' captured in Mexico military operation", "New York Post",
        "A drug lord on the FBI's 10 most wanted list was captured in a joint US-Mexico operation.", 2),
    art("Alleged Mexican drug cartel boss 'El Chapo Isidro' arrested in special forces raid", "The Guardian",
        "Fausto Isidro Meza Flores evaded capture for more than a decade before a raid in Sinaloa.", 4),
    art("How El Chapo Isidro, alleged Mexican cartel leader, was captured", "Al Jazeera",
        "Mexican special forces captured Meza Flores in Sinaloa state on Friday night.", 1),
    art("UN top court rules Myanmar committed genocide against the Rohingya", "NPR",
        "The International Court of Justice found Myanmar acted with genocidal intent against the Rohingya.", 5),
    art("Top UN court finds Myanmar guilty of Rohingya genocide", "Christian Science Monitor",
        "The ICJ ruled that Myanmar security forces acted with genocidal intent in Rakhine state in 2017.", 6),
    art("Race to replant five South African baobabs after export blocked", "The Guardian",
        "Conservationists are racing to replant ancient baobab trees whose export to a Georgian estate was blocked.", 7),
    art("Iran regime's execution spree continues as twins face death penalty", "Fox News",
        "Rights groups say Iran has executed more people this year than in any year since the 1980s.", 8),
]


class TestBias(unittest.TestCase):
    def test_aliases_resolve(self):
        self.assertEqual(resolve_outlet("BBC World"), "BBC News")
        self.assertEqual(outlet_meta("Fox News World")["bias"], "right")
        self.assertEqual(outlet_meta("Some Blog")["bias"], "unrated")

    def test_bar_counts_unique_outlets_and_sums_to_100(self):
        bar = bias_bar_data(["NPR", "NPR", "Fox News", "BBC News"])
        self.assertEqual((bar["left"], bar["center"], bar["right"]), (1, 1, 1))
        self.assertEqual(bar["left_pct"] + bar["center_pct"] + bar["right_pct"], 100)

    def test_unrated_excluded_from_bar(self):
        bar = bias_bar_data(["NPR", "Unknown Outlet"])
        self.assertEqual(bar["left_pct"], 100)
        self.assertEqual(bar["unrated"], 1)

    def test_blindspot_ground_news_formula(self):
        # covered only by the right → the LEFT is missing it
        self.assertEqual(blindspot_side(["Fox News", "New York Post"]), "left")
        self.assertEqual(blindspot_side(["NPR", "The Guardian", "BBC News"]), "right")
        # balanced, single-source, or one center + one left: not blindspots
        self.assertIsNone(blindspot_side(["NPR", "Fox News"]))
        self.assertIsNone(blindspot_side(["Fox News"]))
        self.assertIsNone(blindspot_side(["NPR", "BBC News"]))

    def test_every_configured_feed_has_a_rating(self):
        import yaml
        cfg = yaml.safe_load(open(ROOT / "config.yaml"))
        for feed in cfg["sources"]["rss"]:
            outlet = resolve_outlet(feed.get("outlet") or feed["name"])
            self.assertIn(outlet, OUTLETS, f"{feed['name']} → '{outlet}' missing from bias.OUTLETS")


RSS = """<?xml version="1.0"?><rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/"><channel><title>T</title>
<item><title>Fresh story &amp; more</title><link>https://ex.com/world/1</link>
<description>&lt;p&gt;First line. Second line.&lt;/p&gt; Continue reading...</description>
<pubDate>Sun, 22 Nov 2026 10:00:00 GMT</pubDate><media:thumbnail url="https://ex.com/a.jpg"/></item>
<item><title>Opinion: everyone is wrong</title><link>https://ex.com/opinion/2</link><description>x</description>
<pubDate>Sun, 22 Nov 2026 09:00:00 GMT</pubDate></item>
<item><title>Old story</title><link>https://ex.com/world/3</link><description>x</description>
<pubDate>Wed, 18 Nov 2026 09:00:00 GMT</pubDate></item>
</channel></rss>"""


class TestFetch(unittest.TestCase):
    def test_parse_feed(self):
        items = parse_feed(RSS.encode(), {"name": "BBC World", "outlet": "BBC News"},
                           max_age_hours=48, now=NOW)
        self.assertEqual(len(items), 1, "opinion and old items should be dropped")
        a = items[0]
        self.assertEqual(a["title"], "Fresh story & more")
        self.assertEqual(a["source"], "BBC News")
        self.assertEqual(a["summary"], "First line. Second line.")
        self.assertEqual(a["image_url"], "https://ex.com/a.jpg")
        self.assertTrue(a["published"].startswith("2026-11-22T10:00:00"))

    def test_helpers(self):
        self.assertTrue(is_opinion("https://www.theguardian.com/commentisfree/2026/x", "A take"))
        self.assertFalse(is_opinion("https://ex.com/world/x", "Opinion polls show lead"))
        self.assertEqual(clean_text("The post X appeared first on Y."), "")


class TestGrouping(unittest.TestCase):
    def setUp(self):
        self.stories = group_articles([dict(a) for a in FIXTURE])

    def find(self, word):
        return next(s for s in self.stories if word.lower() in s["title"].lower())

    def test_paraphrased_headlines_group(self):
        s = self.find("Isidro")
        self.assertEqual(s["source_count"], 4)
        self.assertEqual(set(s["all_sources"]), {"Fox News", "New York Post", "The Guardian", "Al Jazeera"})
        self.assertEqual(s["first_reported"]["source"], "The Guardian")
        self.assertEqual(self.find("Myanmar")["source_count"], 2)

    def test_unrelated_stay_separate(self):
        self.assertEqual(self.find("baobab")["source_count"], 1)
        self.assertEqual(self.find("execution")["source_count"], 1)
        self.assertEqual(len(self.stories), 4)

    def test_story_fields(self):
        s = self.find("Isidro")
        for key in ("id", "articles", "bias_bar", "blindspot", "ownership_breakdown", "topic", "places", "score"):
            self.assertIn(key, s)
        self.assertEqual(len(s["articles"]), 4)
        self.assertIn("Mexico", [p["name"] for p in s["places"]])

    def test_ranking_puts_wide_coverage_first(self):
        ranked = sort_articles(self.stories)
        self.assertIn("Isidro", ranked[0]["title"])

    def test_date_sort_uses_real_timestamps(self):
        # Regression: RFC-822 strings used to sort alphabetically by weekday
        a = {"updated": "2026-11-18T10:00:00+00:00"}
        b = {"updated": "2026-11-21T10:00:00+00:00"}
        self.assertEqual(sort_articles([a, b], by_date=True)[0], b)

    def test_cap_never_drops_multi_source_stories(self):
        stories = [{"source": "NPR", "source_count": 1}] * 5 + [{"source": "NPR", "source_count": 3}]
        out = cap_per_source(stories, 2)
        self.assertEqual(len(out), 3)
        self.assertEqual(out[-1]["source_count"], 3)

    def test_process_articles(self):
        out = process_articles([dict(a) for a in FIXTURE], {"max_stories_per_digest": 3})
        self.assertEqual(len(out), 3)


class TestText(unittest.TestCase):
    def test_sentence_split_keeps_abbreviations(self):
        s = split_sentences("Leaders criticised U.S. policy. Dr. Smith spoke at 5 p.m. on Friday. It ended.")
        self.assertEqual(len(s), 3)
        self.assertIn("U.S. policy", s[0])

    def test_multi_source_summary(self):
        story = {"title": "France confirms first Ebola case",
                 "_texts": ["A French doctor has been diagnosed with Ebola. He had travelled to Congo.",
                            "French health officials confirmed the country's first Ebola case on Tuesday."]}
        bullets = summarize_article(story)["bullet_points"]
        self.assertTrue(1 <= len(bullets) <= 3)

    def test_topics(self):
        self.assertEqual(classify_topic("Russian missile strike kills two in Ukraine"), "Conflict")
        names = [p["name"] for p in find_places("Zelensky meets Starmer in London")]
        self.assertIn("Ukraine", names)
        self.assertIn("UK", names)


class TestOutputs(unittest.TestCase):
    def setUp(self):
        from summarize import summarize_articles
        self.stories = summarize_articles(sort_articles(group_articles([dict(a) for a in FIXTURE])))

    def test_markdown(self):
        md = format_digest_markdown(self.stories, "2026-11-22")
        self.assertIn("# News Digest - 2026-11-22", md)
        self.assertIn("Headlines by outlet", md)

    def test_site_and_weekly(self):
        with tempfile.TemporaryDirectory() as tmp:
            status = {"Fox News World": {"feed": "Fox News World", "outlet": "Fox News", "ok": True, "articles": 2, "error": ""},
                      "CBC World": {"feed": "CBC World", "outlet": "CBC News", "ok": False, "articles": 0, "error": "timeout"}}
            path = generate_site(self.stories, output_dir=tmp, feed_status=status)
            data = json.load(open(path))
            self.assertEqual(data["stats"]["total"], len(self.stories))
            self.assertNotIn("_texts", data["stories"][0])
            self.assertTrue(any(s["name"] == "CBC News" and s["ok"] is False for s in data["sources"]))
            self.assertTrue((Path(tmp) / "index.html").exists())
            self.assertTrue((Path(tmp) / ".nojekyll").exists())
            index = json.load(open(Path(tmp) / "data" / "index.json"))
            self.assertEqual(len(index["days"]), 1)
            w = build_weekly(Path(tmp) / "data")
            self.assertGreaterEqual(len(w["stories"]), 1)


def live_check():
    import yaml
    from fetch import fetch_all_articles, FEED_STATUS
    cfg = yaml.safe_load(open(ROOT / "config.yaml"))
    logging.disable(logging.NOTSET)
    arts = fetch_all_articles(cfg)
    print()
    for name, st in FEED_STATUS.items():
        print(f"{'OK  ' if st['ok'] else 'FAIL'} {name:32s} {st['articles']:3d}  {st['error'][:70]}")
    stories = group_articles(arts)
    multi = sum(1 for s in stories if s["source_count"] > 1)
    print(f"\n{len(arts)} articles → {len(stories)} stories, {multi} covered by 2+ outlets")
    return all(st["ok"] for st in FEED_STATUS.values())


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("live", "fetch"):
        sys.exit(0 if live_check() else 1)
    sys.exit(0 if unittest.main(argv=[sys.argv[0], "-v"], exit=False).result.wasSuccessful() else 1)
