import streamlit as st
from datetime import datetime
import json
import gspread
import time

# ==========================================
# ⚙️ 設定エリア
# ==========================================
SPREADSHEET_NAME = "模擬店データベース"

# 🔐 クラスごとのパスワード
CLASS_PASSWORDS = {
    "21HR": "2121", "22HR": "2222", "23HR": "2323", "24HR": "2424",
    "25HR": "2525", "26HR": "2626", "27HR": "2727", "28HR": "2828"
}

st.set_page_config(page_title="文化祭レジ", layout="wide")

st.markdown("""
    <style>
    /* ボタンのスタイル調整 */
    div.stButton > button {
        /* 文字が長くても途中で切らず、単語の区切り（日本語は句読点や種別）で改行 */
        word-break: keep-all !important; 
        overflow-wrap: break-word !important;
        
        /* ボタンの高さを文字数に合わせて自動調整 */
        height: auto !important;
        min-height: 50px !important;
        padding-top: 10px !important;
        padding-bottom: 10px !important;
        
        /* 文字サイズを少し小さくして収まりやすくする（お好みで） */
        /* font-size: 14px !important; */
    }
    </style>
    """, unsafe_allow_html=True)

# セッション初期化（存在しない場合のみ作成）
if "is_logged_in" not in st.session_state:
    st.session_state.update({
        "is_logged_in": False, "logged_class": None, 
        "cart": [], "received_amount": 0
    })

# ==========================================
# 🛠️ 超軽量バックエンド処理
# ==========================================
def get_gc():
    """Gspreadクライアント取得（エラー処理込み）"""
    if "service_account_json" not in st.secrets:
        st.error("Secrets設定なし"); return None
    try:
        return gspread.service_account_from_dict(json.loads(st.secrets["service_account_json"]))
    except: return None

@st.cache_data(ttl=600)
def get_raw_data(tab_name):
    """【高速】生データをリストとして取得"""
    gc = get_gc()
    if not gc: return []
    try:
        # worksheet作成の通信を省略するため、openと同時に取得を試みる
        sh = gc.open(SPREADSHEET_NAME)
        return sh.worksheet(tab_name).get_all_values()
    except: return []

def append_data(tab_name, row, msg="保存完了"):
    """データ追加＆リロード"""
    gc = get_gc()
    if gc:
        try:
            sh = gc.open(SPREADSHEET_NAME).worksheet(tab_name)
            sh.append_row(row)
            get_raw_data.clear() # キャッシュクリア
            st.success(f"✅ {msg}")
            time.sleep(0.3) # 演出用ウェイト（最小限）
            st.rerun()
        except: st.error("保存エラー")

def update_budget(class_name, amount):
    """予算更新"""
    gc = get_gc()
    if gc:
        try:
            sh = gc.open(SPREADSHEET_NAME).worksheet("BUDGET")
            # 既存のセルを探す（API負荷軽減のためセル検索を利用）
            cell = sh.find(class_name)
            if cell: sh.update_cell(cell.row, 2, amount)
            else: sh.append_row([class_name, amount])
            get_raw_data.clear()
            st.success("予算更新！"); time.sleep(0.3); st.rerun()
        except: st.error("更新エラー")

# ==========================================
# 🏫 サイドバー & ログイン
# ==========================================
st.sidebar.title("🏫 クラス選択")
selected_class = st.sidebar.selectbox("クラス", list(CLASS_PASSWORDS.keys()))

# クラス切り替え検知
if st.session_state["logged_class"] != selected_class:
    st.session_state.update({"is_logged_in": False, "logged_class": selected_class, "cart": [], "received_amount": 0})
    st.rerun()

st.sidebar.divider()

if not st.session_state["is_logged_in"]:
    st.title(f"🔒 {selected_class} ログイン")
    pw = st.text_input("パスワード", type="password")
    if st.button("ログイン"):
        if pw.strip() == CLASS_PASSWORDS.get(selected_class):
            st.session_state["is_logged_in"] = True
            st.rerun()
        else: st.error("パスワードが違います")
    st.stop()

# ==========================================
# 🎉 メイン画面
# ==========================================
if st.sidebar.button("ログアウト"):
    st.session_state.update({"is_logged_in": False, "cart": [], "received_amount": 0})
    st.rerun()

menu = st.sidebar.radio("メニュー", ["💸 経費入力", "✅ ToDo", "💰 レジ", "🍔 メニュー", "⚙️ 予算"])
st.sidebar.success(f"Login: **{selected_class}**")

# --- 📊 予算計算（Pandasなしで高速集計） ---
# 1. 予算取得
budget_rows = get_raw_data("BUDGET")
budget = 30000 # デフォルト
for r in budget_rows:
    if r and r[0] == selected_class:
        budget = int(r[1])
        break

# 2. 経費合計（クラスシートのE列(index 4)を集計）
class_rows = get_raw_data(selected_class)
current_expense = 0
if class_rows:
    # 1行目はヘッダーなのでスキップ
    for row in class_rows[1:]:
        # 行の長さが足りているか確認 & B列(index 1)に「経費」が含まれるか
        if len(row) > 4 and "経費" in str(row[1]):
            try: current_expense += int(row[4])
            except: pass

st.write(f"📊 **残金: {budget - current_expense:,}円** (予算: {budget:,}円)")
st.progress(min(current_expense / budget, 1.0))
st.divider()

