import streamlit as st
from datetime import datetime
import json
import gspread
import time
from collections import Counter

# ==========================================
# ⚙️ 設定 & CSS
# ==========================================
SPREADSHEET_NAME = "模擬店データベース"
CLASS_PASSWORDS = {f"{i}HR": str(i)*2 for i in range(21, 29)}

CUSTOM_CSS = """
    <style>
    footer {visibility: hidden;}
    
    /* 商品ボタン（標準） */
    div.stButton > button[kind="secondary"] {
        height: 85px !important; width: 100% !important;
        display: flex !important; flex-direction: column !important;
        justify-content: center !important; align-items: center !important;
        white-space: pre-wrap !important; line-height: 1.1 !important;
        padding: 5px !important; font-weight: bold !important; 
        font-size: 14px !important; border-radius: 12px !important;
        border-left: 6px solid #ccc !important; /* 左側に色を付ける */
        transition: transform 0.1s;
    }
    div.stButton > button[kind="secondary"]:active { transform: scale(0.95); }

    /* A案: 商品の色分け（奇数・偶数で左側の色を変える） */
    div[data-testid="column"]:nth-child(odd) div.stButton > button[kind="secondary"] { border-left-color: #4b9ced !important; }
    div[data-testid="column"]:nth-child(even) div.stButton > button[kind="secondary"] { border-left-color: #7d8ad4 !important; }

    /* B案: 在庫アラート（残りわずか 5個以下）のスタイル定義 */
    .low-stock-btn {
        color: #ff9800 !important; /* オレンジ文字 */
        border: 2px solid #ff9800 !important;
        background-color: rgba(255, 152, 0, 0.05) !important;
    }

    /* 重要ボタン（会計など） */
    div.stButton > button[kind="primary"] {
        min-height: 65px !important; width: 100% !important;
        font-size: 18px !important; font-weight: bold !important;
        border-radius: 12px !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
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
    
    [data-testid="column"] { min-width: 0 !important; flex: 1 1 auto !important; }
    button:disabled { opacity: 0.3 !important; cursor: not-allowed !important; filter: grayscale(1); }
    .block-container { padding-top: 3.5rem !important; padding-bottom: 5rem !important; }
    </style>
"""

st.set_page_config(page_title="文化祭レジPro", layout="wide", initial_sidebar_state="auto")
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

if "is_logged_in" not in st.session_state:
    st.session_state.update({
        "is_logged_in": False, "logged_class": None, "cart": [], 
        "received_amount": 0, "flash_msg": None, "flash_type": "success",
        "del_confirm_idx": None, "show_effect": False # C案演出用
    })

# ==========================================
# 🚀 最適化バックエンド
# ==========================================
@st.cache_resource
def get_gc():
    if "service_account_json" not in st.secrets: return None
    return gspread.service_account_from_dict(json.loads(st.secrets["service_account_json"]))

@st.cache_resource
def get_worksheet(tab_name):
    gc = get_gc()
    return gc.open(SPREADSHEET_NAME).worksheet(tab_name) if gc else None

@st.cache_data(ttl=60) 
def get_raw_data(tab_name):
    ws = get_worksheet(tab_name)
    return ws.get_all_values() if ws else []

def execute_db_action(action_func, msg="完了", effect=False):
    try:
        with st.spinner("送信中..."):
            action_func()
            get_raw_data.clear()
            st.session_state["flash_msg"] = f"✅ {msg}"
            if effect: st.session_state["show_effect"] = True # 演出フラグ
            st.rerun()
    except Exception as e:
        st.error(f"エラー: {e}")

# ==========================================
# 🏫 認証
# ==========================================
if not st.session_state["is_logged_in"]:
    st.title("🏫 文化祭レジPro")
    selected_class = st.selectbox("クラス選択", list(CLASS_PASSWORDS.keys()))
    with st.form("login"):
        pw = st.text_input("パスワード", type="password")
        if st.form_submit_button("ログイン", type="primary", use_container_width=True):
            if pw.strip() == CLASS_PASSWORDS.get(selected_class):
                st.session_state.update({"is_logged_in": True, "logged_class": selected_class})
                st.rerun()
            else: st.error("パスワードが違います")
    st.stop()

