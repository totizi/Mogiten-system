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

# 🔐 クラスごとのパスワード設定
# 好きな数字や文字に変えてください
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

# セッション状態の初期化（ログイン状態を管理するメモリ）
if "is_logged_in" not in st.session_state:
    st.session_state["is_logged_in"] = False
if "logged_class" not in st.session_state:
    st.session_state["logged_class"] = None

# --- 共通：指定した名前のタブに接続する関数 ---
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
# 📱 サイドバー（クラス選択）
# ==========================================
st.sidebar.title("🏫 クラスログイン")

# クラスリスト
class_list = ["21HR", "22HR", "23HR", "24HR", "25HR", "26HR", "27HR", "28HR", "実行委員"]
selected_class = st.sidebar.selectbox("クラスを選んでください", class_list)

# --- 重要：クラスを変えたら自動でログアウトする処理 ---
if st.session_state["logged_class"] != selected_class:
    st.session_state["is_logged_in"] = False
    st.session_state["logged_class"] = selected_class

st.sidebar.divider()

# ==========================================
# 🔐 ログイン制御（ここが関所！）
# ==========================================

# まだログインしていない場合
if not st.session_state["is_logged_in"]:
    st.title(f"🔒 {selected_class} ログイン")
    st.write("このクラスのデータにアクセスするにはパスワードが必要です。")
    
    # パスワード入力フォーム
    with st.form("login_form"):
        input_pass = st.text_input("パスワードを入力", type="password") # 文字を隠す
        login_btn = st.form_submit_button("ログイン")
        
        if login_btn:
            # パスワードチェック
            correct_pass = CLASS_PASSWORDS.get(selected_class)
            
            if input_pass == correct_pass:
                st.session_state["is_logged_in"] = True
                st.success("ログイン成功！")
                time.sleep(0.5) # ちょっと待ってから
                st.rerun() # 画面を再読み込みして中身を表示
            else:
                st.error("パスワードが違います")
    
    # ログインしていないときはここで処理終了（下を表示しない）
    st.stop()


# ==========================================
# 🎉 ここから下はログイン成功した人だけが見れるエリア
# ==========================================

# ログアウトボタン
if st.sidebar.button("ログアウト"):
    st.session_state["is_logged_in"] = False
    st.rerun()

# メニュー選択
menu = st.sidebar.radio(
    "メニュー",
    ["💰 会計記録（入力）", "✅ ToDo掲示板", "📊 履歴確認"],
    captions=["レシート入力はこちら", "連絡事項はこちら", "データを見る"]
)

st.sidebar.success(f"ログイン中: **{selected_class}**")


# ==========================================
# 💰 メニュー1：会計記録（入力）
# ==========================================
if menu == "💰 会計記録（入力）":
    st.title(f"💰 {selected_class} 会計記録")
    st.caption("買い出しや出費があったら、ここに入力してください。")
    
    with st.form("accounting_form"):
        date = st.date_input("日付", datetime.now())
        person = st.text_input("担当者（誰が使った？）")
        item = st.text_input("内容（なにに使った？）")
        amount = st.number_input("金額（円）", min_value=0, step=1)
        
        submitted = st.form_submit_button("記録する")

        if submitted:
            sheet = connect_to_tab(selected_class)
            if sheet:
                d_str = date.strftime("%Y/%m/%d")
                # 日付, 種別(自動で"記録"), 担当者, 内容, 金額
                sheet.append_row([d_str, "記録", person, item, amount])
                st.success(f"✅ {selected_class}のシートに保存しました！")
                st.balloons()

# ==========================================
# ✅ メニュー2：ToDo掲示板
# ==========================================
elif menu == "✅ ToDo掲示板":
    st.title(f"✅ {selected_class} ToDo掲示板")
    target_tab = "TODO"

    # --- 新規追加フォーム ---
    with st.expander("➕ 新しい書き込みをする", expanded=True):
        with st.form("todo_add"):
            col1, col2 = st.columns([3, 1])
            task = col1.text_input("内容（やるべきこと・連絡）")
            person = col2.text_input("担当者（任意）")
            add_btn = st.form_submit_button("掲示板に書き込む")
            
            if add_btn:
                sheet = connect_to_tab(target_tab)
                if sheet:
                    d_str = datetime.now().strftime("%Y/%m/%d")
                    # クラス, 日付, やること, 担当者, 状態
                    sheet.append_row([selected_class, d_str, task, person, "未完了"])
                    st.success("書き込みました！")

    st.divider()

    # --- 掲示板表示 ---
    st.subheader(f"📋 {selected_class} の掲示板")
    
    sheet = connect_to_tab(target_tab)
    if sheet:
        try:
            data = sheet.get_all_records()
            df = pd.DataFrame(data)
            
            if not df.empty and "クラス" in df.columns:
                # 自分のクラスの書き込みだけ抽出
                my_todos = df[df["クラス"] == selected_class]
                
                if not my_todos.empty:
                    my_todos = my_todos.iloc[::-1]
                    st.table(my_todos[["登録日", "やるべきこと", "担当者", "状態"]])
                else:
                    st.info("まだ書き込みはありません。")
            else:
                st.info("データがありません。")
        except Exception as e:
            st.warning("読み込みエラー（スプレッドシートの1行目を確認してください）")

# ==========================================
# 📊 メニュー3：履歴確認
# ==========================================
elif menu == "📊 履歴確認":
    st.title(f"📊 {selected_class} 利用履歴")
    
    if st.button("最新データを読み込む"):