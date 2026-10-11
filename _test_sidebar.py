"""Minimal test: does the sidebar show up at all with the dashboard stylesheet?"""
import streamlit as st
import theme as T

st.set_page_config(
    page_title="Sidebar Test",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.session_state.setdefault("theme_mode", T.DEFAULT_MODE)
T.apply(st.session_state.theme_mode)
st.html(T.stylesheet())
st.html(T.animations())

with st.sidebar:
    st.write("### ✅ SIDEBAR IS VISIBLE")
    st.write("If you can read this, the sidebar is rendering.")
    st.write("---")
    st.write("Filter placeholder 1")
    st.write("Filter placeholder 2")

st.write("## Main content area")
st.write("Check the sidebar on the left. If you don't see it, look for an expand arrow.")
