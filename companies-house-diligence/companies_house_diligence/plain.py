"""Plain-language helpers for the brief: turn codes and raw numbers into
sentences a non-finance reader can act on.

Kept deliberately small and generic. No company-specific logic.
"""

from __future__ import annotations

from typing import Optional

# A small map of the SIC codes most common among the companies this skill is
# pointed at (tech, software, services). Unknown codes degrade gracefully to
# "SIC <code>". This is a convenience, not an authority.
SIC_PLAIN = {
    "62012": "software development (bespoke)",
    "62020": "IT consultancy",
    "62090": "IT services",
    "62011": "computer programming",
    "63110": "data processing & hosting",
    "63120": "web portals",
    "58210": "publishing computer games",
    "58290": "publishing other software",
    "82990": "other business support services",
    "70229": "management consultancy",
    "70100": "head-office / holding-company activities",
    "64209": "holding company",
    "64999": "financial services n.e.c.",
    "46510": "wholesale of computers & software",
    "47410": "retail of computers",
    "26200": "manufacture of computers",
    "73110": "advertising agency",
    "74909": "professional services n.e.c.",
}


def sic_plain(codes) -> str:
    if not codes:
        return "not stated"
    if isinstance(codes, str):
        codes = [c.strip() for c in codes.replace(";", ",").split(",") if c.strip()]
    parts = []
    for c in codes:
        parts.append(SIC_PLAIN.get(c, f"SIC {c}"))
    return ", ".join(parts)


def money(v: Optional[float]) -> str:
    """Readable money: £506k, £1.2m, £(491k) for negatives."""
    if v is None:
        return "n/a"
    neg = v < 0
    a = abs(v)
    if a >= 1_000_000:
        s = f"£{a/1_000_000:.1f}m"
    elif a >= 1_000:
        s = f"£{a/1_000:.0f}k"
    else:
        s = f"£{a:.0f}"
    return f"({s})" if neg else s


def pct_change(cur: Optional[float], prior: Optional[float]) -> Optional[float]:
    if cur is None or prior in (None, 0):
        return None
    return (cur - prior) / abs(prior) * 100.0


def trend_phrase(cur: Optional[float], prior: Optional[float],
                 noun: str = "") -> str:
    p = pct_change(cur, prior)
    if p is None:
        return ""
    if abs(p) < 0.5:
        return "no material change"
    word = "up" if p > 0 else "down"
    return f"{word} {abs(p):.0f}% year on year"


def company_age(incorporated_on: Optional[str]) -> Optional[int]:
    if not incorporated_on:
        return None
    try:
        import datetime as _dt
        y = int(incorporated_on[:4])
        return _dt.date.today().year - y
    except Exception:
        return None


def size_band(employees: Optional[float], net_worth: Optional[float],
              is_group: bool) -> str:
    """Rough plain-language size, for prioritisation only."""
    e = employees or 0
    if is_group:
        return "large group"
    if e >= 250:
        return "large"
    if e >= 50:
        return "mid-sized"
    if e >= 10:
        return "small"
    if e >= 1:
        return "micro"
    # fall back to net worth when headcount not disclosed
    if net_worth is not None:
        if net_worth >= 5_000_000:
            return "mid-sized (by balance sheet)"
        if net_worth >= 500_000:
            return "small (by balance sheet)"
    return "micro / owner-managed"
