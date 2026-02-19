import streamlit as st
import pandas as pd
import os
from datetime import date, datetime, timedelta
import plotly.express as px
import hashlib
from supabase import create_client, Client

# --- 1. ページ設定 ---
st.set_page_config(page_title="Team Ops Hub", page_icon="⚽", layout="wide", initial_sidebar_state="collapsed")

# --- 2. Supabase接続設定 ---
try:
    SUPABASE_URL = st.secrets["supabase"]["url"]
    SUPABASE_KEY = st.secrets["supabase"]["key"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"データベース接続エラー: secrets.toml の設定を確認してください。\n{e}")
    st.stop()

# --- 3. 関数定義 ---
def hash_password(password):
    return hashlib.sha256(str(password).encode()).hexdigest()

def fetch_table_as_df(table_name):
    try:
        response = supabase.table(table_name).select("*").order("id").execute()
        df = pd.DataFrame(response.data)
        if not df.empty and "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"]).dt.date
        return df
    except Exception as e:
        return pd.DataFrame()

def calculate_bmi(height_cm, weight_kg):
    if height_cm > 0:
        height_m = height_cm / 100
        return round(weight_kg / (height_m ** 2), 1)
    return 0

# 画像アップロード関数 (完全英数化)
def upload_image_to_supabase(file, prefix="player"):
    try:
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        safe_file_name = f"{prefix}_{timestamp}.jpg"
        
        bucket_name = "player_images"
        file_bytes = file.getvalue()
        
        supabase.storage.from_(bucket_name).upload(
            safe_file_name, 
            file_bytes, 
            {"content-type": file.type, "upsert": "true"}
        )
        
        res = supabase.storage.from_(bucket_name).get_public_url(safe_file_name)
        if isinstance(res, str):
            return res
        return getattr(res, 'public_url', str(res))
    except Exception as e:
        st.error(f"画像アップロードエラー: {e}")
        return None

# 安全に画像を表示するヘルパー関数
def show_player_image(image_val, width=120):
    if not image_val:
        st.write("No Image")
        return
    if str(image_val).startswith("http"):
        st.image(image_val, width=width)
    elif os.path.exists(str(image_val)):
        st.image(image_val, width=width)
    else:
        st.write("No Image")

