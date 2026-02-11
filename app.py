import streamlit as st
import sqlite3
import json
import pandas as pd
import bcrypt
from datetime import datetime
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

# --- 1. UI表示用テキスト辞書 ---
UI_TEXT = {
    "Japanese": {
        "title": "🌼パダウと🌸桜",
        "login_tab": "ログイン", "reg_tab": "新規登録",
        "username": "ユーザー名", "password": "パスワード",
        "lang_select": "母国語を選択", "login_btn": "ログイン",
        "reg_btn": "登録する", "logout": "ログアウト",
        "my_page": "マイページ", "active_threads": "🧵 進行中のスレッド",
        "new_thread": "🆕 新規スレッド作成", "thread_name": "スレッド名",
        "target_langs": "翻訳対象言語", "create_btn": "作成して開始",
        "back": "⬅️ 一覧に戻る", "settings": "⚙️ 設定",
        "save": "設定を保存", "input_placeholder": "メッセージを入力...",
        "csv_out": "ログ(CSV)出力"
    },
    "Burmese": {
        "title": "🌼ပိတောက်နှင့်🌸ဆာကူရာ",
        "login_tab": "လော့ဂ်အင်", "reg_tab": "အကောင့်ဖွင့်ရန်",
        "username": "အသုံးပြုသူအမည်", "password": "စကားဝှက်",
        "lang_select": "မိခင်ဘာသာစကားကို ရွေးချယ်ပါ", "login_btn": "လော့ဂ်အင်ဝင်ရန်",
        "reg_btn": "စာရင်းသွင်းရန်", "logout": "ထွက်ရန်",
        "my_page": "ကျွန်ုပ်၏စာမျက်နှာ", "active_threads": "🧵 လက်ရှိစကားဝိုင်းများ",
        "new_thread": "🆕 စကားဝိုင်းအသစ်ပြုလုပ်ရန်", "thread_name": "ခေါင်းစဉ်",
        "target_langs": "ဘာသာပြန်မည့် ဘာသာစကားများ", "create_btn": "စတင်ရန်",
        "back": "⬅️ စာရင်းသို့ပြန်သွားရန်", "settings": "⚙️ ဆက်တင်များ",
        "save": "ဆက်တင်များကို သိမ်းဆည်းရန်", "input_placeholder": "စာရိုက်ရန်...",
        "csv_out": "CSV ထုတ်ယူရန်"
    }
}

def T(key):
    lang = st.session_state.get("ui_lang", "Japanese")
    return UI_TEXT[lang].get(key, key)

# --- 2. セッション状態の初期化 ---
if "ui_lang" not in st.session_state:
    st.session_state.ui_lang = "Japanese"
if "user" not in st.session_state:
    st.session_state.user = None
if "page" not in st.session_state:
    st.session_state.page = "list"
if "current_thread" not in st.session_state:
    st.session_state.current_thread = None

st.set_page_config(page_title="Padauk & Sakura 🌼🌸", page_icon="🌸")

# --- 3. データベース & LLM 設定 ---
DB_NAME = 'padauk_sakura.sqlite'

def get_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password BLOB, default_lang TEXT)')
        conn.execute('CREATE TABLE IF NOT EXISTS threads (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, languages TEXT, owner TEXT)')
        conn.execute('CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, thread_id INTEGER, username TEXT, original TEXT, translations TEXT, timestamp TEXT)')
        conn.commit()

init_db()

llm = ChatOpenAI(
    model_name="translategemma:4b",
    openai_api_base="http://localhost:11434/v1",
    openai_api_key="ollama",
    temperature=0.0
)

def translate_text(text, target_lang):
    prompt = ChatPromptTemplate.from_messages([
        ("system", f"You are a professional translator. Translate into {target_lang}. Output ONLY the translation without any explanation."),
        ("user", "{text}")
    ])
    try:
        return (prompt | llm).invoke({"text": text}).content.strip()
    except Exception:
        return "(Translation Error)"

# --- 4. ページ定義 ---

