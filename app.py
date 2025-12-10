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

# 💰 クラスごとの予算（円）
DEFAULT_BUDGET = 30000 

# 🔐 クラスごとのパスワード設定
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

# セッション状態の初期化
if "is_logged_in" not in st.session_state:
    st.session_state["is_logged_in"] = False
if "logged_class" not in st.session_state:
    st.session_state["logged_class"] = None
# ★重要：レジの「買い物かご」を作る
if "cart" not in st.session_state:
    st.session_state["cart"] = []

# --- 共通接続関数 ---
def connect_to_tab(tab_name):
    if "service_account_json" not in st.secrets:
        st.error("Secretsの設定がありません")
        return None
    
    key_dict = json.loads(st.secrets["service_account_json"])
    gc = gspread.service_account_from_dict(key_dict)
    
    try:
        wb = gc.open(SPREADSHEET_NAME)
        return wb.worksheet(tab_name)
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"エラー: 「{tab_name}」というタブが見つかりません。")
        return None
    except Exception as e:
        st.error(f"接続エラー: {e}")
        return None

# ==========================================
# 🏫 サイドバー & ログイン
# ==========================================
st.sidebar.title("🏫 クラスログイン")

class_list = ["21HR", "22HR", "23HR", "24HR", "25HR", "26HR", "27HR", "28HR", "実行委員"]
selected_class = st.sidebar.selectbox("クラスを選んでください", class_list)

# 自動ログアウト
if st.session_state["logged_class"] != selected_class:
    st.session_state["is_logged_in"] = False
    st.session_state["logged_class"] = selected_class
    st.session_state["cart"] = [] # カートも空にする
    st.rerun()

st.sidebar.divider()

# --- ログイン画面 ---
if not st.session_state["is_logged_in"]:
    st.title(f"🔒 {selected_class} ログイン")
    input_pass = st.text_input("パスワード", type="password")
    login_btn = st.button("ログイン")
    
    if login_btn:
        input_pass_clean = input_pass.strip()
        correct_pass = CLASS_PASSWORDS.get(selected_class)
        
        if input_pass_clean == correct_pass:
            st.session_state["is_logged_in"] = True
            st.success("ログイン成功！")
            time.sleep(0.5)
            st.rerun()
        else:
            st.error("パスワードが違います")
    st.stop()

# ==========================================
# 🎉 ログイン後のメイン画面
# ==========================================

# --- ログアウトボタン ---
if st.sidebar.button("ログアウト"):
    st.session_state["is_logged_in"] = False
    st.session_state["cart"] = []
    st.rerun()

# --- メニュー選択 ---
# 分析を削除し、レジと経費を分けました
menu = st.sidebar.radio(
    "メニュー",
    ["💰 レジ（売上登録）", "💸 経費入力（買い出し）", "🍔 商品メニュー登録", "✅ ToDo掲示板"],
)

st.sidebar.success(f"ログイン中: **{selected_class}**")


# ==========================================
# ⚡️ 予算バー（常に表示）
# ==========================================
sheet = connect_to_tab(selected_class)
current_expense = 0
if sheet:
    try:
        all_data = sheet.get_all_records()
        df = pd.DataFrame(all_data)
        if not df.empty and "金額" in df.columns:
            # 経費だけを合計（売上は引かない）
            if "種別" in df.columns:
                expense_df = df[df["種別"].isin(["経費", "記録"])]
                current_expense = expense_df["金額"].sum()
            else:
                current_expense = df["金額"].sum()
    except:
        pass

# 予算表示
remaining = DEFAULT_BUDGET - current_expense
progress_val = min(current_expense / DEFAULT_BUDGET, 1.0)
st.write(f"📊 **予算状況** (予算: {DEFAULT_BUDGET:,}円)")
st.progress(progress_val)
if remaining < 0:
    st.error(f"⚠️ **{abs(remaining):,} 円の赤字です！**")
else:
    st.caption(f"使用済み: {current_expense:,}円 / **残り: {remaining:,}円**")

st.divider()


