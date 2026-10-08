"""Standalone Streamlit admin portal.

Run separately from the normal user application:
    streamlit run admin_app.py --server.port 8502

The normal app.py is intentionally untouched.
"""
import os
from datetime import datetime

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="ResearchAI · Admin",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Playfair+Display:wght@600;700&display=swap');
    html, body, [class*="css"] { font-family:'DM Sans',sans-serif; }
    .stApp { background:linear-gradient(135deg,#fbfaff 0%,#f7f3fb 58%,#f2f6ff 100%); }
    [data-testid="stSidebar"] { background:rgba(255,255,255,.94); border-right:1px solid #ebe6f2; }
    .admin-brand { padding:10px 4px 24px; }
    .mark { display:inline-flex;width:40px;height:40px;border-radius:13px;align-items:center;justify-content:center;
            color:#fff;background:linear-gradient(135deg,#7c3aed,#a855f7);font-weight:700; }
    .brand-title { font-size:19px;font-weight:700;margin-left:10px;color:#17151f;vertical-align:middle; }
    .eyebrow { color:#7c3aed;font-weight:700;font-size:12px;text-transform:uppercase;letter-spacing:1.8px; }
    .hero h1 { font-family:'Playfair Display',serif;font-size:42px;line-height:1.08;color:#17151f;margin:4px 0 8px; }
    .hero p { color:#77727f; }
    .login-card { max-width:470px;margin:9vh auto 0;background:#fff;border:1px solid #ebe6f2;border-radius:24px;
                  padding:34px;box-shadow:0 18px 60px rgba(44,30,70,.10); }
    .metric { background:rgba(255,255,255,.85);border:1px solid #ebe6f2;border-radius:18px;padding:18px;
              box-shadow:0 8px 30px rgba(44,30,70,.05); }
    .metric .v { font-size:27px;font-weight:700;color:#17151f; }
    .metric .l { color:#77727f;font-size:12px;margin-top:3px; }
    div.stButton > button { border-radius:12px;font-weight:600; }
    </style>
    """,
    unsafe_allow_html=True,
)

if "admin_token" not in st.session_state:
    st.session_state.admin_token = None


def admin_headers():
    return {"Authorization": f"Bearer {st.session_state.admin_token}"}


def admin_request(method, path, **kwargs):
    return requests.request(
        method,
        f"{API_URL}{path}",
        headers={**admin_headers(), **kwargs.pop("headers", {})},
        timeout=30,
        **kwargs,
    )


def admin_login(email, password):
    try:
        r = requests.post(
            f"{API_URL}/admin/login",
            json={"email": email, "password": password},
            timeout=20,
        )
    except requests.RequestException as exc:
        st.error(f"Could not connect to the backend: {exc}")
        return
    if r.status_code == 200:
        st.session_state.admin_token = r.json()["access_token"]
        st.rerun()
    st.error("Invalid admin credentials." if r.status_code == 401 else f"Login failed ({r.status_code}).")


def admin_logout():
    st.session_state.admin_token = None
    st.rerun()


def login_page():
    st.markdown(
        """
        <div class="login-card">
            <div class="eyebrow">Private administration</div>
            <h1 style="font-family:'Playfair Display',serif;color:#17151f;">Admin portal</h1>
            <p style="color:#77727f;">Sign in to view application usage and account analytics.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.form("admin_login"):
        email = st.text_input("Admin email", placeholder="admin@example.com")
        password = st.text_input("Admin password", type="password")
        if st.form_submit_button("Sign in to admin", type="primary", use_container_width=True):
            admin_login(email, password)


def dashboard():
    with st.sidebar:
        st.markdown(
            '<div class="admin-brand"><span class="mark">✦</span><span class="brand-title">ResearchAI Admin</span></div>',
            unsafe_allow_html=True,
        )
        st.caption("Private administration portal")
        st.divider()
        if st.button("🚪 Sign out", use_container_width=True):
            admin_logout()

    stats_r = admin_request("GET", "/admin/stats")
    if stats_r.status_code == 401:
        admin_logout()
    if stats_r.status_code != 200:
        st.error("Unable to load admin statistics.")
        return
    stats = stats_r.json()

    st.markdown(
        '<div class="hero"><div class="eyebrow">Overview</div><h1>Admin dashboard</h1>'
        '<p>Private application analytics. This information is not exposed in the normal user interface.</p></div>',
        unsafe_allow_html=True,
    )

    cols = st.columns(5)
    metrics = [
        ("👥", stats["total_users"], "Total users"),
        ("🟢", stats["active_users"], "Users who logged in"),
        ("💬", stats["total_conversations"], "Conversations"),
        ("✦", stats["total_messages"], "Messages"),
        ("📄", stats["total_documents"], "Documents"),
    ]
    for col, (icon, value, label) in zip(cols, metrics):
        with col:
            st.markdown(
                f'<div class="metric"><div class="v">{icon} {value}</div><div class="l">{label}</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown("### 👥 Users")
    users_r = admin_request("GET", "/admin/users")
    if users_r.status_code == 200:
        users = users_r.json()
        if users:
            df = pd.DataFrame(users)
            for c in ("created_at", "last_login"):
                if c in df:
                    df[c] = df[c].fillna("—")
            st.dataframe(
                df[["id", "username", "email", "created_at", "last_login", "login_count"]],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No users yet.")
    else:
        st.error("Could not load users.")

    st.markdown("### 💬 Recent conversations")
    conv_r = admin_request("GET", "/admin/conversations")
    if conv_r.status_code == 200:
        conversations = conv_r.json()
        if conversations:
            df = pd.DataFrame(conversations)
            st.dataframe(
                df[["id", "title", "username", "email", "message_count", "created_at", "updated_at"]],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No conversations yet.")
    else:
        st.error("Could not load conversations.")


if st.session_state.admin_token:
    dashboard()
else:
    login_page()
