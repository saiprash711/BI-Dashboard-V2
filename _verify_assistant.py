"""
Exercise the assistant against the bundled workbook, with no Streamlit runtime.

Checks two things:
  1. every intent routes somewhere and returns non-trivial HTML
  2. the figures it quotes match a hand-computed pandas answer
"""
from __future__ import annotations

import os
import re
import sys

import pandas as pd

import assistant
import data_engine as DE

HERE = os.path.dirname(os.path.abspath(__file__))
path = DE.discover_default_workbook(HERE)
# The workbook lives in a OneDrive folder and can be locked mid-sync, which is
# exactly why the app reads it through this helper rather than open().
raw = DE.read_bytes_resilient(path)
assert raw is not None, f"could not read {path}"
df, notes = DE.parse_workbook(__import__("io").BytesIO(raw))
assert df is not None, f"workbook failed to parse: {notes}"
print(f"workbook : {os.path.basename(path)}  rows={len(df):,}  cols={len(df.columns)}")
print(f"columns  : {[c for c in df.columns]}")

# A filtered slice, mimicking a couple of sidebar selections.
states = sorted(df["State"].dropna().unique().tolist())
fdf = df[df["State"].isin(states[:2])].copy()

ctx = {
    "df": df,
    "fdf": fdf,
    "sel": {"State": states[:2],
            "FY": sorted(df["FY"].dropna().unique().tolist()),
            "Month": [m for m in DE.MONTH_ORDER if m in set(df["Month"].dropna())]},
    "bid_range": (float(df["Final Bid Value"].min()), float(df["Final Bid Value"].max())),
    "source_label": "Bundled workbook",
    "source_path": path,
    "theme_mode": "dark",
    "quality_fn": lambda: DE.compute_quality(df),
}

QUESTIONS = [
    "hi",
    "what can you do?",
    "give me a summary",
    "give me a summary overall",
    "what is take rate?",
    "how is GMV calculated?",
    "show every metric definition",
    "what is the total commission revenue overall",
    "total gmv",
    "how many transactions are there overall",
    "what is the average deal size",
    "take rate",
    "top 5 states by revenue",
    "top 10 sellers by gmv",
    "bottom 5 states by take rate",
    "who are the best buyers",
    "top 3 makes by transactions",
    "revenue by month",
    "transactions by segment",
    "gmv by financial year",
    "revenue by state",
    "how is revenue trending?",
    "which is the best month?",
    "worst month for gmv",
    "year on year comparison",
    "month on month growth",
    "how concentrated is supply?",
    "how concentrated is demand?",
    "top 5 share of gmv",
    "repeat buyers",
    "how often do buyers come back",
    "which price band yields most?",
    "price bands",
    "odometer and vehicle age",
    "how old are the vehicles",
    "how healthy is the data?",
    "any duplicates?",
    "any missing values?",
    "show me the outliers",
    "are the values valid?",
    "is the data consistent?",
    "what columns are in the data?",
    "which states are covered?",
    "what period does the data cover?",
    "how many sellers are there",
    "how many records",
    "what filters are active?",
    "how do I upload data?",
    "how do I export the data?",
    "how do I switch to light mode?",
    "what tabs are there?",
    "captive vs non-captive",
    f"{states[0]} vs {states[1]}",
    states[0],
    f"how did {states[0]} do",
    "what period does the data cover?",
    "what is the time frame of this data",
    "define take rate",
    "what is the formula for gmv",
    "how is average commission calculated",
    "purple monkey dishwasher",
    "",
]

fails: list[str] = []
for q in QUESTIONS:
    try:
        r = assistant.answer(q, ctx)
    except Exception as exc:                                     # noqa: BLE001
        fails.append(f"RAISED  {q!r}: {type(exc).__name__}: {exc}")
        continue
    plain = re.sub(r"<[^>]+>", " ", r.html)
    plain = re.sub(r"\s+", " ", plain).strip()
    if len(plain) < 40:
        fails.append(f"THIN    {q!r}: {plain!r}")
    if "could not finish" in plain:
        fails.append(f"ERRORED {q!r}: {plain[:160]}")
    if "could not pin that question" in plain and q not in ("purple monkey dishwasher",):
        fails.append(f"FELL THROUGH {q!r}")
    print(f"  · {q[:44]:<46} → {len(plain):>5} chars | {plain[:82]}")

