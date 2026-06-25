"""Phase 1: extract identifying information from a company web page.

The goal is NOT to read marketing prose, but to mine the high-signal parts of
the HTML (footer, JSON-LD, structured contact blocks) for identifiers that let
us anchor deterministically on Companies House:

    - UK company registration number
    - VAT number
    - legal entity name(s)
    - registered-office address / postcode
    - contact emails and phone numbers

Dependency-free: uses only the standard library + regex so it runs anywhere.
"""

from __future__ import annotations

import re
import json
import html
import logging
from dataclasses import dataclass, field
from typing import Optional
from urllib.request import Request, urlopen
from urllib.parse import urljoin, urldefrag, urlparse

LOG = logging.getLogger("ch.scrape")

UA = "Mozilla/5.0 (compatible; ch-diligence/1.0)"

# Pages a UK company is most likely to publish its registered number / office on.
# Weights bias the bounded crawl towards legal/privacy pages first.
LEGAL_LINK_KEYWORDS = {
    "privacy": 5, "legal": 5, "impressum": 5, "imprint": 5,
    "terms": 4, "disclaimer": 4, "company-information": 4, "company-info": 4,
    "cookie": 3, "about": 2, "contact": 2,
}
# Anchor hrefs (and their visible text) on the start page.
_ANCHOR_RE = re.compile(
    r"<a\b[^>]*?href=[\"']([^\"'#?]+)[^\"']*[\"'][^>]*>(.*?)</a>",
    re.I | re.S,
)

# 8-char CH numbers, or 2-letter prefix + 6 digits (SC, NI, OC, etc.)
COMPANY_NO_RE = re.compile(
    r"(?:compan(?:y|ies)\s*(?:house\s*)?(?:registration\s*)?(?:number|no\.?|reg(?:istration)?\s*no\.?)"
    r"|registered\s+(?:in\s+\w+\s+)?(?:number|no\.?))\s*[:#]?\s*"
    r"([A-Z]{0,2}\s?\d{6,8})",
    re.I,
)
VAT_LABEL_RE = re.compile(r"vat\s*(?:reg(?:istration)?\.?\s*)?(?:number|no\.?|id)?\s*[:#]?\s*(GB)?\s?(\d[\d\s]{7,13}\d)", re.I)
POSTCODE_RE = re.compile(r"\b([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})\b")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
LEGAL_NAME_RE = re.compile(r"[A-Z][A-Za-z0-9&'.,\- ]{2,60}?\s(?:Limited|Ltd\.?|PLC|LLP|Group|Holdings)\b")


@dataclass
class Identifiers:
    url: str
    company_numbers: list[str] = field(default_factory=list)
    vat_numbers: list[str] = field(default_factory=list)
    legal_names: list[str] = field(default_factory=list)
    postcodes: list[str] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)
    addresses: list[str] = field(default_factory=list)
    jsonld_orgs: list[dict] = field(default_factory=list)
    pages_read: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def fetch(url: str, timeout: int = 30) -> str:
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")


def discover_legal_links(base_url: str, htmltext: str, limit: int = 6) -> list[str]:
    """Find same-host legal/privacy/contact pages linked from a start page.

    UK companies must publish their registered number and office somewhere,
    usually a legal or privacy page rather than the page you were handed. We
    rank candidate links by keyword hits in the href and anchor text, keep only
    same-host (or relative) links, dedupe, and return the top ``limit`` as
    absolute URLs, highest-value first.
    """
    base_host = (urlparse(base_url).netloc or "").lower()
    scored: dict[str, int] = {}
    for href, inner in _ANCHOR_RE.findall(htmltext):
        text = re.sub(r"<[^>]+>", " ", inner)
        blob = f"{href} {html.unescape(text)}".lower()
        score = sum(w for kw, w in LEGAL_LINK_KEYWORDS.items() if kw in blob)
        if score <= 0:
            continue
        absolute = urldefrag(urljoin(base_url, href.strip()))[0]
        p = urlparse(absolute)
        if p.scheme not in ("http", "https"):
            continue
        if p.netloc.lower() != base_host:        # same host only (bounded, polite)
            continue
        if absolute.rstrip("/") == base_url.rstrip("/"):
            continue
        scored[absolute] = max(scored.get(absolute, 0), score)
    return [u for u, _ in sorted(scored.items(), key=lambda kv: -kv[1])][:limit]


