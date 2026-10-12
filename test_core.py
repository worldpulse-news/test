"""Offline tests: run with  python -m pytest -q"""
import os
import sys
import tempfile

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from core import impact, markets, news  # noqa: E402
from core.store import Store  # noqa: E402

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>
<item><title>Oil jumps as OPEC+ cuts output - Reuters</title><link>https://news.google.com/a1</link>
<pubDate>Mon, 12 Oct 2026 08:00:00 GMT</pubDate><description>&lt;a&gt;Oil jumps as OPEC+ cuts output&lt;/a&gt;</description></item>
<item><title>OPEC+ cuts output, oil jumps - Bloomberg</title><link>https://news.google.com/a2</link>
<pubDate>Mon, 12 Oct 2026 08:05:00 GMT</pubDate></item>
<item><title>RBI holds repo rate, hints at rate cut</title><link>https://x.com/b</link>
<pubDate>Mon, 12 Oct 2026 09:00:00 GMT</pubDate><description>The Reserve Bank kept rates unchanged.</description></item>
</channel></rss>"""

GN = {"name": "GN", "url": "https://news.google.com/rss/x", "region": "Global", "category": "Markets"}


def test_parse_and_merge():
    items = news.parse_feed(RSS, GN)
    assert len(items) == 3
    assert items[0]["title"] == "Oil jumps as OPEC+ cuts output" and items[0]["publisher"].startswith("Reuters")
    merged = news.merge_duplicates(items)
    assert len(merged) == 2
    oil = [m for m in merged if "Oil" in m["title"] or "OPEC" in m["title"]][0]
    assert len(oil["also_in"]) == 1


def test_fetch_all_health():
    def fake(src):
        return (news.parse_feed(RSS, src), None) if src["name"] == "ok" else ([], "HTTPError: 404")
    arts, health = news.fetch_all([dict(GN, name="ok"), dict(GN, name="bad")], fetcher=fake)
    assert health["ok"]["ok"] and not health["bad"]["ok"] and len(arts) == 2


def test_rules():
    r = impact.analyze_rules({"title": "Oil prices jump after OPEC+ supply cut", "summary": "", "region": "Global"})
    sect = {s["name"]: s["effect"] for s in r["sectors"]}
    assert "Oil price" in r["themes"] and sect["Energy / Oil & Gas"] == 1 and sect["Airlines"] == -1
    r = impact.analyze_rules({"title": "RBI cuts repo rate as inflation cools", "summary": "", "region": "India"})
    assert "India" in r["regions"] and "Nifty 50" in r["markets"]
    assert {s["name"]: s["effect"] for s in r["sectors"]}["Real estate"] == 1
    r = impact.analyze_rules({"title": "Football league announces schedule", "summary": "", "region": "Global"})
    assert r["level"] == "Low" and not r["themes"]
    # 'war' must not match inside 'software' / 'warn'
    r = impact.analyze_rules({"title": "Software firm warns on outlook", "summary": "", "region": "Global"})
    assert "Geopolitical risk" not in r["themes"]


def test_parse_json():
    assert impact.parse_json('Sure! {"headline_view": "x", "markets": []} done')["headline_view"] == "x"


def _hist(ticker, period, interval):
    idx = pd.date_range("2026-10-12 03:45", periods=30, freq="15min", tz="UTC")
    return pd.DataFrame({"Close": [100 + i for i in range(30)]}, index=idx)


def test_reaction_and_quote():
    df = markets.intraday("^NSEI", history=_hist)
    rx = markets.reaction(df, "2026-10-12T05:00:00+00:00", 60)
    assert round(rx["start_price"]) == 105 and round(rx["window_pct"], 2) == round((109 / 105 - 1) * 100, 2)
    q = markets.quote("^NSEI", history=_hist)
    assert q and q["last"] == 129.0


def test_store():
    with tempfile.TemporaryDirectory() as d:
        s = Store(os.path.join(d, "t.db"))
        s.save_articles([{"id": "a1", "title": "Hello oil", "published": "2026-10-12T00:00:00+00:00"}])
        s.track("a1"); s.mark_read("a1"); s.add_topic("oil"); s.update_tracked("a1", note="watch", status="Done")
        assert s.tracked()[0]["note"] == "watch" and "a1" in s.read_ids() and s.topics()[0]["keyword"] == "oil"
        assert s.search_saved("oil")[0]["id"] == "a1"
        s.set("x", [1]); assert s.get("x") == [1]


def test_inflections_and_assets():
    r = impact.analyze_rules({"title": "Oil jumps 4% as OPEC+ agrees surprise output cut", "summary": "", "region": "Global"})
    sect = {s["name"]: s["effect"] for s in r["sectors"]}
    assert sect["Airlines"] == -1 and "Brent crude" in r["markets"]
    r = impact.analyze_rules({"title": "ECB cuts interest rate as growth slows", "summary": "", "region": "Europe"})
    assert {s["name"]: s["effect"] for s in r["sectors"]}["Real estate"] == 1
