"""
Conversion Analytics — an executive BI dashboard for used-car conversion data.

Run with:  python -m streamlit run app.py
"""
from __future__ import annotations

import os
from datetime import datetime
from io import BytesIO

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit import config as st_config

import auth as A
import charts as C
import chatbot as CB
import data_engine as DE
import theme as T
from fmt import inr, inr_full, num

APP_DIR = os.path.dirname(os.path.abspath(__file__))

st.set_page_config(
    page_title="Conversion Analytics · TVS Certified",
    page_icon="◈",
    layout="wide",
    # Always start expanded: the login stylesheet hides the sidebar with CSS,
    # and st.set_page_config only takes effect on the very first run of a
    # session.  Starting collapsed meant the sidebar stayed collapsed after
    # sign-in because subsequent set_page_config calls are ignored.
    initial_sidebar_state="expanded",
)


# ─────────────────────────────────────────────────────────────────────────────
# THEME
# ─────────────────────────────────────────────────────────────────────────────
def sync_native_theme(mode: str) -> None:
    """
    Push the palette into Streamlit's own theme configuration.

    Our stylesheet covers everything rendered as DOM, but a few widgets are
    painted onto a canvas — dataframes above all — and read their colours from
    Streamlit's theme rather than from CSS. Streamlit rebuilds the message that
    carries that theme at the start of every script run, so options written
    during one run take effect on the next; the toggle therefore ends with a
    rerun.

    The config store is process-wide, so with several browsers attached the last
    toggle wins for all of them. That is a fair trade for a dashboard run per
    analyst, and nothing outside presentation is affected.
    """
    for key, value in T.native_theme(mode).items():
        try:
            st_config.set_option(f"theme.{key}", value)
        except Exception:
            # Unknown option on an older Streamlit: the CSS layer still applies.
            pass


def set_theme_mode(mode: str) -> None:
    st.session_state.theme_mode = mode
    T.apply(mode)
    sync_native_theme(mode)


def theme_toggle() -> None:
    """Light/dark switch, rendered into the current container."""
    mode = st.session_state.theme_mode
    nxt = "light" if mode == "dark" else "dark"
    st.markdown('<div class="theme-row"><span class="lbl">Appearance</span></div>',
                unsafe_allow_html=True)
    label = "☀  Light mode" if nxt == "light" else "☾  Dark mode"
    if st.button(label, key="theme_switch", width="stretch",
                 help=f"Currently showing the {mode} palette — click to switch."):
        set_theme_mode(nxt)
        st.rerun()


# Bind the palette before anything is drawn: charts read these tokens at build
# time, so this has to happen at the very top of every run.
st.session_state.setdefault("theme_mode", T.DEFAULT_MODE)
T.apply(st.session_state.theme_mode)
sync_native_theme(st.session_state.theme_mode)
st.html(T.stylesheet())
st.html(T.animations())


# ─────────────────────────────────────────────────────────────────────────────
# FORMATTING
#
# ``inr``, ``inr_full`` and ``num`` now live in ``fmt`` so the assistant renders
# a figure exactly the way a KPI card does. They are imported at the top of this
# module and re-exported here by name for anything that reads ``app.inr``.
# ─────────────────────────────────────────────────────────────────────────────
def pchart(fig, **kw):
    """
    Render a Plotly figure full-width.

    ``st.plotly_chart`` still takes ``use_container_width`` rather than the newer
    ``width`` argument — anything else lands in ``**kwargs`` and is misread as a
    Plotly config option. Routing every chart through here keeps that detail in
    one place.
    """
    kw.pop("width", None)
    kw.setdefault("config", {"displaylogo": False,
                             "modeBarButtonsToRemove": ["lasso2d", "select2d"]})
    st.plotly_chart(fig, use_container_width=True, **kw)


# ─────────────────────────────────────────────────────────────────────────────
# DATA ACCESS
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def load_from_bytes(raw: bytes, _tag: str):
    return DE.parse_workbook(BytesIO(raw))


def load_default():
    """
    Load the workbook that sits next to ``app.py``.

    Only the parse is cached, and it is keyed on the file's bytes: reading is
    cheap next to parsing, so doing it on every run means a workbook that was
    momentarily unreadable — open in Excel, or mid-OneDrive-sync — is retried
    instead of a failure being cached for the life of the process. It also picks
    up a re-saved workbook without a restart.
    """
    path = DE.discover_default_workbook(APP_DIR)
    if not path:
        return None, ["No .xlsx workbook found in the application folder."], None
    raw = DE.read_bytes_resilient(path)
    if raw is None:
        return None, [f"'{os.path.basename(path)}' could not be read — it is locked by "
                      "another program. Close it in Excel, then press R to rerun."], path
    df, notes = parse_cached(raw)
    return df, notes, path


@st.cache_data(show_spinner=False)
def parse_cached(raw: bytes):
    return DE.parse_workbook(BytesIO(raw))


@st.cache_data(show_spinner=False)
def quality_of(df: pd.DataFrame):
    return DE.compute_quality(df)


