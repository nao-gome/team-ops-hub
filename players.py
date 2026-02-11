import streamlit as st
import pandas as pd
import os
from PIL import Image
from datetime import date
import plotly.express as px
import base64
import hashlib

# --- 0. セキュリティ関数 ---
def hash_password(password):
    """パスワードをSHA-256でハッシュ化（暗号化）する"""
    return hashlib.sha256(str(password).encode()).hexdigest()

# --- 1. ページ設定 ---
st.set_page_config(page_title="選手コンディション管理", page_icon="⚽", layout="wide")

def get_base64_image(image_path):
    """ローカル画像をHTML（円形枠）で表示するためにBase64変換する"""
    if os.path.exists(str(image_path)):
        with open(image_path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    return None

# カスタムCSS（全デザイン統合）
st.markdown("""
    <style>
    header[data-testid="stHeader"] { display: none !important; }
    .block-container { padding-top: 0 !important; }
    
    /* 濃い青のフル幅ヘッダー */
    .full-width-header {
        background-color: #01579b; color: white; width: 100vw; position: relative;
        left: 50%; right: 50%; margin-left: -50vw; margin-right: -50vw; margin-bottom: 2rem;
        box-shadow: 0 4px 10px rgba(0,0,0,0.3); display: flex; justify-content: center; align-items: center; min-height: 120px;
    }
    .full-width-header h1 { margin: 0 !important; font-size: 2.8rem; font-weight: 800; letter-spacing: 0.15em; }

    /* 管理者名簿用の画像タイル */
    .stImage > img { object-fit: cover; width: 100%; height: 200px; border-radius: 8px; }

    /* 選手用プロフィールのデザイン（円形写真用） */
    .profile-container {
        display: flex; background-color: #f8f9fa; padding: 25px; border-radius: 15px;
        border-left: 10px solid #01579b; margin-bottom: 25px; align-items: center; gap: 35px;
        box-shadow: 2px 2px 12px rgba(0,0,0,0.08);
    }
    .profile-photo {
        width: 160px; height: 160px; border-radius: 50%; overflow: hidden;
        display: flex; justify-content: center; align-items: center;
        background-color: #eee; border: 4px solid #fff; box-shadow: 0 2px 8px rgba(0,0,0,0.15); flex-shrink: 0;
    }
    .profile-photo img { width: 100%; height: 100%; object-fit: cover; }
    .profile-details h2 { margin: 0 0 10px 0; color: #01579b; font-size: 2.2rem; }

    /* ボタン共通デザイン */
    div.stButton > button { height: 100px; font-size: 22px !important; font-weight: 800 !important; border-radius: 12px; }
    button[kind="primary"] { background-color: #e1f5fe !important; color: #01579b !important; border-color: #81d4fa !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. データ準備 ---
MASTER_FILE = "player_master.csv"
CONDITION_FILE = "daily_condition.csv"
IMAGE_DIR = "player_images"
if not os.path.exists(IMAGE_DIR): os.makedirs(IMAGE_DIR)

COLUMNS = ["背番号", "名前", "ポジション", "学年", "身長", "体重", "画像パス", "パスワード"]
if os.path.exists(MASTER_FILE):
    df_players = pd.read_csv(MASTER_FILE)
    # パスワード列のハッシュ化対応
    if "パスワード" not in df_players.columns:
        df_players["パスワード"] = hash_password("1234")
    
    # 既存のパスワードがハッシュ化されていない場合の一括変換
    if not df_players.empty and len(str(df_players.iloc[0]["パスワード"])) != 64:
        df_players["パスワード"] = df_players["パスワード"].apply(hash_password)
        df_players.to_csv(MASTER_FILE, index=False, encoding="utf-8-sig")
else:
    df_players = pd.DataFrame(columns=COLUMNS)

if os.path.exists(CONDITION_FILE):
    df_cond = pd.read_csv(CONDITION_FILE)
    df_cond["日付"] = pd.to_datetime(df_cond["日付"]).dt.date
else:
    df_cond = pd.DataFrame(columns=["日付", "名前", "体重", "疲労度", "睡眠の質", "怪我痛み", "痛み詳細"])

# グラフの色設定（睡眠:青, 疲労:赤）
COLOR_MAP = {"睡眠の質": "#1f77b4", "疲労度": "#d62728"}

if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "user_role" not in st.session_state: st.session_state.user_role = None
if "user_name" not in st.session_state: st.session_state.user_name = None
if "show_form" not in st.session_state: st.session_state.show_form = None
if "selected_player_name" not in st.session_state: st.session_state.selected_player_name = None

# --- 3. ログイン画面 ---
if not st.session_state.authenticated:
    st.markdown('<div class="full-width-header"><h1>⚽ LOGIN</h1></div>', unsafe_allow_html=True)
    with st.container(border=True):
        u_id = st.text_input("名前（admin または 選手名）")
        u_pw = st.text_input("パスワード", type="password")
        if st.button("ログイン", width="stretch"):
            # 管理者ログイン（secrets.toml参照）
            if u_id == "admin" and u_pw == st.secrets.get("admin_password", "admin123"):
                st.session_state.authenticated = True; st.session_state.user_role = "admin"; st.session_state.user_name = "管理者"; st.rerun()
            
            # 選手ログイン（ハッシュ比較）
            hashed_input = hash_password(u_pw)
            pm = df_players[(df_players["名前"] == u_id) & (df_players["パスワード"].astype(str) == hashed_input)]
            if not pm.empty:
                st.session_state.authenticated = True; st.session_state.user_role = "player"; st.session_state.user_name = u_id; st.rerun()
            else: st.error("ログイン情報が正しくありません")
    st.stop()

# --- 4. 共通ヘッダー表示 ---
st.markdown(f'<div class="full-width-header"><h1>⚽ {st.session_state.user_name} モード</h1></div>', unsafe_allow_html=True)

with st.sidebar:
    st.write(f"👤: **{st.session_state.user_name}**")
    if st.button("ログアウト", key="logout_btn"): st.session_state.authenticated = False; st.rerun()
    st.divider()
    
    # 管理者用：選手マスタの全項目編集ツール
    if st.session_state.user_role == "admin" and not df_players.empty:
        st.header("🛠️ 選手マスタ管理")
        plist = df_players["名前"].tolist()
        s_idx = plist.index(st.session_state.selected_player_name) if st.session_state.selected_player_name in plist else 0
        edit_target = st.selectbox("選手を選択して修正", plist, index=s_idx)
        st.session_state.selected_player_name = edit_target
        
        target_row = df_players[df_players["名前"] == edit_target].iloc[0]
        with st.expander("📝 選手詳細情報を修正"):
            with st.form("edit_master_full"):
                e_na = st.text_input("名前", value=target_row["名前"])
                e_no = st.number_input("背番号", value=int(target_row["背番号"]))
                e_po = st.selectbox("ポジション", ["GK", "DF", "MF", "FW"], index=["GK", "DF", "MF", "FW"].index(target_row["ポジション"]))
                e_hi = st.number_input("身長 (cm)", value=float(target_row["身長"]))
                e_we = st.number_input("体重 (kg)", value=float(target_row["体重"]))
                e_pw = st.text_input("パスワード（変更時のみ入力）", placeholder="未入力ならそのまま")
                if st.form_submit_button("情報を更新する"):
                    idx = df_players[df_players["名前"] == edit_target].index[0]
                    final_pw = hash_password(e_pw) if e_pw else target_row["パスワード"]
                    df_players.loc[idx, ["名前", "背番号", "ポジション", "身長", "体重", "パスワード"]] = [e_na, e_no, e_po, e_hi, e_we, final_pw]
                    df_players.to_csv(MASTER_FILE, index=False, encoding="utf-8-sig"); st.rerun()
        
        if st.button("❌ 選手を完全に削除", type="secondary", use_container_width=True):
            df_players = df_players[df_players["名前"] != edit_target]
            df_players.to_csv(MASTER_FILE, index=False, encoding="utf-8-sig")
            st.session_state.selected_player_name = None; st.rerun()

# --- 5. メインコンテンツ ---

# A. 管理者ビュー
if st.session_state.user_role == "admin":
    col1, col2 = st.columns(2)
    with col1:
        if st.button("➕\n新規選手登録", width="stretch", type="primary" if st.session_state.show_form=="p" else "secondary"):
            st.session_state.show_form = "p" if st.session_state.show_form != "p" else None; st.rerun()
    with col2:
        if st.button("📝\n体調データ入力", width="stretch", type="primary" if st.session_state.show_form=="c" else "secondary"):
            st.session_state.show_form = "c" if st.session_state.show_form != "c" else None; st.rerun()

    # 新規登録（身長・体重含む）
    if st.session_state.show_form == "p":
        with st.form("new_p", clear_on_submit=True):
            st.subheader("👤 選手新規登録")
            c1, c2 = st.columns(2)
            with c1:
                n_na = st.text_input("名前"); n_no = st.number_input("背番号", 1, 99); n_pw = st.text_input("初期PW", "1234")
                n_po = st.selectbox("ポジション", ["GK", "DF", "MF", "FW"])
            with c2:
                n_hi = st.number_input("身長 (cm)", value=170.0); n_we = st.number_input("体重 (kg)", value=60.0); n_up = st.file_uploader("写真を選択")
            if st.form_submit_button("選手を登録する"):
                path = os.path.join(IMAGE_DIR, f"{n_no}_{n_na}.jpg") if n_up else ""
                if n_up: Image.open(n_up).convert("RGB").resize((300, 300)).save(path)
                new_row = {"背番号": n_no, "名前": n_na, "ポジション": n_po, "学年": "高3", "身長": n_hi, "体重": n_we, "画像パス": path, "パスワード": hash_password(n_pw)}
                df_players = pd.concat([df_players, pd.DataFrame([new_row])], ignore_index=True); df_players.to_csv(MASTER_FILE, index=False, encoding="utf-8-sig"); st.rerun()

    # 代行入力（動的痛み入力含む）
    elif st.session_state.show_form == "c":
        with st.container(border=True):
            st.subheader("📝 管理者代行入力")
            c_na = st.selectbox("選手を選択", df_players["名前"].tolist())
            f_col1, f_col2 = st.columns(2)
            with f_col1:
                c_we = st.number_input("体重 (kg)", value=60.0)
                c_pn = st.radio("怪我・痛みの有無", ["いいえ", "はい"], horizontal=True, key="admin_pn")
                c_dt = st.text_input("痛みの詳細") if c_pn == "はい" else ""
            with f_col2:
                c_fa = st.slider("疲労度 (1-5)", 1, 5, 3); c_sl = st.slider("睡眠 (1-5)", 1, 5, 3)
            if st.button("データを保存", width="stretch"):
                new_c = {"日付": date.today(), "名前": c_na, "体重": c_we, "疲労度": c_fa, "睡眠の質": c_sl, "怪我痛み": c_pn, "痛み詳細": c_dt}
                df_cond = pd.concat([df_cond, pd.DataFrame([new_c])], ignore_index=True); df_cond.to_csv(CONDITION_FILE, index=False, encoding="utf-8-sig"); st.success("保存完了"); st.session_state.show_form = None; st.rerun()

    st.markdown("---")
    t1, t2, t3 = st.tabs(["📋 選手名簿", "📈 個別推移・管理", "📊 チーム全体状況"])
    with t1:
        cl = st.columns(4)
        for i, (idx, row) in enumerate(df_players.iterrows()):
            with cl[i%4]:
                with st.container(border=True):
                    if pd.notnull(row['画像パス']) and os.path.exists(str(row['画像パス'])): st.image(str(row['画像パス']), use_container_width=True)
                    else: st.image("https://via.placeholder.com/300x300.png?text=NO+IMAGE", use_container_width=True)
                    st.markdown(f"### #{row['背番号']} {row['名前']}")
                    if st.button(f"詳細：{row['名前']}", key=f"v_{idx}", width="stretch"):
                        st.session_state.selected_player_name = row['名前']; st.rerun()
    with t2:
        if st.session_state.selected_player_name:
            p_name = st.session_state.selected_player_name
            p_data = df_cond[df_cond["名前"] == p_name].sort_values("日付")
            if not p_data.empty:
                st.plotly_chart(px.line(p_data, x="日付", y="体重", title=f"{p_name} 体重推移", markers=True))
                st.plotly_chart(px.line(p_data, x="日付", y=["疲労度", "睡眠の質"], title=f"{p_name} 推移", markers=True, range_y=[0, 6], color_discrete_map=COLOR_MAP))
                with st.expander("🗑️ 過去データを削除"):
                    del_d = st.selectbox("日付を選択", p_data["日付"].unique(), key="admin_del")
                    if st.button("削除実行"):
                        df_cond = df_cond.drop(df_cond[(df_cond["名前"] == p_name) & (df_cond["日付"] == del_d)].index)
                        df_cond.to_csv(CONDITION_FILE, index=False, encoding="utf-8-sig"); st.rerun()
        else: st.info("名簿から選手を選択してください")
    with t3:
        today_data = df_cond[df_cond["日付"] == date.today()]
        alert_p = today_data[(today_data["疲労度"] >= 4) | (today_data["怪我痛み"] == "はい")]
        st.metric("本日の要注意選手", f"{len(alert_p)} 名")
        for _, r in alert_p.iterrows():
            st.error(f"● {r['名前']} - 疲労:{r['疲労度']} / 痛み:{r['怪我痛み']} ({r['痛み詳細']})")
        if not df_cond.empty:
            team_avg = df_cond.groupby("日付")[["疲労度", "睡眠の質"]].mean().reset_index()
            st.plotly_chart(px.line(team_avg, x="日付", y=["疲労度", "睡眠 de質"], title="チーム平均推移", markers=True, range_y=[0, 6], color_discrete_map=COLOR_MAP))

# B. 選手ビュー
else:
    my_info = df_players[df_players["名前"] == st.session_state.user_name].iloc[0]
    
    # 円形プロフィール写真
    img_tag = "https://via.placeholder.com/150"
    b64_img = get_base64_image(str(my_info['画像パス']))
    if b64_img: img_tag = f"data:image/jpeg;base64,{b64_img}"

    st.markdown(f"""
    <div class="profile-container">
        <div class="profile-photo"><img src="{img_tag}" /></div>
        <div class="profile-details">
            <h2>{my_info['名前']} <span style='font-size: 1.2rem; color: #666;'>#{my_info['背番号']}</span></h2>
            <b>ポジション:</b> {my_info['ポジション']} | <b>学年:</b> {my_info['学年']}<br>
            <b>身長:</b> {my_info['身長']}cm | <b>ベスト体重:</b> {my_info['体重']}kg
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 今日の入力
    with st.container(border=True):
        st.subheader("📝 本日の体調を入力")
        p_col1, p_col2 = st.columns(2)
        with p_col1:
            p_we = st.number_input("体重 (kg)", value=float(my_info['体重']), step=0.1)
            p_pn = st.radio("怪我・痛みの有無", ["いいえ", "はい"], horizontal=True, key="p_pn")
            p_dt = st.text_input("痛みの詳細") if p_pn == "はい" else ""
        with p_col2:
            p_fa = st.slider("疲労度 (1:元気 〜 5:激疲れ)", 1, 5, 3)
            p_sl = st.slider("睡眠の質 (1:悪い 〜 5:快眠)", 1, 5, 3)
        if st.button("送信する", width="stretch", type="primary"):
            new_c = {"日付": str(date.today()), "名前": st.session_state.user_name, "体重": p_we, "疲労度": p_fa, "睡眠の質": p_sl, "怪我痛み": p_pn, "痛み詳細": p_dt}
            df_cond = pd.concat([df_cond, pd.DataFrame([new_c])], ignore_index=True); df_cond.to_csv(CONDITION_FILE, index=False, encoding="utf-8-sig"); st.success("送信完了！"); st.rerun()

    # 自分のデータ管理
    st.divider()
    my_data = df_cond[df_cond["名前"] == st.session_state.user_name].sort_values("日付")
    tab_g, tab_m = st.tabs(["📈 推移グラフ", "⚙️ 履歴の削除"])
    with tab_g:
        if not my_data.empty:
            st.plotly_chart(px.line(my_data, x="日付", y="体重", title="体重推移", markers=True))
            st.plotly_chart(px.line(my_data, x="日付", y=["疲労度", "睡眠の質"], title="推移", markers=True, range_y=[0, 6], color_discrete_map=COLOR_MAP))
    with tab_m:
        if not my_data.empty:
            del_d = st.selectbox("削除する日を選択", my_data["日付"].unique(), key="p_del")
            if st.button("削除実行"):
                df_cond = df_cond.drop(df_cond[(df_cond["名前"] == st.session_state.user_name) & (df_cond["日付"] == del_d)].index)
                df_cond.to_csv(CONDITION_FILE, index=False, encoding="utf-8-sig"); st.rerun()