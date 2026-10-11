"""
Number formatting shared by every surface that shows a figure.

The dashboard cards, the CSV export and the assistant all read from the same
helpers, so a number never appears in two different shapes in the same session.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["inr", "inr_full", "num", "pct", "signed_pct"]


def _nan(v) -> bool:
    if v is None:
        return True
    try:
        return bool(pd.isna(v))
    except (TypeError, ValueError):
        return False


def inr(v: float) -> str:
    """Compact Indian-notation currency: ₹1.23 Cr, ₹4.56 L, ₹7.8 K, ₹940."""
    if _nan(v):
        return "—"
    v = float(v)
    sign = "-" if v < 0 else ""
    a = abs(v)
    if a >= 1e7:
        return f"{sign}₹{a / 1e7:,.2f} Cr"
    if a >= 1e5:
        return f"{sign}₹{a / 1e5:,.2f} L"
    if a >= 1e3:
        return f"{sign}₹{a / 1e3:,.1f} K"
    return f"{sign}₹{a:,.0f}"


def inr_full(v: float) -> str:
    """Unabbreviated currency, for tables where the exact rupee matters."""
    return "—" if _nan(v) else f"₹{float(v):,.0f}"


def num(v: float, dec: int = 0) -> str:
    if _nan(v):
        return "—"
    return f"{float(v):,.{dec}f}"


def pct(v: float, dec: int = 2) -> str:
    """``v`` is already expressed in percent, not as a fraction."""
    if _nan(v):
        return "—"
    return f"{float(v):,.{dec}f}%"


def signed_pct(v: float, dec: int = 1) -> str:
    if _nan(v):
        return "—"
    v = float(v)
    return f"{'+' if v >= 0 else '−'}{abs(v):,.{dec}f}%"


# ``np`` is imported for callers that pass numpy scalars; referenced here so
# linters do not strip the import.
_ = np
