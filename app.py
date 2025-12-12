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

# クラス設定
CLASS_PASSWORDS = {
    f"{i}HR": str(i)*2 for i in range(21, 29)
}

# ページ設定 & CSS
st.set_page_config(page_title="文化祭レジ", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    div.stButton > button {
        word-break: keep-all !important; 
        overflow-wrap: break-word !important;
        height: auto !important;
        min-height: 60px !important;
        padding: 5px 10px !important;
        font-weight: bold !important;
        font-size: 16px !important;
        border-radius: 12px !important;
    }
    .stSpinner > div { border-top-color: #ff4b4b !important; }
    .block-container { padding-top: 1rem !important; padding-bottom: 2rem !important; }
    
    /* 売り切れボタン用 */
    .sold-out {
        background-color: #d3d3d3 !important;
        color: #808080 !important;
        cursor: not-allowed !important;
    }
    </style>
    """, unsafe_allow_html=True)

if "is_logged_in" not in st.session_state:
    st.session_state.update({
        "is_logged_in": False, "logged_class": None, 
        "cart": [], "received_amount": 0
    })

# ==========================================
# 🛡️ バックエンド
# ==========================================
@st.cache_resource(ttl=3600)
def get_spreadsheet():
    if "service_account_json" not in st.secrets:
        st.error("Secrets設定なし"); return None
    try:
        creds = json.loads(st.secrets["service_account_json"])
        gc = gspread.service_account_from_dict(creds)
        return gc.open(SPREADSHEET_NAME)
    except Exception as e:
        st.error(f"DB接続エラー: {e}"); return None

def safe_api_call(func, *args):
    max_retries = 3
    for i in range(max_retries):
        try:
            return func(*args)
        except Exception as e:
            if i == max_retries - 1: st.error(f"通信失敗: {e}"); return None
            time.sleep(1.5 ** i)
    return None

@st.cache_data(ttl=600)
def get_raw_data(tab_name):
    sh = get_spreadsheet()
    if not sh: return []
    try: return sh.worksheet(tab_name).get_all_values()
    except: return []

def append_data(tab_name, row, msg="保存完了"):
    def _append():
        sh = get_spreadsheet(); ws = sh.worksheet(tab_name)
        ws.append_row(row)
    
    with st.spinner("処理中..."):
        if safe_api_call(_append) is not None:
            get_raw_data.clear(); st.toast(f"✅ {msg}", icon="🎉"); time.sleep(0.1); st.rerun()

def update_stock_status(item_name, status):
    def _update():
        sh = get_spreadsheet(); ws = sh.worksheet("MENU")
        cell = ws.find(item_name)
        if cell: ws.update_cell(cell.row, 4, status)
    
    with st.spinner("更新中..."):
        if safe_api_call(_update) is not None:
            get_raw_data.clear(); st.toast(f"{status}にしました"); time.sleep(0.1); st.rerun()

# ==========================================
# 🏫 ログイン
# ==========================================
st.sidebar.title("🏫 クラス")
selected_class = st.sidebar.selectbox("選択", list(CLASS_PASSWORDS.keys()), label_visibility="collapsed")

if st.session_state["logged_class"] != selected_class:
    st.session_state.update({"is_logged_in": False, "logged_class": selected_class, "cart": [], "received_amount": 0})
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
if st.sidebar.button("ログアウト", use_container_width=True):
    st.session_state.update({"is_logged_in": False, "cart": [], "received_amount": 0})
    st.rerun()

menu = st.sidebar.radio("メニュー", ["💰 レジ", "📊 分析・在庫", "💸 経費", "✅ ToDo", "🍔 登録", "⚙️ 予算"])
st.sidebar.success(f"Login: **{selected_class}**")

# --- 予算バー ---
try:
    budget = 30000
    for r in get_raw_data("BUDGET"):
        if r and r[0] == selected_class: budget = int(r[1]); break
    
    c_rows = get_raw_data(selected_class)
    expense = 0
    if c_rows:
        for r in c_rows[1:]:
            if len(r) > 4 and "経費" in str(r[1]):
                try: expense += int(str(r[4]).replace(',', ''))
                except: pass
    
    rem = budget - expense
    st.write(f"📊 **残金: {rem:,}円** (予算: {budget:,}円)")
    st.progress(min(expense / budget, 1.0) if budget > 0 else 0)
except: pass
st.divider()

# ==========================================
# 💰 レジ
# ==========================================
if menu == "💰 レジ":
    st.subheader(f"💰 {selected_class} レジ")

    @st.fragment
    def render_pos():
        c_menu, c_receipt = st.columns([1.5, 1])
        menu_rows = get_raw_data("MENU")
        my_menu = [r for r in menu_rows[1:] if r[0] == selected_class]

        with c_menu:
            if not my_menu: st.info("メニュー未登録")
            cols = st.columns(2)
            for i, item in enumerate(my_menu):
                n, p = item[1], int(item[2])
                is_sold_out = (len(item) > 3 and item[3] == "完売")
                label = f"🚫 {n} (完売)" if is_sold_out else f"{n}\n¥{p}"
                
                # ★修正点: キーを商品名(n)ではなく、通し番号(i)に変更して重複エラーを回避
                if cols[i % 2].button(label, key=f"pos_btn_{i}", use_container_width=True, disabled=is_sold_out):
                    st.session_state["cart"].append({"n": n, "p": p})
                    st.rerun() 

        with c_receipt:
            total = sum([x['p'] for x in st.session_state["cart"]])
            with st.expander("カート", expanded=True):
                if not st.session_state["cart"]: st.write("(空)")
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
                    if st.session_state["received_amount"] < total and st.session_state["received_amount"] != 0:
                        st.toast("⚠️ 金額不足", icon="🚫")
                    else:
                        items_str = ",".join([x['n'] for x in st.session_state["cart"]])
                        append_data(selected_class, [datetime.now().strftime("%Y/%m/%d"), "🔵 売上", "レジ", items_str, total], "売上完了")
                        st.session_state["cart"] = []; st.session_state["received_amount"] = 0
            
            if st.button("クリア", use_container_width=True):
                st.session_state["cart"] = []; st.session_state["received_amount"] = 0; st.rerun()

    render_pos()

# ==========================================
# 📊 分析・在庫
# ==========================================
elif menu == "📊 分析・在庫":
    st.subheader("📊 売上分析 & 在庫")
    
    tab1, tab2 = st.tabs(["📦 在庫", "📈 売上"])
    
    with tab1:
        menu_rows = get_raw_data("MENU")
        my_menu = [r for r in menu_rows[1:] if r[0] == selected_class]
        
        if my_menu:
            for i, item in enumerate(my_menu): # enumerateを使用
                n = item[1]
                status = item[3] if len(item) > 3 else "販売中"
                c1, c2 = st.columns([3, 1])
                c1.write(f"**{n}**")
                
                btn_label = "🔴 完売にする" if status != "完売" else "🟢 販売再開"
                # キーに通し番号(i)を使って重複回避
                if c2.button(btn_label, key=f"stock_{i}_{n}"):
                    new_status = "完売" if status != "完売" else "販売中"
                    update_stock_status(n, new_status)
        else: st.info("メニューがありません")

    with tab2:
        c_rows = get_raw_data(selected_class)
        if len(c_rows) > 1:
            df = pd.DataFrame(c_rows[1:], columns=c_rows[0])
            if "種別" in df.columns and "内容" in df.columns:
                sales_df = df[df["種別"].astype(str).str.contains("売上")]
                item_counts = {}
                for items in sales_df["内容"]:
                    for item in items.split(","):
                        i_name = item.strip()
                        item_counts[i_name] = item_counts.get(i_name, 0) + 1
                
                if item_counts:
                    chart_data = pd.DataFrame(list(item_counts.items()), columns=["商品", "個数"]).set_index("商品")
                    st.bar_chart(chart_data)
                else: st.info("まだ売上がありません")
        else: st.info("データがありません")

# ==========================================
# 💸 経費
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
            else: append_data(selected_class, [d.strftime("%Y/%m/%d"), "🔴 経費", p, i, a])

# ==========================================
# ✅ ToDo
# ==========================================
elif menu == "✅ ToDo":
    st.subheader(f"✅ {selected_class} ToDo")
    with st.expander("➕ タスク追加", expanded=True):
        with st.form("todo"):
            t = st.text_input("内容")
            p = st.text_input("担当")
            if st.form_submit_button("書き込む", use_container_width=True):
                if t: append_data("TODO", [selected_class, datetime.now().strftime("%Y/%m/%d"), t, p, "未完了"])
    st.divider()
    @st.fragment
    def render_todo():
        rows = get_raw_data("TODO")
        if len(rows) > 1:
            active = [r + [idx+1] for idx, r in enumerate(rows) if idx > 0 and r[0] == selected_class and "未完了" in r[4]]
            if active:
                st.caption("チェックして完了")
                updates = []
                for task in active:
                    if st.checkbox(f"{task[2]} ({task[3]})", key=f"chk_todo_{task[-1]}"): updates.append(task[-1])
                if updates and st.button("完了にする", type="primary", use_container_width=True):
                    def _update():
                        sh = get_spreadsheet(); ws = sh.worksheet("TODO")
                        for ridx in updates: ws.update_cell(ridx, 5, "完了")
                    if safe_api_call(_update) is not None:
                        get_raw_data.clear(); st.toast("更新完了"); time.sleep(0.1); st.rerun()
            else: st.info("タスクなし")
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
            if n and p > 0: append_data("MENU", [selected_class, n, p, "販売中"], "追加しました")
            else: st.error("確認してください")

    st.divider()
    
    st.write("📋 登録済みメニュー")
    menu_rows = get_raw_data("MENU")
    
    my_menu_items = []
    for idx, row in enumerate(menu_rows):
        if idx > 0 and row[0] == selected_class:
            my_menu_items.append({"data": row, "idx": idx + 1})

    if my_menu_items:
        for item in my_menu_items:
            row = item["data"]
            row_idx = item["idx"]
            
            c1, c2 = st.columns([3, 1])
            c1.write(f"・**{row[1]}** : ¥{row[2]}")
            
            # 削除ボタン
            if c2.button("削除", key=f"del_menu_{row_idx}"): # 行番号をキーにする
                def _del():
                    sh = get_spreadsheet(); ws = sh.worksheet("MENU")
                    ws.delete_rows(row_idx)
                
                with st.spinner("削除中..."):
                    if safe_api_call(_del) is not None:
                        get_raw_data.clear()
                        st.toast("削除しました")
                        time.sleep(0.1)
                        st.rerun()
    else:
        st.info("登録されている商品はありません")

# ==========================================
# ⚙️ 予算設定
# ==========================================
elif menu == "⚙️ 予算":
    st.subheader("⚙️ 予算")
    with st.form("bud"):
        curr = 30000
        try:
            for r in get_raw_data("BUDGET"):
                if r[0] == selected_class: curr = int(r[1]); break
        except: pass
        new_b = st.number_input("新予算", value=curr, step=1000)
        if st.form_submit_button("更新", use_container_width=True):
            def _upd():
                sh = get_spreadsheet(); ws = sh.worksheet("BUDGET")
                cell = ws.find(selected_class)
                if cell: ws.update_cell(cell.row, 2, new_b)
                else: ws.append_row([selected_class, new_b])
            if safe_api_call(_upd) is not None:
                get_raw_data.clear(); st.toast("予算更新"); time.sleep(0.1); st.rerun()