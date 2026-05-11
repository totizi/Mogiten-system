import streamlit as st
from datetime import datetime
import json
import gspread
import time
from collections import Counter
import pandas as pd

# ==========================================
# ⚙️ 定数 & CSS設定
# ==========================================
SPREADSHEET_NAME = "模擬店データベース"
CLASS_NAME = "3年7組"
CLASS_PASSWORD = "377" # ★パスワードはお好みで変更してください

CUSTOM_CSS = """
    <style>
    footer {visibility: hidden;}
    .block-container { padding-top: 3.5rem !important; padding-bottom: 5rem !important; }
    
    /* 商品ボタン */
    div.stButton > button[kind="secondary"] {
        height: 85px !important; width: 100% !important;
        display: flex !important; flex-direction: column !important;
        justify-content: center !important; align-items: center !important;
        white-space: pre-wrap !important; line-height: 1.1 !important;
        padding: 2px !important; font-weight: bold !important; 
        font-size: 13px !important; border-radius: 12px !important;
        border-left: 6px solid #ccc !important;
    }
    div.stButton > button[kind="secondary"]:active { transform: scale(0.95); }
    div[data-testid="column"]:nth-child(odd) div.stButton > button[kind="secondary"] { border-left-color: #4b9ced !important; }
    div[data-testid="column"]:nth-child(even) div.stButton > button[kind="secondary"] { border-left-color: #7d8ad4 !important; }

    /* 会計・重要ボタン */
    div.stButton > button[kind="primary"] {
        min-height: 65px !important; width: 100% !important;
        font-size: 18px !important; font-weight: bold !important;
        border-radius: 12px !important;
    }

    div[data-testid="stExpander"] button[kind="primary"] {
        height: 40px !important; min-height: 40px !important; width: auto !important;
        background-color: #ff4b4b !important; color: white !important;
    }
    
    div[data-testid="column"] button { min-height: 50px; }
    .sales-card { background: rgba(75, 156, 237, 0.1); padding: 15px; border-radius: 10px; border: 1px solid #4b9ced; margin-bottom: 20px; }
    
    @media (max-width: 640px) {
        div[data-testid="column"] { min-width: 0 !important; flex: 1 1 auto !important; }
        div.stButton > button { font-size: 12px !important; }
    }
    </style>
"""

st.set_page_config(page_title=f"{CLASS_NAME} レジ", layout="wide", initial_sidebar_state="auto")
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

if "is_logged_in" not in st.session_state:
    st.session_state.update({
        "is_logged_in": False, "cart": [], "received_amount": 0, 
        "flash_msg": None, "show_effect": False, "del_confirm_idx": None
    })

# ==========================================
# 🚀 バックエンド
# ==========================================
@st.cache_resource
def get_gc():
    try:
        if "service_account_json" not in st.secrets: return None
        return gspread.service_account_from_dict(json.loads(st.secrets["service_account_json"]))
    except Exception: return None

@st.cache_resource
def get_worksheet(tab_name):
    gc = get_gc()
    try: return gc.open(SPREADSHEET_NAME).worksheet(tab_name) if gc else None
    except Exception: return None

@st.cache_data(ttl=60) 
def get_raw_data(tab_name):
    try: return get_worksheet(tab_name).get_all_values() if get_worksheet(tab_name) else []
    except Exception: return []

def execute_db_action(action_func, msg="完了", effect=False):
    try:
        with st.spinner("通信中..."):
            action_func()
            get_raw_data.clear()
            st.session_state["flash_msg"] = f"✅ {msg}"
            if effect: st.session_state["show_effect"] = True
            st.session_state["received_amount"] = 0
            st.rerun()
    except gspread.exceptions.APIError: st.error("📡 通信エラー：再試行してください")
    except Exception as e: st.error(f"⚠️ エラー: {e}")

def calc_budget():
    try:
        budget = 30000
        b_data = get_raw_data("BUDGET")
        if len(b_data) > 1 and str(b_data[1][0]).isdigit():
            budget = int(b_data[1][0])
            
        expense_data = get_raw_data("経費")
        expense = sum(int(str(r[3]).replace(',', '')) for r in expense_data[1:] if len(r) > 3 and str(r[3]).replace(',', '').isdigit())
        return budget, expense, budget - expense
    except: return 0, 0, 0

