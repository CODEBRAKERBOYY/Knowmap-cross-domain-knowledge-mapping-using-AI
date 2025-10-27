import streamlit as st
import requests
import json

BASE = "http://127.0.0.1:5000"   # Flask backend

st.set_page_config(page_title="KnowMap", page_icon="🧠", layout="centered")
st.title("🧠 KnowMap – Milestone 1 (Auth + Upload)")

# Session
if "token" not in st.session_state:
    st.session_state.token = None

tab_auth, tab_data = st.tabs(["🔐 Auth", "🗂️ Datasets"])

# ---------------- AUTH ----------------
with tab_auth:
    st.subheader("Login / Register")
    mode = st.radio("Choose action", ["Login", "Register"], horizontal=True)
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button(mode):
        url = f"{BASE}/api/auth/login" if mode == "Login" else f"{BASE}/api/auth/register"
        try:
            r = requests.post(url, json={"email": email, "password": password}, timeout=15)
            data = r.json()
            if r.ok:
                st.success(data.get("message", "Success"))
                st.session_state.token = data.get("token", "local-session")  # simple token for now
            else:
                st.error(data.get("error", r.text))
        except Exception as e:
            st.error(str(e))

    if st.session_state.token:
        st.info(f"Session active ✅ (token: {st.session_state.token[:12]}...)")
    else:
        st.warning("Not logged in yet.")

# ---------------- DATASETS ----------------
with tab_data:
    st.subheader("Upload a dataset file")
    if not st.session_state.token:
        st.warning("Please login/register first in the Auth tab.")
    else:
        file = st.file_uploader("Choose a file (.txt, .csv, etc.)")
        if file and st.button("Upload"):
            try:
                files = {"file": (file.name, file.getvalue())}
                r = requests.post(f"{BASE}/api/datasets/upload", files=files, timeout=30)
                data = r.json()
                if r.ok:
                    st.success("Upload successful!")
                    st.json(data)
                else:
                    st.error(data.get("error", r.text))
            except Exception as e:
                st.error(str(e))

st.caption("Milestone 1 complete: Auth + Upload UI connected to Flask API")
