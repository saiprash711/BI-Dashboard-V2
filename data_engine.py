"""
Data loading, normalisation and quality profiling for the Conversion dashboard.

Keeps all business logic out of the UI layer so metric definitions live in
exactly one place (the SSOT principle the dashboard reports on).
"""
from __future__ import annotations

import glob
import io
import os
import re
import unicodedata
from datetime import datetime

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
NUM_COLS = ["Year", "Odometer", "Final Bid Value", "Total Income (Ex GST)", "Total Income"]
REQUIRED_COLUMNS = DIM_COLS + NUM_COLS

# Canonical metric definitions surfaced in the SSOT tab.
METRIC_DEFINITIONS = [
    ("Transactions", "COUNT of rows", "One row = one converted vehicle."),
    ("GMV", "SUM(Final Bid Value)", "Gross merchandise value at winning bid."),
    ("Commission Revenue (Ex GST)", "SUM(Total Income (Ex GST))", "Platform net commission, excluding 18% GST."),
    ("Total Income (Inc GST)", "SUM(Total Income)", "Total platform billing, including 18% GST."),
    ("GST Collected", "SUM(Total Income) - SUM(Total Income (Ex GST))", "18% GST component on platform fees."),
    ("Avg. Commission (Ex GST)", "SUM(Total Income (Ex GST)) / Transactions", "Mean net commission per transaction."),
    ("Take Rate (Net)", "SUM(Total Income (Ex GST)) / SUM(Final Bid Value)", "Revenue captured per rupee of GMV (excluding GST)."),
    ("Avg. Transaction Value", "SUM(Final Bid Value) / Transactions", "Mean winning bid."),
    ("Unique Sellers", "DISTINCT COUNT(Seller Name)", "Distinct supply accounts."),
    ("Avg. Transactions / Seller", "Transactions / Unique Sellers", "Supply-side depth."),
    ("Unique Buyers", "DISTINCT COUNT(Buyer Name)", "Distinct demand accounts."),
    ("Avg. Purchases / Buyer", "Transactions / Unique Buyers", "Demand-side repeat rate."),
]

# Plausible ranges used by the validity checks.
VALID_RULES = {
    "Final Bid Value": (1_000, 50_000_000),
    "Total Income (Ex GST)": (0, 5_000_000),
    "Total Income": (0, 5_000_000),
    "Odometer": (0, 1_000_000),
    "Year": (1980, 2035),
}

_COL_ALIASES = {
    "total income (ex. gst)": "Total Income (Ex GST)",
    "total income (ex.gst)": "Total Income (Ex GST)",
    "total income (ex gst)": "Total Income (Ex GST)",
    "total income(ex gst)": "Total Income (Ex GST)",
    "total income(ex. gst)": "Total Income (Ex GST)",
    "total income ex gst": "Total Income (Ex GST)",
    "total income ex. gst": "Total Income (Ex GST)",
    "commission (ex gst)": "Total Income (Ex GST)",
    "commission (ex. gst)": "Total Income (Ex GST)",
    "commission(ex gst)": "Total Income (Ex GST)",
    "total income (inc. gst)": "Total Income",
    "total income (inc gst)": "Total Income",
    "total income(inc gst)": "Total Income",
    "total income inc gst": "Total Income",
    "gross income": "Total Income",
}

_MONTH_ALIASES = {
    "jan": "Jan", "january": "Jan", "feb": "Feb", "february": "Feb",
    "mar": "Mar", "march": "Mar", "apr": "Apr", "april": "Apr",
    "may": "May", "jun": "Jun", "june": "Jun", "jul": "Jul", "july": "Jul",
    "aug": "Aug", "august": "Aug", "sep": "Sep", "sept": "Sep", "september": "Sep",
    "oct": "Oct", "october": "Oct", "nov": "Nov", "november": "Nov",
    "dec": "Dec", "december": "Dec",
}

_MAKE_ALIASES = {
    "MARUTI": "MARUTI SUZUKI",
    "MARUTI SUZUKI": "MARUTI SUZUKI",
    "MARUTHI": "MARUTI SUZUKI",
    "MARUTHI SUZUKI": "MARUTI SUZUKI",
    "VW": "VOLKSWAGEN",
    "VOLKSWAGEN": "VOLKSWAGEN",
    "MG": "MG MOTORS",
    "MG MOTOR": "MG MOTORS",
    "MG MOTORS": "MG MOTORS",
    "HINDUSTAN MOTOR": "HINDUSTAN MOTORS",
    "HINDUSTAN MOTORS": "HINDUSTAN MOTORS",
}

