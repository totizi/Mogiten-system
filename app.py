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
CLASS_PASSWORDS = {f"{i}HR": str(i)*2 for i in range(21, 29)}

CUSTOM_CSS = """
    <style>
    footer {visibility: hidden;}
    
    /* === 共通設定 === */
    .block-container { padding-top: 3.5rem !important; padding-bottom: 5rem !important; }
    
    /* 商品ボタン（高さ固定・色分け） */
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

    /* カート内の削除ボタン */
    div[data-testid="stExpander"] button[kind="primary"] {
        height: 40px !important; min-height: 40px !important; width: auto !important;
        background-color: #ff4b4b !important; color: white !important;
    }
    
    /* 金額入力ボタン（+1000など） */
    div[data-testid="column"] button {
        min-height: 50px;
    }

    .sales-card {
        background: rgba(75, 156, 237, 0.1); padding: 15px;
        border-radius: 10px; border: 1px solid #4b9ced; margin-bottom: 20px;
    }
    
    /* === 📱 スマホレイアウト調整 === */
    @media (max-width: 640px) {
        /* 商品ボタンの列を強制的に横並び維持 */
        div[data-testid="column"] {
            min-width: 0 !important;
            flex: 1 1 auto !important;
        }
        /* ボタン文字サイズ調整 */
        div.stButton > button {
            font-size: 12px !important;
        }
    }
    </style>
"""