def calc_sales_stats():
    try:
        sales_data = get_raw_data("レジ")
        all_sold, revenue = [], 0
        for r in sales_data[1:]:
            if len(r) > 2:
                all_sold.extend(r[1].split(","))
                if str(r[2]).replace(',', '').isdigit():
                    revenue += int(str(r[2]).replace(',', ''))
        return revenue, Counter(all_sold)
    except: return 0, Counter()

# ==========================================
# 🏫 認証 & UI
# ==========================================
if not st.session_state["is_logged_in"]:
    st.title(f"🏫 {CLASS_NAME} 専用レジ")
    pw = st.text_input("パスワードを入力", type="password")
    if st.button("ログイン", type="primary", use_container_width=True):
        if pw.strip() == CLASS_PASSWORD:
            st.session_state["is_logged_in"] = True
            st.rerun()
        else: st.error("パスワードが違います")
    st.stop()

if st.session_state["flash_msg"]:
    st.success(st.session_state["flash_msg"])
    if st.session_state["show_effect"]: st.balloons(); st.session_state["show_effect"] = False
    st.session_state["flash_msg"] = None

st.sidebar.title(f"🏫 {CLASS_NAME}")
mode = st.sidebar.selectbox("📂 モード", ["🎪 当日運営", "🛠 準備・前日"])
st.sidebar.divider()
if mode == "🛠 準備・前日":
    menu = st.sidebar.radio("メニュー", ["🍔 メニュー登録", "💸 経費記録", "✅ ToDo", "⚙️ 予算設定"])
else:
    menu = st.sidebar.radio("メニュー", ["💰 レジ会計", "📦 在庫・売上一括更新"])
if st.sidebar.button("ログアウト", use_container_width=True):
    st.session_state.update({"is_logged_in": False, "cart": []}); st.rerun()

budget, expense, rem = calc_budget()
if budget > 0:
    bar_color = "#ff4b4b" if rem < 0 else "#00cc96"
    msg = f"🚨 **予算超過: {abs(rem):,}円**" if rem < 0 else f"📊 **残金: {rem:,}円**"
    pct = min(int((expense / budget) * 100), 100)
    st.markdown(f"<div style='padding-top:5px;font-size:16px;'>{msg} (予算:{budget:,}円)</div>", unsafe_allow_html=True)
    st.markdown(f"<div style='background:#f0f2f6;border-radius:10px;height:12px;width:100%;margin-bottom:20px;'><div style='background:{bar_color};width:{pct}%;height:100%;border-radius:10px;'></div></div>", unsafe_allow_html=True)
st.divider()