_MODEL_ALIASES = {
    # Maruti models (Swift is hatchback, Dzire is sedan — strictly kept distinct)
    "swift": "Swift",
    "swiftlxi": "Swift",
    "dzire": "Dzire", "dezire": "Dzire", "swift dzire": "Dzire", "swiftdzire": "Dzire", "swift desire": "Dzire",
    "alto": "Alto", "alto std": "Alto",
    "alto 800": "Alto 800", "alto800": "Alto 800",
    "alto k10": "Alto K10", "altok10": "Alto K10", "k 10": "Alto K10", "k10": "Alto K10",
    "800": "800", "800 std": "800", "m 800": "800", "m800": "800",
    "a star": "A-Star", "a-star": "A-Star", "astar": "A-Star",
    "wagon r": "Wagon R", "wagon-r": "Wagon R", "wagonr": "Wagon R", "wgr": "Wagon R",
    "breeza": "Vitara Brezza", "v brezza": "Vitara Brezza", "brezza": "Vitara Brezza", "vitara brezza": "Vitara Brezza",
    "s-presso": "S-Presso", "spresso": "S-Presso", "espresso": "S-Presso",
    "s-cross": "S-Cross", "scross": "S-Cross",
    "zen estilo": "Zen Estilo", "estilo": "Zen Estilo",
    "zen": "Zen",
    "celerio-x": "Celerio X", "celerio": "Celerio",
    "g vitara": "Grand Vitara",
    "baleno": "Baleno",
    "ciaz": "Ciaz", "ciaz smart hybrid": "Ciaz",
    "ertiga": "Ertiga",
    "xl6": "XL6",
    "eeco": "Eeco",
    "omni": "Omni",
    "ignis": "Ignis",
    "ritz": "Ritz",
    "fronx": "Fronx",
    "jimny": "Jimny",
    "sx4": "SX4",

    # Toyota models (Innova Crysta sub-brand, Etios sedan vs Etios Liva hatch)
    "crysta": "Innova Crysta", "innova": "Innova",
    "altis": "Corolla Altis", "corolla": "Corolla Altis",
    "etios": "Etios", "ethios": "Etios",
    "etios liva": "Etios Liva",
    "glanza": "Glanza",
    "yaris": "Yaris",
    "camry": "Camry",
    "hyryder": "Hyryder",
    "qualis": "Qualis",

    # Datsun / Nissan models
    "datson": "Go", "datsun": "Go", "go": "Go", "go plus": "Go Plus",
    "redi-go": "Redi-GO", "redigo": "Redi-GO",
    "micra": "Micra", "micra active": "Micra Active",
    "sunny": "Sunny", "magnite": "Magnite", "kicks": "Kicks", "terrano": "Terrano", "evalia": "Evalia",

    # Honda models
    "brio": "Brio", "br10": "Brio",
    "amaze": "Amaze", "ameze": "Amaze",
    "jazz": "Jazz", "city": "City", "civic": "Civic", "accord": "Accord",
    "br-v": "BR-V", "brv": "BR-V",
    "wr-v": "WR-V", "wrv": "WR-V",
    "cr-v": "CR-V", "crv": "CR-V",
    "mobilio": "Mobilio", "elevate": "Elevate",

    # Hyundai models (Tiago hatch vs Tigor sedan, Grand i10 vs Xcent)
    "i 10": "i10", "i10": "i10",
    "i 20": "i20", "i20": "i20", "asta": "i20",
    "grand i10": "Grand i10", "grand i10 nios": "Grand i10 Nios", "nios": "Grand i10 Nios", "neos": "Grand i10 Nios",
    "santro": "Santro", "santor": "Santro",
    "eon": "Eon", "getz": "Getz", "getz prime": "Getz",
    "accent": "Accent", "verna": "Verna", "xcent": "Xcent", "aura": "Aura",
    "venue": "Venue", "creta": "Creta", "alcazar": "Alcazar", "tucson": "Tucson",

    # Tata models (Tiago hatch distinct from Tigor sedan)
    "tiago": "Tiago", "tiago ev": "Tiago EV",
    "tigor": "Tigor", "tigore": "Tigor",
    "indica": "Indica", "vista": "Indica",
    "indigo": "Indigo", "ingigo": "Indigo", "indigo cs": "Indigo", "manza": "Indigo",
    "altroz": "Altroz", "punch": "Punch", "nexon": "Nexon", "nexon ev": "Nexon EV",
    "harrier": "Harrier", "safari": "Safari", "hexa": "Hexa", "aria": "Aria",
    "nano": "Nano", "zest": "Zest", "bolt": "Bolt",

    # Ford models (Figo hatch distinct from Aspire sedan)
    "figo": "Figo", "aspire": "Aspire", "figo aspire": "Aspire", "freestyle": "Freestyle",
    "fiesta": "Fiesta", "fiesta classic": "Fiesta Classic", "fiestaclassic": "Fiesta Classic",
    "ecosport": "EcoSport", "ikon": "Ikon", "fusion": "Fusion",

    # Volkswagen & Skoda models (Polo hatch distinct from Vento sedan)
    "polo": "Polo", "vento": "Vento", "ameo": "Ameo", "virtus": "Virtus", "taigun": "Taigun",
    "fabia": "Fabia", "rapid": "Rapid", "octavia": "Octavia", "octovia": "Octavia",
    "laura": "Laura", "kushaq": "Kushaq",

    # Mahindra models
    "xuv 500": "XUV500", "xuv500": "XUV500", "xuv": "XUV500",
    "xuv 300": "XUV300", "xuv300": "XUV300",
    "xuv 400": "XUV400", "xuv400": "XUV400",
    "xuv 700": "XUV700", "xuv700": "XUV700",
    "kuv 100": "KUV100", "kuv100": "KUV100", "kuv": "KUV100",
    "tuv 300": "TUV300", "tuv300": "TUV300",
    "bolero": "Bolero", "scorpio": "Scorpio", "thar": "Thar", "xylo": "Xylo",
    "verito": "Verito", "logan": "Verito", "quanto": "Quanto",

    # Other models
    "sonet": "Sonet", "sonnet": "Sonet", "seltos": "Seltos", "carens": "Carens",
    "lodgy": "Lodgy", "logdy": "Lodgy", "kwid": "Kwid", "triber": "Triber", "kiger": "Kiger", "duster": "Duster", "pulse": "Pulse", "scala": "Scala",
    "pajero": "Pajero", "pajeero": "Pajero",
    "hector": "Hector", "hector-plus": "Hector Plus", "hector plus": "Hector Plus", "astor": "Astor",
    "load king": "Load King", "loadking": "Load King",
}

