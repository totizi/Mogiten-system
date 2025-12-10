import streamlit as st
from datetime import datetime
import json
import gspread
import pandas as pd
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

st.set_page_config(page_title="文化祭レジシステム", layout="wide")

# セッション初期化
default_state = {
    "is_logged_in": False, "logged_class": None, 
    "cart": [], "received_amount": 0
}
for key, val in default_state.items():
    if key not in st.session_state: st.session_state[key] = val

# ==========================================
# 🛠️ 共通関数（バックエンド処理）
# ==========================================
def get_worksheet(tab_name):
    """シート接続用"""
    if "service_account_json" not in st.secrets:
        st.error("Secrets設定エラー"); return None
    try:
        creds = json.loads(st.secrets["service_account_json"])
        gc = gspread.service_account_from_dict(creds)
        return gc.open(SPREADSHEET_NAME).worksheet(tab_name)
    except: return None

@st.cache_data(ttl=600)
def load_data(tab_name):
    """データ読み込み＆キャッシュ"""
    sheet = get_worksheet(tab_name)
    if not sheet: return []
    try:
        return sheet.get_all_records()
    except: return []

def clear_cache():
    """キャッシュ削除"""
    load_data.clear()
    get_class_budget.clear() # 予算のキャッシュも消す

def add_row_to_sheet(tab_name, row_data, success_msg="保存しました"):
    """データ追加共通処理"""
    sheet = get_worksheet(tab_name)
    if sheet:
        sheet.append_row(row_data)
        clear_cache()
        st.success(f"✅ {success_msg}")
        time.sleep(1)
        st.rerun()

# --- 💰 予算管理用の新関数 ---
@st.cache_data(ttl=600)
def get_class_budget(class_name):
    """スプレッドシートから予算を読み込む（なければ30000を返す）"""
    sheet = get_worksheet("BUDGET")
    if not sheet: return 30000
    try:
        records = sheet.get_all_records()
        df = pd.DataFrame(records)
        if not df.empty and "クラス" in df.columns:
            # そのクラスの行を探す
            row = df[df["クラス"] == class_name]
            if not row.empty:
                return int(row.iloc[0]["予算"])
    except: pass
    return 30000 # デフォルト値

def update_class_budget(class_name, new_budget):
    """予算を更新する（あれば上書き、なければ追加）"""
    sheet = get_worksheet("BUDGET")
    if not sheet: return
    try:
        cell = sheet.find(class_name)
        if cell:
            # 既にある場合は、その隣のセル（B列）を更新
            sheet.update_cell(cell.row, 2, new_budget)
        else:
            # ない場合は新規追加
            sheet.append_row([class_name, new_budget])
        
        clear_cache() # キャッシュを消して即反映
        st.success(f"予算を {new_budget:,} 円に設定しました！")
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.error(f"保存エラー: {e}")

# ==========================================
# 🏫 サイドバー & ログイン
# ==========================================
st.sidebar.title("🏫 クラスログイン")
selected_class = st.sidebar.selectbox("クラス選択", list(CLASS_PASSWORDS.keys()))

# クラス切り替え時のリセット処理
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
            st.success("ログイン成功！"); time.sleep(0.5); st.rerun()
        else:
            st.error("パスワードが違います")
    st.stop()

# ==========================================
# 🎉 メイン画面（ログイン後）
# ==========================================
if st.sidebar.button("ログアウト"):
    st.session_state.update({"is_logged_in": False, "cart": [], "received_amount": 0})
    st.rerun()

# ★メニューに「予算設定」を追加
menu = st.sidebar.radio("メニュー", ["💸 経費入力（買い出し）", "✅ ToDo掲示板", "💰 レジ（売上登録）", "🍔 商品メニュー登録", "⚙️ 予算設定"])
st.sidebar.success(f"ログイン中: **{selected_class}**")

# --- 📊 予算バー表示（DBから取得） ---
budget = get_class_budget(selected_class) # ここが変わりました！

records = load_data(selected_class)
df = pd.DataFrame(records)
current_expense = 0
if not df.empty and "金額" in df.columns:
    if "種別" in df.columns:
        current_expense = df[df["種別"].astype(str).str.contains("経費")]["金額"].sum()
    else:
        current_expense = df["金額"].sum()

remaining = budget - current_expense
st.write(f"📊 **予算状況** (予算: {budget:,}円)")
st.progress(min(current_expense / budget, 1.0))
if remaining < 0: st.error(f"⚠️ **{abs(remaining):,} 円の赤字です！**")
else: st.caption(f"使用済み: {current_expense:,}円 / **残り: {remaining:,}円**")
st.divider()

# ==========================================
# 💸 経費入力
# ==========================================
if menu == "💸 経費入力（買い出し）":
    st.title(f"💸 {selected_class} 経費入力")
    with st.form("exp"):
        d, p, i, a = st.date_input("日付"), st.text_input("担当"), st.text_input("品名"), st.number_input("金額", min_value=0, step=1)
        if st.form_submit_button("登録"):
            add_row_to_sheet(selected_class, [d.strftime("%Y/%m/%d"), "🔴 経費", p, i, a])

