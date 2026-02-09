import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta

# --- パスワード設定 ---
MEMBER_PASSWORD = "member2026"
ADMIN_PASSWORD = "admin2026"

# --- st.session_stateの初期化 ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_role" not in st.session_state:
    st.session_state.user_role = None

st.title("シフト提出アプリ")

# --- ログインフォーム ---
if not st.session_state.logged_in:
    st.subheader("ログイン")
    with st.form("login_form"):
        password_input = st.text_input("パスワードを入力してください", type="password")
        login_submit = st.form_submit_button("ログイン")
        
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
    st.stop()  # ログインするまでこれ以降は表示しない

# --- ログイン後のアプリケーション本体 ---
st.markdown("---")
st.header("アルバイト勤務希望提出フォーム")

# 月選択機能
current_month = datetime.now().replace(day=1)
next_month = (current_month + timedelta(days=32)).replace(day=1)

months = {
    current_month.strftime("%Y年%m月"): current_month,
    next_month.strftime("%Y年%m月"): next_month,
}

selected_month_str = st.selectbox("提出する月を選択してください", list(months.keys()))
selected_month = months[selected_month_str]

# 選択された月の全ての日付をリストにする
next_month_start = (selected_month + timedelta(days=32)).replace(day=1)
date_range = []
curr = selected_month
while curr < next_month_start:
    date_range.append(curr)
    curr += timedelta(days=1)

# CSVファイルパス
CSV_FILE = f'shift_data_{selected_month.strftime("%Y_%m")}.csv'

# シフト提出フォーム
with st.form("shift_form"):
    name = st.text_input("名前を入力してください")
    
    selected_dates = st.multiselect(
        "出勤可能日をすべて選んでください（複数選択・飛び飛びOK）",
        options=date_range,
        format_func=lambda x: x.strftime("%Y/%m/%d (%a)")
    )

    start_time = st.time_input("勤務可能開始時間", value=datetime.strptime("09:00", "%H:%M").time())
    end_time = st.time_input("勤務可能終了時間", value=datetime.strptime("18:00", "%H:%M").time())

    submitted = st.form_submit_button("シフトを送信する")

    if submitted:
        if name and selected_dates and start_time and end_time:
            all_data = []
            for d in selected_dates:
                all_data.append({
                    '名前': name,
                    '日付': d.strftime('%Y-%m-%d'),
                    '勤務可能開始時間': start_time.strftime('%H:%M'),
                    '勤務可能終了時間': end_time.strftime('%H:%M'),
                })
            df = pd.DataFrame(all_data)

            # 保存処理
            if not os.path.isfile(CSV_FILE) or os.stat(CSV_FILE).st_size == 0:
                df.to_csv(CSV_FILE, index=False, mode='a', encoding='utf-8-sig')
            else:
                df.to_csv(CSV_FILE, index=False, mode='a', header=False, encoding='utf-8-sig')

            st.success(f"【送信完了】{len(selected_dates)}日分の希望を受け付けました！")
        else:
            st.error("「名前」の入力と「日付」の選択を忘れていませんか？")

# 選択状況の表示
if selected_dates:
    st.info(f"現在 {len(selected_dates)} 日間を選択中です。")

# --- 管理者用セクション ---
if st.session_state.user_role == "admin":
    st.markdown("---")
    st.subheader("🛠️ 管理者専用メニュー")
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, "rb") as file:
            st.download_button(
                label="CSVデータをダウンロード",
                data=file,
                file_name=CSV_FILE,
                mime="text/csv",
            )
    else:
        st.write("まだ提出されたデータはありません。")

# --- ログアウト ---
st.sidebar.write(f"ログイン中: {st.session_state.user_role}")
if st.sidebar.button("ログアウト"):
    st.session_state.logged_in = False
    st.session_state.user_role = None
    st.rerun()