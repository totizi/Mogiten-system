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
DEFAULT_BUDGET = 30000 

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
# ⚙️ アプリ初期設定 & キャッシュ関数
# ==========================================
st.set_page_config(page_title="文化祭レジシステム", layout="wide")

# セッション変数の初期化
if "is_logged_in" not in st.session_state:
    st.session_state["is_logged_in"] = False
if "logged_class" not in st.session_state:
    st.session_state["logged_class"] = None
if "cart" not in st.session_state:
    st.session_state["cart"] = []
# ★追加：お預かり金額を保存する変数
if "received_amount" not in st.session_state:
    st.session_state["received_amount"] = 0

def get_gspread_client():
    if "service_account_json" not in st.secrets:
        st.error("Secretsの設定がありません")
        return None
    key_dict = json.loads(st.secrets["service_account_json"])
    return gspread.service_account_from_dict(key_dict)

def connect_to_tab(tab_name):
    gc = get_gspread_client()
    try:
        wb = gc.open(SPREADSHEET_NAME)
        return wb.worksheet(tab_name)
    except Exception as e:
        return None

# --- キャッシュ関数 ---
@st.cache_data(ttl=600)
def load_menu_data(class_name):
    sheet = connect_to_tab("MENU")
    if not sheet: return []
    try:
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        if not df.empty and "クラス" in df.columns:
            my_menu = df[df["クラス"] == class_name]
            return my_menu.to_dict("records")
    except:
        pass
    return []

@st.cache_data(ttl=30)
def load_expense_total(class_name):
    sheet = connect_to_tab(class_name)
    if not sheet: return 0
    try:
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        if not df.empty and "金額" in df.columns:
            if "種別" in df.columns:
                expense_df = df[df["種別"].isin(["経費", "記録"])]
                return int(expense_df["金額"].sum())
            else:
                return int(df["金額"].sum())
    except:
        pass
    return 0

def clear_cache():
    load_expense_total.clear()
    load_menu_data.clear()

# --- 🗑️ メニュー削除用 ---
def delete_menu_item(class_name, item_name):
    sheet = connect_to_tab("MENU")
    if not sheet: return False
    try:
        rows = sheet.get_all_values()
        for i, row in enumerate(rows):
            if i == 0: continue
            if row[0] == class_name and row[1] == item_name:
                sheet.delete_rows(i + 1)
                clear_cache()
                return True
    except:
        pass
    return False

# --- ✅ ToDo更新用 ---
def update_todo_status(row_index):
    sheet = connect_to_tab("TODO")
    if not sheet: return False
    try:
        sheet.update_cell(row_index, 5, "完了")
        return True
    except:
        return False

# --- 💰 お金ボタンの処理 ---
def add_money(amount):
    st.session_state["received_amount"] += amount

def clear_money():
    st.session_state["received_amount"] = 0

# ==========================================
# 🏫 サイドバー & ログイン
# ==========================================
st.sidebar.title("🏫 クラスログイン")
class_list = ["21HR", "22HR", "23HR", "24HR", "25HR", "26HR", "27HR", "28HR", "実行委員"]
selected_class = st.sidebar.selectbox("クラスを選んでください", class_list)

if st.session_state["logged_class"] != selected_class:
    st.session_state["is_logged_in"] = False
    st.session_state["logged_class"] = selected_class
    st.session_state["cart"] = []
    st.session_state["received_amount"] = 0
    st.rerun()

st.sidebar.divider()

if not st.session_state["is_logged_in"]:
    st.title(f"🔒 {selected_class} ログイン")
    input_pass = st.text_input("パスワード", type="password")
    if st.button("ログイン"):
        if input_pass.strip() == CLASS_PASSWORDS.get(selected_class):
            st.session_state["is_logged_in"] = True
            st.success("ログイン成功！")
            time.sleep(0.5)
            st.rerun()
        else:
            st.error("パスワードが違います")
    st.stop()

# ==========================================
# 🎉 メイン画面
# ==========================================
if st.sidebar.button("ログアウト"):
    st.session_state["is_logged_in"] = False
    st.session_state["cart"] = []
    st.session_state["received_amount"] = 0
    st.rerun()

menu = st.sidebar.radio(
    "メニュー",
    ["💰 レジ（売上登録）", "💸 経費入力（買い出し）", "🍔 商品メニュー登録", "✅ ToDo掲示板"],
)
st.sidebar.success(f"ログイン中: **{selected_class}**")

