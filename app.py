import streamlit as st
from datetime import datetime
import json
import gspread
import time
from collections import Counter
import pandas as pd # データ編集用

# ==========================================
# ⚙️ 定数 & CSS設定
# ==========================================
SPREADSHEET_NAME = "模擬店データベース"
CLASS_PASSWORDS = {f"{i}HR": str(i)*2 for i in range(21, 29)}

CUSTOM_CSS = """
    <style>
    footer {visibility: hidden;}
    
    /* === PC・共通設定 === */
    
    /* 商品ボタン */
    div.stButton > button[kind="secondary"] {
        height: 85px !important; width: 100% !important;
        display: flex !important; flex-direction: column !important;
        justify-content: center !important; align-items: center !important;
        white-space: pre-wrap !important; line-height: 1.1 !important;
        padding: 5px !important; font-weight: bold !important; 
        font-size: 14px !important; border-radius: 12px !important;
        border-left: 6px solid #ccc !important;
        transition: transform 0.1s;
    }
    div.stButton > button[kind="secondary"]:active { transform: scale(0.95); }
    div[data-testid="column"]:nth-child(odd) div.stButton > button[kind="secondary"] { border-left-color: #4b9ced !important; }
    div[data-testid="column"]:nth-child(even) div.stButton > button[kind="secondary"] { border-left-color: #7d8ad4 !important; }

    /* 重要ボタン */
    div.stButton > button[kind="primary"] {
        min-height: 65px !important; width: 100% !important;
        font-size: 18px !important; font-weight: bold !important;
        border-radius: 12px !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* 電卓ボタン */
    .calc-btn > button {
        height: 60px !important; font-size: 20px !important; font-weight: bold !important; margin: 0px !important;
    }

    /* リスト内ボタン */
    div[data-testid="stExpander"] button[kind="primary"] {
        height: 40px !important; min-height: 40px !important; width: auto !important;
        background-color: #ff4b4b !important; color: white !important; border-radius: 6px !important;
    }
    div[data-testid="stExpander"] button[kind="secondary"] {
        height: 40px !important; min-height: 40px !important; width: auto !important;
        color: #00cc96 !important; border: 1px solid #00cc96 !important; border-radius: 6px !important;
    }
    
    .block-container { padding-top: 3.5rem !important; padding-bottom: 5rem !important; }
    .sales-card {
        background: rgba(75, 156, 237, 0.1); padding: 15px;
        border-radius: 10px; border: 1px solid #4b9ced; margin-bottom: 20px;
    }

    /* =========================================
       📱 スマホ専用レイアウト修正 (gap検知版)
       ========================================= */
    @media (max-width: 640px) {
        
        /* 1. gap="small" (1rem/16px) が指定されているブロックを狙い撃ちし、強制的に横並びにする */
        div[data-testid="stHorizontalBlock"][style*="gap: 1rem"],
        div[data-testid="stHorizontalBlock"][style*="gap: 16px"],
        div[data-testid="stHorizontalBlock"][style*="gap: small"] {
            flex-direction: row !important;
            flex-wrap: wrap !important;
        }

        /* 2. その中のカラムの幅制限を解除する */
        div[data-testid="stHorizontalBlock"][style*="gap: 1rem"] > div[data-testid="column"],
        div[data-testid="stHorizontalBlock"][style*="gap: 16px"] > div[data-testid="column"],
        div[data-testid="stHorizontalBlock"][style*="gap: small"] > div[data-testid="column"] {
            width: auto !important;
            flex: 1 1 auto !important;
            min-width: 0 !important;
        }
        
        /* 電卓ボタンのサイズ微調整 */
        .calc-btn > button {
            height: 55px !important;
            padding: 0 !important;
        }
    }
    </style>
"""

st.set_page_config(page_title="文化祭レジPro", layout="wide", initial_sidebar_state="auto")
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# セッション初期化
if "is_logged_in" not in st.session_state:
    st.session_state.update({
        "is_logged_in": False, "logged_class": None, "cart": [], 
        "received_amount": 0, "flash_msg": None, "flash_type": "success",
        "del_confirm_idx": None, "show_effect": False,
        "calc_input": "0"
    })

# ==========================================
# 🚀 バックエンド
# ==========================================
@st.cache_resource
def get_gc():
    try:
        if "service_account_json" not in st.secrets: return None
        return gspread.service_account_from_dict(json.loads(st.secrets["service_account_json"]))
    except Exception as e:
        st.error(f"認証エラー: {e}")
        return None

@st.cache_resource
def get_worksheet(tab_name):
    gc = get_gc()
    try:
        return gc.open(SPREADSHEET_NAME).worksheet(tab_name) if gc else None
    except Exception:
        return None

@st.cache_data(ttl=60) 
def get_raw_data(tab_name):
    try:
        ws = get_worksheet(tab_name)
        return ws.get_all_values() if ws else []
    except Exception:
        return []

def execute_db_action(action_func, msg="完了", effect=False):
    """DB操作を実行し、エラー時はアラートを出す"""
    try:
        with st.spinner("通信中..."):
            action_func()
            get_raw_data.clear() # キャッシュクリア
            st.session_state["flash_msg"] = f"✅ {msg}"
            if effect: st.session_state["show_effect"] = True
            st.session_state["calc_input"] = "0"
            st.rerun()
    except gspread.exceptions.APIError:
        st.error("📡 通信エラー：ネットワークが不安定です。もう一度押してください。")
    except Exception as e:
        st.error(f"⚠️ エラーが発生しました: {e}")