print()

# ── numeric spot checks ─────────────────────────────────────────────────────
def plain_of(q: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", assistant.answer(q, ctx).html))


checks: list[tuple[str, str, str]] = []

rev_col = "Total Income (Ex GST)" if "Total Income (Ex GST)" in df else "Total Income"
rev = df[rev_col].sum()
want = f"₹{rev/1e7:,.2f} Cr" if rev >= 1e7 else f"₹{rev/1e5:,.2f} L"
checks.append(("total revenue overall", want,
               plain_of("what is the total commission revenue overall")))

gmv_f = fdf["Final Bid Value"].sum()
want_gmv = f"₹{gmv_f/1e7:,.2f} Cr" if gmv_f >= 1e7 else f"₹{gmv_f/1e5:,.2f} L"
checks.append(("filtered GMV", want_gmv, plain_of("total gmv")))

top_state = (fdf.groupby("State")[rev_col].sum().sort_values(ascending=False)
             .index[0])
checks.append(("top state by revenue", str(top_state), plain_of("top 5 states by revenue")))

pf = DE.period_frame(fdf)
best_period = pf.loc[pf["Revenue"].idxmax(), "Period"]
checks.append(("best revenue period", str(best_period), plain_of("which is the best month?")))

Q = DE.compute_quality(df)
checks.append(("overall quality score", f"{Q['overall']:,.2f}%",
               plain_of("how healthy is the data?")))

top_seller = DE.entity_performance(fdf, "Seller Name", "Deals").nlargest(1, "GMV")
if not top_seller.empty:
    checks.append(("top seller by GMV", str(top_seller.iloc[0]["Seller Name"])[:22],
                   plain_of("top 10 sellers by gmv")))

n_states = df["State"].nunique()
checks.append(("state count", f"{n_states:,}", plain_of("how many states are there")))

# The "revenue"/"VENUE" trap: a ranking must never be silently narrowed by an
# approximate name match. Top state revenue must equal the plain pandas answer.
top_rev = fdf.groupby("State")[rev_col].sum().max()
want_top = (f"₹{top_rev/1e7:,.2f} Cr" if top_rev >= 1e7
            else f"₹{top_rev/1e5:,.2f} L" if top_rev >= 1e5
            else f"₹{top_rev/1e3:,.1f} K")
checks.append(("top state revenue value", want_top, plain_of("top 5 states by revenue")))

# Comparisons must put both segments in one answer.
segs = sorted(df["Seller Segment"].dropna().unique().tolist())
cmp_txt = plain_of("captive vs non-captive")
checks.append(("comparison names both segments",
               segs[0], cmp_txt))
checks.append(("comparison names second segment", segs[-1], cmp_txt))

# A definition cue must reach the metric dictionary.
checks.append(("definition of take rate", "SUM(Total Income (Ex GST)) / SUM(Final Bid Value)",
               plain_of("define take rate")))

# A bare metric question must return the number, not just the definition.
tr = fdf[rev_col].sum() / fdf["Final Bid Value"].sum() * 100
checks.append(("bare take rate returns value", f"{tr:,.2f}%", plain_of("take rate")))

# Coverage must name the first and last period.
pf_all = DE.period_frame(df)
checks.append(("coverage names latest period", str(pf_all.iloc[-1]["Period"]),
               plain_of("what period does the data cover?")))

print("numeric spot checks")
for name, expected, got in checks:
    ok = expected in got
    print(f"  [{'ok ' if ok else 'BAD'}] {name:<26} expected {expected!r}")
    if not ok:
        fails.append(f"MISMATCH {name}: {expected!r} not in → {got[:220]}")

print()
if fails:
    print(f"FAILURES ({len(fails)}):")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print(f"all {len(QUESTIONS)} questions answered, all {len(checks)} spot checks matched")
_ = pd
