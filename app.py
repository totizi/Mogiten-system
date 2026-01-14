import streamlit as st
from datetime import datetime
import json
import gspread
import time
from collections import Counter

# ==========================================
# ⚙️ 設定エリア
# ==========================================
SPREADSHEET_NAME = "模擬店データベース"
CLASS_PASSWORDS = {f"{i}HR": str(i)*2 for i in range(21, 29)}

st.set_page_config(page_title="文化祭レジ", layout="wide", initial_sidebar_state="auto")

st.markdown("""
    <style>
    footer {visibility: hidden;}
    
    /* === 商品ボタンのデザイン（通常） === 
       高さを80pxに固定して正方形っぽく見せる */
    div.stButton > button[kind="secondary"] {
        height: 80px !important;
        width: 100% !important;
        
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
        align-items: center !important;
        white-space: pre-wrap !important;
        line-height: 1.2 !important;
        
        padding: 2px !important; 
        font-weight: bold !important; 
        font-size: 14px !important;
        border-radius: 8px !important;
    }

    /* === 重要なボタン（会計確定など） === */
    div.stButton > button[kind="primary"] {
        min-height: 60px !important;
        width: 100% !important;
        font-size: 18px !important;
        font-weight: bold !important;
        border-radius: 10px !important;
    }
    
    /* === 【特例】リスト（Expander）の中にあるボタンは小さくする === 
       カートの削除ボタンや、メニュー登録の削除ボタンに適用されます */
    div[data-testid="stExpander"] div.stButton > button {
        height: 40px !important;      /* 高さを40pxに強制 */
        min-height: 40px !important;
        width: auto !important;
        
        background-color: #fff0f0 !important; /* 薄い赤背景 */
        color: #d00 !important;               /* 赤文字 */
        border: 1px solid #ffcccc !important; /* 赤枠 */
        border-radius: 5px !important;
        font-size: 14px !important;
        padding: 0px 10px !important;
    }
    
    /* === スマホレイアウト対策 === */
    [data-testid="column"] {
        min-width: 0 !important;
        flex: 1 1 auto !important;
    }
    
    /* 売り切れボタン */
    button:disabled {
        opacity: 0.4 !important;
        cursor: not-allowed !important;
        border: 1px dashed inherit !important;
    }
    
    .block-container { 
        padding-top: 3.5rem !important;
        padding-bottom: 5rem !important; 
    }
    </style>
""", unsafe_allow_html=True)

if "is_logged_in" not in st.session_state:
    st.session_state.update({
        "is_logged_in": False, "logged_class": None, "cart": [], 
        "received_amount": 0, "flash_msg": None, "flash_type": "success",
        "del_confirm_idx": None # 削除確認用
    })

# ==========================================
# 🚀 バックエンド処理
# ==========================================
@st.cache_resource
def get_gc():
    if "service_account_json" not in st.secrets: return None
    return gspread.service_account_from_dict(json.loads(st.secrets["service_account_json"]))

@st.cache_resource
def get_worksheet(tab_name):
    gc = get_gc()
    if not gc: return None
    try: return gc.open(SPREADSHEET_NAME).worksheet(tab_name)
    except: return None

@st.cache_data(ttl=60) 
def get_raw_data(tab_name):
    ws = get_worksheet(tab_name)
    return ws.get_all_values() if ws else []

def execute_db_action(action_func, msg="完了"):
    try:
        with st.spinner("処理中..."):
            action_func()
            get_raw_data.clear()
            st.session_state["flash_msg"] = f"✅ {msg}"
            st.session_state["flash_type"] = "success"
            st.rerun()
    except Exception as e:
        st.error(f"エラー: {e}")
        time.sleep(1)

# ==========================================
# 🏫 ログイン画面
# ==========================================
if not st.session_state["is_logged_in"]:
    st.title("🏫 文化祭システム")
    selected_class = st.selectbox("クラスを選択", list(CLASS_PASSWORDS.keys()))
    with st.form("login"):
        pw = st.text_input("パスワード", type="password")
        if st.form_submit_button("ログイン", type="primary", use_container_width=True):
            if pw.strip() == CLASS_PASSWORDS.get(selected_class):
                st.session_state["is_logged_in"] = True
                st.session_state["logged_class"] = selected_class
                st.rerun()
            else: st.error("パスワードが違います")
    st.stop()