selected_class = st.session_state["logged_class"]

# フラッシュメッセージ & C案演出
if st.session_state["flash_msg"]:
    st.success(st.session_state["flash_msg"])
    if st.session_state["show_effect"]:
        st.snow() # 会計完了の演出
        st.session_state["show_effect"] = False
    st.session_state["flash_msg"] = None

# --- サイドバー ---
st.sidebar.title(f"🏫 {selected_class}")
mode = st.sidebar.selectbox("📂 モード", ["🎪 当日運営", "🛠 準備・前日"])
st.sidebar.divider()
if mode == "🛠 準備・前日":
    menu = st.sidebar.radio("メニュー", ["🍔 登録", "💸 経費", "✅ ToDo", "⚙️ 予算"])
else:
    menu = st.sidebar.radio("メニュー", ["💰 レジ", "📦 在庫"])
if st.sidebar.button("ログアウト", use_container_width=True):
    st.session_state.update({"is_logged_in": False, "cart": []}); st.rerun()

# --- 📊 予算バー ---
try:
    budget = 30000
    for r in get_raw_data("BUDGET"):
        if len(r) >= 2 and r[0] == selected_class: budget = int(r[1]); break
    class_rows = get_raw_data(selected_class)
    expense = sum(int(str(r[4]).replace(',', '')) for r in class_rows[1:] 
                  if len(r) > 4 and "経費" in str(r[1]) and str(r[4]).replace(',', '').isdigit())
    rem = budget - expense
    bar_color = "#ff4b4b" if rem < 0 else "#00cc96"
    msg = f"🚨 **予算超過: {abs(rem):,}円**" if rem < 0 else f"📊 **残金: {rem:,}円**"
    percent = min(int((expense / budget) * 100), 100) if budget > 0 else 0
    st.markdown(f"<div style='padding-top:5px;font-size:16px;'>{msg} (予算:{budget:,}円)</div>", unsafe_allow_html=True)
    st.markdown(f"<div style='background:#f0f2f6;border-radius:10px;height:12px;width:100%;margin-bottom:20px;'><div style='background:{bar_color};width:{percent}%;height:100%;border-radius:10px;'></div></div>", unsafe_allow_html=True)
except: pass
st.divider()

