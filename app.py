import streamlit as st
from datetime import datetime
import json
import gspread
import pandas as pd
import time

# ==========================================
# 👇 設定エリア
# ==========================================
SPREADSHEET_NAME = "模擬店データベース"

# 🔐 クラスごとのパスワード設定
# 好きな数字や文字に変えてください
CLASS_PASSWORDS = {
    "21HR": "2121",
    "22HR": "2222",
    "23HR": "2323",
    "24HR": "2424",
    "25HR": "2525",
    "26HR": "2626",
    "27HR": "2727",
    "28HR": "2828",
    "実行委員": "admin"
}

# ==========================================
# ⚙️ アプリ初期設定
# ==========================================
st.set_page_config(page_title="文化祭統合システム", layout="wide")

# セッション状態の初期化
if "is_logged_in" not in st.session_state:
    st.session_state["is_logged_in"] = False
if "logged_class" not in st.session_state:
    st.session_state["logged_class"] = None

# --- 共通：指定した名前のタブに接続する関数 ---
def connect_to_tab(tab_name):
    if "service_account_json" not in st.secrets:
        st.error("Secretsの設定がありません")
        return None
    
    key_dict = json.loads(st.secrets["service_account_json"])
    gc = gspread.service_account_from_dict(key_dict)
    
    try:
        wb = gc.open(SPREADSHEET_NAME)
        return wb.worksheet(tab_name)
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"エラー: 「{tab_name}」というタブが見つかりません。")
        return None
    except Exception as e:
        st.error(f"接続エラー: {e}")
        return None

# ==========================================
# 📱 サイドバー（クラス選択）
# ==========================================
st.sidebar.title("🏫 クラスログイン")

class_list = ["21HR", "22HR", "23HR", "24HR", "25HR", "26HR", "27HR", "28HR", "実行委員"]
selected_class = st.sidebar.selectbox("クラスを選んでください", class_list)

# 自動ログアウト処理
if st.session_state["logged_class"] != selected_class:
    st.session_state["is_logged_in"] = False
    st.session_state["logged_class"] = selected_class

st.sidebar.divider()

# ==========================================
# 🔐 ログイン制御
# ==========================================
if not st.session_state["is_logged_in"]:
    st.title(f"🔒 {selected_class} ログイン")
    st.write("このクラスのデータにアクセスするにはパスワードが必要です。")
    
    with st.form("login_form"):
        input_pass = st.text_input("パスワードを入力", type="password")
        login_btn = st.form_submit_button("ログイン")