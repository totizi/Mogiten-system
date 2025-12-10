import streamlit as st
from datetime import datetime
import json
import gspread
import pandas as pd

# ==========================================
# 👇 スプレッドシートのファイル名
SPREADSHEET_NAME = "模擬店データベース"
# ==========================================

st.set_page_config(page_title="文化祭統合システム", layout="wide")

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
# 📱 サイドバー（設定・メニュー）
# ==========================================
st.sidebar.title("🏫 クラス選択")

# クラスリスト
class_list = ["21HR", "22HR", "23HR", "24HR", "25HR", "26HR", "27HR", "28HR", "実行委員"]
selected_class = st.sidebar.selectbox("自分のクラスを選んでください", class_list)

st.sidebar.divider()

# メニュー選択（シンプルに2つ＋確認）
menu = st.sidebar.radio(
    "メニュー",
    ["💰 会計記録（入力）", "✅ ToDo掲示板", "📊 履歴確認"],
    captions=["レシート入力はこちら", "連絡事項はこちら", "データを見る"]
)

st.sidebar.info(f"操作中: **{selected_class}**")


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
        
        # 備考（メモ）もあると便利かも
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
    st.caption("クラスへの連絡、買うものリスト、タスクなどを共有しよう！")

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
                    # 最新が上に来るように逆順にする
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
        sheet = connect_to_tab(selected_class)
        if sheet:
            try:
                data = sheet.get_all_records()
                df = pd.DataFrame(data)

                if not df.empty:
                    # 金額の合計を計算
                    total_amount = df["金額"].sum()

                    # 合計を大きく表示
                    st.metric("💸 現在の合計使用金額", f"{total_amount:,} 円")
                    
                    st.divider()
                    st.write("📋 履歴一覧")
                    st.dataframe(df)
                else:
                    st.warning("まだ記録がありません")
            except Exception as e:
                st.error(f"読み込みエラー: {e}")