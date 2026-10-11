"""
Design system for the Conversion Analytics Dashboard — dual mode.

Two hand-tuned palettes share one visual language:

  dark  · "Obsidian & Jade"    — near-black graphite surfaces, luminous jade
  light · "Porcelain & Jade"   — warm porcelain surfaces, deep jade ink

Both deliberately avoid blue.

Everything the rest of the app draws with (Plotly colours, CSS custom
properties, Streamlit's own native theme) is derived from a single palette
dict, so a mode switch can never leave half the UI behind.

Usage
-----
    import theme as T
    T.apply("light")          # rebinds every module-level colour token
    st.html(T.stylesheet())   # inject the matching stylesheet

``apply()`` mutates module globals on purpose: ``charts.py`` reads ``T.TEXT``,
``T.GRID`` and friends at call time, so one call at the top of a Streamlit run
re-themes every figure built during that run.
"""
from __future__ import annotations

MODES = ("dark", "light")
DEFAULT_MODE = "dark"

# ═════════════════════════════════════════════════════════════════════════════
# PALETTES
# ═════════════════════════════════════════════════════════════════════════════
_DARK: dict = dict(
    # ── surfaces ────────────────────────────────────────────────────────
    bg="#08090B", surface="#0F1114", surface_2="#15181D", surface_3="#1C2027",
    border="rgba(255,255,255,.07)", border_strong="rgba(255,255,255,.14)",

    # ── hues: `*_text` variants are the readable-on-this-background twins ─
    jade="#00E5A0",   jade_deep="#00B884", jade_text="#00E5A0",
    amber="#FFB84D",  amber_text="#FFB84D",
    rose="#FF6B8A",   rose_text="#FF6B8A",
    violet="#B79CFF", violet_text="#B79CFF",
    teal="#4DE8D4",   teal_text="#4DE8D4",
    lime="#A3E635",   coral="#FF9E7A",

    # ── type ────────────────────────────────────────────────────────────
    text="#F2F5F8", muted="#8A94A6", faint="#5B6472",
    body="#D6DCE5", strong="#FFFFFF",

    # ── chart chrome ────────────────────────────────────────────────────
    grid="rgba(255,255,255,.055)",
    axis_line="rgba(255,255,255,.10)",
    track="rgba(255,255,255,.07)",
    hover_bg="#1C2027", hover_border="rgba(255,255,255,.16)",
    polar_bg="rgba(255,255,255,.022)",
    box_fill="rgba(255,255,255,.035)",
    present_tint="rgba(0,229,160,.16)",
    gauge_bg="rgba(255,255,255,.04)",
    gauge_tick="rgba(255,255,255,.14)",
    step_bad="rgba(255,107,138,.13)",
    step_mid="rgba(255,184,77,.13)",
    step_good="rgba(0,229,160,.13)",
    marker_edge="#08090B",
    treemap_text="#E9FFF6",

    chart_colors=["#00E5A0", "#FFB84D", "#B79CFF", "#FF6B8A", "#4DE8D4",
                  "#A3E635", "#FF9E7A", "#FFD666", "#7DD3C0", "#E0A3FF",
                  "#FFC9A3", "#9AE6B4"],
    scale_jade=[[0.0, "#0B3D30"], [0.5, "#00B884"], [1.0, "#00E5A0"]],
    scale_amber=[[0.0, "#4A2E0A"], [0.5, "#D18A1F"], [1.0, "#FFB84D"]],
    scale_violet=[[0.0, "#2E2547"], [0.5, "#8B6BD9"], [1.0, "#B79CFF"]],
    scale_health=[[0.0, "#00E5A0"], [0.5, "#FFB84D"], [1.0, "#FF6B8A"]],
    # Narrow lightness band so one label colour stays legible on every tile.
    scale_treemap=[[0.0, "#093026"], [0.5, "#0E5442"], [1.0, "#137F61"]],

    # ── CSS-only tokens ─────────────────────────────────────────────────
    app_bg=("radial-gradient(1100px 620px at 8% -8%,rgba(0,229,160,.11),transparent 60%),"
            "radial-gradient(900px 560px at 104% 4%,rgba(183,156,255,.09),transparent 62%),"
            "radial-gradient(1000px 700px at 60% 112%,rgba(255,184,77,.06),transparent 65%),"
            "var(--bg)"),
    hero_bg="linear-gradient(135deg,#101317 0%,#0B0D10 55%,#0E1512 100%)",
    hero_glow=("radial-gradient(560px 260px at 6% 0%,rgba(0,229,160,.20),transparent 65%),"
               "radial-gradient(520px 260px at 92% 12%,rgba(183,156,255,.16),transparent 65%),"
               "radial-gradient(420px 220px at 55% 108%,rgba(255,184,77,.12),transparent 65%)"),
    hero_rule="linear-gradient(90deg,transparent,rgba(0,229,160,.75),rgba(183,156,255,.45),transparent)",
    hero_title="linear-gradient(120deg,#FFFFFF 0%,#D8FFF0 42%,#00E5A0 78%,#B79CFF 100%)",
    kpi_sheen=("linear-gradient(160deg,rgba(255,255,255,.045) 0%,"
               "rgba(255,255,255,.012) 42%,transparent 100%)"),
    panel_sheen="linear-gradient(160deg,rgba(255,255,255,.035),transparent 60%)",
    plot_sheen="linear-gradient(160deg,rgba(255,255,255,.028),transparent 55%)",
    shadow="0 18px 50px -12px rgba(0,0,0,.75)",
    shadow_hover="0 22px 48px -18px rgba(0,0,0,.9)",
    sidebar_bg="linear-gradient(190deg,#0C0E11 0%,#101317 55%,#0A0C0F 100%)",
    input_bg="rgba(255,255,255,.03)",
    sel_bg="rgba(0,229,160,.28)", sel_fg="#FFFFFF",
    dashed="rgba(255,255,255,.06)",
    tag_bg="linear-gradient(135deg,rgba(0,229,160,.20),rgba(0,184,132,.14))",
    tag_border="rgba(0,229,160,.32)", tag_text="#CFFFEE", tag_svg="#8CF5D2",
    head_bg="#1C2027", head_text="#CFFFEE",
    tab_active_bg="linear-gradient(135deg,rgba(0,229,160,.16),rgba(183,156,255,.12))",
    tab_active_text="#FFFFFF",
    tab_active_ring="0 0 22px -6px rgba(0,229,160,.4)",
    tab_hover_bg="rgba(255,255,255,.045)",
    pill_neutral_bg="rgba(255,255,255,.04)",
    primary_bg="linear-gradient(135deg,#00E5A0,#00B884)",
    primary_text="#05261C",
    primary_shadow="0 10px 26px -10px rgba(0,229,160,.75)",
    primary_shadow_hover="0 14px 34px -10px rgba(0,229,160,.95)",
    mark_bg="linear-gradient(135deg,rgba(0,229,160,.95),rgba(0,184,132,.8))",
    mark_fg="#05261C",
    mark_shadow="0 6px 20px -6px rgba(0,229,160,.7)",
    jade_soft="rgba(0,229,160,.10)", jade_line="rgba(0,229,160,.30)",
    amber_soft="rgba(255,184,77,.10)", amber_line="rgba(255,184,77,.30)",
    rose_soft="rgba(255,107,138,.10)", violet_soft="rgba(183,156,255,.10)",
    flat_soft="rgba(255,255,255,.05)",
    scroll_thumb="linear-gradient(180deg,rgba(0,229,160,.35),rgba(183,156,255,.28))",
    scroll_thumb_hover="linear-gradient(180deg,rgba(0,229,160,.6),rgba(183,156,255,.45))",
    drop_bg="linear-gradient(150deg,rgba(0,229,160,.05),rgba(183,156,255,.035)),#15181D",
    drop_bg_hover="linear-gradient(150deg,rgba(0,229,160,.09),rgba(183,156,255,.05)),#15181D",
    drop_border="rgba(0,229,160,.32)", drop_border_hover="rgba(0,229,160,.6)",
    drop_btn_bg="rgba(0,229,160,.12)", drop_btn_border="rgba(0,229,160,.35)",
    drop_btn_text="#CFFFEE",
    toggle_bg="linear-gradient(135deg,rgba(0,229,160,.12),rgba(183,156,255,.10))",
    toggle_bg_hover="linear-gradient(135deg,rgba(0,229,160,.22),rgba(183,156,255,.16))",
    dot_ring="rgba(0,229,160,.16)",
    kpi_hover_border="rgba(255,255,255,.14)",
    plot_hover_border="rgba(255,255,255,.11)",

    # ── Streamlit's own theme (drives canvas widgets: dataframes, sliders) ─
    native=dict(
        base="dark",
        primaryColor="#00E5A0",
        backgroundColor="#08090B",
        secondaryBackgroundColor="#15181D",
        textColor="#F2F5F8",
        linkColor="#4DE8D4",
        borderColor="#23272E",
        dataframeBorderColor="#23272E",
        dataframeHeaderBackgroundColor="#1C2027",
        codeBackgroundColor="#15181D",
    ),
)

