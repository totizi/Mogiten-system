import streamlit as st
from datetime import datetime
import json
import gspread

# --- 設定エリア ---
SPREADSHEET_NAME = "模擬店データベース"

st.set_page_config(page_title="模擬店会計アプリ", layout="wide")
st.title("💸 模擬店 経費入力システム (完成版)")

# --- スプレッドシート接続関数（最新版） ---
def connect_to_sheet():
    # Secretsから鍵を取り出す
    key_dict = json.loads(st.secrets["service_account_json"])
    
    # 認証（これだけでOK！）
    gc = gspread.service_account_from_dict(key_dict)
    
    # シートを開く
    sh = gc.open(SPREADSHEET_NAME)
    return sh.sheet1

# --- 入力フォーム ---
st.header("📝 新しいレシートを入力")
with st.form("input_form"):
    date = st.date_input("購入日", datetime.now())
    buyer = st.selectbox("購入者", ["自分", "Aさん", "Bさん", "Cさん", "先生"])
    item_name = st.text_input("品名")
    amount = st.number_input("金額（円）", min_value=0, step=1)
    
    submitted = st.form_submit_button("登録する")

    if submitted:
        try:
            sheet = connect_to_sheet()
            date_str = date.strftime("%Y/%m/%d")
            
            # データを追加
            sheet.append_row([date_str, buyer, item_name, amount])
            
            st.success("✅ スプレッドシートに保存しました！")
            st.balloons()
            
            st.warning("👇 本当にここに書き込まれているか、クリックして確認してください！")
            st.write(f"書き込み先URL: {sheet.url}")
            # --- デバッグ用（どこに書き込んだか表示） ---
            st.info(f"書き込み先: {SPREADSHEET_NAME}")
            
        except Exception as e:
            st.error(f"エラーが発生しました: {e}")
            # もし詳細なエラーがあれば表示
            if hasattr(e, 'response'):
                st.write(e.response.text)

# --- 履歴表示 ---
st.divider()
st.header("📊 履歴")
if st.button("最新データを読み込む"):
    try:
        sheet = connect_to_sheet()
        data = sheet.get_all_values() # 単純なリストとして取得
        st.dataframe(data)
    except Exception as e:
        st.error("読み込み失敗")