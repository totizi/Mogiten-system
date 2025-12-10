import streamlit as st
from datetime import datetime
import json
import gspread

# --- 設定エリア ---
SPREADSHEET_NAME = "模擬店データベース"

st.title("🛠️ 接続テストモード")

# --- 接続関数 ---
def connect_to_sheet():
    # Secretsがあるかチェック
    if "service_account_json" not in st.secrets:
        st.error("Secretsが設定されていません！")
        return None

    key_dict = json.loads(st.secrets["service_account_json"])
    # 这里的 gspread 版本如果是 6.0.0 以上可能会出问题，但在 debug 模式下我们要看原生报错
    gc = gspread.service_account_from_dict(key_dict)
    sh = gc.open(SPREADSHEET_NAME)
    return sh.sheet1

# --- テスト実行ボタン ---
if st.button("テスト送信（ガードなし）"):
    st.write("接続を開始します...")
    
    # ★ここから try-except を外しています！
    # エラーが起きるとここでアプリが止まり、詳細が表示されます
    
    sheet = connect_to_sheet()
    st.write("シートを開けました！書き込みを試みます...")
    
    date_str = datetime.now().strftime("%Y/%m/%d")
    
    # テストデータを書き込み
    sheet.append_row([date_str, "テスト君", "接続テスト", 100])
    
    st.success("✅ 書き込み成功！スプレッドシートを確認してください。")