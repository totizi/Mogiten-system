import streamlit as st
from datetime import datetime
import json
import gspread
import time
import pandas as pd

# ==========================================
# ⚙️ 設定エリア
# ==========================================
SPREADSHEET_NAME = "模擬店データベース"

# クラス設定 (21HR~28HR)
CLASS_PASSWORDS = {f"{i}HR": str(i)*2 for i in range(21, 29)}

# ページ設定 & CSS
st.set_page_config(page_title="文化祭レジ", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden;}
    
    /* ボタンデザイン */
    div.stButton > button {
        word-break: keep-all !important; 
        overflow-wrap: break-word !important;
        height: auto !important;
        min-height: 60px !important;
        padding: 8px 12px !important;
        font-weight: bold !important;
        font-size: 18px !important;
        border-radius: 12px !important;
    }
    
    /* スピナーの色 */
    .stSpinner > div { border-top-color: #ff4b4b !important; }
    
    /* 売り切れボタン用 */
    button:disabled {
        background-color: #e0e0e0 !important;
        color: #a0a0a0 !important;
        border-color: #d0d0d0 !important;
        cursor: not-allowed !important;
        opacity: 0.8 !important;
    }
    
    .block-container { padding-top: 1rem !important; padding-bottom: 3rem !important; }
    </style>
    """, unsafe_allow_html=True)

# セッション初期化
if "is_logged_in" not in st.session_state:
    st.session_state.update({
        "is_logged_in": False, 
        "logged_class": None, 
        "cart": [], 
        "received_amount": 0,
        "flash_msg": None,
        "flash_type": "success"
    })

# ==========================================
# 🛡️ バックエンド処理
# ==========================================
@st.cache_resource(ttl=3600)
def get_spreadsheet():
    """DB接続を維持"""
    if "service_account_json" not in st.secrets:
        st.error("Secrets未設定"); return None
    try:
        creds = json.loads(st.secrets["service_account_json"])
        gc = gspread.service_account_from_dict(creds)
        return gc.open(SPREADSHEET_NAME)
    except Exception as e:
        st.error(f"DB接続エラー: {e}"); return None

@st.cache_data(ttl=180)
def get_raw_data(tab_name):
    """データ取得"""
    sh = get_spreadsheet()
    if not sh: return []
    try: return sh.worksheet(tab_name).get_all_values()
    except: return []

def handle_db_action(action_func, success_msg="完了しました", wait_time=0.1):
    """書き込み処理・通知・リロードを一括管理"""
    max_retries = 3
    
    with st.spinner("処理中..."):
        for i in range(max_retries):
            try:
                action_func()
                get_raw_data.clear() # キャッシュクリア
                st.session_state["flash_msg"] = f"✅ {success_msg}"
                st.session_state["flash_type"] = "success"
                time.sleep(wait_time)
                st.rerun()
                return
            except Exception as e:
                if i == max_retries - 1: st.error(f"通信エラー: {e}")
                time.sleep(1.5 ** i)

# ==========================================
# 🏫 ログイン画面
# ==========================================
st.sidebar.title("🏫 クラス")
selected_class = st.sidebar.selectbox("選択", list(CLASS_PASSWORDS.keys()), label_visibility="collapsed")

if st.session_state["logged_class"] != selected_class:
    st.session_state.update({"is_logged_in": False, "logged_class": selected_class, "cart": [], "received_amount": 0, "flash_msg": None})
    st.rerun()

st.sidebar.divider()

if not st.session_state["is_logged_in"]:
    st.title(f"🔒 {selected_class}")
    with st.form("login"):
        pw = st.text_input("パスワード", type="password")
        if st.form_submit_button("ログイン", type="primary", use_container_width=True):
            if pw.strip() == CLASS_PASSWORDS.get(selected_class):
                st.session_state["is_logged_in"] = True; st.rerun()
            else: st.error("パスワードが違います")
    st.stop()

# ==========================================
# 🎉 メイン画面
# ==========================================
# フラッシュメッセージ
if st.session_state["flash_msg"]:
    if st.session_state["flash_type"] == "success":
        st.success(st.session_state["flash_msg"])
    else:
        st.error(st.session_state["flash_msg"])
    st.session_state["flash_msg"] = None

# サイドバー
if st.sidebar.button("ログアウト", use_container_width=True):
    st.session_state.update({"is_logged_in": False, "cart": [], "received_amount": 0})
    st.rerun()

menu = st.sidebar.radio("メニュー", ["💰 レジ", "📦 在庫管理", "💸 経費", "✅ ToDo", "🍔 登録", "⚙️ 予算"])
st.sidebar.success(f"Login: **{selected_class}**")

# --- 予算バー ---
try:
    budget_data = {r[0]: int(r[1]) for r in get_raw_data("BUDGET") if len(r) >= 2}
    budget = budget_data.get(selected_class, 30000)
    
    class_data = get_raw_data(selected_class)
    expense = sum([int(str(r[4]).replace(',', '')) for r in class_data[1:] 
                   if len(r) > 4 and "経費" in str(r[1]) and str(r[4]).replace(',', '').isdigit()])
    
    rem = budget - expense
    st.write(f"📊 **残金: {rem:,}円** (予算: {budget:,}円)")
    st.progress(min(expense / budget, 1.0) if budget > 0 else 0)
except: pass
st.divider()

# ==========================================
# 💰 レジ機能
# ==========================================
if menu == "💰 レジ":
    st.subheader(f"💰 {selected_class} レジ")

    @st.fragment
    def render_pos():
        c_menu, c_receipt = st.columns([1.5, 1])
        
        all_menu = get_raw_data("MENU")
        my_menu = [r for r in all_menu[1:] if r[0] == selected_class]

        # 左側: 商品
        with c_menu:
            if not my_menu: st.info("メニュー未登録")
            cols = st.columns(2)
            for i, item in enumerate(my_menu):
                n, p = item[1], int(item[2])
                is_sold_out = (len(item) > 3 and item[3] == "完売")
                label = f"🚫 {n}\n(完売)" if is_sold_out else f"{n}\n¥{p}"
                
                if cols[i % 2].button(label, key=f"pos_{i}", use_container_width=True, disabled=is_sold_out):
                    st.session_state["cart"].append({"n": n, "p": p})
                    st.rerun()

        # 右側: 会計
        with c_receipt:
            total = sum([x['p'] for x in st.session_state["cart"]])
            
            with st.expander("🛒 カート", expanded=True):
                if not st.session_state["cart"]: st.write("(空)")
                else:
                    for x in st.session_state["cart"]: st.text(f"・{x['n']} : ¥{x['p']}")

            st.metric("合計", f"¥{total:,}")

            if total > 0:
                val = st.number_input("¥", value=st.session_state["received_amount"], step=10, label_visibility="collapsed")
                if val != st.session_state["received_amount"]:
                    st.session_state["received_amount"] = val; st.rerun()
                
                b_cols = st.columns(3)
                for i, amt in enumerate([1000, 500, 100, 50, 10, 0]):
                    label = "C" if amt == 0 else f"+{amt}"
                    if b_cols[i % 3].button(label, use_container_width=True):
                        st.session_state["received_amount"] = 0 if amt == 0 else st.session_state["received_amount"] + amt
                        st.rerun()

                change = st.session_state["received_amount"] - total
                if st.session_state["received_amount"] > 0:
                    if change >= 0: st.success(f"お釣り: ¥{change:,}")
                    else: st.error(f"不足: ¥{abs(change):,}")

                if st.button("会計確定", type="primary", use_container_width=True):
                    # ★修正: 合計金額より少ない場合（0円含む）はエラーにする
                    if st.session_state["received_amount"] < total:
                        st.session_state["flash_msg"] = "⚠️ 金額が足りません！"
                        st.session_state["flash_type"] = "error"
                        st.rerun()
                    else:
                        items_str = ",".join([x['n'] for x in st.session_state["cart"]])
                        def save_sales():
                            sh = get_spreadsheet(); ws = sh.worksheet(selected_class)
                            ws.append_row([datetime.now().strftime("%Y/%m/%d"), "🔵 売上", "レジ", items_str, total])
                        
                        st.session_state["cart"] = []
                        st.session_state["received_amount"] = 0
                        handle_db_action(save_sales, "売上を記録しました！")

            if st.button("クリア", use_container_width=True):
                st.session_state["cart"] = []; st.session_state["received_amount"] = 0; st.rerun()

    render_pos()

# ==========================================
# 📦 在庫管理
# ==========================================
elif menu == "📦 在庫管理":
    st.subheader("📦 在庫管理")
    st.caption("売り切れた商品はボタンを押して「完売」にしてください。レジで押せなくなります。")
    
    all_menu = get_raw_data("MENU")
    my_menu = [r for r in all_menu[1:] if r[0] == selected_class]
    
    if my_menu:
        for i, item in enumerate(my_menu):
            n = item[1]
            status = item[3] if len(item) > 3 else "販売中"
            c1, c2 = st.columns([3, 1])
            c1.write(f"**{n}**")
            
            btn_label = "🔴 完売にする" if status != "完売" else "🟢 販売再開"
            if c2.button(btn_label, key=f"stk_{i}"):
                new_status = "完売" if status != "完売" else "販売中"
                def update_status():
                    sh = get_spreadsheet(); ws = sh.worksheet("MENU")
                    cell = ws.find(n)
                    if cell: ws.update_cell(cell.row, 4, new_status)
                
                handle_db_action(update_status, f"{new_status}にしました")
    else: st.info("メニューなし")

# ==========================================
# 💸 経費入力
# ==========================================
elif menu == "💸 経費":
    st.subheader(f"💸 {selected_class} 経費")
    with st.form("exp"):
        c1, c2 = st.columns(2)
        d = c1.date_input("日付")
        p = c2.text_input("担当")
        i = st.text_input("品名")
        a = st.number_input("金額", min_value=0, step=1)
        if st.form_submit_button("登録", use_container_width=True):
            if not i or a <= 0: st.error("入力を確認してください")
            else:
                def save_exp():
                    sh = get_spreadsheet(); ws = sh.worksheet(selected_class)
                    ws.append_row([d.strftime("%Y/%m/%d"), "🔴 経費", p, i, a])
                handle_db_action(save_exp, "経費を登録しました")

# ==========================================
# ✅ ToDo
# ==========================================
elif menu == "✅ ToDo":
    st.subheader(f"✅ {selected_class} ToDo")
    with st.expander("➕ タスク追加", expanded=True):
        with st.form("todo"):
            t = st.text_input("内容")
            p = st.text_input("担当")
            if st.form_submit_button("追加", use_container_width=True):
                if t:
                    def save_todo():
                        sh = get_spreadsheet(); ws = sh.worksheet("TODO")
                        ws.append_row([selected_class, datetime.now().strftime("%Y/%m/%d"), t, p, "未完了"])
                    handle_db_action(save_todo, "タスクを追加しました")

    st.divider()
    
    @st.fragment
    def render_todo():
        all_todos = get_raw_data("TODO")
        if len(all_todos) > 1:
            active = [r + [idx+1] for idx, r in enumerate(all_todos) 
                      if idx > 0 and r[0] == selected_class and "未完了" in r[4]]
            
            if active:
                st.caption("チェックして完了")
                updates = []
                for task in active:
                    if st.checkbox(f"{task[2]} ({task[3]})", key=f"chk_{task[-1]}"): updates.append(task[-1])
                
                if updates and st.button("完了にする", type="primary", use_container_width=True):
                    def update_todo():
                        sh = get_spreadsheet(); ws = sh.worksheet("TODO")
                        for ridx in updates: ws.update_cell(ridx, 5, "完了")
                    handle_db_action(update_todo, "タスクを完了しました")
            else: st.info("現在タスクはありません")
    render_todo()

# ==========================================
# 🍔 メニュー登録
# ==========================================
elif menu == "🍔 登録":
    st.subheader("🍔 メニュー登録")
    with st.form("add_m"):
        c1, c2 = st.columns(2)
        n = c1.text_input("商品名")
        p = c2.number_input("単価", min_value=0, step=10)
        if st.form_submit_button("追加", use_container_width=True):
            if n and p > 0:
                def add_menu_item():
                    sh = get_spreadsheet(); ws = sh.worksheet("MENU")
                    ws.append_row([selected_class, n, p, "販売中"])
                handle_db_action(add_menu_item, f"「{n}」を追加しました")
            else: st.error("入力を確認してください")

    st.divider()
    st.write("📋 登録済みメニュー")
    
    menu_rows = get_raw_data("MENU")
    my_menu_list = [{"data": r, "idx": i+1} for i, r in enumerate(menu_rows) 
                    if i > 0 and r[0] == selected_class]
    
    if my_menu_list:
        for item in my_menu_list:
            row = item["data"]
            row_idx = item["idx"]
            c1, c2 = st.columns([3, 1])
            c1.write(f"・**{row[1]}** : ¥{row[2]}")
            
            if c2.button("削除", key=f"del_{row_idx}"):
                def del_menu_item():
                    sh = get_spreadsheet(); ws = sh.worksheet("MENU")
                    ws.delete_rows(row_idx)
                handle_db_action(del_menu_item, "削除しました")
    else: st.info("登録なし")

# ==========================================
# ⚙️ 予算設定
# ==========================================
elif menu == "⚙️ 予算":
    st.subheader("⚙️ 予算設定")
    with st.form("bud"):
        curr = 30000
        try:
            for r in get_raw_data("BUDGET"):
                if r[0] == selected_class: curr = int(r[1]); break
        except: pass
        
        new_b = st.number_input("新予算", value=curr, step=1000)
        if st.form_submit_button("更新", use_container_width=True):
            def update_budget():
                sh = get_spreadsheet(); ws = sh.worksheet("BUDGET")
                cell = ws.find(selected_class)
                if cell: ws.update_cell(cell.row, 2, new_b)
                else: ws.append_row([selected_class, new_b])
            handle_db_action(update_budget, "予算を更新しました")
