"""Visualise a discovery graph.

Modes:

  confirmed   Clean ownership tree: Confirmed companies + active CONTROLS edges
              only. The unambiguous picture of who owns whom (the usual choice).

  probables   One focused 'why is X Probable/Possible?' graph per soft-classified
              company, written to --outdir.

  connectors  Company nodes PLUS the shared Person and Address nodes that
              actually link them (an officer/PSC sitting on >=2 boards, or a
              registered office shared by >=2 companies). This shows the
              *evidence* behind Probable/Possible classifications instead of
              asserting an ownership edge we cannot prove.

  tree        Like confirmed, but also includes Excluded companies and stubs
              (diagnostic; rarely needed).

    python -m companies_house_diligence.viz "$D/structure.graphml" \
        --classes "$D/structure.json" --mode confirmed \
        --out "$D/confirmed_tree.png"

    python -m companies_house_diligence.viz "$D/structure.graphml" \
        --classes "$D/structure.json" --mode connectors \
        --out "$D/connectors.png"
"""
from __future__ import annotations

import json
import math
import argparse
from collections import defaultdict

import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.lines as mlines

COLORS = {"Confirmed": "#2e7d32", "Probable": "#f9a825",
          "Possible": "#ef6c00", "Excluded": "#c62828", "stub": "#b0bec5"}
PERSON_COLOR = "#1565c0"
ADDR_COLOR = "#6a1b9a"


def included_companies(g, label, include_excluded, include_stubs):
    keep = {}
    for n, d in g.nodes(data=True):
        if d.get("kind") != "company":
            continue
        lab = label.get(d.get("company_number", ""), "stub")
        if lab == "Excluded" and not include_excluded:
            continue
        if lab == "stub" and not include_stubs:
            continue
        keep[n] = lab
    return keep


def _short(name, n=24):
    name = name or ""
    return name if len(name) <= n else name[:n - 1] + "…"


# --------------------------------------------------------------------------
# tree mode
# --------------------------------------------------------------------------
def build_tree(g, keep):
    H = nx.DiGraph()
    for n, lab in keep.items():
        d = g.nodes[n]
        H.add_node(n, label=f"{_short(d.get('name') or d.get('company_number'))}\n"
                            f"{d.get('company_number','')}", cls=lab)
    for u, v, d in g.edges(data=True):
        if d.get("rel") == "CONTROLS" and not str(d.get("ceased", "")).lower().startswith("t"):
            if u in H and v in H:
                H.add_edge(u, v)
    return H


def layered_pos(H, orient="TB", x_gap=2.6, y_gap=2.4):
    """Position nodes by ownership depth; one full-width row per layer.

    Wide layers are NOT wrapped — every node in a layer sits on a single row,
    spread as wide as needed. The caller sizes the canvas to fit.
    """
    roots = [n for n in H if H.in_degree(n) == 0] or list(H.nodes)[:1]
    depth = {}
    for r in roots:
        for n, d in nx.shortest_path_length(H, r).items():
            depth[n] = max(depth.get(n, 0), d)
    for n in H:
        depth.setdefault(n, 0)
    layers = defaultdict(list)
    for n, dd in depth.items():
        layers[dd].append(n)
    pos = {}
    for dd in sorted(layers):
        nodes = sorted(layers[dd], key=lambda n: H.nodes[n]["label"])
        w = len(nodes)
        for i, n in enumerate(nodes):
            pos[n] = ((i - (w - 1) / 2) * x_gap, -dd * y_gap)
    if orient == "LR":
        pos = {n: (-y, x) for n, (x, y) in pos.items()}
    return pos


def _figsize_for(pos, min_w=20, min_h=12, scale=0.6, cap=250):
    """Size the canvas to the layout extent so nothing gets cramped."""
    xs = [p[0] for p in pos.values()] or [0]
    ys = [p[1] for p in pos.values()] or [0]
    w = max(min_w, min(cap, (max(xs) - min(xs)) * scale + 4))
    h = max(min_h, min(cap, (max(ys) - min(ys)) * scale + 4))
    return (w, h)


