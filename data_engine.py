"""
Data loading, normalisation and quality profiling for the Conversion dashboard.

Keeps all business logic out of the UI layer so metric definitions live in
exactly one place (the SSOT principle the dashboard reports on).
"""
from __future__ import annotations

import glob
import os
import re
import unicodedata

import numpy as np
import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
# CANONICAL SCHEMA
# ─────────────────────────────────────────────────────────────────────────────
MONTH_ORDER = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTH_INDEX = {m: i for i, m in enumerate(MONTH_ORDER)}

DIM_COLS = ["FY", "Month", "State", "Vehicle Number", "Make", "Model",
            "Seller Name", "Seller Segment", "Buyer Name"]
NUM_COLS = ["Year", "Odometer", "Final Bid Value", "Total Income"]
REQUIRED_COLUMNS = DIM_COLS + NUM_COLS

# Canonical metric definitions surfaced in the SSOT tab.
METRIC_DEFINITIONS = [
    ("Transactions", "COUNT of rows", "One row = one converted vehicle."),
    ("GMV", "SUM(Final Bid Value)", "Gross merchandise value at winning bid."),
    ("Commission Revenue", "SUM(Total Income)", "Platform income, excluding GST."),
    ("Avg. Commission", "SUM(Total Income) / Transactions", "Mean income per transaction."),
    ("Take Rate", "SUM(Total Income) / SUM(Final Bid Value)", "Revenue captured per rupee of GMV."),
    ("Avg. Transaction Value", "SUM(Final Bid Value) / Transactions", "Mean winning bid."),
    ("Unique Sellers", "DISTINCT COUNT(Seller Name)", "Distinct supply accounts."),
    ("Avg. Transactions / Seller", "Transactions / Unique Sellers", "Supply-side depth."),
    ("Unique Buyers", "DISTINCT COUNT(Buyer Name)", "Distinct demand accounts."),
    ("Avg. Purchases / Buyer", "Transactions / Unique Buyers", "Demand-side repeat rate."),
]

# Plausible ranges used by the validity checks.
VALID_RULES = {
    "Final Bid Value": (1_000, 50_000_000),
    "Total Income": (0, 5_000_000),
    "Odometer": (0, 1_000_000),
    "Year": (1980, 2035),
}

_MONTH_ALIASES = {
    "jan": "Jan", "january": "Jan", "feb": "Feb", "february": "Feb",
    "mar": "Mar", "march": "Mar", "apr": "Apr", "april": "Apr",
    "may": "May", "jun": "Jun", "june": "Jun", "jul": "Jul", "july": "Jul",
    "aug": "Aug", "august": "Aug", "sep": "Sep", "sept": "Sep", "september": "Sep",
    "oct": "Oct", "october": "Oct", "nov": "Nov", "november": "Nov",
    "dec": "Dec", "december": "Dec",
}


# ─────────────────────────────────────────────────────────────────────────────
# LOADING
# ─────────────────────────────────────────────────────────────────────────────
def _clean_text(s: pd.Series) -> pd.Series:
    """Collapse whitespace and strip non-printing characters."""
    return (s.astype("string")
             .str.replace(r"\s+", " ", regex=True)
             .str.strip())


def _find_header_row(raw: pd.DataFrame, max_scan: int = 12) -> int | None:
    """Locate the row index that holds the column headers."""
    targets = {"fy", "month", "state", "final bid value", "seller name", "buyer name"}
    best_row, best_hits = None, 0
    for i in range(min(max_scan, len(raw))):
        vals = {str(v).strip().lower() for v in raw.iloc[i].tolist() if pd.notna(v)}
        hits = len(targets & vals)
        if hits > best_hits:
            best_row, best_hits = i, hits
    return best_row if best_hits >= 3 else None


