import streamlit as st
from datetime import datetime
import json
import gspread

# ==========================================
# 👇 ここにスプレッドシートのURLを貼り付けてください！
SHEET_URL = "https://docs.google.com/spreadsheets/d/xxxxxxxxxxxx/edit"
# ==========================================

st.title("💸 模擬店 経費入力システム")

# --- 接続関数 ---
def connect_to_sheet():
    if "service_account_json" not in st.secrets:
        st.error("Secretsの設定がありません")
        return None

    key_dict = json.loads(st.secrets["service_account_json"])
    
    # ロボットのアドレスを表示（共有確認用）
    robot_email = key_dict["client_email"]
    st.info(f"🤖 ロボットのアドレス: {robot_email}")
    st.caption("↑ このアドレスをコピーして、スプレッドシートの「共有」に追加してください！")

    gc = gspread.service_account_from_dict(key_dict)
    
    # ★ここを変更：名前ではなくURLで開く！
    sh = gc.open_by_url(SHEET_URL)
    return sh.sheet1

# --- 入力フォーム ---
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
            sheet.append_row([date_str, buyer, item_name, amount])
            st.success("✅ 保存成功！")
            st.balloons()
            
        except Exception as e:
            st.error(f"エラー: {e}")