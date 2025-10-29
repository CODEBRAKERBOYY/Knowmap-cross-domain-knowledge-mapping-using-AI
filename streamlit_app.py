# streamlit_app.py
import os
import requests
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from extract_relations import load_csv, df_to_triples, triples_to_graph
from visualize_graph import graph_to_pyvis_html

# ------------------ CONFIG ------------------
BASE = os.getenv("KNOWMAP_API", "http://127.0.0.1:5001")
st.set_page_config(page_title="KnowMap", page_icon="🧠", layout="wide")
st.title("🧠 KnowMap – Milestone 1 + 2 (+ NLP Extract)")

# initialize session state
for key, default in {
    "token": None,
    "preview_df": None,
    "rel_filter": [],
    "dom_filter": []
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ------------------ UTIL ------------------
def list_upload_csvs():
    """Return CSV files inside uploads/"""
    if not os.path.isdir("uploads"):
        return []
    return sorted([f for f in os.listdir("uploads") if f.lower().endswith(".csv")])

@st.cache_data(show_spinner=False)
def cached_load_csv(path: str):
    return load_csv(path)


# ------------------ TABS ------------------
tab_auth, tab_upload, tab_sample, tab_preview, tab_graph, tab_nlp = st.tabs(
    ["🔐 Auth", "🗂️ Upload", "📦 Generate Sample", "📊 Data Preview", "🌐 Knowledge Graph", "🧠 NLP Extract"]
)


# ------------------ AUTH ------------------
with tab_auth:
    st.subheader("Login / Register")
    mode = st.radio("Choose action", ["Login", "Register"], horizontal=True)
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button(mode):
        if not email or not password:
            st.warning("Please enter both email and password.")
        else:
            try:
                url = f"{BASE}/api/auth/login" if mode == "Login" else f"{BASE}/api/auth/register"
                r = requests.post(url, json={"email": email, "password": password}, timeout=15)
                data = r.json()
                if r.ok:
                    st.success(data.get("message", "Success"))
                    st.session_state.token = data.get("token", "local-session")
                else:
                    st.error(data.get("error", r.text))
            except Exception as e:
                st.error(str(e))

    if st.session_state.token:
        st.info(f"Session active ✅ ({st.session_state.token[:10]}...)")
    else:
        st.warning("Not logged in yet.")


# ------------------ UPLOAD ------------------
with tab_upload:
    st.subheader("Upload Dataset")
    up = st.file_uploader("Select a CSV file", type=["csv"])
    if up and st.button("Upload to backend"):
        try:
            files = {"file": (up.name, up.getvalue())}
            r = requests.post(f"{BASE}/api/datasets/upload", files=files, timeout=30)
            data = r.json()
            if r.ok:
                st.success("Upload successful!")
                st.json(data)
            else:
                st.error(data.get("error", r.text))
        except Exception as e:
            st.error(str(e))


# ------------------ GENERATE / FIND SAMPLE ------------------
with tab_sample:
    st.subheader("Existing CSVs in uploads/")
    csvs = list_upload_csvs()
    if csvs:
        st.success("Found CSV files:")
        for f in csvs:
            st.write(f"- uploads/{f}")

        if st.button("Load most recent CSV"):
            latest_path = max((os.path.join("uploads", f) for f in csvs), key=os.path.getmtime)
            try:
                df_latest = cached_load_csv(latest_path)
                st.session_state.preview_df = df_latest
                st.success(f"Loaded: {latest_path}. Now check **Knowledge Graph** tab.")
            except Exception as e:
                st.error(f"Error loading file: {e}")
    else:
        st.warning("No CSV files found. Please upload one first.")


# ------------------ DATA PREVIEW ------------------
with tab_preview:
    st.subheader("Preview CSV")

    uploads_list = [f"uploads/{p}" for p in list_upload_csvs()]
    chosen = st.selectbox("Pick a file from uploads/", uploads_list)
    adhoc = st.file_uploader("Or preview a local CSV (not saved)", type=["csv"], key="preview_uploader")

    df, src = None, None
    c1, c2 = st.columns(2)
    with c1:
        if chosen and st.button("Load selected file"):
            try:
                df = cached_load_csv(chosen)
                src = chosen
            except Exception as e:
                st.error(str(e))
    with c2:
        if adhoc is not None and st.button("Preview uploaded file"):
            try:
                df = pd.read_csv(adhoc)
                src = f"(adhoc) {adhoc.name}"
            except Exception as e:
                st.error(str(e))

    if df is not None:
        st.success(f"Loaded: {src}")
        st.dataframe(df.head(50), use_container_width=True)
        st.caption(f"Rows: {len(df)} | Columns: {list(df.columns)}")
        st.session_state.preview_df = df


# ------------------ KNOWLEDGE GRAPH ------------------
with tab_graph:
    st.subheader("Build Interactive Knowledge Graph")

    df = st.session_state.get("preview_df")

    # Auto-load last uploaded CSV
    if df is None:
        csvs = list_upload_csvs()
        if csvs:
            latest = max((os.path.join("uploads", f) for f in csvs), key=os.path.getmtime)
            try:
                df = cached_load_csv(latest)
                st.session_state.preview_df = df
                st.info(f"Auto-loaded: {latest}")
            except Exception as e:
                st.error(f"Failed to auto-load CSV: {e}")

    if df is None:
        st.warning("No dataset loaded. Please upload or load a CSV first.")
        st.stop()

    # ---------- Filters ----------
    has_rel = ("relation" in df.columns)
    has_dom = ("domain" in df.columns)

    if not has_rel:
        st.error("This CSV must include at least 'entity_1', 'relation', 'entity_2'.")
        st.stop()

    rels = sorted(df["relation"].dropna().astype(str).unique().tolist())
    doms = sorted(df["domain"].dropna().astype(str).unique().tolist()) if has_dom else []

    if not st.session_state.rel_filter:
        st.session_state.rel_filter = rels
    if has_dom and not st.session_state.dom_filter:
        st.session_state.dom_filter = doms

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.session_state.rel_filter = st.multiselect("Relations", rels, default=st.session_state.rel_filter)
    with c2:
        st.session_state.dom_filter = (
            st.multiselect("Domains", doms, default=st.session_state.dom_filter) if has_dom else []
        )
    with c3:
        max_nodes = st.slider("Max nodes", 50, 1500, 400, step=50)
    with c4:
        min_degree = st.slider("Min degree", 0, 20, 2, step=1)

    focus_col1, focus_col2 = st.columns([2, 1])
    with focus_col1:
        focus_node = st.text_input("🔍 Focus node (optional)", placeholder="Albert Einstein")
    with focus_col2:
        focus_hops = st.radio("Hops", [1, 2], index=0, horizontal=True)

    if st.button("Reset filters"):
        st.session_state.rel_filter = rels
        st.session_state.dom_filter = doms if has_dom else []

    # --- Apply filters ---
    df_f = df.copy()
    if st.session_state.rel_filter:
        df_f = df_f[df_f["relation"].astype(str).isin(st.session_state.rel_filter)]
    if has_dom and st.session_state.dom_filter:
        df_f = df_f[df_f["domain"].astype(str).isin(st.session_state.dom_filter)]

    st.caption(f"Dataset rows: {len(df)} | After filters → {len(df_f)}")

    triples = df_to_triples(df_f)
    if triples.empty:
        st.warning("No triples found. Try resetting filters.")
        st.stop()

    # Download filtered triples
    csv_bytes = triples.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download filtered triples (CSV)",
        data=csv_bytes,
        file_name="knowmap_triples_filtered.csv",
        mime="text/csv",
    )

    G = triples_to_graph(triples)
    html = graph_to_pyvis_html(
        G,
        max_nodes=max_nodes,
        min_degree=min_degree,
        focus_node=focus_node.strip() or None,
        focus_hops=int(focus_hops),
    )
    components.html(html, height=750, scrolling=True)
    st.caption(f"Nodes: {G.number_of_nodes()} | Edges: {G.number_of_edges()}")