def parse_workbook(source) -> tuple[pd.DataFrame | None, list[str]]:
    """
    Parse a conversion-data workbook from a path or a bytes buffer.

    Returns (dataframe, notes). ``notes`` records the normalisations applied so
    they can be shown to the user instead of happening silently.
    """
    notes: list[str] = []
    try:
        raw = pd.read_excel(source, sheet_name=0, header=None)
    except Exception as exc:                                    # noqa: BLE001
        return None, [f"Could not read the workbook: {exc}"]

    hdr = _find_header_row(raw)
    if hdr is None:
        return None, ["Could not locate a header row containing FY / Month / State. "
                      "Check that the first sheet matches the expected template."]
    if hdr:
        notes.append(f"Header detected on row {hdr + 1}; {hdr} banner row(s) skipped.")

    df = raw.iloc[hdr + 1:].copy()
    df.columns = [str(c).strip() for c in raw.iloc[hdr].tolist()]

    # Drop unnamed / empty spacer columns
    drop = [c for c in df.columns if c in ("nan", "None", "") or c.startswith("Unnamed")]
    if drop:
        df = df.drop(columns=drop)
        notes.append(f"Dropped {len(drop)} unnamed spacer column(s).")

    df = df.loc[:, ~df.columns.duplicated()]
    df = df.dropna(how="all").reset_index(drop=True)

    # Text normalisation
    for col in DIM_COLS:
        if col in df.columns:
            df[col] = _clean_text(df[col])

    # Month canonicalisation (handles 'jan', 'JAN', ' Jan ')
    if "Month" in df.columns:
        before = df["Month"].copy()
        df["Month"] = (df["Month"].str.lower()
                                  .map(_MONTH_ALIASES)
                                  .fillna(df["Month"]))
        changed = int((before.fillna("") != df["Month"].fillna("")).sum())
        if changed:
            notes.append(f"Standardised {changed} month value(s) to Title case (e.g. 'JAN' → 'Jan').")

    # FY canonicalisation
    if "FY" in df.columns:
        df["FY"] = df["FY"].str.upper().str.replace(r"\s+", "", regex=True)

    # Vehicle number canonicalisation
    if "Vehicle Number" in df.columns:
        df["Vehicle Number"] = (df["Vehicle Number"].str.upper()
                                .str.replace(r"[^A-Z0-9]", "", regex=True))

    # Make canonicalisation (source mixes 'Volkswagen' and 'MARUTI SUZUKI')
    if "Make" in df.columns:
        before = df["Make"].copy()
        df["Make"] = df["Make"].str.upper()
        if int((before.fillna("") != df["Make"].fillna("")).sum()):
            notes.append("Standardised vehicle Make casing to UPPER CASE.")

    # Numerics
    for col in NUM_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Rows must have the grain keys to be usable
    grain = [c for c in ("FY", "Month", "State") if c in df.columns]
    if grain:
        n0 = len(df)
        df = df.dropna(subset=grain, how="any").reset_index(drop=True)
        if n0 - len(df):
            notes.append(f"Removed {n0 - len(df)} row(s) missing FY / Month / State.")

    # Derived ordering helpers
    if "Month" in df.columns:
        df["_month_idx"] = df["Month"].map(MONTH_INDEX)
    if {"FY", "Month"} <= set(df.columns):
        df["Period"] = df["FY"].astype(str) + " · " + df["Month"].astype(str)

    if df.empty:
        return None, notes + ["The sheet parsed but contained no usable data rows."]

    return df, notes