def login_page():
    st.title(T("title"))
    st.divider()
    
    tab1, tab2 = st.tabs([T("login_tab"), T("reg_tab")])
    with tab1:
        u = st.text_input(T("username"), key="l_u")
        p = st.text_input(T("password"), type="password", key="l_p")
        if st.button(T("login_btn"), use_container_width=True, type="primary"):
            with get_db() as conn:
                res = conn.execute("SELECT * FROM users WHERE username=?", (u,)).fetchone()
                if res and bcrypt.checkpw(p.encode('utf-8'), res['password']):
                    st.session_state.user = {"name": u, "lang": res['default_lang']}
                    st.session_state.ui_lang = res['default_lang']
                    st.rerun()
                else: st.error("Login Failed.")
    
    with tab2:
        nu = st.text_input(T("username"), key="r_u")
        np = st.text_input(T("password"), type="password", key="r_p")
        nl = st.selectbox(T("lang_select"), ["Japanese", "Burmese"], key="r_l")
        if st.button(T("reg_btn"), use_container_width=True):
            try:
                hashed = bcrypt.hashpw(np.encode('utf-8'), bcrypt.gensalt())
                with get_db() as conn:
                    conn.execute("INSERT INTO users VALUES (?, ?, ?)", (nu, hashed, nl))
                    conn.commit()
                st.success("Registered! Please login.")
            except: st.error("User might already exist.")

@st.fragment(run_every=5)
def message_area(thread_id, user_lang):
    with get_db() as conn:
        msgs = conn.execute("SELECT * FROM messages WHERE thread_id=? ORDER BY id ASC", (thread_id,)).fetchall()
    for m in msgs:
        is_me = m['username'] == st.session_state.user['name']
        with st.chat_message("user" if is_me else "assistant"):
            st.caption(f"{m['username']} | {m['timestamp']}")
            st.markdown(f"**{m['original']}**")
            translations = json.loads(m['translations'])
            for lang, text in translations.items():
                flag = "🇲🇲" if lang == "Burmese" else "🇯🇵"
                if lang == user_lang: 
                    st.info(f"{flag} **{lang}:** {text}")
                else: 
                    st.markdown(f"&nbsp;&nbsp;&nbsp;{flag} *{lang}:* {text}")

def thread_list_page():
    st.header(f"{T('my_page')} : {st.session_state.user['name']}")
    with st.sidebar:
        if st.button(T("logout"), use_container_width=True):
            st.session_state.user = None
            st.rerun()
    
    with get_db() as conn:
        threads = conn.execute("SELECT * FROM threads ORDER BY id DESC").fetchall()
    
    for t in threads:
        col1, col2 = st.columns([8, 2])
        if col1.button(f"📄 {t['title']}", key=f"t_{t['id']}", use_container_width=True):
            st.session_state.current_thread = t['id']
            st.session_state.page = "chat"
            st.rerun()
        if col2.button("🗑️", key=f"del_{t['id']}"):
            with get_db() as conn:
                conn.execute("DELETE FROM threads WHERE id=?", (t['id'],))
                conn.execute("DELETE FROM messages WHERE thread_id=?", (t['id'],))
                conn.commit()
            st.rerun()
            
    st.divider()
    st.subheader(T("new_thread"))
    nt = st.text_input(T("thread_name"))
    tl = st.multiselect(T("target_langs"), ["Japanese", "Burmese"], default=["Japanese", "Burmese"])
    if st.button(T("create_btn")):
        if nt and tl:
            with get_db() as conn:
                conn.execute("INSERT INTO threads (title, languages, owner) VALUES (?, ?, ?)", 
                             (nt, ",".join(tl), st.session_state.user['name']))
                conn.commit()
            st.rerun()

def chat_page():
    with get_db() as conn:
        thread = conn.execute("SELECT * FROM threads WHERE id=?", (st.session_state.current_thread,)).fetchone()
    if not thread:
        st.session_state.page = "list"
        st.rerun()
    
    st.title(f"🧵 {thread['title']}")
    with st.sidebar:
        if st.button(T("back"), use_container_width=True):
            st.session_state.page = "list"
            st.rerun()
        st.divider()
        with get_db() as conn:
            df = pd.read_sql("SELECT username, original, translations, timestamp FROM messages WHERE thread_id=?", conn, params=(st.session_state.current_thread,))
        st.download_button(T("csv_out"), df.to_csv(index=False).encode('utf-8_sig'), f"{thread['title']}.csv")

    message_area(thread['id'], st.session_state.user['lang'])

    if prompt := st.chat_input(T("input_placeholder")):
        target_langs = thread['languages'].split(",")
        translations = {l: translate_text(prompt, l) for l in target_langs if l != st.session_state.user['lang']}
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        with get_db() as conn:
            conn.execute("INSERT INTO messages (thread_id, username, original, translations, timestamp) VALUES (?, ?, ?, ?, ?)", 
                         (thread['id'], st.session_state.user['name'], prompt, json.dumps(translations, ensure_ascii=False), now))
            conn.commit()
        st.rerun()

# --- 5. メイン実行 ---
if st.session_state.user is None:
    login_page()
else:
    if st.session_state.page == "list":
        thread_list_page()
    elif st.session_state.page == "chat":
        chat_page()