# visualize_graph.py
from pyvis.network import Network
import networkx as nx
import tempfile, os

def _color_for(node_type: str, domain: str):
    # type priority first, then domain fallback
    type_colors = {
        "scientist": "#4e79a7",
        "person":    "#e15759",
        "country":   "#f28e2b",
        "concept":   "#59a14f",
        "award":     "#b07aa1",
        "institution":"#76b7b2",
        "field":     "#9c755f",
        "topic":     "#edc949",
        "discipline":"#af7aa1",
        "method":    "#8cd17d",
        "task":      "#59a14f",
    }
    domain_colors = {
        "politics": "#e15759", "science": "#4e79a7", "ai_physics": "#4e79a7",
        "ai_medicine": "#59a14f", "cross_domain": "#9c755f",
        "physics": "#4e79a7", "biology": "#59a14f", "chemistry": "#b07aa1",
        "computer_science": "#76b7b2", "mathematics": "#af7aa1",
    }
    return type_colors.get((node_type or "").lower()) or domain_colors.get((domain or "").lower()) or "#9aa0a6"

def _limit_by_degree(G: nx.Graph, min_degree: int):
    if min_degree <= 0: return G
    keep = [n for n, d in G.degree() if d >= min_degree]
    return G.subgraph(keep).copy()

def _ego_subgraph(G: nx.MultiDiGraph, center: str, hops: int = 1, max_nodes: int = 400):
    if center not in G: 
        return nx.MultiDiGraph()
    nodes = {center}
    frontier = {center}
    for _ in range(max(1, hops)):
        nxt = set()
        for u in frontier:
            nxt.update(G.successors(u))
            nxt.update(G.predecessors(u))
        nodes |= nxt
        frontier = nxt
    H = G.subgraph(list(nodes)).copy()
    # safety limit
    if H.number_of_nodes() > max_nodes:
        deg = sorted(H.degree, key=lambda x: x[1], reverse=True)[:max_nodes]
        keep = {n for n,_ in deg}
        H = H.subgraph(keep).copy()
    return H

def graph_to_pyvis_html(
    G: nx.MultiDiGraph,
    height="650px",
    width="100%",
    physics=True,
    filter_nodes=None,
    max_nodes=300,
    min_degree=0,
    focus_node=None,
    focus_hops=1,
):
    # focus or filter first
    H = G.copy()
    if focus_node:
        H = _ego_subgraph(H, focus_node, hops=focus_hops, max_nodes=max_nodes)
    if filter_nodes:
        H = H.subgraph([n for n in H.nodes if n in set(filter_nodes)]).copy()

    # degree filter & size cap
    H = _limit_by_degree(H, min_degree)
    if H.number_of_nodes() > max_nodes:
        deg = sorted(H.degree, key=lambda x: x[1], reverse=True)[:max_nodes]
        keep = {n for n,_ in deg}
        H = H.subgraph(keep).copy()

    net = Network(height=height, width=width, notebook=False, directed=True)
    net.barnes_hut() if physics else net.force_atlas_2based()

    # nodes with color + size by degree
    deg_map = dict(H.degree())
    for n, attrs in H.nodes(data=True):
        ntype  = (attrs.get("type") or "").lower()
        domain = (attrs.get("domain") or "").lower()
        title  = f"{n}<br>type: {ntype}<br>domain: {domain}"
        color  = _color_for(ntype, domain)
        size   = 8 + min(22, deg_map.get(n, 1) * 1.5)  # scale by degree
        net.add_node(n, label=n, title=title, color=color, value=size)

    # edges
    for u, v, attrs in H.edges(data=True):
        rel = attrs.get("relation","")
        s = attrs.get("start_year"); e = attrs.get("end_year")
        notes = attrs.get("notes") or ""
        title = f"{rel}"
        if s or e: title += f" ({s or ''}–{e or ''})"
        if notes:  title += f"<br>{notes}"
        net.add_edge(u, v, title=title, label=rel)

    # export safe for Streamlit
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
        net.save_graph(tmp.name)
        tmp.flush()
        html = open(tmp.name, "r", encoding="utf-8").read()
        os.unlink(tmp.name)
    return html
