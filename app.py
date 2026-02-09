import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta

# --- 1. ページ設定の追加 ---
st.set_page_config(
    page_title="シフト提出システム",
    page_icon="📅",
    layout="centered"
)

# --- パスワード設定 ---
MEMBER_PASSWORD = "member2026"
ADMIN_PASSWORD = "admin2026"

# --- st.session_stateの初期化 ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_role" not in st.session_state:
    st.session_state.user_role = None

# --- 3. サイドバーの活用 (共通部分) ---
with st.sidebar:
    st.title("📖 操作ガイド")
    st.info("""
    1. **ログイン**する
    2. **提出月**を選択する
    3. **出勤可能日**をすべて選ぶ
    4. **送信ボタン**を押す
    """)
    st.markdown("---")
    
    # ログイン済みの場合はユーザー情報を表示
    if st.session_state.logged_in:
        st.write(f"👤 ログイン中: **{st.session_state.user_role}**")
        if st.button("ログアウト", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user_role = None
            st.rerun()

# --- 2. ヘッダーのデザイン (メイン画面) ---
st.title("📝 シフト提出フォーム")
st.caption("希望日をすべて選択して、下の「シフトを送信する」ボタンを押してください。")

# --- ログインフォーム ---
if not st.session_state.logged_in:
    st.subheader("🔑 ログイン")
    with st.form("login_form"):
        password_input = st.text_input("パスワードを入力してください", type="password")
        login_submit = st.form_submit_button("ログイン", use_container_width=True)
        
        if login_submit:
            if password_input == MEMBER_PASSWORD:
                st.session_state.logged_in = True
                st.session_state.user_role = "member"
                st.rerun()
            elif password_input == ADMIN_PASSWORD:
                st.session_state.logged_in = True
                st.session_state.user_role = "admin"
                st.rerun()
            else:
                st.error("パスワードが間違っています。")
    st.stop()

# --- ログイン後のメイン画面 ---
st.markdown("---")

# 月選択機能
current_month = datetime.now().replace(day=1)
next_month = (current_month + timedelta(days=32)).replace(day=1)
months = {
    current_month.strftime("%Y年%m月"): current_month,
    next_month.strftime("%Y年%m月"): next_month,
}

selected_month_str = st.selectbox("📅 提出する月を選択してください", list(months.keys()))
selected_month = months[selected_month_str]

# 選択された月の全ての日付を生成
next_month_start = (selected_month + timedelta(days=32)).replace(day=1)
date_range = []
curr = selected_month
while curr < next_month_start:
    date_range.append(curr)
    curr += timedelta(days=1)

CSV_FILE = f'shift_data_{selected_month.strftime("%Y_%m")}.csv'

# シフト提出フォーム
with st.form("shift_form"):
    st.subheader("📋 入力項目")
    name = st.text_input("名前 (フルネーム)", placeholder="例：山田 太郎")
    
    selected_dates = st.multiselect(
        "出勤可能日 (複数選択可)",
        options=date_range,
        format_func=lambda x: x.strftime("%Y/%m/%d (%a)"),
        help="飛び飛びで選択可能です"
    )

    col1, col2 = st.columns(2)
    with col1:
        start_time = st.time_input("勤務開始時間", value=datetime.strptime("09:00", "%H:%M").time())
    with col2:
        end_time = st.time_input("勤務終了時間", value=datetime.strptime("18:00", "%H:%M").time())

    submitted = st.form_submit_button("🚀 シフトを送信する", use_container_width=True)

    if submitted:
        if name and selected_dates:
            all_data = []
            for d in selected_dates:
                all_data.append({
                    '名前': name,
                    '日付': d.strftime('%Y-%m-%d'),
                    '開始': start_time.strftime('%H:%M'),
                    '終了': end_time.strftime('%H:%M'),
                })
            df = pd.DataFrame(all_data)

            # 保存処理
            if not os.path.isfile(CSV_FILE) or os.stat(CSV_FILE).st_size == 0:
                df.to_csv(CSV_FILE, index=False, mode='a', encoding='utf-8-sig')
            else:
                df.to_csv(CSV_FILE, index=False, mode='a', header=False, encoding='utf-8-sig')

            # --- 4. 送信完了画面の演出 ---
            st.balloons()
            st.success(f"【送信完了】{name}さん、{len(selected_dates)}日分のシフトを受け付けました！")
        else:
            st.error("「名前」と「日付」は必須項目です。")

# --- 管理者用セクション ---
if st.session_state.user_role == "admin":
    st.sidebar.markdown("---")
    st.sidebar.subheader("🛠️ 管理者メニュー")
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, "rb") as file:
            st.sidebar.download_button(
                label="📊 CSVをダウンロード",
                data=file,
                file_name=CSV_FILE,
                mime="text/csv",
                use_container_width=True
            )
    else:
        st.sidebar.write("（データ未提出）")