# ==========================================
# ✅ ToDo掲示板
# ==========================================
elif menu == "✅ ToDo掲示板":
    st.title(f"✅ {selected_class} ToDo")
    with st.expander("➕ タスク追加", expanded=True):
        with st.form("todo"):
            t, p = st.text_input("内容"), st.text_input("担当")
            if st.form_submit_button("書き込む"):
                add_row_to_sheet("TODO", [selected_class, datetime.now().strftime("%Y/%m/%d"), t, p, "未完了"], "書き込みました")
    
    st.divider()
    all_todos = load_data("TODO")
    if all_todos:
        my_todos = [t for t in all_todos if t.get("クラス") == selected_class]
        active = [t for t in my_todos if "未完了" in t.get("状態", "")]
        done = [t for t in my_todos if "未完了" not in t.get("状態", "")]

        st.subheader("🔥 未完了タスク")
        if active:
            updates = []
            sheet_todo = get_worksheet("TODO")
            all_values = sheet_todo.get_all_values()
            
            for task in active:
                row_idx = -1
                for idx, row in enumerate(all_values):
                    if len(row) > 2 and row[0] == selected_class and row[2] == task["やるべきこと"] and "未完了" in row[4]:
                        row_idx = idx + 1
                        break
                
                if row_idx != -1 and st.checkbox(f"**{task['やるべきこと']}** ({task['担当者']})", key=f"chk_{row_idx}"):
                    updates.append(row_idx)

            if updates and st.button("完了にする"):
                for ridx in updates: sheet_todo.update_cell(ridx, 5, "完了")
                clear_cache(); st.success("更新しました"); st.rerun()
        else: st.info("タスクなし")

        with st.expander("✅ 完了済み履歴"):
            for t in reversed(done): st.write(f"・~~{t['やるべきこと']}~~ ({t['担当者']})")

# ==========================================
# 💰 レジ（売上登録）
# ==========================================
elif menu == "💰 レジ（売上登録）":
    st.title(f"💰 {selected_class} レジ")
    c_menu, c_receipt = st.columns([1.5, 1])

    with c_menu:
        st.subheader("🍔 商品選択")
        menu_list = [m for m in load_data("MENU") if m.get("クラス") == selected_class]
        if not menu_list: st.info("メニュー未登録")
        
        cols = st.columns(3)
        for i, item in enumerate(menu_list):
            if cols[i % 3].button(f"{item['商品名']}\n¥{item['単価']}", key=f"btn_{i}", use_container_width=True):
                st.session_state["cart"].append(item)
                st.rerun()

    with c_receipt:
        st.subheader("🧾 会計")
        total = sum([x['単価'] for x in st.session_state["cart"]])
        
        with st.expander("カート詳細", expanded=True):
            if not st.session_state["cart"]: st.write("（空）")
            for x in st.session_state["cart"]: st.text(f"・{x['商品名']} : ¥{x['単価']}")
        
        st.divider()
        st.metric("合計", f"¥{total:,}")

        if total > 0:
            st.write("🔻 **預かり金入力**")
            val = st.number_input("¥", value=st.session_state["received_amount"], step=10, label_visibility="collapsed")
            if val != st.session_state["received_amount"]:
                st.session_state["received_amount"] = val; st.rerun()
            
            amounts = [1000, 500, 100, 50, 10, 0]
            b_cols = st.columns(3)
            for i, amt in enumerate(amounts):
                label = "クリア" if amt == 0 else f"+{amt:,}"
                if b_cols[i % 3].button(label, use_container_width=True):
                    st.session_state["received_amount"] = 0 if amt == 0 else st.session_state["received_amount"] + amt
                    st.rerun()

            change = st.session_state["received_amount"] - total
            if st.session_state["received_amount"] > 0:
                if change >= 0: st.success(f"お釣り: ¥{change:,}")
                else: st.error(f"不足: ¥{abs(change):,}")

        st.divider()
        if st.button("会計確定", type="primary", use_container_width=True):
            if total > 0:
                items_str = ", ".join([x['商品名'] for x in st.session_state["cart"]])
                add_row_to_sheet(selected_class, [datetime.now().strftime("%Y/%m/%d"), "🔵 売上", "レジ", items_str, total], "売上記録完了")
                st.session_state["cart"] = []; st.session_state["received_amount"] = 0
            else: st.warning("商品を選んでください")
        
        if st.button("カートを空にする"):
            st.session_state["cart"] = []; st.session_state["received_amount"] = 0; st.rerun()

# ==========================================
# 🍔 メニュー登録
# ==========================================
elif menu == "🍔 商品メニュー登録":
    st.title(f"🍔 {selected_class} メニュー設定")
    with st.form("add_m"):
        n, p = st.text_input("商品名"), st.number_input("単価", min_value=0, step=10)
        if st.form_submit_button("追加"):
            add_row_to_sheet("MENU", [selected_class, n, p], "追加しました")

    st.divider()
    menu_list = [m for m in load_data("MENU") if m.get("クラス") == selected_class]
    if menu_list:
        for i, item in enumerate(menu_list):
            c1, c2 = st.columns([3, 1])
            c1.write(f"・**{item['商品名']}** : ¥{item['単価']}")
            if c2.button("削除", key=f"del_{i}"):
                sheet = get_worksheet("MENU")
                rows = sheet.get_all_values()
                for idx, row in enumerate(rows):
                    if idx > 0 and row[0] == selected_class and row[1] == item['商品名']:
                        sheet.delete_rows(idx + 1); clear_cache(); st.success("削除しました"); time.sleep(0.5); st.rerun()

# ==========================================
# ⚙️ 予算設定（新機能）
# ==========================================
elif menu == "⚙️ 予算設定":
    st.title(f"⚙️ {selected_class} 予算設定")
    st.caption("クラスの予算を変更できます。")

    # 現在の予算を表示
    current_b = get_class_budget(selected_class)
    
    with st.form("budget_form"):
        new_budget = st.number_input("新しい予算（円）", value=current_b, step=1000)
        if st.form_submit_button("保存する"):
            update_class_budget(selected_class, new_budget)