# ==========================================
# 🎉 メイン画面
# ==========================================
selected_class = st.session_state["logged_class"]

# フラッシュメッセージ
if st.session_state["flash_msg"]:
    if st.session_state["flash_type"] == "success": st.success(st.session_state["flash_msg"])
    else: st.error(st.session_state["flash_msg"])
    st.session_state["flash_msg"] = None

# --- サイドバー構成 ---
st.sidebar.title(f"🏫 {selected_class}")
mode = st.sidebar.selectbox("📂 モード切替", ["🎪 当日運営", "🛠 準備・前日"])
st.sidebar.divider()

if mode == "🛠 準備・前日":
    menu = st.sidebar.radio("メニュー", ["🍔 登録", "💸 経費", "✅ ToDo", "⚙️ 予算"])
else:
    menu = st.sidebar.radio("メニュー", ["💰 レジ", "📦 在庫"])

st.sidebar.divider()
if st.sidebar.button("ログアウト", use_container_width=True):
    st.session_state.update({"is_logged_in": False, "cart": [], "received_amount": 0}); st.rerun()


# --- メインエリア表示 ---

# 予算バー
try:
    budget = 30000
    for r in get_raw_data("BUDGET"):
        if len(r) >= 2 and r[0] == selected_class:
            budget = int(r[1]); break
            
    class_rows = get_raw_data(selected_class)
    expense = sum(int(str(r[4]).replace(',', '')) for r in class_rows[1:] 
                  if len(r) > 4 and "経費" in str(r[1]) and str(r[4]).replace(',', '').isdigit())
    
    remaining = budget - expense
    
    if remaining < 0:
        bar_color = "#ff4b4b"
        msg_html = f"🚨 <b style='color: #ff4b4b'>予算超過: {abs(remaining):,}円</b> (予算: {budget:,}円)"
        percent = 100
    else:
        bar_color = "#00cc96"
        msg_html = f"📊 <b>残金: {remaining:,}円</b> (予算: {budget:,}円)"
        percent = int((expense / budget) * 100) if budget > 0 else 0
        percent = min(percent, 100)

    st.markdown(f"""
        <div style="padding-top: 5px; margin-bottom: 5px; font-size: 16px;">
            {msg_html}
        </div>
        <div style="background-color: #f0f2f6; border-radius: 10px; height: 20px; width: 100%; margin-bottom: 20px;">
            <div style="background-color: {bar_color}; width: {percent}%; height: 100%; border-radius: 10px; transition: width 0.5s;"></div>
        </div>
    """, unsafe_allow_html=True)
    
except: pass

st.divider()

