"""Phase 4 (figures): pull headline numbers out of filed accounts.

Companies House serves most small/micro company accounts as **iXBRL**
(`application/xhtml+xml`) — machine-readable XML with each number tagged by a
standard FRS taxonomy concept. We parse those tags directly, so we get real
figures (net worth, cash, headcount, and turnover/profit when disclosed)
without guessing from prose.

Large *group* (consolidated) accounts are usually filed as **PDF only**, and
those PDFs are frequently scanned images with no text layer — so they cannot be
parsed reliably here. For those we download the PDF and flag it for a human (or
a vision-capable agent) to read; see `fetch_accounts_pdf`.

Dependency policy: iXBRL parsing uses only the standard library (regex over the
XML). PDF download uses the API client. No heavyweight deps required.
"""

from __future__ import annotations

import re
from typing import Optional

from .client import CompaniesHouseClient

# Headline concepts we care about, keyed by the iXBRL local name (the part after
# the ':' — works whether the prefix is frs-core, core, uk-bus, etc.).
# Order matters: this is the order we present them.
HEADLINE_CONCEPTS = [
    # label,                      iXBRL local-name(s)
    ("Turnover / revenue",        ["Turnover", "TurnoverRevenue", "Revenue"]),
    ("Gross profit",              ["GrossProfitLoss"]),
    ("Operating profit",          ["OperatingProfitLoss"]),
    ("Profit/(loss) before tax",  ["ProfitLossBeforeTax", "ProfitLossOnOrdinaryActivitiesBeforeTax"]),
    ("Profit/(loss) for year",    ["ProfitLoss", "ComprehensiveIncomeExpense"]),
    ("Net assets (net worth)",    ["NetAssetsLiabilities"]),
    ("Total equity",             ["Equity"]),
    ("Cash at bank",              ["CashBankOnHand", "CashBankInHand"]),
    ("Net current assets",        ["NetCurrentAssetsLiabilities"]),
    ("Total assets less current liabilities", ["TotalAssetsLessCurrentLiabilities"]),
    ("Average employees",         ["AverageNumberEmployeesDuringPeriod"]),
]

_FACT_RE = re.compile(
    r"<ix:nonFraction\b([^>]*)>(.*?)</ix:nonFraction>", re.S | re.I)
_ATTR_RE = re.compile(r'([\w:.-]+)\s*=\s*"([^"]*)"')
_CTX_RE = re.compile(
    r'<xbrli:context\s+id="([^"]+)"\s*>(.*?)</xbrli:context>', re.S | re.I)
_INSTANT_RE = re.compile(r"<xbrli:instant>([^<]+)</xbrli:instant>", re.I)
_ENDDATE_RE = re.compile(r"<xbrli:endDate>([^<]+)</xbrli:endDate>", re.I)
_DIM_RE = re.compile(r"explicitMember|<xbrldi:|<xbrli:segment", re.I)


def _local(name: str) -> str:
    return name.split(":", 1)[-1]


def _parse_contexts(xml: str) -> dict:
    """id -> {'date': 'YYYY-MM-DD' or None, 'dimensioned': bool}."""
    out = {}
    for cid, body in _CTX_RE.findall(xml):
        m = _INSTANT_RE.search(body) or _ENDDATE_RE.search(body)
        out[cid] = {
            "date": m.group(1).strip()[:10] if m else None,
            "dimensioned": bool(_DIM_RE.search(body)),
        }
    return out


def _to_number(text: str, attrs: dict) -> Optional[float]:
    raw = re.sub(r"<[^>]+>", "", text)  # strip nested spans
    raw = raw.replace(",", "").replace("\xa0", "").strip()
    if not raw or not re.search(r"\d", raw):
        return None
    neg = raw.startswith("(") and raw.endswith(")")
    raw = raw.strip("()")
    try:
        val = float(raw)
    except ValueError:
        return None
    scale = attrs.get("scale")
    if scale:
        try:
            val *= 10 ** int(scale)
        except ValueError:
            pass
    if attrs.get("sign") == "-":
        val = -val
    if neg:
        val = -val
    return val