_LIGHT: dict = dict(
    # ── surfaces ────────────────────────────────────────────────────────
    bg="#F2F6F3", surface="#FFFFFF", surface_2="#FFFFFF", surface_3="#EAF1EC",
    border="rgba(12,34,27,.11)", border_strong="rgba(12,34,27,.22)",

    # ── hues ────────────────────────────────────────────────────────────
    jade="#00A97C",   jade_deep="#00805E", jade_text="#06724F",
    amber="#E08A00",  amber_text="#A05F00",
    rose="#E23D63",   rose_text="#BE1E44",
    violet="#7C55E0", violet_text="#5732BE",
    teal="#009E96",   teal_text="#00736C",
    lime="#6E9B12",   coral="#DD6135",

    # ── type ────────────────────────────────────────────────────────────
    text="#101A16", muted="#566068", faint="#6B7680",
    body="#2A343A", strong="#0B1418",

    # ── chart chrome ────────────────────────────────────────────────────
    grid="rgba(12,34,27,.10)",
    axis_line="rgba(12,34,27,.18)",
    track="rgba(12,34,27,.09)",
    hover_bg="#FFFFFF", hover_border="rgba(12,34,27,.20)",
    polar_bg="rgba(0,169,124,.035)",
    box_fill="rgba(12,34,27,.035)",
    present_tint="rgba(0,169,124,.20)",
    gauge_bg="rgba(12,34,27,.05)",
    gauge_tick="rgba(12,34,27,.22)",
    step_bad="rgba(226,61,99,.15)",
    step_mid="rgba(224,138,0,.16)",
    step_good="rgba(0,169,124,.16)",
    marker_edge="#FFFFFF",
    treemap_text="#04301F",

    chart_colors=["#00A97C", "#E08A00", "#7C55E0", "#E23D63", "#009E96",
                  "#6E9B12", "#DD6135", "#B98A00", "#2E9E85", "#9A5BD1",
                  "#C96A3C", "#4A9358"],
    scale_jade=[[0.0, "#E2F5EE"], [0.5, "#3EBE97"], [1.0, "#007154"]],
    scale_amber=[[0.0, "#FCF0DB"], [0.5, "#EFAA3C"], [1.0, "#A85F00"]],
    scale_violet=[[0.0, "#EEE8FD"], [0.5, "#9576EA"], [1.0, "#4F2BB0"]],
    scale_health=[[0.0, "#00A97C"], [0.5, "#E08A00"], [1.0, "#E23D63"]],
    scale_treemap=[[0.0, "#D8F2E8"], [0.5, "#A5E1CD"], [1.0, "#6ECCAE"]],

    # ── CSS-only tokens ─────────────────────────────────────────────────
    app_bg=("radial-gradient(1100px 620px at 8% -8%,rgba(0,169,124,.14),transparent 60%),"
            "radial-gradient(900px 560px at 104% 4%,rgba(124,85,224,.10),transparent 62%),"
            "radial-gradient(1000px 700px at 60% 112%,rgba(224,138,0,.09),transparent 65%),"
            "var(--bg)"),
    hero_bg="linear-gradient(135deg,#FFFFFF 0%,#F8FCFA 55%,#EFFBF5 100%)",
    hero_glow=("radial-gradient(560px 260px at 6% 0%,rgba(0,169,124,.20),transparent 65%),"
               "radial-gradient(520px 260px at 92% 12%,rgba(124,85,224,.14),transparent 65%),"
               "radial-gradient(420px 220px at 55% 108%,rgba(224,138,0,.14),transparent 65%)"),
    hero_rule="linear-gradient(90deg,transparent,rgba(0,169,124,.85),rgba(124,85,224,.5),transparent)",
    hero_title="linear-gradient(120deg,#0B221B 0%,#06724F 44%,#00A97C 72%,#5732BE 100%)",
    kpi_sheen=("linear-gradient(160deg,rgba(0,169,124,.055) 0%,"
               "rgba(124,85,224,.022) 45%,transparent 100%)"),
    panel_sheen="linear-gradient(160deg,rgba(0,169,124,.04),transparent 62%)",
    plot_sheen="linear-gradient(160deg,rgba(0,169,124,.035),transparent 58%)",
    shadow="0 14px 40px -16px rgba(15,45,35,.20)",
    shadow_hover="0 20px 44px -18px rgba(15,45,35,.28)",
    sidebar_bg="linear-gradient(190deg,#FFFFFF 0%,#F7FBF8 55%,#F0F7F2 100%)",
    input_bg="#FFFFFF",
    sel_bg="rgba(0,169,124,.24)", sel_fg="#062A1E",
    dashed="rgba(12,34,27,.10)",
    tag_bg="linear-gradient(135deg,rgba(0,169,124,.16),rgba(0,128,94,.10))",
    tag_border="rgba(0,169,124,.38)", tag_text="#05563E", tag_svg="#06724F",
    head_bg="#E7F3EE", head_text="#06724F",
    tab_active_bg="linear-gradient(135deg,rgba(0,169,124,.18),rgba(124,85,224,.11))",
    tab_active_text="#0B241C",
    tab_active_ring="0 4px 14px -6px rgba(0,169,124,.5)",
    tab_hover_bg="rgba(12,34,27,.05)",
    pill_neutral_bg="rgba(12,34,27,.05)",
    primary_bg="linear-gradient(135deg,#00845C,#00654A)",
    primary_text="#FFFFFF",
    primary_shadow="0 10px 24px -10px rgba(0,132,92,.55)",
    primary_shadow_hover="0 14px 30px -10px rgba(0,132,92,.7)",
    mark_bg="linear-gradient(135deg,#00A97C,#00785A)",
    mark_fg="#FFFFFF",
    mark_shadow="0 6px 18px -6px rgba(0,169,124,.55)",
    jade_soft="rgba(0,169,124,.11)", jade_line="rgba(0,169,124,.34)",
    amber_soft="rgba(224,138,0,.12)", amber_line="rgba(224,138,0,.34)",
    rose_soft="rgba(226,61,99,.11)", violet_soft="rgba(124,85,224,.11)",
    flat_soft="rgba(12,34,27,.06)",
    scroll_thumb="linear-gradient(180deg,rgba(0,169,124,.45),rgba(124,85,224,.32))",
    scroll_thumb_hover="linear-gradient(180deg,rgba(0,169,124,.7),rgba(124,85,224,.5))",
    drop_bg="linear-gradient(150deg,rgba(0,169,124,.06),rgba(124,85,224,.035)),#FFFFFF",
    drop_bg_hover="linear-gradient(150deg,rgba(0,169,124,.11),rgba(124,85,224,.05)),#FFFFFF",
    drop_border="rgba(0,169,124,.38)", drop_border_hover="rgba(0,169,124,.65)",
    drop_btn_bg="rgba(0,169,124,.12)", drop_btn_border="rgba(0,169,124,.4)",
    drop_btn_text="#05563E",
    toggle_bg="linear-gradient(135deg,rgba(0,169,124,.13),rgba(124,85,224,.10))",
    toggle_bg_hover="linear-gradient(135deg,rgba(0,169,124,.22),rgba(124,85,224,.16))",
    dot_ring="rgba(0,169,124,.18)",
    kpi_hover_border="rgba(12,34,27,.22)",
    plot_hover_border="rgba(12,34,27,.18)",

    native=dict(
        base="light",
        primaryColor="#00A97C",
        backgroundColor="#F2F6F3",
        secondaryBackgroundColor="#FFFFFF",
        textColor="#101A16",
        linkColor="#06724F",
        borderColor="#D2DFD8",
        dataframeBorderColor="#D2DFD8",
        dataframeHeaderBackgroundColor="#E7F3EE",
        codeBackgroundColor="#EDF4F0",
    ),
)

PALETTES: dict[str, dict] = {"dark": _DARK, "light": _LIGHT}

FONT_UI = "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"
FONT_MONO = "'JetBrains Mono', 'SF Mono', Consolas, monospace"


# ═════════════════════════════════════════════════════════════════════════════
# ACTIVE TOKENS  (rebound by apply())
# ═════════════════════════════════════════════════════════════════════════════
MODE = DEFAULT_MODE
P: dict = _DARK


def _build_accents(p: dict) -> dict:
    """Per-mode accent presets used by the card helpers and the gauge."""

    def spec(graphic: str, deep: str, ink: str, rgb: str) -> dict:
        return dict(
            accent=f"linear-gradient(90deg,{graphic},{deep})",
            solid=graphic,          # graphic use: bars, gauges, rules
            text=ink,               # text use: readable on this mode's surface
            glow=f"rgba({rgb},.16)",
            chip=f"rgba({rgb},.11)",
            chipb=f"rgba({rgb},.30)",
        )

    if p is _LIGHT or p.get("native", {}).get("base") == "light":
        return {
            "jade":   spec("#00A97C", "#00785A", "#06724F", "0,169,124"),
            "amber":  spec("#E08A00", "#B06B00", "#A05F00", "224,138,0"),
            "violet": spec("#7C55E0", "#5E36C4", "#5732BE", "124,85,224"),
            "rose":   spec("#E23D63", "#C02249", "#BE1E44", "226,61,99"),
            "teal":   spec("#009E96", "#007A73", "#00736C", "0,158,150"),
        }
    return {
        "jade":   spec("#00E5A0", "#00B884", "#00E5A0", "0,229,160"),
        "amber":  spec("#FFB84D", "#E09528", "#FFB84D", "255,184,77"),
        "violet": spec("#B79CFF", "#8B6BD9", "#B79CFF", "183,156,255"),
        "rose":   spec("#FF6B8A", "#E04E70", "#FF6B8A", "255,107,138"),
        "teal":   spec("#4DE8D4", "#2FB8A8", "#4DE8D4", "77,232,212"),
    }


def apply(mode: str = DEFAULT_MODE) -> str:
    """
    Rebind every module-level colour token to ``mode`` and return the mode used.

    Call once per Streamlit script run, before any figure is built.
    """
    global MODE, P
    global BG, SURFACE, SURFACE_2, SURFACE_3
    global JADE, JADE_DEEP, JADE_TEXT, AMBER, AMBER_TEXT, ROSE, ROSE_TEXT
    global VIOLET, VIOLET_TEXT, TEAL, TEAL_TEXT, LIME, CORAL
    global TEXT, TEXT_MUTED, TEXT_FAINT, TEXT_BODY, TEXT_STRONG
    global POSITIVE, NEGATIVE, WARNING
    global GRID, AXIS_LINE, TRACK, HOVER_BG, HOVER_BORDER, POLAR_BG, BOX_FILL
    global PRESENT_TINT, GAUGE_BG, GAUGE_TICK, STEP_BAD, STEP_MID, STEP_GOOD
    global MARKER_EDGE, TREEMAP_TEXT
    global CHART_COLORS, SCALE_JADE, SCALE_AMBER, SCALE_VIOLET, SCALE_HEALTH
    global SCALE_TREEMAP, ACCENTS

    mode = mode if mode in PALETTES else DEFAULT_MODE
    p = PALETTES[mode]
    MODE, P = mode, p

    BG, SURFACE = p["bg"], p["surface"]
    SURFACE_2, SURFACE_3 = p["surface_2"], p["surface_3"]

    JADE, JADE_DEEP, JADE_TEXT = p["jade"], p["jade_deep"], p["jade_text"]
    AMBER, AMBER_TEXT = p["amber"], p["amber_text"]
    ROSE, ROSE_TEXT = p["rose"], p["rose_text"]
    VIOLET, VIOLET_TEXT = p["violet"], p["violet_text"]
    TEAL, TEAL_TEXT = p["teal"], p["teal_text"]
    LIME, CORAL = p["lime"], p["coral"]

    TEXT, TEXT_MUTED, TEXT_FAINT = p["text"], p["muted"], p["faint"]
    TEXT_BODY, TEXT_STRONG = p["body"], p["strong"]

    POSITIVE, NEGATIVE, WARNING = p["jade"], p["rose"], p["amber"]

    GRID, AXIS_LINE, TRACK = p["grid"], p["axis_line"], p["track"]
    HOVER_BG, HOVER_BORDER = p["hover_bg"], p["hover_border"]
    POLAR_BG, BOX_FILL = p["polar_bg"], p["box_fill"]
    PRESENT_TINT = p["present_tint"]
    GAUGE_BG, GAUGE_TICK = p["gauge_bg"], p["gauge_tick"]
    STEP_BAD, STEP_MID, STEP_GOOD = p["step_bad"], p["step_mid"], p["step_good"]
    MARKER_EDGE, TREEMAP_TEXT = p["marker_edge"], p["treemap_text"]

    CHART_COLORS = list(p["chart_colors"])
    SCALE_JADE = [list(s) for s in p["scale_jade"]]
    SCALE_AMBER = [list(s) for s in p["scale_amber"]]
    SCALE_VIOLET = [list(s) for s in p["scale_violet"]]
    SCALE_HEALTH = [list(s) for s in p["scale_health"]]
    SCALE_TREEMAP = [list(s) for s in p["scale_treemap"]]

    ACCENTS = _build_accents(p)
    return mode