def _merge_ids(into: "Identifiers", other: "Identifiers") -> None:
    """Union the list fields of ``other`` into ``into`` (order-preserving dedupe)."""
    into.company_numbers = _dedupe([*into.company_numbers, *other.company_numbers])
    into.vat_numbers = _dedupe([*into.vat_numbers, *other.vat_numbers])
    into.legal_names = _dedupe([*into.legal_names, *other.legal_names])[:15]
    into.postcodes = _dedupe([*into.postcodes, *other.postcodes])[:10]
    into.emails = _dedupe([*into.emails, *other.emails])[:10]
    into.addresses = _dedupe([*into.addresses, *other.addresses])
    into.jsonld_orgs.extend(other.jsonld_orgs)


def extract_site(url: str, htmltext: Optional[str] = None, *,
                 follow: bool = True, max_pages: int = 6,
                 timeout: int = 30) -> Identifiers:
    """Phase 1 with bounded auto-following of legal/privacy pages.

    Extracts the start page, then -- unless a company number is already found,
    or ``follow`` is off -- fetches the top same-host legal/privacy/contact
    links and merges their identifiers in. Short-circuits as soon as a company
    number appears, so it is cheap in the common case. Each fetch is isolated:
    a failure on one page is logged and skipped, never fatal.

    ``htmltext`` (e.g. a saved HTML file) disables following, since there are
    no further pages to fetch.
    """
    if htmltext is not None:
        ids = extract(url, htmltext)
        ids.pages_read = [url]
        return ids

    start_html = fetch(url, timeout=timeout)
    ids = extract(url, start_html)
    ids.pages_read = [url]
    if not follow or ids.company_numbers:
        return ids

    for link in discover_legal_links(url, start_html, limit=max_pages):
        try:
            page = fetch(link, timeout=timeout)
        except Exception as e:                   # network / decode / 404 etc.
            LOG.debug("skip %s: %s", link, e)
            continue
        _merge_ids(ids, extract(link, page))
        ids.pages_read.append(link)
        if ids.company_numbers:                   # found the anchor -> stop early
            break
    return ids


def _visible_text(htmltext: str) -> str:
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", htmltext, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", html.unescape(t))


def _dedupe(seq):
    seen, out = set(), []
    for x in seq:
        k = re.sub(r"\s+", "", x).upper()
        if k and k not in seen:
            seen.add(k)
            out.append(x.strip())
    return out


def _norm_company_no(raw: str) -> str:
    s = re.sub(r"\s+", "", raw).upper()
    if s.isdigit():
        return s.zfill(8)
    return s


def extract_jsonld(htmltext: str) -> list[dict]:
    orgs = []
    for m in re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        htmltext, flags=re.S | re.I,
    ):
        try:
            data = json.loads(m.strip())
        except Exception:
            continue
        nodes = data.get("@graph", data) if isinstance(data, dict) else data
        if isinstance(nodes, dict):
            nodes = [nodes]
        for n in nodes if isinstance(nodes, list) else []:
            if isinstance(n, dict) and "Organization" in str(n.get("@type", "")):
                orgs.append(n)
    return orgs


def extract(url: str, htmltext: Optional[str] = None) -> Identifiers:
    if htmltext is None:
        htmltext = fetch(url)
    text = _visible_text(htmltext)
    ids = Identifiers(url=url)

    # company numbers: only labelled matches (high precision)
    labelled = [_norm_company_no(m) for m in COMPANY_NO_RE.findall(htmltext)]
    labelled += [_norm_company_no(m) for m in COMPANY_NO_RE.findall(text)]
    ids.company_numbers = _dedupe(labelled)

    # VAT
    vats = []
    for m in VAT_LABEL_RE.findall(htmltext + " " + text):
        vats.append((m[0] or "") + re.sub(r"\s+", "", m[1]))
    ids.vat_numbers = _dedupe(vats)

    # legal names, postcodes, emails from full text
    ids.legal_names = _dedupe(LEGAL_NAME_RE.findall(text))[:15]
    ids.postcodes = _dedupe(POSTCODE_RE.findall(text))[:10]
    ids.emails = _dedupe(EMAIL_RE.findall(htmltext))[:10]

    # JSON-LD orgs (names, vatID, addresses)
    ids.jsonld_orgs = extract_jsonld(htmltext)
    for org in ids.jsonld_orgs:
        if org.get("name"):
            ids.legal_names = _dedupe([org["name"], *ids.legal_names])
        if org.get("vatID"):
            ids.vat_numbers = _dedupe([org["vatID"], *ids.vat_numbers])
        addr = org.get("address")
        addrs = addr if isinstance(addr, list) else ([addr] if addr else [])
        for a in addrs:
            if isinstance(a, dict):
                parts = [a.get("streetAddress"), a.get("addressLocality"),
                         a.get("addressRegion"), a.get("postalCode"),
                         a.get("addressCountry")]
                ids.addresses.append(", ".join(p for p in parts if p))

    return ids
