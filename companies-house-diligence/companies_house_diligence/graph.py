"""Graph model for corporate-structure discovery.

A single networkx.MultiDiGraph holds every discovered node and edge with full
provenance. Node and edge helpers enforce consistent identity keys so that the
same company / person / address discovered via different API calls merges onto
one node.

Node id conventions (the string used as the networkx node key):
    Company        -> "company:<company_number>"
    ExternalEntity -> "ext:<slug-of-name>"
    Person         -> "person:<slug-surname-forename>:<dob_my>"
    Address        -> "addr:<premises>|<postcode>"  (normalised, upper)

Every node has a 'kind' attribute in {company, external, person, address}.
Every edge has a 'rel' attribute and a 'source' (provenance) attribute.
"""

from __future__ import annotations

import re
from typing import Optional

import networkx as nx


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def _norm_postcode(pc: str) -> str:
    return re.sub(r"\s+", "", (pc or "")).upper()


# --------------------------------------------------------------------------
# id builders
# --------------------------------------------------------------------------
def company_id(number: str) -> str:
    return f"company:{number}"


def external_id(name: str, jurisdiction: str = "") -> str:
    return f"ext:{_slug(name)}" + (f":{_slug(jurisdiction)}" if jurisdiction else "")


def person_id(name: str, dob_month: Optional[int] = None,
              dob_year: Optional[int] = None) -> str:
    dob = f"{dob_year or '?'}-{dob_month or '?'}"
    return f"person:{_slug(name)}:{dob}"


def address_id(premises: str, postcode: str, fallback: str = "") -> str:
    key = f"{_slug(premises)}|{_norm_postcode(postcode)}"
    if key == "|":
        key = _slug(fallback)
    return f"addr:{key}"


def _ch_address(a: dict) -> tuple[str, str]:
    """Return (node_id, human_readable) for a CH address dict."""
    premises = a.get("premises", "") or a.get("address_line_1", "")
    postcode = a.get("postal_code", "")
    parts = [a.get("premises"), a.get("address_line_1"), a.get("address_line_2"),
             a.get("locality"), a.get("region"), a.get("postal_code"),
             a.get("country")]
    human = ", ".join(p for p in parts if p)
    return address_id(premises, postcode, fallback=human), human


class StructureGraph:
    def __init__(self):
        self.g = nx.MultiDiGraph()
        # true occupancy of an office postcode (from advanced-search hits),
        # used to recognise shared-service addresses even when we did not
        # expand the companies registered there.
        self.office_occupancy: dict[str, int] = {}

    def set_office_occupancy(self, postcode: str, count: int) -> None:
        pc = _norm_postcode(postcode)
        if pc:
            self.office_occupancy[pc] = max(count, self.office_occupancy.get(pc, 0))

    # -- node upserts ------------------------------------------------------
    def add_company(self, profile: dict, *, role: str = "", source: str = "") -> str:
        num = profile.get("company_number")
        nid = company_id(num)
        attrs = {
            "kind": "company",
            "company_number": num,
            "name": profile.get("company_name"),
            "status": profile.get("company_status"),
            "type": profile.get("type"),
            "incorporated_on": profile.get("date_of_creation"),
            "sic_codes": profile.get("sic_codes", []),
            "accounts_type": (profile.get("accounts", {})
                              .get("last_accounts", {}).get("type")),
            "has_charges": profile.get("has_charges"),
            "former_names": [p.get("name") for p in
                             profile.get("previous_company_names", []) or []],
            "source": source or "company-profile",
        }
        if role:
            attrs["role"] = role
        self._upsert(nid, attrs)
        # link registered office
        roa = profile.get("registered_office_address")
        if roa:
            aid, human = _ch_address(roa)
            self.add_address(aid, human, postcode=roa.get("postal_code"))
            self.add_edge(nid, aid, "REGISTERED_AT", source="company-profile")
        return nid

    def add_external(self, name: str, *, jurisdiction: str = "",
                     reg_no: str = "", legal_form: str = "", source: str = "") -> str:
        nid = external_id(name, jurisdiction)
        self._upsert(nid, {
            "kind": "external",
            "name": name,
            "jurisdiction": jurisdiction,
            "foreign_reg_no": reg_no,
            "legal_form": legal_form,
            "source": source,
        })
        return nid

    def add_person(self, name: str, *, dob_month=None, dob_year=None,
                   nationality: str = "", occupation: str = "",
                   source: str = "") -> str:
        nid = person_id(name, dob_month, dob_year)
        self._upsert(nid, {
            "kind": "person",
            "name": name,
            "dob_month": dob_month,
            "dob_year": dob_year,
            "nationality": nationality,
            "occupation": occupation,
            "source": source,
        })
        return nid

    def add_address(self, nid: str, human: str, postcode: str = "") -> str:
        attrs = {"kind": "address", "address": human}
        if postcode:
            attrs["postcode"] = _norm_postcode(postcode)
        self._upsert(nid, attrs)
        return nid

    def _upsert(self, nid: str, attrs: dict):
        if self.g.has_node(nid):
            for k, v in attrs.items():
                if v not in (None, "", []) or k not in self.g.nodes[nid]:
                    self.g.nodes[nid][k] = v
        else:
            self.g.add_node(nid, **attrs)

    # -- edges -------------------------------------------------------------
    def add_edge(self, src: str, dst: str, rel: str, **props):
        # avoid exact duplicate (same rel + key props) edges
        for _, _, d in self.g.edges(src, data=True):
            if d.get("rel") == rel and d.get("_dst") == dst and \
               d.get("appointed_on") == props.get("appointed_on") and \
               d.get("notified_on") == props.get("notified_on"):
                return
        props.update({"rel": rel, "_dst": dst})
        self.g.add_edge(src, dst, **props)

    # -- analytics helpers -------------------------------------------------
    def address_fan_out(self) -> dict[str, int]:
        """Set each address node's `fan_out`: the number of companies registered
        there. This is the larger of (a) the companies seen at the address in the
        graph and (b) the address's true occupancy from advanced-search hits, so
        that a shared-service address is recognised even when its co-located
        companies were not expanded."""
        counts: dict[str, int] = {}
        for u, v, d in self.g.edges(data=True):
            if d.get("rel") == "REGISTERED_AT":
                counts[v] = counts.get(v, 0) + 1
        for nid, nd in self.g.nodes(data=True):
            if nd.get("kind") != "address":
                continue
            edge_count = counts.get(nid, 0)
            true_occ = self.office_occupancy.get(nd.get("postcode", ""), 0)
            nd["fan_out"] = max(edge_count, true_occ)
        return counts

    def companies(self):
        return [n for n, d in self.g.nodes(data=True) if d.get("kind") == "company"]

    def to_graphml(self, path: str):
        # graphml needs scalar attrs; stringify lists
        h = self.g.copy()
        for _, d in h.nodes(data=True):
            for k, v in list(d.items()):
                if isinstance(v, (list, dict)):
                    d[k] = "; ".join(map(str, v)) if isinstance(v, list) else str(v)
                elif v is None:
                    d[k] = ""
        for _, _, d in h.edges(data=True):
            for k, v in list(d.items()):
                if isinstance(v, (list, dict)):
                    d[k] = "; ".join(map(str, v)) if isinstance(v, list) else str(v)
                elif v is None:
                    d[k] = ""
        nx.write_graphml(h, path)