def native_theme(mode: str | None = None) -> dict[str, str]:
    """
    Streamlit's own theme options for ``mode``.

    These drive the widgets Streamlit paints itself — most importantly the
    canvas-rendered dataframes and sliders, which CSS cannot reach.
    """
    p = PALETTES.get(mode or MODE, PALETTES[DEFAULT_MODE])
    return dict(p["native"])


def is_dark(mode: str | None = None) -> bool:
    return (mode or MODE) == "dark"


def rgba(color: str, alpha: float) -> str:
    """``rgba()`` string for a hex colour — used for Plotly fills and tints."""
    h = color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


# ═════════════════════════════════════════════════════════════════════════════
# GLOBAL STYLESHEET
#
# Injected through st.html(), which passes the string straight to the DOM.
# st.markdown() would run it through a Markdown parser first, where a blank line
# closes a raw-HTML block and a 4-space indent opens a code block — both of which
# dump the remaining CSS onto the page as visible text. stylesheet() also strips
# blank lines and indentation so the payload stays safe wherever it is used.
#
# Every colour lives in the :root block below, generated from the palette. The
# rest of the sheet only ever reads var(--token), so the two modes share one
# structural definition and can never drift apart.
# ═════════════════════════════════════════════════════════════════════════════
_VAR_MAP: tuple[tuple[str, str], ...] = (
    ("bg", "bg"), ("surface", "surface"), ("surface-2", "surface_2"),
    ("surface-3", "surface_3"), ("border", "border"), ("border-strong", "border_strong"),
    ("jade", "jade"), ("jade-deep", "jade_deep"), ("jade-text", "jade_text"),
    ("amber", "amber"), ("amber-text", "amber_text"),
    ("rose", "rose"), ("rose-text", "rose_text"),
    ("violet", "violet"), ("violet-text", "violet_text"),
    ("teal", "teal"), ("teal-text", "teal_text"),
    ("text", "text"), ("muted", "muted"), ("faint", "faint"),
    ("body", "body"), ("strong", "strong"),
    ("track", "track"), ("dashed", "dashed"),
    ("app-bg", "app_bg"), ("hero-bg", "hero_bg"), ("hero-glow", "hero_glow"),
    ("hero-rule", "hero_rule"), ("hero-title", "hero_title"),
    ("kpi-sheen", "kpi_sheen"), ("panel-sheen", "panel_sheen"),
    ("plot-sheen", "plot_sheen"),
    ("shadow", "shadow"), ("shadow-hover", "shadow_hover"),
    ("sidebar-bg", "sidebar_bg"), ("input-bg", "input_bg"),
    ("sel-bg", "sel_bg"), ("sel-fg", "sel_fg"),
    ("tag-bg", "tag_bg"), ("tag-border", "tag_border"),
    ("tag-text", "tag_text"), ("tag-svg", "tag_svg"),
    ("head-bg", "head_bg"), ("head-text", "head_text"),
    ("tab-active-bg", "tab_active_bg"), ("tab-active-text", "tab_active_text"),
    ("tab-active-ring", "tab_active_ring"), ("tab-hover-bg", "tab_hover_bg"),
    ("pill-neutral-bg", "pill_neutral_bg"),
    ("primary-bg", "primary_bg"), ("primary-text", "primary_text"),
    ("primary-shadow", "primary_shadow"), ("primary-shadow-hover", "primary_shadow_hover"),
    ("mark-bg", "mark_bg"), ("mark-fg", "mark_fg"), ("mark-shadow", "mark_shadow"),
    ("jade-soft", "jade_soft"), ("jade-line", "jade_line"),
    ("amber-soft", "amber_soft"), ("amber-line", "amber_line"),
    ("rose-soft", "rose_soft"), ("violet-soft", "violet_soft"),
    ("flat-soft", "flat_soft"),
    ("scroll-thumb", "scroll_thumb"), ("scroll-thumb-hover", "scroll_thumb_hover"),
    ("drop-bg", "drop_bg"), ("drop-bg-hover", "drop_bg_hover"),
    ("drop-border", "drop_border"), ("drop-border-hover", "drop_border_hover"),
    ("drop-btn-bg", "drop_btn_bg"), ("drop-btn-border", "drop_btn_border"),
    ("drop-btn-text", "drop_btn_text"),
    ("toggle-bg", "toggle_bg"), ("toggle-bg-hover", "toggle_bg_hover"),
    ("dot-ring", "dot_ring"),
    ("kpi-hover-border", "kpi_hover_border"), ("plot-hover-border", "plot_hover_border"),
)

_FONT_LINKS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:'
    'wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700'
    '&display=swap" rel="stylesheet">'
)