# ==========================================
# 💰 レジ (POS)
# ==========================================
if menu == "💰 レジ会計":
    st.subheader("💰 レジ")

    @st.fragment
    def render_pos():
        c1, c2 = st.columns([1.5, 1])
        menu_data = get_raw_data("MENU")[1:]
        cart_counts = Counter([x['n'] for x in st.session_state["cart"]])

        with c1: 
            if not menu_data: st.info("メニュー未登録")
            else:
                chunk_size = 2
                for i in range(0, len(menu_data), chunk_size):
                    row_items = menu_data[i:i+chunk_size]
                    cols = st.columns(chunk_size)
                    for j, item in enumerate(row_items):
                        n, p = item[0], int(item[1])
                        status = item[2] if len(item) > 2 else "販売中"
                        stock = int(item[3]) if len(item) > 3 and item[3].isdigit() else 0
                        rem_stock = max(0, stock - cart_counts[n])
                        
                        label = f"🚫\n{n}\n(完売)" if (status=="完売" or stock<=0) else (f"🚫\n{n}\n(上限)" if rem_stock==0 else (f"⚠️ 残{rem_stock}\n{n}\n¥{p}" if rem_stock<=5 else f"{n}\n¥{p}\n(残{stock})"))
                        is_disabled = (status == "完売" or stock <= 0 or rem_stock == 0)
                        
                        if cols[j].button(label, key=f"pos_{i+j}", use_container_width=True, disabled=is_disabled):
                            st.session_state["cart"].append({"n": n, "p": p}); st.rerun()

        with c2: 
            total = sum(x['p'] for x in st.session_state["cart"])
            with st.expander("🛒 カート", expanded=True):
                if not st.session_state["cart"]: st.write("(空)")
                else:
                    for i, item in enumerate(st.session_state["cart"]):
                        ct, cb = st.columns([3, 1])
                        ct.write(f"・{item['n']}")
                        if cb.button("削", key=f"d_cart_{i}", type="primary"):
                            st.session_state["cart"].pop(i); st.rerun()
            
            st.metric("合計", f"¥{total:,}")
            
            if total > 0:
                st.markdown("##### 💵 預かり金入力")
                val = st.number_input("直接入力", value=st.session_state["received_amount"], step=10, label_visibility="collapsed")
                if val != st.session_state["received_amount"]:
                    st.session_state["received_amount"] = val; st.rerun()
                
                bc = st.columns(3)
                for i, amt in enumerate([1000, 500, 100, 50, 10, 0]):
                    label = f"+{amt}" if amt > 0 else "C (0)"
                    if bc[i%3].button(label, key=f"pay_{amt}", use_container_width=True):
                        st.session_state["received_amount"] = 0 if amt == 0 else st.session_state["received_amount"] + amt
                        st.rerun()

                received = st.session_state["received_amount"]
                change = received - total
                if received > 0:
                    if change >= 0: st.success(f"お釣り: ¥{change:,}")
                    else: st.error(f"不足: ¥{abs(change):,}")

                if st.button("会計確定", type="primary", use_container_width=True):
                    if received < total: st.error("金額不足")
                    else:
                        c_names = [x['n'] for x in st.session_state["cart"]]
                        c_counts = Counter(c_names)
                        def checkout():
                            ws_r, ws_m = get_worksheet("レジ"), get_worksheet("MENU")
                            ws_r.append_row([datetime.now().strftime("%m/%d %H:%M"), ",".join(c_names), total])
                            
                            m_data = ws_m.get_all_values()
                            for idx, row in enumerate(m_data):
                                if idx > 0 and row[0] in c_counts:
                                    new_s = max(0, int(row[3]) - c_counts[row[0]])
                                    ws_m.update_cell(idx+1, 4, new_s)
                                    if new_s == 0: ws_m.update_cell(idx+1, 3, "完売")
                        
                        st.session_state["cart"] = []; st.session_state["received_amount"] = 0
                        execute_db_action(checkout, "会計完了！", effect=True)
            
            if st.button("全クリア", use_container_width=True):
                st.session_state.update({"cart":[], "received_amount":0}); st.rerun()
    render_pos()

# ==========================================
# 📦 在庫・売上 (一括更新)
# ==========================================
elif menu == "📦 在庫・売上一括更新":
    st.subheader("📦 在庫・売上分析 & 一括更新")
    total_rev, sold_counts = calc_sales_stats()
    st.markdown(f"<div class='sales-card'>💰 累計総売上: <b>{total_rev:,}円</b></div>", unsafe_allow_html=True)

    raw_menu = get_raw_data("MENU")[1:]
    if raw_menu:
        edit_data = []
        for i, row in enumerate(raw_menu):
            if len(row) >= 4:
                sold = sold_counts[row[0]]
                edit_data.append({
                    "商品名": row[0], "単価": int(row[1]), "在庫数": int(row[3]), 
                    "累計販売数": sold, "売上高": sold*int(row[1]), "_row_idx": i+2
                })
        
        edited_df = st.data_editor(
            pd.DataFrame(edit_data),
            column_config={
                "商品名": st.column_config.TextColumn(disabled=True),
                "単価": st.column_config.NumberColumn(disabled=True, format="¥%d"),
                "在庫数": st.column_config.NumberColumn(min_value=0, step=1, required=True),
                "累計販売数": st.column_config.NumberColumn(disabled=True),
                "売上高": st.column_config.NumberColumn(disabled=True, format="¥%d"),
            },
            column_order=["商品名", "単価", "在庫数", "累計販売数", "売上高"],
            hide_index=True, use_container_width=True, num_rows="fixed"
        )
        if st.button("💾 在庫数を一括保存", type="primary"):
            def bulk_update():
                ws = get_worksheet("MENU")
                for index, row in edited_df.iterrows():
                    new_s = int(row["在庫数"])
                    ws.update_cell(row["_row_idx"], 4, new_s)
                    ws.update_cell(row["_row_idx"], 3, "完売" if new_s==0 else "販売中")
            execute_db_action(bulk_update, "在庫を一括更新しました！")
    else: st.info("メニューがありません")

