"""Phase 1: fetch the raw HTML of a company web page (no parsing).

The job here is deliberately small: download the page (and, optionally, a few
likely legal/privacy/contact pages on the same site) and hand the raw HTML
back. We do **not** parse identifiers out of it -- a capable agent reads the
HTML directly and far more reliably than any regex, picking out the company
registration number, registered office, VAT number and legal name by eye.

UK companies must publish their registered number and office somewhere, usually
the footer or a legal/privacy page, so following a handful of those pages gives
the agent the best chance of finding the killer identifier (the 8-digit, or
2-letter-prefixed, company number).

Dependency-free: standard library only, so it runs anywhere (including a locked
down Windows box with no extra packages).
"""

from __future__ import annotations

import re
import html
import logging
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urljoin, urldefrag, urlparse

LOG = logging.getLogger("ch.scrape")

UA = "Mozilla/5.0 (compatible; ch-diligence/1.0)"

# Pages a UK company is most likely to publish its registered number / office
# on. Weights bias the bounded crawl towards legal/privacy pages first.
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


def fetch(url: str, timeout: int = 30) -> str:
    """Download a URL and return its body decoded as text (best effort)."""
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")


def discover_legal_links(base_url: str, htmltext: str, limit: int = 6) -> list[str]:
    """Find same-host legal/privacy/contact pages linked from a start page.

    Ranks candidate links by keyword hits in the href and anchor text, keeps
    only same-host (or relative) links, dedupes, and returns the top ``limit``
    as absolute URLs, highest-value first.
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


def fetch_pages(url: str, *, follow: bool = True, max_pages: int = 6,
                timeout: int = 30) -> list[tuple[str, str]]:
    """Fetch the start page and, optionally, its top legal/privacy/contact pages.

    Returns an ordered list of ``(url, html)``. The start page is always first.
    Each extra fetch is isolated: a failure on one page is logged and skipped,
    never fatal. No parsing happens here.
    """
    start_html = fetch(url, timeout=timeout)
    pages: list[tuple[str, str]] = [(url, start_html)]
    if not follow:
        return pages
    for link in discover_legal_links(url, start_html, limit=max_pages):
        try:
            pages.append((link, fetch(link, timeout=timeout)))
        except Exception as e:                   # network / decode / 404 etc.
            LOG.debug("skip %s: %s", link, e)
    return pages


def _slug(url: str) -> str:
    p = urlparse(url)
    path = (p.path or "").strip("/").replace("/", "-") or "index"
    return re.sub(r"[^a-z0-9-]+", "-", path.lower()).strip("-")[:60] or "page"


def save_pages(pages: list[tuple[str, str]], outdir) -> list[Path]:
    """Write fetched pages to ``outdir`` as ``page_NN_<slug>.html``; return paths."""
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for i, (u, body) in enumerate(pages, 1):
        dest = out / f"page_{i:02d}_{_slug(u)}.html"
        dest.write_text(body, encoding="utf-8")
        written.append(dest)
    return written


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(
        description="Fetch raw HTML of a company page (and likely legal pages) "
                    "for an agent to read. No parsing is done.")
    ap.add_argument("url", help="company web page (ideally /about, /contact or /legal)")
    ap.add_argument("--out", default="output/_scrape",
                    help="directory to write the .html files into")
    ap.add_argument("--no-follow", dest="follow", action="store_false",
                    help="fetch only the given page; do not follow legal/privacy links")
    ap.add_argument("--max-pages", type=int, default=6,
                    help="max legal/privacy/contact pages to also fetch (default 6)")
    args = ap.parse_args(argv)
    pages = fetch_pages(args.url, follow=args.follow, max_pages=args.max_pages)
    written = save_pages(pages, args.out)
    print(f"fetched {len(written)} page(s) into {args.out}:")
    for p in written:
        print(f"  {p}")
    print("\nNext: read these files and find the company registration number "
          "(8 digits, or a 2-letter prefix + 6 digits such as SC/NI/OC), then "
          "anchor with:  python -m companies_house_diligence.cli --number <NUMBER>")


if __name__ == "__main__":
    main()
