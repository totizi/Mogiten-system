import streamlit as st
import pandas as pd
from datetime import datetime
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- 設定エリア ---
# スプレッドシートの名前（作ったファイル名と完全に一致させること！）
SPREADSHEET_NAME = "模擬店データベース"

# ページ設定
st.set_page_config(page_title="模擬店会計アプリ", layout="wide")
st.title("💸 模擬店 経費入力システム (Excel連携版)")

# --- スプレッドシートに接続する関数（おまじない） ---
def connect_to_sheet():
    # Secretsから鍵情報を取り出す
    key_dict = json.loads(st.secrets["service_account_json"])
    
    # 認証の設定
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
    client = gspread.authorize(creds)
    
    # シートを開く
    sheet = client.open(SPREADSHEET_NAME).sheet1
    return sheet

# --- 機能1: 経費の入力フォーム ---
st.header("📝 新しいレシートを入力")
with st.form("input_form"):
    date = st.date_input("購入日", datetime.now())
    buyer = st.selectbox("購入者", ["自分", "Aさん", "Bさん", "Cさん", "先生"])
    item_name = st.text_input("品名")
    amount = st.number_input("金額（円）", min_value=0, step=1)
    
    submitted = st.form_submit_button("登録する")

    if submitted:
        try:
            # スプレッドシートに接続
            sheet = connect_to_sheet()
            
            # 日付を文字列に変換
            date_str = date.strftime("%Y/%m/%d")
            
            # データを追加（行の一番下に追加される）
            sheet.append_row([date_str, buyer, item_name, amount])
            
            st.success("✅ スプレッドシートに保存しました！")
            st.balloons() # 風船を飛ばす演出
            
        except Exception as e:
            st.error(f"エラーが発生しました: {e}")

# --- 機能2: リアルタイム履歴表示 ---
st.divider()
st.header("📊 スプレッドシートの中身")

# ボタンを押したときだけ読み込む（通信節約）
if st.button("最新データを読み込む"):
    try:
        sheet = connect_to_sheet()
        # 全データを取得
        data = sheet.get_all_records()
        
        if data:
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True)
            
            # 合計金額の計算
            if "金額" in df.columns:
                total = df["金額"].sum()
                st.metric("現在の経費合計", f"{total:,} 円")
        else:
            st.info("データはまだありません。")
            
    except Exception as e:
        st.warning("データの読み込みに失敗しました。まだ1行目にヘッダー（日付、購入者...）がない可能性があります。")
        st.info("💡 ヒント: スプレッドシートの1行目に手動で「日付」「購入者」「品名」「金額」と入力してみてください。")