# ==========================================
# 💰 メニュー1：本格レジ（売上登録）
# ==========================================
if menu == "💰 レジ（売上登録）":
    st.title(f"💰 {selected_class} POSレジ")
    
    # 画面を左右に分割（左：商品ボタン、右：レシート）
    col_menu, col_receipt = st.columns([2, 1])

    # --- 左側：商品ボタンエリア ---
    with col_menu:
        st.subheader("商品を選択")
        
        # MENUシートから商品を読み込む
        menu_sheet = connect_to_tab("MENU")
        menu_items = []
        if menu_sheet:
            try:
                menu_data = menu_sheet.get_all_records()
                menu_df = pd.DataFrame(menu_data)
                if not menu_df.empty and "クラス" in menu_df.columns:
                    my_menu = menu_df[menu_df["クラス"] == selected_class]
                    menu_items = my_menu.to_dict("records")
            except:
                st.warning("メニュー読み込みエラー")

        if not menu_items:
            st.info("サイドバーの「🍔 商品メニュー登録」から商品を登録してください")
        else:
            # ボタンをグリッド状に配置
            # 3列で表示
            cols = st.columns(3)
            for i, item in enumerate(menu_items):
                name = item["商品名"]
                price = item["単価"]
                
                # ボタン配置
                with cols[i % 3]:
                    # ボタンを押したら「カート」に追加
                    if st.button(f"{name}\n¥{price}", key=f"btn_{i}", use_container_width=True):
                        st.session_state["cart"].append({"name": name, "price": price})
                        st.rerun() # 画面更新してレシートに反映

    # --- 右側：レシートエリア ---
    with col_receipt:
        st.subheader("🧾 お会計リスト")
        
        # カートの中身を表示
        total_price = 0
        if len(st.session_state["cart"]) > 0:
            for idx, cart_item in enumerate(st.session_state["cart"]):
                st.text(f"・{cart_item['name']} : ¥{cart_item['price']}")
                total_price += cart_item['price']
            
            st.divider()
            st.metric("合計金額", f"¥{total_price:,}")
            
            # お会計ボタン
            checkout_btn = st.button("お会計（確定）", type="primary", use_container_width=True)
            
            # クリアボタン
            if st.button("リセット（取り消し）", use_container_width=True):
                st.session_state["cart"] = []
                st.rerun()

            # --- 会計処理 ---
            if checkout_btn:
                sheet = connect_to_tab(selected_class)
                if sheet:
                    # まとめて書き込むデータを作る
                    rows_to_add = []
                    d_str = datetime.now().strftime("%Y/%m/%d")
                    
                    for cart_item in st.session_state["cart"]:
                        # 日付, 種別, 担当者, 内容, 金額
                        rows_to_add.append([d_str, "売上", "レジ", cart_item["name"], cart_item["price"]])
                    
                    # スプレッドシートに追加
                    sheet.append_rows(rows_to_add)
                    
                    st.session_state["cart"] = [] # カートを空にする
                    st.success("✅ お会計完了！ありがとうございました！")
                    st.balloons()
                    time.sleep(2)
                    st.rerun()
        else:
            st.info("左の商品を選んでください")
            st.metric("合計金額", "¥0")


# ==========================================
# 💸 メニュー2：経費入力（買い出し）
# ==========================================
elif menu == "💸 経費入力（買い出し）":
    st.title(f"💸 {selected_class} 経費入力")
    st.caption("買い出しのレシートを見ながら入力してください")
    
    with st.form("expense_form"):
        date = st.date_input("購入日", datetime.now())
        person = st.text_input("担当者（誰が払った？）")
        item = st.text_input("品名（なにを買った？）")
        amount = st.number_input("金額（円）", min_value=0, step=1)
        
        submitted = st.form_submit_button("経費を登録")

        if submitted:
            sheet = connect_to_tab(selected_class)
            if sheet:
                d_str = date.strftime("%Y/%m/%d")
                # 日付, 種別, 担当者, 内容, 金額
                sheet.append_row([d_str, "経費", person, item, amount])
                st.success(f"✅ {selected_class}のシートに保存しました！")
                st.rerun() # 予算バー更新のため


# ==========================================
# 🍔 メニュー3：商品メニュー登録
# ==========================================
elif menu == "🍔 商品メニュー登録":
    st.title(f"🍔 {selected_class} 商品登録")
    st.caption("ここで登録した商品がレジに表示されます")

    with st.form("add_menu_form"):
        col1, col2 = st.columns(2)
        new_item = col1.text_input("商品名（例：焼きそば）")
        new_price = col2.number_input("単価（円）", min_value=0, step=10)
        add_btn = st.form_submit_button("メニューに追加")

        if add_btn and new_item:
            menu_sheet = connect_to_tab("MENU")
            if menu_sheet:
                menu_sheet.append_row([selected_class, new_item, new_price])
                st.success(f"✅ 「{new_item}」を追加しました")
                time.sleep(1)
                st.rerun()

    st.divider()
    st.subheader("📋 現在のメニュー")
    
    menu_sheet = connect_to_tab("MENU")
    if menu_sheet:
        try:
            data = menu_sheet.get_all_records()
            df = pd.DataFrame(data)
            if not df.empty and "クラス" in df.columns:
                my_menu = df[df["クラス"] == selected_class]
                st.table(my_menu[["商品名", "単価"]])
        except:
            st.error("MENUシート読込エラー")


# ==========================================
# ✅ メニュー4：ToDo掲示板
# ==========================================
elif menu == "✅ ToDo掲示板":
    st.title(f"✅ {selected_class} ToDo掲示板")
    target_tab = "TODO"

    with st.expander("➕ 新しい書き込みをする", expanded=True):
        with st.form("todo_add"):
            col1, col2 = st.columns([3, 1])
            task = col1.text_input("内容")
            person = col2.text_input("担当者")
            add_btn = st.form_submit_button("書き込む")
            
            if add_btn:
                sheet = connect_to_tab(target_tab)
                if sheet:
                    d_str = datetime.now().strftime("%Y/%m/%d")
                    sheet.append_row([selected_class, d_str, task, person, "未完了"])
                    st.success("書き込みました！")

    st.divider()
    
    sheet = connect_to_tab(target_tab)
    if sheet:
        try:
            data = sheet.get_all_records()
            df = pd.DataFrame(data)
            if not df.empty and "クラス" in df.columns:
                my_todos = df[df["クラス"] == selected_class]
                if not my_todos.empty:
                    my_todos = my_todos.iloc[::-1]
                    st.table(my_todos[["登録日", "やるべきこと", "担当者", "状態"]])
                else:
                    st.info("書き込みはありません")
        except:
            pass