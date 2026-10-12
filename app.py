"""
WorldPulse – world news + its likely impact on share markets.
Run:  streamlit run app.py
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import config as C
from core import impact, markets, news
from core.article import full_text
from core.store import Store

st.set_page_config(page_title=C.APP_NAME, page_icon="🌐", layout="wide")
DEMO = os.environ.get("WORLDPULSE_DEMO") == "1"
HERE = os.path.dirname(__file__)
TZ = ZoneInfo(C.DISPLAY_TIMEZONE)

st.markdown("""
<style>
.block-container{padding-top:1.4rem;max-width:1250px}
.wp-meta{color:#6b7280;font-size:.83rem}
.wp-chip{display:inline-block;border-radius:999px;padding:1px 9px;margin:2px 4px 2px 0;font-size:.78rem;border:1px solid rgba(128,128,128,.35)}
.wp-up{color:#047857;border-color:#04785755;background:#04785712}
.wp-down{color:#b91c1c;border-color:#b91c1c55;background:#b91c1c12}
.wp-mixed{color:#92400e;border-color:#92400e55;background:#92400e12}
.wp-lvl-High{background:#b91c1c;color:#fff;border:none}
.wp-lvl-Medium{background:#d97706;color:#fff;border:none}
.wp-lvl-Low{opacity:.75}
.wp-title{font-size:1.05rem;font-weight:650;line-height:1.35}
.wp-read .wp-title{opacity:.55}
</style>""", unsafe_allow_html=True)


# ------------------------------------------------------------------ data
@st.cache_resource
def get_store() -> Store:
    return Store()


S = get_store()


def all_sources() -> list[dict]:
    custom = S.get("custom_sources", [])
    disabled = set(S.get("disabled_sources", []))
    return [s for s in C.SOURCES + custom if s["name"] not in disabled]


@st.cache_data(ttl=C.REFRESH_MINUTES * 60, show_spinner=False)
def load_news(sources_json: str) -> tuple[list[dict], dict, str]:
    sources = json.loads(sources_json)
    if DEMO:
        arts = json.load(open(os.path.join(HERE, "data", "sample_news.json")))
        base = datetime.now(timezone.utc)
        for i, a in enumerate(arts):  # sample stories get fresh timestamps so filters work
            a["published"] = (base - timedelta(minutes=35 * i + 5)).isoformat()
        health = {s["name"]: {"ok": True, "count": 0, "error": None, "url": s["url"]} for s in sources}
        arts = news.merge_duplicates(arts)
    else:
        arts, health = news.fetch_all(sources)
    for a in arts:
        a["impact"] = impact.analyze_rules(a)
    return arts, health, datetime.now(timezone.utc).isoformat()


@st.cache_data(ttl=C.PRICE_REFRESH_SECONDS, show_spinner=False)
def load_quotes(names: tuple[str, ...]) -> dict:
    book = {**C.INDICES, **C.COMMODITIES_FX}
    out = {}
    from concurrent.futures import ThreadPoolExecutor
    hist = _demo_history if DEMO else markets._history
    with ThreadPoolExecutor(max_workers=10) as pool:
        res = pool.map(lambda n: (n, markets.quote(book[n][0], history=hist)), names)
        for n, q in res:
            out[n] = q
    return out


@st.cache_data(ttl=C.PRICE_REFRESH_SECONDS, show_spinner=False)
def load_intraday(ticker: str) -> pd.DataFrame:
    return markets.intraday(ticker, history=_demo_history if DEMO else markets._history)


def _demo_history(ticker, period, interval):  # synthetic prices – only used in demo/test mode
    import numpy as np
    n = {"1mo": 22, "1d": 75, "5d": 130}[period]
    step = {"1d": "1D", "5m": "5min", "15m": "15min"}[interval]
    end = pd.Timestamp.now(tz="UTC").floor("15min")
    idx = pd.date_range(end=end, periods=n, freq=step)
    rng = np.random.default_rng(abs(hash(ticker)) % 2**32)
    return pd.DataFrame({"Close": 100 * np.cumprod(1 + rng.normal(0, .004, n))}, index=idx)


# ------------------------------------------------------------------ helpers
def ago(iso: str) -> str:
    d = datetime.fromisoformat(iso)
    mins = int((datetime.now(timezone.utc) - d).total_seconds() // 60)
    if mins < 1:
        return "just now"
    if mins < 60:
        return f"{mins} min ago"
    if mins < 1440:
        return f"{mins // 60} h ago"
    return d.astimezone(TZ).strftime("%d %b")


def local(iso: str) -> str:
    return datetime.fromisoformat(iso).astimezone(TZ).strftime("%d %b %Y, %I:%M %p")


def chip(text, cls=""):
    return f'<span class="wp-chip {cls}">{text}</span>'


def effect_chip(name, eff):
    arrow, cls = {1: ("▲", "wp-up"), -1: ("▼", "wp-down")}.get(eff, ("◆", "wp-mixed"))
    return chip(f"{arrow} {name}", cls)


def open_story(aid: str):
    st.session_state["open_id"] = aid
    st.session_state["page"] = "Reader"
    S.mark_read(aid)


def go_page(p):
    st.session_state["page"] = p


def api_key() -> str | None:
    key = st.session_state.get("api_key")
    if key:
        return key
    try:
        return st.secrets.get("ANTHROPIC_API_KEY")
    except Exception:
        return os.environ.get("ANTHROPIC_API_KEY")


def story_card(a: dict, read: set, tracked: set, key_prefix: str):
    imp = a["impact"]
    with st.container(border=True):
        cls = "wp-read" if a["id"] in read else ""
        also = f" · +{len(a['also_in'])} more outlets" if a.get("also_in") else ""
        st.markdown(
            f'<div class="{cls}"><div class="wp-title">{a["title"]}</div>'
            f'<div class="wp-meta">{a["publisher"]} · {", ".join(imp["regions"])} · {ago(a["published"])}{also}</div></div>',
            unsafe_allow_html=True)
        if a.get("summary"):
            st.caption(a["summary"][:260] + ("…" if len(a["summary"]) > 260 else ""))
        chips = chip(f"Impact: {imp['level']}", f"wp-lvl-{imp['level']}")
        chips += "".join(chip(m) for m in imp["markets"][:3])
        chips += "".join(effect_chip(s["name"], s["effect"]) for s in imp["sectors"][:4])
        st.markdown(chips, unsafe_allow_html=True)
        c1, c2, c3, _ = st.columns([1, 1, 1, 3])
        c1.button("Read", key=f"{key_prefix}r{a['id']}", on_click=open_story, args=(a["id"],), width="stretch")
        if a["id"] in tracked:
            c2.button("★ Tracking", key=f"{key_prefix}u{a['id']}", on_click=S.untrack, args=(a["id"],), width="stretch")
        else:
            c2.button("☆ Track", key=f"{key_prefix}t{a['id']}", on_click=S.track, args=(a["id"],), width="stretch")
        if a["id"] in read:
            c3.button("Mark unread", key=f"{key_prefix}m{a['id']}", on_click=S.mark_unread, args=(a["id"],), width="stretch")
        else:
            c3.button("Mark read", key=f"{key_prefix}m{a['id']}", on_click=S.mark_read, args=(a["id"],), width="stretch")


# ------------------------------------------------------------------ load
sources = all_sources()
with st.spinner(f"Fetching news from {len(sources)} sources…"):
    ARTS, HEALTH, FETCHED = load_news(json.dumps(sources, sort_keys=True))
S.save_articles(ARTS)
BY_ID = {a["id"]: a for a in ARTS}
READ, TRACKED = S.read_ids(), S.tracked_ids()

# ------------------------------------------------------------------ sidebar
PAGES = ["Live news", "Markets", "Reader", "My tracker", "Sources & settings"]
st.session_state.setdefault("page", "Live news")
with st.sidebar:
    st.markdown(f"## 🌐 {C.APP_NAME}")
    st.caption("World news and what it could mean for markets")
    st.radio("Go to", PAGES, key="page", label_visibility="collapsed")
    ok = sum(1 for h in HEALTH.values() if h["ok"])
    st.caption(f"{len(ARTS)} stories from {ok}/{len(HEALTH)} sources · updated {ago(FETCHED)}")
    st.toggle("Live auto-update", value=True, key="auto",
              help=f"New stories appear automatically (checked every {C.AUTO_REFRESH_SECONDS} s); prices refresh every minute.")
    if st.button("↻ Refresh now", width="stretch"):
        load_news.clear(); load_quotes.clear(); load_intraday.clear(); st.rerun()
    if DEMO:
        st.warning("Demo mode: sample stories and simulated prices.")
    st.divider()
    st.caption("Impact tags are indicative, from keyword rules or AI. Not investment advice.")

page = st.session_state["page"]


@st.fragment(run_every=None if os.environ.get("WORLDPULSE_TEST") else int(os.environ.get("WORLDPULSE_AUTO_SECONDS", C.AUTO_REFRESH_SECONDS)))
def live_watch():
    """Runs quietly every minute: if the news cache has expired, fetch again and redraw the page."""
    if not st.session_state.get("auto", True) or page in ("Sources & settings",):
        return
    _, _, fetched = load_news(json.dumps(all_sources(), sort_keys=True))
    if fetched != FETCHED:
        new = sum(1 for a in load_news(json.dumps(all_sources(), sort_keys=True))[0] if a["id"] not in BY_ID)
        if new:
            st.toast(f"{new} new stor{'y' if new == 1 else 'ies'}")
        st.rerun(scope="app")
    if page == "Markets" and st.session_state.get("_q_at") != load_quotes_stamp():
        st.rerun(scope="app")


@st.cache_data(ttl=C.PRICE_REFRESH_SECONDS, show_spinner=False)
def _stamp():
    return datetime.now(timezone.utc).isoformat()


def load_quotes_stamp():
    return _stamp()

# ================================================================== LIVE NEWS
if page == "Live news":
    st.title("Live news")
    f1, f2, f3, f4 = st.columns([2.2, 1.4, 1.4, 1.2])
    q = f1.text_input("Search", placeholder="e.g. RBI, crude, Nvidia, tariff", key="q")
    regions = f2.multiselect("Region", C.REGIONS, key="regions")
    cats = f3.multiselect("Category", C.CATEGORIES, key="cats")
    hours = f4.selectbox("Time", [3, 6, 12, 24, 48, 168], index=3, format_func=lambda h: f"Last {h} h" if h < 168 else "Last 7 days", key="hours")
    g1, g2, g3 = st.columns([1.4, 1.4, 2])
    level = g1.segmented_control("Market impact", ["All", "Medium+", "High"], default="All", key="lvl")
    hide_read = g2.toggle("Hide stories I've read", key="hide_read")
    sort = g3.segmented_control("Sort", ["Latest", "Biggest impact", "Most covered"], default="Latest", key="sort")

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = [a for a in ARTS if datetime.fromisoformat(a["published"]) >= cutoff]
    if q:
        ql = q.lower()
        rows = [a for a in rows if ql in (a["title"] + " " + a.get("summary", "")).lower()]
    if regions:
        rows = [a for a in rows if set(regions) & set(a["impact"]["regions"] + [a["region"]])]
    if cats:
        rows = [a for a in rows if a["category"] in cats]
    if level == "Medium+":
        rows = [a for a in rows if a["impact"]["level"] in ("Medium", "High")]
    elif level == "High":
        rows = [a for a in rows if a["impact"]["level"] == "High"]
    if hide_read:
        rows = [a for a in rows if a["id"] not in READ]
    if sort == "Biggest impact":
        rows.sort(key=lambda a: a["impact"]["score"], reverse=True)
    elif sort == "Most covered":
        rows.sort(key=lambda a: len(a.get("also_in", [])), reverse=True)

    top = sorted([a for a in rows if a["impact"]["level"] == "High"], key=lambda a: a["impact"]["score"], reverse=True)[:4]
    if top and not q:
        st.subheader("Market-moving now")
        cols = st.columns(len(top))
        for c, a in zip(cols, top):
            with c.container(border=True):
                st.markdown(f"**{a['title'][:110]}**")
                st.caption(f"{a['publisher']} · {ago(a['published'])}")
                st.markdown("".join(effect_chip(s["name"], s["effect"]) for s in a["impact"]["sectors"][:3]) or chip("General"), unsafe_allow_html=True)
                st.button("Read", key=f"top{a['id']}", on_click=open_story, args=(a["id"],))
        st.divider()

    st.caption(f"{len(rows)} stories")
    PER = 25
    pages = max(1, (len(rows) + PER - 1) // PER)
    pg = st.number_input("Page", 1, pages, 1, key="pg") if pages > 1 else 1
    for a in rows[(pg - 1) * PER: pg * PER]:
        story_card(a, READ, TRACKED, "f")
    if not rows:
        st.info("No stories match these filters. Widen the time window or clear the search.")

# ================================================================== MARKETS
elif page == "Markets":
    st.title("Markets")
    st.caption("Prices from Yahoo Finance; may be delayed by about 15 minutes.")
    quotes = load_quotes(tuple(list(C.INDICES) + list(C.COMMODITIES_FX)))
    st.session_state["_q_at"] = load_quotes_stamp()

    def tiles(names):
        cols = st.columns(4)
        for i, n in enumerate(names):
            qd = quotes.get(n)
            with cols[i % 4]:
                if not qd:
                    st.metric(n, "–", help="Price not available right now", border=True)
                else:
                    st.metric(n, f"{qd['last']:,.2f}", f"{qd['change_pct']:+.2f}%", border=True,
                              chart_data=qd["spark"], chart_type="area")

    for reg in ["United States", "India", "Europe", "Japan", "China", "Asia", "Middle East"]:
        names = [n for n, (_, r) in C.INDICES.items() if r == reg]
        if names:
            st.subheader(reg)
            tiles(names)
    st.subheader("Commodities, currencies, bonds & crypto")
    tiles(list(C.COMMODITIES_FX))

    st.divider()
    st.subheader("News moving each region")
    reg = st.segmented_control("Region", C.REGIONS, default="India", key="mreg")
    rel = sorted([a for a in ARTS if reg in a["impact"]["regions"] and a["impact"]["level"] != "Low"],
                 key=lambda a: (a["impact"]["score"], a["published"]), reverse=True)[:10]
    for a in rel:
        story_card(a, READ, TRACKED, "m")
    if not rel:
        st.info("No market-relevant stories for this region right now.")

# ================================================================== READER
elif page == "Reader":
    aid = st.session_state.get("open_id")
    a = BY_ID.get(aid) or (S.article(aid) if aid else None)
    if not a:
        st.title("Reader")
        st.info("Open any story with **Read** to see it here in detail.")
        st.button("Go to live news", on_click=go_page, args=("Live news",))
    else:
        a.setdefault("impact", impact.analyze_rules(a))
        imp = a["impact"]
        st.button("← Back to news", on_click=go_page, args=("Live news",))
        st.title(a["title"])
        st.markdown(f'<div class="wp-meta">{a["publisher"]} · {local(a["published"])} ({ago(a["published"])})</div>', unsafe_allow_html=True)
        if a.get("also_in"):
            st.caption("Also reported by: " + ", ".join(a["also_in"][:12]))
        b1, b2, _ = st.columns([1.3, 1.3, 4])
        b1.link_button("Open original ↗", a["link"], width="stretch")
        if a["id"] in TRACKED:
            b2.button("★ Tracking", on_click=S.untrack, args=(a["id"],), width="stretch")
        else:
            b2.button("☆ Track this story", on_click=S.track, args=(a["id"],), width="stretch")

        left, right = st.columns([3, 2], gap="large")
        with left:
            st.subheader("Story")
            if a.get("summary"):
                st.write(a["summary"])
            body = S.get_fulltext(a["id"])
            if body is None and st.session_state.get(f"ft_tried_{a['id']}") is None:
                with st.spinner("Loading full article…"):
                    body = None if DEMO else full_text(a["link"])
                st.session_state[f"ft_tried_{a['id']}"] = True
                if body:
                    S.set_fulltext(a["id"], body)
            if body:
                with st.expander("Full article", expanded=True):
                    for para in body.split("\n"):
                        if para.strip():
                            st.write(para)
            else:
                st.caption("Full text isn't available inside the app for this source (paywall or redirect link). Use **Open original**.")

            st.subheader("Related coverage")
            key = set(news.story_key(a["title"]).split())
            rel = [x for x in ARTS if x["id"] != a["id"] and len(key & set(news.story_key(x["title"]).split())) >= 2][:6]
            for x in rel:
                st.button(f"{x['title'][:120]}  ·  {x['publisher']}", key=f"rel{x['id']}", on_click=open_story, args=(x["id"],))
            if not rel:
                st.caption("No related stories in the current feed.")

        with right:
            st.subheader("Market impact")
            st.markdown(chip(f"Impact: {imp['level']}", f"wp-lvl-{imp['level']}") +
                        "".join(chip(m) for m in imp["markets"]), unsafe_allow_html=True)
            st.write(imp["summary"])
            if imp["sectors"]:
                st.markdown("".join(effect_chip(s["name"], s["effect"]) for s in imp["sectors"]), unsafe_allow_html=True)
                st.caption("▲ likely positive · ▼ likely negative · ◆ depends / watch. Keyword rules, indicative only.")

            ai = S.get_analysis(a["id"])
            key_ = api_key()
            if ai:
                st.markdown("**AI analysis**")
                st.write(ai.get("headline_view", ""))
                for m in ai.get("markets", []):
                    arrow = {"up": "▲", "down": "▼"}.get(m.get("direction"), "◆")
                    st.markdown(f"- {arrow} **{m.get('name')}** – {m.get('why', '')}")
                for s_ in ai.get("sectors", []):
                    arrow = {"up": "▲", "down": "▼"}.get(s_.get("direction"), "◆")
                    st.markdown(f"- {arrow} {s_.get('name')} – {s_.get('why', '')}")
                if ai.get("stocks_to_watch"):
                    st.markdown("**Stocks to watch:** " + ", ".join(ai["stocks_to_watch"]))
                st.caption(f"Horizon: {ai.get('time_horizon', '–')} · Confidence: {ai.get('confidence', '–')} · {ai.get('what_to_watch_next', '')}")
            elif key_:
                if st.button("Analyse impact with Claude", type="primary"):
                    with st.spinner("Asking Claude…"):
                        try:
                            res = impact.analyze_claude(a, S.get_fulltext(a["id"]) or a.get("summary", ""), key_,
                                                        S.get("model", C.DEFAULT_CLAUDE_MODEL))
                            S.set_analysis(a["id"], res)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Couldn't get an AI analysis: {str(e)[:200]}. Check your API key on the Settings page.")
            else:
                st.caption("Add an Anthropic API key in **Sources & settings** to get a detailed AI impact analysis.")

            st.subheader("How the market reacted")
            idx_names = imp["markets"] or ["S&P 500"]
            pick = st.selectbox("Market", idx_names + [n for n in C.INDICES if n not in idx_names] + list(C.COMMODITIES_FX), key=f"rx{a['id']}")
            tick = {**C.INDICES, **C.COMMODITIES_FX}[pick][0]
            df = load_intraday(tick)
            rx = markets.reaction(df, a["published"])
            if df.empty or not rx:
                st.caption("Price data not available for this period.")
            else:
                m1, m2 = st.columns(2)
                if "window_pct" in rx:
                    m1.metric(f"First {rx['window_min']} min", f"{rx['window_pct']:+.2f}%")
                m2.metric("Since publication", f"{rx['since_pct']:+.2f}%")
                if rx.get("note"):
                    st.caption(rx["note"])
                fig = go.Figure(go.Scatter(x=df.index.tz_convert(TZ), y=df["Close"], mode="lines", line=dict(width=2)))
                t = pd.Timestamp(a["published"]).tz_convert(TZ)
                fig.add_shape(type="line", x0=t, x1=t, y0=0, y1=1, yref="paper", line=dict(dash="dot", width=1.5, color="#d97706"))
                fig.add_annotation(x=t, y=1, yref="paper", text="News", showarrow=False, yanchor="bottom", font=dict(color="#d97706"))
                fig.update_layout(height=260, margin=dict(l=10, r=10, t=24, b=10), showlegend=False)
                st.plotly_chart(fig, width="stretch")
                st.caption("Markets move for many reasons at once – this shows timing, not cause.")

# ================================================================== TRACKER
elif page == "My tracker":
    st.title("My tracker")
    hist = S.history(1000)
    today = datetime.now(TZ).date()
    read_today = sum(1 for _, t in hist if datetime.fromisoformat(t).astimezone(TZ).date() == today)
    read_week = sum(1 for _, t in hist if datetime.fromisoformat(t).astimezone(TZ).date() > today - timedelta(days=7))
    tr = S.tracked()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Read today", read_today, border=True)
    m2.metric("Read this week", read_week, border=True)
    m3.metric("Stories tracked", len(tr), border=True)
    m4.metric("Topics followed", len(S.topics()), border=True)

    t1, t2, t3 = st.tabs(["Tracked stories", "Topics I follow", "Reading history"])
    with t1:
        if not tr:
            st.info("Tap **☆ Track** on any story to follow it here, with your own notes.")
        status_f = st.segmented_control("Show", ["Following", "Done", "All"], default="Following", key="trf")
        for t in tr:
            if status_f != "All" and t["status"] != status_f:
                continue
            a = BY_ID.get(t["id"]) or S.article(t["id"])
            if not a:
                continue
            a.setdefault("impact", impact.analyze_rules(a))
            with st.container(border=True):
                st.markdown(f"**{a['title']}**")
                st.caption(f"{a['publisher']} · published {local(a['published'])} · tracked {ago(t['added_at'])}")
                note = st.text_area("My notes", t["note"], key=f"note{t['id']}", height=70, placeholder="Why does this matter to you? What to check next?")
                c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
                if note != t["note"]:
                    S.update_tracked(t["id"], note=note)
                c1.button("Read", key=f"tr{t['id']}", on_click=open_story, args=(t["id"],), width="stretch")
                new_status = "Done" if t["status"] == "Following" else "Following"
                c2.button(f"Mark {new_status.lower()}", key=f"ts{t['id']}", on_click=S.update_tracked, args=(t["id"],), kwargs={"status": new_status}, width="stretch")
                c3.button("Remove", key=f"tu{t['id']}", on_click=S.untrack, args=(t["id"],), width="stretch")
                # follow-up coverage: newer stories that share key words
                key = set(news.story_key(a["title"]).split())
                upd = [x for x in ARTS if x["id"] != a["id"] and x["published"] > a["published"]
                       and len(key & set(news.story_key(x["title"]).split())) >= 2]
                if upd:
                    with st.expander(f"{len(upd)} newer update(s) on this story"):
                        for x in upd[:8]:
                            st.button(f"{x['title'][:110]} · {x['publisher']} · {ago(x['published'])}", key=f"tup{t['id']}{x['id']}", on_click=open_story, args=(x["id"],))
    with t2:
        with st.form("addtopic", clear_on_submit=True):
            c1, c2 = st.columns([4, 1])
            kw = c1.text_input("Follow a topic", placeholder="e.g. Adani, crude oil, Fed, semiconductor, Iran")
            if c2.form_submit_button("Follow", width="stretch") and kw:
                S.add_topic(kw)
                st.rerun()
        for tp in S.topics():
            kwl = tp["keyword"].lower()
            hits = [a for a in ARTS if kwl in (a["title"] + " " + a.get("summary", "")).lower()]
            new = [a for a in hits if a["published"] > tp["last_seen"]]
            with st.expander(f"{tp['keyword']} · {len(hits)} stories" + (f" · {len(new)} new" if new else "")):
                c1, c2 = st.columns([1, 1])
                c1.button("Mark all seen", key=f"seen{kwl}", on_click=S.topic_seen, args=(tp["keyword"],))
                c2.button("Stop following", key=f"rm{kwl}", on_click=S.remove_topic, args=(tp["keyword"],))
                for a in hits[:15]:
                    story_card(a, READ, TRACKED, f"tp{kwl}")
        if not S.topics():
            st.caption("Follow topics to see every new story that mentions them, with a 'new' count since your last visit.")
    with t3:
        if not hist:
            st.info("Stories you open or mark read will appear here.")
        for aid, when in hist[:100]:
            a = BY_ID.get(aid) or S.article(aid)
            if a:
                c1, c2 = st.columns([5, 1])
                c1.markdown(f"**{a['title']}**  \n<span class='wp-meta'>{a['publisher']} · read {ago(when)}</span>", unsafe_allow_html=True)
                c2.button("Open", key=f"h{aid}", on_click=open_story, args=(aid,))

# ================================================================== SETTINGS
elif page == "Sources & settings":
    st.title("Sources & settings")
    st.subheader("News sources")
    disabled = set(S.get("disabled_sources", []))
    rows = []
    for s_ in C.SOURCES + S.get("custom_sources", []):
        h = HEALTH.get(s_["name"], {})
        rows.append({"On": s_["name"] not in disabled, "Source": s_["name"], "Region": s_["region"], "Category": s_["category"],
                     "Status": ("✓ ok" if h.get("ok") else ("✗ " + (h.get("error") or "not fetched"))) if h else "off",
                     "Stories": h.get("count", 0)})
    ed = st.data_editor(pd.DataFrame(rows), hide_index=True, width="stretch",
                        disabled=["Source", "Region", "Category", "Status", "Stories"], key="src_editor")
    if st.button("Save source choices"):
        S.set("disabled_sources", [r["Source"] for _, r in ed.iterrows() if not r["On"]])
        load_news.clear(); st.success("Saved. Reloading news…"); st.rerun()

    with st.form("addsrc", clear_on_submit=True):
        st.markdown("**Add your own RSS feed**")
        c1, c2 = st.columns(2)
        nm = c1.text_input("Name", placeholder="e.g. Reuters via Google News – Oil")
        url = c2.text_input("RSS URL", placeholder="https://…/rss")
        c3, c4 = st.columns(2)
        rg = c3.selectbox("Region", C.REGIONS)
        ct = c4.selectbox("Category", C.CATEGORIES)
        st.caption("Tip: any Google News search works as a feed: https://news.google.com/rss/search?q=YOUR+TOPIC&hl=en-IN&gl=IN&ceid=IN:en")
        if st.form_submit_button("Add source") and nm and url.startswith("http"):
            S.set("custom_sources", S.get("custom_sources", []) + [{"name": nm, "url": url, "region": rg, "category": ct}])
            load_news.clear(); st.rerun()
    custom = S.get("custom_sources", [])
    if custom:
        rm = st.selectbox("Remove a custom source", ["–"] + [c["name"] for c in custom])
        if rm != "–" and st.button("Remove"):
            S.set("custom_sources", [c for c in custom if c["name"] != rm]); load_news.clear(); st.rerun()

    st.subheader("AI impact analysis (optional)")
    st.write("Add an Anthropic API key to get a reasoned market-impact note on any story. Each analysis costs a fraction of a cent with the default model.")
    k = st.text_input("Anthropic API key", type="password", value=st.session_state.get("api_key", ""),
                      help="Kept only for this browser session. For permanent use, put it in .streamlit/secrets.toml (see README).")
    if k != st.session_state.get("api_key", ""):
        st.session_state["api_key"] = k
    model = st.selectbox("Model", [C.DEFAULT_CLAUDE_MODEL, "claude-sonnet-5-5"],
                         index=0 if S.get("model", C.DEFAULT_CLAUDE_MODEL) == C.DEFAULT_CLAUDE_MODEL else 1)
    if model != S.get("model", C.DEFAULT_CLAUDE_MODEL):
        S.set("model", model)
    st.caption("Key status: " + ("✓ found" if api_key() else "not set"))


# runs last, after the page is drawn, so it never interrupts the first render
with st.sidebar:
    live_watch()
