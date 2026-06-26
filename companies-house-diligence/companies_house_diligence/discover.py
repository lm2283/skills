"""Phases 2-3b: anchor, expand, walk ownership, discover members, classify.

Pipeline:
    1. anchor(identifiers)            -> resolve to one company_number
    2. expand_company(num)            -> add profile + officers + PSC to graph
    3. walk_up(anchor)                -> follow corporate PSC edges to ultimate owner
    4. discover_members(...)          -> name-stem + shared-office candidates
    5. classify(graph, anchor)        -> Confirmed / Probable / Possible / Excluded

Membership is decided by graph topology, never by name similarity:
    - Confirmed : in the anchor's weakly-connected component of the active
                  CONTROLS (PSC) subgraph -> a real ownership path exists.
    - Probable  : not on the ownership backbone, but linked to confirmed
                  companies by >=2 independent low-fan-out connectors
                  (shared person and/or shared low-fan-out address).
    - Possible  : linked by exactly one weak connector -> human review.
    - Excluded  : separate component / only high-fan-out address shared.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

import networkx as nx

from .client import CompaniesHouseClient
from .graph import (StructureGraph, company_id, address_id, _ch_address)

LOG = logging.getLogger("ch.discover")

# An address used by more than this many companies is treated as a shared
# service address (formation agent / accountant) and discounted as a connector.
HIGH_FAN_OUT = 25

# Member discovery by shared registered office: the occupancy above which an
# address is treated as a shared-service address (formation agent / accountant)
# and skipped entirely. Offices at or below it are read in full (bounded by it).
OFFICE_SHARED_MAX = 200

# UK company numbers are either 8 digits (England & Wales / older zero-padded)
# or a 1-2 letter prefix followed by 6 digits. Prefixes include SC (Scotland),
# NI (Northern Ireland), OC/SO/NC (LLPs), plus FC/BR/etc. (overseas/branch).
_UK_NUMERIC = re.compile(r"^\d{1,8}$")
_UK_PREFIXED = re.compile(r"^[A-Z]{1,2}\d{6}$")


def normalize_company_number(raw: Optional[str]) -> Optional[str]:
    """Normalise a Companies House number to its canonical form, or None.

    Handles the real-world messiness of PSC ``registration_number`` fields:
    lowercase or mixed-case prefixes (e.g. ``Sc709057``), embedded spaces and
    punctuation, and short numeric numbers that need zero-padding to 8 digits.
    Crucially it accepts alpha-prefixed numbers (SC/NI/OC/SO/...), which a bare
    ``str.isdigit()`` test wrongly rejects -- the bug that previously dropped
    Scottish/NI/LLP parents off the ownership chain.

    Returns the canonical number (8-digit numeric zero-padded, or
    ``PREFIX`` + 6 digits, upper-cased) or None if it is not a recognisable
    UK company number.
    """
    if not raw:
        return None
    s = re.sub(r"[^A-Za-z0-9]", "", raw).upper()
    if _UK_PREFIXED.match(s):
        return s
    if _UK_NUMERIC.match(s):
        return s.zfill(8)
    return None


_UK_COUNTRY_TOKENS = ("united kingdom", "england", "wales", "scotland",
                      "northern ireland", "great britain", "uk")


def _resolve_uk_psc_number(reg: Optional[str],
                           country_registered: Optional[str]) -> Optional[str]:
    """Decide whether a corporate PSC's registration number is a UK company.

    Alpha-prefixed numbers (SC/NI/OC/SO/...) are unambiguously UK and accepted
    regardless of the country string. Purely-numeric numbers are accepted only
    when the country looks UK or is unspecified, so an overseas entity whose
    registration number is coincidentally 6-8 digits stays an external node
    (e.g. a Jersey/Luxembourg holdco) rather than being mis-resolved.
    """
    norm = normalize_company_number(reg)
    if not norm:
        return None
    if _UK_PREFIXED.match(norm):
        return norm
    ctry = (country_registered or "").lower()
    if not ctry or any(tok in ctry for tok in _UK_COUNTRY_TOKENS):
        return norm
    return None


# --------------------------------------------------------------------------
# Phase 2: anchoring
# --------------------------------------------------------------------------
@dataclass
class AnchorResult:
    company_number: Optional[str]
    method: str
    confidence: str
    candidates: list[dict]


def anchor(client: CompaniesHouseClient, *, number: Optional[str] = None,
           name: Optional[str] = None,
           postcodes: Optional[list[str]] = None) -> AnchorResult:
    """Resolve identifiers (read by the agent from the page) to one company.

    Confidence, in order: an explicit, verified company ``number`` (high); a
    ``name`` whose registered-office postcode matches one seen on the page
    (high); a ``name`` best-guess only (low).
    """
    postcodes = postcodes or []
    # 1. explicit company number -> verify it exists
    if number:
        prof = client.company(number)
        if prof:
            return AnchorResult(number, "company-number-on-page", "high", [prof])

    # 2. fall back to name + postcode correlation
    cands: list[dict] = []
    if name:
        res = client.search_companies(name, items_per_page=20)
        page_pcs = {p.replace(" ", "").upper() for p in postcodes}
        for item in res.get("items", []):
            prof = client.company(item["company_number"])
            if not prof:
                continue
            roa = prof.get("registered_office_address", {})
            pc = (roa.get("postal_code") or "").replace(" ", "").upper()
            score = 1 if pc and pc in page_pcs else 0
            cands.append({"profile": prof, "postcode_match": bool(score)})
        cands.sort(key=lambda c: c["postcode_match"], reverse=True)
        if cands and cands[0]["postcode_match"]:
            return AnchorResult(cands[0]["profile"]["company_number"],
                                "name+postcode-match", "high",
                                [c["profile"] for c in cands])
        if cands:
            return AnchorResult(cands[0]["profile"]["company_number"],
                                "name-best-guess", "low",
                                [c["profile"] for c in cands])
    return AnchorResult(None, "unresolved", "none", [])


# --------------------------------------------------------------------------
# Phase 2/3: expansion
# --------------------------------------------------------------------------
def expand_company(client: CompaniesHouseClient, sg: StructureGraph,
                   number: str, *, role: str = "") -> Optional[str]:
    """Fetch profile, officers and PSC for a company and add them to the graph.

    Returns the company node id, or None if the company does not exist.
    Corporate PSCs that carry a UK registration number are returned so the
    caller can decide whether to expand them too.
    """
    prof = client.company(number)
    if not prof:
        return None
    nid = sg.add_company(prof, role=role)
    own_pc = (prof.get("registered_office_address", {}).get("postal_code") or "")

    # officers -> Person nodes + OFFICER_OF edges
    for off in client.officers(number).get("items", []):
        dob = off.get("date_of_birth", {})
        pid = sg.add_person(off.get("name", ""),
                            dob_month=dob.get("month"), dob_year=dob.get("year"),
                            nationality=off.get("nationality", ""),
                            occupation=off.get("occupation", ""),
                            source="officers")
        sg.add_edge(pid, nid, "OFFICER_OF",
                    role=off.get("officer_role"),
                    appointed_on=off.get("appointed_on"),
                    resigned_on=off.get("resigned_on"),
                    is_active=not off.get("resigned_on"),
                    source="officers")
        addr = off.get("address")
        if addr:
            aid, human = _ch_address(addr)
            sg.add_address(aid, human, postcode=addr.get("postal_code", ""))
            sg.add_edge(pid, aid, "CORRESPONDENCE_AT", source="officers")

    # PSC -> CONTROLS edges (corporate) or Person CONTROLS (individual)
    for psc in client.psc(number).get("items", []):
        kind = psc.get("kind", "")
        ctrl = dict(natures_of_control=psc.get("natures_of_control", []),
                    notified_on=psc.get("notified_on"),
                    ceased=bool(psc.get("ceased")),
                    ceased_on=psc.get("ceased_on"),
                    source="psc")
        idn = psc.get("identification", {}) or {}
        if kind.startswith("corporate") or kind.startswith("legal"):
            reg = (idn.get("registration_number") or "").strip()
            resolved = _resolve_uk_psc_number(reg, idn.get("country_registered"))
            if resolved:
                pass
            elif not reg and psc.get("name"):
                # PSC record omits the number -> resolve by name (postcode hint)
                resolved = _resolve_company_by_name(client, psc["name"], own_pc)
            else:
                resolved = None
            if resolved:
                src_id = company_id(resolved)
                if not sg.g.has_node(src_id):
                    sg.g.add_node(src_id, kind="company", company_number=resolved,
                                  name=psc.get("name"), status="(stub)",
                                  source="psc-stub")
            else:
                src_id = sg.add_external(psc.get("name", ""),
                                         jurisdiction=idn.get("country_registered", ""),
                                         reg_no=reg,
                                         legal_form=idn.get("legal_form", ""),
                                         source="psc")
            sg.add_edge(src_id, nid, "CONTROLS", **ctrl)
        else:
            dob = psc.get("date_of_birth", {})
            pid = sg.add_person(psc.get("name", ""),
                                dob_month=dob.get("month"), dob_year=dob.get("year"),
                                nationality=psc.get("nationality", ""),
                                source="psc")
            sg.add_edge(pid, nid, "CONTROLS", **ctrl)
        # PSC address
        if psc.get("address"):
            aid, human = _ch_address(psc["address"])
            sg.add_address(aid, human, postcode=psc["address"].get("postal_code", ""))
    return nid


def _resolve_company_by_name(client: CompaniesHouseClient, name: str,
                             hint_postcode: str = "") -> Optional[str]:
    """Resolve a corporate name to a company number via search.

    Many PSC records omit the registration number (only a name is given).
    We search by name and accept a hit only when it is a confident match:
    exact (normalised) name match, preferring an active company and, if known,
    a shared registered-office postcode.
    """
    target = re.sub(r"[^a-z0-9]", "", name.lower())
    hint = (hint_postcode or "").replace(" ", "").upper()
    best = None
    for item in client.search_companies(name, items_per_page=20).get("items", []):
        title = re.sub(r"[^a-z0-9]", "", item.get("title", "").lower())
        if title != target:
            continue
        num = item.get("company_number")
        prof = client.company(num)
        if not prof:
            continue
        pc = (prof.get("registered_office_address", {})
              .get("postal_code") or "").replace(" ", "").upper()
        active = prof.get("company_status") == "active"
        score = (2 if hint and pc == hint else 0) + (1 if active else 0)
        if best is None or score > best[0]:
            best = (score, num)
    return best[1] if best else None


def _corporate_psc_parents(client, number, hint_postcode=""):
    """Yield UK company numbers that are active corporate PSCs of `number`."""
    for psc in client.psc(number).get("items", []):
        if psc.get("ceased"):
            continue
        if not psc.get("kind", "").startswith(("corporate", "legal")):
            continue
        idn = psc.get("identification", {}) or {}
        reg = (idn.get("registration_number") or "").strip()
        resolved = _resolve_uk_psc_number(reg, idn.get("country_registered"))
        if resolved:
            yield resolved
        elif not reg and psc.get("name"):
            # no reg number on the PSC record -> resolve by name
            resolved = _resolve_company_by_name(client, psc["name"], hint_postcode)
            if resolved:
                yield resolved


def walk_up(client: CompaniesHouseClient, sg: StructureGraph, anchor_num: str,
            max_depth: int = 25) -> list[str]:
    """Follow active corporate PSC edges upward to the ultimate UK owner."""
    chain = [anchor_num]
    seen = {anchor_num}
    current = anchor_num
    expand_company(client, sg, current, role="anchor")
    for _ in range(max_depth):
        prof = client.company(current)
        cur_pc = (prof.get("registered_office_address", {})
                  .get("postal_code", "") if prof else "")
        parents = [p for p in _corporate_psc_parents(client, current, cur_pc)
                   if p not in seen]
        if not parents:
            break
        nxt = parents[0]
        expand_company(client, sg, nxt, role="owner")
        chain.append(nxt)
        seen.add(nxt)
        current = nxt
    return chain


# --------------------------------------------------------------------------
# Phase 3b: member discovery
# --------------------------------------------------------------------------
def discover_members(client: CompaniesHouseClient, sg: StructureGraph,
                     name_stem: str, postcodes: list[str],
                     max_candidates: int = 40) -> list[str]:
    """Find candidate group members by name stem and shared registered office.

    Two defensible, bounded heuristics (Companies House has no list-subsidiaries
    endpoint):

      1. Name stem: the top `max_candidates` relevance-ranked search hits for the
         anchor's distinctive name token.
      2. Shared registered office: companies at the anchor's office postcode(s),
         but only when that address is not a shared-service address (a formation
         agent or accountant hosting very many unrelated companies). Such
         addresses are skipped, because co-location there carries no signal and
         would otherwise pull in hundreds of irrelevant companies.

    Every surfaced candidate is expanded into the graph so classify() can judge
    it on ownership topology; name-stem hits are expanded first as the more
    relevant set. Returns the candidate company numbers expanded.
    """
    name_hits: list[str] = []
    for item in client.search_companies(
            name_stem, items_per_page=max_candidates).get("items", []):
        num = item.get("company_number")
        if num and num not in name_hits:
            name_hits.append(num)

    office_hits: set[str] = set()
    for pc in postcodes[:3]:
        probe = client.advanced_search(location=pc, size=1)
        total = int(probe.get("hits") or 0)
        # record the true occupancy so the classifier can discount shared-service
        # addresses even when their co-located companies are not expanded.
        sg.set_office_occupancy(pc, total)
        # skip obvious shared-service addresses (formation agents / accountants),
        # which host very many unrelated companies and carry no group signal.
        if total == 0 or total > OFFICE_SHARED_MAX:
            continue
        res = client.advanced_search(location=pc,
                                     size=min(total, OFFICE_SHARED_MAX))
        for item in res.get("items", []):
            num = item.get("company_number")
            if num:
                office_hits.add(num)

    ordered = name_hits + [n for n in sorted(office_hits) if n not in name_hits]
    added = []
    for num in ordered:
        if expand_company(client, sg, num, role="candidate"):
            added.append(num)
    return added


# --------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------
@dataclass
class Classification:
    company_number: str
    name: str
    label: str            # Confirmed | Probable | Possible | Excluded
    evidence: list[str]


def _active_controls_subgraph(g: nx.MultiDiGraph) -> nx.Graph:
    h = nx.Graph()
    for u, v, d in g.edges(data=True):
        if d.get("rel") == "CONTROLS" and not d.get("ceased"):
            h.add_edge(u, v)
    return h


def classify(sg: StructureGraph, anchor_num: str) -> list[Classification]:
    g = sg.g
    sg.address_fan_out()
    anchor_id = company_id(anchor_num)

    # backbone = anchor's weakly-connected component in active CONTROLS subgraph
    ctrl = _active_controls_subgraph(g)
    backbone: set[str] = set()
    if anchor_id in ctrl:
        backbone = nx.node_connected_component(ctrl, anchor_id)

    # undirected view for shared-attribute reasoning
    undirected = g.to_undirected(as_view=True)

    results = []
    for nid in sg.companies():
        d = g.nodes[nid]
        if d.get("status") == "(stub)":
            continue
        evidence = []
        if nid in backbone:
            # describe the path briefly
            evidence.append("active PSC ownership path to anchor/owner")
            results.append(Classification(d["company_number"], d.get("name", ""),
                                          "Confirmed", evidence))
            continue
        if nid == anchor_id:
            results.append(Classification(d["company_number"], d.get("name", ""),
                                          "Confirmed", ["anchor"]))
            continue

        # shared connectors with backbone companies
        shared_people, shared_low_addr, shared_high_addr = [], [], []
        for nb in undirected.neighbors(nid):
            nd = g.nodes[nb]
            if nd.get("kind") == "person":
                # is this person also linked to a backbone company?
                if any(c in backbone for c in undirected.neighbors(nb)):
                    shared_people.append(nd.get("name"))
            elif nd.get("kind") == "address":
                if any(c in backbone for c in undirected.neighbors(nb)):
                    if (nd.get("fan_out") or 0) > HIGH_FAN_OUT:
                        shared_high_addr.append(nd.get("address"))
                    else:
                        shared_low_addr.append(nd.get("address"))

        connectors = 0
        if shared_people:
            connectors += 1
            evidence.append(f"shared officer(s): {', '.join(filter(None, shared_people[:3]))}")
        if shared_low_addr:
            connectors += 1
            evidence.append(f"shared registered office: {shared_low_addr[0]}")
        if shared_high_addr and not shared_low_addr:
            evidence.append(f"shared high-traffic address (discounted): {shared_high_addr[0]}")

        if connectors >= 2:
            label = "Probable"
        elif connectors == 1:
            label = "Possible"
        else:
            label = "Excluded"
            if not evidence:
                evidence.append("no PSC path and no shared low-traffic connector")
        results.append(Classification(d["company_number"], d.get("name", ""),
                                      label, evidence))

    order = {"Confirmed": 0, "Probable": 1, "Possible": 2, "Excluded": 3}
    results.sort(key=lambda r: (order[r.label], r.name or ""))
    return results