def draw_tree(ax, H, pos):
    colors = [COLORS.get(H.nodes[n]["cls"], "#b0bec5") for n in H]
    nx.draw_networkx_edges(H, pos, ax=ax, edge_color="#888", arrows=True,
                           arrowsize=10, width=0.9, alpha=0.55,
                           connectionstyle="arc3,rad=0.02")
    nx.draw_networkx_nodes(H, pos, ax=ax, node_color=colors, node_size=520, alpha=0.95)
    nx.draw_networkx_labels(H, pos, ax=ax,
                            labels={n: H.nodes[n]["label"] for n in H}, font_size=5)
    handles = [mpatches.Patch(color=c, label=k) for k, c in COLORS.items()]
    ax.legend(handles=handles, loc="upper left", fontsize=10)


# --------------------------------------------------------------------------
# connectors mode
# --------------------------------------------------------------------------
def build_connectors(g, keep, min_degree=2, max_addr_fan=80):
    """Company nodes + the shared person/address nodes linking >=min_degree of them."""
    H = nx.Graph()
    for n, lab in keep.items():
        d = g.nodes[n]
        H.add_node(n, kind="company",
                   label=f"{_short(d.get('name') or d.get('company_number'))}",
                   cls=lab)
    # candidate connector nodes
    for n, d in g.nodes(data=True):
        if d.get("kind") not in ("person", "address"):
            continue
        comp_neighbours = [m for m in g.to_undirected().neighbors(n) if m in keep]
        if len(set(comp_neighbours)) < min_degree:
            continue
        if d.get("kind") == "address":
            # skip giant shared-service addresses that would dominate
            if len(set(comp_neighbours)) > max_addr_fan:
                continue
            lab = _short(d.get("address", ""), 30)
        else:
            lab = _short(d.get("name", ""), 22)
        H.add_node(n, kind=d["kind"], label=lab, cls=d["kind"])
        for m in set(comp_neighbours):
            H.add_edge(n, m, rel=d["kind"])
    # also keep hard ownership edges between companies for context
    for u, v, d in g.edges(data=True):
        if d.get("rel") == "CONTROLS" and not str(d.get("ceased", "")).lower().startswith("t"):
            if u in keep and v in keep:
                H.add_edge(u, v, rel="CONTROLS")
    # drop company nodes that ended up isolated
    H.remove_nodes_from([n for n in list(H) if H.degree(n) == 0])
    return H


def draw_connectors(ax, H):
    pos = nx.spring_layout(H, seed=11, k=1.8, iterations=300)
    comps = [n for n, d in H.nodes(data=True) if d["kind"] == "company"]
    persons = [n for n, d in H.nodes(data=True) if d["kind"] == "person"]
    addrs = [n for n, d in H.nodes(data=True) if d["kind"] == "address"]

    own = [(u, v) for u, v, d in H.edges(data=True) if d.get("rel") == "CONTROLS"]
    offi = [(u, v) for u, v, d in H.edges(data=True) if d.get("rel") == "person"]
    addr_e = [(u, v) for u, v, d in H.edges(data=True) if d.get("rel") == "address"]
    nx.draw_networkx_edges(H, pos, ax=ax, edgelist=addr_e, edge_color=ADDR_COLOR,
                           style="dotted", width=0.7, alpha=0.35)
    nx.draw_networkx_edges(H, pos, ax=ax, edgelist=offi, edge_color=PERSON_COLOR,
                           width=0.7, alpha=0.4)
    nx.draw_networkx_edges(H, pos, ax=ax, edgelist=own, edge_color="#444",
                           width=1.4, alpha=0.8)

    nx.draw_networkx_nodes(H, pos, ax=ax, nodelist=comps,
                           node_color=[COLORS.get(H.nodes[n]["cls"], "#b0bec5") for n in comps],
                           node_size=480, alpha=0.95)
    nx.draw_networkx_nodes(H, pos, ax=ax, nodelist=persons, node_color=PERSON_COLOR,
                           node_shape="s", node_size=160, alpha=0.85)
    nx.draw_networkx_nodes(H, pos, ax=ax, nodelist=addrs, node_color=ADDR_COLOR,
                           node_shape="D", node_size=160, alpha=0.85)
    nx.draw_networkx_labels(H, pos, ax=ax,
                            labels={n: H.nodes[n]["label"] for n in H}, font_size=4.5)
    handles = [mpatches.Patch(color=COLORS["Confirmed"], label="Confirmed company"),
               mpatches.Patch(color=COLORS["Probable"], label="Probable company"),
               mpatches.Patch(color=COLORS["Possible"], label="Possible company"),
               mlines.Line2D([], [], color=PERSON_COLOR, marker="s", linestyle="",
                             label="shared person (officer/PSC)"),
               mlines.Line2D([], [], color=ADDR_COLOR, marker="D", linestyle="",
                             label="shared address"),
               mlines.Line2D([], [], color="#444", label="ownership (CONTROLS)"),
               mlines.Line2D([], [], color=PERSON_COLOR, alpha=0.5, label="officer-of"),
               mlines.Line2D([], [], color=ADDR_COLOR, linestyle=":", label="registered-at")]
    ax.legend(handles=handles, loc="upper left", fontsize=9)


