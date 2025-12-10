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
# ここを変えればクラスごとに予算を変えられます
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
st.set_page_config(page_title="文化祭統合システム", layout="wide")

if "is_logged_in" not in st.session_state:
    st.session_state["is_logged_in"] = False
if "logged_class" not in st.session_state:
    st.session_state["logged_class"] = None

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
    st.rerun()

st.sidebar.divider()

# --- ログイン画面 ---
if not st.session_state["is_logged_in"]:
    st.title(f"🔒 {selected_class} ログイン")
    st.write("パスワードを入力してください")
    
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
    st.rerun()

# --- メニュー選択 ---
menu = st.sidebar.radio(
    "メニュー",
    ["💰 レジ・会計記録", "🍔 商品メニュー登録", "✅ ToDo掲示板", "📊 履歴・分析"],
)

st.sidebar.success(f"ログイン中: **{selected_class}**")


# ==========================================
# ⚡️ 新機能：予算バーの表示（常に上に表示）
# ==========================================
sheet = connect_to_tab(selected_class)
current_expense = 0
if sheet:
    try:
        # 全データを取得して「記録(経費)」の合計を出す
        all_data = sheet.get_all_records()
        df = pd.DataFrame(all_data)
        if not df.empty and "金額" in df.columns:
            # 種別が「記録」または「経費」のものを合計
            # (以前のデータ形式に対応するため、種別カラムがない場合も考慮)
            if "種別" in df.columns:
                expense_df = df[df["種別"].isin(["経費", "記録"])]
                current_expense = expense_df["金額"].sum()
            else:
                # 種別がない古いデータなら全額を経費とみなす（仮）
                current_expense = df["金額"].sum()
    except:
        pass

# 予算計算
remaining = DEFAULT_BUDGET - current_expense
progress_val = min(current_expense / DEFAULT_BUDGET, 1.0)

# バーを表示
st.write(f"📊 **予算状況** (予算: {DEFAULT_BUDGET:,}円)")
st.progress(progress_val)
if remaining < 0:
    st.error(f"⚠️ **{abs(remaining):,} 円の赤字です！**")
else:
    st.caption(f"使用済み: {current_expense:,}円 / **残り: {remaining:,}円**")

st.divider()


# ==========================================
# 💰 メニュー1：レジ・会計記録
# ==========================================
if menu == "💰 レジ・会計記録":
    st.title(f"💰 {selected_class} レジ・会計")
    
    # タブで「レジモード」と「手入力」を分ける
    tab1, tab2 = st.tabs(["⚡️ カンタン売上レジ", "📝 手動入力 (経費など)"])

    # --- ⚡️ レジモード ---
    with tab1:
        st.header("⚡️ 売上登録")
        st.caption("ボタンを押すだけで売上が登録されます")

        # MENUシートから商品を読み込む
        menu_sheet = connect_to_tab("MENU")
        menu_items = []
        if menu_sheet:
            try:
                menu_data = menu_sheet.get_all_records()
                menu_df = pd.DataFrame(menu_data)
                if not menu_df.empty and "クラス" in menu_df.columns:
                    # 自分のクラスの商品だけ抽出
                    my_menu = menu_df[menu_df["クラス"] == selected_class]
                    menu_items = my_menu.to_dict("records")
            except:
                st.warning("メニューの読み込みに失敗しました")

        if not menu_items:
            st.info("まだ商品が登録されていません。サイドバーの「🍔 商品メニュー登録」から登録してください。")
        else:
            # 商品ボタンを並べる
            cols = st.columns(3) # 3列で表示
            for i, item in enumerate(menu_items):
                name = item["商品名"]
                price = item["単価"]
                
                # ボタンを表示（列を順番に使う）
                with cols[i % 3]:
                    # ボタンを押したら即登録
                    if st.button(f"{name}\n¥{price}", key=f"btn_{i}", use_container_width=True):
                        sheet = connect_to_tab(selected_class)
                        if sheet:
                            d_str = datetime.now().strftime("%Y/%m/%d")
                            # 日付, 種別, 担当者, 内容, 金額
                            sheet.append_row([d_str, "売上", "レジ", name, price])
                            st.success(f"✅ {name} (¥{price}) を売上登録しました！")
                            time.sleep(1) # 少し待って
                            st.rerun() # 予算バーなどを更新

    # --- 📝 手動入力モード ---
    with tab2:
        st.header("📝 経費・その他の入力")
        st.caption("買い出しのレシート入力などはここから")
        
        with st.form("manual_form"):
            date = st.date_input("日付", datetime.now())
            # 種別選択
            type_option = st.selectbox("種別", ["経費", "売上"])
            person = st.text_input("担当者")
            item = st.text_input("内容")
            amount = st.number_input("金額（円）", min_value=0, step=1)
            
            submitted = st.form_submit_button("記録する")

            if submitted:
                sheet = connect_to_tab(selected_class)
                if sheet:
                    d_str = date.strftime("%Y/%m/%d")
                    sheet.append_row([d_str, type_option, person, item, amount])
                    st.success(f"✅ 保存しました！")
                    st.rerun()

