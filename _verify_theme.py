"""Temporary check: build every figure in both palettes and assert they differ."""
import os
import re

import data_engine as DE
import charts as C
import theme as T

APP_DIR = os.path.dirname(os.path.abspath(__file__))
path = DE.discover_default_workbook(APP_DIR)
raw = DE.read_bytes_resilient(path)
from io import BytesIO
df, notes = DE.parse_workbook(BytesIO(raw))
print(f"loaded {len(df):,} rows from {os.path.basename(path)}")

pf = DE.period_frame(df)
q = DE.compute_quality(df)
sellers = DE.entity_performance(df, "Seller Name", "Deals")


def build_all():
    figs = {
        "revenue_vs_transactions": C.revenue_vs_transactions(pf),
        "monthly_by_fy": C.monthly_by_fy(pf, "GMV", "t", "\u20b9"),
        "take_rate_trend": C.take_rate_trend(pf),
        "avg_bid_trend": C.avg_bid_trend(pf),
        "state_donut": C.state_donut(df),
        "state_performance": C.state_performance(df),
        "segment_split": C.segment_split(df),
        "make_treemap": C.make_treemap(df),
        "top_models": C.top_models(df),
        "price_band_chart": C.price_band_chart(DE.price_bands(df)),
        "age_vs_value": C.age_vs_value(df),
        "pareto": C.pareto(sellers, "Seller Name", "Deals", "t"),
        "cohort_heatmap": C.cohort_heatmap(df, "State", "t"),
        "quality_gauge": C.quality_gauge(q["overall"], "jade"),
        "dimension_radar": C.dimension_radar(q["dimensions"]),
        "null_profile": C.null_profile(q["column_health"]),
        "missingness_map": C.missingness_map(df),
        "outlier_box": C.outlier_box(df, ["Final Bid Value", "Total Income", "Odometer"]),
        "empty": C.empty(),
    }
    return {k: v.to_json() for k, v in figs.items()}


out = {}
sheets = {}
for mode in T.MODES:
    T.apply(mode)
    assert T.MODE == mode
    out[mode] = build_all()
    sheets[mode] = T.stylesheet()
    print(f"{mode:<5} ok — {len(out[mode])} figures, "
          f"stylesheet {len(sheets[mode]):,} chars, "
          f"text={T.TEXT} bg={T.BG} jade={T.JADE} grid={T.GRID}")

# 1. every figure must actually change between modes
same = [k for k in out["dark"] if out["dark"][k] == out["light"][k]]
assert not same, f"figures identical across modes: {same}"

# 2. no dark-mode leftovers in the light stylesheet / figures
leaks = re.findall(r"rgba\(255,255,255", sheets["light"])
assert not leaks, f"{len(leaks)} white-alpha values leaked into the light sheet"
for name, js in out["light"].items():
    for bad in ("#F2F5F8", "#08090B", "#00E5A0", "rgba(255,255,255"):
        assert bad not in js, f"{name}: dark token {bad} leaked into light figure"

# 3. and the reverse
for name, js in out["dark"].items():
    for bad in ("#101A16", "#F2F6F3", "#00A97C"):
        assert bad not in js, f"{name}: light token {bad} leaked into dark figure"

# 4. every CSS var referenced is defined
for mode, sheet in sheets.items():
    defined = set(re.findall(r"--([a-z0-9-]+)\s*:", sheet))
    used = set(re.findall(r"var\(--([a-z0-9-]+)\)", sheet))
    missing = used - defined - {"accent", "glow", "chip", "chipb"}  # set inline per card
    assert not missing, f"{mode}: undefined CSS vars {sorted(missing)}"
    assert "<style>" in sheet and sheet.count("<style>") == sheet.count("</style>")

# 5. native theme options are complete and distinct
dark_native, light_native = T.native_theme("dark"), T.native_theme("light")
assert dark_native.keys() == light_native.keys()
assert dark_native["base"] == "dark" and light_native["base"] == "light"
assert all(dark_native[k] != light_native[k] for k in dark_native)
print("native theme keys:", ", ".join(sorted(dark_native)))

# 6. card helpers render in both modes
for mode in T.MODES:
    T.apply(mode)
    for html in (T.kpi_card("L", "1", "x", "amber", 4.2, "vs", "sub"),
                 T.section("a", "b"), T.insight_card("t", "x", "rose"),
                 T.score_card("l", "9%", "n", "violet", pct=50),
                 T.check_row(False, "r", "m")):
        assert html.startswith("<div") and html.endswith("</div>")

print("\nALL CHECKS PASSED")
