import streamlit as st
import pandas as pd
import os
from datetime import datetime

# ページの設定
st.set_page_config(page_title="模擬店会計アプリ", layout="wide")

# タイトル
st.title("💸 模擬店 経費入力システム")

# データを保存するファイル名
DATA_FILE = "kaidashi_data.csv"

# --- 機能1: 経費の入力フォーム ---
st.header("📝 新しいレシートを入力")
with st.form("input_form"):
    # 日付（今日は自動入力）
    date = st.date_input("購入日", datetime.now())
    # 誰が買った？
    buyer = st.selectbox("購入者（誰が払った？）", ["自分", "Aさん", "Bさん", "Cさん", "先生"])
    # 何を買った？
    item_name = st.text_input("品名（例：紙コップ、氷）")
    # いくら？
    amount = st.number_input("金額（円）", min_value=0, step=1)
    
    # 送信ボタン
    submitted = st.form_submit_button("登録する")

    if submitted:
        # 入力データのまとまりを作る
        new_data = {
            "日付": [date],
            "購入者": [buyer],
            "品名": [item_name],
            "金額": [amount]
        }
        df_new = pd.DataFrame(new_data)

        # ファイルに保存する処理（CSV追記モード）
        if os.path.exists(DATA_FILE):
            # ファイルがあれば追記
            df_new.to_csv(DATA_FILE, mode='a', header=False, index=False)
        else:
            # ファイルがなければ新規作成
            df_new.to_csv(DATA_FILE, mode='w', header=True, index=False)
        
        st.success("✅ 登録しました！")

# --- 機能2: データの表示 ---
st.divider() # 区切り線
st.header("📊 現在の経費リスト")

if os.path.exists(DATA_FILE):
    # CSVファイルを読み込んで表示
    df = pd.read_csv(DATA_FILE)
    st.dataframe(df, use_container_width=True)
    
    # 合計金額の計算
    total_amount = df["金額"].sum()
    st.metric(label="現在の経費合計", value=f"{total_amount:,} 円")
else:
    st.info("まだデータがありません。")