# --------------------------------------------------------------------------
# focused 'why probable' mode
# --------------------------------------------------------------------------
def build_focus(g, target, confirmed):
    """Small graph: the target company + the shared person/address nodes that
    link it to confirmed companies + those confirmed companies."""
    F = nx.Graph()
    td = g.nodes[target]
    F.add_node(target, kind="company", role="target",
               label=f"{_short(td.get('name') or td.get('company_number'))}\n"
                     f"{td.get('company_number','')}", cls="Probable")
    ug = g.to_undirected()
    for conn in ug.neighbors(target):
        cd = g.nodes[conn]
        if cd.get("kind") not in ("person", "address"):
            continue
        linked_confirmed = [m for m in ug.neighbors(conn) if m in confirmed]
        if not linked_confirmed:
            continue
        if cd["kind"] == "address":
            F.add_node(conn, kind="address", label=_short(cd.get("address", ""), 30),
                       cls="address")
        else:
            F.add_node(conn, kind="person", label=_short(cd.get("name", ""), 22),
                       cls="person")
        F.add_edge(target, conn, rel=cd["kind"])
        for c in linked_confirmed:
            ccd = g.nodes[c]
            F.add_node(c, kind="company", role="confirmed",
                       label=f"{_short(ccd.get('name') or ccd.get('company_number'))}\n"
                             f"{ccd.get('company_number','')}", cls="Confirmed")
            F.add_edge(conn, c, rel=cd["kind"])
    return F