# --- ⚡️ 予算バー ---
target_budget = CLASS_BUDGETS = {
    "21HR": 30000, "22HR": 30000, "23HR": 35000, "24HR": 30000,
    "25HR": 30000, "26HR": 30000, "27HR": 30000, "28HR": 30000, "実行委員": 100000
}.get(selected_class, 30000)

current_expense = load_expense_total(selected_class)
remaining = target_budget - current_expense
progress_val = min(current_expense / target_budget, 1.0)
st.write(f"📊 **予算状況** (予算: {target_budget:,}円)")
st.progress(progress_val)
if remaining < 0:
    st.error(f"⚠️ **{abs(remaining):,} 円の赤字です！**")
else:
    st.caption(f"使用済み: {current_expense:,}円 / **残り: {remaining:,}円**")
st.divider()

# ==========================================
# 💰 レジ（高速お釣り計算版）
# ==========================================
if menu == "💰 レジ（売上登録）":
    st.title(f"💰 {selected_class} POSレジ")
    col_menu, col_receipt = st.columns([1.5, 1])

    # --- 左側：メニュー ---
    with col_menu:
        st.subheader("商品を選択")
        menu_items = load_menu_data(selected_class)
        if not menu_items:
            st.info("「🍔 商品メニュー登録」から商品を登録してください")
        else:
            cols = st.columns(3)
            for i, item in enumerate(menu_items):
                name = item["商品名"]
                price = item["単価"]
                with cols[i % 3]:
                    if st.button(f"{name}\n¥{price}", key=f"btn_{i}", use_container_width=True):
                        st.session_state["cart"].append({"name": name, "price": price})
                        st.rerun()

    # --- 右側：レシート & お金入力 ---
    with col_receipt:
        st.subheader("🧾 会計・お釣り")
        total_price = sum([item['price'] for item in st.session_state["cart"]])
        
        # カート内容
        with st.expander("カートの中身を確認", expanded=True):
            if not st.session_state["cart"]:
                st.write("（商品を選んでください）")
            for item in st.session_state["cart"]:
                st.text(f"・{item['name']} : ¥{item['price']}")
        
        st.divider()
        st.metric("合計金額", f"¥{total_price:,}")
        
        # --- ⚡️ お金入力エリア（ここが進化！） ---
        if total_price > 0:
            st.write("🔻 **お預かり金額を入力**")
            
            # 1. 現在の入力額を表示（手入力も可能）
            val = st.number_input("預かり金", value=st.session_state["received_amount"], step=100, label_visibility="collapsed")
            # 手入力された場合の同期
            if val != st.session_state["received_amount"]:
                st.session_state["received_amount"] = val
                st.rerun()

            # 2. 紙幣・硬貨ボタン（押すと即座に加算）
            c1, c2, c3 = st.columns(3)
            c1.button("+1万", on_click=add_money, args=(10000,), use_container_width=True)
            c2.button("+5千", on_click=add_money, args=(5000,), use_container_width=True)
            c3.button("+千円", on_click=add_money, args=(1000,), use_container_width=True)
            
            c4, c5, c6 = st.columns(3)
            c4.button("+500", on_click=add_money, args=(500,), use_container_width=True)
            c5.button("+100", on_click=add_money, args=(100,), use_container_width=True)
            c6.button("クリア", on_click=clear_money, use_container_width=True) # 0にする

            # 3. お釣り計算結果
            change = st.session_state["received_amount"] - total_price
            
            if st.session_state["received_amount"] > 0:
                if change >= 0:
                    st.success(f"お釣り: ¥{change:,}")
                else:
                    st.error(f"あと ¥{abs(change):,} 足りません")
        
        st.divider()
        
        # 確定・リセットボタン
        checkout_btn = st.button("お会計（確定）", type="primary", use_container_width=True)
        if st.button("カートを空にする", use_container_width=True):
            st.session_state["cart"] = []
            st.session_state["received_amount"] = 0
            st.rerun()

        if checkout_btn and total_price > 0:
            if st.session_state["received_amount"] < total_price and st.session_state["received_amount"] != 0:
                st.warning("お金が足りていませんが、登録してよろしいですか？")
            else:
                sheet = connect_to_tab(selected_class)
                if sheet:
                    rows = []
                    d_str = datetime.now().strftime("%Y/%m/%d")
                    for item in st.session_state["cart"]:
                        rows.append([d_str, "売上", "レジ", item["name"], item["price"]])
                    sheet.append_rows(rows)
                    
                    st.session_state["cart"] = []
                    st.session_state["received_amount"] = 0 # お金もリセット
                    st.balloons()
                    st.success("✅ 会計完了！")
                    time.sleep(1)
                    st.rerun()