st.set_page_config(page_title="文化祭レジPro", layout="wide", initial_sidebar_state="auto")
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# セッション初期化
if "is_logged_in" not in st.session_state:
    st.session_state.update({
        "is_logged_in": False, "logged_class": None, "cart": [], 
        "received_amount": 0, "flash_msg": None, "flash_type": "success",
        "del_confirm_idx": None, "show_effect": False
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

def calc_budget(cls_name):
    try:
        budget = 30000
        for r in get_raw_data("BUDGET"):
            if len(r) >= 2 and r[0] == cls_name: budget = int(r[1]); break
        class_data = get_raw_data(cls_name)
        expense = sum(int(str(r[4]).replace(',', '')) for r in class_data[1:] 
                      if len(r) > 4 and "経費" in str(r[1]) and str(r[4]).replace(',', '').isdigit())
        return budget, expense, budget - expense
    except: return 0, 0, 0

def calc_sales_stats(cls_name):
    try:
        sales_data = get_raw_data(cls_name)
        all_sold, revenue = [], 0
        for r in sales_data[1:]:
            if len(r) > 4 and "売上" in r[1]:
                all_sold.extend(r[3].split(","))
                revenue += int(str(r[4]).replace(',', ''))
        return revenue, Counter(all_sold)
    except: return 0, Counter()

# ==========================================
# 🏫 認証 & UI
# ==========================================
if not st.session_state["is_logged_in"]:
    st.title("🏫 文化祭レジPro")
    sel_cls = st.selectbox("クラス選択", list(CLASS_PASSWORDS.keys()))
    pw = st.text_input("パスワード", type="password")
    if st.button("ログイン", type="primary", use_container_width=True):
        if pw.strip() == CLASS_PASSWORDS.get(sel_cls):
            st.session_state.update({"is_logged_in": True, "logged_class": sel_cls})
            st.rerun()
        else: st.error("パスワードが違います")
    st.stop()

selected_class = st.session_state["logged_class"]

if st.session_state["flash_msg"]:
    st.success(st.session_state["flash_msg"])
    if st.session_state["show_effect"]: st.balloons(); st.session_state["show_effect"] = False
    st.session_state["flash_msg"] = None

st.sidebar.title(f"🏫 {selected_class}")
mode = st.sidebar.selectbox("📂 モード", ["🎪 当日運営", "🛠 準備・前日"])
st.sidebar.divider()
if mode == "🛠 準備・前日":
    menu = st.sidebar.radio("メニュー", ["🍔 登録", "💸 経費", "✅ ToDo", "⚙️ 予算"])
else:
    menu = st.sidebar.radio("メニュー", ["💰 レジ", "📦 在庫・売上"])
if st.sidebar.button("ログアウト", use_container_width=True):
    st.session_state.update({"is_logged_in": False, "cart": []}); st.rerun()

budget, expense, rem = calc_budget(selected_class)
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
if menu == "💰 レジ":
    st.subheader(f"💰 {selected_class} レジ")

    @st.fragment
    def render_pos():
        c1, c2 = st.columns([1.5, 1])
        menu_data = [r for r in get_raw_data("MENU")[1:] if r[0] == selected_class]
        cart_counts = Counter([x['n'] for x in st.session_state["cart"]])

        # --- 商品選択エリア ---
        with c1: 
            if not menu_data: st.info("メニュー未登録")
            else:
                chunk_size = 2
                for i in range(0, len(menu_data), chunk_size):
                    row_items = menu_data[i:i+chunk_size]
                    cols = st.columns(chunk_size)
                    for j, item in enumerate(row_items):
                        n, p = item[1], int(item[2])
                        stock = int(item[4]) if len(item) > 4 and item[4].isdigit() else 0
                        status = item[3] if len(item) > 3 else "販売中"
                        rem_stock = max(0, stock - cart_counts[n])
                        
                        label = f"🚫\n{n}\n(完売)" if (status=="完売" or stock<=0) else (f"🚫\n{n}\n(上限)" if rem_stock==0 else (f"⚠️ 残{rem_stock}\n{n}\n¥{p}" if rem_stock<=5 else f"{n}\n¥{p}\n(残{stock})"))
                        is_disabled = (status == "完売" or stock <= 0 or rem_stock == 0)
                        
                        if cols[j].button(label, key=f"pos_{i+j}", use_container_width=True, disabled=is_disabled):
                            st.session_state["cart"].append({"n": n, "p": p}); st.rerun()

        # --- カート & 会計エリア ---
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
                # ★修正: 預かり金入力を元の「ボタン加算式」に戻しました
                st.markdown("##### 💵 預かり金入力")
                
                # 直接入力欄
                val = st.number_input("直接入力", value=st.session_state["received_amount"], step=10, label_visibility="collapsed")
                if val != st.session_state["received_amount"]:
                    st.session_state["received_amount"] = val; st.rerun()
                
                # ボタン配列 (3列で表示)
                bc = st.columns(3)
                for i, amt in enumerate([1000, 500, 100, 50, 10, 0]):
                    label = f"+{amt}" if amt > 0 else "C (0)"
                    if bc[i%3].button(label, key=f"pay_{amt}", use_container_width=True):
                        if amt == 0: st.session_state["received_amount"] = 0
                        else: st.session_state["received_amount"] += amt
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
                            ws_s, ws_m = get_worksheet(selected_class), get_worksheet("MENU")
                            ws_s.append_row([datetime.now().strftime("%m/%d %H:%M"), "🔵 売上", "レジ", ",".join(c_names), total])
                            m_data = ws_m.get_all_values()
                            for idx, row in enumerate(m_data):
                                if idx>0 and row[0]==selected_class and row[1] in c_counts:
                                    new_s = max(0, int(row[4]) - c_counts[row[1]])
                                    ws_m.update_cell(idx+1, 5, new_s)
                                    if new_s == 0: ws_m.update_cell(idx+1, 4, "完売")
                        st.session_state["cart"] = []; st.session_state["received_amount"] = 0
                        execute_db_action(checkout, "会計完了！", effect=True)
            
            if st.button("全クリア", use_container_width=True):
                st.session_state.update({"cart":[], "received_amount":0}); st.rerun()
    render_pos()

# ==========================================
# 📦 在庫・売上 (一括更新)
# ==========================================
elif menu == "📦 在庫・売上":
    st.subheader("📦 在庫・売上分析 & 一括更新")
    total_rev, sold_counts = calc_sales_stats(selected_class)
    st.markdown(f"<div class='sales-card'>💰 クラス総売上: <b>{total_rev:,}円</b></div>", unsafe_allow_html=True)

    raw_menu = get_raw_data("MENU")
    my_menu_indices = [i for i, r in enumerate(raw_menu) if i > 0 and r[0] == selected_class]
    if my_menu_indices:
        edit_data = []
        for idx in my_menu_indices:
            row = raw_menu[idx]
            sold = sold_counts[row[1]]
            edit_data.append({"商品名": row[1], "単価": int(row[2]), "在庫数": int(row[4]), "累計販売数": sold, "売上高": sold*int(row[2]), "_row_idx": idx+1})
        
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
                    ws.update_cell(row["_row_idx"], 5, new_s)
                    ws.update_cell(row["_row_idx"], 4, "完売" if new_s==0 else "販売中")
            execute_db_action(bulk_update, "在庫を一括更新しました！")
    else: st.info("メニューなし")

elif menu == "💸 経費":
    st.subheader(f"💸 {selected_class} 経費")
    with st.form("exp"):
        d, p, i, a = st.date_input("日付"), st.text_input("担当者"), st.text_input("品名"), st.number_input("金額", min_value=0, step=1)
        if st.form_submit_button("登録", use_container_width=True):
            execute_db_action(lambda: get_worksheet(selected_class).append_row([d.strftime("%Y/%m/%d"), "🔴 経費", p, i, a]), "経費登録完了")

elif menu == "✅ ToDo":
    st.subheader(f"✅ {selected_class} ToDo")
    with st.form("todo"):
        t, p = st.text_input("内容"), st.text_input("担当者")
        if st.form_submit_button("追加", use_container_width=True):
            if t: execute_db_action(lambda: get_worksheet("TODO").append_row([selected_class, datetime.now().strftime("%m/%d"), t, p, "未完了"]), "タスク追加")
    st.divider()
    @st.fragment
    def render_todo():
        raw = get_raw_data("TODO")
        active = [{"r": r, "idx": i+1} for i, r in enumerate(raw) if i > 0 and r[0] == selected_class and "未完了" in r[4]]
        if active:
            upds = [item['idx'] for item in active if st.checkbox(f"{item['r'][2]} ({item['r'][3]})", key=f"chk_{item['idx']}")]
            if upds and st.button("完了にする", type="primary", use_container_width=True):
                execute_db_action(lambda: [get_worksheet("TODO").update_cell(rid, 5, "完了") for rid in upds], "タスク完了")
        else: st.info("タスクなし")
    render_todo()

elif menu == "🍔 登録":
    st.subheader("🍔 メニュー登録")
    with st.form("add_m"):
        n, p, s = st.text_input("商品名"), st.number_input("単価", min_value=0, step=10), st.number_input("初期在庫", min_value=1, value=50)
        if st.form_submit_button("追加", use_container_width=True):
            if n and p > 0: execute_db_action(lambda: get_worksheet("MENU").append_row([selected_class, n, p, "販売中", s]), f"{n}を追加")
            else: st.error("入力確認")
    st.divider()
    with st.expander("📋 登録済みメニュー", expanded=True):
        m_data = [{"d": r, "idx": i+1} for i, r in enumerate(get_raw_data("MENU")) if i > 0 and r[0] == selected_class]
        for item in m_data:
            row, idx = item["d"], item["idx"]
            c1, c2 = st.columns([3, 1])
            c1.write(f"・**{row[1]}** (¥{row[2]}) / 在庫: {row[4]}")
            if st.session_state["del_confirm_idx"] == idx:
                cy, cn = c2.columns(2)
                if cy.button("はい", key=f"y_{idx}", type="primary"): execute_db_action(lambda: get_worksheet("MENU").delete_rows(idx), "削除完了"); st.session_state["del_confirm_idx"] = None
                if cn.button("いいえ", key=f"n_{idx}", type="secondary"): st.session_state["del_confirm_idx"] = None; st.rerun()
            else:
                if c2.button("削除", key=f"d_{idx}", type="primary"): st.session_state["del_confirm_idx"] = idx; st.rerun()

elif menu == "⚙️ 予算":
    st.subheader("⚙️ 予算設定")
    with st.form("bud"):
        curr = 30000
        for r in get_raw_data("BUDGET"):
            if len(r) >= 2 and r[0] == selected_class: curr = int(r[1]); break
        nb = st.number_input("新予算", value=curr, step=1000)
        if st.form_submit_button("更新", use_container_width=True):
            ws = get_worksheet("BUDGET")
            row_idx = next((i+1 for i, r in enumerate(ws.get_all_values()) if r[0] == selected_class), None)
            execute_db_action(lambda: ws.update_cell(row_idx, 2, nb) if row_idx else ws.append_row([selected_class, nb]), "予算更新")