def parse_ixbrl(xml: str) -> dict:
    """Extract headline figures for the current and prior period.

    Returns {'current': {...}, 'prior': {...}, 'current_date', 'prior_date'}
    where each {...} maps our human label -> number. Only undimensioned
    (whole-entity) facts are used, so we get balance-sheet/P&L totals rather
    than per-segment breakdowns.
    """
    contexts = _parse_contexts(xml)
    # collect, per concept-local-name, the undimensioned facts with a date
    facts: dict[str, list[tuple[str, float]]] = {}
    for attr_str, body in _FACT_RE.findall(xml):
        attrs = dict(_ATTR_RE.findall(attr_str))
        name = _local(attrs.get("name", ""))
        if not name:
            continue
        ctx = contexts.get(attrs.get("contextRef", ""))
        if not ctx or ctx["dimensioned"] or not ctx["date"]:
            continue
        val = _to_number(body, attrs)
        if val is None:
            continue
        facts.setdefault(name, []).append((ctx["date"], val))

    # the two reporting period-ends present across the doc
    all_dates = sorted({d for lst in facts.values() for d, _ in lst})
    current_date = all_dates[-1] if all_dates else None
    prior_date = all_dates[-2] if len(all_dates) >= 2 else None

    def pick(localnames, date):
        for ln in localnames:
            for d, v in facts.get(ln, []):
                if d == date:
                    return v
        return None

    current, prior = {}, {}
    for label, names in HEADLINE_CONCEPTS:
        cv = pick(names, current_date)
        pv = pick(names, prior_date) if prior_date else None
        if cv is not None:
            current[label] = cv
        if pv is not None:
            prior[label] = pv
    return {
        "current": current, "prior": prior,
        "current_date": current_date, "prior_date": prior_date,
    }


def fetch_latest_accounts_doc(client: CompaniesHouseClient, number: str) -> Optional[dict]:
    """Return metadata about the latest accounts filing, incl. available formats.

    {'date','description','metadata_url','formats':{'application/pdf':..,
     'application/xhtml+xml':..}} or None.
    """
    fh = client.filing_history(number, category="accounts", items_per_page=1)
    items = fh.get("items", []) if fh else []
    if not items:
        return None
    it = items[0]
    meta_url = (it.get("links") or {}).get("document_metadata")
    formats = {}
    if meta_url:
        try:
            meta = client.get("", base=meta_url, use_cache=True)
            formats = (meta or {}).get("resources", {}) or {}
        except Exception:
            pass
    return {
        "date": it.get("date"),
        "description": it.get("description"),
        "metadata_url": meta_url,
        "formats": formats,
    }


def fetch_figures(client: CompaniesHouseClient, number: str) -> Optional[dict]:
    """Best-effort headline figures for a company from its latest iXBRL accounts.

    Returns the parse_ixbrl() dict plus 'source' metadata, or None when no
    iXBRL is available (e.g. PDF-only group accounts)."""
    doc = fetch_latest_accounts_doc(client, number)
    if not doc or "application/xhtml+xml" not in (doc.get("formats") or {}):
        return None
    try:
        xml = client.document_content(doc["metadata_url"], "application/xhtml+xml")
    except Exception:
        xml = None
    if not xml:
        return None
    parsed = parse_ixbrl(xml)
    parsed["filing_date"] = doc["date"]
    parsed["description"] = doc["description"]
    parsed["metadata_url"] = doc["metadata_url"]
    return parsed


def fetch_accounts_pdf(client: CompaniesHouseClient, metadata_url: str,
                       dest) -> dict:
    """Download an accounts PDF to `dest`. Reports whether it has a text layer.

    Returns {'path', 'bytes', 'has_text'}; has_text=False usually means the
    accounts were filed as a scanned image and need a human / vision pass."""
    data = client.document_content(metadata_url, "application/pdf", binary=True)
    from pathlib import Path
    p = Path(dest)
    p.write_bytes(data)
    has_text = False
    try:
        from pypdf import PdfReader
        r = PdfReader(str(p))
        has_text = any((pg.extract_text() or "").strip() for pg in r.pages[:15])
    except Exception:
        pass
    return {"path": str(p), "bytes": len(data), "has_text": has_text}
