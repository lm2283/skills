"""CLI: discover and classify a company's corporate structure.

Usage:
    python -m companies_house_diligence.cli --url https://www.example.com/about/
    python -m companies_house_diligence.cli --number 01234567
    python -m companies_house_diligence.cli --url ... --html saved.html --stem ACME

Outputs (into a per-company subdir <out>/<number>_<name-slug>/):
    identifiers.json   extracted page identifiers
    structure.graphml  the discovery graph (open in Gephi/yEd)
    structure.json     nodes + edges + classifications
"""

from __future__ import annotations

import os
import re
import json
import argparse
import logging
from pathlib import Path

from .client import CompaniesHouseClient
from .graph import StructureGraph, company_id
from .scrape import extract, extract_site, Identifiers
from . import discover


def main(argv=None):
    ap = argparse.ArgumentParser(description="Companies House structure discovery")
    ap.add_argument("--url", help="company web page (ideally /about or /contact)")
    ap.add_argument("--html", help="path to a saved HTML file (skip fetching)")
    ap.add_argument("--no-follow", dest="follow", action="store_false",
                    help="do not auto-follow same-site legal/privacy pages when "
                         "the start page has no company number")
    ap.add_argument("--max-pages", type=int, default=6,
                    help="max legal/privacy pages to auto-follow (default 6)")
    ap.add_argument("--number", help="anchor directly on this company number")
    ap.add_argument("--stem", help="name stem for member discovery (default: first token of anchor name)")
    ap.add_argument("--out", default="output", help="output root; a per-company subdirectory is created inside it")
    ap.add_argument("--cache", default=".ch_cache", help="API cache dir ('' to disable)")
    ap.add_argument("--max-candidates", type=int, default=40,
                    help="cap on name-stem search hits expanded as candidate "
                         "group members")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(name)s %(levelname)s %(message)s")
    root = Path(args.out)

    client = CompaniesHouseClient(cache_dir=args.cache or None)
    sg = StructureGraph()

    # ---- Phase 1: identifiers --------------------------------------------
    ids = Identifiers(url=args.number or "")
    if args.url or args.html:
        htmltext = Path(args.html).read_text(encoding="utf-8", errors="ignore") if args.html else None
        ids = extract_site(args.url or "(local html)", htmltext,
                           follow=args.follow, max_pages=args.max_pages)
        print(f"[1] identifiers: numbers={ids.company_numbers} vat={ids.vat_numbers} "
              f"postcodes={ids.postcodes[:3]}")
        if len(ids.pages_read) > 1:
            print(f"    pages read: {', '.join(ids.pages_read)}")

    # ---- Phase 2: anchor -------------------------------------------------
    if args.number:
        anchor_num, method, conf = args.number, "explicit", "high"
    else:
        ar = discover.anchor(client, ids)
        anchor_num, method, conf = ar.company_number, ar.method, ar.confidence
    if not anchor_num:
        print("Could not anchor on a company. Provide --number.")
        return 2
    prof = client.company(anchor_num)
    # per-company output subdirectory: <root>/<number>_<name-slug>
    slug = re.sub(r"[^a-z0-9]+", "-",
                  (prof.get("company_name") or "").lower()).strip("-")[:50]
    out = root / f"{anchor_num}_{slug}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "identifiers.json").write_text(json.dumps(ids.to_dict(), indent=2),
                                          encoding="utf-8")
    print(f"[2] anchor: {anchor_num} {prof.get('company_name')} "
          f"(method={method}, confidence={conf})")
    print(f"    output dir: {out}")

    # ---- Phase 3: walk up ------------------------------------------------
    chain = discover.walk_up(client, sg, anchor_num)
    print(f"[3] ownership chain ({len(chain)} levels):")
    for i, num in enumerate(chain):
        n = sg.g.nodes.get(company_id(num), {})
        print(f"      {'  '*i}^ {n.get('name')} ({num})")
    # report ultimate external owner if any
    for nid, d in sg.g.nodes(data=True):
        if d.get("kind") == "external":
            print(f"      ~ external controller: {d.get('name')} "
                  f"[{d.get('jurisdiction','')}]")

    # ---- Phase 3b: discover members -------------------------------------
    stem = args.stem or (prof.get("company_name", "").split()[0] if prof else "")
    # probe the anchor's true registered-office postcode as well as any scraped
    # ones, so a shared-service office is recognised even if the page omitted it.
    office_pc = (prof.get("registered_office_address", {}) or {}).get("postal_code", "")
    postcodes = ([office_pc] if office_pc else []) + [
        p for p in ids.postcodes if p != office_pc]
    added = discover.discover_members(client, sg, stem, postcodes,
                                      max_candidates=args.max_candidates)
    print(f"[3b] discovered {len(added)} candidate companies (stem='{stem}')")

    # ---- Classification --------------------------------------------------
    results = discover.classify(sg, anchor_num)
    by_label: dict[str, list] = {}
    for r in results:
        by_label.setdefault(r.label, []).append(r)
    print("[4] classification:")
    for label in ("Confirmed", "Probable", "Possible", "Excluded"):
        rows = by_label.get(label, [])
        print(f"    {label}: {len(rows)}")
        for r in rows:
            ev = ("  | " + "; ".join(r.evidence)) if r.evidence else ""
            print(f"        - {r.name} ({r.company_number}){ev}")

    # ---- persist ---------------------------------------------------------
    sg.to_graphml(str(out / "structure.graphml"))
    dump = {
        "anchor": anchor_num, "method": method, "confidence": conf,
        "ownership_chain": chain,
        "classifications": [r.__dict__ for r in results],
        "api_calls": client.call_count,
    }
    (out / "structure.json").write_text(json.dumps(dump, indent=2), encoding="utf-8")
    print(f"[5] wrote {out}/structure.graphml and structure.json "
          f"({client.call_count} API calls)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
