"""Polished Streamlit front-end for the AI Research Assistant.

Run the backend first:
    uvicorn backend.main:app --reload
Then:
    streamlit run app.py
"""
import hashlib
import inspect
import os
from datetime import datetime

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000").rstrip("/")
CONNECTION_HELP = "Backend unavailable. Start it with `uvicorn backend.main:app --reload`."
DOCS_LABEL = "My documents"
QUESTIONS_LABEL = "PDF questions"
GENERAL_LABEL = "General knowledge"
MODE_BY_LABEL = {DOCS_LABEL: "documents", QUESTIONS_LABEL: "pdf_questions", GENERAL_LABEL: "general"}
VOICE_IN_CHAT = "accept_audio" in inspect.signature(st.chat_input).parameters

st.set_page_config(page_title="ResearchAI", page_icon="✦", layout="wide", initial_sidebar_state="expanded")


def inject_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Playfair+Display:wght@600;700&display=swap');
        :root { --ink:#17151f; --muted:#77727f; --card:#ffffff; --soft:#f7f4fb; --accent:#7c3aed; --accent2:#a855f7; --line:#ebe6f2; }
        html, body, [class*="css"] { font-family:'DM Sans',sans-serif; }
        .stApp { background:linear-gradient(135deg,#fbfaff 0%,#f7f3fb 55%,#f3f7ff 100%); }
        [data-testid="stSidebar"] { background:rgba(255,255,255,.90); border-right:1px solid var(--line); }
        [data-testid="stSidebar"] > div:first-child { padding-top:1rem; }
        .brand { padding:4px 6px 18px; }
        .brand-mark { width:38px;height:38px;border-radius:13px;background:linear-gradient(135deg,var(--accent),var(--accent2));display:inline-flex;align-items:center;justify-content:center;color:#fff;font-weight:700;box-shadow:0 8px 24px rgba(124,58,237,.25); }
        .brand-name { font-weight:700;font-size:18px;margin-left:9px;vertical-align:middle;color:var(--ink); }
        .brand-sub { color:var(--muted);font-size:11px;margin:7px 0 0 48px; }
        .hero { padding:26px 4px 10px; }
        .hero h1 { font-family:'Playfair Display',serif;font-size:42px;line-height:1.08;margin:0;color:var(--ink);letter-spacing:-1px; }
        .hero p { color:var(--muted);font-size:15px;margin-top:10px;max-width:720px; }
        .eyebrow { color:var(--accent);font-weight:700;font-size:12px;text-transform:uppercase;letter-spacing:1.8px;margin-bottom:8px; }
        .stat-card { background:rgba(255,255,255,.82);border:1px solid var(--line);border-radius:18px;padding:15px 17px;box-shadow:0 8px 30px rgba(44,30,70,.05); }
        .stat-value { font-size:23px;font-weight:700;color:var(--ink); }
        .stat-label { color:var(--muted);font-size:12px;margin-top:2px; }
        .chat-title { font-weight:700;font-size:13px;color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis; }
        .chat-meta { font-size:10px;color:var(--muted);margin-top:2px; }
        .section-label { color:#8a8394;font-size:10px;font-weight:700;letter-spacing:1.4px;text-transform:uppercase;margin:16px 4px 7px; }
        .auth-wrap { max-width:920px;margin:7vh auto 0; }
        .auth-copy { padding:25px 35px 25px 10px; }
        .auth-copy h1 { font-family:'Playfair Display',serif;font-size:50px;line-height:1.05;margin:0 0 15px;color:var(--ink); }
        .auth-copy p { color:var(--muted);font-size:16px;line-height:1.7; }
        .feature { background:rgba(255,255,255,.6);border:1px solid var(--line);border-radius:15px;padding:12px 14px;margin-top:9px;font-size:13px; }
        .auth-card { background:#fff;border:1px solid var(--line);border-radius:24px;padding:28px;box-shadow:0 18px 60px rgba(44,30,70,.10); }
        .tiny { color:var(--muted);font-size:11px; }
        div.stButton > button { border-radius:12px;border:1px solid var(--line);font-weight:600; }
        div.stButton > button[kind="primary"] { background:linear-gradient(135deg,var(--accent),var(--accent2));border:0;color:#fff; }
        .profile-card { background:var(--soft);border:1px solid var(--line);border-radius:16px;padding:12px; }
        [data-testid="stChatMessage"] { border-radius:18px; }
        .footer-note { text-align:center;color:#9b95a4;font-size:11px;padding:24px 0; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _defaults():
    return {
        "token": None, "username": None, "user": None, "messages": [],
        "documents": [], "conversations": [], "conversation_id": None,
        "mode_label": DOCS_LABEL, "flash": [], "chat_search": "", "auth_tab": "Login",
    }


for key, value in _defaults().items():
    if key not in st.session_state:
        st.session_state[key] = value

inject_css()


def flash(kind, text):
    st.session_state.flash.append((kind, text))


def show_flashes():
    for kind, text in st.session_state.flash:
        getattr(st, kind)(text)
    st.session_state.flash = []


def error_detail(response):
    try:
        detail = response.json().get("detail")
    except ValueError:
        return response.text[:300] or f"HTTP {response.status_code}"
    if isinstance(detail, list):
        return "; ".join(f"{str(x.get('loc',[''])[-1])}: {x.get('msg','invalid value')}" for x in detail)
    return str(detail) if detail else f"HTTP {response.status_code}"


def logout(message=None):
    for key in ["token", "username", "user", "messages", "documents", "conversations", "conversation_id"]:
        st.session_state[key] = None if key in ["token", "username", "user", "conversation_id"] else []
    if message:
        flash("warning", message)
    st.rerun()


def api(method, path, auth=True, timeout=60, **kwargs):
    headers = kwargs.pop("headers", {})
    if auth and st.session_state.token:
        headers["Authorization"] = f"Bearer {st.session_state.token}"
    response = requests.request(method, f"{API_URL}{path}", headers=headers, timeout=timeout, **kwargs)
    if auth and response.status_code == 401:
        logout("Your session expired. Please sign in again.")
    return response


def refresh_user():
    try:
        r = api("GET", "/auth/me", timeout=20)
        if r.status_code == 200:
            st.session_state.user = r.json()
            st.session_state.username = st.session_state.user["username"]
    except requests.RequestException:
        pass


def refresh_conversations(select_latest=False):
    try:
        r = api("GET", "/conversations", timeout=30)
        if r.status_code == 200:
            st.session_state.conversations = r.json()
            if select_latest and st.session_state.conversations:
                st.session_state.conversation_id = st.session_state.conversations[0]["id"]
    except requests.RequestException:
        pass


def load_messages(conversation_id):
    if not conversation_id:
        st.session_state.messages = []
        return
    try:
        r = api("GET", f"/conversations/{conversation_id}/messages", params={"limit": 1000}, timeout=30)
        if r.status_code == 200:
            st.session_state.messages = r.json()
    except requests.RequestException:
        pass


def refresh_documents():
    try:
        r = api("GET", "/documents")
        if r.status_code == 200:
            st.session_state.documents = r.json()
    except requests.RequestException:
        pass


def new_chat():
    try:
        r = api("POST", "/conversations", json={"title": "New research chat"})
        if r.status_code == 201:
            st.session_state.conversation_id = r.json()["id"]
            st.session_state.messages = []
            refresh_conversations()
            st.rerun()
    except requests.RequestException as exc:
        st.error(f"Could not create a new chat: {exc}")


def select_chat(cid):
    st.session_state.conversation_id = cid
    load_messages(cid)
    st.rerun()


def rename_chat(cid, title):
    try:
        r = api("PATCH", f"/conversations/{cid}", json={"title": title.strip()})
        if r.status_code == 200:
            refresh_conversations()
            load_messages(cid)
            flash("success", "Chat renamed.")
            st.rerun()
        else:
            st.error(error_detail(r))
    except requests.RequestException as exc:
        st.error(str(exc))


def delete_chat(cid):
    try:
        r = api("DELETE", f"/conversations/{cid}")
        if r.status_code == 204:
            remaining = [c for c in st.session_state.conversations if c["id"] != cid]
            st.session_state.conversations = remaining
            if remaining:
                st.session_state.conversation_id = remaining[0]["id"]
                load_messages(remaining[0]["id"])
            else:
                st.session_state.conversation_id = None
                st.session_state.messages = []
            st.rerun()
        else:
            st.error(error_detail(r))
    except requests.RequestException as exc:
        st.error(str(exc))


def authenticate(path, payload):
    try:
        r = api("POST", path, auth=False, json=payload, timeout=30)
    except requests.exceptions.ConnectionError:
        st.error(CONNECTION_HELP); return
    except requests.RequestException as exc:
        st.error(f"Request failed: {exc}"); return
    if r.status_code in (200, 201):
        data = r.json()
        st.session_state.token = data["access_token"]
        st.session_state.username = data["username"]
        refresh_user(); refresh_conversations(select_latest=True); refresh_documents()
        if st.session_state.conversations:
            load_messages(st.session_state.conversations[0]["id"])
        st.rerun()
    else:
        st.error(error_detail(r))


def auth_page():
    st.markdown('<div class="auth-wrap">', unsafe_allow_html=True)
    left, right = st.columns([1.05, .95], gap="large")
    with left:
        st.markdown(
            '<div class="auth-copy"><div class="eyebrow">Your intelligent research workspace</div>'
            '<h1>Think deeper.<br>Research faster.</h1>'
            '<p>A private AI workspace for your PDFs, questions, notes and research conversations — with every chat organised for you.</p>'
            '<div class="feature">✦ <b>Persistent conversations</b><br><span class="tiny">Pick up any previous research thread exactly where you left it.</span></div>'
            '<div class="feature">⌕ <b>Document-aware answers</b><br><span class="tiny">Ask questions about your uploaded PDFs with source context.</span></div>'
            '<div class="feature">◌ <b>Multimodal tools</b><br><span class="tiny">Voice questions, image analysis and image generation.</span></div></div>',
            unsafe_allow_html=True,
        )
    with right:
        st.markdown('<div class="auth-card">', unsafe_allow_html=True)
        st.markdown("### Welcome back ✦")
        st.caption("Sign in to continue your research workspace.")
        login, signup = st.tabs(["Sign in", "Create account"])
        with login:
            with st.form("login_form", clear_on_submit=False):
                email = st.text_input("Email", placeholder="you@example.com")
                password = st.text_input("Password", type="password", placeholder="Your password")
                submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
            if submitted:
                authenticate("/auth/login", {"email": email, "password": password})
        with signup:
            with st.form("signup_form", clear_on_submit=False):
                username = st.text_input("Name", placeholder="Your name")
                email = st.text_input("Email", key="signup_email", placeholder="you@example.com")
                password = st.text_input("Password", type="password", key="signup_password", placeholder="At least 6 characters")
                confirm = st.text_input("Confirm password", type="password")
                submitted = st.form_submit_button("Create account", type="primary", use_container_width=True)
            if submitted:
                if password != confirm:
                    st.error("Passwords do not match.")
                else:
                    authenticate("/auth/signup", {"username": username, "email": email, "password": password})
        st.markdown('<div class="footer-note">Your password is securely hashed before storage.</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    show_flashes()


def sidebar():
    with st.sidebar:
        st.markdown('<div class="brand"><span class="brand-mark">✦</span><span class="brand-name">ResearchAI</span><div class="brand-sub">Your private research desk</div></div>', unsafe_allow_html=True)
        if st.button("＋  New chat", type="primary", use_container_width=True):
            new_chat()

        st.markdown('<div class="section-label">Search chats</div>', unsafe_allow_html=True)
        st.text_input("Search", key="chat_search", placeholder="Search your conversations…", label_visibility="collapsed")
        query = st.session_state.chat_search.lower().strip()
        chats = [c for c in st.session_state.conversations if not query or query in c["title"].lower()]

        st.markdown('<div class="section-label">Recent conversations</div>', unsafe_allow_html=True)
        if not chats:
            st.caption("No saved chats yet. Start a new conversation above.")
        for c in chats[:30]:
            active = c["id"] == st.session_state.conversation_id
            cols = st.columns([6, 1])
            label = ("●  " if active else "   ") + c["title"]
            if cols[0].button(label, key=f"chat::{c['id']}", use_container_width=True):
                select_chat(c["id"])
            with cols[1].popover("⋯", use_container_width=True):
                new_title = st.text_input("Chat name", value=c["title"], key=f"rename::{c['id']}")
                if st.button("Rename", key=f"rename_btn::{c['id']}", use_container_width=True):
                    rename_chat(c["id"], new_title)
                if st.button("Delete chat", key=f"delete::{c['id']}", use_container_width=True):
                    delete_chat(c["id"])

        st.markdown("---")
        st.markdown('<div class="section-label">Workspace</div>', unsafe_allow_html=True)
        st.subheader("📄 Documents")
        uploaded_files = st.file_uploader("Choose PDF files", type=["pdf"], accept_multiple_files=True, label_visibility="collapsed")
        if st.button("Process documents", disabled=not uploaded_files, use_container_width=True):
            upload_files(uploaded_files)
        if not st.session_state.documents:
            st.caption("No documents uploaded yet.")
        for doc in st.session_state.documents:
            a, b = st.columns([6, 1])
            a.caption(f"{doc['filename']} · {doc['chunks']} chunks")
            if b.button("×", key=f"del::{doc['filename']}"):
                delete_documents(doc["filename"])
        if st.session_state.documents and st.button("Remove all documents", use_container_width=True):
            delete_documents(None)

        st.markdown("---")
        st.markdown('<div class="section-label">Account</div>', unsafe_allow_html=True)
        user = st.session_state.user or {}
        with st.expander(f"👤 {st.session_state.username}"):
            st.markdown(f"**{user.get('username', st.session_state.username)}**")
            st.caption(user.get("email", ""))
            if user.get("created_at"):
                st.caption(f"Member since {user['created_at'][:10]}")
            st.caption(f"Sign-ins: {user.get('login_count', 0)}")
            if st.button("Sign out", use_container_width=True):
                logout()
        if st.button("Clear all chat history", use_container_width=True):
            clear_all_history()


def upload_files(uploaded_files):
    files = [("files", (f.name, f.getvalue(), "application/pdf")) for f in uploaded_files]
    with st.spinner("Processing your documents…"):
        try:
            r = api("POST", "/upload", files=files, timeout=600)
        except requests.RequestException as exc:
            st.error(f"Upload failed: {exc}"); return
    if r.status_code == 200:
        data = r.json(); refresh_documents()
        flash("success", f"Processed {data['chunks']} new chunks across your documents.")
        st.rerun()
    else:
        st.error(error_detail(r))


def delete_documents(filename):
    try:
        r = api("DELETE", "/documents", params={"filename": filename} if filename else None)
        if r.status_code == 204:
            refresh_documents(); st.rerun()
        else: st.error(error_detail(r))
    except requests.RequestException as exc: st.error(str(exc))


def clear_all_history():
    try:
        r = api("DELETE", "/history")
        if r.status_code == 204:
            st.session_state.conversations = []; st.session_state.messages = []; st.session_state.conversation_id = None; st.rerun()
        else: st.error(error_detail(r))
    except requests.RequestException as exc: st.error(str(exc))


def render_sources(sources):
    if not sources: return
    with st.expander(f"Sources · {len(sources)}"):
        for src in sources:
            st.markdown(f"**{src['source']}** · page {src['page']} · relevance {src['score']:.2f}")
            st.caption(src["snippet"])


def ask(question):
    try:
        r = api("POST", "/chat/", json={"question": question, "mode": MODE_BY_LABEL.get(st.session_state.mode_label, "documents"), "conversation_id": st.session_state.conversation_id}, timeout=120)
    except requests.exceptions.ConnectionError:
        return {"role": "assistant", "content": CONNECTION_HELP, "sources": []}
    except requests.exceptions.Timeout:
        return {"role": "assistant", "content": "⏳ That took too long. Please try again.", "sources": []}
    except requests.RequestException as exc:
        return {"role": "assistant", "content": f"❌ {exc}", "sources": []}
    if r.status_code == 200:
        data = r.json()
        st.session_state.conversation_id = data.get("conversation_id") or st.session_state.conversation_id
        return {"role": "assistant", "content": data["answer"], "sources": data.get("sources", [])}
    return {"role": "assistant", "content": f"❌ {error_detail(r)}", "sources": []}


def ask_image(instruction, image_file):
    try:
        r = api("POST", "/vision/ask", files={"image": (image_file.name, image_file.getvalue(), image_file.type or "application/octet-stream")}, data={"instruction": instruction, "conversation_id": str(st.session_state.conversation_id or "")}, timeout=120)
    except requests.RequestException as exc:
        return {"role": "assistant", "content": f"❌ {exc}", "sources": []}
    if r.status_code == 200:
        data = r.json(); st.session_state.conversation_id = data.get("conversation_id") or st.session_state.conversation_id
        return {"role": "assistant", "content": data["answer"], "sources": []}
    return {"role": "assistant", "content": f"❌ {error_detail(r)}", "sources": []}


def listen_button(text, index):
    key = "audio::" + hashlib.md5(text.encode()).hexdigest()
    if st.button("🔊 Listen", key=f"listen::{index}"):
        try:
            r = api("POST", "/voice/speak", json={"text": text}, timeout=60)
            if r.status_code == 200: st.session_state[key] = r.content
            else: st.error(error_detail(r))
        except requests.RequestException as exc: st.error(str(exc))
    if key in st.session_state: st.audio(st.session_state[key], format="audio/mpeg")


def transcribe(audio_bytes):
    try:
        r = api("POST", "/voice/transcribe", files={"audio": ("question.wav", audio_bytes, "audio/wav")}, timeout=60)
        if r.status_code == 200: return r.json()["text"]
        st.error(error_detail(r))
    except requests.RequestException as exc: st.error(str(exc))
    return None


def make_image(prompt):
    if len(prompt.strip()) < 3: st.warning("Describe the image first."); return
    with st.spinner("Generating image…"):
        try: r = api("POST", "/images/generate", json={"prompt": prompt}, timeout=120)
        except requests.RequestException as exc: st.error(str(exc)); return
    if r.status_code == 200:
        st.session_state.messages.append({"role":"assistant","content":f"Generated image for: *{prompt}*","sources":[],"image":r.content})
        st.rerun()
    else: st.error(error_detail(r))


def extras_sidebar():
    spoken = None; answer_clicked = False
    with st.sidebar:
        st.markdown('<div class="section-label">Answer mode</div>', unsafe_allow_html=True)
        st.radio("Answer from", [DOCS_LABEL, QUESTIONS_LABEL, GENERAL_LABEL], key="mode_label", label_visibility="collapsed")
        if VOICE_IN_CHAT:
            st.caption("🎤 Use the microphone inside the message box for voice input.")
        else:
            audio = st.audio_input("Record a question", label_visibility="collapsed")
            if audio:
                digest = hashlib.md5(audio.getvalue()).hexdigest()
                if digest != st.session_state.get("last_audio"):
                    st.session_state.last_audio = digest; spoken = transcribe(audio.getvalue())
        st.markdown('<div class="section-label">Image tools</div>', unsafe_allow_html=True)
        image_file = st.file_uploader("Screenshot or photo", type=["png","jpg","jpeg","webp"], key="image_upload")
        if image_file:
            st.image(image_file, use_container_width=True)
            answer_clicked = st.button("Answer from this image", use_container_width=True)
        prompt = st.text_input("Generate an image", key="image_prompt", placeholder="Describe an image…")
        if st.button("Generate image", use_container_width=True): make_image(prompt)
    return spoken, image_file, answer_clicked


def chat_page():
    sidebar()
    spoken, image_file, answer_clicked = extras_sidebar()
    current = next((c for c in st.session_state.conversations if c["id"] == st.session_state.conversation_id), None)
    title = current["title"] if current else "New research chat"

    st.markdown(f'<div class="hero"><div class="eyebrow">AI research workspace</div><h1>{title}</h1><p>Ask questions, explore your PDFs, analyse images and keep every research thread organised in one place.</p></div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(f'<div class="stat-card"><div class="stat-value">{len(st.session_state.conversations)}</div><div class="stat-label">Saved conversations</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="stat-card"><div class="stat-value">{len(st.session_state.documents)}</div><div class="stat-label">Your documents</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="stat-card"><div class="stat-value">{len(st.session_state.messages)}</div><div class="stat-label">Messages in this chat</div></div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    if not st.session_state.messages:
        st.info("Start a conversation below. Your chat will automatically be saved and titled from your first question.")

    for i, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("image"): st.image(message["image"])
            render_sources(message.get("sources"))
            if message["role"] == "assistant" and not message.get("image"): listen_button(message["content"], i)

    if image_file:
        st.caption(f"📎 Attached: **{image_file.name}** — your next question will be answered using this image.")
    typed = None
    recorded = None
    if VOICE_IN_CHAT:
        value = st.chat_input("Ask anything…", accept_audio=True)
        if value:
            try: typed = (value["text"] or "").strip() or None
            except (KeyError, TypeError): typed = getattr(value, "text", None)
            audio = None
            try: audio = value["audio"]
            except (KeyError, TypeError): audio = getattr(value, "audio", None)
            if audio is not None: recorded = audio.getvalue()
    else:
        typed = st.chat_input("Ask anything…")
    question = typed
    if recorded:
        heard = transcribe(recorded); question = f"{typed} {heard}".strip() if typed and heard else (heard or typed)
    question = question or spoken

    if question or answer_clicked:
        user_text = question or "Answer the question in the attached image"
        st.session_state.messages.append({"role":"user","content":user_text,"sources":[], **({"image":image_file.getvalue()} if image_file else {})})
        with st.chat_message("user"):
            st.markdown(user_text)
            if image_file: st.image(image_file.getvalue())
        with st.chat_message("assistant"):
            with st.spinner("Researching…"):
                reply = ask_image(question or "", image_file) if image_file else ask(question)
            st.markdown(reply["content"]); render_sources(reply["sources"])
        st.session_state.messages.append(reply)
        refresh_conversations()
        if st.session_state.conversation_id:
            load_messages(st.session_state.conversation_id)
        st.rerun()


if st.session_state.token:
    if not st.session_state.conversations:
        refresh_conversations()
        refresh_documents()
        refresh_user()
    chat_page()
else:
    auth_page()