_CSS_BODY = """
<style>
/* ── Canvas ─────────────────────────────────────────────────────────── */
.stApp{
  background:var(--app-bg);
  background-attachment:fixed;
  font-family:var(--font);
  color:var(--text);
}
.stApp, .stApp p, .stApp li, .stApp span, .stApp label, .stApp div{
  -webkit-font-smoothing:antialiased;
}
.block-container{padding-top:1.6rem; padding-bottom:3.5rem; max-width:1560px;}

/* Keep the sidebar toggle usable, drop the opaque chrome */
header[data-testid="stHeader"]{background:transparent; height:0; overflow:visible;}
[data-testid="stDecoration"], [data-testid="stStatusWidget"]{display:none;}
#MainMenu, footer{visibility:hidden;}

::selection{background:var(--sel-bg); color:var(--sel-fg);}
/* ::-webkit-scrollbar{width:10px; height:10px;}
::-webkit-scrollbar-track{background:transparent;}
::-webkit-scrollbar-thumb{
  background:var(--scroll-thumb);
  border-radius:20px; border:2px solid transparent; background-clip:content-box;
}
::-webkit-scrollbar-thumb:hover{background:var(--scroll-thumb-hover); background-clip:content-box;} */

h1,h2,h3,h4,h5{font-family:var(--font); color:var(--text); letter-spacing:-.02em;}
.stApp p, .stApp li{color:var(--body);}
.stApp a{color:var(--jade-text);}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p{color:var(--faint) !important;}
[data-testid="stMarkdownContainer"] code{
  background:var(--jade-soft); color:var(--jade-text);
  padding:.1rem .38rem; border-radius:5px; font-family:var(--mono); font-size:.78rem;
}

/* ── Hero ───────────────────────────────────────────────────────────── */
.hero{
  position:relative; overflow:hidden;
  border:1px solid var(--border); border-radius:var(--r-lg);
  background:var(--hero-bg);
  padding:1.9rem 2.2rem; margin-bottom:1.5rem; box-shadow:var(--shadow);
}
.hero::before{
  content:""; position:absolute; inset:0;
  background:var(--hero-glow);
  animation:drift 16s ease-in-out infinite alternate; pointer-events:none;
}
.hero::after{
  content:""; position:absolute; top:0; left:0; right:0; height:1px;
  background:var(--hero-rule);
}
@keyframes drift{
  0%{transform:translate3d(0,0,0) scale(1); opacity:.9;}
  100%{transform:translate3d(-18px,10px,0) scale(1.06); opacity:1;}
}
.hero-inner{position:relative; z-index:1; display:flex; justify-content:space-between; align-items:flex-start; gap:1.5rem; flex-wrap:wrap;}
.eyebrow{
  display:inline-flex; align-items:center; gap:.5rem;
  font-size:.66rem; font-weight:800; letter-spacing:.22em; text-transform:uppercase;
  color:var(--jade-text); margin-bottom:.7rem;
}
.eyebrow::before{content:""; width:22px; height:2px; border-radius:2px; background:linear-gradient(90deg,var(--jade),transparent);}
.hero h1{
  font-size:2.15rem; font-weight:800; line-height:1.1; margin:0;
  background:var(--hero-title);
  -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text;
}
.hero p{color:var(--muted); font-size:.92rem; margin:.55rem 0 0; max-width:62ch; line-height:1.55;}
.hero-meta{display:flex; flex-direction:column; gap:.5rem; align-items:flex-end;}
.pill{
  display:inline-flex; align-items:center; gap:.45rem; white-space:nowrap;
  padding:.42rem .85rem; border-radius:999px; font-size:.72rem; font-weight:700;
  background:var(--jade-soft); border:1px solid var(--jade-line); color:var(--jade-text);
}
.pill.neutral{background:var(--pill-neutral-bg); border-color:var(--border-strong); color:var(--muted);}
.pill.amber{background:var(--amber-soft); border-color:var(--amber-line); color:var(--amber-text);}
.dot{width:6px; height:6px; border-radius:50%; background:currentColor; box-shadow:0 0 0 3px var(--dot-ring);}
.dot.live{animation:pulse 2.2s ease-in-out infinite;}
@keyframes pulse{0%,100%{opacity:1;} 50%{opacity:.4;}}

/* ── Section heading ────────────────────────────────────────────────── */
.sect{display:flex; align-items:baseline; gap:.9rem; margin:2.1rem 0 1rem;}
.sect-bar{width:3px; height:26px; border-radius:3px; background:linear-gradient(180deg,var(--jade),var(--violet)); flex:none;}
.sect-txt h3{font-size:1.06rem; font-weight:700; margin:0; letter-spacing:-.01em; color:var(--text);}
.sect-txt span{display:block; font-size:.7rem; color:var(--faint); letter-spacing:.12em; text-transform:uppercase; margin-top:.2rem;}
.sect-rule{flex:1; height:1px; background:linear-gradient(90deg,var(--border-strong),transparent); align-self:center;}

/* ── KPI cards ──────────────────────────────────────────────────────── */
.kpi{
  position:relative; overflow:hidden; height:100%;
  background:var(--kpi-sheen),var(--surface-2);
  border:1px solid var(--border); border-radius:var(--r-md);
  padding:1.15rem 1.25rem 1.2rem;
  box-shadow:var(--shadow);
  transition:transform .28s cubic-bezier(.2,.8,.2,1), border-color .28s, box-shadow .28s;
}
.kpi::before{content:""; position:absolute; top:0; left:0; right:0; height:2px; background:var(--accent); opacity:.9;}
.kpi::after{
  content:""; position:absolute; top:-40%; right:-30%; width:170px; height:170px; border-radius:50%;
  background:radial-gradient(circle,var(--glow),transparent 68%); opacity:.55; pointer-events:none;
  transition:opacity .3s;
}
.kpi:hover{transform:translateY(-4px); border-color:var(--kpi-hover-border); box-shadow:var(--shadow-hover);}
.kpi:hover::after{opacity:.9;}
.kpi-top{display:flex; align-items:center; justify-content:space-between; gap:.6rem; position:relative; z-index:1;}
.kpi-ico{
  width:30px; height:30px; border-radius:9px; display:grid; place-items:center; font-size:.9rem;
  background:var(--chip); border:1px solid var(--chipb); flex:none; color:var(--text);
}
.kpi-label{font-size:.66rem; font-weight:800; letter-spacing:.14em; text-transform:uppercase; color:var(--muted); line-height:1.35;}
.kpi-val{
  font-family:var(--mono); font-size:1.72rem; font-weight:700; letter-spacing:-.03em;
  margin:.7rem 0 0; color:var(--text); position:relative; z-index:1; line-height:1.1;
}
.kpi-sub{font-size:.72rem; color:var(--faint); margin-top:.3rem; position:relative; z-index:1;}
.kpi-delta{
  display:inline-flex; align-items:center; gap:.28rem; margin-top:.55rem; position:relative; z-index:1;
  font-size:.71rem; font-weight:700; font-family:var(--mono);
  padding:.2rem .5rem; border-radius:6px;
}
.kpi-delta.up{color:var(--jade-text); background:var(--jade-soft);}
.kpi-delta.down{color:var(--rose-text); background:var(--rose-soft);}
.kpi-delta.flat{color:var(--muted); background:var(--flat-soft);}

/* ── Generic panel ──────────────────────────────────────────────────── */
.panel{
  background:var(--panel-sheen),var(--surface-2);
  border:1px solid var(--border); border-radius:var(--r-md); padding:1.25rem 1.35rem;
  height:100%; box-shadow:var(--shadow);
}
.panel h4{font-size:.9rem; font-weight:700; margin:0 0 .8rem; display:flex; align-items:center; gap:.5rem; color:var(--text);}
.panel ul{margin:.2rem 0 0; padding-left:1.1rem; color:var(--muted); font-size:.83rem; line-height:1.85;}
.panel li{color:var(--muted) !important;}
.panel code{background:var(--jade-soft); color:var(--jade-text); padding:.1rem .38rem; border-radius:5px; font-family:var(--mono); font-size:.78rem;}

/* ── Insight cards ──────────────────────────────────────────────────── */
.insight{
  position:relative; height:100%;
  background:var(--panel-sheen),var(--surface-2);
  border:1px solid var(--border); border-left:2px solid var(--accent);
  border-radius:var(--r-sm); padding:.95rem 1.1rem; box-shadow:var(--shadow);
}
.insight-tag{
  font-size:.62rem; font-weight:800; letter-spacing:.16em; text-transform:uppercase;
  color:var(--accent); display:block; margin-bottom:.4rem;
}
.insight-txt{font-size:.83rem; color:var(--body) !important; line-height:1.6; margin:0;}
.insight-txt b{color:var(--strong); font-weight:700;}

/* ── Score / quality ────────────────────────────────────────────────── */
.score{
  text-align:center; padding:1.3rem 1rem;
  background:var(--panel-sheen),var(--surface-2);
  border:1px solid var(--border); border-radius:var(--r-md); height:100%;
  box-shadow:var(--shadow);
}
.score-num{font-family:var(--mono); font-size:2.1rem; font-weight:700; letter-spacing:-.03em; line-height:1.1; margin:.35rem 0 .1rem;}
.score-lbl{font-size:.64rem; font-weight:800; letter-spacing:.16em; text-transform:uppercase; color:var(--muted);}
.score-note{font-size:.7rem; color:var(--faint); margin-top:.2rem;}
.bar{height:5px; border-radius:99px; background:var(--track); overflow:hidden; margin-top:.75rem;}
.bar>i{display:block; height:100%; border-radius:99px; background:var(--accent);}

.check{display:flex; align-items:flex-start; gap:.6rem; padding:.5rem 0; border-bottom:1px dashed var(--dashed); font-size:.83rem; color:var(--body);}
.check:last-child{border-bottom:none;}
.check-ico{width:17px; height:17px; border-radius:5px; display:grid; place-items:center; font-size:.62rem; font-weight:800; flex:none; margin-top:.1rem;}
.check-ico.ok{background:var(--jade-soft); color:var(--jade-text); border:1px solid var(--jade-line);}
.check-ico.no{background:var(--rose-soft); color:var(--rose-text); border:1px solid var(--rose-text);}
.check-meta{display:block; font-size:.72rem; color:var(--faint); margin-top:.15rem;}

/* ── Tabs ───────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"]{
  gap:.35rem; background:var(--surface); border:1px solid var(--border);
  padding:.4rem; border-radius:14px; margin-bottom:1.4rem;
  box-shadow:var(--shadow);
}
.stTabs [data-baseweb="tab-list"]{scrollbar-width:none;}
.stTabs [data-baseweb="tab-list"]::-webkit-scrollbar{display:none;}
.stTabs [data-baseweb="tab"]{
  height:auto; padding:.62rem 1.25rem; border-radius:10px; background:transparent;
  color:var(--muted); font-weight:600; font-size:.85rem; letter-spacing:.01em;
  transition:all .22s ease; border:1px solid transparent;
}
.stTabs [data-baseweb="tab"]:hover{color:var(--text); background:var(--tab-hover-bg);}
.stTabs [aria-selected="true"]{
  background:var(--tab-active-bg);
  color:var(--tab-active-text) !important; border-color:var(--jade-line);
  box-shadow:var(--tab-active-ring);
}
.stTabs [aria-selected="true"] p{color:var(--tab-active-text) !important;}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"]{display:none;}
.stTabs [data-baseweb="tab-panel"]{padding-top:0;}

/* ── Sidebar ────────────────────────────────────────────────────────── */
section[data-testid="stSidebar"]{
  background:var(--sidebar-bg);
  border-right:1px solid var(--border);
  /* Pin the rail to the viewport. The content div below scrolls at height:100%,
     which resolves against this box — and an unconstrained section grows to fit
     its content, making the scroll container exactly as tall as the thing it is
     meant to scroll. That silently strands anything past the fold: the filter
     stack ends up below the window with no way to reach it. */
  height:100vh !important; max-height:100vh !important;
  height:100dvh !important; max-height:100dvh !important;
}
section[data-testid="stSidebar"] > div{
  padding-top:1.4rem;
  overflow-y:auto !important;
  height:100% !important; max-height:100% !important;
}

/* Getting the filters back.

   The whole filter stack lives in the sidebar, so collapsing it — by clicking
   the chevron, or automatically when the viewport gets narrow or the page is
   zoomed in — reads as "the filters disappeared". Streamlit's way back is a
   bare 28px chevron in the top-left corner, dim against a dark page and easy
   to miss. Both controls are made explicit here: the collapse chevron stays
   visible instead of appearing on hover, and the reopen control is dressed as
   a labelled pill. */
[data-testid="stSidebarCollapseButton"]{opacity:1 !important;}
[data-testid="stSidebarCollapseButton"] button{visibility:visible !important;}

[data-testid="stExpandSidebarButton"]{
  width:auto !important; min-width:0 !important; height:32px !important;
  padding:0 .72rem 0 .5rem !important; gap:.3rem;
  border-radius:999px !important;
  background:var(--jade-soft) !important;
  border:1px solid var(--jade-line) !important;
  box-shadow:var(--shadow);
  transition:border-color .2s ease, background .2s ease, transform .2s ease;
}
[data-testid="stExpandSidebarButton"]::after{
  content:"Filters"; font-family:var(--font); font-size:.68rem; font-weight:800;
  letter-spacing:.12em; text-transform:uppercase; color:var(--jade-text);
  white-space:nowrap;
}
[data-testid="stExpandSidebarButton"] span,
[data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"]{
  color:var(--jade-text) !important; font-size:1.05rem !important;
}
[data-testid="stExpandSidebarButton"]:hover{
  background:var(--flat-soft) !important; border-color:var(--jade) !important;
  transform:translateX(2px);
}
.sb-brand{
  display:flex; align-items:center; gap:.7rem; padding:0 .25rem 1rem;
  border-bottom:1px solid var(--border); margin-bottom:1.1rem;
}
.sb-mark{
  width:36px; height:36px; border-radius:11px; flex:none; display:grid; place-items:center;
  font-size:1.05rem; color:var(--mark-fg);
  background:var(--mark-bg);
  box-shadow:var(--mark-shadow);
}
.sb-brand strong{display:block; font-size:.9rem; font-weight:700; line-height:1.2; color:var(--text);}
.sb-brand span{display:block; font-size:.68rem; color:var(--faint); letter-spacing:.1em; text-transform:uppercase; margin-top:.15rem;}
.sb-head{
  font-size:.64rem; font-weight:800; letter-spacing:.2em; text-transform:uppercase;
  color:var(--jade-text); margin:1.4rem 0 .55rem; display:flex; align-items:center; gap:.5rem;
}
.sb-head::after{content:""; flex:1; height:1px; background:linear-gradient(90deg,var(--jade-line),transparent);}
.sb-stat{
  display:flex; justify-content:space-between; align-items:center; gap:.6rem;
  padding:.5rem .7rem; border-radius:9px; background:var(--flat-soft);
  border:1px solid var(--border); margin-bottom:.4rem; font-size:.76rem;
}
.sb-stat span{color:var(--muted);}
.sb-stat b{font-family:var(--mono); color:var(--text); font-weight:600; text-align:right;}

/* ── Sidebar account ────────────────────────────────────────────────── */
.sb-user{
  display:flex; align-items:center; gap:.65rem; min-width:0;
  padding:.6rem .7rem; border-radius:12px;
  background:var(--jade-soft); border:1px solid var(--jade-line); margin-bottom:.5rem;
}
.sb-av{
  width:34px; height:34px; border-radius:10px; flex:none; display:grid; place-items:center;
  font-family:var(--mono); font-size:.76rem; font-weight:700; letter-spacing:.02em;
  background:var(--mark-bg); color:var(--mark-fg); box-shadow:var(--mark-shadow);
}
.sb-user .who{min-width:0;}
.sb-user .who b{
  display:block; font-size:.79rem; font-weight:700; color:var(--text);
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
}
.sb-user .who span{
  display:block; font-size:.62rem; font-weight:800; letter-spacing:.14em;
  text-transform:uppercase; color:var(--jade-text); margin-top:.12rem;
}
.st-key-logout_btn button{
  width:100%; justify-content:center; border-radius:10px !important;
  padding:.42rem .6rem !important;
  background:transparent !important; border:1px solid var(--border-strong) !important;
  transition:all .2s ease;
}
.st-key-logout_btn button p{
  font-size:.65rem !important; font-weight:800 !important;
  letter-spacing:.14em; text-transform:uppercase; color:var(--muted) !important;
}
.st-key-logout_btn button:hover{
  border-color:var(--rose-text) !important; background:var(--rose-soft) !important;
  transform:none;
}
.st-key-logout_btn button:hover p{color:var(--rose-text) !important;}

section[data-testid="stSidebar"] label{
  font-size:.73rem !important; font-weight:700 !important; color:var(--muted) !important;
  letter-spacing:.04em; text-transform:uppercase;
}

/* ── Sidebar filters ────────────────────────────────────────────────── */
/* Section header: label · rule · active-count badge */
.flt-head{display:flex; align-items:center; gap:.55rem; margin:1.4rem 0 .6rem;}
.flt-head .t{
  font-size:.64rem; font-weight:800; letter-spacing:.2em; text-transform:uppercase;
  color:var(--jade-text); white-space:nowrap;
}
.flt-head .r{flex:1; height:1px; background:linear-gradient(90deg,var(--jade-line),transparent);}
.flt-head .n{
  font-family:var(--mono); font-size:.62rem; font-weight:700; color:var(--muted);
  background:var(--flat-soft); border:1px solid var(--border);
  padding:.14rem .48rem; border-radius:999px; white-space:nowrap;
}
.flt-head .n.on{color:var(--jade-text); background:var(--jade-soft); border-color:var(--jade-line);}

/* Each filter group is an expander dressed as a card */
section[data-testid="stSidebar"] [data-testid="stExpander"]{
  background:var(--flat-soft) !important;
  border:1px solid var(--border) !important;
  border-radius:12px !important; margin-bottom:.45rem;
  transition:border-color .2s ease, background .2s ease;
}
section[data-testid="stSidebar"] [data-testid="stExpander"]:hover{border-color:var(--jade-line) !important;}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary{
  padding:.52rem .7rem !important; min-height:0 !important;
}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary p{
  font-size:.76rem !important; font-weight:700 !important; color:var(--text) !important;
  text-transform:none !important; letter-spacing:0 !important;
}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary code{
  background:var(--jade-soft) !important; color:var(--jade-text) !important;
  border:1px solid var(--jade-line); border-radius:999px;
  padding:.04rem .44rem !important; font-size:.62rem !important; font-weight:700 !important;
  letter-spacing:.06em; text-transform:uppercase;
}
section[data-testid="stSidebar"] [data-testid="stExpanderDetails"]{padding:.1rem .7rem .65rem !important;}
section[data-testid="stSidebar"] [data-testid="stExpander"] label{
  font-size:.62rem !important; letter-spacing:.14em !important; color:var(--faint) !important;
}

/* Chip toggles (st.pills) */
section[data-testid="stSidebar"] [data-testid="stButtonGroup"] button{
  border-radius:999px !important; min-height:0 !important;
  padding:.24rem .6rem !important;
  border:1px solid var(--border) !important; background:var(--input-bg) !important;
  transition:all .18s ease;
}
section[data-testid="stSidebar"] [data-testid="stButtonGroup"] button p{
  font-size:.7rem !important; font-weight:700 !important; color:var(--muted) !important;
}
section[data-testid="stSidebar"] [data-testid="stButtonGroup"] button:hover{border-color:var(--jade-line) !important;}
section[data-testid="stSidebar"] [data-testid="stButtonGroup"] button:hover p{color:var(--text) !important;}
section[data-testid="stSidebar"] [data-testid="stButtonGroup"] button[aria-pressed="true"],
section[data-testid="stSidebar"] [data-testid="stButtonGroup"] button[kind="pillsActive"]{
  background:var(--jade-soft) !important; border-color:var(--jade-line) !important;
}
section[data-testid="stSidebar"] [data-testid="stButtonGroup"] button[aria-pressed="true"] p,
section[data-testid="stSidebar"] [data-testid="stButtonGroup"] button[kind="pillsActive"] p{
  color:var(--jade-text) !important;
}

/* Quick actions inside a card: All / Top n / Clear */
section[data-testid="stSidebar"] [class*="st-key-qa_"] button{
  padding:.2rem .25rem !important; min-height:0 !important; border-radius:7px !important;
  background:transparent !important; border:1px solid var(--border) !important;
}
section[data-testid="stSidebar"] [class*="st-key-qa_"] button p{
  font-size:.62rem !important; font-weight:800 !important;
  letter-spacing:.1em; text-transform:uppercase; color:var(--faint) !important;
}
section[data-testid="stSidebar"] [class*="st-key-qa_"] button:hover{
  border-color:var(--jade-line) !important; background:var(--jade-soft) !important;
}
section[data-testid="stSidebar"] [class*="st-key-qa_"] button:hover p{color:var(--jade-text) !important;}

/* Reset-all control */
.st-key-flt_reset button{
  width:100%; justify-content:center; border-radius:9px !important;
  padding:.38rem .6rem !important; background:transparent !important;
  border:1px dashed var(--border-strong) !important;
}
.st-key-flt_reset button p{
  font-size:.65rem !important; font-weight:800 !important;
  letter-spacing:.14em; text-transform:uppercase; color:var(--muted) !important;
}
.st-key-flt_reset button:hover{
  border-style:solid !important; border-color:var(--jade-line) !important;
  background:var(--jade-soft) !important; transform:none;
}
.st-key-flt_reset button:hover p{color:var(--jade-text) !important;}

/* Long option lists stay contained instead of pushing the sidebar around */
section[data-testid="stSidebar"] div[data-baseweb="select"] > div > div:first-child{
  max-height:118px; overflow-y:auto;
}
section[data-testid="stSidebar"] span[data-baseweb="tag"]{
  font-size:.66rem !important; height:auto !important;
}

/* Numeric range readout, drawn above the slider */
.flt-range{display:flex; align-items:center; gap:.5rem; margin:.15rem 0 .1rem;}
.flt-range b{font-family:var(--mono); font-size:.75rem; font-weight:600; color:var(--text);}
.flt-range i{flex:1; height:1px; background:var(--dashed);}
/* endpoint ticks are redundant next to the readout above the track */
.st-key-f_bid [data-testid="stSliderTickBar"]{display:none;}
.st-key-f_bid [data-testid="stSliderThumbValue"]{
  font-family:var(--mono) !important; font-size:.66rem !important; color:var(--muted) !important;
}

/* ── Theme toggle ───────────────────────────────────────────────────── */
.theme-row{display:flex; align-items:center; gap:.5rem; margin:.1rem 0 .35rem;}
.theme-row .lbl{font-size:.62rem; font-weight:800; letter-spacing:.2em; text-transform:uppercase; color:var(--faint);}
.st-key-theme_switch button{
  width:100%; justify-content:center; gap:.5rem;
  background:var(--toggle-bg) !important;
  border:1px solid var(--jade-line) !important;
  color:var(--text) !important;
  font-weight:800 !important; font-size:.72rem !important;
  letter-spacing:.1em; text-transform:uppercase;
  padding:.6rem 1rem !important; border-radius:11px !important;
  transition:all .22s ease;
}
.st-key-theme_switch button:hover{
  background:var(--toggle-bg-hover) !important;
  border-color:var(--jade) !important;
  transform:translateY(-1px);
}
.st-key-theme_switch button p{color:var(--text) !important; font-weight:800 !important;}

/* Inputs */
div[data-baseweb="select"] > div, div[data-baseweb="input"] > div{
  background:var(--input-bg) !important; border:1px solid var(--border) !important;
  border-radius:10px !important; font-size:.83rem;
}
div[data-baseweb="select"] > div:hover{border-color:var(--jade-line) !important;}
div[data-baseweb="select"] [aria-selected="true"]{background:var(--jade-soft) !important;}
span[data-baseweb="tag"]{
  background:var(--tag-bg) !important;
  border:1px solid var(--tag-border) !important; color:var(--tag-text) !important;
  border-radius:7px !important; font-size:.72rem !important; font-weight:700 !important;
}
span[data-baseweb="tag"] span{color:var(--tag-text) !important;}
span[data-baseweb="tag"] svg{fill:var(--tag-svg) !important;}
div[data-baseweb="popover"] ul{background:var(--surface) !important; border:1px solid var(--border-strong) !important;}
div[data-baseweb="popover"] li{color:var(--text) !important;}

/* Buttons */
.stButton > button, .stDownloadButton > button{
  border-radius:10px; font-weight:700; font-size:.82rem; letter-spacing:.01em;
  border:1px solid var(--border-strong); background:var(--flat-soft); color:var(--text);
  padding:.55rem 1.1rem; transition:all .22s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover{
  border-color:var(--jade-line); background:var(--jade-soft); color:var(--jade-text); transform:translateY(-1px);
}
.stButton > button[kind="primary"]{
  background:var(--primary-bg); color:var(--primary-text) !important; border:none;
  box-shadow:var(--primary-shadow);
}
.stButton > button[kind="primary"] p{color:var(--primary-text) !important;}
.stButton > button[kind="primary"]:hover{box-shadow:var(--primary-shadow-hover);}

/* File uploader */
[data-testid="stFileUploaderDropzone"]{
  background:var(--drop-bg);
  border:1.5px dashed var(--drop-border); border-radius:var(--r-md); padding:1.6rem;
  transition:all .25s ease;
}
[data-testid="stFileUploaderDropzone"]:hover{border-color:var(--drop-border-hover); background:var(--drop-bg-hover);}
[data-testid="stFileUploaderDropzone"] button{background:var(--drop-btn-bg) !important; border:1px solid var(--drop-btn-border) !important; color:var(--drop-btn-text) !important;}
[data-testid="stFileUploaderDropzone"] span, [data-testid="stFileUploaderDropzone"] small{color:var(--muted) !important;}

/* Expander */
details, [data-testid="stExpander"]{
  background:var(--surface-2); border:1px solid var(--border) !important; border-radius:var(--r-md) !important;
  overflow:hidden;
}
[data-testid="stExpander"] summary{font-weight:700; font-size:.85rem; color:var(--text);}
[data-testid="stExpander"] summary:hover{color:var(--jade-text);}
[data-testid="stExpander"] summary svg{fill:var(--muted);}

/* Dataframe */
[data-testid="stDataFrame"], [data-testid="stDataFrameResizable"]{
  border:1px solid var(--border); border-radius:var(--r-md); overflow:hidden;
}
[data-testid="stDataFrame"] [role="columnheader"]{
  background:var(--head-bg) !important; color:var(--head-text) !important;
  font-size:.72rem !important; font-weight:700 !important; letter-spacing:.06em; text-transform:uppercase;
}

/* Metric */
div[data-testid="stMetric"]{
  background:var(--surface-2); border:1px solid var(--border); border-radius:var(--r-md); padding:1rem 1.15rem;
}
div[data-testid="stMetricValue"]{font-family:var(--mono) !important; font-size:1.4rem !important; color:var(--text) !important;}
div[data-testid="stMetricLabel"]{font-size:.7rem !important; letter-spacing:.12em; text-transform:uppercase; color:var(--muted) !important;}

/* Sliders */
[data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"]{border-color:var(--jade) !important;}
[data-testid="stSliderTickBar"], [data-testid="stSliderTickBarMin"], [data-testid="stSliderTickBarMax"]{color:var(--faint) !important;}

/* Alerts */
div[data-testid="stAlert"]{border-radius:var(--r-sm); border:1px solid var(--border-strong); font-size:.85rem;}
div[data-testid="stAlert"] p{color:var(--text) !important;}

/* Spinner */
[data-testid="stSpinner"] p{color:var(--muted) !important;}

/* Plotly container polish */
[data-testid="stPlotlyChart"]{
  background:var(--plot-sheen),var(--surface-2);
  border:1px solid var(--border); border-radius:var(--r-md); padding:.55rem .3rem .2rem;
  box-shadow:var(--shadow);
  transition:border-color .25s;
}
[data-testid="stPlotlyChart"]:hover{border-color:var(--plot-hover-border);}
.modebar-btn path{fill:var(--muted) !important;}

hr{border-color:var(--border) !important;}
.small-note{font-size:.75rem; color:var(--faint) !important; margin-top:.5rem;}
</style>
"""