def calc_budget(cls_name):
    try:
        budget_data = get_raw_data("BUDGET")
        budget = 30000
        for r in budget_data:
            if len(r) >= 2 and r[0] == cls_name:
                budget = int(r[1]); break
        class_data = get_raw_data(cls_name)
        expense = sum(int(str(r[4]).replace(',', '')) for r in class_data[1:] 
                      if len(r) > 4 and "経費" in str(r[1]) and str(r[4]).replace(',', '').isdigit())
        return budget, expense, budget - expense
    except:
        return 0, 0, 0

def calc_sales_stats(cls_name):
    try:
        sales_data = get_raw_data(cls_name)
        all_sold = []
        revenue = 0
        for r in sales_data[1:]:
            if len(r) > 4 and "売上" in r[1]:
                all_sold.extend(r[3].split(","))
                revenue += int(str(r[4]).replace(',', ''))
        return revenue, Counter(all_sold)
    except:
        return 0, Counter()

# ==========================================
# 🏫 認証 & 共通UI
# ==========================================
if not st.session_state["is_logged_in"]:
    st.title("🏫 文化祭レジPro")
    sel_cls = st.selectbox("クラス選択", list(CLASS_PASSWORDS.keys()))
    pw = st.text_input("パスワード", type="password")
    if st.button("ログイン", type="primary", use_container_width=True):
        if pw.strip() == CLASS_PASSWORDS.get(sel_cls):
            st.session_state.update({"is_logged_in": True, "logged_class": sel_cls})
            st.rerun()
        else: st.error("パスワードが違います")
    st.stop()

selected_class = st.session_state["logged_class"]

if st.session_state["flash_msg"]:
    st.success(st.session_state["flash_msg"])
    if st.session_state["show_effect"]:
        st.balloons()
        st.session_state["show_effect"] = False
    st.session_state["flash_msg"] = None

st.sidebar.title(f"🏫 {selected_class}")
mode = st.sidebar.selectbox("📂 モード", ["🎪 当日運営", "🛠 準備・前日"])
st.sidebar.divider()
if mode == "🛠 準備・前日":
    menu = st.sidebar.radio("メニュー", ["🍔 登録", "💸 経費", "✅ ToDo", "⚙️ 予算"])
else:
    menu = st.sidebar.radio("メニュー", ["💰 レジ", "📦 在庫・売上"])
if st.sidebar.button("ログアウト", use_container_width=True):
    st.session_state.update({"is_logged_in": False, "cart": []}); st.rerun()

# 予算バー
budget, expense, rem = calc_budget(selected_class)
if budget > 0:
    bar_color = "#ff4b4b" if rem < 0 else "#00cc96"
    msg = f"🚨 **予算超過: {abs(rem):,}円**" if rem < 0 else f"📊 **残金: {rem:,}円**"
    pct = min(int((expense / budget) * 100), 100)
    st.markdown(f"<div style='padding-top:5px;font-size:16px;'>{msg} (予算:{budget:,}円)</div>", unsafe_allow_html=True)
    st.markdown(f"<div style='background:#f0f2f6;border-radius:10px;height:12px;width:100%;margin-bottom:20px;'><div style='background:{bar_color};width:{pct}%;height:100%;border-radius:10px;'></div></div>", unsafe_allow_html=True)
st.divider()

# ==========================================
# 💰 レジ (POS)
# ==========================================
if menu == "💰 レジ":
    st.subheader(f"💰 {selected_class} レジ")

    @st.fragment
    def render_pos():
        # メインレイアウト（PC用）
        c1, c2 = st.columns([1.5, 1])
        
        menu_data = [r for r in get_raw_data("MENU")[1:] if r[0] == selected_class]
        cart_counts = Counter([x['n'] for x in st.session_state["cart"]])

        # --- 商品選択エリア ---
        with c1: 
            if not menu_data: 
                st.info("メニュー未登録")
            else:
                # ★修正: gap="small" を指定して、CSSでこれを検知させる
                chunk_size = 2
                for i in range(0, len(menu_data), chunk_size):
                    row_items = menu_data[i:i+chunk_size]
                    cols = st.columns(chunk_size, gap="small") # CSSフック用の gap="small"
                    
                    for j, item in enumerate(row_items):
                        n, p = item[1], int(item[2])
                        stock = int(item[4]) if len(item) > 4 and item[4].isdigit() else 0
                        status = item[3] if len(item) > 3 else "販売中"
                        rem_stock = max(0, stock - cart_counts[n])
                        is_disabled = (status == "完売" or stock <= 0 or rem_stock == 0)
                        
                        if status == "完売" or stock <= 0: label = f"🚫\n{n}\n(完売)"
                        elif rem_stock == 0: label = f"🚫\n{n}\n(上限)"
                        elif rem_stock <= 5: label = f"⚠️ 残り{rem_stock}\n{n}\n¥{p}"
                        else: label = f"{n}\n¥{p}\n(残{stock})"

                        if cols[j].button(label, key=f"pos_{i+j}", use_container_width=True, disabled=is_disabled):