# ─────────────────────────────────────────────────────────────────────────────
# INSIGHTS
# ─────────────────────────────────────────────────────────────────────────────
def build_insights(fdf: pd.DataFrame, pf: pd.DataFrame, m: dict,
                   deltas: dict) -> list[tuple[str, str, str]]:
    """Generate plain-language, decision-oriented observations."""
    out: list[tuple[str, str, str]] = []

    # Momentum
    if "revenue" in deltas and len(pf) >= 2:
        d = deltas["revenue"]
        direction = "grew" if d > 0 else "declined"
        acc = "jade" if d > 0 else "rose"
        out.append(("Momentum",
                    f"Commission revenue <b>{direction} {abs(d):.1f}%</b> in "
                    f"<b>{pf.iloc[-1]['Period']}</b> versus {pf.iloc[-2]['Period']}, "
                    f"landing at <b>{inr(pf.iloc[-1]['Revenue'])}</b>.", acc))

    # Geographic concentration
    if "State" in fdf.columns and fdf["State"].notna().any():
        g = fdf.groupby("State")["Total Income"].sum().sort_values(ascending=False)
        top, share = g.index[0], g.iloc[0] / g.sum() * 100 if g.sum() else 0
        acc = "amber" if share > 55 else "teal"
        risk = ("a concentration risk worth diversifying"
                if share > 55 else "a healthy spread across states")
        out.append(("Geography",
                    f"<b>{top}</b> contributes <b>{share:.1f}%</b> of commission revenue "
                    f"({inr(g.iloc[0])}) — {risk}.", acc))

    # Supply concentration
    if "Seller Name" in fdf.columns and fdf["Seller Name"].notna().any():
        sp = DE.entity_performance(fdf, "Seller Name", "Deals")
        top5 = sp.nlargest(5, "GMV")["GMVShare"].sum()
        acc = "rose" if top5 > 60 else ("amber" if top5 > 40 else "jade")
        out.append(("Supply concentration",
                    f"The top 5 sellers drive <b>{top5:.1f}%</b> of GMV across "
                    f"<b>{m['unique_sellers']}</b> active sellers "
                    f"(avg <b>{m['txn_per_seller']:.1f}</b> deals each).", acc))

    # Segment economics
    if "Seller Segment" in fdf.columns and fdf["Seller Segment"].nunique() > 1:
        seg = (fdf.groupby("Seller Segment")
                  .agg(rev=("Total Income", "sum"), gmv=("Final Bid Value", "sum"),
                       n=("Final Bid Value", "size")))
        seg["take"] = seg["rev"] / seg["gmv"] * 100
        best = seg["take"].idxmax()
        spread = seg["take"].max() - seg["take"].min()
        out.append(("Segment economics",
                    f"<b>{best}</b> sellers convert at the better take rate "
                    f"(<b>{seg.loc[best,'take']:.2f}%</b>), a "
                    f"<b>{spread:.2f} pt</b> spread over the other segment.", "violet"))

    # Price-band yield
    bands = DE.price_bands(fdf)
    if not bands.empty and bands["Transactions"].sum():
        b = bands[bands["Transactions"] > 0]
        best_band = b.loc[b["TakeRate"].idxmax()]
        busiest = b.loc[b["Transactions"].idxmax()]
        out.append(("Pricing yield",
                    f"Take rate peaks in the <b>{best_band['Band']}</b> band at "
                    f"<b>{best_band['TakeRate']:.2f}%</b>, while volume clusters in "
                    f"<b>{busiest['Band']}</b> ({int(busiest['Transactions']):,} deals).",
                    "amber"))

    # Demand repeat behaviour
    if "Buyer Name" in fdf.columns and fdf["Buyer Name"].notna().any():
        counts = fdf["Buyer Name"].value_counts()
        repeat = int((counts > 1).sum())
        repeat_share = repeat / len(counts) * 100 if len(counts) else 0
        out.append(("Demand quality",
                    f"<b>{repeat:,}</b> of {len(counts):,} buyers purchased more than once "
                    f"(<b>{repeat_share:.1f}%</b> repeat rate), averaging "
                    f"<b>{m['purchases_per_buyer']:.1f}</b> purchases per buyer.", "teal"))

    return out


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR FILTERS
#
# Each filter is a collapsed card carrying a badge that states its selection at
# a glance ("all", "3/22", "none"), so the whole filter stack stays readable
# without unfolding it. Selections live in session_state under `f_*` keys, which
# lets the quick actions and the reset control write them from an on_click
# callback — callbacks run before the script body, so a card's badge and its
# widget always agree within the same run.
# ─────────────────────────────────────────────────────────────────────────────
CHIP_MAX = 9        # up to this many options render as chips, beyond as a search list


def _touch(key: str) -> None:
    """
    Remember that a card has been used, so it stays unfolded.

    The badge lives in the expander's label, so every selection changes that
    label — which re-keys the element and remounts it at its collapsed default.
    Left alone, a card would snap shut under the cursor on each chip click.
    """
    st.session_state.setdefault("f_open", set()).add(key)


def _set_filter(key: str, value) -> None:
    st.session_state[key] = list(value) if isinstance(value, (list, tuple)) else value
    _touch(key)


def _reset_filters(plan: dict) -> None:
    for key, full in plan.items():
        st.session_state[key] = tuple(full) if isinstance(full, tuple) else list(full)
    st.session_state["f_open"] = set()      # fold the stack back to its resting state


def _sanitise(key: str, options: list) -> None:
    """
    Seed a filter with every option, and drop values the dataset no longer has.

    Swapping in an uploaded workbook changes the option lists underneath state
    that has already been stored; a multiselect raises if its value contains
    something outside its options, so stale entries are pruned here.
    """
    cur = st.session_state.get(key)
    if cur is None:
        st.session_state[key] = list(options)
        return
    keep = [v for v in cur if v in options]
    if len(keep) != len(cur):
        st.session_state[key] = keep


def _badge(key: str, options: list) -> str:
    picked = [v for v in (st.session_state.get(key) or []) if v in options]
    if not picked:
        return "none"
    return "all" if len(picked) >= len(options) else f"{len(picked)}/{len(options)}"


def _quick_actions(key: str, options: list, top: list | None) -> None:
    """Compact All / Top n / Clear row, applied before the widget is drawn."""
    cols = st.columns(3 if top else 2, gap="small")
    with cols[0]:
        st.button("All", key=f"qa_{key}_all", width="stretch",
                  on_click=_set_filter, args=(key, options),
                  help="Select every value")
    slot = 1
    if top:
        with cols[slot]:
            st.button(f"Top {len(top)}", key=f"qa_{key}_top", width="stretch",
                      on_click=_set_filter, args=(key, top),
                      help="Keep only the highest-volume values")
        slot += 1
    with cols[slot]:
        st.button("Clear", key=f"qa_{key}_clear", width="stretch",
                  on_click=_set_filter, args=(key, []),
                  help="Deselect everything")