_SELLER_ALIASES = {
    # Aadhi Cars & AA Cars
    "AADHI CARS": "AADHI CARS PRIVATE LIMITED",
    "AADHI CARS PRIVATE LIMITED": "AADHI CARS PRIVATE LIMITED",
    "AA CARS MADHURAI": "AA CARS",
    "AA CARS": "AA CARS",
    "A A CARS": "AA CARS",

    # Popular dealer group
    "POIPULAR MARUTI": "POPULAR MARUTI",
    "POPULAR HUNDAI": "POPULAR HYUNDAI",
    "POPULAR HYUNDAI": "POPULAR HYUNDAI",
    "POPULAR MOTOR WORLD": "POPULAR MOTORWORLD PVT LTD",
    "POPULAR MOTORWORLD PVT LTD": "POPULAR MOTORWORLD PVT LTD",
    "POPULAR MOTORWORLD": "POPULAR MOTORWORLD PVT LTD",
    "POPULAR VEHICLES AND SERVICES LIMITED": "POPULAR VEHICLES",
    "POPULAR VEHICLES": "POPULAR VEHICLES",

    # Castle Traders
    "CASTEL TRADERS HONADA": "CASTLE TRADERS HONDA",
    "CASTEL TRADERS HONDA": "CASTLE TRADERS HONDA",
    "CASTLE TRADERS HONDA": "CASTLE TRADERS HONDA",
    "CASTLE TRADERS MAHINDRA)": "CASTLE TRADERS MAHINDRA",
    "CASTEL TRADER MAHINDRA": "CASTLE TRADERS MAHINDRA",
    "CASTLE TRADERS MAHINDRA": "CASTLE TRADERS MAHINDRA",

    # Authorized dealer networks and branch locations
    "KIRALI TOYOTA": "KAIRALI TOYOTA",
    "Kirali Toyota": "KAIRALI TOYOTA",
    "INCHEION KIA": "INCHEON KIA",
    "INCHIEON KIA": "INCHEON KIA",
    "PINNACALE NISSAN": "PINNACLE NISSAN",
    "EVM CETREON": "EVM CITROEN",
    "EVM CITRON": "EVM CITROEN",
    "EVM AUTOCRAFT CITRON": "EVM CITROEN",
    "LUXON TATA": "LUXON TATA",
    "lUXON TATA": "LUXON TATA",
    "KALYANIMOTORS MARUTHI": "KALYANI MOTORS MARUTI",
    "CARZONE": "CAR ZONE",
    "MAXXMOTORS": "MAXX MOTORS",
    "PRAJOTH": "PRAJOSH",
    "PRAJOSH P": "PRAJOSH",
    "AMRUTH V CHANDY": "AMRITH V CHANDY",
    "AUGSTY MJ": "AUGUSTHY M J",
    "LANSAON CMBT": "LANSON COIMBATORE",
    "ABT LIMITED - COIMBATORE": "ABT LIMITED",
    "BALAJI CARS (THENI)": "BALAJI CARS",
    "KRISH TOYOTA - COIMBATORE": "KRISH TOYOTA",
    "THIRUMALAI CARS (MADURAI)": "THIRUMALAI CARS",
}

_BUYER_ALIASES = {
    "33CARS": "33 Cars",
    "A A CARS": "AA Cars",
    "AASIM MOTOR": "Aasim Motors",
    "AASIM MOTORS": "Aasim Motors",
    "AITO CARS": "Aitos Cars",
    "AITOS CARS": "Aitos Cars",
    "ALI .HAPPY DRIVE": "Ali Happy Drive",
    "ALI,HAPPY DRIVE": "Ali Happy Drive",
    "ATHULRAJ": "Athul Raj",
    "AUTO BOT": "Autobot",
    "AUTOBOOT": "Autobot",
    "AUTOBOT": "Autobot",
    "AUTOMOTIVATORS": "Auto Motivators",
    "AUTO MOTIVATORS": "Auto Motivators",
    "AYYAPA CARS": "Ayyappa Cars",
    "CARS 24": "Cars24",
    "CARS24": "Cars24",
    "DEREAM DRIVE": "Dream Drive",
    "ESSARPREOWNEDCARS": "Essar Preowned Cars",
    "GUGHAA CARS": "Gugha Cars",
    "GOPI NAGA RAJU": "Gopi Nagaraju",
    "HUSSIAN O E": "Hussain O E",
    "KAM AUTO CONSELTING": "KSM Auto Consulting",
    "KSM AUTO CONSULTING": "KSM Auto Consulting",
    "MAXXMOTORS": "Maxx Motors",
    "MOHAMMED ASALAM K": "Mohammed Aslam K",
    "POPULAR KOTAYAM": "Popular Kottayam",
    "SAJITH.LEAPS TRUACKS": "Sajith Leaps Trucks",
    "SARVESH CAARS": "Sarvesh Cars",
    "SHIVASHANKAR CARS": "Sivashankar Cars",
    "SIVASHANKAR CARS": "Sivashankar Cars",
    "SHRI SHAKTHI VINAYAGA CARS": "Sri Shakthi Vinayaga Cars",
    "SHRI LAKSHMI CARS": "Sri Lakshmi Cars",
    "UMESHKUMAR T U": "Umesh Kumar T U",
    "UMESH KUMAR TU": "Umesh Kumar T U",
    "ULAVAN ENTERPRISES": "Uzhavan Enterprise",
    "UZHAVAN ENTERPRISE": "Uzhavan Enterprise",
    "M/S YES CARS": "Yes Cars",
}