def _root_block(p: dict) -> str:
    decls = "".join(f"--{css}:{p[key]};" for css, key in _VAR_MAP)
    return (
        "<style>:root{"
        + decls
        + "--r-lg:20px;--r-md:14px;--r-sm:10px;"
        + f"--font:{FONT_UI};--mono:{FONT_MONO};"
        + "}</style>"
    )


def stylesheet(mode: str | None = None) -> str:
    """
    Return the global stylesheet for ``mode`` as a single contiguous HTML block.

    Blank lines and leading indentation are removed: a blank line would end the
    raw-HTML block and an indent of four or more spaces would start a code block
    if this string ever reaches a Markdown renderer.
    """
    p = PALETTES.get(mode or MODE, PALETTES[DEFAULT_MODE])
    body = " ".join(line.strip() for line in _CSS_BODY.splitlines() if line.strip())
    return _FONT_LINKS + _root_block(p) + body


# ═════════════════════════════════════════════════════════════════════════════
# SIGN-IN SCREEN
#
# Kept in its own sheet because it is the only view that reshapes the page
# shell — it hides the sidebar, centres the container vertically and paints a
# full-viewport backdrop. Loading it only on the sign-in route means none of
# those overrides can leak into the dashboard.
#
# Colours come from the same :root tokens as everything else, so the screen
# follows the active mode without a second palette.
# ═════════════════════════════════════════════════════════════════════════════
_LOGIN_CSS = """
<style>
/* ── Page shell ─────────────────────────────────────────────────────── */
section[data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"]{display:none !important;}
[data-testid="stToolbar"]{display:none !important;}
.stApp .block-container{
  max-width:1140px; padding-top:2.2rem; padding-bottom:2.2rem; min-height:100vh;
}
/* The container's own child stretches to fill it, so the free space has to be
   distributed one level in — on the vertical block that holds the columns. */
.stApp .block-container > [data-testid="stVerticalBlock"]{
  justify-content:center; min-height:100%;
}

/* Ambient backdrop: three slow-drifting orbs behind a masked measurement grid */
.lg-aurora{position:fixed; inset:0; z-index:0; overflow:hidden; pointer-events:none;}
.lg-aurora i{position:absolute; display:block; border-radius:50%; filter:blur(80px);}
.lg-aurora i:nth-child(1){
  width:540px; height:540px; left:-9%; top:-16%; background:var(--jade); opacity:.20;
  animation:lgDriftA 21s ease-in-out infinite alternate;
}
.lg-aurora i:nth-child(2){
  width:460px; height:460px; right:-8%; top:2%; background:var(--violet); opacity:.17;
  animation:lgDriftB 25s ease-in-out infinite alternate;
}
.lg-aurora i:nth-child(3){
  width:460px; height:460px; right:16%; bottom:-26%; background:var(--amber); opacity:.09;
  filter:blur(100px);
  animation:lgDriftC 28s ease-in-out infinite alternate;
}
.lg-grid{
  position:fixed; inset:0; z-index:0; pointer-events:none;
  background-image:linear-gradient(var(--dashed) 1px,transparent 1px),
                   linear-gradient(90deg,var(--dashed) 1px,transparent 1px);
  background-size:56px 56px;
  -webkit-mask-image:radial-gradient(ellipse 76% 60% at 50% 42%,#000 10%,transparent 76%);
  mask-image:radial-gradient(ellipse 76% 60% at 50% 42%,#000 10%,transparent 76%);
}
@keyframes lgDriftA{0%{transform:translate3d(0,0,0) scale(1);}100%{transform:translate3d(70px,50px,0) scale(1.12);}}
@keyframes lgDriftB{0%{transform:translate3d(0,0,0) scale(1.05);}100%{transform:translate3d(-60px,70px,0) scale(1);}}
@keyframes lgDriftC{0%{transform:translate3d(0,0,0) scale(1);}100%{transform:translate3d(-50px,-45px,0) scale(1.14);}}
@keyframes lgRise{
  0%{opacity:0; transform:translateY(16px);}
  100%{opacity:1; transform:translateY(0);}
}

/* ── Brand column ───────────────────────────────────────────────────── */
.lg-brand{position:relative; z-index:1; animation:lgRise .75s cubic-bezier(.2,.8,.2,1) both;}
.lg-logo{display:flex; align-items:center; gap:.8rem; margin-bottom:1.9rem;}
.lg-logo .m{
  width:46px; height:46px; border-radius:14px; flex:none; display:grid; place-items:center;
  font-size:1.3rem; background:var(--mark-bg); color:var(--mark-fg); box-shadow:var(--mark-shadow);
}
.lg-logo b{display:block; font-size:1rem; font-weight:800; color:var(--text); letter-spacing:-.01em;}
.lg-logo span{
  display:block; font-size:.66rem; font-weight:700; letter-spacing:.2em;
  text-transform:uppercase; color:var(--faint); margin-top:.18rem;
}
.lg-brand h1{
  font-size:2.6rem; font-weight:800; line-height:1.06; margin:0; letter-spacing:-.03em;
  background:var(--hero-title);
  -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text;
}
.lg-brand .lead{
  color:var(--muted) !important; font-size:.93rem; line-height:1.6;
  margin:.85rem 0 0; max-width:46ch;
}
.lg-feats{display:grid; gap:.5rem; margin-top:1.6rem;}
.lg-feat{
  display:flex; gap:.72rem; align-items:flex-start;
  padding:.62rem .8rem; border-radius:12px;
  background:var(--flat-soft); border:1px solid var(--border);
  transition:border-color .25s ease, transform .25s ease;
}
.lg-feat:hover{border-color:var(--jade-line); transform:translateX(3px);}
.lg-feat .i{
  width:27px; height:27px; border-radius:9px; flex:none; display:grid; place-items:center;
  font-size:.8rem; background:var(--jade-soft); border:1px solid var(--jade-line);
  color:var(--jade-text);
}
.lg-feat strong{display:block; font-size:.8rem; font-weight:700; color:var(--text);}
.lg-feat em{display:block; font-style:normal; font-size:.73rem; color:var(--faint); margin-top:.14rem;}
.lg-trust{
  display:flex; gap:1.6rem; margin-top:1.7rem; padding-top:1.1rem;
  border-top:1px solid var(--border); flex-wrap:wrap;
}
.lg-trust div b{
  display:block; font-family:var(--mono); font-size:1.05rem; font-weight:700;
  color:var(--text); letter-spacing:-.02em;
}
.lg-trust div span{
  display:block; font-size:.63rem; font-weight:700; letter-spacing:.14em;
  text-transform:uppercase; color:var(--faint); margin-top:.2rem;
}

/* ── Credential card ────────────────────────────────────────────────── */
.st-key-login_card{
  position:relative; z-index:1; overflow:hidden;
  background:var(--kpi-sheen),var(--surface-2);
  border:1px solid var(--border-strong); border-radius:22px;
  padding:1.9rem 1.85rem 1.55rem !important;
  box-shadow:var(--shadow-hover);
  animation:lgRise .75s .09s cubic-bezier(.2,.8,.2,1) both;
}
.st-key-login_card::before{
  content:""; position:absolute; top:0; left:0; right:0; height:2px; background:var(--hero-rule);
}
.st-key-login_card::after{
  content:""; position:absolute; top:-32%; right:-26%; width:240px; height:240px; border-radius:50%;
  background:radial-gradient(circle,var(--jade-soft),transparent 70%); pointer-events:none;
}
.st-key-login_card > div{position:relative; z-index:1;}
.lg-head{margin-bottom:1.15rem;}
.lg-head .k{
  display:inline-flex; align-items:center; gap:.45rem;
  font-size:.63rem; font-weight:800; letter-spacing:.2em; text-transform:uppercase;
  color:var(--jade-text); margin-bottom:.55rem;
}
.lg-head .k::before{content:""; width:18px; height:2px; border-radius:2px; background:linear-gradient(90deg,var(--jade),transparent);}
.lg-head h2{font-size:1.32rem; font-weight:800; margin:0; letter-spacing:-.02em; color:var(--text);}
.lg-head p{font-size:.81rem; color:var(--faint) !important; margin:.35rem 0 0; line-height:1.5;}

/* The form is a layout device only — Streamlit's own frame is removed */
.st-key-login_card [data-testid="stForm"]{
  border:none !important; background:transparent !important; padding:0 !important;
}
.st-key-login_card [data-testid="stForm"] [data-testid="stVerticalBlock"]{gap:.75rem;}
.st-key-login_card label, .st-key-login_card label p{
  font-size:.64rem !important; font-weight:800 !important; letter-spacing:.16em !important;
  text-transform:uppercase; color:var(--muted) !important;
}
.st-key-login_card div[data-baseweb="input"],
.st-key-login_card div[data-baseweb="base-input"]{
  background:var(--input-bg) !important;
  border:1px solid var(--border-strong) !important;
  border-radius:12px !important;
  transition:border-color .2s ease, box-shadow .2s ease;
}
.st-key-login_card div[data-baseweb="input"]:focus-within{
  border-color:var(--jade) !important; box-shadow:0 0 0 3px var(--jade-soft) !important;
}
.st-key-login_card input{
  height:2.85rem !important; font-size:.9rem !important; color:var(--text) !important;
  background:transparent !important;
}
.st-key-login_card input::placeholder{color:var(--faint) !important; opacity:1;}
.st-key-login_card [data-testid="stTextInput"] button svg{fill:var(--muted) !important;}
.st-key-login_card [data-testid="stFormSubmitButton"]{margin-top:.35rem;}
.st-key-login_card [data-testid="stFormSubmitButton"] button{
  width:100%; justify-content:center; border:none !important;
  background:var(--primary-bg) !important;
  padding:.8rem 1rem !important; border-radius:12px !important;
  box-shadow:var(--primary-shadow) !important;
  transition:transform .2s ease, box-shadow .2s ease, filter .2s ease;
}
.st-key-login_card [data-testid="stFormSubmitButton"] button p{
  color:var(--primary-text) !important; font-size:.77rem !important; font-weight:800 !important;
  letter-spacing:.16em; text-transform:uppercase;
}
.st-key-login_card [data-testid="stFormSubmitButton"] button:hover{
  transform:translateY(-1px); box-shadow:var(--primary-shadow-hover) !important;
}
.st-key-login_card [data-testid="stFormSubmitButton"] button:disabled{
  filter:grayscale(.65); opacity:.55; transform:none;
}

/* Feedback + footer */
.lg-alert{
  display:flex; gap:.6rem; align-items:flex-start; margin:0 0 .95rem;
  padding:.62rem .8rem; border-radius:11px; font-size:.79rem; line-height:1.45;
  background:var(--rose-soft); border:1px solid var(--rose-text); color:var(--rose-text) !important;
  animation:lgRise .3s ease both;
}
.lg-alert.warn{background:var(--amber-soft); border-color:var(--amber-line); color:var(--amber-text) !important;}
.lg-alert b{font-weight:800;}
.lg-alert .g{flex:none; font-weight:800;}
.lg-hint{
  display:flex; align-items:center; gap:.45rem; margin:.9rem 0 0;
  font-size:.71rem; color:var(--faint) !important;
}
.lg-hint::before{content:""; flex:1; height:1px; background:linear-gradient(90deg,transparent,var(--border-strong));}
.lg-hint::after{content:""; flex:1; height:1px; background:linear-gradient(90deg,var(--border-strong),transparent);}
/* A div, not a p: Streamlit's markdown paragraph rule outranks a bare class */
.lg-note{
  margin:.5rem 0 0; text-align:center; line-height:1.5;
  font-size:.73rem !important; color:var(--faint) !important;
}
.lg-foot{
  position:relative; z-index:1; text-align:center; margin-top:1.7rem;
  font-size:.7rem; color:var(--faint) !important;
}
.lg-foot .sep{opacity:.45; margin:0 .5rem;}

/* ── Narrow viewports ───────────────────────────────────────────────── */
@media (max-width:900px){
  .stApp .block-container{padding-top:1.6rem; min-height:0; display:block;}
  .lg-brand h1{font-size:2.05rem;}
  .lg-feats, .lg-trust{display:none;}
  .lg-grid{display:none;}
}
</style>
"""


