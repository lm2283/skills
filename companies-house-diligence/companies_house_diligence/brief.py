"""Phase 7: render a professional, plain-language company brief.

Reads the discovery outputs (structure.json + structure.graphml), runs the
Phase 4-6 enrichment, pulls headline figures from filed accounts (iXBRL where
available; downloads group PDFs otherwise), (re)generates the confirmed
ownership tree, and writes a single Markdown brief.

The brief is written for a reader without a finance background, in a measured,
presentable register: a short summary paragraph at the top, then plain headings,
plain tables, and minimal styling. Facts carry numbered citations to the
Companies House page or filing they came from; a References list and a Caveats
section sit at the foot. Sections with nothing to report are omitted.

    python -m companies_house_diligence.brief --out output/<dir>
        [--no-financials] [--no-risk] [--download-accounts]

Run the discovery CLI first so that <dir>/structure.json exists.
"""

from __future__ import annotations

import json
import os
import shutil
import argparse
import subprocess
import datetime as _dt
from pathlib import Path
from typing import Optional

import networkx as nx

from .client import CompaniesHouseClient
from . import enrich, accounts, plain

OFFSHORE = {"jersey", "guernsey", "luxembourg", "cayman", "cayman islands",
            "isle of man", "bermuda", "british virgin islands"}
PE_TOKENS = ("BIDCO", "MIDCO", "TOPCO", "DEBTCO", "HOLDCO", "FINCO", "NEWCO")
CH_WEB = "https://find-and-update.company-information.service.gov.uk"


def _profile_url(num): return f"{CH_WEB}/company/{num}"
def _charges_url(num): return f"{CH_WEB}/company/{num}/charges"
def _officers_url(num): return f"{CH_WEB}/company/{num}/officers"
def _filings_url(num): return f"{CH_WEB}/company/{num}/filing-history"
def _psc_url(num): return f"{CH_WEB}/company/{num}/persons-with-significant-control"


class Cites:
    """Collects numbered citations, de-duplicated by URL."""

    def __init__(self):
        self.items = []        # [(label, url)]
        self._by_url = {}

    def ref(self, label: str, url: str) -> str:
        if not url:
            return ""
        if url in self._by_url:
            return f" [{self._by_url[url]}]"
        n = len(self.items) + 1
        self._by_url[url] = n
        self.items.append((label, url))
        return f" [{n}]"

    def render(self) -> list[str]:
        return [f"{i}. {label}: {url}"
                for i, (label, url) in enumerate(self.items, 1)]


def _node_attrs_by_number(g) -> dict:
    out = {}
    for n, d in g.nodes(data=True):
        if d.get("kind") == "company" and d.get("company_number"):
            out[d["company_number"]] = d
    return out


def _external_controllers(g, ingroup_numbers) -> list[dict]:
    """External (non-UK-resolved) controller nodes that actually control an
    in-group company (anchor, a chain link, or a Confirmed member).

    During member discovery every candidate — including the same-name impostors
    that are ultimately Excluded — is expanded into the graph, which pulls in
    *their* unresolved corporate parents as `external` nodes. Those parents do
    not control the subject group at all. Without this filter they leak into the
    brief's "Ultimate or overseas controllers" list (e.g. an impostor's parent
    appearing as if it controlled the anchor). We therefore keep only externals
    with a CONTROLS edge into an in-group company.
    """
    ingroup = set(ingroup_numbers)
    out, seen = [], set()
    for n, d in g.nodes(data=True):
        if d.get("kind") != "external":
            continue
        controls_ingroup = any(
            e.get("rel") == "CONTROLS"
            and g.nodes[v].get("company_number") in ingroup
            for _, v, e in g.out_edges(n, data=True))
        if not controls_ingroup:
            continue
        key = (d.get("name"), d.get("jurisdiction"))
        if key not in seen:
            seen.add(key)
            out.append(d)
    return out


