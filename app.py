import streamlit as st
from datetime import datetime
import json
import gspread
import time

# ==========================================
# ⚙️ 設定 & CSS (変更なし)
# ==========================================
SPREADSHEET_NAME = "模擬店データベース"
CLASS_PASSWORDS = {f"{i}HR": str(i)*2 for i in range(21, 29)}

st.set_page_config(page_title="文化祭レジ", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden;}
    div.stButton > button {
        word-break: keep-all !important; overflow-wrap: break-word !important;
        height: auto !important; min-height: 60px !important;
        padding: 8px 12px !important; font-weight: bold !important; font-size: 18px !important;
        border-radius: 12px !important;
    }
    .stSpinner > div { border-top-color: #ff4b4b !important; }
    button:disabled {
        background-color: #e0e0e0 !important; color: #a0a0a0 !important;
        border-color: #d0d0d0 !important; cursor: not-allowed !important; opacity: 0.8 !important;
    }
    .block-container { padding-top: 1rem !important; padding-bottom: 3rem !important; }
    </style>
""", unsafe_allow_html=True)

if "is_logged_in" not in st.session_state:
    st.session_state.update({
        "is_logged_in": False, "logged_class": None, "cart": [], 
        "received_amount": 0, "flash_msg": None, "flash_type": "success"
    })

# ==========================================
# 🚀 超高速バックエンド処理
# ==========================================
@st.cache_resource
def get_gc():
    """Gspreadクライアントを永続キャッシュ"""
    if "service_account_json" not in st.secrets: return None
    return gspread.service_account_from_dict(json.loads(st.secrets["service_account_json"]))

@st.cache_resource
def get_worksheet(tab_name):
    """【高速化の肝】ワークシート接続オブジェクト自体をキャッシュ"""
    gc = get_gc()
    if not gc: return None
    try: return gc.open(SPREADSHEET_NAME).worksheet(tab_name)
    except: return None

@st.cache_data(ttl=60) # 在庫反映のため1分更新
def get_raw_data(tab_name):
    """データ取得"""
    ws = get_worksheet(tab_name)
    return ws.get_all_values() if ws else []

def execute_db_action(action_func, msg="完了"):
    """アクション実行・キャッシュクリア・即リロード"""
    try:
        with st.spinner("処理中..."):
            action_func()
            get_raw_data.clear() # データキャッシュのみ破棄
            st.session_state["flash_msg"] = f"✅ {msg}"
            st.session_state["flash_type"] = "success"
            st.rerun()
    except Exception as e:
        st.error(f"エラー: {e}")
        time.sleep(1) # エラー時のみ少し待つ

# ==========================================
# 🏫 ログイン
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
if st.session_state["flash_msg"]:
    if st.session_state["flash_type"] == "success": st.success(st.session_state["flash_msg"])
    else: st.error(st.session_state["flash_msg"])
    st.session_state["flash_msg"] = None

if st.sidebar.button("ログアウト", use_container_width=True):
    st.session_state.update({"is_logged_in": False, "cart": [], "received_amount": 0}); st.rerun()

menu = st.sidebar.radio("メニュー", ["💰 レジ", "📦 在庫管理", "💸 経費", "✅ ToDo", "🍔 登録", "⚙️ 予算"])
st.sidebar.success(f"Login: **{selected_class}**")

# --- 📊 予算バー (超高速集計) ---
try:
    # 予算: リスト内包表記で検索 (APIコールなし)
    budget = 30000
    for r in get_raw_data("BUDGET"):
        if len(r) >= 2 and r[0] == selected_class:
            budget = int(r[1]); break
    
    # 経費: ジェネレータ式でメモリ節約
    class_rows = get_raw_data(selected_class)
    expense = sum(int(str(r[4]).replace(',', '')) for r in class_rows[1:] 
                  if len(r) > 4 and "経費" in str(r[1]) and str(r[4]).replace(',', '').isdigit())
    
    st.write(f"📊 **残金: {budget - expense:,}円** (予算: {budget:,}円)")
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
        c1, c2 = st.columns([1.5, 1])
        my_menu = [r for r in get_raw_data("MENU")[1:] if r[0] == selected_class]

        with c1: # メニュー
            if not my_menu: st.info("メニュー未登録")
            cols = st.columns(2)
            for i, item in enumerate(my_menu):
                n, p = item[1], int(item[2])
                sold_out = (len(item) > 3 and item[3] == "完売")
                label = f"🚫 {n}\n(完売)" if sold_out else f"{n}\n¥{p}"
                if cols[i % 2].button(label, key=f"p_{i}", use_container_width=True, disabled=sold_out):
                    st.session_state["cart"].append({"n": n, "p": p}); st.rerun()

        with c2: # 会計
            total = sum(x['p'] for x in st.session_state["cart"])
            with st.expander("🛒 カート", expanded=True):
                if not st.session_state["cart"]: st.write("(空)")
                for x in st.session_state["cart"]: st.text(f"・{x['n']} : ¥{x['p']}")
            
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
                        items = ",".join(x['n'] for x in st.session_state["cart"])
                        st.session_state["cart"] = []; st.session_state["received_amount"] = 0
                        execute_db_action(lambda: get_worksheet(selected_class).append_row(
                            [datetime.now().strftime("%Y/%m/%d"), "🔵 売上", "レジ", items, total]), "売上記録完了")
            
            if st.button("クリア", use_container_width=True):
                st.session_state["cart"] = []; st.session_state["received_amount"] = 0; st.rerun()
    render_pos()

# ==========================================
# 📦 在庫管理
# ==========================================
elif menu == "📦 在庫管理":
    st.subheader("📦 在庫管理")
    my_menu = [r for r in get_raw_data("MENU")[1:] if r[0] == selected_class]
    if my_menu:
        for i, item in enumerate(my_menu):
            n = item[1]
            status = item[3] if len(item) > 3 else "販売中"
            c1, c2 = st.columns([3, 1])
            c1.write(f"**{n}**"); c2.write(f"状態: {status}")
            
            btn_lbl = "🔴 完売にする" if status != "完売" else "🟢 販売再開"
            if c2.button(btn_label=btn_lbl, key=f"s_{i}"):
                new_stat = "完売" if status != "完売" else "販売中"
                # 安全のためセル検索して更新
                execute_db_action(lambda: get_worksheet("MENU").find(n) and 
                                  get_worksheet("MENU").update_cell(get_worksheet("MENU").find(n).row, 4, new_stat), 
                                  f"{new_stat}にしました")
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
            if not i or a <= 0: st.error("入力確認")
            else: execute_db_action(lambda: get_worksheet(selected_class).append_row(
                [d.strftime("%Y/%m/%d"), "🔴 経費", p, i, a]), "経費登録完了")

# ==========================================
# ✅ ToDo
# ==========================================
elif menu == "✅ ToDo":
    st.subheader(f"✅ {selected_class} ToDo")
    with st.expander("➕ タスク追加", expanded=True):
        with st.form("todo"):
            t, p = st.text_input("内容"), st.text_input("担当")
            if st.form_submit_button("追加", use_container_width=True):
                if t: execute_db_action(lambda: get_worksheet("TODO").append_row(
                    [selected_class, datetime.now().strftime("%Y/%m/%d"), t, p, "未完了"]), "追加完了")
    st.divider()
    
    @st.fragment
    def render_todo():
        raw = get_raw_data("TODO")
        # index保持: [row_data..., row_idx]
        active = [r + [idx+1] for idx, r in enumerate(raw) if idx > 0 and r[0] == selected_class and "未完了" in r[4]]
        if active:
            updates = []
            for task in active:
                if st.checkbox(f"{task[2]} ({task[3]})", key=f"chk_{task[-1]}"): updates.append(task[-1])
            if updates and st.button("完了にする", type="primary", use_container_width=True):
                ws = get_worksheet("TODO")
                # update_cellsで一括更新したいが、行が飛び飛びなのでループ処理
                execute_db_action(lambda: [ws.update_cell(r, 5, "完了") for r in updates], "タスク完了")
        else: st.info("タスクなし")
    render_todo()

# ==========================================
# 🍔 メニュー登録
# ==========================================
elif menu == "🍔 登録":
    st.subheader("🍔 メニュー登録")
    with st.form("add_m"):
        c1, c2 = st.columns(2)
        n, p = c1.text_input("商品名"), c2.number_input("単価", min_value=0, step=10)
        if st.form_submit_button("追加", use_container_width=True):
            if n and p > 0:
                execute_db_action(lambda: get_worksheet("MENU").append_row(
                    [selected_class, n, p, "販売中"]), f"「{n}」追加完了")
            else: st.error("入力確認")

    st.divider()
    my_menu = [{"d": r, "idx": i+1} for i, r in enumerate(get_raw_data("MENU")) if i > 0 and r[0] == selected_class]
    if my_menu:
        for item in my_menu:
            row, idx = item["d"], item["idx"]
            c1, c2 = st.columns([3, 1])
            c1.write(f"・**{row[1]}** : ¥{row[2]}")
            if c2.button("削除", key=f"d_{idx}"):
                 # 安全のため商品名検索で削除
                execute_db_action(lambda: get_worksheet("MENU").find(row[1]) and 
                                  get_worksheet("MENU").delete_rows(get_worksheet("MENU").find(row[1]).row), 
                                  "削除完了")

# ==========================================
# ⚙️ 予算
# ==========================================
elif menu == "⚙️ 予算":
    st.subheader("⚙️ 予算")
    curr = 30000
    for r in get_raw_data("BUDGET"):
        if len(r) >= 2 and r[0] == selected_class: curr = int(r[1]); break
    
    with st.form("bud"):
        nb = st.number_input("新予算", value=curr, step=1000)
        if st.form_submit_button("更新", use_container_width=True):
            ws = get_worksheet("BUDGET")
            execute_db_action(lambda: ws.update_cell(ws.find(selected_class).row, 2, nb) 
                              if ws.find(selected_class) else ws.append_row([selected_class, nb]), "予算更新")