# ==========================================
# 💸 経費入力
# ==========================================
elif menu == "💸 経費入力（買い出し）":
    st.title(f"💸 {selected_class} 経費入力")
    with st.form("expense_form"):
        date = st.date_input("購入日", datetime.now())
        person = st.text_input("担当者")
        item = st.text_input("品名")
        amount = st.number_input("金額", min_value=0, step=1)
        if st.form_submit_button("登録"):
            sheet = connect_to_tab(selected_class)
            if sheet:
                sheet.append_row([date.strftime("%Y/%m/%d"), "経費", person, item, amount])
                clear_cache()
                st.success("保存しました")
                time.sleep(1)
                st.rerun()

# ==========================================
# 🍔 商品メニュー登録
# ==========================================
elif menu == "🍔 商品メニュー登録":
    st.title(f"🍔 {selected_class} 商品登録")
    with st.form("add_menu"):
        col1, col2 = st.columns(2)
        new_item = col1.text_input("商品名")
        new_price = col2.number_input("単価", min_value=0, step=10)
        if st.form_submit_button("追加"):
            sheet = connect_to_tab("MENU")
            if sheet:
                sheet.append_row([selected_class, new_item, new_price])
                clear_cache()
                st.success(f"「{new_item}」を追加しました")
                time.sleep(1)
                st.rerun()
    st.divider()
    st.subheader("📋 メニュー編集")
    items = load_menu_data(selected_class)
    if items:
        for i, item in enumerate(items):
            col_txt, col_btn = st.columns([3, 1])
            with col_txt:
                st.write(f"・**{item['商品名']}** : ¥{item['単価']}")
            with col_btn:
                if st.button("削除", key=f"del_{i}"):
                    if delete_menu_item(selected_class, item["商品名"]):
                        st.success("削除しました")
                        time.sleep(0.5)
                        st.rerun()
    else:
        st.info("登録されている商品はありません")

# ==========================================
# ✅ ToDo掲示板
# ==========================================
elif menu == "✅ ToDo掲示板":
    st.title(f"✅ {selected_class} ToDo掲示板")
    target_tab = "TODO"
    with st.expander("➕ 新しいタスクを追加", expanded=True):
        with st.form("todo_add"):
            task = st.text_input("内容")
            person = st.text_input("担当者")
            if st.form_submit_button("書き込む"):
                sheet = connect_to_tab(target_tab)
                if sheet:
                    sheet.append_row([selected_class, datetime.now().strftime("%Y/%m/%d"), task, person, "未完了"])
                    st.success("書き込みました")
                    time.sleep(1)
                    st.rerun()
    st.divider()
    sheet = connect_to_tab(target_tab)
    if sheet:
        try:
            all_rows = sheet.get_all_values()
            my_active_tasks = [] 
            my_done_tasks = []
            for i, row in enumerate(all_rows):
                if i == 0: continue 
                if len(row) >= 5 and row[0] == selected_class:
                    task_info = {"row_index": i + 1, "date": row[1], "task": row[2], "person": row[3], "status": row[4]}
                    if "未完了" in row[4]:
                        my_active_tasks.append(task_info)
                    else:
                        my_done_tasks.append(task_info)
            st.subheader("🔥 未完了タスク")
            if my_active_tasks:
                tasks_to_complete = []
                for task in my_active_tasks:
                    is_checked = st.checkbox(f"**{task['task']}** ({task['person']})", key=f"chk_{task['row_index']}")
                    if is_checked: tasks_to_complete.append(task['row_index'])
                if tasks_to_complete and st.button("完了にする"):
                    progress = st.progress(0)
                    for idx, r_idx in enumerate(tasks_to_complete):
                        update_todo_status(r_idx)
                        progress.progress((idx+1)/len(tasks_to_complete))
                    st.success("更新しました")
                    time.sleep(1)
                    st.rerun()
            else:
                st.write("タスクなし")
            st.divider()
            with st.expander("✅ 完了済み"):
                if my_done_tasks:
                    for task in reversed(my_done_tasks):
                        st.write(f"・~~{task['task']}~~")
        except: pass