# ==========================================
# 💰 レジ
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
                
                in_cart_qty = cart_counts[n]
                remaining_addable = max(0, stock - in_cart_qty)
                is_disabled = (status == "完売" or stock <= 0 or remaining_addable == 0)
                
                if status == "完売" or stock <= 0: label = f"🚫\n{n}\n(完売)"
                elif remaining_addable == 0: label = f"🚫\n{n}\n(上限)"
                else: label = f"{n}\n¥{p}\n(残{stock})"

                if cols[i % 2].button(label, key=f"p_{i}", use_container_width=True, disabled=is_disabled):
                    st.session_state["cart"].append({"n": n, "p": p}); st.rerun()

        with c2: 
            total = sum(x['p'] for x in st.session_state["cart"])
            with st.expander("🛒 カート", expanded=True):
                if not st.session_state["cart"]:
                    st.write("(空)")
                else:
                    for i, item in enumerate(st.session_state["cart"]):
                        c_text, c_del = st.columns([3, 1])
                        c_text.write(f"・{item['n']}")
                        if c_del.button("削除", key=f"del_cart_{i}", type="secondary"):
                            st.session_state["cart"].pop(i)
                            st.rerun()
            
            st.metric("合計", f"¥{total:,}")
            if total > 0:
                val = st.number_input("¥", value=st.session_state["received_amount"], step=10, label_visibility="collapsed")
                if val != st.session_state["received_amount"]:
                    st.session_state["received_amount"] = val; st.rerun()
                
                bc = st.columns(3)
                for i, amt in enumerate([1000, 500, 100, 50, 10, 0]):
                    if bc[i%3].button(f"+{amt}" if amt else "C", use_container_width=True):
                        st.session_state["received_amount"] = 0 if amt == 0 else st.session_state["received_amount"] + amt
                        st.rerun()

                if st.session_state["received_amount"] > 0:
                    change = st.session_state["received_amount"] - total
                    if change >= 0: st.success(f"お釣り: ¥{change:,}")
                    else: st.error(f"不足: ¥{abs(change):,}")

                if st.button("会計確定", type="primary", use_container_width=True):
                    if st.session_state["received_amount"] < total:
                        st.session_state["flash_msg"] = "⚠️ 金額不足"; st.session_state["flash_type"] = "error"; st.rerun()
                    else:
                        cart_item_names = [x['n'] for x in st.session_state["cart"]]
                        item_counts = Counter(cart_item_names)
                        items_str = ",".join(cart_item_names)
                        
                        def process_checkout():
                            ws_sales = get_worksheet(selected_class)
                            ws_menu = get_worksheet("MENU")
                            ws_sales.append_row([datetime.now().strftime("%Y/%m/%d"), "🔵 売上", "レジ", items_str, total])
                            
                            menu_data = ws_menu.get_all_values()
                            for idx, row in enumerate(menu_data):
                                if idx > 0 and row[0] == selected_class and row[1] in item_counts:
                                    item_name = row[1]
                                    sell_count = item_counts[item_name]
                                    current_stock = int(row[4]) if len(row) > 4 and row[4].isdigit() else 0
                                    new_stock = max(0, current_stock - sell_count)
                                    ws_menu.update_cell(idx + 1, 5, new_stock)
                                    if new_stock == 0: ws_menu.update_cell(idx + 1, 4, "完売")
                                        
                        st.session_state["cart"] = []; st.session_state["received_amount"] = 0
                        execute_db_action(process_checkout, "売上＆在庫更新完了")
            
            if st.button("クリア", use_container_width=True):
                st.session_state["cart"] = []; st.session_state["received_amount"] = 0; st.rerun()
    render_pos()

# ==========================================
# 📦 在庫管理
# ==========================================
elif menu == "📦 在庫":
    st.subheader("📦 在庫管理")
    my_menu = [r for r in get_raw_data("MENU")[1:] if r[0] == selected_class]
    if my_menu:
        for i, item in enumerate(my_menu):
            n = item[1]
            stock = int(item[4]) if len(item) > 4 and item[4].isdigit() else 0
            
            c1, c2, c3 = st.columns([2, 1, 1])
            c1.write(f"**{n}**")
            new_stock = c2.number_input(f"在庫 ({n})", value=stock, min_value=0, step=1, label_visibility="collapsed", key=f"inp_{i}")
            if c3.button("更新", key=f"upd_{i}"):
                def update_stock():
                    ws = get_worksheet("MENU")
                    cell = ws.find(n)
                    if cell:
                        ws.update_cell(cell.row, 5, new_stock)
                        ws.update_cell(cell.row, 4, "完売" if new_stock == 0 else "販売中")
                execute_db_action(update_stock, f"在庫更新: {new_stock}個")
    else: st.info("メニューなし")

# ==========================================
# 💸 経費入力
# ==========================================
elif menu == "💸 経費":
    st.subheader(f"💸 {selected_class} 経費")
    with st.form("exp"):
        c1, c2 = st.columns(2)
        d, p = c1.date_input("日付"), c2.text_input("担当")
        i, a = st.text_input("品名"), st.number_input("金額", min_value=0, step=1)
        if st.form_submit_button("登録", use_container_width=True):
            if not p or not i or a <= 0:
                st.error("⚠️ 担当者・品名・金額をすべて入力してください")
            else: 
                execute_db_action(lambda: get_worksheet(selected_class).append_row(
                    [d.strftime("%Y/%m/%d"), "🔴 経費", p, i, a]), "経費登録完了")