def login_stylesheet(mode: str | None = None) -> str:
    """
    Return the sign-in screen stylesheet as one contiguous HTML block.

    Layered on top of :func:`stylesheet`, which supplies the palette tokens this
    sheet reads. Same blank-line and indentation stripping applies.
    """
    _ = mode  # colours come from :root, kept for signature symmetry
    return " ".join(line.strip() for line in _LOGIN_CSS.splitlines() if line.strip())


# ═════════════════════════════════════════════════════════════════════════════
# CARD HELPERS
# ═════════════════════════════════════════════════════════════════════════════
def kpi_card(label, value, icon="", accent="jade", delta=None, delta_label="", sub=""):
    """Return HTML for a single KPI card."""
    a = ACCENTS.get(accent, ACCENTS["jade"])
    delta_html = ""
    if delta is not None:
        if delta > 0.05:
            cls, arrow = "up", "▲"
        elif delta < -0.05:
            cls, arrow = "down", "▼"
        else:
            cls, arrow = "flat", "●"
        delta_html = (f'<div class="kpi-delta {cls}">{arrow} {abs(delta):.1f}%'
                      f'<span style="font-weight:500;opacity:.75">&nbsp;{delta_label}</span></div>')
    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    return (
        f'<div class="kpi" style="--accent:{a["accent"]};--glow:{a["glow"]};'
        f'--chip:{a["chip"]};--chipb:{a["chipb"]}">'
        f'<div class="kpi-top"><div class="kpi-label">{label}</div>'
        f'<div class="kpi-ico">{icon}</div></div>'
        f'<div class="kpi-val">{value}</div>{sub_html}{delta_html}</div>'
    )


