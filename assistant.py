"""
The dashboard assistant — a deterministic question-answering engine.

Design note
-----------
Every answer is *computed* from the live dataframe through ``data_engine``, the
same functions the cards and charts use. Nothing is generated, so a number in
the chat can never disagree with a number on a card, there is no API key to
manage, and the panel keeps working with no network at all.

The router is intentionally ordered rather than scored: specific questions
("what is take rate", "top 5 states by revenue") are matched before general
ones ("how is revenue doing"), so a narrow question never falls through to a
broad summary.

Entry point
-----------
    reply = assistant.answer("top 5 sellers by revenue", ctx)
    reply.html      → HTML for the chat bubble
    reply.chips     → follow-up suggestions

``ctx`` is built by ``app.main()`` and carries the full frame, the filtered
frame, the active selection and a lazy hook for the quality report.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from html import escape

import numpy as np
import pandas as pd

import data_engine as DE
from fmt import inr, num, pct, signed_pct


# ═════════════════════════════════════════════════════════════════════════════
# REPLY
# ═════════════════════════════════════════════════════════════════════════════
@dataclass
class Reply:
    html: str
    chips: list[str] = field(default_factory=list)


# ═════════════════════════════════════════════════════════════════════════════
# VOCABULARY
#
# Phrases are matched longest-first, so "average commission" wins over
# "commission" and "take rate" wins over "rate".
# ═════════════════════════════════════════════════════════════════════════════
MEASURES: dict[str, dict] = {
    "revenue": dict(
        label="Commission revenue", short="commission revenue",
        pf="Revenue", metric="revenue", fmt="inr",
        words=("commission revenue", "commission income", "revenue", "income",
               "total income", "earnings", "commission earned", "platform income",
               "top line", "topline"),
    ),
    "gmv": dict(
        label="GMV", short="GMV",
        pf="GMV", metric="gmv", fmt="inr",
        words=("gmv", "gross merchandise value", "gross merchandise",
               "final bid value", "bid value", "sales value", "turnover",
               "merchandise value", "transaction value total"),
    ),
    "transactions": dict(
        label="Transactions", short="transactions",
        pf="Transactions", metric="transactions", fmt="num",
        words=("transactions", "transaction", "deals", "deal", "conversions",
               "conversion", "volume", "count", "units", "vehicles sold",
               "cars sold", "how many cars", "throughput"),
    ),
    "take_rate": dict(
        label="Take rate", short="take rate",
        pf="TakeRate", metric="take_rate", fmt="pct",
        words=("take rate", "takerate", "take-rate", "commission rate",
               "margin", "monetisation", "monetization", "yield"),
    ),
    "avg_bid": dict(
        label="Avg. transaction value", short="average transaction value",
        pf="AvgBid", metric="avg_txn_value", fmt="inr",
        words=("average transaction value", "avg transaction value",
               "average txn value", "avg txn value", "average bid", "avg bid",
               "average deal size", "avg deal size", "average deal value",
               "average selling price", "average ticket", "ticket size", "asp"),
    ),
    "avg_commission": dict(
        label="Avg. commission", short="average commission",
        pf="AvgCommission", metric="avg_commission", fmt="inr",
        words=("average commission", "avg commission", "commission per deal",
               "commission per transaction", "average income", "avg income",
               "income per deal"),
    ),
}

DIMENSIONS: dict[str, tuple[str, ...]] = {
    "State": ("state", "states", "region", "regions", "geography", "geographic",
              "geo", "location", "market", "markets", "territory"),
    "Seller Name": ("seller", "sellers", "seller name", "supplier", "suppliers",
                    "supply", "consignor", "vendor", "vendors", "dealer", "dealers"),
    "Buyer Name": ("buyer", "buyers", "buyer name", "purchaser", "purchasers",
                   "bidder", "bidders", "demand", "customer", "customers"),
    "Make": ("make", "makes", "brand", "brands", "oem", "oems",
             "manufacturer", "manufacturers"),
    "Model": ("model", "models", "variant", "variants", "nameplate"),
    "Seller Segment": ("segment", "segments", "seller segment", "captive",
                       "non-captive", "noncaptive", "non captive"),
    "Month": ("month", "months", "monthly", "month on month", "mom"),
    "FY": ("fy", "financial year", "financial years", "fiscal year",
           "fiscal years", "year on year", "yoy"),
    "Period": ("period", "periods", "timeline"),
}

_DIM_ORDER = ["Seller Segment", "Seller Name", "Buyer Name", "State", "Make",
              "Model", "FY", "Month", "Period"]

# Dataset values that double as ordinary English — month names, and the vehicle
# models named after nouns ("Venue", "City", "Go"). These only count as an entity
# when a preposition puts them in the position of a name.
_AMBIGUOUS_VALUES = {"may", "march", "august", "mg", "on", "go", "one",
                     "city", "venue", "best", "top", "new", "count"}

GREETINGS = ("hi", "hello", "hey", "yo", "namaste", "good morning",
             "good afternoon", "good evening", "hiya", "sup")

DEFAULT_CHIPS = [
    "Give me a summary",
    "Top 5 states by revenue",
    "How is revenue trending?",
    "How healthy is the data?",
]


# ═════════════════════════════════════════════════════════════════════════════
# HTML FRAGMENTS  (styled by chatbot._CSS)
# ═════════════════════════════════════════════════════════════════════════════
def _p(t: str) -> str:
    return f"<p>{t}</p>"


def _note(t: str) -> str:
    return f'<p class="kb-note">{t}</p>'


def _kvs(rows: list[tuple[str, str]]) -> str:
    if not rows:
        return ""
    cells = "".join(
        f'<div class="kb-kv" style="--i:{i}"><span>{escape(str(k))}</span>'
        f"<b>{v}</b></div>"
        for i, (k, v) in enumerate(rows)
    )
    return f'<div class="kb-kvs">{cells}</div>'


def _rank(rows: list[tuple[str, str, str]], *, tone: str = "jade") -> str:
    """
    Ranked bar list.

    ``rows`` is (label, formatted value, fill 0-100). The bar width rides on a
    CSS custom property so the growth animation can be pure CSS.
    """
    if not rows:
        return ""
    items = "".join(
        f'<div class="kb-row" style="--w:{max(2.0, min(100.0, float(w))):.1f}%;--i:{i}">'
        f'<span class="kb-rk">{i + 1}</span>'
        f'<span class="kb-lb" title="{escape(str(lb))}">{escape(str(lb))}</span>'
        f'<span class="kb-vl">{v}</span><i></i></div>'
        for i, (lb, v, w) in enumerate(rows)
    )
    return f'<div class="kb-rank kb-{tone}">{items}</div>'


def _delta_tag(v: float | None, label: str = "") -> str:
    if v is None or pd.isna(v):
        return ""
    cls = "kb-up" if v > 0.05 else ("kb-down" if v < -0.05 else "kb-flat")
    arrow = "▲" if v > 0.05 else ("▼" if v < -0.05 else "●")
    tail = f' <em>{escape(label)}</em>' if label else ""
    return f'<span class="kb-tag {cls}">{arrow} {abs(v):.1f}%{tail}</span>'


def _tag(t: str, tone: str = "") -> str:
    return f'<span class="kb-tag {tone}">{t}</span>'


def _bullets(items: list[str]) -> str:
    if not items:
        return ""
    lis = "".join(f'<li style="--i:{i}">{t}</li>' for i, t in enumerate(items))
    return f'<ul class="kb-ul">{lis}</ul>'


def _scopebar(label: str) -> str:
    return f'<div class="kb-scope">{escape(label)}</div>'


# ═════════════════════════════════════════════════════════════════════════════
# PARSING
# ═════════════════════════════════════════════════════════════════════════════
_WORD_RE = re.compile(r"[a-z0-9&+.\-]+")


def _norm(s: str) -> str:
    s = str(s or "").lower()
    s = s.replace("₹", " ").replace("’", "'").replace("%", " percent ")
    return re.sub(r"\s+", " ", s).strip()


def _words(q: str) -> list[str]:
    return _WORD_RE.findall(q)


def _grams(q: str, upto: int = 6) -> set[str]:
    w = _words(q)
    out: set[str] = set()
    for size in range(1, upto + 1):
        for i in range(len(w) - size + 1):
            out.add(" ".join(w[i:i + size]))
    return out


def _key(s: str) -> str:
    return " ".join(_WORD_RE.findall(str(s).lower()))


def _has(q: str, *phrases: str) -> bool:
    g = _grams(q)
    return any(p in g for p in phrases if p)


def _longest_match(grams: set[str], table: dict[str, tuple[str, ...]]) -> list[str]:
    """Return every key in ``table`` matched by the question, longest phrase first."""
    hits: list[tuple[int, str]] = []
    for key, words in table.items():
        best = 0
        for w in words:
            if w in grams:
                best = max(best, len(w))
        if best:
            hits.append((best, key))
    hits.sort(key=lambda h: -h[0])
    return [k for _, k in hits]


def _find_measure(q: str) -> str | None:
    grams = _grams(q)
    table = {k: v["words"] for k, v in MEASURES.items()}
    found = _longest_match(grams, table)
    return found[0] if found else None


def _find_dims(q: str) -> list[str]:
    return _longest_match(_grams(q), DIMENSIONS)


def _find_n(q: str, default: int = 5) -> int:
    m = re.search(r"\b(?:top|bottom|first|last|best|worst|lowest|highest)\s+(\d{1,3})\b", q)
    if m:
        return max(1, min(25, int(m.group(1))))
    m = re.search(r"\b(\d{1,3})\s+(?:top|best|biggest|largest|worst)\b", q)
    if m:
        return max(1, min(25, int(m.group(1))))
    return default


_ENTITY_COLS = ("Seller Segment", "State", "Make", "Model",
                "Seller Name", "Buyer Name", "FY", "Month")


def _scan_entities(df: pd.DataFrame, q: str) -> list[tuple[str, str]]:
    """
    Find dataset values named in the question.

    Matching is on whole-word n-grams rather than substrings, so 'Goa' never
    matches 'goal'. Values that are also ordinary English need a preposition in
    front of them ("in May") before they count.
    """
    grams = _grams(q)
    hits: list[tuple[int, str, str]] = []
    for col in _ENTITY_COLS:
        if col not in df.columns:
            continue
        for raw in df[col].dropna().astype(str).unique():
            k = _key(raw)
            if len(k) < 2:
                continue
            if k not in grams:
                continue
            if k in _AMBIGUOUS_VALUES and not re.search(
                    r"\b(?:in|for|during|of|month|fy|from|to|vs|versus)\s+" + re.escape(k) + r"\b", q):
                continue
            hits.append((len(k), col, raw))

    hits.sort(key=lambda h: -h[0])
    out: list[tuple[str, str]] = []
    seen: list[str] = []
    for _, col, raw in hits:
        k = _key(raw)
        if any(k != s and k in s for s in seen):      # swallowed by a longer hit
            continue
        if (col, raw) in out:
            continue
        seen.append(k)
        out.append((col, raw))
    return out[:6]


def _fuzzy_entity(df: pd.DataFrame, q: str) -> tuple[str, str] | None:
    """
    Last-chance lookup for a misspelt seller / buyer / make.

    Deliberately timid. Approximate matching against thousands of names will
    happily pair any word with something — "revenue" sits 0.83 away from the
    model "Venue" — so the cutoff is high and every word this module already
    understands is excluded before the comparison runs. It is only reached for
    short questions that named no measure and no dimension, i.e. the case where
    the user almost certainly typed a name and nothing else.
    """
    grams = [g for g in _grams(q, 4)
             if len(g) >= 5 and not (set(g.split()) & _RESERVED)]
    if not grams:
        return None
    for col in ("Seller Name", "Buyer Name", "Make", "Model", "State"):
        if col not in df.columns:
            continue
        index = {_key(v): v for v in df[col].dropna().astype(str).unique()}
        for g in sorted(grams, key=len, reverse=True):
            near = difflib.get_close_matches(g, list(index), n=1, cutoff=0.9)
            if near:
                return col, index[near[0]]
    return None


# ═════════════════════════════════════════════════════════════════════════════
# AGGREGATION
# ═════════════════════════════════════════════════════════════════════════════
_PLURALS = {"State": "states", "Seller Name": "sellers", "Buyer Name": "buyers",
            "Make": "makes", "Model": "models", "Seller Segment": "segments",
            "Month": "months", "FY": "financial years", "Period": "periods"}


def _plural(dim: str) -> str:
    """Natural plural for a column name, used in the follow-up suggestions."""
    return _PLURALS.get(dim, dim.lower() + "s")


def _fmt_measure(measure: str, v) -> str:
    kind = MEASURES[measure]["fmt"]
    if kind == "inr":
        return inr(v)
    if kind == "pct":
        return pct(v)
    return num(v)


def _total(df: pd.DataFrame, measure: str) -> float:
    m = DE.compute_metrics(df)
    return float(m[MEASURES[measure]["metric"]])


def _breakdown(df: pd.DataFrame, dim: str, measure: str) -> pd.DataFrame:
    """One row per value of ``dim`` with the measure, deal count and GMV share."""
    if df.empty or dim not in df.columns or not df[dim].notna().any():
        return pd.DataFrame()
    src = df[df[dim].notna()]
    g = src.groupby(dim, dropna=True, observed=False)
    base = pd.DataFrame({
        "Deals": g.size(),
        "GMV": g["Final Bid Value"].sum(),
        "Revenue": g["Total Income"].sum(),
        "AvgBid": g["Final Bid Value"].mean(),
        "AvgCommission": g["Total Income"].mean(),
    })
    base["TakeRate"] = np.where(base["GMV"] > 0, base["Revenue"] / base["GMV"] * 100, np.nan)
    base["Transactions"] = base["Deals"]
    col = MEASURES[measure]["pf"]
    base["value"] = base[col]
    total = base["value"].sum()
    base["share"] = np.where(total > 0, base["value"] / total * 100, 0.0) \
        if MEASURES[measure]["fmt"] != "pct" else np.nan
    out = base.reset_index().rename(columns={dim: "label"})
    out["label"] = out["label"].astype(str)
    if dim == "Month":
        out["_o"] = out["label"].map(DE.MONTH_INDEX)
    return out


def _rank_rows(bd: pd.DataFrame, measure: str, n: int, ascending: bool) -> list[tuple]:
    d = bd.dropna(subset=["value"]).sort_values("value", ascending=ascending).head(n)
    if d.empty:
        return []
    peak = float(d["value"].abs().max()) or 1.0
    return [(r["label"], _fmt_measure(measure, r["value"]), abs(r["value"]) / peak * 100)
            for _, r in d.iterrows()]


# ═════════════════════════════════════════════════════════════════════════════
# SCOPE
# ═════════════════════════════════════════════════════════════════════════════
_ALL_DATA_WORDS = ("overall", "all data", "entire dataset", "whole dataset",
                   "full dataset", "unfiltered", "ignore filters",
                   "ignoring filters", "across everything", "all time",
                   "in total across", "whole data", "entire data")


def _filter_summary(ctx: dict) -> list[str]:
    """Human description of the filters that differ from 'everything'."""
    df, sel = ctx["df"], ctx.get("sel") or {}
    out: list[str] = []
    for col, picked in sel.items():
        if col not in df.columns:
            continue
        full = df[col].dropna().unique().tolist()
        picked = list(picked or [])
        if len(picked) >= len(full):
            continue
        if not picked:
            out.append(f"{col}: nothing selected")
        elif len(picked) <= 4:
            out.append(f"{col}: {', '.join(map(str, picked))}")
        else:
            out.append(f"{col}: {len(picked)} of {len(full)} selected")
    lo, hi = (ctx.get("bid_range") or (None, None))
    if lo is not None and "Final Bid Value" in df.columns and df["Final Bid Value"].notna().any():
        blo = float(df["Final Bid Value"].min())
        bhi = float(df["Final Bid Value"].max())
        if lo > blo or hi < bhi:
            out.append(f"Bid value: {inr(lo)} – {inr(hi)}")
    return out


def _scope(q: str, ctx: dict) -> tuple[pd.DataFrame, str]:
    """Pick the frame a question is about and describe it in one line."""
    if _has(q, *_ALL_DATA_WORDS):
        df = ctx["df"]
        return df, f"Whole dataset · {len(df):,} records · filters ignored"
    fdf = ctx["fdf"]
    active = _filter_summary(ctx)
    if active:
        return fdf, f"Current selection · {len(fdf):,} records · {'; '.join(active[:3])}"
    return fdf, f"Current selection · {len(fdf):,} records · no filters applied"


# ═════════════════════════════════════════════════════════════════════════════
# HANDLERS
# ═════════════════════════════════════════════════════════════════════════════
def _h_greeting(ctx: dict) -> Reply:
    df, fdf = ctx["df"], ctx["fdf"]
    m = DE.compute_metrics(fdf)
    html = (
        _p("Hello. I am the analyst built into this dashboard — I read the same "
           "dataset the cards do and work the numbers out on the spot.")
        + _kvs([("Records in view", num(len(fdf))),
                ("GMV", inr(m["gmv"])),
                ("Revenue", inr(m["revenue"])),
                ("Take rate", pct(m["take_rate"]))])
        + _note(f"Loaded from <b>{escape(str(ctx.get('source_label', 'workbook')))}</b> · "
                f"{len(df):,} rows total. Ask me anything below.")
    )
    return Reply(html, DEFAULT_CHIPS)


def _h_help(ctx: dict) -> Reply:
    html = (
        _p("I answer from the live dataset — no guessing, every figure recomputed "
           "when you ask. Things I am good at:")
        + _bullets([
            "<b>Headline numbers</b> — “what is the total revenue”, “take rate”, “avg deal size”",
            "<b>Rankings</b> — “top 10 sellers by GMV”, “worst 5 states by take rate”",
            "<b>Breakdowns</b> — “revenue by month”, “transactions by segment”",
            "<b>Anything or anyone by name</b> — “how did Maharashtra do”, “MARUTI SUZUKI performance”",
            "<b>Comparisons</b> — “Captive vs Non-Captive”, “FY24 vs FY25”",
            "<b>Trends</b> — “how is revenue trending”, “best month”, “month on month growth”",
            "<b>Concentration risk</b> — “how concentrated is supply”, “top 5 share of GMV”",
            "<b>Price bands and vehicle mix</b> — “which price band yields most”, “odometer spread”",
            "<b>Data quality</b> — “is the data clean”, “duplicates”, “missing values”, “outliers”",
            "<b>Definitions</b> — “what is take rate”, “how is GMV calculated”",
            "<b>Using the dashboard</b> — “how do I upload data”, “how do I export”",
        ])
        + _note("Say <b>overall</b> anywhere in a question and I will ignore the "
                "sidebar filters for that answer.")
    )
    return Reply(html, ["Top 10 sellers by GMV", "Captive vs Non-Captive",
                        "Which price band yields most?", "What is take rate?"])


def _h_definition(q: str, ctx: dict) -> Reply:
    grams = _grams(q)
    rows: list[tuple[str, str, str]] = []
    for name, formula, meaning in DE.METRIC_DEFINITIONS:
        k = _key(name)
        aliases = {k, k.replace("avg.", "average"), k.replace(".", "")}
        measure_hit = False
        mk = _find_measure(q)
        if mk:
            measure_hit = _key(MEASURES[mk]["label"]) == k or _key(MEASURES[mk]["short"]) == k
        if aliases & grams or measure_hit:
            rows.append((name, formula, meaning))

    if not rows:
        body = _p("Here is the full metric dictionary this dashboard runs on — "
                  "one definition per number, used everywhere.")
        body += "".join(
            f'<div class="kb-def" style="--i:{i}"><b>{escape(n)}</b>'
            f'<code>{escape(f)}</code><span>{escape(mn)}</span></div>'
            for i, (n, f, mn) in enumerate(DE.METRIC_DEFINITIONS))
        return Reply(body, ["What is take rate?", "How is GMV calculated?",
                            "Give me a summary"])

    scope_df, scope = _scope(q, ctx)
    m = DE.compute_metrics(scope_df)
    live = {"Transactions": num(m["transactions"]), "GMV": inr(m["gmv"]),
            "Commission Revenue": inr(m["revenue"]),
            "Avg. Commission": inr(m["avg_commission"]),
            "Take Rate": pct(m["take_rate"]),
            "Avg. Transaction Value": inr(m["avg_txn_value"]),
            "Unique Sellers": num(m["unique_sellers"]),
            "Avg. Transactions / Seller": f"{m['txn_per_seller']:.1f}",
            "Unique Buyers": num(m["unique_buyers"]),
            "Avg. Purchases / Buyer": f"{m['purchases_per_buyer']:.1f}"}

    html = ""
    for i, (n, f, mn) in enumerate(rows[:4]):
        html += (f'<div class="kb-def" style="--i:{i}"><b>{escape(n)}</b>'
                 f'<code>{escape(f)}</code><span>{escape(mn)}</span></div>')
    vals = [(n, live[n]) for n, _, _ in rows[:4] if n in live]
    if vals:
        html += _p("In the current selection that works out to:") + _kvs(vals)
    html += _scopebar(scope)
    return Reply(html, ["Show every metric definition", "Give me a summary",
                        "How healthy is the data?"])


def _h_howto(q: str, ctx: dict) -> Reply:
    if _has(q, "upload", "new data", "new file", "my own data", "import", "replace data"):
        html = (_p("Loading your own workbook:")
                + _bullets([
                    "Open the <b>⤒ Upload Data</b> tab.",
                    "Drop an <code>.xlsx</code> / <code>.xls</code> file with the 13 template "
                    "columns — <b>FY, Month, State, Final Bid Value</b> and "
                    "<b>Total Income</b> are the mandatory ones.",
                    "The file is validated first: blocking errors are listed in red, "
                    "cosmetic fixes (month casing, spacing, registration format) are "
                    "applied automatically and reported.",
                    "Press <b>Load this dataset</b> — every tab, filter and KPI rebinds to it.",
                    "<b>↺ Restore bundled dataset</b> in the sidebar puts the original back.",
                ]))
        return Reply(html, ["What columns are required?", "How healthy is the data?"])
    if _has(q, "export", "download", "csv", "excel out", "save data", "extract"):
        return Reply(
            _p("The <b>⬢ Sellers, Buyers &amp; Vehicles</b> tab ends with a download "
               "button that exports exactly the rows surviving your current filters, "
               "as CSV. Charts export individually too — hover any chart and use the "
               "camera icon in its toolbar for a PNG.")
            + _note("The export follows the filters, not the whole workbook. Clear the "
                    "filters first if you want everything."),
            ["What filters are active?", "Give me a summary"])
    if _has(q, "filter", "filters", "narrow", "slice", "selection"):
        return Reply(
            _p("Filters live in the sidebar, each one a card whose badge shows its state "
               "at a glance — <code>all</code>, <code>3/22</code> or <code>none</code>.")
            + _bullets([
                "<b>Financial year</b>, <b>Month</b>, <b>State</b>, <b>Seller segment</b> "
                "and <b>Make</b> are value pickers; each has <b>All</b>, <b>Top n</b> "
                "and <b>Clear</b> shortcuts.",
                "<b>Bid value</b> is a range slider on the winning bid.",
                "The header badge counts how many filters differ from 'everything'.",
                "<b>↺ Reset filters</b> returns all of them to full range.",
            ])
            + _note("Overview and the performance tab respect the filters. "
                    "Data Quality deliberately does not — it always audits the whole file."),
            ["What filters are active?", "Top 5 states by revenue"])
    if _has(q, "theme", "dark mode", "light mode", "appearance", "colour", "color"):
        mode = ctx.get("theme_mode", "dark")
        return Reply(
            _p(f"You are on the <b>{escape(mode)}</b> palette. The switch sits at the top "
               "of the sidebar under <b>Appearance</b> — it repaints the CSS layer, the "
               "Plotly figures and Streamlit's own canvas widgets together, so nothing "
               "is left behind."),
            ["Give me a summary", "How is revenue trending?"])
    if _has(q, "tab", "tabs", "navigate", "sections", "where do i find", "layout"):
        return Reply(
            _p("Four tabs:")
            + _bullets([
                "<b>◈ Overview</b> — ten headline KPIs, auto-written insights, trend, "
                "geography and seller-mix charts.",
                "<b>⬢ Sellers, Buyers &amp; Vehicles</b> — ranked tables, Pareto curves, "
                "make treemap, top models, price bands, age-vs-value and the CSV export.",
                "<b>⤒ Upload Data</b> — the template contract and the file uploader.",
                "<b>◉ Data Quality &amp; SSOT</b> — completeness, uniqueness, validity and "
                "consistency scores on the unfiltered file, plus the metric dictionary.",
            ]),
            ["Give me a summary", "How healthy is the data?"])
    return _h_help(ctx)


def _h_quality(q: str, ctx: dict) -> Reply:
    qf = ctx.get("quality_fn")
    if not callable(qf):
        return Reply(_p("The quality report is not available in this session."), DEFAULT_CHIPS)
    Q = qf()
    label, _tone = DE.grade(Q["overall"])

    if _has(q, "duplicate", "duplicates", "duplicated", "repeated vehicle", "repeat rows"):
        html = (_p(f"Uniqueness scores <b>{pct(Q['uniqueness'])}</b>.")
                + _kvs([("Fully duplicated rows", num(Q["duplicate_rows"])),
                        ("Repeated vehicle numbers", num(Q["duplicate_vehicles"])),
                        ("Rows audited", num(Q["rows"]))]))
        rv = Q.get("repeated_vehicle_list")
        if isinstance(rv, pd.DataFrame) and not rv.empty:
            peak = float(rv["Occurrences"].max()) or 1.0
            html += _p("Registrations appearing most often:")
            html += _rank([(r["Vehicle Number"], f"{int(r['Occurrences'])}×",
                            r["Occurrences"] / peak * 100)
                           for _, r in rv.head(6).iterrows()], tone="amber")
            html += _note("A registration can legitimately recur — the same vehicle "
                          "resold later. Check the period before treating it as an error.")
        return Reply(html, ["Any missing values?", "Show me the outliers",
                            "How healthy is the data?"])

    if _has(q, "missing", "null", "nulls", "blank", "blanks", "empty", "incomplete",
            "completeness", "gaps"):
        html = (_p(f"Completeness is <b>{pct(Q['completeness'])}</b> — "
                   f"{num(Q['null_cells'])} empty cells out of {num(Q['total_cells'])}.")
                )
        ch = Q.get("column_health")
        if isinstance(ch, pd.DataFrame) and not ch.empty:
            worst = ch[ch["Nulls"] > 0].head(6)
            if worst.empty:
                html += _p("Every business column is fully populated. Nothing to chase.")
            else:
                peak = float(worst["Null %"].max()) or 1.0
                html += _p("Columns carrying the gaps:")
                html += _rank([(r["Column"], f"{r['Null %']:.1f}% empty",
                                r["Null %"] / peak * 100)
                               for _, r in worst.iterrows()], tone="rose")
        return Reply(html, ["Any duplicates?", "Are the values valid?",
                            "How healthy is the data?"])

    if _has(q, "outlier", "outliers", "anomaly", "anomalies", "extreme", "suspicious value"):
        outs = Q.get("outliers") or {}
        if not outs:
            return Reply(_p("No numeric column had enough values to run an outlier test."),
                         DEFAULT_CHIPS)
        html = _p("IQR test — anything beyond 1.5× the interquartile range:")
        for i, (col, o) in enumerate(outs.items()):
            html += (f'<div class="kb-def" style="--i:{i}"><b>{escape(col)}</b>'
                     f'<code>{o["count"]:,} flagged · {o["pct"]:.2f}% of values</code>'
                     f'<span>expected band {inr(o["lower"]) if col != "Odometer" else num(o["lower"])}'
                     f' – {inr(o["upper"]) if col != "Odometer" else num(o["upper"])}'
                     f' · observed {inr(o["min"]) if col != "Odometer" else num(o["min"])}'
                     f' to {inr(o["max"]) if col != "Odometer" else num(o["max"])}</span></div>')
        html += _note("Outliers are flagged, never dropped. A ₹40 L bid can be perfectly "
                      "real — the point is that you saw it.")
        return Reply(html, ["Any duplicates?", "Any missing values?"])

    if _has(q, "valid", "validity", "invalid", "rule", "rules", "check", "checks",
            "consistency", "consistent", "variant", "variants", "spelling"):
        html = (_p(f"Validity <b>{pct(Q['validity'])}</b> · "
                   f"consistency <b>{pct(Q['consistency'])}</b>.")
                + _kvs([("Rows failing a rule", num(Q["invalid_rows"])),
                        ("Rows with spelling variants", num(Q["consistency_rows_affected"]))]))
        checks = Q.get("validity_checks") or []
        failing = [(name, n) for name, n, _ in checks if n]
        if failing:
            html += _p("Rules with exceptions:")
            html += _bullets([f"{escape(n)} — <b>{c:,}</b> row(s)" for n, c in failing[:6]])
        else:
            html += _p("Every declared rule passes on all rows.")
        vr = Q.get("variant_report")
        if isinstance(vr, pd.DataFrame) and not vr.empty:
            html += _p("Same entity, different spelling:")
            html += _bullets([f"<b>{escape(str(r['Column']))}</b> — "
                              f"{escape(str(r['Values Found']))} "
                              f"({int(r['Rows Affected']):,} rows)"
                              for _, r in vr.head(4).iterrows()])
        return Reply(html, ["Any duplicates?", "Any missing values?",
                            "Show me the outliers"])

    dims = Q["dimensions"]
    peak = 100.0
    html = (_p(f"Overall data health is <b>{pct(Q['overall'])}</b> — "
               f"<b>{escape(label)}</b>, measured across {num(Q['rows'])} rows "
               f"and {Q['cols']} fields.")
            + _rank([(k, pct(v), v / peak * 100) for k, v in dims.items()],
                    tone="jade")
            + _kvs([("Empty cells", num(Q["null_cells"])),
                    ("Duplicate rows", num(Q["duplicate_rows"])),
                    ("Repeated vehicles", num(Q["duplicate_vehicles"])),
                    ("Rows failing a rule", num(Q["invalid_rows"]))])
            + _note("Audited on the unfiltered workbook, on purpose — quality is a "
                    "property of the file, not of your current view."))
    return Reply(html, ["Any missing values?", "Any duplicates?",
                        "Show me the outliers", "Are the values valid?"])


def _h_coverage(q: str, ctx: dict) -> Reply:
    df = ctx["df"]
    fdf = ctx["fdf"]

    # "how many <dimension>"
    if _has(q, "how many", "number of", "count of", "distinct", "unique"):
        dims = _find_dims(q)
        target = next((d for d in dims if d in df.columns), None)
        if target:
            full = int(df[target].nunique(dropna=True))
            inview = int(fdf[target].nunique(dropna=True)) if not fdf.empty else 0
            return Reply(
                _p(f"<b>{full:,}</b> distinct {escape(target)} value(s) in the workbook, "
                   f"<b>{inview:,}</b> present in your current selection.")
                + _kvs([("In workbook", num(full)), ("In view", num(inview))]),
                [f"Top 5 {_plural(target)} by revenue", "Give me a summary"])
        if _has(q, "record", "records", "row", "rows", "transaction", "transactions", "deals"):
            return Reply(
                _p(f"The workbook holds <b>{len(df):,}</b> transaction rows. "
                   f"<b>{len(fdf):,}</b> survive the current filters "
                   f"({len(fdf) / len(df) * 100 if len(df) else 0:.1f}%)."),
                DEFAULT_CHIPS)

    if _has(q, "column", "columns", "field", "fields", "schema", "structure",
            "what data", "which data", "template"):
        cols = [c for c in df.columns if not c.startswith("_") and c != "Period"]
        present = [c for c in DE.REQUIRED_COLUMNS if c in cols]
        extra = [c for c in cols if c not in DE.REQUIRED_COLUMNS]
        html = (_p(f"One row per converted vehicle, <b>{len(cols)}</b> fields, "
                   f"<b>{len(df):,}</b> rows.")
                + _p("<b>Dimensions</b> — " + ", ".join(f"<code>{escape(c)}</code>"
                                                        for c in DE.DIM_COLS if c in cols))
                + _p("<b>Measures</b> — " + ", ".join(f"<code>{escape(c)}</code>"
                                                      for c in DE.NUM_COLS if c in cols)))
        missing = [c for c in DE.REQUIRED_COLUMNS if c not in cols]
        if missing:
            html += _note("Absent from this file, so the related visuals are hidden: "
                          + ", ".join(f"<code>{escape(c)}</code>" for c in missing))
        if extra:
            html += _note("Extra columns carried along: "
                          + ", ".join(f"<code>{escape(c)}</code>" for c in extra[:8]))
        html += _note(f"{len(present)} of the {len(DE.REQUIRED_COLUMNS)} template "
                      "columns are present.")
        return Reply(html, ["What period does the data cover?",
                            "Which states are covered?", "What is take rate?"])

    if _has(q, "state", "states", "region", "geography", "which states", "covered"):
        if "State" in df.columns:
            states = sorted(df["State"].dropna().unique().tolist())
            bd = _breakdown(fdf, "State", "revenue")
            html = _p(f"<b>{len(states)}</b> states in the workbook: "
                      + ", ".join(escape(s) for s in states[:24])
                      + (" …" if len(states) > 24 else ""))
            if not bd.empty:
                html += _p("By commission revenue in the current view:")
                html += _rank(_rank_rows(bd, "revenue", 6, False))
            return Reply(html, ["Top 5 states by revenue",
                                "Which state has the best take rate?"])

    cov_fy = sorted(df["FY"].dropna().unique().tolist()) if "FY" in df else []
    months = [m for m in DE.MONTH_ORDER if "Month" in df and m in set(df["Month"].dropna())]
    pf = DE.period_frame(df)
    html = (_p("Coverage of the loaded workbook:")
            + _kvs([("Rows", num(len(df))),
                    ("Financial years", ", ".join(map(str, cov_fy)) or "—"),
                    ("Periods", num(len(pf))),
                    ("Months seen", ", ".join(months) or "—")]))
    if not pf.empty:
        html += _p(f"Earliest period <b>{escape(str(pf.iloc[0]['Period']))}</b>, "
                   f"latest <b>{escape(str(pf.iloc[-1]['Period']))}</b>.")
    counts = [(lbl, num(int(df[col].nunique(dropna=True))))
              for col, lbl in (("State", "States"), ("Seller Name", "Sellers"),
                               ("Buyer Name", "Buyers"), ("Make", "Makes"),
                               ("Model", "Models")) if col in df.columns]
    if counts:
        html += _kvs(counts)
    html += _note(f"Source: <b>{escape(str(ctx.get('source_label', 'workbook')))}</b>")
    return Reply(html, ["What columns are in the data?", "Which states are covered?",
                        "Give me a summary"])


def _h_filters(q: str, ctx: dict) -> Reply:
    df, fdf = ctx["df"], ctx["fdf"]
    active = _filter_summary(ctx)
    share = len(fdf) / len(df) * 100 if len(df) else 0
    if not active:
        html = (_p(f"No filters are narrowing the view — all <b>{len(df):,}</b> rows "
                   "are in scope.")
                + _note("Sidebar filter cards show <code>all</code> across the board."))
    else:
        html = (_p(f"<b>{len(active)}</b> filter(s) are narrowing the view to "
                   f"<b>{len(fdf):,}</b> of {len(df):,} rows ({share:.1f}%).")
                + _bullets([escape(a) for a in active]))
        if fdf.empty:
            html += _note("Nothing matches that combination — every number will read "
                          "zero until you widen it. <b>↺ Reset filters</b> clears it.")
    if not fdf.empty:
        m = DE.compute_metrics(fdf)
        html += _kvs([("Transactions", num(m["transactions"])), ("GMV", inr(m["gmv"])),
                      ("Revenue", inr(m["revenue"])), ("Take rate", pct(m["take_rate"]))])
    return Reply(html, ["Give me a summary", "How is revenue trending?"])


def _h_summary(q: str, ctx: dict) -> Reply:
    scope_df, scope = _scope(q, ctx)
    if scope_df.empty:
        return _h_empty(scope)
    m = DE.compute_metrics(scope_df)
    pf = DE.period_frame(scope_df)
    d = DE.latest_period_deltas(pf)
    dl = d.get("_label", "")

    html = _p("Headline read on the data in scope:")
    html += _kvs([
        ("Transactions", num(m["transactions"])),
        ("GMV", inr(m["gmv"])),
        ("Commission revenue", inr(m["revenue"])),
        ("Take rate", pct(m["take_rate"])),
        ("Avg. deal value", inr(m["avg_txn_value"])),
        ("Avg. commission", inr(m["avg_commission"])),
        ("Unique sellers", num(m["unique_sellers"])),
        ("Unique buyers", num(m["unique_buyers"])),
    ])
    if d:
        tags = "".join(
            f'<span class="kb-mv">{escape(lbl)} {_delta_tag(d[k])}</span>'
            for k, lbl in (("revenue", "Revenue"), ("gmv", "GMV"),
                           ("transactions", "Deals"), ("take_rate", "Take rate"))
            if k in d)
        if tags:
            html += _p(f"Latest period <b>{escape(str(pf.iloc[-1]['Period']))}</b> "
                       f"{escape(dl)}:") + f'<div class="kb-mvs">{tags}</div>'

    lines: list[str] = []
    if "State" in scope_df.columns and scope_df["State"].notna().any():
        g = scope_df.groupby("State")["Total Income"].sum().sort_values(ascending=False)
        if g.sum():
            lines.append(f"<b>{escape(str(g.index[0]))}</b> leads geography with "
                         f"{inr(g.iloc[0])} of revenue ({g.iloc[0] / g.sum() * 100:.1f}% of the total).")
    if "Seller Name" in scope_df.columns and scope_df["Seller Name"].notna().any():
        sp = DE.entity_performance(scope_df, "Seller Name", "Deals")
        if not sp.empty:
            top5 = float(sp.nlargest(5, "GMV")["GMVShare"].sum())
            lines.append(f"The top 5 of {m['unique_sellers']:,} sellers carry "
                         f"<b>{top5:.1f}%</b> of GMV.")
    if "Seller Segment" in scope_df.columns and scope_df["Seller Segment"].nunique() > 1:
        seg = scope_df.groupby("Seller Segment").agg(
            r=("Total Income", "sum"), g=("Final Bid Value", "sum"))
        seg["t"] = seg["r"] / seg["g"] * 100
        best = seg["t"].idxmax()
        lines.append(f"<b>{escape(str(best))}</b> sellers monetise better at "
                     f"{seg.loc[best, 't']:.2f}% take rate.")
    bands = DE.price_bands(scope_df)
    if not bands.empty:
        b = bands[bands["Transactions"] > 0]
        if not b.empty and b["TakeRate"].notna().any():
            bb = b.loc[b["TakeRate"].idxmax()]
            lines.append(f"Yield peaks in the <b>{escape(str(bb['Band']))}</b> price band "
                         f"at {bb['TakeRate']:.2f}%.")
    if lines:
        html += _p("Standouts:") + _bullets(lines)
    html += _scopebar(scope)
    return Reply(html, ["Top 5 sellers by GMV", "How is revenue trending?",
                        "How concentrated is supply?", "How healthy is the data?"])


def _h_ranking(q: str, ctx: dict, dim: str, measure: str,
               entities: list[tuple[str, str]]) -> Reply:
    scope_df, scope = _scope(q, ctx)
    scoped_note = ""
    for col, val in entities:
        if col != dim and col in scope_df.columns:
            scope_df = scope_df[scope_df[col].astype(str) == str(val)]
            scoped_note += f" · {escape(str(val))}"
    if scope_df.empty:
        return _h_empty(scope + scoped_note)

    bottom = _has(q, "bottom", "worst", "lowest", "weakest", "least", "smallest",
                  "poorest", "underperforming", "under performing")
    n = _find_n(q, 5 if bottom else 10)
    bd = _breakdown(scope_df, dim, measure)
    if bd.empty:
        return Reply(_p(f"<code>{escape(dim)}</code> has no usable values in this "
                        "selection, so I cannot rank on it.") + _scopebar(scope),
                     DEFAULT_CHIPS)

    rows = _rank_rows(bd, measure, n, ascending=bottom)
    total = float(bd["value"].sum())
    word = "Lowest" if bottom else "Top"
    spec = MEASURES[measure]

    html = _p(f"{word} <b>{len(rows)}</b> {escape(dim)} by <b>{escape(spec['short'])}</b>"
              f", out of {bd['label'].nunique():,} value(s).")
    html += _rank(rows, tone="rose" if bottom else "jade")

    if spec["fmt"] != "pct" and total:
        shown = float(bd.dropna(subset=["value"])
                        .sort_values("value", ascending=bottom)
                        .head(n)["value"].sum())
        html += _kvs([(f"{word} {len(rows)} combined", _fmt_measure(measure, shown)),
                      ("Share of total", pct(shown / total * 100)),
                      ("Total in scope", _fmt_measure(measure, total))])
    else:
        html += _kvs([("Overall in scope", _fmt_measure(measure, _total(scope_df, measure)))])

    if not bottom and spec["fmt"] != "pct" and len(bd) >= 5 and total:
        top5 = float(bd.nlargest(5, "value")["value"].sum()) / total * 100
        verdict = ("heavily concentrated" if top5 > 60
                   else "moderately concentrated" if top5 > 40 else "well spread")
        html += _note(f"Top 5 hold {top5:.1f}% — {verdict}.")

    html += _scopebar(scope + scoped_note)
    other = "Revenue" if measure != "revenue" else "GMV"
    return Reply(html, [f"{'Top' if bottom else 'Bottom'} 5 {_plural(dim)} "
                        f"by {spec['short']}",
                        f"{other} by {dim.lower()}",
                        "How concentrated is supply?"])


def _h_breakdown(q: str, ctx: dict, dim: str, measure: str) -> Reply:
    scope_df, scope = _scope(q, ctx)
    if scope_df.empty:
        return _h_empty(scope)
    bd = _breakdown(scope_df, dim, measure)
    if bd.empty:
        return Reply(_p(f"No usable <code>{escape(dim)}</code> values in this selection.")
                     + _scopebar(scope), DEFAULT_CHIPS)

    spec = MEASURES[measure]
    if "_o" in bd.columns:
        bd = bd.sort_values("_o")
        rows_src = bd
    else:
        rows_src = bd.sort_values("value", ascending=False)
    rows_src = rows_src.head(14)
    peak = float(bd["value"].abs().max()) or 1.0
    rows = [(r["label"], _fmt_measure(measure, r["value"]), abs(r["value"]) / peak * 100)
            for _, r in rows_src.iterrows()]

    html = _p(f"<b>{escape(spec['label'])}</b> by <b>{escape(dim)}</b> "
              f"({len(bd):,} value(s)):")
    html += _rank(rows, tone="violet")
    if spec["fmt"] != "pct":
        html += _kvs([("Total", _fmt_measure(measure, float(bd["value"].sum()))),
                      ("Average per value", _fmt_measure(measure, float(bd["value"].mean()))),
                      ("Values shown", f"{len(rows)} of {len(bd):,}")])
    html += _scopebar(scope)
    return Reply(html, [f"Top 5 {_plural(dim)} by revenue",
                        "How is revenue trending?", "Give me a summary"])


def _h_entity(q: str, ctx: dict, entities: list[tuple[str, str]]) -> Reply:
    scope_df, scope = _scope(q, ctx)
    col, val = entities[0]
    if col not in scope_df.columns:
        return Reply(_p(f"<code>{escape(col)}</code> is not in this dataset."), DEFAULT_CHIPS)

    sub = scope_df[scope_df[col].astype(str) == str(val)]
    if sub.empty:
        alt = ctx["df"][ctx["df"][col].astype(str) == str(val)]
        if alt.empty:
            return Reply(_p(f"I could not find <b>{escape(str(val))}</b> anywhere in "
                            f"<code>{escape(col)}</code>."), DEFAULT_CHIPS)
        return Reply(
            _p(f"<b>{escape(str(val))}</b> exists in the workbook with "
               f"<b>{len(alt):,}</b> transactions, but your current filters exclude all "
               "of them.")
            + _note("Ask again with the word <b>overall</b> to read it against the "
                    "whole dataset, or reset the sidebar filters.")
            + _scopebar(scope),
            [f"{val} overall", "What filters are active?"])

    m = DE.compute_metrics(sub)
    whole = DE.compute_metrics(scope_df)
    html = _p(f"<b>{escape(str(val))}</b> "
              f'<span class="kb-chiplbl">{escape(col)}</span> in the data in scope:')
    html += _kvs([
        ("Transactions", num(m["transactions"])),
        ("GMV", inr(m["gmv"])),
        ("Commission revenue", inr(m["revenue"])),
        ("Take rate", pct(m["take_rate"])),
        ("Avg. deal value", inr(m["avg_txn_value"])),
        ("Avg. commission", inr(m["avg_commission"])),
    ])

    shares = []
    if whole["transactions"]:
        shares.append(("Share of transactions",
                       pct(m["transactions"] / whole["transactions"] * 100)))
    if whole["gmv"]:
        shares.append(("Share of GMV", pct(m["gmv"] / whole["gmv"] * 100)))
    if whole["revenue"]:
        shares.append(("Share of revenue", pct(m["revenue"] / whole["revenue"] * 100)))
    if whole["take_rate"]:
        gap = m["take_rate"] - whole["take_rate"]
        shares.append(("Take rate vs average",
                       f"{'+' if gap >= 0 else '−'}{abs(gap):.2f} pts"))
    if shares:
        html += _kvs(shares)

    # Rank of this value inside its dimension
    bd = _breakdown(scope_df, col, "revenue")
    if not bd.empty:
        order = bd.sort_values("value", ascending=False).reset_index(drop=True)
        pos = order.index[order["label"] == str(val)]
        if len(pos):
            html += _p(f"Ranks <b>#{int(pos[0]) + 1}</b> of {len(order):,} "
                       f"{escape(col)} value(s) by commission revenue.")

    # Composition inside the entity
    detail_cols = [c for c in ("State", "Make", "Seller Segment", "Model",
                               "Seller Name", "Buyer Name") if c != col and c in sub.columns]
    for dc in detail_cols[:2]:
        inner = _breakdown(sub, dc, "revenue")
        if inner.empty or inner["label"].nunique() < 2:
            continue
        html += _p(f"Revenue mix by <b>{escape(dc)}</b>:")
        html += _rank(_rank_rows(inner, "revenue", 5, False), tone="teal")
        break

    pf = DE.period_frame(sub)
    if len(pf) >= 2:
        d = DE.latest_period_deltas(pf)
        if "revenue" in d:
            html += _p(f"Latest period <b>{escape(str(pf.iloc[-1]['Period']))}</b> "
                       f"{escape(d.get('_label', ''))}: {_delta_tag(d['revenue'], 'revenue')}")
        peak = pf.loc[pf["Revenue"].idxmax()]
        html += _note(f"Best period so far: <b>{escape(str(peak['Period']))}</b> at "
                      f"{inr(peak['Revenue'])}.")
    html += _scopebar(scope)

    chips = [f"{val} overall"] if "overall" not in q else []
    chips += ["Give me a summary", f"Top 5 {_plural(col)} by revenue"]
    return Reply(html, chips[:3])


def _h_compare(q: str, ctx: dict, entities: list[tuple[str, str]],
               measure: str | None) -> Reply:
    scope_df, scope = _scope(q, ctx)
    if scope_df.empty:
        return _h_empty(scope)

    pairs = entities[:4]
    frames: list[tuple[str, pd.DataFrame]] = []
    for col, val in pairs:
        if col in scope_df.columns:
            frames.append((f"{val}", scope_df[scope_df[col].astype(str) == str(val)]))
    frames = [(lbl, f) for lbl, f in frames if not f.empty]
    if len(frames) < 2:
        return _h_entity(q, ctx, entities) if entities else _h_summary(q, ctx)

    rows_spec = [("Transactions", "transactions", num),
                 ("GMV", "gmv", inr),
                 ("Revenue", "revenue", inr),
                 ("Take rate", "take_rate", pct),
                 ("Avg. deal value", "avg_txn_value", inr),
                 ("Avg. commission", "avg_commission", inr)]
    mets = [(lbl, DE.compute_metrics(f)) for lbl, f in frames]

    head = "".join(f"<th>{escape(lbl)}</th>" for lbl, _ in mets)
    body = ""
    for i, (rl, key, fn) in enumerate(rows_spec):
        vals = [mm[key] for _, mm in mets]
        best = max(range(len(vals)), key=lambda j: vals[j]) if any(vals) else -1
        cells = "".join(
            f'<td class="{"kb-best" if j == best else ""}">{fn(v)}</td>'
            for j, v in enumerate(vals))
        body += f'<tr style="--i:{i}"><th>{escape(rl)}</th>{cells}</tr>'
    html = (_p("Side by side on the data in scope — the stronger figure in each row is "
               "highlighted:")
            + f'<div class="kb-tbl"><table><tr><th></th>{head}</tr>{body}</table></div>')

    if len(mets) == 2:
        (la, ma), (lb, mb) = mets
        notes = []
        for lbl, key, fn in (("revenue", "revenue", inr), ("GMV", "gmv", inr),
                             ("transactions", "transactions", num)):
            if mb[key]:
                gap = (ma[key] - mb[key]) / mb[key] * 100
                lead = la if gap >= 0 else lb
                notes.append(f"<b>{escape(lead)}</b> is ahead on {lbl} by "
                             f"{abs(gap):.1f}% ({fn(ma[key])} vs {fn(mb[key])}).")
        tr = ma["take_rate"] - mb["take_rate"]
        notes.append(f"Take-rate gap is <b>{abs(tr):.2f} pts</b> in favour of "
                     f"<b>{escape(la if tr >= 0 else lb)}</b>.")
        html += _bullets(notes)
    html += _scopebar(scope)
    return Reply(html, ["Give me a summary", "How is revenue trending?"])


def _h_trend(q: str, ctx: dict, measure: str | None) -> Reply:
    scope_df, scope = _scope(q, ctx)
    if scope_df.empty:
        return _h_empty(scope)
    measure = measure or "revenue"
    spec = MEASURES[measure]
    pf = DE.period_frame(scope_df)
    if pf.empty:
        return Reply(_p("There is no FY / Month information to build a timeline from.")
                     + _scopebar(scope), DEFAULT_CHIPS)
    col = spec["pf"]

    # Year on year
    if _has(q, "year on year", "yoy", "yearly", "annual", "financial year",
            "fy comparison", "compare years", "by year") and pf["FY"].nunique() > 1:
        bd = _breakdown(scope_df, "FY", measure)
        rows = [(r["label"], _fmt_measure(measure, r["value"]),
                 abs(r["value"]) / (float(bd["value"].abs().max()) or 1) * 100)
                for _, r in bd.sort_values("label").iterrows()]
        html = _p(f"<b>{escape(spec['label'])}</b> by financial year:") + _rank(rows, tone="violet")
        srt = bd.sort_values("label").reset_index(drop=True)
        moves = []
        for i in range(1, len(srt)):
            prev, cur = srt.loc[i - 1, "value"], srt.loc[i, "value"]
            if prev:
                moves.append(f"{escape(str(srt.loc[i, 'label']))} vs "
                             f"{escape(str(srt.loc[i - 1, 'label']))}: "
                             f"{_delta_tag((cur - prev) / prev * 100)}")
        if moves:
            html += _bullets(moves)
        html += _scopebar(scope)
        return Reply(html, ["How is revenue trending?", "Which is the best month?"])

    # Best / worst period
    if _has(q, "best month", "best period", "peak", "highest month", "strongest month",
            "top month", "worst month", "weakest month", "lowest month", "worst period"):
        low = _has(q, "worst month", "weakest month", "lowest month", "worst period",
                   "slowest")
        valid = pf.dropna(subset=[col])
        if valid.empty:
            return Reply(_p("That measure has no values across the periods in scope.")
                         + _scopebar(scope), DEFAULT_CHIPS)
        pick = valid.loc[valid[col].idxmin() if low else valid[col].idxmax()]
        word = "weakest" if low else "strongest"
        html = (_p(f"The {word} period for <b>{escape(spec['short'])}</b> is "
                   f"<b>{escape(str(pick['Period']))}</b> at "
                   f"<b>{_fmt_measure(measure, pick[col])}</b>.")
                + _kvs([("Transactions", num(pick["Transactions"])),
                        ("GMV", inr(pick["GMV"])),
                        ("Revenue", inr(pick["Revenue"])),
                        ("Take rate", pct(pick["TakeRate"])),
                        ("Sellers active", num(pick["Sellers"])),
                        ("Buyers active", num(pick["Buyers"]))]))
        order = valid.sort_values(col, ascending=low).reset_index(drop=True)
        peak = float(order[col].abs().max()) or 1.0
        html += _p(f"{'Weakest' if low else 'Strongest'} periods in order:")
        html += _rank([(r["Period"], _fmt_measure(measure, r[col]),
                        abs(r[col]) / peak * 100)
                       for _, r in order.head(6).iterrows()],
                      tone="rose" if low else "jade")
        html += _scopebar(scope)
        return Reply(html, ["Which is the worst month?" if not low else "Which is the best month?",
                            "How is revenue trending?", "Revenue by month"])

    # Momentum
    d = DE.latest_period_deltas(pf)
    valid = pf.dropna(subset=[col])
    html = _p(f"<b>{escape(spec['label'])}</b> across the last "
              f"{min(8, len(valid))} of {len(pf)} period(s):")
    tail = valid.tail(8)
    peak = float(tail[col].abs().max()) or 1.0
    html += _rank([(r["Period"], _fmt_measure(measure, r[col]),
                    abs(r[col]) / peak * 100) for _, r in tail.iterrows()],
                  tone="jade")

    if d and measure in d:
        v = d[measure]
        direction = "grew" if v > 0 else ("declined" if v < 0 else "held flat")
        html += _p(f"Latest period <b>{escape(str(pf.iloc[-1]['Period']))}</b> "
                   f"{direction} {_delta_tag(v, escape(d.get('_label', '')))}")
    if d:
        tags = "".join(f'<span class="kb-mv">{escape(lbl)} {_delta_tag(d[k])}</span>'
                       for k, lbl in (("revenue", "Revenue"), ("gmv", "GMV"),
                                      ("transactions", "Deals"),
                                      ("take_rate", "Take rate"),
                                      ("avg_commission", "Avg. comm."))
                       if k in d)
        if tags:
            html += f'<div class="kb-mvs">{tags}</div>'

    if len(valid) >= 3:
        first, last = float(valid.iloc[0][col]), float(valid.iloc[-1][col])
        if first:
            total_growth = (last - first) / first * 100
            html += _note(f"From {escape(str(valid.iloc[0]['Period']))} to "
                          f"{escape(str(valid.iloc[-1]['Period']))} the measure moved "
                          f"{signed_pct(total_growth)} overall, averaging "
                          f"{_fmt_measure(measure, float(valid[col].mean()))} per period.")
        best = valid.loc[valid[col].idxmax()]
        worst = valid.loc[valid[col].idxmin()]
        html += _note(f"Peak {escape(str(best['Period']))} "
                      f"({_fmt_measure(measure, best[col])}) · trough "
                      f"{escape(str(worst['Period']))} "
                      f"({_fmt_measure(measure, worst[col])}).")
    html += _scopebar(scope)
    return Reply(html, ["Which is the best month?", "Year on year comparison",
                        "Transactions by month"])


def _h_concentration(q: str, ctx: dict, entities: list[tuple[str, str]]) -> Reply:
    scope_df, scope = _scope(q, ctx)
    if scope_df.empty:
        return _h_empty(scope)
    dims = _find_dims(q)
    dim = next((d for d in dims if d in ("Seller Name", "Buyer Name", "State",
                                         "Make", "Model")), None)
    if dim is None:
        dim = "Seller Name" if "Seller Name" in scope_df.columns else "State"
    if dim not in scope_df.columns:
        return Reply(_p(f"<code>{escape(dim)}</code> is not in this dataset."), DEFAULT_CHIPS)

    bd = _breakdown(scope_df, dim, "gmv").sort_values("value", ascending=False)
    if bd.empty:
        return Reply(_p("Not enough values to measure concentration.") + _scopebar(scope),
                     DEFAULT_CHIPS)
    total = float(bd["value"].sum()) or 1.0
    n = len(bd)
    cum = bd["value"].cumsum() / total * 100

    def share(k: int) -> float:
        return float(cum.iloc[min(k, n) - 1]) if n else 0.0

    top1, top3, top5, top10 = share(1), share(3), share(5), share(10)
    need_80 = int((cum < 80).sum()) + 1
    verdict = ("heavily concentrated — a handful of accounts carry the business"
               if top5 > 60 else
               "moderately concentrated — worth watching" if top5 > 40 else
               "healthily spread")

    html = (_p(f"GMV concentration across <b>{n:,}</b> {escape(dim)} value(s) — "
               f"{verdict}.")
            + _rank([("Top 1", pct(top1), top1), ("Top 3", pct(top3), top3),
                     ("Top 5", pct(top5), top5), ("Top 10", pct(top10), top10)],
                    tone="amber" if top5 > 40 else "jade")
            + _p(f"<b>{need_80:,}</b> of {n:,} "
                 f"({need_80 / n * 100:.1f}%) account for the first 80% of GMV.")
            + _p("The names behind it:")
            + _rank(_rank_rows(bd, "gmv", 6, False), tone="jade"))
    tail = bd.tail(max(1, n // 2))
    html += _note(f"The bottom half ({len(tail):,} values) contributes "
                  f"{float(tail['value'].sum()) / total * 100:.1f}% of GMV.")
    html += _scopebar(scope)
    return Reply(html, [f"Top 10 {_plural(dim)} by GMV",
                        "How concentrated is demand?", "Give me a summary"])


def _h_repeat(q: str, ctx: dict) -> Reply:
    scope_df, scope = _scope(q, ctx)
    if scope_df.empty:
        return _h_empty(scope)
    dim = "Seller Name" if _has(q, "seller", "sellers", "supply", "supplier") else "Buyer Name"
    if dim not in scope_df.columns:
        return Reply(_p(f"<code>{escape(dim)}</code> is not in this dataset."), DEFAULT_CHIPS)
    counts = scope_df[dim].dropna().value_counts()
    if counts.empty:
        return Reply(_p("No accounts to analyse in this selection.") + _scopebar(scope),
                     DEFAULT_CHIPS)
    total = len(counts)
    repeat = int((counts > 1).sum())
    once = total - repeat
    heavy = int((counts >= 5).sum())
    word = "purchases" if dim == "Buyer Name" else "deals"

    html = (_p(f"Repeat behaviour across <b>{total:,}</b> {escape(dim)} account(s):")
            + _kvs([("One-off", f"{once:,} ({once / total * 100:.1f}%)"),
                    ("Returned", f"{repeat:,} ({repeat / total * 100:.1f}%)"),
                    (f"5+ {word}", f"{heavy:,}"),
                    (f"Avg. {word} each", f"{counts.mean():.2f}"),
                    ("Busiest account", f"{int(counts.iloc[0]):,} {word}"),
                    ("Median", f"{counts.median():.0f}")]))
    buckets = [("1", int((counts == 1).sum())), ("2", int((counts == 2).sum())),
               ("3–4", int(counts.between(3, 4).sum())),
               ("5–9", int(counts.between(5, 9).sum())),
               ("10+", int((counts >= 10).sum()))]
    peak = max((c for _, c in buckets), default=1) or 1
    html += _p(f"Distribution of {word} per account:")
    html += _rank([(f"{b} {word}", f"{c:,} accounts", c / peak * 100)
                   for b, c in buckets if c], tone="teal")
    html += _p("Most active accounts:")
    html += _rank([(str(k), f"{int(v):,} {word}", v / float(counts.iloc[0]) * 100)
                   for k, v in counts.head(5).items()], tone="violet")
    html += _note("A high one-off share means growth depends on constant new "
                  "acquisition rather than on the accounts you already have.")
    html += _scopebar(scope)
    return Reply(html, ["How concentrated is demand?",
                        "Top 10 buyers by GMV", "Give me a summary"])


def _h_bands(q: str, ctx: dict) -> Reply:
    scope_df, scope = _scope(q, ctx)
    if scope_df.empty:
        return _h_empty(scope)

    if _has(q, "odometer", "kilometre", "kilometer", "km", "mileage", "usage",
            "age", "vehicle age", "old", "year of manufacture", "manufacture year"):
        rows: list[tuple[str, str]] = []
        html = ""
        if "Odometer" in scope_df.columns and scope_df["Odometer"].notna().any():
            o = scope_df["Odometer"].dropna()
            rows += [("Median odometer", f"{o.median():,.0f} km"),
                     ("Mean odometer", f"{o.mean():,.0f} km"),
                     ("25th – 75th pct",
                      f"{o.quantile(.25):,.0f} – {o.quantile(.75):,.0f} km")]
        if "Year" in scope_df.columns and scope_df["Year"].notna().any():
            y = scope_df["Year"].dropna()
            rows += [("Model years", f"{int(y.min())} – {int(y.max())}"),
                     ("Median model year", f"{int(y.median())}")]
        if not rows:
            return Reply(_p("This dataset carries neither <code>Odometer</code> nor "
                            "<code>Year</code>, so I cannot describe vehicle condition.")
                         + _scopebar(scope), DEFAULT_CHIPS)
        html += _p("Vehicle condition in scope:") + _kvs(rows)
        if {"Year", "Final Bid Value"} <= set(scope_df.columns):
            tmp = scope_df.dropna(subset=["Year", "Final Bid Value"]).copy()
            if not tmp.empty:
                tmp["Age"] = pd.Timestamp.now().year - tmp["Year"]
                grp = tmp.groupby(pd.cut(tmp["Age"], [-1, 2, 5, 8, 12, 100],
                                         labels=["0–2 yr", "3–5 yr", "6–8 yr",
                                                 "9–12 yr", "12 yr+"]),
                                  observed=False)["Final Bid Value"].agg(["mean", "size"])
                grp = grp[grp["size"] > 0]
                if not grp.empty:
                    peak = float(grp["mean"].max()) or 1.0
                    html += _p("Average winning bid by vehicle age:")
                    html += _rank([(str(i), f"{inr(r['mean'])} · {int(r['size']):,} deals",
                                    r["mean"] / peak * 100)
                                   for i, r in grp.iterrows()], tone="amber")
                    html += _note("Older stock trades lower — the gradient here is the "
                                  "depreciation the marketplace is actually pricing in.")
        html += _scopebar(scope)
        return Reply(html, ["Which price band yields most?", "Top 5 makes by GMV"])

    bands = DE.price_bands(scope_df)
    if bands.empty:
        return Reply(_p("No bid values to band in this selection.") + _scopebar(scope),
                     DEFAULT_CHIPS)
    b = bands[bands["Transactions"] > 0].copy()
    if b.empty:
        return Reply(_p("Every price band is empty in this selection.") + _scopebar(scope),
                     DEFAULT_CHIPS)

    peak_t = float(b["Transactions"].max()) or 1.0
    peak_r = float(b["Revenue"].max()) or 1.0
    best = b.loc[b["TakeRate"].idxmax()] if b["TakeRate"].notna().any() else None
    busiest = b.loc[b["Transactions"].idxmax()]

    html = _p("Volume by price band:")
    html += _rank([(str(r["Band"]), f"{int(r['Transactions']):,} deals",
                    r["Transactions"] / peak_t * 100) for _, r in b.iterrows()],
                  tone="jade")
    html += _p("Commission revenue by price band:")
    html += _rank([(str(r["Band"]), inr(r["Revenue"]), r["Revenue"] / peak_r * 100)
                   for _, r in b.iterrows()], tone="amber")
    if best is not None:
        html += _p("Take rate by price band:")
        html += _rank([(str(r["Band"]), pct(r["TakeRate"]),
                        (r["TakeRate"] / float(b["TakeRate"].max()) * 100)
                        if pd.notna(r["TakeRate"]) else 0)
                       for _, r in b.iterrows()], tone="violet")
        html += _bullets([
            f"Yield is best in <b>{escape(str(best['Band']))}</b> at "
            f"<b>{best['TakeRate']:.2f}%</b>.",
            f"Volume clusters in <b>{escape(str(busiest['Band']))}</b> with "
            f"<b>{int(busiest['Transactions']):,}</b> deals.",
            ("Those are the same band, so the busiest band is also the most profitable "
             "one — no trade-off to manage."
             if str(best["Band"]) == str(busiest["Band"]) else
             "They differ: the busiest band is not the most profitable one, so there "
             "is mix to shift."),
        ])
    html += _scopebar(scope)
    return Reply(html, ["Top 5 makes by GMV", "Odometer and vehicle age",
                        "Give me a summary"])


def _h_metric_total(q: str, ctx: dict, measure: str) -> Reply:
    scope_df, scope = _scope(q, ctx)
    if scope_df.empty:
        return _h_empty(scope)
    spec = MEASURES[measure]
    v = _total(scope_df, measure)
    pf = DE.period_frame(scope_df)
    d = DE.latest_period_deltas(pf)

    html = _p(f"<b>{escape(spec['label'])}</b> on the data in scope:")
    html += f'<div class="kb-big">{_fmt_measure(measure, v)}</div>'
    if measure in d:
        html += _p(f"Latest period {escape(d.get('_label', ''))}: "
                   f"{_delta_tag(d[measure])}")

    m = DE.compute_metrics(scope_df)
    context_rows = [("Transactions", num(m["transactions"]))]
    if measure != "gmv":
        context_rows.append(("GMV", inr(m["gmv"])))
    if measure != "revenue":
        context_rows.append(("Commission revenue", inr(m["revenue"])))
    if measure != "take_rate":
        context_rows.append(("Take rate", pct(m["take_rate"])))
    if measure != "avg_bid":
        context_rows.append(("Avg. deal value", inr(m["avg_txn_value"])))
    if measure != "avg_commission":
        context_rows.append(("Avg. commission", inr(m["avg_commission"])))
    html += _kvs(context_rows[:6])

    if not pf.empty and spec["pf"] in pf.columns:
        tail = pf.dropna(subset=[spec["pf"]]).tail(6)
        if len(tail) >= 2:
            peak = float(tail[spec["pf"]].abs().max()) or 1.0
            html += _p("Recent periods:")
            html += _rank([(r["Period"], _fmt_measure(measure, r[spec["pf"]]),
                            abs(r[spec["pf"]]) / peak * 100)
                           for _, r in tail.iterrows()], tone="teal")

    for dim in ("State", "Seller Segment", "Make"):
        if dim in scope_df.columns and scope_df[dim].nunique(dropna=True) > 1:
            bd = _breakdown(scope_df, dim, measure)
            if not bd.empty:
                html += _p(f"Biggest contributors by <b>{escape(dim)}</b>:")
                html += _rank(_rank_rows(bd, measure, 4, False), tone="violet")
            break

    # Carrying the definition here is what lets the router send a bare
    # "what is take rate" to this handler without losing the explanation.
    formula, meaning = _definition_of(spec["label"])
    html += _note(f"Formula <code>{escape(formula)}</code>"
                  + (f" — {escape(meaning)}" if meaning else ""))
    html += _scopebar(scope)
    return Reply(html, [f"{spec['short'].capitalize()} by month",
                        f"Top 5 states by {spec['short']}",
                        "Give me a summary"])


def _definition_of(label: str) -> tuple[str, str]:
    """Look up (formula, interpretation) for a metric label."""
    # MEASURES labels and METRIC_DEFINITIONS names differ only in casing, and
    # _key() keeps the abbreviating full stop, so one normalised compare is enough.
    want = _key(label)
    for name, formula, meaning in DE.METRIC_DEFINITIONS:
        if _key(name) == want:
            return formula, meaning
    return "see the metric dictionary in the Data Quality & SSOT tab", ""


def _h_empty(scope: str) -> Reply:
    return Reply(
        _p("Nothing matches the current selection, so every figure would read zero.")
        + _note("Widen the sidebar filters, press <b>↺ Reset filters</b>, or add the "
                "word <b>overall</b> to your question and I will read the whole "
                "workbook instead.")
        + _scopebar(scope),
        ["What filters are active?", "Give me a summary overall"])


def _h_fallback(q: str, ctx: dict, measure: str | None, dims: list[str]) -> Reply:
    df = ctx["df"]
    guesses: list[str] = []
    if measure:
        guesses.append(f"the measure <b>{escape(MEASURES[measure]['label'])}</b>")
    if dims:
        guesses.append("the dimension <b>" + escape(dims[0]) + "</b>")

    html = _p("I could not pin that question to something in this dataset.")
    if guesses:
        html += _p("I did pick up " + " and ".join(guesses)
                   + " — try phrasing it as a ranking or a total, "
                     "for example “top 5 states by revenue” or “total revenue”.")
    html += _p("What I can work with:")
    html += _bullets([
        "<b>Measures</b> — revenue, GMV, transactions, take rate, avg deal value, "
        "avg commission",
        "<b>Dimensions</b> — " + ", ".join(
            escape(d) for d in _DIM_ORDER if d in df.columns or d == "Period"),
        "<b>Shapes</b> — totals, top / bottom N, breakdowns, comparisons, trends, "
        "concentration, price bands, data quality, definitions",
    ])
    html += _note("Names work directly too: type a state, seller, buyer, make or model "
                  "and I will profile it.")
    return Reply(html, ["What can you do?", "Give me a summary",
                        "Top 5 states by revenue"])


# ═════════════════════════════════════════════════════════════════════════════
# ROUTER
# ═════════════════════════════════════════════════════════════════════════════
_RANK_WORDS = ("top", "bottom", "best", "worst", "highest", "lowest", "biggest",
               "largest", "smallest", "leading", "leaders", "rank", "ranking",
               "ranked", "strongest", "weakest", "most", "least", "who are the",
               "which are the")

_TREND_WORDS = ("trend", "trending", "trajectory", "momentum", "growth", "growing",
                "grew", "declining", "decline", "declined", "falling", "rising",
                "month on month", "mom", "over time", "year on year", "yoy",
                "best month", "worst month", "best period", "worst period",
                "seasonality", "seasonal", "peak", "trough", "how is it going",
                "improving", "slowing")

_QUALITY_WORDS = ("data quality", "quality", "clean", "cleanliness", "healthy",
                  "health", "trustworthy", "trust the data", "reliable", "ssot",
                  "single source of truth", "duplicate", "duplicates", "missing",
                  "nulls", "null", "blank", "blanks", "completeness", "outlier",
                  "outliers", "anomaly", "anomalies", "validity", "valid",
                  "invalid", "consistency", "consistent", "variants", "audit",
                  "integrity")

_DEF_WORDS = ("what is", "what does", "define", "definition", "meaning", "means",
              "how is it calculated", "how is", "how do you calculate",
              "calculated", "formula", "explain", "what do you mean by",
              "difference between")

_HOWTO_WORDS = ("how do i", "how can i", "how to", "where do i", "where can i",
                "where is", "upload", "export", "download", "dark mode",
                "light mode", "theme", "tabs", "navigate", "reset filters")

_HELP_WORDS = ("what can you do", "who are you", "what are you", "help",
               "capabilities", "commands", "how do you work", "what do you know",
               "examples", "what can i ask")

_SUMMARY_WORDS = ("summary", "summarise", "summarize", "overview", "snapshot",
                  "headline", "kpi", "kpis", "how are we doing", "how is business",
                  "brief me", "tell me about the data", "the big picture",
                  "executive summary", "recap", "status")

_CONC_WORDS = ("concentration", "concentrated", "pareto", "80/20", "80 20",
               "dependency", "dependence", "reliance", "risk of losing",
               "how spread", "spread out", "diversified", "diversification",
               "share of gmv", "top 5 share")

_REPEAT_WORDS = ("repeat", "repeating", "returning", "retention", "loyal",
                 "loyalty", "churn", "one off", "one-off", "come back",
                 "purchases per buyer", "frequency", "how often")

_BAND_WORDS = ("price band", "price bands", "bands", "banding", "price range",
               "price ranges", "distribution of price", "price segment",
               "odometer", "mileage", "kilometre", "kilometer", "vehicle age",
               "how old", "model year", "depreciation")

_FILTER_WORDS = ("what filters", "which filters", "filters active",
                 "active filters", "current selection", "what is selected",
                 "in scope", "what am i looking at", "current view",
                 "applied filters")

_COVERAGE_WORDS = ("columns", "column", "fields", "schema", "structure",
                   "what data", "which data", "coverage", "period covered",
                   "periods covered", "what period", "which periods",
                   "does the data cover", "data cover", "time period",
                   "time frame", "timeframe", "how far back", "date range",
                   "how many records", "how many rows",
                   "how many transactions", "how many states", "how many sellers",
                   "how many buyers", "how many makes", "how many models",
                   "which states", "what states", "source", "where does the data",
                   "how many", "distinct", "unique", "template", "required columns")

_COMPARE_WORDS = ("compare", "comparison", "compared", "versus", "vs", "vs.",
                  "against", "better than", "difference between", "side by side")

_DEF_CUES = ("define", "definition", "definitions", "formula", "formulas",
             "calculated", "calculate", "meaning", "means", "metric dictionary",
             "every metric", "all metrics", "metric definitions",
             "what do you mean by", "how is it worked out")

# Every word this module assigns a meaning to. Used to keep the approximate
# name matcher away from vocabulary it should never treat as a name.
_RESERVED: frozenset[str] = frozenset(
    tok
    for group in (
        *(m["words"] for m in MEASURES.values()),
        *DIMENSIONS.values(),
        _RANK_WORDS, _TREND_WORDS, _QUALITY_WORDS, _DEF_WORDS, _HOWTO_WORDS,
        _HELP_WORDS, _SUMMARY_WORDS, _CONC_WORDS, _REPEAT_WORDS, _BAND_WORDS,
        _FILTER_WORDS, _COVERAGE_WORDS, _COMPARE_WORDS, _DEF_CUES,
        _ALL_DATA_WORDS, GREETINGS,
        ("what", "which", "who", "where", "when", "why", "how", "the", "and",
         "for", "with", "from", "this", "that", "give", "show", "tell", "about",
         "please", "there", "here", "does", "data", "dashboard", "report",
         "number", "numbers", "figure", "figures", "total", "totals", "much",
         "many", "share", "percent", "percentage", "average", "avg", "mean",
         "median", "value", "values", "amount", "period", "periods"),
    )
    for phrase in group
    for tok in phrase.split()
)


def _route(raw: str, q: str, ctx: dict) -> Reply:
    df = ctx["df"]
    words = _words(q)
    measure = _find_measure(q)
    dims = _find_dims(q)
    entities = _scan_entities(df, q)
    # Approximate name matching is a last resort for a short question that named
    # nothing this module recognises — otherwise it hijacks perfectly clear
    # questions by pairing a keyword with a similar-looking record.
    if not entities and not measure and not dims and len(words) <= 5:
        fz = _fuzzy_entity(df, q)
        if fz:
            entities = [fz]

    # 1 · greeting on its own
    if len(words) <= 3 and any(w in GREETINGS for w in words) and not measure and not dims:
        return _h_greeting(ctx)

    # 2 · capabilities
    if _has(q, *_HELP_WORDS) and not measure:
        return _h_help(ctx)

    # 3 · definitions — only on an explicit cue. A bare "what is take rate" is
    #     answered with the live number instead, which carries the formula and
    #     the interpretation with it, so nothing is lost either way.
    if _has(q, *_DEF_CUES) and not _has(q, *_RANK_WORDS):
        return _h_definition(q, ctx)

    # 4 · using the dashboard
    if _has(q, *_HOWTO_WORDS) and not _has(q, *_RANK_WORDS):
        return _h_howto(q, ctx)

    # 5 · data quality
    if _has(q, *_QUALITY_WORDS):
        return _h_quality(q, ctx)

    # 6 · what am I looking at
    if _has(q, *_FILTER_WORDS):
        return _h_filters(q, ctx)

    # 7 · schema and coverage
    if _has(q, *_COVERAGE_WORDS) and not _has(q, *_RANK_WORDS) and not entities:
        return _h_coverage(q, ctx)

    # 8 · two things named side by side
    if len(entities) >= 2:
        return _h_compare(q, ctx, entities, measure)

    # 9 · concentration and dependency
    if _has(q, *_CONC_WORDS):
        return _h_concentration(q, ctx, entities)

    # 10 · repeat behaviour
    if _has(q, *_REPEAT_WORDS):
        return _h_repeat(q, ctx)

    # 11 · price bands, odometer, age
    if _has(q, *_BAND_WORDS):
        return _h_bands(q, ctx)

    # 12 · trends — ahead of the dimension comparison below, so "year on year"
    #      reads as a timeline rather than as two columns side by side
    if _has(q, *_TREND_WORDS):
        return _h_trend(q, ctx, measure)

    # 12b · compare every value of a small dimension ("captive vs non-captive")
    if _has(q, *_COMPARE_WORDS):
        col = next((d for d in dims if d in df.columns), None)
        if col:
            vals = df[col].dropna().unique().tolist()
            if 2 <= len(vals) <= 4:
                return _h_compare(q, ctx, [(col, v) for v in vals], measure)
        if entities:
            return _h_entity(q, ctx, entities)

    # 13 · rankings
    if _has(q, *_RANK_WORDS):
        dim = next((d for d in dims if d in df.columns), None)
        if dim is None and entities:
            hinted = [c for c, _ in entities]
            dim = next((d for d in _DIM_ORDER
                        if d in df.columns and d not in hinted), None)
        if dim is None:
            dim = "Seller Name" if "Seller Name" in df.columns else "State"
        if dim == "Period":
            return _h_trend(q, ctx, measure)
        return _h_ranking(q, ctx, dim, measure or "revenue", entities)

    # 14 · explicit breakdown ("revenue by state")
    if dims and (measure or _has(q, "by", "per", "split", "breakdown", "break down",
                                 "across", "distribution")):
        if dims[0] == "Period" and not measure:
            return _h_coverage(q, ctx)
        dim = next((d for d in dims if d in df.columns), None)
        if dims[0] == "Period" or (dim in ("Month", "FY") and _has(q, "trend", "trending")):
            return _h_trend(q, ctx, measure)
        if dim:
            return _h_breakdown(q, ctx, dim, measure or "revenue")

    # 14b · a timeline question with no other handle ("what period is covered")
    if dims and dims[0] == "Period":
        return _h_coverage(q, ctx) if not measure else _h_trend(q, ctx, measure)

    # 15 · a named thing
    if entities:
        return _h_entity(q, ctx, entities)

    # 16 · a plain measure question
    if measure:
        return _h_metric_total(q, ctx, measure)

    # 17 · broad summary
    if _has(q, *_SUMMARY_WORDS) or len(words) <= 2:
        return _h_summary(q, ctx)

    return _h_fallback(q, ctx, measure, dims)


# ═════════════════════════════════════════════════════════════════════════════
# PUBLIC ENTRY
# ═════════════════════════════════════════════════════════════════════════════
def answer(question: str, ctx: dict) -> Reply:
    """Answer ``question`` against ``ctx``; never raises."""
    q = _norm(question)
    if not q:
        return _h_help(ctx)

    df = ctx.get("df")
    if df is None or getattr(df, "empty", True):
        return Reply(
            _p("No dataset is loaded yet, so there is nothing for me to read.")
            + _note("Open the <b>⤒ Upload Data</b> tab and load a conversion workbook, "
                    "or drop one next to <code>app.py</code>."),
            ["How do I upload data?", "What columns are required?"])

    try:
        return _route(question, q, ctx)
    except Exception as exc:                                      # noqa: BLE001
        return Reply(
            _p("I could not finish that one — the calculation raised "
               f"<code>{escape(type(exc).__name__)}</code>.")
            + _note(escape(str(exc)[:200]))
            + _p("Try a narrower phrasing, for example "
                 "“top 5 states by revenue” or “total commission revenue”."),
            ["What can you do?", "Give me a summary"])


def opening_message(ctx: dict) -> Reply:
    """First bubble shown when the panel is opened for the first time."""
    return _h_greeting(ctx)