# ─────────────────────────────────────────────────────────────────────────────
# LOADING
# ─────────────────────────────────────────────────────────────────────────────
def _clean_text(s: pd.Series) -> pd.Series:
    """Collapse whitespace and strip non-printing characters."""
    return (s.astype("string")
             .str.replace(r"\s+", " ", regex=True)
             .str.strip())


def standardize_make(series: pd.Series, models: pd.Series | None = None) -> pd.Series:
    """Canonicalise vehicle Make casing, aliases, and imputations."""
    clean = _clean_text(series).str.upper()
    mapped = clean.map(lambda x: _MAKE_ALIASES.get(x, x) if pd.notna(x) else x)
    if models is not None:
        for idx in mapped[mapped.isna()].index:
            m = str(models.get(idx, "")).strip().lower()
            if m == "samrat":
                mapped[idx] = "SML ISUZU"
    return mapped.astype("string")


def standardize_model(series: pd.Series) -> pd.Series:
    """Standardise vehicle Model names, spacing, and variant spellings."""
    clean = _clean_text(series)
    def _map(val):
        if pd.isna(val) or str(val).strip().lower() in ("na", "nan", "none", "-", ""):
            return None
        v = str(val).strip()
        k = v.lower()
        if k in _MODEL_ALIASES:
            return _MODEL_ALIASES[k]
        k_no_punct = re.sub(r"[^a-z0-9]", "", k)
        for mk, tgt in _MODEL_ALIASES.items():
            if re.sub(r"[^a-z0-9]", "", mk) == k_no_punct:
                return tgt
        return v.title()
    return clean.map(_map).astype("string")


_LEGAL_SUFFIX_RE = re.compile(
    r"\b(private limited|pvt\.?\s*ltd\.?|private ltd\.?|pvt limited|limited|ltd\.?|llp|inc\.?|corp\.?)\b",
    re.IGNORECASE,
)


def _entity_stem(name: str) -> str:
    """Strip common corporate suffixes and punctuation to create a clustering stem."""
    s = _LEGAL_SUFFIX_RE.sub("", name)
    s = re.sub(r"[\(\)\-\,\./]", " ", s)
    return re.sub(r"[^a-z0-9]", "", s.lower()).strip()


def _entity_corporate_score(name: str) -> int:
    """Give higher priority to official registered corporate names."""
    up = name.upper()
    score = 0
    if "PRIVATE LIMITED" in up:
        score += 50
    elif "PVT LTD" in up or "PVT. LTD" in up:
        score += 40
    elif "LIMITED" in up or "LTD" in up:
        score += 30
    elif "LLP" in up:
        score += 25
    return score


def standardize_entities(series: pd.Series, overrides: dict[str, str], default_upper: bool = False) -> pd.Series:
    """
    Standardise company, dealer, and account names.
    Removes honorific prefixes (M/s), applies domain dictionary overrides,
    and clusters case/spacing/punctuation/corporate suffix variants into a single canonical entity.
    """
    clean = _clean_text(series)
    clean = clean.str.replace(r"^(?i:m/s[\.\s]+|m/s-)", "", regex=True).str.strip()

    def _apply_override(val):
        if pd.isna(val) or not str(val).strip():
            return None
        v = str(val).strip()
        up = v.upper()
        if up in overrides:
            return overrides[up]
        up_clean = re.sub(r"[^A-Z0-9 ]", "", up)
        if up_clean in overrides:
            return overrides[up_clean]
        v = re.sub(r"\)+$", "", v).strip()
        return v

    step1 = clean.map(_apply_override)

    counts = step1.value_counts().to_dict()
    stem_to_canonical: dict[str, tuple[str, int, int]] = {}
    for val, count in counts.items():
        if pd.isna(val) or not str(val).strip():
            continue
        v = str(val).strip()
        stem = _entity_stem(v)
        if not stem:
            continue
        score = _entity_corporate_score(v)
        if stem not in stem_to_canonical:
            stem_to_canonical[stem] = (v, score, count)
        else:
            prev_v, prev_score, prev_cnt = stem_to_canonical[stem]
            if (score, count) > (prev_score, prev_cnt):
                stem_to_canonical[stem] = (v, score, count)

    def _resolve_canonical(val):
        if pd.isna(val) or not str(val).strip():
            return None
        v = str(val).strip()
        stem = _entity_stem(v)
        if stem in stem_to_canonical:
            res = stem_to_canonical[stem][0]
            if default_upper:
                return res.upper()
            return res
        return v.upper() if default_upper else v

    return step1.map(_resolve_canonical).astype("string")


