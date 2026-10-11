"""
Diagnostic: reproduce the exact sidebar_controls path and catch any error
that might be silently swallowed by Streamlit's expander/pills rendering.
"""
import traceback
from io import BytesIO

import pandas as pd
import streamlit as st

import data_engine as DE
import theme as T

st.set_page_config(layout="wide", initial_sidebar_state="expanded")
st.session_state.setdefault("theme_mode", T.DEFAULT_MODE)
T.apply(st.session_state.theme_mode)
st.html(T.stylesheet())
st.html(T.animations())

# Load data the same way app.py does
path = DE.discover_default_workbook(".")
raw = DE.read_bytes_resilient(path)
df, notes = DE.parse_workbook(BytesIO(raw))

CHIP_MAX = 9

def _sanitise(key, options):
    cur = st.session_state.get(key)
    if cur is None:
        st.session_state[key] = list(options)
        return
    keep = [v for v in cur if v in options]
    if len(keep) != len(cur):
        st.session_state[key] = keep

def _badge(key, options):
    picked = [v for v in (st.session_state.get(key) or []) if v in options]
    if not picked:
        return "none"
    return "all" if len(picked) >= len(options) else f"{len(picked)}/{len(options)}"

def _filter_card(title, key, options, *, expanded=False, top=None):
    _sanitise(key, options)
    with st.expander(f"{title}  `{_badge(key, options)}`", expanded=expanded):
        if len(options) <= CHIP_MAX:
            st.pills(title, options, selection_mode="multi", key=key,
                     label_visibility="collapsed")
        else:
            st.multiselect(title, options, key=key, label_visibility="collapsed",
                           placeholder="Type to search…")
    return list(st.session_state.get(key) or [])

with st.sidebar:
    st.markdown("### Sidebar Test")
    st.write(f"Data loaded: {len(df)} rows, {len(df.columns)} cols")

    cards = [
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

    st.markdown(f"**Cards to render: {len(cards)}**")
    for i, (title, key, opts, kw) in enumerate(cards):
        st.write(f"  Card {i}: {title} ({len(opts)} options)")

    st.markdown("---")
    st.markdown("**Rendering filter cards...**")

    for title, key, opts, kw in cards:
        try:
            result = _filter_card(title, key, opts, **kw)
            st.write(f"✅ {title}: {len(result)} selected")
        except Exception as e:
            st.error(f"❌ {title}: {e}")
            st.code(traceback.format_exc())

st.write("## Main area — check sidebar for filter diagnostics")