def draw_focus(ax, F, target):
    persons = [n for n, d in F.nodes(data=True) if d["kind"] == "person"]
    addrs = [n for n, d in F.nodes(data=True) if d["kind"] == "address"]
    confirmed = [n for n, d in F.nodes(data=True)
                 if d["kind"] == "company" and d.get("role") == "confirmed"]
    # radial layout: target centre, connectors ring, confirmed outer
    pos = {target: (0, 0)}
    conns = persons + addrs
    for i, n in enumerate(conns):
        a = 2 * math.pi * i / max(len(conns), 1)
        pos[n] = (math.cos(a), math.sin(a))
    for i, n in enumerate(confirmed):
        a = 2 * math.pi * i / max(len(confirmed), 1)
        pos[n] = (2.4 * math.cos(a), 2.4 * math.sin(a))

    offi = [(u, v) for u, v, d in F.edges(data=True) if d.get("rel") == "person"]
    addr_e = [(u, v) for u, v, d in F.edges(data=True) if d.get("rel") == "address"]
    nx.draw_networkx_edges(F, pos, ax=ax, edgelist=addr_e, edge_color=ADDR_COLOR,
                           style="dotted", width=0.8, alpha=0.5)
    nx.draw_networkx_edges(F, pos, ax=ax, edgelist=offi, edge_color=PERSON_COLOR,
                           width=0.9, alpha=0.55)
    nx.draw_networkx_nodes(F, pos, ax=ax, nodelist=[target], node_color=COLORS["Probable"],
                           node_size=1400, alpha=0.95)
    nx.draw_networkx_nodes(F, pos, ax=ax, nodelist=confirmed, node_color=COLORS["Confirmed"],
                           node_size=900, alpha=0.95)
    nx.draw_networkx_nodes(F, pos, ax=ax, nodelist=persons, node_color=PERSON_COLOR,
                           node_shape="s", node_size=320, alpha=0.9)
    nx.draw_networkx_nodes(F, pos, ax=ax, nodelist=addrs, node_color=ADDR_COLOR,
                           node_shape="D", node_size=320, alpha=0.9)
    nx.draw_networkx_labels(F, pos, ax=ax,
                            labels={n: F.nodes[n]["label"] for n in F}, font_size=6)
    handles = [mpatches.Patch(color=COLORS["Probable"], label="target (this company)"),
               mpatches.Patch(color=COLORS["Confirmed"], label="confirmed group company"),
               mlines.Line2D([], [], color=PERSON_COLOR, marker="s", linestyle="",
                             label="shared person"),
               mlines.Line2D([], [], color=ADDR_COLOR, marker="D", linestyle="",
                             label="shared address")]
    ax.legend(handles=handles, loc="upper left", fontsize=9)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("graphml")
    ap.add_argument("--classes", required=True)
    ap.add_argument("--out", default="output/structure.png",
                    help="output file (confirmed/connectors/tree modes)")
    ap.add_argument("--outdir", default="output/probables",
                    help="output directory (probables mode)")
    ap.add_argument("--mode",
                    choices=["confirmed", "probables", "tree", "connectors"],
                    default="confirmed")
    ap.add_argument("--orient", choices=["TB", "LR"], default="TB")
    ap.add_argument("--include-excluded", action="store_true")
    ap.add_argument("--include-stubs", action="store_true")
    ap.add_argument("--min-degree", type=int, default=2)
    args = ap.parse_args(argv)

    g = nx.read_graphml(args.graphml)
    data = json.loads(open(args.classes).read())
    label = {c["company_number"]: c["label"] for c in data["classifications"]}

    if args.mode == "confirmed":
        # clean ownership tree: Confirmed companies only, no people/addresses
        keep = {n: lab for n, lab in
                included_companies(g, label, False, args.include_stubs).items()
                if lab == "Confirmed"}
        H = build_tree(g, keep)
        pos = layered_pos(H, args.orient)
        fig, ax = plt.subplots(figsize=_figsize_for(pos))
        draw_tree(ax, H, pos)
        ax.set_title("Confirmed corporate structure: ownership tree "
                     f"({args.orient}); arrows point controller → controlled",
                     fontsize=13)
        ax.axis("off"); fig.tight_layout()
        fig.savefig(args.out, dpi=150, bbox_inches="tight")
        print("wrote", args.out, f"({H.number_of_nodes()} confirmed companies)")
        return

    if args.mode == "probables":
        import os, re
        os.makedirs(args.outdir, exist_ok=True)
        confirmed = {n for n, lab in
                     included_companies(g, label, False, False).items()
                     if lab == "Confirmed"}
        keep = included_companies(g, label, args.include_excluded, False)
        targets = [(n, lab) for n, lab in keep.items()
                   if lab in ("Probable", "Possible")]
        written = []
        for node, lab in targets:
            F = build_focus(g, node, confirmed)
            if F.number_of_edges() == 0:
                continue
            fig, ax = plt.subplots(figsize=(14, 11))
            draw_focus(ax, F, node)
            name = g.nodes[node].get("name", "")
            num = g.nodes[node].get("company_number", "")
            ax.set_title(f"Why '{name}' ({num}) is classified {lab}\n"
                         "shared people / addresses linking it to confirmed group",
                         fontsize=12)
            ax.axis("off"); fig.tight_layout()
            safe = re.sub(r"[^A-Za-z0-9]+", "_", f"{lab}_{num}_{name}")[:80]
            p = os.path.join(args.outdir, safe + ".png")
            fig.savefig(p, dpi=140, bbox_inches="tight")
            plt.close(fig)
            written.append(p)
        print(f"wrote {len(written)} focused graphs to {args.outdir}/")
        for p in written:
            print("   ", p)
        return

    if args.mode == "tree":
        keep = included_companies(g, label, args.include_excluded, args.include_stubs)
        H = build_tree(g, keep)
        pos = layered_pos(H, args.orient)
        fig, ax = plt.subplots(figsize=_figsize_for(pos))
        draw_tree(ax, H, pos)
        ax.set_title("Corporate structure: ownership tree "
                     f"({args.orient})", fontsize=13)
    else:  # connectors
        keep = included_companies(g, label, args.include_excluded, args.include_stubs)
        H = build_connectors(g, keep, args.min_degree)
        fig, ax = plt.subplots(figsize=(22, 18))
        draw_connectors(ax, H)
        ax.set_title("Corporate structure: shared people and addresses "
                     "(evidence view)", fontsize=13)

    ax.axis("off")
    fig.tight_layout()
    fig.savefig(args.out, dpi=150, bbox_inches="tight")
    print("wrote", args.out, f"({H.number_of_nodes()} nodes, {H.number_of_edges()} edges)")


if __name__ == "__main__":
    main()