# ==========================================
# ✅ ToDo
# ==========================================
elif menu == "✅ ToDo":
    st.subheader(f"✅ {selected_class} ToDo")
    with st.form("todo"):
        t, p = st.text_input("内容"), st.text_input("担当")
        if st.form_submit_button("追加", use_container_width=True):
            if t: execute_db_action(lambda: get_worksheet("TODO").append_row(
                [selected_class, datetime.now().strftime("%Y/%m/%d"), t, p, "未完了"]), "追加完了")
    st.divider()
    @st.fragment
    def render_todo():
        raw = get_raw_data("TODO")
        active = [r + [idx+1] for idx, r in enumerate(raw) if idx > 0 and r[0] == selected_class and "未完了" in r[4]]
        if active:
            updates = []
            for task in active:
                if st.checkbox(f"{task[2]} ({task[3]})", key=f"chk_{task[-1]}"): updates.append(task[-1])
            if updates and st.button("完了にする", type="primary", use_container_width=True):
                ws = get_worksheet("TODO")
                execute_db_action(lambda: [ws.update_cell(r, 5, "完了") for r in updates], "タスク完了")
        else: st.info("タスクなし")
    render_todo()

# ==========================================
# 🍔 メニュー登録
# ==========================================
elif menu == "🍔 登録":
    st.subheader("🍔 メニュー登録")
    with st.form("add_m"):
        c1, c2, c3 = st.columns([2, 1, 1])
        n = c1.text_input("商品名")
        p = c2.number_input("単価", min_value=0, step=10)
        s = c3.number_input("在庫数", min_value=1, value=50, step=1)
        if st.form_submit_button("追加", use_container_width=True):
            if n and p > 0:
                execute_db_action(lambda: get_worksheet("MENU").append_row(
                    [selected_class, n, p, "販売中", s]), f"「{n}」を{s}個で追加")
            else: st.error("入力確認")

    st.divider()
    
    # ★修正点: Expanderで囲むことでCSSの「小さいボタンルール」を適用させる
    with st.expander("📋 登録済みメニュー一覧", expanded=True):
        my_menu = [{"d": r, "idx": i+1} for i, r in enumerate(get_raw_data("MENU")) if i > 0 and r[0] == selected_class]
        
        if my_menu:
            for item in my_menu:
                row, idx = item["d"], item["idx"]
                stock = row[4] if len(row) > 4 else "0"
                
                c1, c2 = st.columns([3, 1])
                c1.write(f"・**{row[1]}** : ¥{row[2]} (在庫: {stock})")
                
                # ★修正点: 削除確認ロジック
                # 削除確認モードかどうかチェック
                if st.session_state["del_confirm_idx"] == idx:
                    c2.warning("本当に削除？")
                    c_yes, c_no = c2.columns(2)
                    if c_yes.button("はい", key=f"yes_{idx}"):
                        execute_db_action(lambda: get_worksheet("MENU").delete_rows(idx), "削除しました")
                        st.session_state["del_confirm_idx"] = None # リセット
                    if c_no.button("取消", key=f"no_{idx}"):
                        st.session_state["del_confirm_idx"] = None
                        st.rerun()
                else:
                    # 通常の削除ボタン
                    if c2.button("削除", key=f"d_{idx}"):
                        st.session_state["del_confirm_idx"] = idx
                        st.rerun()
        else:
            st.info("登録なし")

# ==========================================
# ⚙️ 予算
# ==========================================
elif menu == "⚙️ 予算":
    st.subheader("⚙️ 予算設定")
    curr = 30000
    for r in get_raw_data("BUDGET"):
        if len(r) >= 2 and r[0] == selected_class: curr = int(r[1]); break
    
    with st.form("bud"):
        nb = st.number_input("新予算", value=curr, step=1000)
        if st.form_submit_button("更新", use_container_width=True):
            ws = get_worksheet("BUDGET")
            execute_db_action(lambda: ws.update_cell(ws.find(selected_class).row, 2, nb) 
                              if ws.find(selected_class) else ws.append_row([selected_class, nb]), "予算更新")