# ==========================================
# 🍔 メニュー2：商品メニュー登録
# ==========================================
elif menu == "🍔 商品メニュー登録":
    st.title(f"🍔 {selected_class} 商品メニュー設定")
    st.caption("レジに表示するボタン（商品）を作ります")

    # 新規登録フォーム
    with st.form("add_menu_form"):
        col1, col2 = st.columns(2)
        new_item = col1.text_input("商品名（例：焼きそば）")
        new_price = col2.number_input("単価（円）", min_value=0, step=10)
        add_btn = st.form_submit_button("メニューに追加")

        if add_btn and new_item:
            menu_sheet = connect_to_tab("MENU")
            if menu_sheet:
                # クラス, 商品名, 単価
                menu_sheet.append_row([selected_class, new_item, new_price])
                st.success(f"✅ 「{new_item}」を追加しました")
                time.sleep(1)
                st.rerun()

    st.divider()
    st.subheader("📋 現在のメニュー")
    
    # 一覧表示
    menu_sheet = connect_to_tab("MENU")
    if menu_sheet:
        try:
            data = menu_sheet.get_all_records()
            df = pd.DataFrame(data)
            if not df.empty and "クラス" in df.columns:
                my_menu = df[df["クラス"] == selected_class]
                if not my_menu.empty:
                    st.table(my_menu[["商品名", "単価"]])
                    st.caption("※削除したい場合は、スプレッドシートの「MENU」タブから直接行を消してください。")
                else:
                    st.info("登録済みメニューはありません")
        except:
            st.error("MENUシートの読み込みエラー（1行目の見出しを確認してください）")

# ==========================================
# ✅ メニュー3：ToDo掲示板
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

# ==========================================
# 📊 メニュー4：履歴・分析
# ==========================================
elif menu == "📊 履歴・分析":
    st.title(f"📊 {selected_class} 経営レポート")
    
    if st.button("最新データを計算"):
        sheet = connect_to_tab(selected_class)
        if sheet:
            try:
                data = sheet.get_all_records()
                df = pd.DataFrame(data)

                if not df.empty and "種別" in df.columns:
                    # 経費の合計
                    exp_df = df[df["種別"].isin(["経費", "記録"])]
                    total_exp = exp_df["金額"].sum()

                    # 売上の合計
                    sales_df = df[df["種別"] == "売上"]
                    total_sales = sales_df["金額"].sum()

                    # 利益
                    profit = total_sales - total_exp

                    col1, col2, col3 = st.columns(3)
                    col1.metric("総売上", f"{total_sales:,} 円")
                    col2.metric("総経費", f"{total_exp:,} 円")
                    col3.metric("利益", f"{profit:,} 円", delta=profit)
                    
                    st.divider()
                    st.write("📋 全データ履歴")
                    st.dataframe(df)
                else:
                    st.warning("データがありません")
            except Exception as e:
                st.error(f"エラー: {e}")