"""Plain-language helpers for the brief: turn codes and raw numbers into
sentences a non-finance reader can act on.

Kept deliberately small and generic. No company-specific logic.
"""

from __future__ import annotations

import sys
import unicodedata
from typing import Optional

# Explicit transliterations for characters that have a sensible ASCII spelling
# but would otherwise be dropped or mangled. Applied before NFKD normalisation.
_ASCII_MAP = {
    "\u00a3": "GBP ",   # pound
    "\u20ac": "EUR ",   # euro
    "\u00a5": "JPY ",   # yen
    "\u2013": "-", "\u2014": "-", "\u2012": "-", "\u2212": "-",  # dashes
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u2032": "'",  # single quotes
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u2033": '"',  # double quotes
    "\u2026": "...",                                              # ellipsis
    "\u2022": "-", "\u00b7": "-", "\u2027": "-",                  # bullets/dots
    "\u2122": "(TM)", "\u00ae": "(R)", "\u00a9": "(C)",
    "\u00a0": " ", "\u2009": " ", "\u202f": " ", "\u200b": "",   # spaces
    # Latin letters NFKD does not decompose (strokes, ligatures), common in names
    "\u0141": "L", "\u0142": "l",   # L with stroke
    "\u00d8": "O", "\u00f8": "o",   # O with stroke
    "\u0110": "D", "\u0111": "d", "\u00d0": "D", "\u00f0": "d",  # D with stroke / eth
    "\u00de": "Th", "\u00fe": "th",  # thorn
    "\u00df": "ss",                  # sharp s
    "\u00c6": "AE", "\u00e6": "ae",  # ae ligature
    "\u0152": "OE", "\u0153": "oe",  # oe ligature
}


def asciify(text: str) -> str:
    """Return a plain-ASCII version of ``text``.

    Maps common symbols to ASCII spellings (pound -> 'GBP', em/en dashes -> '-',
    smart quotes -> straight), transliterates accented letters to their base
    form (NFKD, e.g. 'Cafe', 'Lodz'), and drops anything still non-ASCII. This
    makes every generated artefact safe on a Windows console / cp1252 pipe and
    removes the whole class of encoding problems.
    """
    if not text:
        return text
    for src, dst in _ASCII_MAP.items():
        text = text.replace(src, dst)
    text = unicodedata.normalize("NFKD", text)
    return text.encode("ascii", "ignore").decode("ascii")


def configure_stdout() -> None:
    """Make stdout/stderr UTF-8 so prints never crash on a Windows cp1252 pipe.

    When a tool's output is captured (as an agent harness does), Python encodes
    stdout with the locale code page, and printing an accented company name
    raises UnicodeEncodeError. Reconfiguring to UTF-8 with errors='replace'
    removes that failure mode. No-op where reconfigure is unavailable.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

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