# ==========================================
# 💰 レジ（POS）
# ==========================================
if menu == "💰 レジ":
    st.subheader(f"💰 {selected_class} レジ")

    @st.fragment
    def render_pos():
        c1, c2 = st.columns([1.5, 1])
        my_menu = [r for r in get_raw_data("MENU")[1:] if r[0] == selected_class]
        cart_counts = Counter([x['n'] for x in st.session_state["cart"]])

        with c1: 
            if not my_menu: st.info("メニュー未登録")
            cols = st.columns(2)
            for i, item in enumerate(my_menu):
                n, p = item[1], int(item[2])
                stock = int(item[4]) if len(item) > 4 and item[4].isdigit() else 0
                status = item[3] if len(item) > 3 else "販売中"
                rem_stock = max(0, stock - cart_counts[n])
                is_disabled = (status == "完売" or stock <= 0 or rem_stock == 0)
                
                # B案: 在庫アラートの表示ロジック
                if status == "完売" or stock <= 0: label = f"🚫\n{n}\n(完売)"
                elif rem_stock == 0: label = f"🚫\n{n}\n(上限)"
                elif rem_stock <= 5: label = f"⚠️ 残り{rem_stock}\n{n}\n¥{p}" # 警告表示
                else: label = f"{n}\n¥{p}\n(残{stock})"

                # 在庫僅少（5個以下）の時、CSSクラスを動的に切り替える（疑似実装）
                # Streamlitのbutton自体にclass指定はできないため、HTMLインジェクションか
                # キー名を工夫してCSSで拾う手法があるが、今回はシンプルに「文字」で警告
                if cols[i % 2].button(label, key=f"p_{i}", use_container_width=True, disabled=is_disabled):
                    st.session_state["cart"].append({"n": n, "p": p}); st.rerun()

        with c2: 
            total = sum(x['p'] for x in st.session_state["cart"])
            with st.expander("🛒 カート", expanded=True):
                if not st.session_state["cart"]: st.write("(空)")
                else:
                    for i, item in enumerate(st.session_state["cart"]):
                        ct, cb = st.columns([3, 1])
                        ct.write(f"・{item['n']}")
                        if cb.button("削", key=f"del_{i}", type="primary"):
                            st.session_state["cart"].pop(i); st.rerun()
            
            st.metric("合計", f"¥{total:,}")
            if total > 0:
                # 預かり金
                val = st.number_input("預かり金", value=st.session_state["received_amount"], step=10, label_visibility="collapsed")
                if val != st.session_state["received_amount"]: st.session_state["received_amount"] = val; st.rerun()
                
                bc = st.columns(3)
                for i, amt in enumerate([1000, 500, 100, 50, 10, 0]):
                    if bc[i%3].button(f"+{amt}" if amt else "C", use_container_width=True):
                        st.session_state["received_amount"] = 0 if amt == 0 else st.session_state["received_amount"] + amt
                        st.rerun()

                change = st.session_state["received_amount"] - total
                if st.session_state["received_amount"] > 0:
                    if change >= 0: st.success(f"お釣り: ¥{change:,}")
                    else: st.error(f"不足: ¥{abs(change):,}")

                if st.button("会計確定", type="primary", use_container_width=True):
                    if st.session_state["received_amount"] < total:
                        st.error("金額が足りません")
                    else:
                        cart_names = [x['n'] for x in st.session_state["cart"]]
                        item_counts = Counter(cart_names)
                        def checkout():
                            ws_sales = get_worksheet(selected_class)
                            ws_menu = get_worksheet("MENU")
                            ws_sales.append_row([datetime.now().strftime("%m/%d %H:%M"), "🔵 売上", "レジ", ",".join(cart_names), total])
                            menu_data = ws_menu.get_all_values()
                            for idx, row in enumerate(menu_data):
                                if idx > 0 and row[0] == selected_class and row[1] in item_counts:
                                    cur = int(row[4]) if len(row) > 4 and row[4].isdigit() else 0
                                    new_s = max(0, cur - item_counts[row[1]])
                                    ws_menu.update_cell(idx + 1, 5, new_s)
                                    if new_s == 0: ws_menu.update_cell(idx + 1, 4, "完売")
                        st.session_state["cart"] = []; st.session_state["received_amount"] = 0
                        execute_db_action(checkout, "売上記録完了！", effect=True)
            
            if st.button("全クリア", use_container_width=True):
                st.session_state["cart"] = []; st.session_state["received_amount"] = 0; st.rerun()
    render_pos()

# ==========================================
# 📦 在庫管理
# ==========================================
elif menu == "📦 在庫":
    st.subheader("📦 在庫管理")
    my_menu = [{"row": r, "idx": i+1} for i, r in enumerate(get_raw_data("MENU")) if i > 0 and r[0] == selected_class]
    if my_menu:
        for item in my_menu:
            row, idx = item["row"], item["idx"]
            stock = int(row[4]) if len(row) > 4 and row[4].isdigit() else 0
            c1, c2, c3 = st.columns([2, 1, 1])
            c1.write(f"**{row[1]}**")
            new_s = c2.number_input(f"在庫({row[1]})", value=stock, min_value=0, step=1, label_visibility="collapsed", key=f"inv_{idx}")
            if c3.button("更新", key=f"upd_{idx}"):
                execute_db_action(lambda: [get_worksheet("MENU").update_cell(idx, 5, new_s), get_worksheet("MENU").update_cell(idx, 4, "完売" if new_s == 0 else "販売中")], f"{row[1]}を{new_s}個に更新")
    else: st.info("メニューなし")