# ==========================================
# 💸 経費記録
# ==========================================
elif menu == "💸 経費記録":
    st.subheader("💸 経費記録")
    with st.form("exp"):
        d, p, i, a = st.date_input("日付"), st.text_input("購入者"), st.text_input("品名"), st.number_input("金額", min_value=0, step=1)
        if st.form_submit_button("登録", use_container_width=True):
            execute_db_action(lambda: get_worksheet("経費").append_row([d.strftime("%Y/%m/%d"), p, i, a]), "経費を登録しました")

# ==========================================
# ✅ ToDoリスト
# ==========================================
elif menu == "✅ ToDo":
    st.subheader("✅ 準備ToDoリスト")
    with st.form("todo"):
        t, p = st.text_input("タスク内容"), st.text_input("担当者")
        if st.form_submit_button("追加", use_container_width=True):
            if t: execute_db_action(lambda: get_worksheet("todo").append_row([datetime.now().strftime("%m/%d"), t, p, "未完了"]), "タスクを追加しました")
    st.divider()
    
    @st.fragment
    def render_todo():
        raw = get_raw_data("todo")[1:]
        active = [{"r": r, "idx": i+2} for i, r in enumerate(raw) if len(r) > 3 and "未完了" in r[3]]
        if active:
            upds = [item['idx'] for item in active if st.checkbox(f"{item['r'][1]} (担当:{item['r'][2]})", key=f"chk_{item['idx']}")]
            if upds and st.button("選択したタスクを完了にする", type="primary", use_container_width=True):
                execute_db_action(lambda: [get_worksheet("todo").update_cell(rid, 4, "完了") for rid in upds], "タスクを完了にしました")
        else: st.info("現在残っているタスクはありません")
    render_todo()

# ==========================================
# 🍔 メニュー登録
# ==========================================
elif menu == "🍔 メニュー登録":
    st.subheader("🍔 メニュー登録")
    with st.form("add_m"):
        n, p, s = st.text_input("商品名"), st.number_input("単価", min_value=0, step=10), st.number_input("初期在庫", min_value=1, value=50)
        if st.form_submit_button("追加", use_container_width=True):
            if n and p > 0: execute_db_action(lambda: get_worksheet("MENU").append_row([n, p, "販売中", s]), f"{n}を登録しました")
            else: st.error("入力内容を確認してください")
    st.divider()
    
    with st.expander("📋 登録済みメニューの管理", expanded=True):
        m_data = [{"d": r, "idx": i+2} for i, r in enumerate(get_raw_data("MENU")[1:]) if len(r) > 0]
        for item in m_data:
            row, idx = item["d"], item["idx"]
            c1, c2 = st.columns([3, 1])
            c1.write(f"・**{row[0]}** (¥{row[1]}) / 在庫: {row[3]}")
            if st.session_state["del_confirm_idx"] == idx:
                cy, cn = c2.columns(2)
                if cy.button("はい", key=f"y_{idx}", type="primary"): execute_db_action(lambda: get_worksheet("MENU").delete_rows(idx), "削除しました"); st.session_state["del_confirm_idx"] = None
                if cn.button("いいえ", key=f"n_{idx}", type="secondary"): st.session_state["del_confirm_idx"] = None; st.rerun()
            else:
                if c2.button("削除", key=f"d_{idx}"): st.session_state["del_confirm_idx"] = idx; st.rerun()

# ==========================================
# ⚙️ 予算設定
# ==========================================
elif menu == "⚙️ 予算設定":
    st.subheader("⚙️ 予算設定")
    with st.form("bud"):
        curr = 30000
        b_data = get_raw_data("BUDGET")
        if len(b_data) > 1 and str(b_data[1][0]).isdigit(): curr = int(b_data[1][0])
            
        nb = st.number_input("クラス予算額", value=curr, step=1000)
        if st.form_submit_button("更新", use_container_width=True):
            ws = get_worksheet("BUDGET")
            execute_db_action(lambda: ws.update_cell(2, 1, nb) if len(ws.get_all_values()) > 1 else ws.append_row([nb]), "予算を更新しました")