def _filter_card(title: str, key: str, options: list, *, expanded: bool = False,
                 top: list | None = None) -> list:
    """One filter, rendered as a badged card. Returns the current selection."""
    _sanitise(key, options)
    open_now = expanded or key in st.session_state.get("f_open", set())
    with st.expander(f"{title}  `{_badge(key, options)}`", expanded=open_now):
        _quick_actions(key, options, top)
        if len(options) <= CHIP_MAX:
            st.pills(title, options, selection_mode="multi", key=key,
                     label_visibility="collapsed", on_change=_touch, args=(key,))
        else:
            st.multiselect(title, options, key=key, label_visibility="collapsed",
                           placeholder="Type to search…", on_change=_touch, args=(key,))
    return list(st.session_state.get(key) or [])


def _bid_card(bounds: tuple[float, float]) -> tuple[float, float]:
    lo, hi = bounds
    cur = st.session_state.get("f_bid")
    if (not isinstance(cur, (tuple, list)) or len(cur) != 2
            or float(cur[0]) < lo or float(cur[1]) > hi):
        st.session_state["f_bid"] = (lo, hi)
    a, b = st.session_state["f_bid"]
    at_full = a <= lo and b >= hi
    with st.expander(f"Bid value  `{'all' if at_full else 'custom'}`",
                     expanded=not at_full or "f_bid" in st.session_state.get("f_open", set())):
        st.markdown(f'<div class="flt-range"><b>{inr(a)}</b><i></i><b>{inr(b)}</b></div>',
                    unsafe_allow_html=True)
        st.slider("Final bid value (₹)", min_value=lo, max_value=hi,
                  step=max(1000.0, round((hi - lo) / 100, -3) or 1000.0),
                  format="₹%d", key="f_bid", label_visibility="collapsed",
                  on_change=_touch, args=("f_bid",))
    return tuple(st.session_state["f_bid"])


def _bid_bounds(df: pd.DataFrame) -> tuple[float, float]:
    col = df.get("Final Bid Value")
    if col is None or not col.notna().any():
        return 0.0, 1.0
    lo = float(int(np.nanmin(col)))
    hi = float(int(np.nanmax(col)) + 1)
    return lo, (hi if hi > lo else lo + 1)


def _active_filters(plan: dict) -> int:
    n = 0
    for key, full in plan.items():
        cur = st.session_state.get(key)
        if cur is None:
            continue
        if isinstance(full, tuple):
            n += 0 if (float(cur[0]) <= full[0] and float(cur[1]) >= full[1]) else 1
        else:
            n += 0 if set(cur) == set(full) else 1
    return n


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
def sidebar_controls(df: pd.DataFrame, source_label: str, source_path: str | None):
    with st.sidebar:
        st.markdown(
            '<div class="sb-brand"><div class="sb-mark">◈</div>'
            '<div><strong>Conversion Analytics</strong>'
            '<span>TVS Certified</span></div></div>',
            unsafe_allow_html=True)

        A.sidebar_account()
        theme_toggle()

        st.markdown('<div class="sb-head">Active source</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="sb-stat"><span>Dataset</span><b>{source_label}</b></div>'
            f'<div class="sb-stat"><span>Records</span><b>{len(df):,}</b></div>'
            f'<div class="sb-stat"><span>Fields</span><b>'
            f'{len([c for c in df.columns if not c.startswith("_")])}</b></div>',
            unsafe_allow_html=True)
        if source_path:
            st.caption(f"📄 {os.path.basename(source_path)}")

        # ── Filters ─────────────────────────────────────────────────────
        # Option lists are resolved first: the header badge and the reset
        # control both need to know what "everything selected" means before
        # any card is drawn.
        cards: list[tuple[str, str, list, dict]] = [
            ("Financial year", "f_fy",
             sorted(df["FY"].dropna().unique().tolist()), {"expanded": True}),
            ("Month", "f_month",
             [m for m in DE.MONTH_ORDER if m in set(df["Month"].dropna())],
             {"expanded": True}),
            ("State", "f_state",
             sorted(df["State"].dropna().unique().tolist()), {}),
        ]
        if "Seller Segment" in df.columns:
            cards.append(("Seller segment", "f_segment",
                          sorted(df["Seller Segment"].dropna().unique().tolist()), {}))
        if "Make" in df.columns:
            cards.append(("Make", "f_make",
                          sorted(df["Make"].dropna().unique().tolist()),
                          {"top": df["Make"].value_counts().head(8).index.tolist()}))

        bounds = _bid_bounds(df)
        plan = {key: opts for _, key, opts, _ in cards} | {"f_bid": bounds}
        active = _active_filters(plan)

        st.markdown(
            '<div class="flt-head"><span class="t">Filters</span>'
            '<span class="r"></span>'
            f'<span class="n{" on" if active else ""}">'
            f'{f"{active} active" if active else "all data"}</span></div>',
            unsafe_allow_html=True)
        st.button("↺  Reset filters", key="flt_reset", disabled=not active,
                  on_click=_reset_filters, args=(plan,),
                  help="Return every filter to its full range")

        columns = {"f_fy": "FY", "f_month": "Month", "f_state": "State",
                   "f_segment": "Seller Segment", "f_make": "Make"}
        sel = {columns[key]: _filter_card(title, key, opts, **kw)
               for title, key, opts, kw in cards}
        bid_range = _bid_card(bounds)

        st.divider()
        if st.session_state.get("uploaded") is not None:
            if st.button("↺ Restore bundled dataset", width="stretch"):
                st.session_state.uploaded = None
                st.rerun()
        st.caption(f"Rendered {datetime.now():%d %b %Y · %H:%M}")

    return sel, bid_range