def section(title, kicker=""):
    """Return HTML for a section heading."""
    return (f'<div class="sect"><div class="sect-bar"></div><div class="sect-txt">'
            f'<h3>{title}</h3><span>{kicker}</span></div><div class="sect-rule"></div></div>')


def insight_card(tag, text, accent="jade"):
    a = ACCENTS.get(accent, ACCENTS["jade"])
    return (f'<div class="insight" style="--accent:{a["text"]}">'
            f'<span class="insight-tag">{tag}</span>'
            f'<p class="insight-txt">{text}</p></div>')


def score_card(label, value, note="", accent="jade", pct=None):
    a = ACCENTS.get(accent, ACCENTS["jade"])
    bar = f'<div class="bar"><i style="width:{max(0,min(100,pct)):.0f}%"></i></div>' if pct is not None else ""
    return (f'<div class="score" style="--accent:{a["accent"]}">'
            f'<div class="score-lbl">{label}</div>'
            f'<div class="score-num" style="color:{a["text"]}">{value}</div>'
            f'<div class="score-note">{note}</div>{bar}</div>')


def check_row(passed, text, meta=""):
    ico = ("ok", "✓") if passed else ("no", "✕")
    meta_html = f'<span class="check-meta">{meta}</span>' if meta else ""
    return (f'<div class="check"><div class="check-ico {ico[0]}">{ico[1]}</div>'
            f'<div>{text}{meta_html}</div></div>')


# Bind the default palette so importing the module is enough to use it.
apply(DEFAULT_MODE)