def _detect_ownership(g, chain, attrs, ingroup_numbers=()) -> dict:
    ext = _external_controllers(g, set(ingroup_numbers) | set(chain))
    offshore_ctrl = [e for e in ext
                     if (e.get("jurisdiction") or "").strip().lower() in OFFSHORE]
    pe_layers = []
    for num in chain:
        a = attrs.get(num, {})
        blob = f"{a.get('name','')} {a.get('former_names','')}".upper()
        if any(t in blob for t in PE_TOKENS):
            pe_layers.append(a.get("name", num))

    if offshore_ctrl or pe_layers:
        controller = offshore_ctrl[0].get("name") if offshore_ctrl else None
        juris = offshore_ctrl[0].get("jurisdiction") if offshore_ctrl else None
        summary = ("It is owned through a chain of holding companies"
                   + (f", with the highest UK-visible controller being "
                      f"{controller}" + (f" ({juris})" if juris else "")
                      if controller else "")
                   + ". The intermediate companies named BIDCO, MIDCO, TOPCO and "
                   "similar are holding vehicles used in private-equity ownership; "
                   "they do not trade.")
        note = ("As a private-equity-owned group, purchasing decisions are "
                "likely to be centralised and assessed closely against cost and "
                "return on investment.")
        return {"type": "private-equity-backed group", "summary": summary,
                "note": note}
    if len(chain) > 1:
        top = attrs.get(chain[-1], {}).get("name", chain[-1])
        return {
            "type": "subsidiary of a larger group",
            "summary": f"It is part of a group headed by {top}.",
            "note": ("Budget and supplier decisions may sit with the parent "
                     "rather than this entity."),
        }
    return {
        "type": "independent / owner-managed company",
        "summary": "No corporate parent was found; it appears to be "
                   "independently owned.",
        "note": "Decisions are likely made by the directors listed below.",
    }


def _emp_str(v) -> str:
    if v is None:
        return "not disclosed"
    if v < 1:
        return "fewer than 1 (directors only)"
    return f"{round(v):,}"


def _lead_assessment(*, band, own_type, status, nw, nw_p, emp, n_charges,
                     insolv, has_group, triggers, recent_appts, recent_res) -> dict:
    """A measured lead-qualification view from Companies House signals alone.

    Deliberately conservative and free of hyperbole. Returns
    ``{'verdict', 'factors'}`` where ``verdict`` is one honest sentence and
    ``factors`` is a short list of the signals behind it. The caller adds the
    caveat that Companies House is only one lens (no contact, product-fit or
    intent data), and the agent refines the wording in the sales-lens pass.
    """
    factors: list[str] = []
    pos = neg = 0

    st = (status or "").lower()
    if st and st != "active":
        return {
            "verdict": f"Not a current fit on these signals: the company's "
                       f"status is '{status}'.",
            "factors": [f"Companies House status is '{status}', not active."],
        }

    # size / budget capacity
    if has_group or (band and any(w in band for w in ("large", "medium"))):
        factors.append("Size suggests the budget capacity to fund external "
                       "work.")
        pos += 1
    elif band and any(w in band for w in ("micro", "dormant")):
        factors.append("Small scale points to limited budget capacity.")
        neg += 1

    # momentum
    d = plain.pct_change(nw, nw_p)
    if d is not None and d >= 10:
        factors.append(f"Net worth is growing (up about {abs(d):.0f}% "
                       "year on year).")
        pos += 1
    elif d is not None and d <= -15:
        factors.append(f"Net worth is shrinking (down about {abs(d):.0f}% "
                       "year on year).")
        neg += 1

    # decision-making / ownership
    if own_type.startswith("private"):
        factors.append("Private-equity ownership means procurement is likely "
                       "centralised and judged on return on investment.")
    elif "subsidiary" in own_type:
        factors.append("As a subsidiary, budget decisions may sit with the "
                       "parent rather than this entity.")
    else:
        factors.append("Owner-managed: decisions likely rest with the directors.")

    # timing triggers (engagement openings)
    triggers_present = []
    if recent_appts:
        triggers_present.append("a recent senior appointment")
    if recent_res:
        triggers_present.append("a recent board departure")
    if triggers.get("recent_incorporations"):
        triggers_present.append("a newly incorporated group entity")
    if triggers.get("rebrands"):
        triggers_present.append("a recent rebrand")
    if triggers_present:
        factors.append("Recent change provides a timing hook: "
                       + ", ".join(triggers_present) + ".")
        pos += 1

    # risk
    if insolv:
        factors.append("Insolvency history on file warrants caution.")
        neg += 2
    elif n_charges:
        factors.append("Outstanding charges indicate borrowing; not a concern "
                       "in itself, but note any near-term debt maturity.")

    if neg >= 2:
        verdict = ("Approach with caution on these signals; the risk markers "
                   "outweigh the positives.")
    elif pos >= 2 and neg == 0:
        verdict = ("Appears reasonably well-qualified on these signals and worth "
                   "prioritising for a closer look.")
    elif pos >= 1 and pos > neg:
        verdict = ("A moderate lead on these signals; worth a look if other "
                   "sources support it.")
    else:
        verdict = ("Nothing in the Companies House record strongly distinguishes "
                   "this company as a lead; prioritise only if other signals "
                   "support it.")
    return {"verdict": verdict, "factors": factors}