# カスタムCSS
st.markdown("""
    <style>
    header[data-testid="stHeader"] { display: none !important; }
    section[data-testid="stSidebar"] { display: none; }
    
    .full-width-header {
        background-color: #01579b; color: white; padding: 20px; margin-bottom: 10px;
        display: flex; justify-content: center; align-items: center; border-radius: 0 0 15px 15px;
    }
    .profile-container {
        display: flex; background-color: #f8f9fa; padding: 20px; border-radius: 15px;
        border-left: 10px solid #01579b; margin-bottom: 20px; align-items: center; gap: 20px;
    }
    .profile-photo {
        width: 120px; height: 120px; border-radius: 50%; overflow: hidden;
        background-color: #eee; border: 3px solid #fff; flex-shrink: 0;
        display: flex; justify-content: center; align-items: center;
    }
    .profile-photo img { width: 100%; height: 100%; object-fit: cover; }
    
    div[data-testid="stExpander"] details summary p { font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# 定数
COLOR_MAP = {"睡眠の質": "#1f77b4", "疲労度": "#d62728"}
PHYS_TESTS = ["30mスプリント (秒)", "プロアジリティ (秒)", "垂直跳び (cm)", "Yo-Yoテスト (m)"]

# セッション状態
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "user_role" not in st.session_state: st.session_state.user_role = None
if "user_name" not in st.session_state: st.session_state.user_name = None

# --- 4. ログイン画面 ---
if not st.session_state.authenticated:
    st.markdown('<div class="full-width-header"><h1>⚽ LOGIN</h1></div>', unsafe_allow_html=True)
    with st.container(border=True):
        u_id = st.text_input("名前 (Name)")
        u_pw = st.text_input("パスワード", type="password")
        
        if st.button("ログイン", use_container_width=True):
            if u_id == "admin" and u_pw == st.secrets.get("admin_password", "admin123"):
                st.session_state.authenticated = True
                st.session_state.user_role = "admin"
                st.session_state.user_name = "管理者"
                st.rerun()
            
            h_pw = hash_password(u_pw)
            try:
                res = supabase.table("players").select("*").eq("name", u_id).eq("password_hash", h_pw).execute()
                if res.data:
                    st.session_state.authenticated = True
                    st.session_state.user_role = "player"
                    st.session_state.user_name = u_id
                    st.rerun()
                else:
                    st.error("名前またはパスワードが違います")
            except Exception as e:
                st.error(f"ログインエラー: {e}")
    st.stop()

# --- 5. メイン画面 ---
st.markdown(f'<div class="full-width-header"><h1>⚽ {st.session_state.user_name} モード</h1></div>', unsafe_allow_html=True)

lo_col1, lo_col2 = st.columns([10, 1])
with lo_col1:
    st.write(f"Login: **{st.session_state.user_name}**")
with lo_col2:
    if st.button("ログアウト", key="logout_btn", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

st.divider()

# データ取得
df_players = fetch_table_as_df("players")
df_cond = fetch_table_as_df("conditions")
df_phys = fetch_table_as_df("physical_tests")

# ========== 管理者モード ==========
if st.session_state.user_role == "admin":
    tabs = st.tabs([
        "📋 名簿・編集", 
        "👤 新規登録", 
        "📈 分析", 
        "💊 コンディション代行",
        "🏆 ランキング", 
        "⏱️ フィジカルテスト入力"
    ])

    # 1. 名簿・編集
    with tabs[0]:
        st.subheader("選手情報の編集・更新")
        if not df_players.empty:
            for i, row in df_players.iterrows():
                bmi = calculate_bmi(row['height'], row['weight'])
                with st.expander(f"No.{row['number']} : {row['name']} (Pos: {row['position']})"):
                    with st.form(key=f"edit_form_{row['id']}"):
                        c1, c2 = st.columns([1, 3])
                        with c1:
                            show_player_image(row.get('image_url'))
                            e_img = st.file_uploader("写真を更新", type=["jpg", "png", "jpeg"], key=f"img_up_{row['id']}")
                        with c2:
                            e_num = st.number_input("背番号", value=int(row['number']), step=1)
                            e_pos = st.selectbox("ポジション", ["GK", "DF", "MF", "FW"], index=["GK", "DF", "MF", "FW"].index(row['position']))
                            e_height = st.number_input("身長 (cm)", value=float(row['height']), min_value=100.0, max_value=250.0, step=0.1)
                            e_weight = st.number_input("体重 (kg)", value=float(row['weight']), min_value=30.0, max_value=150.0, step=0.1)
                            e_new_pw = st.text_input("新しいパスワード (変更する場合のみ)", type="password", key=f"pw_edit_{row['id']}")
                            st.caption(f"現在のBMI: {bmi}")

                        if st.form_submit_button("情報を更新"):
                            try:
                                update_data = {
                                    "number": e_num, "position": e_pos,
                                    "height": e_height, "weight": e_weight
                                }
                                if e_new_pw:
                                    update_data["password_hash"] = hash_password(e_new_pw)
                                
                                if e_img:
                                    uploaded_url = upload_image_to_supabase(e_img, prefix=f"player_{e_num}")
                                    if uploaded_url:
                                        update_data["image_url"] = uploaded_url
                                    else:
                                        st.error("画像のアップロードに失敗したため、他の情報の更新を中断しました。")
                                        st.stop()

                                supabase.table("players").update(update_data).eq("id", row['id']).execute()
                                st.success(f"{row['name']} 選手の情報を更新しました！")
                                st.rerun()
                            except Exception as e:
                                st.error(f"更新エラー: {e}")
                    
                    st.divider()
                    with st.expander("🗑️ 削除メニュー（注意）"):
                        st.warning(f"{row['name']} 選手を削除します。")
                        if st.button("削除を確定する", key=f"del_btn_{row['id']}", type="primary"):
                            try:
                                supabase.table("players").delete().eq("id", row['id']).execute()
                                st.success(f"{row['name']} を削除しました。")
                                st.rerun()
                            except Exception as e:
                                st.error(f"削除エラー: {e}")
        else:
            st.info("選手が登録されていません。")

    # 2. 新規登録
    with tabs[1]:
        st.subheader("👤 新規選手登録")
        with st.form("reg_player", clear_on_submit=True):
            n_name = st.text_input("名前")
            n_num = st.number_input("背番号", step=1, value=10)
            n_pos = st.selectbox("ポジション", ["GK", "DF", "MF", "FW"])
            n_h = st.number_input("身長 (cm)", value=170.0, min_value=100.0, max_value=250.0, step=0.1)
            n_w = st.number_input("体重 (kg)", value=60.0, min_value=30.0, max_value=150.0, step=0.1)
            n_pw = st.text_input("初期パスワード", "1234")
            n_img = st.file_uploader("写真 (jpg/png)")
            
            if st.form_submit_button("登録実行", use_container_width=True):
                if n_name:
                    image_url = ""
                    if n_img:
                        uploaded_url = upload_image_to_supabase(n_img, prefix=f"player_{n_num}")
                        if uploaded_url:
                            image_url = uploaded_url
                        else:
                            st.error("画像アップロード失敗のため登録を中止しました。")
                            st.stop()

                    data = {
                        "name": n_name, "number": n_num, "position": n_pos, 
                        "height": n_h, "weight": n_w, 
                        "password_hash": hash_password(n_pw), 
                        "image_url": image_url
                    }
                    try:
                        supabase.table("players").insert(data).execute()
                        st.success(f"{n_name} を新規登録しました！")
                        st.rerun()
                    except Exception as e:
                        st.error(f"登録エラー: {e}")
                else:
                    st.error("名前を入力してください。")

    # 3. 分析
    with tabs[2]:
        st.subheader("⚠️ 要注意選手アラート (前日比)")
        if not df_cond.empty and "player_name" in df_cond.columns:
            alert_players = []
            for player in df_cond["player_name"].unique():
                p_data = df_cond[df_cond["player_name"] == player].sort_values("date")
                if len(p_data) >= 2:
                    curr, prev = p_data.iloc[-1], p_data.iloc[-2]
                    reasons = []
                    if (curr["fatigue"] - prev["fatigue"] >= 3): reasons.append("疲労急増")
                    if (prev["sleep"] - curr["sleep"] >= 3): reasons.append("睡眠悪化")
                    if (prev["weight"] - curr["weight"] >= 1.5): reasons.append("体重急減")
                    if reasons: alert_players.append(f"**{player}**: {', '.join(reasons)}")
            if alert_players:
                for a in alert_players: st.error(a)
            else: st.success("アラートなし")
        else:
            st.info("コンディションデータがまだありません。")
            
        st.divider()
        st.subheader("📊 チーム平均推移")
        if not df_cond.empty and "date" in df_cond.columns and "fatigue" in df_cond.columns:
            df_avg = df_cond.groupby("date")[["fatigue", "sleep"]].mean().reset_index().rename(columns={"fatigue": "疲労度", "sleep": "睡眠の質"})
            st.plotly_chart(px.line(df_avg, x="date", y=["疲労度", "睡眠の質"], range_y=[0, 6], markers=True, color_discrete_map=COLOR_MAP), use_container_width=True)

    # 4. 代行
    with tabs[3]:
        st.subheader("💊 コンディション記録代行")
        with st.container(border=True):
            if not df_players.empty:
                p_target = st.selectbox("対象選手", df_players["name"].tolist(), key="proxy_target")
                c1, c2 = st.columns(2)
                with c1:
                    p_w = st.number_input("体重 (kg)", step=0.1, min_value=30.0, max_value=150.0, key="proxy_w")
                    p_inj = st.radio("怪我・痛み", ["なし", "あり"], horizontal=True, key="proxy_inj")
                    p_inj_dt = st.text_input("痛みの詳細", key="proxy_inj_dt") if p_inj == "あり" else ""
                with c2:
                    p_fat = st.slider("疲労度", 1, 5, 3, key="proxy_fat")
                    p_slp = st.slider("睡眠", 1, 5, 3, key="proxy_slp")
                p_date = st.date_input("対象日", date.today(), key="proxy_date")
                
                if st.button("代行保存", use_container_width=True, key="proxy_submit"):
                    data = {
                        "player_name": p_target, "date": str(p_date), 
                        "weight": p_w, "fatigue": p_fat, "sleep": p_slp, 
                        "injury": p_inj, "injury_detail": p_inj_dt
                    }
                    supabase.table("conditions").insert(data).execute()
                    st.success("保存完了")
            else:
                st.info("選手が登録されていません。")

    # 5. ランキング
    with tabs[4]:
        st.subheader("🏆 フィジカルランキング")
        if not df_phys.empty and "test_name" in df_phys.columns:
            cols = st.columns(2)
            for i, test in enumerate(PHYS_TESTS):
                with cols[i%2]:
                    st.markdown(f"**{test}**")
                    sub = df_phys[df_phys["test_name"] == test]
                    if not sub.empty:
                        rank = sub.sort_values("value", ascending=("秒" in test)).drop_duplicates("player_name").head(5)
                        st.dataframe(rank[["player_name", "value", "date"]], hide_index=True)
                    else:
                        st.write("記録なし")
        else:
            st.info("フィジカルテストのデータがまだありません。")

    # 6. フィジカルテスト
    with tabs[5]:
        st.subheader("⏱️ フィジカルテスト記録入力")
        with st.form("reg_phys", clear_on_submit=True):
            if not df_players.empty:
                t_player = st.selectbox("選手", df_players["name"].tolist())
                t_name = st.selectbox("種目", PHYS_TESTS)
                t_val = st.number_input("数値", step=0.01, min_value=0.0)
                t_date = st.date_input("測定日", date.today())
                if st.form_submit_button("テスト記録を保存"):
                    supabase.table("physical_tests").insert({"player_name": t_player, "test_name": t_name, "value": t_val, "date": str(t_date)}).execute()
                    st.success("記録完了")
            else:
                st.info("選手が登録されていません。")

# ========== 選手モード ==========
else:
    my_info = df_players[df_players["name"] == st.session_state.user_name].iloc[0]
    img_val = my_info.get("image_url")
    img_src = img_val if (img_val and str(img_val).startswith("http")) else "https://via.placeholder.com/150"
    
    bmi_val = calculate_bmi(my_info['height'], my_info['weight'])
    st.markdown(f"""
    <div class="profile-container">
        <div class="profile-photo"><img src="{img_src}"></div>
        <div>
            <h2>{my_info['name']} <small>#{my_info['number']}</small></h2>
            <p>{my_info['height']}cm / {my_info['weight']}kg | <b>BMI: {bmi_val}</b> | Pos: {my_info['position']}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["📝 コンディション入力", "📊 履歴", "🔐 パスワード"])

    with tab1:
        with st.container(border=True):
            c1, c2 = st.columns(2)
            with c1:
                in_w = st.number_input("今日の体重 (kg)", value=float(my_info['weight']), step=0.1, min_value=30.0, max_value=150.0, key="daily_w")
                in_inj = st.radio("怪我・痛み", ["なし", "あり"], horizontal=True, key="daily_inj")
                in_inj_dt = st.text_input("痛みの詳細", key="daily_inj_dt") if in_inj == "あり" else ""
            with c2:
                in_fat = st.slider("疲労度 (1-5)", 1, 5, 3, key="daily_fat")
                in_slp = st.slider("睡眠 (1-5)", 1, 5, 3, key="daily_slp")
                
            if st.button("送信", use_container_width=True, key="daily_submit"):
                data = {
                    "player_name": st.session_state.user_name, "date": str(date.today()), 
                    "weight": in_w, "fatigue": in_fat, "sleep": in_slp, 
                    "injury": in_inj, "injury_detail": in_inj_dt
                }
                supabase.table("conditions").insert(data).execute()
                st.success("記録しました！")

    with tab2:
        my_cond = pd.DataFrame()
        if not df_cond.empty and "player_name" in df_cond.columns:
            my_cond = df_cond[df_cond["player_name"] == st.session_state.user_name].sort_values("date")
            
        if not my_cond.empty:
            # --- 選手自身へのアラート表示 ---
            if len(my_cond) >= 2:
                curr = my_cond.iloc[-1]
                prev = my_cond.iloc[-2]
                reasons = []
                if (curr["fatigue"] - prev["fatigue"] >= 3): reasons.append("疲労急増")
                if (prev["sleep"] - curr["sleep"] >= 3): reasons.append("睡眠悪化")
                if (prev["weight"] - curr["weight"] >= 1.5): reasons.append("体重急減")
                
                if reasons:
                    st.error(f"⚠️ **要注意アラート**: {', '.join(reasons)}。無理をせずコーチやスタッフに相談してください。")
            
            # --- コンディション推移グラフ ---
            st.markdown("#### コンディション推移")
            my_cond_plot = my_cond.rename(columns={"fatigue": "疲労度", "sleep": "睡眠の質", "weight": "体重"})
            st.plotly_chart(px.line(my_cond_plot, x="date", y=["疲労度", "睡眠の質"], range_y=[0,6], markers=True, color_discrete_map=COLOR_MAP), use_container_width=True)
            
            # --- 体重推移グラフ ---
            st.markdown("#### 体重推移")
            st.plotly_chart(px.line(my_cond_plot, x="date", y="体重", markers=True), use_container_width=True)
            
            # --- 最新体重とJFA目標体重の表示 ---
            last_w = my_cond.iloc[-1]["weight"]
            prev_w = my_cond.iloc[-2]["weight"] if len(my_cond) >= 2 else my_info['weight']
            height_m = my_info['height'] / 100
            target_w = round(height_m ** 2 * 22, 1)  # JFA U-18基準 (BMI 22)
            
            m1, m2 = st.columns(2)
            with m1: 
                st.metric("最新体重", f"{last_w} kg", delta=f"{last_w - prev_w:.1f} kg (前回比)")
            with m2: 
                st.metric("目標体重 (U-18/BMI22基準)", f"{target_w} kg", delta=f"{last_w - target_w:.1f} kg (差分)", delta_color="off")
                
        else: 
            st.info("データがまだありません。「📝 コンディション入力」から今日の状態を送信してください！")

    with tab3:
        with st.form("pw_form"):
            curr_pw = st.text_input("現在のパスワード", type="password")
            new_pw = st.text_input("新しいパスワード", type="password")
            if st.form_submit_button("更新"):
                if hash_password(curr_pw) == my_info['password_hash'] and len(new_pw) >= 4:
                    
                    supabase.table("players").update(
                        {"password_hash": hash_password(new_pw)}
                    ).eq("id", my_info['id']).execute()
                    
                    st.success("完了！")
                else: 
                    st.error("不備あり")