# ═════════════════════════════════════════════════════════════════════════════
# MOTION LAYER
#
# Purely additive: this sheet only sets `animation`, adds a handful of decorative
# pseudo-elements and sharpens existing hover transitions. It never redefines a
# colour, a size or a layout rule, so it can be injected after stylesheet()
# without any risk of the two disagreeing.
#
# Three principles keep it from becoming noise:
#   · entrances run once, on first paint, and settle — `both` fill, no loops
#   · looping animations are slow, low amplitude and decorative only
#   · a `prefers-reduced-motion` block switches the whole layer off
#
# Staggering is done with :nth-child() delays on Streamlit's column wrappers,
# which is why a row of KPI cards deals itself out left to right.
# ═════════════════════════════════════════════════════════════════════════════
_ANIM_CSS = """
<style>
/* ── Keyframes ───────────────────────────────────────────────────────── */
@keyframes fxRise{
  0%{opacity:0; transform:translateY(18px);}
  100%{opacity:1; transform:translateY(0);}
}
@keyframes fxPop{
  0%{opacity:0; transform:translateY(14px) scale(.94);}
  100%{opacity:1; transform:translateY(0) scale(1);}
}
@keyframes fxFade{0%{opacity:0;}100%{opacity:1;}}
@keyframes fxSweep{
  0%{transform:translateX(-120%) skewX(-18deg);}
  100%{transform:translateX(320%) skewX(-18deg);}
}
@keyframes fxShimmer{
  0%{background-position:0% 50%;}
  100%{background-position:200% 50%;}
}
@keyframes fxGrowBar{0%{transform:scaleY(0);}100%{transform:scaleY(1);}}
@keyframes fxGrowRule{0%{transform:scaleX(0);}100%{transform:scaleX(1);}}
@keyframes fxAuroraA{
  0%{transform:translate3d(0,0,0) scale(1);}
  100%{transform:translate3d(90px,60px,0) scale(1.18);}
}
@keyframes fxAuroraB{
  0%{transform:translate3d(0,0,0) scale(1.1);}
  100%{transform:translate3d(-80px,80px,0) scale(1);}
}
@keyframes fxBreathe{
  0%,100%{opacity:.55;}
  50%{opacity:1;}
}

/* ── Drifting aurora behind everything ───────────────────────────────── */
/* pointer-events:none and a negative z-index keep it strictly decorative. */
.stApp::before, .stApp::after{
  content:""; position:fixed; border-radius:50%; pointer-events:none; z-index:0;
  filter:blur(120px);
}
.stApp::before{
  width:46vw; height:46vw; left:-12vw; top:-14vw;
  background:var(--jade); opacity:.10;
  animation:fxAuroraA 24s ease-in-out infinite alternate;
}
.stApp::after{
  width:40vw; height:40vw; right:-10vw; top:8vh;
  background:var(--violet); opacity:.09;
  animation:fxAuroraB 29s ease-in-out infinite alternate;
}
[data-testid="stAppViewContainer"]{position:relative; z-index:1;}
section[data-testid="stSidebar"]{z-index:2;}

/* ── Hero ────────────────────────────────────────────────────────────── */
.hero{animation:fxPop .7s cubic-bezier(.2,.85,.25,1) both;}
.hero h1{
  background-size:200% auto !important;
  animation:fxShimmer 9s ease-in-out infinite alternate;
}
.hero::after{transform-origin:left center; animation:fxGrowRule 1.1s .25s cubic-bezier(.2,.9,.2,1) both;}
.hero p{animation:fxRise .8s .16s cubic-bezier(.2,.85,.25,1) both;}
.eyebrow{animation:fxRise .7s .08s cubic-bezier(.2,.85,.25,1) both;}
.hero-meta .pill{animation:fxPop .6s cubic-bezier(.16,1.4,.4,1) both;}
.hero-meta .pill:nth-child(1){animation-delay:.24s;}
.hero-meta .pill:nth-child(2){animation-delay:.34s;}
.hero-meta .pill:nth-child(3){animation-delay:.44s;}

/* ── Section headings ────────────────────────────────────────────────── */
.sect-bar{transform-origin:center top; animation:fxGrowBar .6s cubic-bezier(.2,.9,.2,1) both;}
.sect-txt h3{animation:fxRise .55s .08s cubic-bezier(.2,.85,.25,1) both;}
.sect-txt span{animation:fxFade .8s .2s ease both;}
.sect-rule{transform-origin:left center; animation:fxGrowRule .9s .12s cubic-bezier(.2,.9,.2,1) both;}

/* ── KPI cards: dealt out left to right, then a sheen on hover ───────── */
.kpi{animation:fxPop .6s cubic-bezier(.2,.85,.25,1) both;}
[data-testid="stHorizontalBlock"] > div:nth-child(1) .kpi{animation-delay:.05s;}
[data-testid="stHorizontalBlock"] > div:nth-child(2) .kpi{animation-delay:.13s;}
[data-testid="stHorizontalBlock"] > div:nth-child(3) .kpi{animation-delay:.21s;}
[data-testid="stHorizontalBlock"] > div:nth-child(4) .kpi{animation-delay:.29s;}
[data-testid="stHorizontalBlock"] > div:nth-child(5) .kpi{animation-delay:.37s;}
.kpi-val{animation:fxRise .6s .18s cubic-bezier(.2,.85,.25,1) both;}
.kpi::before{transform-origin:left center; animation:fxGrowRule .8s .1s cubic-bezier(.2,.9,.2,1) both;}
.kpi:hover{transform:translateY(-6px) scale(1.012);}
/* The sheen lives in a wrapper span so .kpi's own ::before/::after stay free */
.kpi .kpi-top::after{
  content:""; position:absolute; top:-1.1rem; left:-2.2rem;
  width:38%; height:16rem; pointer-events:none; opacity:0;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.13),transparent);
}
.kpi:hover .kpi-top::after{opacity:1; animation:fxSweep .95s cubic-bezier(.3,.7,.3,1);}
.kpi-ico{transition:transform .35s cubic-bezier(.2,.9,.3,1.5);}
.kpi:hover .kpi-ico{transform:rotate(-12deg) scale(1.14);}

/* ── Insight cards ───────────────────────────────────────────────────── */
.insight{
  animation:fxPop .6s cubic-bezier(.2,.85,.25,1) both;
  transition:transform .28s cubic-bezier(.2,.8,.2,1), border-color .28s, box-shadow .28s;
}
[data-testid="stHorizontalBlock"] > div:nth-child(1) .insight{animation-delay:.06s;}
[data-testid="stHorizontalBlock"] > div:nth-child(2) .insight{animation-delay:.16s;}
[data-testid="stHorizontalBlock"] > div:nth-child(3) .insight{animation-delay:.26s;}
.insight:hover{transform:translateY(-4px); border-color:var(--jade-line); box-shadow:var(--shadow-hover);}
.insight-tag{animation:fxFade .7s .2s ease both;}

/* ── Score cards and quality checks ──────────────────────────────────── */
.score{animation:fxPop .6s cubic-bezier(.2,.85,.25,1) both; transition:transform .28s, border-color .28s;}
.score:hover{transform:translateY(-4px);}
.score-num{animation:fxRise .6s .16s cubic-bezier(.2,.85,.25,1) both;}
.bar > i{transform-origin:left center; animation:fxGrowRule 1.1s .28s cubic-bezier(.2,.9,.2,1) both;}
.check{animation:fxRise .45s cubic-bezier(.2,.85,.25,1) both;}
.check-ico{transition:transform .3s cubic-bezier(.2,.9,.3,1.5);}
.check:hover .check-ico{transform:scale(1.18) rotate(-8deg);}

/* ── Charts ──────────────────────────────────────────────────────────── */
[data-testid="stPlotlyChart"]{animation:fxPop .7s .08s cubic-bezier(.2,.85,.25,1) both;}
[data-testid="stPlotlyChart"]:hover{box-shadow:var(--shadow-hover);}

/* ── Tabs ────────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"]{animation:fxRise .55s cubic-bezier(.2,.85,.25,1) both;}
.stTabs [data-baseweb="tab"]{position:relative;}
.stTabs [data-baseweb="tab"]:hover{transform:translateY(-1px);}
.stTabs [aria-selected="true"]{animation:fxPop .45s cubic-bezier(.16,1.4,.4,1) both;}
.stTabs [aria-selected="true"]::after{
  content:""; position:absolute; left:22%; right:22%; bottom:3px; height:2px;
  border-radius:2px; background:linear-gradient(90deg,transparent,var(--jade),transparent);
  animation:fxBreathe 2.6s ease-in-out infinite;
}
.stTabs [data-baseweb="tab-panel"]{animation:fxFade .5s ease both;}

/* ── Sidebar ─────────────────────────────────────────────────────────── */
.sb-brand{animation:fxRise .55s cubic-bezier(.2,.85,.25,1) both;}
.sb-mark{transition:transform .4s cubic-bezier(.2,.9,.3,1.5);}
.sb-brand:hover .sb-mark{transform:rotate(-14deg) scale(1.1);}
.sb-stat{animation:fxRise .5s cubic-bezier(.2,.85,.25,1) both; transition:border-color .2s, transform .2s;}
.sb-stat:nth-of-type(2){animation-delay:.06s;}
.sb-stat:nth-of-type(3){animation-delay:.12s;}
.sb-stat:hover{border-color:var(--jade-line); transform:translateX(2px);}
.sb-user{animation:fxPop .55s cubic-bezier(.16,1.4,.4,1) both;}
.sb-av{transition:transform .4s cubic-bezier(.2,.9,.3,1.5);}
.sb-user:hover .sb-av{transform:rotate(-10deg) scale(1.08);}
section[data-testid="stSidebar"] [data-testid="stExpander"]{transition:border-color .2s ease, background .2s ease, transform .2s ease;}
section[data-testid="stSidebar"] [data-testid="stExpander"]:hover{transform:translateX(2px);}

/* ── Buttons and pills ───────────────────────────────────────────────── */
.stButton button, [data-testid="stDownloadButton"] button{
  transition:transform .18s cubic-bezier(.2,.9,.3,1.4), box-shadow .18s ease,
             border-color .18s ease, background .18s ease;
}
.stButton button:active, [data-testid="stDownloadButton"] button:active{transform:scale(.96);}
[data-testid="stDownloadButton"] button:hover{transform:translateY(-2px);}
[data-testid="stButtonGroup"] button{transition:all .18s cubic-bezier(.2,.9,.3,1.3);}
[data-testid="stButtonGroup"] button:active{transform:scale(.93);}
.pill{transition:transform .22s cubic-bezier(.2,.9,.3,1.4), box-shadow .22s;}
.pill:hover{transform:translateY(-2px) scale(1.03);}

/* ── Metrics, alerts, dataframes ─────────────────────────────────────── */
div[data-testid="stMetric"]{animation:fxPop .55s cubic-bezier(.2,.85,.25,1) both;}
div[data-testid="stAlert"]{animation:fxRise .45s cubic-bezier(.2,.85,.25,1) both;}
[data-testid="stDataFrame"]{animation:fxFade .6s .1s ease both;}
[data-testid="stExpander"]{animation:fxFade .5s ease both;}

/* ── Reduced motion: the whole layer stands down ─────────────────────── */
@media (prefers-reduced-motion:reduce){
  .stApp::before, .stApp::after{animation:none !important;}
  .hero, .hero h1, .hero::after, .hero p, .eyebrow, .hero-meta .pill,
  .sect-bar, .sect-txt h3, .sect-txt span, .sect-rule,
  .kpi, .kpi-val, .kpi::before, .kpi .kpi-top::after,
  .insight, .insight-tag, .score, .score-num, .bar > i, .check,
  [data-testid="stPlotlyChart"], .stTabs [data-baseweb="tab-list"],
  .stTabs [aria-selected="true"], .stTabs [aria-selected="true"]::after,
  .stTabs [data-baseweb="tab-panel"], .sb-brand, .sb-stat, .sb-user,
  div[data-testid="stMetric"], div[data-testid="stAlert"],
  [data-testid="stDataFrame"], [data-testid="stExpander"]{
    animation:none !important;
  }
  .sect-bar, .sect-rule, .hero::after, .kpi::before, .bar > i{transform:none !important;}
  .kpi:hover, .insight:hover, .score:hover, .pill:hover,
  [data-testid="stDownloadButton"] button:hover{transform:none !important;}
}
</style>
"""


def animations() -> str:
    """
    Return the motion layer as one contiguous HTML block.

    Inject *after* :func:`stylesheet` — it deliberately overrides a few of that
    sheet's transitions. Blank lines and indentation are stripped for the same
    reason as everywhere else in this module.
    """
    return " ".join(line.strip() for line in _ANIM_CSS.splitlines() if line.strip())