def _figs_table(figs: dict) -> list[str]:
    L = [f"| Measure | Latest ({figs.get('current_date','?')}) | "
         f"Prior ({figs.get('prior_date','?')}) | Change |",
         "| --- | --- | --- | --- |"]
    cur, prior = figs.get("current", {}), figs.get("prior", {})
    for label in cur:
        cv, pv = cur.get(label), prior.get(label)
        if label == "Average employees":
            c, p = _emp_str(cv), _emp_str(pv)
            change = plain.trend_phrase(cv, pv) if (cv and cv >= 1 and pv and pv >= 1) else ""
        else:
            c, p = plain.money(cv), plain.money(pv)
            change = plain.trend_phrase(cv, pv)
        L.append(f"| {label} | {c} | {p} | {change} |")
    return L


def _money_read(figs: dict) -> list[str]:
    cur, prior = figs.get("current", {}), figs.get("prior", {})
    out = []
    nca = cur.get("Net current assets")
    if nca is not None and nca < 0:
        out.append(f"Net current assets are negative at {plain.money(nca)}, "
                   "meaning short-term liabilities exceed short-term assets. "
                   "This is worth noting but is not unusual in some business "
                   "models.")
    return out


def build_brief(outdir: Path, do_financials=True, do_risk=True,
                download_accounts=False, cache_dir=".ch_cache") -> Path:
    struct = json.loads((outdir / "structure.json").read_text(encoding="utf-8"))
    g = nx.read_graphml(str(outdir / "structure.graphml"))
    attrs = _node_attrs_by_number(g)
    classifications = struct["classifications"]
    anchor = struct["anchor"]
    chain = struct.get("ownership_chain", [])

    client = CompaniesHouseClient(cache_dir=cache_dir or None)
    anchor_attrs = attrs.get(anchor, {})

    by_label = {}
    for c in classifications:
        by_label.setdefault(c["label"], []).append(c)
    confirmed = by_label.get("Confirmed", [])
    confirmed_nums = [c["company_number"] for c in confirmed]

    own = _detect_ownership(g, chain, attrs,
                            ingroup_numbers=set(chain) | set(confirmed_nums))
    fin = enrich.gather_financials(client, confirmed_nums) if do_financials else []
    charges = enrich.gather_charges(client, confirmed_nums) if do_risk else []
    insolv = enrich.gather_insolvency(client, confirmed_nums) if do_risk else []
    people = enrich.gather_people(client, anchor)
    triggers = enrich.gather_triggers(attrs, classifications)

    anchor_figs = accounts.fetch_figures(client, anchor) if do_financials else None
    group_fin = []
    if do_financials:
        for f in fin:
            figs = accounts.fetch_figures(client, f["company_number"])
            pdf_info = None
            if not figs and download_accounts:
                doc = accounts.fetch_latest_accounts_doc(client, f["company_number"])
                if doc and "application/pdf" in (doc.get("formats") or {}):
                    doc_dir = outdir / f"group_accounts_{f['company_number']}"
                    try:
                        pdf_info = accounts.fetch_accounts_pdf(
                            client, doc["metadata_url"], doc_dir)
                    except Exception:
                        pdf_info = None
            group_fin.append((f, figs, pdf_info))

    # ---- derived values --------------------------------------------------
    cites = Cites()
    L = []
    name = anchor_attrs.get("name", anchor)
    age = plain.company_age(anchor_attrs.get("incorporated_on"))
    inc = anchor_attrs.get("incorporated_on")
    year = inc[:4] if inc else None

    cur = (anchor_figs or {}).get("current", {})
    prior = (anchor_figs or {}).get("prior", {})
    emp = cur.get("Average employees")
    nw = cur.get("Net assets (net worth)") or cur.get("Total equity")
    nw_p = prior.get("Net assets (net worth)") or prior.get("Total equity")
    cash = cur.get("Cash at bank")
    nca = cur.get("Net current assets")
    band = plain.size_band(emp, nw, own["type"].startswith("private"))
    out_charges = [c for c in charges if c["outstanding"]]
    n_charges = sum(len(c["outstanding"]) for c in out_charges)
    is_grouped = len(confirmed) > 1 or len(chain) > 1 \
        or bool(by_label.get("Probable")) or bool(by_label.get("Possible"))

    cprofile = cites.ref(f"{name} on Companies House", _profile_url(anchor))

    # ---- header ----------------------------------------------------------
    L.append(f"# Companies House profile: {name}")
    L.append("")
    L.append(f"Company number {anchor}. Prepared {_dt.date.today().isoformat()} "
             "from Companies House public filings.")
    L.append("")

    # ---- summary paragraph ----------------------------------------------
    L.append("## Summary")
    L.append("")
    s = []
    if is_grouped:
        ident = (f"{name} (company number {anchor}{cprofile}) is a UK company "
                 f"whose registered activity is "
                 f"{plain.sic_plain(anchor_attrs.get('sic_codes'))}")
    else:
        art = "an" if (band[:1].lower() in "aeiou") else "a"
        ident = (f"{name} (company number {anchor}{cprofile}) is {art} {band} "
                 f"UK company whose registered activity is "
                 f"{plain.sic_plain(anchor_attrs.get('sic_codes'))}")
    if year:
        ident += f", incorporated in {year} (about {age} years ago)"
    ident += "."
    s.append(ident)
    if emp and emp >= 1:
        s.append(f"It reports approximately {round(emp):,} employees.")
    s.append(own["summary"][0].upper() + own["summary"][1:])
    s.append(own["note"])
    L.append(" ".join(s))
    L.append("")
    # second paragraph: financial position and recent events
    fin_bits = []
    if nw is not None:
        d = plain.pct_change(nw, nw_p)
        msg = f"net assets stand at {plain.money(nw)}"
        if d is not None:
            msg += (f", {'up' if d>=0 else 'down'} {abs(d):.0f}% on the prior "
                    "year")
        fin_bits.append(msg)
    if cash is not None:
        fin_bits.append(f"cash at bank is {plain.money(cash)}")
    if nca is not None and nca < 0:
        fin_bits.append("net current assets are negative")
    risk_clause = ""
    if insolv:
        risk_clause = " The group has insolvency history on file."
    elif n_charges:
        risk_clause = (f" There {'is' if n_charges==1 else 'are'} {n_charges} "
                       f"outstanding charge{'s' if n_charges!=1 else ''} on file.")
    elif do_risk:
        risk_clause = " No charges or insolvency are recorded."
    if fin_bits:
        L.append("On the most recent filed accounts, "
                 + "; ".join(fin_bits) + "." + risk_clause)
    elif risk_clause.strip():
        L.append(risk_clause.strip())
    # recent events
    recent_appts = [d for d in people["recent_changes"] if not d["resigned_on"]]
    recent_res = [d for d in people["recent_changes"] if d["resigned_on"]]
    ev = []
    if recent_appts:
        ev.append("recent board appointment(s)")
    if recent_res:
        ev.append("recent board departure(s)")
    if triggers["recent_incorporations"]:
        ev.append("a newly incorporated group entity")
    if triggers["rebrands"]:
        ev.append("name change(s) within the group")
    if ev:
        L.append("Recent filings show " + ", ".join(ev)
                 + " (see Directors and recent changes below).")
    L.append("")

    # ---- lead assessment (Companies House signals only) -----------------
    la = _lead_assessment(
        band=band, own_type=own["type"],
        status=anchor_attrs.get("status"), nw=nw, nw_p=nw_p, emp=emp,
        n_charges=n_charges, insolv=insolv, has_group=bool(group_fin),
        triggers=triggers, recent_appts=recent_appts, recent_res=recent_res)
    L.append("## Lead assessment")
    L.append("")
    L.append(la["verdict"])
    L.append("")
    if la["factors"]:
        L.append("On the Companies House record:")
        L.append("")
        for fct in la["factors"]:
            L.append(f"- {fct}")
        L.append("")
    L.append("This view draws only on Companies House data — it carries no "
             "information on the people to contact, product fit, current "
             "projects or buying intent, so treat it as one input to "
             "qualification, not the whole picture.")
    L.append("")

    # ---- registration details ------------------------------------------
    L.append("## Registration details")
    L.append("")
    L.append(f"- Registered name: {name}")
    L.append(f"- Company number: {anchor}{cprofile}")
    L.append(f"- Status: {anchor_attrs.get('status','not stated')}")
    L.append(f"- Incorporated: {anchor_attrs.get('incorporated_on','not stated')}"
             + (f" (about {age} years)" if age else ""))
    L.append(f"- Nature of business (SIC): "
             f"{plain.sic_plain(anchor_attrs.get('sic_codes'))} "
             f"(code {anchor_attrs.get('sic_codes','not stated')})")
    if anchor_attrs.get("former_names"):
        L.append(f"- Former names: {anchor_attrs['former_names']}")
    L.append(f"- Identification method: {struct.get('method')} "
             f"(confidence: {struct.get('confidence')})")
    L.append("")

    # ---- ownership -------------------------------------------------------
    if is_grouped:
        L.append("## Ownership and group structure")
        L.append("")
        cpsc = cites.ref(f"{name} persons with significant control",
                         _psc_url(anchor))
        L.append(f"{own['summary'][0].upper()}{own['summary'][1:]}{cpsc}")
        L.append("")
        if chain and len(chain) > 1:
            L.append("Chain of control (each company is owned by the one below it):")
            L.append("")
            L.append("```")
            for i, num in enumerate(chain):
                a = attrs.get(num, {})
                tag = "  (the company itself)" if num == anchor else ""
                L.append(f"{'  ' * i}{a.get('name', num)} ({num}){tag}")
            L.append("```")
            ext = _external_controllers(g, set(chain) | set(confirmed_nums))
            if ext:
                L.append("")
                L.append("Ultimate or overseas controllers:")
                for e in ext:
                    L.append(f"- {e.get('name')} "
                             f"({e.get('jurisdiction') or 'jurisdiction not stated'})"
                             + (f", registration {e.get('foreign_reg_no')}"
                                if e.get('foreign_reg_no') else ""))
        L.append("")
        L.append(f"Confirmed group members (linked by verified ownership): "
                 f"{len(confirmed)}. Probable: {len(by_label.get('Probable', []))}. "
                 f"Possible: {len(by_label.get('Possible', []))}. Same-name "
                 f"companies set aside as not part of the group: "
                 f"{len(by_label.get('Excluded', []))}.")
        L.append("")
        if len(confirmed) > 1:
            L.append("Confirmed members:")
            L.append("")
            for c in sorted(confirmed, key=lambda x: x["name"] or ""):
                L.append(f"- {c['name']} ({c['company_number']})")
            L.append("")
        for lab, gloss in (
            ("Probable", "very likely part of the group, but not proven by an "
             "ownership link; verify before relying on this"),
            ("Possible", "a single weak connection only; treat as a lead to "
             "verify, not as fact")):
            rows = by_label.get(lab, [])
            if rows:
                L.append(f"{lab} ({gloss}):")
                L.append("")
                for c in rows:
                    ev2 = "; ".join(c.get("evidence", []))
                    L.append(f"- {c['name']} ({c['company_number']}). "
                             f"Evidence: {ev2}")
                L.append("")
        excluded = by_label.get("Excluded", [])
        if excluded:
            L.append(f"{len(excluded)} same-name companies were excluded as "
                     "having different owners and no verified link; the full "
                     "list is in structure.json.")
            L.append("")

    # ---- financial summary ----------------------------------------------
    has_anchor_figs = bool(anchor_figs and anchor_figs.get("current"))
    if has_anchor_figs or group_fin:
        L.append("## Financial summary")
        L.append("")
        if has_anchor_figs:
            caccts = cites.ref(
                f"{name} accounts filed {anchor_figs.get('filing_date','')}",
                _filings_url(anchor))
            L.append("Figures from the company's own filed accounts" + caccts + ".")
            L.append("")
            L += _figs_table(anchor_figs)
            L.append("")
            for line in _money_read(anchor_figs):
                L.append(f"- {line}")
                L.append("")
        if group_fin:
            L.append("Consolidated (whole-group) accounts report revenue and "
                     "profit for the entire group, where the true scale is "
                     "visible.")
            L.append("")
            for f, figs, pdf_info in group_fin:
                la = f.get("latest_accounts") or {}
                cgrp = cites.ref(
                    f"{f['name']} group accounts to {f.get('made_up_to','')}",
                    _filings_url(f["company_number"]))
                L.append(f"- {f['name']} ({f['company_number']}): group accounts "
                         f"to {f.get('made_up_to','date not stated')}{cgrp}.")
                if figs and figs.get("current"):
                    for sub in _figs_table(figs):
                        L.append(f"  {sub}")
                elif pdf_info:
                    rel = Path(pdf_info["pages_dir"]).relative_to(outdir)
                    if pdf_info["page_count"]:
                        L.append(
                            f"  - Downloaded and rendered to {pdf_info['page_count']} "
                            f"page images under {rel}/ "
                            f"(PDF: {Path(pdf_info['pdf_path']).relative_to(outdir)}, "
                            f"{pdf_info['bytes']//1024} KB). Read the page images "
                            "to transcribe the headline figures.")
                    else:
                        L.append(
                            f"  - Downloaded the PDF "
                            f"({Path(pdf_info['pdf_path']).relative_to(outdir)}, "
                            f"{pdf_info['bytes']//1024} KB), but could not render "
                            f"page images: {pdf_info.get('error')}")
                else:
                    L.append("  - No machine-readable data is available; the "
                             "figures are in the PDF accounts. Re-run with "
                             "--download-accounts to download and render them.")
            L.append("")

    # ---- borrowing and risk (only if there is something to report) ------
    if out_charges or insolv:
        L.append("## Borrowing and risk")
        L.append("")
        if out_charges:
            L.append("Outstanding charges. A charge indicates that a lender "
                     "holds security over the company's assets, that is, the "
                     "company has borrowed against them.")
            L.append("")
            for c in out_charges:
                cch = cites.ref(f"{c['name']} charges", _charges_url(c["company_number"]))
                for o in c["outstanding"]:
                    holders = ", ".join(o.get("persons_entitled") or ["not stated"])
                    L.append(f"- {c['name']}: {o.get('classification')}, "
                             f"created {o.get('created_on')}, held by "
                             f"{holders}{cch}.")
            L.append("")
            holder_blob = " ".join(
                (p or "") for c in out_charges for o in c["outstanding"]
                for p in (o.get("persons_entitled") or [])).lower()
            if any(t in holder_blob for t in ("trust", "security agent",
                                              "security trustee")):
                L.append("A trustee or security agent named as the holder "
                         "usually indicates acquisition or leveraged debt rather "
                         "than a simple bank loan.")
                L.append("")
        if insolv:
            L.append("Insolvency history is recorded for the following and "
                     "should be investigated before pursuing:")
            L.append("")
            for i in insolv:
                ci = cites.ref(f"{i['name']} insolvency", _profile_url(i["company_number"]))
                L.append(f"- {i['name']} ({i['company_number']}){ci}")
            L.append("")

    # ---- directors -------------------------------------------------------
    L.append("## Directors and recent changes")
    L.append("")
    coff = cites.ref(f"{name} officers", _officers_url(anchor))
    L.append(f"Current directors{coff}:")
    L.append("")
    for d in people["current_directors"]:
        extra = f", {d['occupation']}" if d.get("occupation") else ""
        L.append(f"- {d['name']}, {d['role']}, appointed {d['appointed_on']}{extra}")
    if people["recent_changes"]:
        L.append("")
        L.append("Board changes in approximately the last 18 months:")
        L.append("")
        seen = set()
        for d in people["recent_changes"]:
            if d["name"] in seen:
                continue
            seen.add(d["name"])
            verb = (f"resigned {d['resigned_on']}" if d["resigned_on"]
                    else f"appointed {d['appointed_on']}")
            L.append(f"- {d['name']}: {verb}")
    if triggers["recent_incorporations"]:
        L.append("")
        L.append("Newly incorporated group entities:")
        L.append("")
        for r in triggers["recent_incorporations"]:
            L.append(f"- {r['name']} ({r['company_number']}), incorporated "
                     f"{r['incorporated_on']}")
    if triggers["rebrands"]:
        L.append("")
        L.append("Name changes within the group:")
        L.append("")
        for r in triggers["rebrands"]:
            L.append(f"- {r['name']}: formerly {r['former_names']}")
    L.append("")

    # ---- glossary (only terms used) -------------------------------------
    is_pe = own["type"].startswith("private")
    glossary = []
    if is_grouped:
        glossary.append(
            "- Person with significant control (PSC): a party that ultimately "
            "owns or controls more than 25% of a company. Used here to trace "
            "ownership upward.")
    if is_pe:
        glossary.append(
            "- BIDCO, MIDCO, TOPCO, HOLDCO: holding companies used in "
            "private-equity buyouts to hold debt and equity. They do not trade.")
    if group_fin:
        glossary.append(
            "- Group (consolidated) accounts: a single set of accounts covering "
            "the whole group, where total revenue and profit are reported.")
    if out_charges:
        glossary.append(
            "- Charge: security held by a lender over a company's assets; "
            "evidence of borrowing.")
    if has_anchor_figs:
        glossary.append(
            "- Net assets (net worth): total assets minus all liabilities.")
        if nca is not None:
            glossary.append(
                "- Net current assets: short-term assets minus short-term "
                "liabilities. A negative figure means short-term liabilities "
                "exceed short-term assets.")
    if glossary:
        L.append("## Glossary")
        L.append("")
        L.extend(glossary)
        L.append("")

    # ---- references ------------------------------------------------------
    refs = cites.render()
    if refs:
        L.append("## References")
        L.append("")
        L.extend(refs)
        L.append("")

    # ---- caveats ---------------------------------------------------------
    L.append("## Caveats")
    L.append("")
    L.append("- All data is from Companies House public filings, retrieved on "
             f"{_dt.date.today().isoformat()}, and reflects the latest filings, "
             "which can lag real-world events. This brief is read-only.")
    L.append("- Financial figures are taken from filed accounts. Figures for "
             "companies that file iXBRL data are extracted automatically; "
             "PDF-only group accounts are downloaded and rendered to page "
             "images, and the headline figures are read from those images and "
             "attributed to the source filing.")
    L.append("- Group membership is established by verified ownership for "
             "Confirmed members. Downward discovery relies on name-stem and "
             "shared-office heuristics (Companies House has no list-subsidiaries "
             "endpoint) and is capped, so the group list may be incomplete; a "
             "member sharing neither a name stem nor a registered office can be "
             "missed. Probable and Possible members are leads to verify, not "
             "proof.")
    L.append("- Person matching uses name and birth month and year; the same "
             "individual may occasionally appear more than once. Shared-person "
             "evidence is supporting only.")
    L.append("")

    brief_path = outdir / "brief.md"
    brief_path.write_text("\n".join(L), encoding="utf-8")
    return brief_path