# ==========================================
# 💸 経費入力
# ==========================================
if menu == "💸 経費入力":
    st.subheader(f"💸 {selected_class} 経費")
    with st.form("exp"):
        c1, c2 = st.columns(2)
        d = c1.date_input("日付")
        p = c2.text_input("担当")
        i = st.text_input("品名")
        a = st.number_input("金額", min_value=0, step=1)
        if st.form_submit_button("登録"):
            add_row_to_sheet(selected_class, [d.strftime("%Y/%m/%d"), "🔴 経費", p, i, a])

# ==========================================
# ✅ ToDo
# ==========================================
elif menu == "✅ ToDo":
    st.subheader(f"✅ {selected_class} ToDo")
    with st.expander("➕ タスク追加", expanded=True):
        with st.form("todo"):
            t = st.text_input("内容")
            p = st.text_input("担当")
            if st.form_submit_button("書き込む"):
                add_row_to_sheet("TODO", [selected_class, datetime.now().strftime("%Y/%m/%d"), t, p, "未完了"])

    st.divider()
    # ToDo読み込みとフィルタリング
    all_todos = get_raw_data("TODO")
    if len(all_todos) > 1:
        # 自分のクラス かつ 未完了 のもの
        # データ構造: [Class, Date, Task, Person, Status]
        active = [r + [idx+1] for idx, r in enumerate(all_todos) if idx > 0 and r[0] == selected_class and "未完了" in r[4]]
        
        if active:
            st.caption("チェックして「完了」ボタンを押してください")
            updates = []
            for task in active:
                # task[2]=内容, task[3]=担当, task[-1]=行番号
                if st.checkbox(f"{task[2]} ({task[3]})", key=f"chk_{task[-1]}"):
                    updates.append(task[-1])
            
            if updates and st.button("完了にする"):
                gc = get_gc()
                sh = gc.open(SPREADSHEET_NAME).worksheet("TODO")
                for ridx in updates: sh.update_cell(ridx, 5, "完了")
                get_raw_data.clear(); st.success("更新！"); time.sleep(0.3); st.rerun()
        else: st.info("タスクなし")
    else: st.info("タスクなし")

# ==========================================
# 💰 レジ
# ==========================================
elif menu == "💰 レジ":
    st.subheader(f"💰 {selected_class} レジ")
    c_menu, c_receipt = st.columns([1.5, 1])

    # メニュー読み込み
    menu_rows = get_raw_data("MENU")
    # フィルタリング: [Class, Name, Price]
    my_menu = [r for r in menu_rows[1:] if r[0] == selected_class]

    with c_menu:
        if not my_menu: st.info("メニュー未登録")
        cols = st.columns(3)
        for i, item in enumerate(my_menu):
            name, price = item[1], int(item[2])
            if cols[i % 3].button(f"{name}\n¥{price}", key=f"btn_{i}", use_container_width=True):
                st.session_state["cart"].append({"n": name, "p": price})
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
            
            # クイックボタン生成
            b_cols = st.columns(3)
            for i, amt in enumerate([1000, 500, 100, 50, 10, 0]):
                if b_cols[i % 3].button(f"+{amt}" if amt else "C", use_container_width=True):
                    st.session_state["received_amount"] = 0 if amt == 0 else st.session_state["received_amount"] + amt
                    st.rerun()

            change = st.session_state["received_amount"] - total
            if st.session_state["received_amount"] > 0:
                if change >= 0: st.success(f"お釣り: ¥{change:,}")
                else: st.error(f"不足: ¥{abs(change):,}")

        if st.button("会計確定", type="primary", use_container_width=True):
            if total > 0:
                items_str = ",".join([x['n'] for x in st.session_state["cart"]])
                add_row_to_sheet(selected_class, [datetime.now().strftime("%Y/%m/%d"), "🔵 売上", "レジ", items_str, total])
                st.session_state["cart"] = []; st.session_state["received_amount"] = 0
        
        if st.button("クリア"):
            st.session_state["cart"] = []; st.session_state["received_amount"] = 0; st.rerun()

# ==========================================
# 🍔 メニュー登録
# ==========================================
elif menu == "🍔 メニュー":
    st.subheader("🍔 メニュー登録")
    with st.form("add_m"):
        c1, c2 = st.columns(2)
        n = c1.text_input("商品名")
        p = c2.number_input("単価", min_value=0, step=10)
        if st.form_submit_button("追加"):
            add_row_to_sheet("MENU", [selected_class, n, p])

    st.divider()
    menu_rows = get_raw_data("MENU")
    # 削除機能（行番号を保持してループ）
    for idx, row in enumerate(menu_rows):
        if idx > 0 and row[0] == selected_class:
            c1, c2 = st.columns([3, 1])
            c1.write(f"・{row[1]} : ¥{row[2]}")
            if c2.button("削除", key=f"del_{idx}"):
                gc = get_gc()
                sh = gc.open(SPREADSHEET_NAME).worksheet("MENU")
                # スプレッドシートの行番号はidx+1
                sh.delete_rows(idx + 1)
                get_raw_data.clear(); st.success("削除！"); time.sleep(0.3); st.rerun()

# ==========================================
# ⚙️ 予算設定
# ==========================================
elif menu == "⚙️ 予算":
    st.subheader("⚙️ 予算設定")
    with st.form("bud"):
        new_b = st.number_input("新予算", value=budget, step=1000)
        if st.form_submit_button("更新"):
            update_budget(selected_class, new_b)