def extract_standardization_audit(raw_df: pd.DataFrame, clean_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """
    Extract comprehensive before-and-after audit logs for standardized columns.
    Returns a dict with keys: 'models', 'sellers', 'buyers', 'makes'.
    Each DataFrame contains:
      - 'Raw Input in Excel'
      - 'Standardised Canonical Value'
      - 'Records Affected'
      - 'Standardisation Rule / Body Style Reason'
    """
    col_map = {
        "models": ("Model", "model"),
        "sellers": ("Seller Name", "seller"),
        "buyers": ("Buyer Name", "buyer"),
        "makes": ("Make", "make"),
    }
    out: dict[str, pd.DataFrame] = {}
    for key, (col, kind) in col_map.items():
        if col not in raw_df.columns or col not in clean_df.columns:
            out[key] = pd.DataFrame(columns=[
                "Raw Input in Excel", "Standardised Canonical Value",
                "Records Affected", "Standardisation Rule / Body Style Reason"
            ])
            continue
        common_idx = raw_df.index.intersection(clean_df.index)
        r = raw_df.loc[common_idx, col].astype(str).str.strip()
        c = clean_df.loc[common_idx, col].astype(str).str.strip()
        mask = (r != c) & (r != "nan") & (r != "") & (r.str.lower() != "none")
        if not mask.any():
            out[key] = pd.DataFrame(columns=[
                "Raw Input in Excel", "Standardised Canonical Value",
                "Records Affected", "Standardisation Rule / Body Style Reason"
            ])
            continue
        diff = pd.DataFrame({"Raw Input in Excel": r[mask], "Standardised Canonical Value": c[mask]})
        grp = diff.groupby(["Raw Input in Excel", "Standardised Canonical Value"]).size().reset_index(name="Records Affected")
        grp = grp.sort_values(by="Records Affected", ascending=False)

        def explain(row):
            r_val, c_val = str(row["Raw Input in Excel"]), str(row["Standardised Canonical Value"])
            rl, cl = r_val.lower(), c_val.lower()
            if kind == "model":
                if any(k in rl for k in ["dzire", "dezire", "desire"]):
                    return "Body style separation: Sedan (distinct from Swift Hatchback)"
                if cl == "swift":
                    return "Variant trim unified into Swift Hatchback"
                if "tigor" in cl or "tigor" in rl:
                    return "Typo corrected to Tigor Sedan (distinct from Tiago Hatchback)"
                if "tiago" in cl:
                    return "Casing normalised to Tiago Hatchback"
                if "indigo" in cl:
                    return "Unified into Indigo Sedan (distinct from Indica Hatchback)"
                if "aspire" in cl or "aspire" in rl:
                    return "Body style separation: Sedan (distinct from Figo Hatchback)"
                if "crysta" in cl or "crysta" in rl:
                    return "Sub-brand resolved to Toyota Innova Crysta"
                if "altis" in cl or "altis" in rl:
                    return "Sub-brand resolved to Toyota Corolla Altis"
                if "brezza" in cl:
                    return "Consolidated into Vitara Brezza SUV"
                if cl == "go":
                    return "Resolved to Datsun Go Hatchback"
                if rl.replace(" ", "") == cl.replace(" ", ""):
                    return "Spacing / hyphenation standardised"
                return "Model alias / spelling standardised"
            elif kind == "seller":
                if "aadh" in rl:
                    return "Consolidated corporate entity into registered Private Limited"
                if "aa car" in rl:
                    return "Dealership branch / name unified"
                if "popular" in rl:
                    return "Dealer group name standardised"
                if "cast" in rl:
                    return "Dealer franchise spelling corrected"
                if "pvt" in cl or "limited" in cl:
                    return "Corporate legal suffix standardised"
                if rl.upper() == cl.upper():
                    return "Casing standardised to UPPER CASE"
                return "Entity name / branch standardised"
            elif kind == "buyer":
                if rl.lower().replace(" ", "") == cl.lower().replace(" ", ""):
                    return "Account casing and spacing deduplicated"
                return "Buyer name deduplicated"
            elif kind == "make":
                return "Canonical brand name (UPPER CASE)"
            return "Standardised"

        grp["Standardisation Rule / Body Style Reason"] = grp.apply(explain, axis=1)
        out[key] = grp
    return out


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
    except PermissionError:
        if isinstance(source, (str, os.PathLike)):
            b = read_bytes_resilient(str(source))
            if b:
                raw = pd.read_excel(io.BytesIO(b), sheet_name=0, header=None)
            else:
                return None, [f"Could not read the workbook (locked by another program): {source}"]
        else:
            return None, ["Could not read the workbook: permission denied."]
    except Exception as exc:                                    # noqa: BLE001
        return None, [f"Could not read the workbook: {exc}"]

    hdr = _find_header_row(raw)
    if hdr is None:
        # Check if another sheet contains the conversion data table
        try:
            xl = pd.ExcelFile(source)
            for sname in xl.sheet_names[1:]:
                candidate = pd.read_excel(xl, sheet_name=sname, header=None)
                cand_hdr = _find_header_row(candidate)
                if cand_hdr is not None:
                    raw = candidate
                    hdr = cand_hdr
                    notes.append(f"Loaded conversion dataset from sheet '{sname}'.")
                    break
        except Exception:
            pass

    if hdr is None:
        return None, ["Could not locate a header row containing FY / Month / State. "
                      "Check that the first sheet matches the expected template."]
    if hdr:
        notes.append(f"Header detected on row {hdr + 1}; {hdr} banner row(s) skipped.")

    df = raw.iloc[hdr + 1:].copy()
    raw_cols = [str(c).strip() for c in raw.iloc[hdr].tolist()]
    renames = {}
    for c in raw_cols:
        c_clean = re.sub(r"\s+", " ", c).strip().lower()
        if c_clean in _COL_ALIASES:
            renames[c] = _COL_ALIASES[c_clean]
    df.columns = [renames.get(c, c) for c in raw_cols]
    if renames:
        mapped_summary = [f"'{old}' -> '{new}'" for old, new in renames.items() if old != new]
        if mapped_summary:
            notes.append(f"Standardised column name(s): {', '.join(mapped_summary)}.")

    # Drop unnamed / empty spacer columns
    drop = [c for c in df.columns if c in ("nan", "None", "") or c.startswith("Unnamed")]
    if drop:
        df = df.drop(columns=drop)
        notes.append(f"Dropped {len(drop)} unnamed spacer column(s).")

    df = df.loc[:, ~df.columns.duplicated()]
    df = df.dropna(how="all").reset_index(drop=True)
    raw_snapshot = df.copy()

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
            notes.append(f"Standardised {changed} month value(s) to Title case (e.g. 'JAN' -> 'Jan').")

    # FY canonicalisation
    if "FY" in df.columns:
        df["FY"] = df["FY"].str.upper().str.replace(r"\s+", "", regex=True)

    # Vehicle number canonicalisation
    if "Vehicle Number" in df.columns:
        df["Vehicle Number"] = (df["Vehicle Number"].str.upper()
                                .str.replace(r"[^A-Z0-9]", "", regex=True))

    # Make canonicalisation
    if "Make" in df.columns:
        n_before = int(df["Make"].nunique(dropna=True))
        df["Make"] = standardize_make(df["Make"], df["Model"] if "Model" in df.columns else None)
        n_after = int(df["Make"].nunique(dropna=True))
        if n_before != n_after:
            notes.append(f"Standardised vehicle Make: consolidated {n_before} raw entries into {n_after} canonical brands (e.g. 'MARUTI' -> 'MARUTI SUZUKI', 'VW' -> 'VOLKSWAGEN').")
        else:
            notes.append("Standardised vehicle Make casing to UPPER CASE.")

    # Model canonicalisation
    if "Model" in df.columns:
        n_before = int(df["Model"].nunique(dropna=True))
        df["Model"] = standardize_model(df["Model"])
        n_after = int(df["Model"].nunique(dropna=True))
        if n_before != n_after:
            notes.append(f"Standardised vehicle Model: consolidated {n_before} raw entries into {n_after} canonical models (e.g. 'Wagonr' -> 'Wagon R', 'Alto800' -> 'Alto 800').")

    # Seller Name canonicalisation
    if "Seller Name" in df.columns:
        n_before = int(df["Seller Name"].nunique(dropna=True))
        df["Seller Name"] = standardize_entities(df["Seller Name"], _SELLER_ALIASES, default_upper=True)
        n_after = int(df["Seller Name"].nunique(dropna=True))
        if n_before != n_after:
            notes.append(f"Standardised Seller Name: consolidated {n_before} raw names into {n_after} clean entities (resolved dealer casing, suffixes and typos).")

    # Buyer Name canonicalisation
    if "Buyer Name" in df.columns:
        n_before = int(df["Buyer Name"].nunique(dropna=True))
        df["Buyer Name"] = standardize_entities(df["Buyer Name"], _BUYER_ALIASES, default_upper=False)
        n_after = int(df["Buyer Name"].nunique(dropna=True))
        if n_before != n_after:
            notes.append(f"Standardised Buyer Name: consolidated {n_before} raw accounts into {n_after} clean entities (deduplicated case variants and spacing).")

    # Numerics
    for col in NUM_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Derive missing income metrics if one is provided
    has_ex = "Total Income (Ex GST)" in df.columns
    has_inc = "Total Income" in df.columns

    if has_ex and not has_inc:
        df["Total Income"] = (df["Total Income (Ex GST)"] * 1.18).round(2)
        notes.append("Derived 'Total Income' (inc. GST) from 'Total Income (Ex GST)' at 18% GST.")
    elif has_inc and not has_ex:
        df["Total Income (Ex GST)"] = (df["Total Income"] / 1.18).round(2)
        notes.append("Derived 'Total Income (Ex GST)' from 'Total Income' at 18% GST.")
    elif has_ex and has_inc:
        # Fill any sparse row-level gaps across the two columns
        m_ex = df["Total Income (Ex GST)"].isna() & df["Total Income"].notna()
        if m_ex.any():
            df.loc[m_ex, "Total Income (Ex GST)"] = (df.loc[m_ex, "Total Income"] / 1.18).round(2)
        m_inc = df["Total Income"].isna() & df["Total Income (Ex GST)"].notna()
        if m_inc.any():
            df.loc[m_inc, "Total Income"] = (df.loc[m_inc, "Total Income (Ex GST)"] * 1.18).round(2)

    # Derived GST
    if "Total Income" in df.columns and "Total Income (Ex GST)" in df.columns:
        df["GST"] = (df["Total Income"] - df["Total Income (Ex GST)"]).clip(lower=0).round(2)

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

    try:
        df.attrs["standardization_audit"] = extract_standardization_audit(raw_snapshot, df)
    except Exception:
        df.attrs["standardization_audit"] = {}

    return df, notes


def validate_schema(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Return (blocking_errors, warnings) for an uploaded frame."""
    errors, warnings = [], []
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    critical = [c for c in ("FY", "Month", "State", "Final Bid Value") if c in missing]
    if "Total Income (Ex GST)" in missing and "Total Income" in missing:
        critical.append("Total Income (Ex GST)")
    if critical:
        errors.append("Missing required column(s): " + ", ".join(f"`{c}`" for c in critical))
    optional_missing = [c for c in missing if c not in critical]
    if optional_missing:
        warnings.append("Optional column(s) absent, related visuals will be hidden: "
                        + ", ".join(f"`{c}`" for c in optional_missing))
    for col in ("Final Bid Value", "Total Income (Ex GST)", "Total Income"):
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

    # Revenue is platform net commission (Ex GST)
    if "Total Income (Ex GST)" in df:
        rev = float(df["Total Income (Ex GST)"].sum())
    elif "Total Income" in df:
        rev = float(df["Total Income"].sum()) / 1.18
    else:
        rev = 0.0

    # Total Income is platform billing (Inc GST)
    if "Total Income" in df:
        total_income = float(df["Total Income"].sum())
    elif "Total Income (Ex GST)" in df:
        total_income = float(df["Total Income (Ex GST)"].sum()) * 1.18
    else:
        total_income = 0.0

    gst_amount = float(df["GST"].sum()) if "GST" in df else (total_income - rev if total_income and rev else 0.0)

    sellers = int(df["Seller Name"].nunique()) if "Seller Name" in df else 0
    buyers = int(df["Buyer Name"].nunique()) if "Buyer Name" in df else 0
    return {
        "transactions": n,
        "gmv": gmv,
        "revenue": rev,
        "total_income": total_income,
        "gst": gst_amount,
        "gst_amount": gst_amount,
        "avg_commission": rev / n if n else 0.0,
        "avg_total_income": total_income / n if n else 0.0,
        "avg_txn_value": gmv / n if n else 0.0,
        "take_rate": (rev / gmv * 100) if gmv else 0.0,
        "gross_take_rate": (total_income / gmv * 100) if gmv else 0.0,
        "unique_sellers": sellers,
        "unique_buyers": buyers,
        "txn_per_seller": n / sellers if sellers else 0.0,
        "purchases_per_buyer": n / buyers if buyers else 0.0,
    }


def period_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate to the FY-Month grain, correctly ordered across financial years."""
    if not {"FY", "Month"} <= set(df.columns) or df.empty:
        return pd.DataFrame()
    rev_col = "Total Income (Ex GST)" if "Total Income (Ex GST)" in df else "Total Income"
    agg_kwargs = dict(
        Transactions=("Final Bid Value", "size"),
        GMV=("Final Bid Value", "sum"),
        Revenue=(rev_col, "sum"),
        AvgBid=("Final Bid Value", "mean"),
        AvgCommission=(rev_col, "mean"),
        Sellers=("Seller Name", "nunique"),
        Buyers=("Buyer Name", "nunique"),
    )
    if "Total Income" in df:
        agg_kwargs["TotalIncome"] = ("Total Income", "sum")
    if "GST" in df:
        agg_kwargs["GST"] = ("GST", "sum")
    g = (df.groupby(["FY", "Month"], dropna=False)
           .agg(**agg_kwargs)
           .reset_index())
    g["_m"] = g["Month"].map(MONTH_INDEX)
    g = g.sort_values(["FY", "_m"]).reset_index(drop=True)
    g["Period"] = g["FY"].astype(str) + " · " + g["Month"].astype(str)
    g["TakeRate"] = np.where(g["GMV"] > 0, g["Revenue"] / g["GMV"] * 100, np.nan)
    if "TotalIncome" in g.columns:
        g["GrossTakeRate"] = np.where(g["GMV"] > 0, g["TotalIncome"] / g["GMV"] * 100, np.nan)
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
    rev_col = "Total Income (Ex GST)" if "Total Income (Ex GST)" in df else "Total Income"
    agg_kwargs = {
        count_name: ("Final Bid Value", "size"),
        "GMV": ("Final Bid Value", "sum"),
        "AvgTxnValue": ("Final Bid Value", "mean"),
        "Commission": (rev_col, "sum"),
        "AvgCommission": (rev_col, "mean"),
    }
    if "Total Income" in df and rev_col != "Total Income":
        agg_kwargs["TotalIncome"] = ("Total Income", "sum")
    if "GST" in df:
        agg_kwargs["GST"] = ("GST", "sum")
    g = (src.groupby(key, dropna=True)
           .agg(**agg_kwargs)
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
    rev_col = "Total Income (Ex GST)" if "Total Income (Ex GST)" in df else "Total Income"
    agg_kwargs = dict(
        Transactions=("Final Bid Value", "size"),
        GMV=("Final Bid Value", "sum"),
        Revenue=(rev_col, "sum"),
    )
    if "Total Income" in df and rev_col != "Total Income":
        agg_kwargs["TotalIncome"] = ("Total Income", "sum")
    g = (tmp.groupby("Band", observed=False)
            .agg(**agg_kwargs)
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
    work = df.drop(columns=[c for c in ("_month_idx", "Period", "GST") if c in df.columns])
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
    if {"Total Income (Ex GST)", "Final Bid Value"} <= set(work.columns):
        bad = (work["Total Income (Ex GST)"].notna() & work["Final Bid Value"].notna()
               & (work["Total Income (Ex GST)"] > work["Final Bid Value"]))
        checks.append(("Commission (Ex GST) never exceeds the bid value", int(bad.sum()), []))
        failing_mask |= bad
    if {"Total Income", "Final Bid Value"} <= set(work.columns):
        bad = (work["Total Income"].notna() & work["Final Bid Value"].notna()
               & (work["Total Income"] > work["Final Bid Value"]))
        checks.append(("Total Income never exceeds the bid value", int(bad.sum()), []))
        failing_mask |= bad
    if {"Total Income", "Total Income (Ex GST)"} <= set(work.columns):
        bad = (work["Total Income"].notna() & work["Total Income (Ex GST)"].notna()
               & (work["Total Income"] < work["Total Income (Ex GST)"]))
        checks.append(("Total Income (inc GST) >= Total Income (ex GST)", int(bad.sum()), []))
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
    for col in ("Final Bid Value", "Total Income (Ex GST)", "Total Income", "Odometer"):
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


# ─────────────────────────────────────────────────────────────────────────────
# EXPORT
# ─────────────────────────────────────────────────────────────────────────────
def export_normalised_workbook(
    df: pd.DataFrame,
    source_name: str = "",
    notes: list[str] | None = None,
    sheet_name: str = "Normalised Data",
) -> bytes:
    """
    Export the normalised DataFrame into a production-grade, formatted Excel (.xlsx) file.

    Features:
    - Internal helper columns (starting with '_', e.g. '_month_idx') are excluded.
    - Sheet 1 ('Normalised Data'):
        * Top header pane is frozen (row 1 fixed).
        * Auto-filter enabled across all table columns.
        * Styled headers with clean corporate dark fill and white bold text.
        * Number formatting for currency ('#,##0.00'), kilometres ('#,##0'), and Year ('0').
        * Auto-adjusted column widths so data is never clipped or displayed as '###'.
    - Sheet 2 ('Normalisation Audit'):
        * Ingestion summary (source file name, record count, timestamp).
        * Full audit log of normalisations applied.
    """
    clean_df = df.drop(columns=[c for c in df.columns if c.startswith("_")]).copy()

    # Place canonical columns first if present
    lead = [c for c in REQUIRED_COLUMNS if c in clean_df.columns]
    rest = [c for c in clean_df.columns if c not in lead]
    clean_df = clean_df[lead + rest]

    buf = io.BytesIO()

    try:
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter

        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            clean_df.to_excel(writer, index=False, sheet_name=sheet_name)
            ws = writer.sheets[sheet_name]

            # Freeze top header row and enable filters
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions

            hdr_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
            hdr_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")

            # Style header and detect numeric formatting
            for col_idx, col_name in enumerate(clean_df.columns, start=1):
                col_letter = get_column_letter(col_idx)
                hdr_cell = ws.cell(row=1, column=col_idx)
                hdr_cell.fill = hdr_fill
                hdr_cell.font = hdr_font
                hdr_cell.alignment = Alignment(horizontal="center", vertical="center")

                # Determine number format
                is_curr = any(k in col_name.lower() for k in ("value", "income", "gmv", "revenue", "price", "bid", "gst"))
                is_int = col_name in ("Odometer", "Year") or any(k in col_name.lower() for k in ("km", "count", "transactions"))
                fmt = "#,##0.00" if is_curr else ("#,##0" if is_int and col_name != "Year" else ("0" if col_name == "Year" else None))

                if fmt:
                    for cell in ws.iter_cols(min_col=col_idx, max_col=col_idx, min_row=2, max_row=len(clean_df) + 1):
                        for c in cell:
                            if c.value is not None:
                                c.number_format = fmt

                # Column width
                sample_vals = clean_df[col_name].dropna().head(120).astype(str).tolist()
                max_content = max([len(v) for v in sample_vals], default=0)
                col_width = max(max_content + 3, len(str(col_name)) + 4, 12)
                ws.column_dimensions[col_letter].width = min(col_width, 50)

            # ── Sheet 2: Audit & Ingestion Log ─────────────────────────────
            ws_audit = writer.book.create_sheet(title="Normalisation Audit")
            ws_audit.views.sheetView[0].showGridLines = True

            ws_audit["A1"] = "CONVERSION ANALYTICS — NORMALISATION AUDIT & SUMMARY"
            ws_audit["A1"].font = Font(name="Calibri", size=13, bold=True, color="0F172A")

            meta_rows = [
                ("Source File", source_name or "Uploaded workbook"),
                ("Export Timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                ("Normalised Records", f"{len(clean_df):,} rows"),
                ("Attributes / Columns", f"{len(clean_df.columns)} fields"),
            ]
            if "Final Bid Value" in clean_df.columns and clean_df["Final Bid Value"].notna().any():
                meta_rows.append(("Total GMV", f"{clean_df['Final Bid Value'].sum():,.2f}"))
            if "Total Income (Ex GST)" in clean_df.columns and clean_df["Total Income (Ex GST)"].notna().any():
                meta_rows.append(("Commission Revenue (Ex GST)", f"{clean_df['Total Income (Ex GST)'].sum():,.2f}"))
            if "Total Income" in clean_df.columns and clean_df["Total Income"].notna().any():
                meta_rows.append(("Total Platform Income (Inc GST)", f"{clean_df['Total Income'].sum():,.2f}"))
            if "GST" in clean_df.columns and clean_df["GST"].notna().any():
                meta_rows.append(("GST Component (18%)", f"{clean_df['GST'].sum():,.2f}"))

            for r_i, (k, v) in enumerate(meta_rows, start=3):
                ws_audit.cell(row=r_i, column=1, value=k).font = Font(name="Calibri", size=10, bold=True, color="334155")
                ws_audit.cell(row=r_i, column=2, value=v).font = Font(name="Calibri", size=10, color="475569")

            audit_start_row = len(meta_rows) + 4
            ws_audit.cell(row=audit_start_row, column=1, value="Normalisations & Rules Applied").font = Font(name="Calibri", size=11, bold=True, color="1E293B")
            if notes:
                for idx, note in enumerate(notes, start=audit_start_row + 1):
                    ws_audit.cell(row=idx, column=1, value=f"•  {note}").font = Font(name="Calibri", size=10, color="475569")
            else:
                ws_audit.cell(row=audit_start_row + 1, column=1, value="•  Dataset conformed to schema without warnings.").font = Font(name="Calibri", size=10, color="475569")

            ws_audit.column_dimensions["A"].width = 36
            ws_audit.column_dimensions["B"].width = 40

    except Exception:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            clean_df.to_excel(writer, index=False, sheet_name=sheet_name)

    return buf.getvalue()