def build_docx(md_path: Path) -> Optional[Path]:
    """Convert a profile Markdown file to .docx via pandoc.

    Cross-platform: invokes ``pandoc`` directly (no shell / bash), using the
    bundled reference document and lua filters in ``docx-build/`` so the Word
    styling matches that tool. Returns the .docx path on success, or None when
    pandoc is missing or the build fails -- the Markdown profile is always the
    primary artefact and is produced regardless.
    """
    if not shutil.which("pandoc"):
        return None
    build_dir = Path(__file__).resolve().parent.parent / "docx-build"
    reference = build_dir / "reference.docx"
    if not reference.exists():
        return None
    out = md_path.with_suffix(".docx")
    # filters are applied in order; resource-path lets pandoc find images
    # relative to the source dir, the skill root and the build dir.
    resource_path = os.pathsep.join(
        [str(md_path.resolve().parent), str(build_dir.parent), str(build_dir)])
    cmd = [
        "pandoc",
        "--from=markdown+lists_without_preceding_blankline",
        f"--reference-doc={reference.name}",
        "-o", str(out.resolve()),
        f"--resource-path={resource_path}",
    ]
    for f in ("figure-img.lua", "table-width.lua", "titlepage.lua", "sections.lua"):
        if (build_dir / f).exists():
            cmd += [f"--lua-filter={f}"]
    cmd.append(str(md_path.resolve()))
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True,
                       cwd=str(build_dir))
    except (subprocess.CalledProcessError, OSError):
        return None
    return out if out.exists() else None


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render the Companies House profile")
    ap.add_argument("--out", default="output", help="per-company dir (with structure.json)")
    ap.add_argument("--no-financials", action="store_true")
    ap.add_argument("--no-risk", action="store_true")
    ap.add_argument("--download-accounts", action="store_true",
                    help="download group-accounts PDFs (for entities with no iXBRL)")
    ap.add_argument("--cache", default=".ch_cache",
                    help="API cache dir ('' to disable); match the CLI")
    ap.add_argument("--no-docx", action="store_true",
                    help="skip building the .docx (Markdown only)")
    args = ap.parse_args(argv)
    p = build_brief(Path(args.out), not args.no_financials, not args.no_risk,
                    args.download_accounts, args.cache)
    print("wrote", p)
    if not args.no_docx:
        d = build_docx(p)
        if d:
            print("wrote", d)
        elif shutil.which("pandoc") is None:
            print("note: pandoc not found; skipped .docx (install pandoc to enable)")
        else:
            print("note: .docx build failed; the Markdown profile is available")


if __name__ == "__main__":
    main()