# ------------------ NLP EXTRACT ------------------
with tab_nlp:
    st.subheader("🧠 NLP: Extract subject–relation–object triples from text")
    st.caption("Backend endpoint: POST /api/nlp/extract")

    sample_text = (
        "Albert Einstein developed the theory of relativity. "
        "C. V. Raman won the Nobel Prize in Physics. "
        "Joe Biden is the president of the United States. "
        "India has the president Droupadi Murmu."
    )
    text = st.text_area("Enter text:", value=sample_text, height=150)

    c1, c2 = st.columns([1, 1])
    with c1:
        max_show = st.slider("Max triples to show", 1, 15, 3)
    with c2:
        run_btn = st.button("Extract")

    if run_btn:
        try:
            resp = requests.post(f"{BASE}/api/nlp/extract", json={"text": text}, timeout=30)
            data = resp.json()
            if resp.ok:
                triples = data.get("triples", [])[:max_show]
                st.success(f"✅ Extracted {len(triples)} triple(s).")
                if triples:
                    df_tri = pd.DataFrame(triples)
                    st.dataframe(df_tri, use_container_width=True)

                    if st.button("➕ Add these triples to current dataset (session only)"):
                        add_df = df_tri.rename(columns={
                            "subject": "entity_1",
                            "relation": "relation",
                            "object": "entity_2"
                        })
                        for col in [
                            "domain", "country", "start_year", "end_year", "notes",
                            "entity_1_type", "entity_2_type"
                        ]:
                            if col not in add_df.columns:
                                add_df[col] = None
                        if st.session_state.get("preview_df") is None:
                            st.session_state["preview_df"] = add_df
                        else:
                            st.session_state["preview_df"] = pd.concat(
                                [st.session_state["preview_df"], add_df], ignore_index=True
                            )
                        st.success("Added! Go to **Knowledge Graph** tab to visualize.")
                else:
                    st.info("No triples found. Try different text.")
            else:
                st.error(data.get("error", resp.text))
        except Exception as e:
            st.error(f"Request failed: {e}")
