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
# ⚙️ アプリ初期設定
# ==========================================
st.set_page_config(page_title="文化祭レジシステム", layout="wide")

if "is_logged_in" not in st.session_state:
    st.session_state["is_logged_in"] = False
if "logged_class" not in st.session_state:
    st.session_state["logged_class"] = None
if "cart" not in st.session_state:
    st.session_state["cart"] = []

# --- 接続関数（ここも少し工夫） ---
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

# --- ⚡️【重要】データをキャッシュする関数（通信節約） ---
# ttl=600 は「600秒間（10分）はデータを覚えておく」という意味
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

# 予算計算用データは30秒に1回だけ更新（ttl=30）
@st.cache_data(ttl=30)
def load_expense_total(class_name):
    sheet = connect_to_tab(class_name)
    if not sheet: return 0
    try:
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        if not df.empty and "金額" in df.columns:
            if "種別" in df.columns:
                # 経費と記録だけを合計
                expense_df = df[df["種別"].isin(["経費", "記録"])]
                return int(expense_df["金額"].sum())
            else:
                return int(df["金額"].sum())
    except:
        pass
    return 0

# キャッシュを強制的にクリアする関数（書き込み直後用）
def clear_cache():
    load_expense_total.clear()
    load_menu_data.clear()

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
    st.rerun()

menu = st.sidebar.radio(
    "メニュー",
    ["💰 レジ（売上登録）", "💸 経費入力（買い出し）", "🍔 商品メニュー登録", "✅ ToDo掲示板"],
)
st.sidebar.success(f"ログイン中: **{selected_class}**")

# --- ⚡️ 予算バー（キャッシュ利用版） ---
current_expense = load_expense_total(selected_class)
remaining = DEFAULT_BUDGET - current_expense
progress_val = min(current_expense / DEFAULT_BUDGET, 1.0)

st.write(f"📊 **予算状況** (予算: {DEFAULT_BUDGET:,}円)")
st.progress(progress_val)
if remaining < 0:
    st.error(f"⚠️ **{abs(remaining):,} 円の赤字です！**")
else:
    st.caption(f"使用済み: {current_expense:,}円 / **残り: {remaining:,}円** (※更新は30秒毎)")
st.divider()

# ==========================================
# 💰 レジ（売上登録）
# ==========================================
if menu == "💰 レジ（売上登録）":
    st.title(f"💰 {selected_class} POSレジ")
    col_menu, col_receipt = st.columns([2, 1])

    with col_menu:
        st.subheader("商品を選択")
        # ★キャッシュを使って読み込むので高速＆エラーなし！
        menu_items = load_menu_data(selected_class)

        if not menu_items:
            st.info("サイドバーの「🍔 商品メニュー登録」から商品を登録してください")
        else:
            cols = st.columns(3)
            for i, item in enumerate(menu_items):
                name = item["商品名"]
                price = item["単価"]
                with cols[i % 3]:
                    if st.button(f"{name}\n¥{price}", key=f"btn_{i}", use_container_width=True):
                        st.session_state["cart"].append({"name": name, "price": price})
                        st.rerun()

    with col_receipt:
        st.subheader("🧾 お会計リスト")
        total_price = sum([item['price'] for item in st.session_state["cart"]])
        
        for item in st.session_state["cart"]:
            st.text(f"・{item['name']} : ¥{item['price']}")
        
        st.divider()
        st.metric("合計金額", f"¥{total_price:,}")
        
        checkout_btn = st.button("お会計（確定）", type="primary", use_container_width=True)
        if st.button("リセット", use_container_width=True):
            st.session_state["cart"] = []
            st.rerun()

        if checkout_btn and total_price > 0:
            sheet = connect_to_tab(selected_class)
            if sheet:
                rows = []
                d_str = datetime.now().strftime("%Y/%m/%d")
                for item in st.session_state["cart"]:
                    rows.append([d_str, "売上", "レジ", item["name"], item["price"]])
                
                sheet.append_rows(rows)
                st.session_state["cart"] = []
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
                clear_cache() # 書き込んだのでキャッシュを消して即反映
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
                clear_cache() # メニューが変わったのでキャッシュクリア
                st.success(f"「{new_item}」を追加しました")
                time.sleep(1)
                st.rerun()
    
    st.divider()
    st.subheader("📋 現在のメニュー")
    items = load_menu_data(selected_class) # ここもキャッシュ利用
    if items:
        st.table(pd.DataFrame(items)[["商品名", "単価"]])

# ==========================================
# ✅ ToDo掲示板
# ==========================================
elif menu == "✅ ToDo掲示板":
    st.title(f"✅ {selected_class} ToDo掲示板")
    target_tab = "TODO"

    with st.expander("➕ 新しい書き込み", expanded=True):
        with st.form("todo_add"):
            task = st.text_input("内容")
            person = st.text_input("担当者")
            if st.form_submit_button("書き込む"):
                sheet = connect_to_tab(target_tab)
                if sheet:
                    sheet.append_row([selected_class, datetime.now().strftime("%Y/%m/%d"), task, person, "未完了"])
                    st.success("書き込みました")

    st.divider()
    sheet = connect_to_tab(target_tab)
    if sheet:
        try:
            data = sheet.get_all_records()
            df = pd.DataFrame(data)
            if not df.empty and "クラス" in df.columns:
                my_todos = df[df["クラス"] == selected_class]
                if not my_todos.empty:
                    st.table(my_todos.iloc[::-1][["登録日", "やるべきこと", "担当者", "状態"]])
                else:
                    st.info("書き込みはありません")
        except:
            pass