# ==========================================
# 💸 経費 / ✅ ToDo / 🍔 登録 / ⚙️ 予算
# ==========================================
elif menu == "💸 経費":
    st.subheader(f"💸 {selected_class} 経費")
    with st.form("exp"):
        d, p, i, a = st.date_input("日付"), st.text_input("担当者"), st.text_input("品名"), st.number_input("金額", min_value=0, step=1)
        if st.form_submit_button("登録", use_container_width=True):
            if not p or not i or a <= 0: st.error("全項目入力してください")
            else: execute_db_action(lambda: get_worksheet(selected_class).append_row([d.strftime("%Y/%m/%d"), "🔴 経費", p, i, a]), "経費登録完了")

elif menu == "✅ ToDo":
    st.subheader(f"✅ {selected_class} ToDo")
    with st.form("todo"):
        t, p = st.text_input("内容"), st.text_input("担当者")
        if st.form_submit_button("追加", use_container_width=True):
            if t: execute_db_action(lambda: get_worksheet("TODO").append_row([selected_class, datetime.now().strftime("%m/%d"), t, p, "未完了"]), "タスク追加")
    st.divider()
    @st.fragment
    def render_todo():
        raw = get_raw_data("TODO")
        active = [{"r": r, "idx": i+1} for i, r in enumerate(raw) if i > 0 and r[0] == selected_class and "未完了" in r[4]]
        if active:
            upds = []
            for item in active:
                if st.checkbox(f"{item['r'][2]} ({item['r'][3]})", key=f"chk_{item['idx']}"): upds.append(item['idx'])
            if upds and st.button("完了にする", type="primary", use_container_width=True):
                execute_db_action(lambda: [get_worksheet("TODO").update_cell(rid, 5, "完了") for rid in upds], "タスク完了")
        else: st.info("タスクなし")
    render_todo()

elif menu == "🍔 登録":
    st.subheader("🍔 メニュー登録")
    with st.form("add_m"):
        n, p, s = st.text_input("商品名"), st.number_input("単価", min_value=0, step=10), st.number_input("初期在庫", min_value=1, value=50)
        if st.form_submit_button("追加", use_container_width=True):
            if n and p > 0: execute_db_action(lambda: get_worksheet("MENU").append_row([selected_class, n, p, "販売中", s]), f"{n}を追加")
            else: st.error("正しく入力してください")
    st.divider()
    with st.expander("📋 登録済みメニュー", expanded=True):
        my_menu = [{"d": r, "idx": i+1} for i, r in enumerate(get_raw_data("MENU")) if i > 0 and r[0] == selected_class]
        for item in my_menu:
            row, idx = item["d"], item["idx"]
            c1, c2 = st.columns([3, 1])
            c1.write(f"・**{row[1]}** (¥{row[2]}) / 在庫: {row[4]}")
            if st.session_state["del_confirm_idx"] == idx:
                c2.caption("本当に？")
                cy, cn = c2.columns(2)
                if cy.button("はい", key=f"y_{idx}", type="primary"):
                    execute_db_action(lambda: get_worksheet("MENU").delete_rows(idx), "削除完了"); st.session_state["del_confirm_idx"] = None
                if cn.button("いいえ", key=f"n_{idx}", type="secondary"): st.session_state["del_confirm_idx"] = None; st.rerun()
            else:
                if c2.button("削除", key=f"d_{idx}", type="primary"): st.session_state["del_confirm_idx"] = idx; st.rerun()

elif menu == "⚙️ 予算":
    st.subheader("⚙️ 予算設定")
    curr = 30000
    for r in get_raw_data("BUDGET"):
        if len(r) >= 2 and r[0] == selected_class: curr = int(r[1]); break
    with st.form("bud"):
        nb = st.number_input("新予算", value=curr, step=1000)
        if st.form_submit_button("更新", use_container_width=True):
            ws = get_worksheet("BUDGET")
            data = ws.get_all_values()
            row_idx = next((i+1 for i, r in enumerate(data) if r[0] == selected_class), None)
            execute_db_action(lambda: ws.update_cell(row_idx, 2, nb) if row_idx else ws.append_row([selected_class, nb]), "予算更新")