def apply_filters(df: pd.DataFrame, sel: dict, bid_range) -> pd.DataFrame:
    mask = pd.Series(True, index=df.index)
    for col, vals in sel.items():
        if col in df.columns:
            mask &= df[col].isin(vals)
    if "Final Bid Value" in df.columns:
        mask &= df["Final Bid Value"].between(bid_range[0], bid_range[1]) | df["Final Bid Value"].isna()
    return df[mask].copy()


# ─────────────────────────────────────────────────────────────────────────────
# HERO
# ─────────────────────────────────────────────────────────────────────────────
def hero(title: str, sub: str, kicker: str, pills: list[str]):
    st.markdown(
        f'<div class="hero"><div class="hero-inner"><div>'
        f'<div class="eyebrow">{kicker}</div>'
        f'<h1>{title}</h1><p>{sub}</p></div>'
        f'<div class="hero-meta">{"".join(pills)}</div>'
        f'</div></div>',
        unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 — OVERVIEW
# ═════════════════════════════════════════════════════════════════════════════
def tab_overview(fdf: pd.DataFrame):
    if fdf.empty:
        st.warning("No records match the current filters. Widen the selection in the sidebar.")
        return

    m = DE.compute_metrics(fdf)
    pf = DE.period_frame(fdf)
    deltas = DE.latest_period_deltas(pf)
    dlabel = deltas.get("_label", "")

    st.markdown(T.section("Headline performance",
                          f"{len(fdf):,} transactions in scope"), unsafe_allow_html=True)
    r1 = st.columns(5)
    cards = [
        ("Transactions", num(m["transactions"]), "▦", "jade", deltas.get("transactions"),
         f"{m['transactions'] / max(len(pf), 1):,.0f} per period avg"),
        ("GMV", inr(m["gmv"]), "◈", "violet", deltas.get("gmv"),
         f"avg deal {inr(m['avg_txn_value'])}"),
        ("Commission revenue", inr(m["revenue"]), "◆", "amber", deltas.get("revenue"),
         "excluding GST"),
        ("Take rate", f"{m['take_rate']:.2f}%", "◐", "teal", deltas.get("take_rate"),
         "revenue ÷ GMV"),
        ("Avg. commission", inr(m["avg_commission"]), "◇", "rose",
         deltas.get("avg_commission"), "per transaction"),
    ]
    for col, (lbl, val, ico, acc, dv, sub) in zip(r1, cards):
        with col:
            st.markdown(T.kpi_card(lbl, val, ico, acc, dv, dlabel, sub),
                        unsafe_allow_html=True)

    st.markdown("<div style='height:.9rem'></div>", unsafe_allow_html=True)
    r2 = st.columns(5)
    marketplace = [
        ("Unique sellers", num(m["unique_sellers"]), "⬢", "jade", None,
         "distinct supply accounts"),
        ("Avg. transactions / seller", f"{m['txn_per_seller']:.1f}", "⬡", "teal", None,
         "supply-side depth"),
        ("Unique buyers", num(m["unique_buyers"]), "⬣", "violet", None,
         "distinct demand accounts"),
        ("Avg. purchases / buyer", f"{m['purchases_per_buyer']:.1f}", "◎", "amber", None,
         "demand repeat rate"),
        ("Avg. transaction value", inr(m["avg_txn_value"]), "◍", "rose", None,
         "mean winning bid"),
    ]
    for col, (lbl, val, ico, acc, dv, sub) in zip(r2, marketplace):
        with col:
            st.markdown(T.kpi_card(lbl, val, ico, acc, dv, dlabel, sub),
                        unsafe_allow_html=True)

    # ── Insights ────────────────────────────────────────────────────────
    insights = build_insights(fdf, pf, m, deltas)
    if insights:
        st.markdown(T.section("What the numbers are saying",
                              "auto-generated from the current selection"),
                    unsafe_allow_html=True)
        for row_start in range(0, len(insights), 3):
            chunk = insights[row_start:row_start + 3]
            cols = st.columns(3)
            for col, (tag, text, acc) in zip(cols, chunk):
                with col:
                    st.markdown(T.insight_card(tag, text, acc), unsafe_allow_html=True)
            if row_start + 3 < len(insights):
                st.markdown("<div style='height:.7rem'></div>", unsafe_allow_html=True)

    # ── Trends ──────────────────────────────────────────────────────────
    st.markdown(T.section("Trajectory", "period-on-period movement"), unsafe_allow_html=True)
    pchart(C.revenue_vs_transactions(pf))

    c1, c2 = st.columns(2)
    with c1:
        pchart(C.monthly_by_fy(pf, "GMV", "GMV by month, year on year", "₹"))
    with c2:
        pchart(C.take_rate_trend(pf))

    c3, c4 = st.columns(2)
    with c3:
        pchart(C.monthly_by_fy(pf, "Transactions", "Transactions by month, year on year"))
    with c4:
        pchart(C.avg_bid_trend(pf))

    # ── Geography & segment ─────────────────────────────────────────────
    st.markdown(T.section("Geography and seller mix", "where revenue is created"),
                unsafe_allow_html=True)
    g1, g2 = st.columns([1, 1.35])
    with g1:
        pchart(C.state_donut(fdf))
    with g2:
        pchart(C.state_performance(fdf))

    pchart(C.segment_split(fdf))
    pchart(C.cohort_heatmap(fdf, "State", "Revenue by state and period"))


# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 — PERFORMANCE
# ═════════════════════════════════════════════════════════════════════════════
def _perf_table(perf: pd.DataFrame, label_col: str, count_col: str, n: int,
                key: str, search_cap: int = 200):
    noun = label_col.replace(" Name", "").lower()
    query = st.text_input(
        f"Search {noun}s", key=f"perf_search_{key}",
        placeholder=f"Type part of a {noun} name to search all "
                    f"{len(perf):,} {noun}s…",
    ).strip()

    if query:
        hits = perf[perf[label_col].astype(str)
                    .str.contains(query, case=False, na=False, regex=False)]
        if hits.empty:
            st.info(f"No {noun} matches “{query}”. The search looks at every "
                    f"{noun} in the current filter scope, not just the rows on display.")
            return
        d = hits.head(search_cap).copy()
        shown = len(d)
        st.caption(f"{len(hits):,} {noun}{'' if len(hits) == 1 else 's'} match "
                   f"“{query}”" + (f" · showing the first {shown:,} "
                                   f"by {count_col.lower()}"
                                   if shown < len(hits) else ""))
    else:
        d = perf.head(n).copy()

    # Keep the GMV-share bars comparable regardless of the active search.
    share_max = float(max(perf["GMVShare"].max(), 1))

    show = pd.DataFrame({
        label_col: d[label_col],
        count_col: d[count_col],
        "GMV": d["GMV"],
        "GMV share %": d["GMVShare"].round(2),
        "Avg. transaction value": d["AvgTxnValue"],
        "Commission": d["Commission"],
        "Avg. commission": d["AvgCommission"],
        "Take rate %": d["TakeRate"].round(2),
    })
    st.dataframe(
        show, width="stretch", hide_index=True, height=min(520, 42 + 35 * len(show)),
        column_config={
            count_col: st.column_config.NumberColumn(count_col, format="%d", width="small"),
            "GMV": st.column_config.NumberColumn("GMV", format="₹%.0f"),
            "GMV share %": st.column_config.ProgressColumn(
                "GMV share", format="%.2f%%", min_value=0.0,
                max_value=share_max),
            "Avg. transaction value": st.column_config.NumberColumn(
                "Avg. txn value", format="₹%.0f"),
            "Commission": st.column_config.NumberColumn("Commission", format="₹%.0f"),
            "Avg. commission": st.column_config.NumberColumn("Avg. commission", format="₹%.0f"),
            "Take rate %": st.column_config.NumberColumn("Take rate", format="%.2f%%"),
        },
    )


def tab_performance(fdf: pd.DataFrame):
    if fdf.empty:
        st.warning("No records match the current filters.")
        return

    top_n = st.slider("Rows to display in the ranking tables", 5, 50, 15, step=5)

    sellers = DE.entity_performance(fdf, "Seller Name", "Deals")
    buyers = DE.entity_performance(fdf, "Buyer Name", "Purchases")

    st.markdown(T.section("Key seller performance", "supply side contribution"),
                unsafe_allow_html=True)
    if sellers.empty:
        st.info("Seller Name is not available in this dataset.")
    else:
        s1, s2 = st.columns([1.15, 1])
        with s1:
            pchart(C.pareto(sellers, "Seller Name", "Deals",
                            "Seller GMV contribution and cumulative share"))
        with s2:
            pchart(C.cohort_heatmap(
                fdf[fdf["Seller Name"].isin(sellers.head(12)["Seller Name"])],
                "Seller Name", "Top sellers · revenue by period"))
        _perf_table(sellers, "Seller Name", "Deals", top_n, key="sellers")

    st.markdown(T.section("Key buyer performance", "demand side contribution"),
                unsafe_allow_html=True)
    if buyers.empty:
        st.info("Buyer Name is not available in this dataset.")
    else:
        b1, b2 = st.columns([1.15, 1])
        with b1:
            pchart(C.pareto(buyers, "Buyer Name", "Purchases",
                            "Buyer GMV contribution and cumulative share"))
        with b2:
            counts = fdf["Buyer Name"].value_counts()
            freq = (counts.value_counts().sort_index()
                          .rename_axis("Purchases").reset_index(name="Buyers"))
            freq["Purchases"] = freq["Purchases"].astype(str) + "×"
            fig = go.Figure(go.Bar(
                x=freq["Purchases"], y=freq["Buyers"],
                marker=dict(color=freq["Buyers"], colorscale=T.SCALE_VIOLET, line=dict(width=0)),
                text=freq["Buyers"], textposition="outside",
                textfont=dict(size=10.5, color=T.TEXT_MUTED),
                hovertemplate="<b>%{x} purchases</b><br>%{y:,} buyers<extra></extra>"))
            C.style(fig, height=400, title="Buyer repeat-purchase distribution",
                    legend_top=False)
            fig.update_xaxes(title_text="purchases made")
            pchart(fig)
        _perf_table(buyers, "Buyer Name", "Purchases", top_n, key="buyers")

    st.markdown(T.section("Vehicle portfolio", "what is actually moving"),
                unsafe_allow_html=True)
    v1, v2 = st.columns(2)
    with v1:
        pchart(C.make_treemap(fdf), width="stretch")
    with v2:
        pchart(C.top_models(fdf), width="stretch")

    v3, v4 = st.columns(2)
    with v3:
        pchart(C.price_band_chart(DE.price_bands(fdf)), width="stretch")
    with v4:
        pchart(C.age_vs_value(fdf), width="stretch")

    st.markdown(T.section("Export", "take the filtered slice with you"),
                unsafe_allow_html=True)
    export = fdf.drop(columns=[c for c in ("_month_idx",) if c in fdf.columns])
    st.download_button(
        "⤓  Download filtered data (CSV)",
        data=export.to_csv(index=False).encode("utf-8"),
        file_name=f"conversion_filtered_{datetime.now():%Y%m%d_%H%M}.csv",
        mime="text/csv",
    )


# ═════════════════════════════════════════════════════════════════════════════
# TAB 3 — UPLOAD
# ═════════════════════════════════════════════════════════════════════════════
def tab_upload():
    hero("Bring your own workbook",
         "Drop in a conversion extract with the same shape as the template. "
         "The header row is detected automatically, months and makes are standardised, "
         "and the file is validated before it replaces the active dataset.",
         "Data ingestion",
         ['<span class="pill neutral"><span class="dot"></span>.xlsx / .xls</span>',
          '<span class="pill neutral">First sheet</span>'])

    spec = pd.DataFrame({
        "Column": DE.REQUIRED_COLUMNS,
        "Type": ["Text", "Text", "Text", "Text", "Text", "Text", "Text", "Text", "Text",
                 "Number", "Number", "Number", "Number"],
        "Example": ["FY27", "Jan", "TN", "TN01AB1234", "HYUNDAI", "i20",
                    "Exchange Chennai", "Captive", "A. Kumar",
                    "2018", "45000", "350000", "5084.75"],
        "Notes": ["FYnn format", "Jan…Dec, any case", "State or cluster code",
                  "Registration number", "Manufacturer", "Model name",
                  "Selling entity", "Captive / Non-Captive", "Buying party",
                  "Year of manufacture", "Kilometres", "Winning bid",
                  "Commission, excluding GST"],
    })
    with st.expander("◈  Expected template", expanded=False):
        st.dataframe(spec, width="stretch", hide_index=True, height=500)
        st.markdown('<p class="small-note">Banner rows above the header are skipped '
                    'automatically. Extra columns are preserved and profiled in the '
                    'Data Quality tab.</p>', unsafe_allow_html=True)

    up = st.file_uploader("Workbook", type=["xlsx", "xls"], label_visibility="collapsed")
    if up is None:
        return

    with st.spinner("Parsing and validating…"):
        raw = up.read()
        df, notes = load_from_bytes(raw, up.name)

    if df is None:
        st.error("**Could not use this file.**\n\n" + "\n\n".join(f"- {n}" for n in notes))
        return

    errors, warnings = DE.validate_schema(df)

    st.markdown(T.section("Validation result", up.name), unsafe_allow_html=True)
    if errors:
        st.error("**Blocking issues — the file cannot be loaded:**\n\n"
                 + "\n".join(f"- {e}" for e in errors))
    else:
        st.success(f"Schema accepted. **{len(df):,}** usable records parsed.")
    for w in warnings:
        st.warning(w)
    if notes:
        with st.expander(f"◇  {len(notes)} normalisation(s) applied", expanded=False):
            for n in notes:
                st.markdown(f"- {n}")

    if errors:
        return

    m = DE.compute_metrics(df)
    q = quality_of(df)
    g_txt, g_acc = DE.grade(q["overall"])

    cols = st.columns(5)
    preview = [
        ("Records", num(len(df)), "▦", "jade"),
        ("GMV", inr(m["gmv"]), "◈", "violet"),
        ("Commission revenue", inr(m["revenue"]), "◆", "amber"),
        ("Unique sellers", num(m["unique_sellers"]), "⬢", "teal"),
        ("Quality score", f"{q['overall']:.1f}%", "◉", g_acc),
    ]
    for col, (lbl, val, ico, acc) in zip(cols, preview):
        with col:
            st.markdown(T.kpi_card(lbl, val, ico, acc), unsafe_allow_html=True)

    st.markdown(T.section("Preview", "first 15 rows after normalisation"),
                unsafe_allow_html=True)
    st.dataframe(df.drop(columns=[c for c in ("_month_idx",) if c in df.columns]).head(15),
                 width="stretch", hide_index=True)

    a, b = st.columns([1, 3])
    with a:
        if st.button("✓  Load this dataset", type="primary", width="stretch"):
            st.session_state.uploaded = df
            st.session_state.uploaded_name = up.name
            st.rerun()
    with b:
        st.markdown('<p class="small-note">Loading replaces the active dataset for this '
                    'session only. The bundled workbook on disk is never modified, and you '
                    'can restore it any time from the sidebar.</p>', unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 4 — DATA QUALITY & SSOT
# ═════════════════════════════════════════════════════════════════════════════
def tab_quality(df: pd.DataFrame, source_label: str, source_path: str | None,
                notes: list[str]):
    q = quality_of(df)
    g_txt, g_acc = DE.grade(q["overall"])

    hero("Data quality and single source of truth",
         "Four scored dimensions, every validation rule, and the canonical metric "
         "definitions the rest of this dashboard is built on. Assessed on the full "
         "dataset, independent of the sidebar filters.",
         "Governance",
         [f'<span class="pill"><span class="dot live"></span>{g_txt} · '
          f'{q["overall"]:.1f}%</span>',
          f'<span class="pill neutral">{q["rows"]:,} records × {q["cols"]} fields</span>'])

    # ── Scores ──────────────────────────────────────────────────────────
    st.markdown(T.section("Quality scorecard", "0–100 per dimension, equally weighted"),
                unsafe_allow_html=True)

    gcol, rcol, scol = st.columns([1, 1, 1.5])
    with gcol:
        st.markdown('<div class="panel"><h4>Composite score</h4></div>',
                    unsafe_allow_html=True)
        pchart(C.quality_gauge(q["overall"], g_acc),
               config={"displayModeBar": False})
    with rcol:
        st.markdown('<div class="panel"><h4>Dimension balance</h4></div>',
                    unsafe_allow_html=True)
        pchart(C.dimension_radar(q["dimensions"]),
               config={"displayModeBar": False})
    with scol:
        dim_meta = [
            ("Completeness", q["completeness"], f"{q['null_cells']:,} empty of "
                                                f"{q['total_cells']:,} cells", "jade"),
            ("Uniqueness", q["uniqueness"], f"{q['duplicate_rows']:,} duplicate rows · "
                                            f"{q['duplicate_vehicles']:,} repeated regs", "teal"),
            ("Validity", q["validity"], f"{q['invalid_rows']:,} rows break at least one rule",
             "amber"),
            ("Consistency", q["consistency"],
             f"{q['consistency_rows_affected']:,} rows use a non-standard spelling", "violet"),
        ]
        pairs = st.columns(2)
        for i, (lbl, val, note, acc) in enumerate(dim_meta):
            with pairs[i % 2]:
                st.markdown(T.score_card(lbl, f"{val:.1f}%", note, acc, pct=val),
                            unsafe_allow_html=True)
                st.markdown("<div style='height:.55rem'></div>", unsafe_allow_html=True)

    # ── Completeness ────────────────────────────────────────────────────
    st.markdown(T.section("Completeness", "population rate per field"),
                unsafe_allow_html=True)
    c1, c2 = st.columns([1, 1])
    with c1:
        pchart(C.null_profile(q["column_health"]), width="stretch")
    with c2:
        pchart(C.missingness_map(df), width="stretch")

    health = q["column_health"]
    st.dataframe(
        health[["Column", "Type", "Populated %", "Nulls", "Distinct"]],
        width="stretch", hide_index=True, height=min(480, 42 + 35 * len(health)),
        column_config={
            "Populated %": st.column_config.ProgressColumn(
                "Populated", format="%.2f%%", min_value=0.0, max_value=100.0),
            "Nulls": st.column_config.NumberColumn("Nulls", format="%d"),
            "Distinct": st.column_config.NumberColumn("Distinct values", format="%d"),
        })

    # ── Validity ────────────────────────────────────────────────────────
    st.markdown(T.section("Validity rules", "domain and range constraints"),
                unsafe_allow_html=True)
    v1, v2 = st.columns([1.25, 1])
    with v1:
        rows = []
        for name, fails, examples in q["validity_checks"]:
            meta = (f"{fails:,} row(s) failing" if fails else "all rows pass")
            if examples:
                meta += " · e.g. " + ", ".join(f"“{e}”" for e in examples[:4])
            rows.append(T.check_row(fails == 0, name, meta))
        st.markdown('<div class="panel"><h4>◆ Rule results</h4>' + "".join(rows) + '</div>',
                    unsafe_allow_html=True)
    with v2:
        out = q["outliers"]
        if out:
            body = "".join(
                f'<div class="sb-stat"><span>{k}</span>'
                f'<b>{v["count"]:,} ({v["pct"]:.2f}%)</b></div>'
                f'<p class="small-note" style="margin:-.15rem 0 .6rem">'
                f'expected band {inr_full(v["lower"])} – {inr_full(v["upper"])}, '
                f'observed {inr_full(v["min"])} – {inr_full(v["max"])}</p>'
                for k, v in out.items())
            st.markdown('<div class="panel"><h4>◇ IQR outliers</h4>' + body +
                        '<p class="small-note">Outliers are flagged, never dropped — '
                        'high-value vehicles are legitimate but worth confirming.</p></div>',
                        unsafe_allow_html=True)
        else:
            st.info("No numeric columns available for outlier analysis.")

    pchart(C.outlier_box(df, ["Final Bid Value", "Total Income", "Odometer"]))

    # ── Uniqueness ──────────────────────────────────────────────────────
    st.markdown(T.section("Uniqueness", "duplicate detection at the vehicle grain"),
                unsafe_allow_html=True)
    u1, u2 = st.columns([1, 1.3])
    with u1:
        st.markdown(
            '<div class="panel"><h4>⬢ Grain integrity</h4>'
            f'<div class="sb-stat"><span>Exact duplicate rows</span>'
            f'<b>{q["duplicate_rows"]:,}</b></div>'
            f'<div class="sb-stat"><span>Repeated registrations</span>'
            f'<b>{q["duplicate_vehicles"]:,}</b></div>'
            f'<div class="sb-stat"><span>Declared grain</span><b>1 row = 1 vehicle</b></div>'
            '<p class="small-note">A registration can legitimately reappear if the same '
            'vehicle transacts twice. Exact duplicate rows cannot, and should be '
            'investigated upstream.</p></div>',
            unsafe_allow_html=True)
    with u2:
        rv = q["repeated_vehicle_list"]
        if isinstance(rv, pd.DataFrame) and not rv.empty:
            st.dataframe(rv, width="stretch", hide_index=True, height=320)
        else:
            st.success("Every vehicle registration appears exactly once.")

    # ── Consistency ─────────────────────────────────────────────────────
    st.markdown(T.section("Consistency", "the same entity written more than one way"),
                unsafe_allow_html=True)
    var = q["variant_report"]
    if isinstance(var, pd.DataFrame) and not var.empty:
        st.markdown(
            f'<p class="small-note">{len(var)} value group(s) differ only by case, spacing '
            f'or punctuation, affecting {q["consistency_rows_affected"]:,} rows. These are '
            f'normalised on load so aggregations stay correct, and are listed here so the '
            f'source system can be corrected.</p>', unsafe_allow_html=True)
        st.dataframe(var, width="stretch", hide_index=True,
                     height=min(420, 42 + 35 * len(var)))
    else:
        st.success("All categorical values are standardised — no case or spacing variants found.")

    # ── SSOT ────────────────────────────────────────────────────────────
    st.markdown(T.section("Single source of truth", "lineage, coverage and definitions"),
                unsafe_allow_html=True)

    cov = q["coverage"]
    l1, l2 = st.columns([1, 1])
    with l1:
        st.markdown(
            '<div class="panel"><h4>◈ Lineage</h4><ul>'
            f'<li>Source: <code>{source_label}</code></li>'
            f'<li>File: <code>{os.path.basename(source_path) if source_path else "in-session upload"}</code></li>'
            f'<li>Grain: <code>one row per converted vehicle</code></li>'
            f'<li>Records: <code>{q["rows"]:,}</code> · Fields: <code>{q["cols"]}</code></li>'
            f'<li>Loaded: <code>{datetime.now():%d %b %Y %H:%M}</code></li>'
            f'<li>Currency: <code>INR, commission excludes GST</code></li>'
            '</ul></div>', unsafe_allow_html=True)
    with l2:
        st.markdown(
            '<div class="panel"><h4>◐ Coverage</h4><ul>'
            f'<li>Financial years: <code>{", ".join(cov["FY"]) or "—"}</code></li>'
            f'<li>Months: <code>{", ".join(cov["Month"]) or "—"}</code></li>'
            f'<li>States: <code>{", ".join(cov["State"]) or "—"}</code></li>'
            f'<li>Segments: <code>{", ".join(cov["Segment"]) or "—"}</code></li>'
            '</ul></div>', unsafe_allow_html=True)

    st.markdown("<div style='height:.9rem'></div>", unsafe_allow_html=True)
    st.markdown('<div class="panel"><h4>◆ Canonical metric definitions</h4>'
                '<p class="small-note" style="margin-top:-.4rem">Every figure in this '
                'dashboard is derived from these formulas in one place '
                '(<code>data_engine.compute_metrics</code>), so two tabs can never '
                'disagree.</p></div>', unsafe_allow_html=True)
    st.dataframe(
        pd.DataFrame(DE.METRIC_DEFINITIONS, columns=["Metric", "Formula", "Interpretation"]),
        width="stretch", hide_index=True, height=400)

    if notes:
        with st.expander(f"◇  Normalisations applied when loading ({len(notes)})",
                         expanded=False):
            for n in notes:
                st.markdown(f"- {n}")

    st.markdown(T.section("Field profile", "type, cardinality and sample values"),
                unsafe_allow_html=True)
    work = df.drop(columns=[c for c in ("_month_idx", "Period") if c in df.columns])
    profile = pd.DataFrame({
        "Field": work.columns,
        "Type": [str(t) for t in work.dtypes],
        "Populated": [int(work[c].notna().sum()) for c in work.columns],
        "Distinct": [int(work[c].nunique(dropna=True)) for c in work.columns],
        "Sample values": [", ".join(map(str, work[c].dropna().unique()[:3])) or "—"
                          for c in work.columns],
    })
    st.dataframe(profile, width="stretch", hide_index=True,
                 height=min(520, 42 + 35 * len(profile)))


# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════
def main():
    st.session_state.setdefault("uploaded", None)
    st.session_state.setdefault("uploaded_name", "")

    # Nothing below this line renders until a session is established: the whole
    # script runs server-side, so an unauthenticated visitor never receives the
    # data, only the sign-in screen.
    if not A.require_login():
        return

    if st.session_state.uploaded is not None:
        df = st.session_state.uploaded
        notes: list[str] = []
        source_label = "Uploaded"
        source_path = st.session_state.uploaded_name or None
    else:
        df, notes, source_path = load_default()
        source_label = "Bundled workbook"

    if df is None:
        with st.sidebar:
            st.markdown(
                '<div class="sb-brand"><div class="sb-mark">◈</div>'
                '<div><strong>Conversion Analytics</strong>'
                '<span>TVS Certified</span></div></div>',
                unsafe_allow_html=True)
            A.sidebar_account()
            theme_toggle()
            # Filters describe a dataset, so there are none to draw here. Saying
            # so is better than a silently short sidebar, which reads as the
            # filter stack having vanished.
            st.markdown('<div class="flt-head"><span class="t">Filters</span>'
                        '<span class="r"></span><span class="n">no data</span></div>',
                        unsafe_allow_html=True)
            st.caption("Filters appear once a dataset is loaded.")
            if st.button("↻  Retry loading the workbook", key="reload_default",
                         width="stretch",
                         help="Re-read the workbook next to app.py"):
                st.rerun()
        hero("Conversion Analytics",
             "No dataset is loaded yet. Upload a conversion workbook to begin.",
             "Getting started",
             ['<span class="pill amber"><span class="dot"></span>Awaiting data</span>'])
        for n in (notes or []):
            st.warning(n)
        tab_upload()
        # The assistant still answers "how do I load data" with no dataset present.
        CB.render({"df": None, "fdf": None, "sel": {}, "bid_range": None,
                   "source_label": "none", "source_path": None,
                   "theme_mode": st.session_state.theme_mode})
        return

    sel, bid_range = sidebar_controls(df, source_label, source_path)
    fdf = apply_filters(df, sel, bid_range)

    m_all = DE.compute_metrics(df)
    m_sel = DE.compute_metrics(fdf)
    share = (m_sel["transactions"] / m_all["transactions"] * 100) if m_all["transactions"] else 0
    cov_fy = ", ".join(sorted(df["FY"].dropna().unique().tolist()))

    hero("Conversion Analytics",
         "Transaction-level view of used-car conversions across states, sellers, buyers "
         "and vehicle segments — built to answer where revenue comes from, which "
         "relationships carry it, and where the yield is strongest.",
         f"{cov_fy} · Executive overview",
         [f'<span class="pill"><span class="dot live"></span>'
          f'{m_sel["transactions"]:,} of {m_all["transactions"]:,} records '
          f'({share:.0f}%)</span>',
          f'<span class="pill neutral">GMV in view {inr(m_sel["gmv"])}</span>',
          f'<span class="pill amber">Revenue {inr(m_sel["revenue"])}</span>'])

    t1, t2, t3, t4 = st.tabs([
        "◈  Overview",
        "⬢  Sellers, Buyers & Vehicles",
        "⤒  Upload Data",
        "◉  Data Quality & SSOT",
    ])
    with t1:
        tab_overview(fdf)
    with t2:
        tab_performance(fdf)
    with t3:
        tab_upload()
    with t4:
        tab_quality(df, source_label, source_path, notes)

    # The assistant is drawn last so it floats above the finished layout, and it
    # receives both frames: the filtered one for "what am I looking at"
    # questions, the full one for anything asked "overall". The quality report is
    # passed as a callable so its scan only runs if a question needs it.
    CB.render({
        "df": df,
        "fdf": fdf,
        "sel": sel,
        "bid_range": bid_range,
        "source_label": source_label,
        "source_path": source_path,
        "theme_mode": st.session_state.theme_mode,
        "quality_fn": lambda: quality_of(df),
    })


if __name__ == "__main__":
    main()