def validate_schema(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Return (blocking_errors, warnings) for an uploaded frame."""
    errors, warnings = [], []
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    critical = [c for c in ("FY", "Month", "State", "Final Bid Value", "Total Income")
                if c in missing]
    if critical:
        errors.append("Missing required column(s): " + ", ".join(f"`{c}`" for c in critical))
    optional_missing = [c for c in missing if c not in critical]
    if optional_missing:
        warnings.append("Optional column(s) absent, related visuals will be hidden: "
                        + ", ".join(f"`{c}`" for c in optional_missing))
    for col in ("Final Bid Value", "Total Income"):
        if col in df.columns and df[col].notna().sum() == 0:
            errors.append(f"`{col}` contains no numeric values.")
    return errors, warnings


def discover_default_workbook(folder: str) -> str | None:
    """Find the most recently modified .xlsx in the folder, ignoring Excel lock files."""
    candidates = [
        p for p in glob.glob(os.path.join(folder, "*.xls*"))
        if not os.path.basename(p).startswith("~$")
    ]
    if not candidates:
        return None
    return max(candidates, key=os.path.getmtime)


def read_bytes_resilient(path: str) -> bytes | None:
    """
    Read a file that may be locked by Excel or a OneDrive sync pass.

    Falls back to a byte-wise copy through a temporary file.
    """
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except PermissionError:
        pass
    try:
        import shutil
        import tempfile
        tmp = os.path.join(tempfile.gettempdir(), "conv_dash_" + os.path.basename(path))
        shutil.copy2(path, tmp)
        with open(tmp, "rb") as fh:
            data = fh.read()
        try:
            os.remove(tmp)
        except OSError:
            pass
        return data
    except Exception:                                           # noqa: BLE001
        return None


# ─────────────────────────────────────────────────────────────────────────────
# METRICS  (single definition point)
# ─────────────────────────────────────────────────────────────────────────────
def compute_metrics(df: pd.DataFrame) -> dict:
    """Compute the headline metric set for a (possibly filtered) frame."""
    n = len(df)
    gmv = float(df["Final Bid Value"].sum()) if "Final Bid Value" in df else 0.0
    rev = float(df["Total Income"].sum()) if "Total Income" in df else 0.0
    sellers = int(df["Seller Name"].nunique()) if "Seller Name" in df else 0
    buyers = int(df["Buyer Name"].nunique()) if "Buyer Name" in df else 0
    return {
        "transactions": n,
        "gmv": gmv,
        "revenue": rev,
        "avg_commission": rev / n if n else 0.0,
        "avg_txn_value": gmv / n if n else 0.0,
        "take_rate": (rev / gmv * 100) if gmv else 0.0,
        "unique_sellers": sellers,
        "unique_buyers": buyers,
        "txn_per_seller": n / sellers if sellers else 0.0,
        "purchases_per_buyer": n / buyers if buyers else 0.0,
    }


def period_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate to the FY-Month grain, correctly ordered across financial years."""
    if not {"FY", "Month"} <= set(df.columns) or df.empty:
        return pd.DataFrame()
    g = (df.groupby(["FY", "Month"], dropna=False)
           .agg(Transactions=("Final Bid Value", "size"),
                GMV=("Final Bid Value", "sum"),
                Revenue=("Total Income", "sum"),
                AvgBid=("Final Bid Value", "mean"),
                AvgCommission=("Total Income", "mean"),
                Sellers=("Seller Name", "nunique"),
                Buyers=("Buyer Name", "nunique"))
           .reset_index())
    g["_m"] = g["Month"].map(MONTH_INDEX)
    g = g.sort_values(["FY", "_m"]).reset_index(drop=True)
    g["Period"] = g["FY"].astype(str) + " · " + g["Month"].astype(str)
    g["TakeRate"] = np.where(g["GMV"] > 0, g["Revenue"] / g["GMV"] * 100, np.nan)
    return g


def latest_period_deltas(pf: pd.DataFrame) -> dict:
    """Percentage change of the newest period against the one before it."""
    if len(pf) < 2:
        return {}
    last, prev = pf.iloc[-1], pf.iloc[-2]
    out = {"_label": f"vs {prev['Period']}"}
    for key, col in (("transactions", "Transactions"), ("gmv", "GMV"),
                     ("revenue", "Revenue"), ("avg_commission", "AvgCommission"),
                     ("take_rate", "TakeRate")):
        base = prev[col]
        if pd.notna(base) and base:
            out[key] = float((last[col] - base) / base * 100)
    return out


def entity_performance(df: pd.DataFrame, key: str, count_name: str) -> pd.DataFrame:
    """Per-seller or per-buyer performance table."""
    if key not in df.columns or df.empty:
        return pd.DataFrame()
    src = df[df[key].notna()]
    if src.empty:
        return pd.DataFrame()
    g = (src.groupby(key, dropna=True)
           .agg(**{count_name: ("Final Bid Value", "size")},
                GMV=("Final Bid Value", "sum"),
                AvgTxnValue=("Final Bid Value", "mean"),
                Commission=("Total Income", "sum"),
                AvgCommission=("Total Income", "mean"))
           .reset_index())
    g["TakeRate"] = np.where(g["GMV"] > 0, g["Commission"] / g["GMV"] * 100, np.nan)
    total_gmv = g["GMV"].sum()
    g["GMVShare"] = np.where(total_gmv > 0, g["GMV"] / total_gmv * 100, 0)
    return g.sort_values(count_name, ascending=False).reset_index(drop=True)


PRICE_BINS = [0, 100_000, 200_000, 300_000, 500_000, 750_000, np.inf]
PRICE_LABELS = ["< ₹1L", "₹1–2L", "₹2–3L", "₹3–5L", "₹5–7.5L", "₹7.5L+"]


def price_bands(df: pd.DataFrame) -> pd.DataFrame:
    if "Final Bid Value" not in df.columns or df.empty:
        return pd.DataFrame()
    tmp = df.copy()
    tmp["Band"] = pd.cut(tmp["Final Bid Value"], bins=PRICE_BINS,
                         labels=PRICE_LABELS, right=False)
    g = (tmp.groupby("Band", observed=False)
            .agg(Transactions=("Final Bid Value", "size"),
                 GMV=("Final Bid Value", "sum"),
                 Revenue=("Total Income", "sum"))
            .reset_index())
    g["TakeRate"] = np.where(g["GMV"] > 0, g["Revenue"] / g["GMV"] * 100, np.nan)
    return g


# ─────────────────────────────────────────────────────────────────────────────
# DATA QUALITY
# ─────────────────────────────────────────────────────────────────────────────
def _norm_key(v) -> str:
    s = unicodedata.normalize("NFKD", str(v))
    return re.sub(r"[\s_\-./]+", "", s).lower()


def case_variant_report(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """
    Find categorical values that are the same entity written differently
    (case, spacing, punctuation). These break group-bys and are the classic
    reason a warehouse loses its single source of truth.
    """
    rows = []
    for col in cols:
        if col not in df.columns:
            continue
        s = df[col].dropna()
        if s.empty:
            continue
        tmp = pd.DataFrame({"raw": s.astype(str)})
        tmp["key"] = tmp["raw"].map(_norm_key)
        grp = tmp.groupby("key")["raw"].agg(["nunique", "count", lambda x: sorted(set(x))])
        grp.columns = ["variants", "rows", "values"]
        bad = grp[grp["variants"] > 1]
        for _, r in bad.iterrows():
            rows.append({"Column": col,
                         "Variants": int(r["variants"]),
                         "Rows Affected": int(r["rows"]),
                         "Values Found": " | ".join(map(str, r["values"][:6]))})
    return pd.DataFrame(rows)


def compute_quality(df: pd.DataFrame) -> dict:
    """
    Score the frame across four dimensions and return supporting detail.

    completeness  – share of populated cells in business columns
    uniqueness    – absence of duplicate rows / duplicate vehicle registrations
    validity      – values inside declared domains and plausible ranges
    consistency   – categorical values standardised to one spelling
    """
    q: dict = {}
    work = df.drop(columns=[c for c in ("_month_idx", "Period") if c in df.columns])
    rows, cols = work.shape
    q["rows"], q["cols"] = rows, cols

    # ── Completeness ────────────────────────────────────────────────────
    nulls = work.isna().sum()
    total_cells = rows * cols
    q["null_cells"] = int(nulls.sum())
    q["total_cells"] = int(total_cells)
    q["completeness"] = float((1 - nulls.sum() / total_cells) * 100) if total_cells else 0.0
    q["column_health"] = pd.DataFrame({
        "Column": work.columns,
        "Nulls": nulls.values,
        "Null %": (nulls.values / rows * 100).round(2) if rows else 0,
        "Populated %": (100 - nulls.values / rows * 100).round(2) if rows else 0,
        "Distinct": [int(work[c].nunique(dropna=True)) for c in work.columns],
        "Type": [str(t) for t in work.dtypes],
    }).sort_values("Null %", ascending=False).reset_index(drop=True)

    # ── Uniqueness ──────────────────────────────────────────────────────
    dup_rows = int(work.duplicated().sum())
    q["duplicate_rows"] = dup_rows
    if "Vehicle Number" in work.columns:
        vc = work["Vehicle Number"].dropna()
        q["duplicate_vehicles"] = int(vc.duplicated().sum())
        q["repeated_vehicle_list"] = (vc.value_counts()
                                        .loc[lambda s: s > 1]
                                        .head(25)
                                        .rename_axis("Vehicle Number")
                                        .reset_index(name="Occurrences"))
    else:
        q["duplicate_vehicles"] = 0
        q["repeated_vehicle_list"] = pd.DataFrame()
    dup_penalty = ((dup_rows + q["duplicate_vehicles"]) / rows * 100) if rows else 0
    q["uniqueness"] = float(max(0.0, 100 - dup_penalty))

    # ── Validity ────────────────────────────────────────────────────────
    checks, failing_mask = [], pd.Series(False, index=work.index)

    if "Month" in work.columns:
        bad = ~work["Month"].isin(MONTH_ORDER) & work["Month"].notna()
        checks.append(("Month is a valid calendar abbreviation", int(bad.sum()),
                       sorted(work.loc[bad, "Month"].dropna().unique().tolist())[:8]))
        failing_mask |= bad
    if "FY" in work.columns:
        bad = ~work["FY"].astype(str).str.match(r"^FY\d{2}$", na=False) & work["FY"].notna()
        checks.append(("FY matches the FYnn pattern", int(bad.sum()),
                       sorted(work.loc[bad, "FY"].dropna().unique().tolist())[:8]))
        failing_mask |= bad
    if "Vehicle Number" in work.columns:
        bad = (~work["Vehicle Number"].astype(str)
                .str.match(r"^[A-Z]{2}\d{1,2}[A-Z]{0,3}\d{1,4}$", na=False)
               & work["Vehicle Number"].notna())
        checks.append(("Vehicle Number matches an Indian registration format",
                       int(bad.sum()),
                       sorted(work.loc[bad, "Vehicle Number"].dropna().unique().tolist())[:8]))
        failing_mask |= bad
    for col, (lo, hi) in VALID_RULES.items():
        if col in work.columns:
            bad = work[col].notna() & ((work[col] < lo) | (work[col] > hi))
            checks.append((f"{col} within {lo:,} – {hi:,}", int(bad.sum()), []))
            failing_mask |= bad
    if {"Total Income", "Final Bid Value"} <= set(work.columns):
        bad = (work["Total Income"].notna() & work["Final Bid Value"].notna()
               & (work["Total Income"] > work["Final Bid Value"]))
        checks.append(("Commission never exceeds the bid value", int(bad.sum()), []))
        failing_mask |= bad
    if "Seller Segment" in work.columns:
        allowed = {"Captive", "Non-Captive"}
        bad = work["Seller Segment"].notna() & ~work["Seller Segment"].isin(allowed)
        checks.append(("Seller Segment is Captive or Non-Captive", int(bad.sum()),
                       sorted(work.loc[bad, "Seller Segment"].dropna().unique().tolist())[:8]))
        failing_mask |= bad

    q["validity_checks"] = checks
    q["invalid_rows"] = int(failing_mask.sum())
    q["validity"] = float((1 - failing_mask.sum() / rows) * 100) if rows else 0.0

    # ── Consistency ─────────────────────────────────────────────────────
    cat_cols = [c for c in ("FY", "Month", "State", "Make", "Model",
                            "Seller Name", "Seller Segment", "Buyer Name")
                if c in work.columns]
    variants = case_variant_report(work, cat_cols)
    q["variant_report"] = variants
    affected = int(variants["Rows Affected"].sum()) if not variants.empty else 0
    q["consistency_rows_affected"] = affected
    q["consistency"] = float(max(0.0, 100 - (affected / rows * 100))) if rows else 0.0

    # ── Outliers (IQR) ──────────────────────────────────────────────────
    outliers = {}
    for col in ("Final Bid Value", "Total Income", "Odometer"):
        if col in work.columns and work[col].notna().sum() > 4:
            s = work[col].dropna()
            q1, q3 = s.quantile(0.25), s.quantile(0.75)
            iqr = q3 - q1
            lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            mask = (s < lo) | (s > hi)
            outliers[col] = {"count": int(mask.sum()),
                             "pct": float(mask.sum() / len(s) * 100),
                             "lower": float(lo), "upper": float(hi),
                             "min": float(s.min()), "max": float(s.max())}
    q["outliers"] = outliers

    # ── Coverage / lineage facts ────────────────────────────────────────
    q["coverage"] = {
        "FY": sorted(work["FY"].dropna().unique().tolist()) if "FY" in work else [],
        "State": sorted(work["State"].dropna().unique().tolist()) if "State" in work else [],
        "Month": [m for m in MONTH_ORDER
                  if "Month" in work and m in set(work["Month"].dropna())],
        "Segment": sorted(work["Seller Segment"].dropna().unique().tolist())
        if "Seller Segment" in work else [],
    }

    # ── Composite score ─────────────────────────────────────────────────
    dims = {"Completeness": q["completeness"], "Uniqueness": q["uniqueness"],
            "Validity": q["validity"], "Consistency": q["consistency"]}
    q["dimensions"] = dims
    q["overall"] = float(np.mean(list(dims.values())))
    return q


def grade(score: float) -> tuple[str, str]:
    """Map a 0-100 score to a letter grade and an accent name."""
    if score >= 95:
        return "Excellent", "jade"
    if score >= 85:
        return "Good", "teal"
    if score >= 70:
        return "Needs attention", "amber"
    return "Critical", "rose"
