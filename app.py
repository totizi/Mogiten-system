app.py
import streamlit as st

st.title("文化祭会計 Mogi-Pay 🚀")
st.write("これはスマホでの動作テストです！")

# 入力フォームのテスト
user_name = st.text_input("あなたの名前は？")
ok_btn = st.button("送信")

if ok_btn:
    st.success(f"{user_name}さん、こんにちは！スマホから見えてますね！")