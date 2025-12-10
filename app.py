import streamlit as st
from datetime import datetime
import json
import gspread

# ==========================================
# 👇 ここにスプレッドシートの「ファイル名」を正確に入れてください
SPREADSHEET_NAME = "模擬店データベース"
# ==========================================

st.title("💸 模擬店 経費入力システム")

# --- 接続関数 ---
def connect_to_sheet():
    # Secretsから鍵を取り出す
    key_dict = json.loads(st.secrets["service_account_json"])
    gc = gspread.service_account_from_dict(key_dict)
    
    # ★URLではなく、さっき成功した「名前」で探す方法に戻しました！
    sh = gc.open(SPREADSHEET_NAME)
    
    return sh.sheet1

# --- 入力フォーム ---
with st.form("input_form"):
    date = st.date_input("購入日", datetime.now())
    buyer = st.selectbox("購入者", ["自分", "Aさん", "Bさん", "Cさん", "先生"])
    item_name = st.text_input("品名")
    amount = st.number_input("金額（円）", min_value=0, step=1)
    
    submitted = st.form_submit_button("登録する")

    if submitted:
        # エラーを隠さない設定（ガードなし）
        sheet = connect_to_sheet()
        date_str = date.strftime("%Y/%m/%d")
        
        # 追加
        sheet.append_row([date_str, buyer, item_name, amount])
        
        st.success("✅ 保存成功！")
        st.balloons()