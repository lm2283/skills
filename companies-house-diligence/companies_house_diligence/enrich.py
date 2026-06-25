"""Phases 4-6: enrich the discovered structure with financials, risk and people.

These functions take the classified company set (from the discovery pass) and
make additional Companies House calls to gather:

    Phase 4  financials  -> which entity files group (consolidated) accounts,
                            and a link to the latest accounts document
    Phase 5  risk        -> charges (leverage/lenders), insolvency history
    Phase 6  people      -> current directors, leadership churn, and timing
                            triggers (recent incorporations, rebrands)

Everything is read-only. Calls are bounded to the Confirmed set (plus the
anchor) to keep within rate limits.
"""

from __future__ import annotations

import datetime as _dt
from typing import Optional

from .client import CompaniesHouseClient


def _confirmed_numbers(classifications: list[dict]) -> list[str]:
    return [c["company_number"] for c in classifications if c["label"] == "Confirmed"]


# --------------------------------------------------------------------------
# Phase 4: financials
# --------------------------------------------------------------------------
def gather_financials(client: CompaniesHouseClient, numbers: list[str]) -> list[dict]:
    """Find entities filing group (consolidated) accounts and their latest doc."""
    out = []
    for num in numbers:
        prof = client.company(num)
        if not prof:
            continue
        last = prof.get("accounts", {}).get("last_accounts", {}) or {}
        if last.get("type") != "group":
            continue
        rec = {
            "company_number": num,
            "name": prof.get("company_name"),
            "accounts_type": last.get("type"),
            "made_up_to": last.get("made_up_to"),
            "latest_accounts": None,
        }
        fh = client.filing_history(num, category="accounts", items_per_page=5)
        for item in fh.get("items", []):
            rec["latest_accounts"] = {
                "date": item.get("date"),
                "description": item.get("description"),
                "document_metadata_url": item.get("links", {}).get("document_metadata"),
            }
            break
        out.append(rec)
    return out


# --------------------------------------------------------------------------
# Phase 5: risk
# --------------------------------------------------------------------------
def gather_charges(client: CompaniesHouseClient, numbers: list[str]) -> list[dict]:
    out = []
    for num in numbers:
        ch = client.charges(num)
        total = ch.get("total_count", 0)
        if not total:
            continue
        outstanding = []
        for c in ch.get("items", []):
            if c.get("status") == "outstanding":
                outstanding.append({
                    "created_on": c.get("created_on"),
                    "classification": c.get("classification", {}).get("description"),
                    "persons_entitled": [p.get("name") for p in c.get("persons_entitled", [])],
                })
        prof = client.company(num)
        out.append({
            "company_number": num,
            "name": prof.get("company_name") if prof else num,
            "total": total,
            "satisfied": ch.get("satisfied_count", 0),
            "part_satisfied": ch.get("part_satisfied_count", 0),
            "outstanding": outstanding,
        })
    return out


def gather_insolvency(client: CompaniesHouseClient, numbers: list[str]) -> list[dict]:
    out = []
    for num in numbers:
        prof = client.company(num)
        if not prof or not prof.get("has_insolvency_history"):
            continue
        ins = client.get(f"/company/{num}/insolvency") or {}
        out.append({
            "company_number": num,
            "name": prof.get("company_name"),
            "cases": [{"type": c.get("type"), "dates": c.get("dates")}
                      for c in ins.get("cases", [])],
        })
    return out


# --------------------------------------------------------------------------
# Phase 6: people & triggers
# --------------------------------------------------------------------------
def gather_people(client: CompaniesHouseClient, anchor: str,
                  months_recent: int = 18) -> dict:
    officers = client.officers(anchor).get("items", [])
    current, recent_changes = [], []
    cutoff = _dt.date.today() - _dt.timedelta(days=months_recent * 30)
    for o in officers:
        active = not o.get("resigned_on")
        row = {
            "name": o.get("name"),
            "role": o.get("officer_role"),
            "appointed_on": o.get("appointed_on"),
            "resigned_on": o.get("resigned_on"),
            "nationality": o.get("nationality"),
            "occupation": o.get("occupation"),
        }
        if active:
            current.append(row)
        for datestr in (o.get("appointed_on"), o.get("resigned_on")):
            if datestr:
                try:
                    d = _dt.date.fromisoformat(datestr)
                except ValueError:
                    continue
                if d >= cutoff:
                    recent_changes.append(row)
                    break
    return {"current_directors": current, "recent_changes": recent_changes}


def gather_triggers(node_attrs: dict, classifications: list[dict],
                    months_recent: int = 18) -> dict:
    """Timing signals derived from graph node attributes (no extra API calls)."""
    cutoff = _dt.date.today() - _dt.timedelta(days=months_recent * 30)
    recent_inc, rebrands = [], []
    for c in classifications:
        if c["label"] not in ("Confirmed", "Probable"):
            continue
        attrs = node_attrs.get(c["company_number"], {})
        inc = attrs.get("incorporated_on")
        if inc:
            try:
                if _dt.date.fromisoformat(inc) >= cutoff:
                    recent_inc.append({"company_number": c["company_number"],
                                       "name": c["name"], "incorporated_on": inc})
            except ValueError:
                pass
        former = attrs.get("former_names")
        if former:
            rebrands.append({"company_number": c["company_number"],
                             "name": c["name"], "former_names": former})
    return {"recent_incorporations": recent_inc, "rebrands": rebrands}
