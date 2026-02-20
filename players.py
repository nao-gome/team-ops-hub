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

# ストリーク（連続入力）計算関数（火〜金のみカウント）
def calculate_streak(player_name, df_cond):
    if df_cond.empty or "player_name" not in df_cond.columns:
        return 0
    
    p_cond = df_cond[df_cond["player_name"] == player_name]
    if p_cond.empty:
        return 0
        
    input_dates = set(pd.to_datetime(p_cond["date"]).dt.date)
    today = date.today()
    
    streak = 0
    check_date = today
    
    for _ in range(100):
        if check_date.weekday() in [0, 5, 6]:
            check_date -= timedelta(days=1)
            continue
            
        if check_date in input_dates:
            streak += 1
        else:
            if check_date != today:
                break
                
        check_date -= timedelta(days=1)
        
    return streak

# フィジカルテストのスコア化（サカゲー風0-100スケール）関数
def calculate_physical_score(player_name, df_phys):
    if df_phys.empty or "test_name" not in df_phys.columns:
        return pd.DataFrame()

    latest_phys = df_phys.sort_values("date").drop_duplicates(subset=["player_name", "test_name"], keep="last")
    
    scores = []
    for test in PHYS_TESTS:
        test_data = latest_phys[latest_phys["test_name"] == test]
        if test_data.empty: continue
            
        p_data = test_data[test_data["player_name"] == player_name]
        if p_data.empty: continue
            
        p_val = float(p_data.iloc[0]["value"])
        max_val = float(test_data["value"].max())
        min_val = float(test_data["value"].min())
        
        if max_val == min_val:
            score = 70
        else:
            if "秒" in test:
                score = 100 * (max_val - p_val) / (max_val - min_val)
            else:
                score = 100 * (p_val - min_val) / (max_val - min_val)
        
        score = max(20, min(100, int(score)))
        short_name = test.replace(" (秒)", "").replace(" (cm)", "").replace(" (m)", "")
        scores.append({"テスト": short_name, "スコア": score, "実数値": p_val, "単位": test.split()[-1] if " " in test else ""})
        
    return pd.DataFrame(scores)

# 画像アップロード関数 (完全英数化)
def upload_image_to_supabase(file, prefix="player"):
    try:
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        safe_file_name = f"{prefix}_{timestamp}.jpg"
        bucket_name = "player_images"
        file_bytes = file.getvalue()
        supabase.storage.from_(bucket_name).upload(safe_file_name, file_bytes, {"content-type": file.type, "upsert": "true"})
        res = supabase.storage.from_(bucket_name).get_public_url(safe_file_name)
        if isinstance(res, str): return res
        return getattr(res, 'public_url', str(res))
    except Exception as e:
        st.error(f"画像アップロードエラー: {e}")
        return None

def show_player_image(image_val, width=120):
    if not image_val:
        st.write("No Image")
        return
    if str(image_val).startswith("http"): st.image(image_val, width=width)
    elif os.path.exists(str(image_val)): st.image(image_val, width=width)
    else: st.write("No Image")

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

COLOR_MAP = {"睡眠の質": "#1f77b4", "疲労度": "#d62728"}
PHYS_TESTS = ["30mスプリント (秒)", "プロアジリティ (秒)", "垂直跳び (cm)", "Yo-Yoテスト (m)"]

if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "user_role" not in st.session_state: st.session_state.user_role = None
if "user_name" not in st.session_state: st.session_state.user_name = None

# --- 4. ログイン画面 ---
if not st.session_state.authenticated:
    st.markdown('<div class="full-width-header"><h1>⚽ LOGIN</h1></div>', unsafe_allow_html=True)
    with st.container(border=True):
        # 【追加】ログイン種別の選択
        login_type = st.radio("ログイン種別を選択してください", ["選手", "保護者", "管理者"], horizontal=True)
        
        if login_type == "管理者":
            u_id = st.text_input("管理者ID", value="admin")
        else:
            u_id = st.text_input("選手の名前 (Name)")
            
        u_pw = st.text_input("パスワード", type="password")
        
        if st.button("ログイン", use_container_width=True):
            if login_type == "管理者":
                if u_id == "admin" and u_pw == st.secrets.get("admin_password", "admin123"):
                    st.session_state.authenticated = True
                    st.session_state.user_role = "admin"
                    st.session_state.user_name = "管理者"
                    st.rerun()
                else: 
                    st.error("管理者IDまたはパスワードが違います")
            else:
                h_pw = hash_password(u_pw)
                try:
                    res = supabase.table("players").select("*").eq("name", u_id).eq("password_hash", h_pw).execute()
                    if res.data:
                        st.session_state.authenticated = True
                        # 保護者を選んだ場合は専用のロールを付与
                        st.session_state.user_role = "parent" if login_type == "保護者" else "player"
                        st.session_state.user_name = u_id
                        st.rerun()
                    else: 
                        st.error("名前またはパスワードが違います")
                except Exception as e: 
                    st.error(f"ログインエラー: {e}")
    st.stop()

# --- 5. メイン画面 ---
# 役割に応じたヘッダー表示
if st.session_state.user_role == "admin":
    header_text = f"⚽ {st.session_state.user_name} モード"
elif st.session_state.user_role == "parent":
    header_text = f"⚽ {st.session_state.user_name} 選手の保護者ページ"
else:
    header_text = f"⚽ {st.session_state.user_name} モード"

st.markdown(f'<div class="full-width-header"><h1>{header_text}</h1></div>', unsafe_allow_html=True)

lo_col1, lo_col2 = st.columns([10, 1])
with lo_col1: st.write(f"Login: **{st.session_state.user_name}** ({st.session_state.user_role})")
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
    tabs = st.tabs(["📋 名簿・編集", "👤 新規登録", "📈 分析", "💊 代行入力", "🏆 ランキング", "⏱️ テスト入力"])

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
                            e_name = st.text_input("名前", value=row['name'], key=f"name_edit_{row['id']}")
                            e_num = st.number_input("背番号", value=int(row['number']), step=1)
                            e_pos = st.selectbox("ポジション", ["GK", "DF", "MF", "FW"], index=["GK", "DF", "MF", "FW"].index(row['position']))
                            e_height = st.number_input("身長 (cm)", value=float(row['height']), min_value=100.0, max_value=250.0, step=0.1)
                            e_weight = st.number_input("体重 (kg)", value=float(row['weight']), min_value=30.0, max_value=150.0, step=0.1)
                            e_new_pw = st.text_input("新しいパスワード (変更する場合のみ)", type="password", key=f"pw_edit_{row['id']}")
                            st.caption(f"現在のBMI: {bmi}")

                        if st.form_submit_button("情報を更新"):
                            try:
                                update_data = {"name": e_name, "number": e_num, "position": e_pos, "height": e_height, "weight": e_weight}
                                if e_new_pw: update_data["password_hash"] = hash_password(e_new_pw)
                                if e_img:
                                    url = upload_image_to_supabase(e_img, prefix=f"player_{e_num}")
                                    if url: update_data["image_url"] = url
                                    else: st.stop()
                                supabase.table("players").update(update_data).eq("id", row['id']).execute()
                                st.success(f"{e_name} 選手の情報を更新しました！")
                                st.rerun()
                            except Exception as e: st.error(f"更新エラー: {e}")
                    with st.expander("🗑️ 削除メニュー（注意）"):
                        if st.button("削除を確定する", key=f"del_btn_{row['id']}", type="primary"):
                            supabase.table("players").delete().eq("id", row['id']).execute()
                            st.rerun()

    with tabs[1]:
        st.subheader("👤 新規選手登録")
        with st.form("reg_player", clear_on_submit=True):
            n_name = st.text_input("名前")
            n_num = st.number_input("背番号", step=1, value=10)
            n_pos = st.selectbox("ポジション", ["GK", "DF", "MF", "FW"])
            n_h, n_w = st.number_input("身長 (cm)", 170.0), st.number_input("体重 (kg)", 60.0)
            n_pw, n_img = st.text_input("初期パスワード", "1234"), st.file_uploader("写真 (jpg/png)")
            if st.form_submit_button("登録実行", use_container_width=True):
                if n_name:
                    url = upload_image_to_supabase(n_img, prefix=f"player_{n_num}") if n_img else ""
                    data = {"name": n_name, "number": n_num, "position": n_pos, "height": n_h, "weight": n_w, "password_hash": hash_password(n_pw), "image_url": url}
                    supabase.table("players").insert(data).execute()
                    st.success(f"{n_name} を新規登録しました！")
                    st.rerun()

    with tabs[2]:
        st.subheader("⚠️ 要注意選手アラート (前日比)")
        if not df_cond.empty and "player_name" in df_cond.columns:
            for p in df_cond["player_name"].unique():
                d = df_cond[df_cond["player_name"] == p].sort_values("date")
                if len(d) >= 2:
                    c, pr = d.iloc[-1], d.iloc[-2]
                    r = [k for k, v in {"疲労急増": c["fatigue"]-pr["fatigue"]>=3, "睡眠悪化": pr["sleep"]-c["sleep"]>=3, "体重急減": pr["weight"]-c["weight"]>=1.5}.items() if v]
                    if r: st.error(f"**{p}**: {', '.join(r)}")
            st.divider()
            st.subheader("📊 チーム平均推移")
            df_avg = df_cond.groupby("date")[["fatigue", "sleep"]].mean().reset_index().rename(columns={"fatigue": "疲労度", "sleep": "睡眠の質"})
            st.plotly_chart(px.line(df_avg, x="date", y=["疲労度", "睡眠の質"], range_y=[0, 6], markers=True, color_discrete_map=COLOR_MAP), use_container_width=True)
            st.divider()
            
            st.subheader("👤 個人詳細分析")
            if not df_players.empty:
                target = st.selectbox("分析する選手を選択", df_players["name"].tolist(), key="admin_target")
                p_cond = df_cond[df_cond["player_name"] == target].sort_values("date")
                if not p_cond.empty:
                    st.plotly_chart(px.line(p_cond.rename(columns={"fatigue":"疲労度","sleep":"睡眠の質","weight":"体重"}), x="date", y=["疲労度","睡眠の質"], markers=True, range_y=[0,6], color_discrete_map=COLOR_MAP), use_container_width=True)
                    st.plotly_chart(px.line(p_cond.rename(columns={"weight":"体重"}), x="date", y="体重", markers=True), use_container_width=True)
                p_phys = df_phys[df_phys["player_name"] == target].sort_values("date") if not df_phys.empty and "player_name" in df_phys.columns else pd.DataFrame()
                if not p_phys.empty and "test_name" in p_phys.columns:
                    st.markdown("#### フィジカルテスト履歴")
                    t_kind = st.selectbox("種目を選択", PHYS_TESTS, key="admin_phys_kind")
                    p_test = p_phys[p_phys["test_name"] == t_kind]
                    if not p_test.empty: st.plotly_chart(px.line(p_test, x="date", y="value", markers=True, title=f"{t_kind}の推移"), use_container_width=True)
                    else: st.write("この種目の記録はありません。")

    with tabs[3]:
        st.subheader("💊 コンディション記録代行")
        with st.container(border=True):
            if not df_players.empty:
                p_t = st.selectbox("対象選手", df_players["name"].tolist())
                c1, c2 = st.columns(2)
                with c1:
                    p_w = st.number_input("体重", 60.0)
                    p_i = st.radio("怪我・痛み", ["なし", "あり"], horizontal=True)
                    p_id = st.text_input("痛みの詳細") if p_i == "あり" else ""
                with c2:
                    p_f, p_s = st.slider("疲労", 1, 5, 3), st.slider("睡眠", 1, 5, 3)
                if st.button("代行保存", use_container_width=True):
                    supabase.table("conditions").insert({"player_name": p_t, "date": str(date.today()), "weight": p_w, "fatigue": p_f, "sleep": p_s, "injury": p_i, "injury_detail": p_id}).execute()
                    st.success("保存完了")

    with tabs[4]:
        st.subheader("🏆 フィジカルランキング")
        if not df_phys.empty and "test_name" in df_phys.columns:
            cols = st.columns(2)
            for i, test in enumerate(PHYS_TESTS):
                with cols[i%2]:
                    st.markdown(f"**{test}**")
                    sub = df_phys[df_phys["test_name"] == test]
                    if not sub.empty:
                        st.dataframe(sub.sort_values("value", ascending=("秒" in test)).drop_duplicates("player_name").head(5)[["player_name", "value", "date"]], hide_index=True)

    with tabs[5]:
        st.subheader("⏱️ フィジカルテスト記録入力")
        with st.form("reg_phys", clear_on_submit=True):
            if not df_players.empty:
                t_p = st.selectbox("選手", df_players["name"].tolist())
                t_n, t_v = st.selectbox("種目", PHYS_TESTS), st.number_input("数値", step=0.01)
                t_d = st.date_input("測定日", date.today())
                if st.form_submit_button("保存"):
                    supabase.table("physical_tests").insert({"player_name": t_p, "test_name": t_n, "value": t_v, "date": str(t_d)}).execute()
                    st.success("完了")

# ========== 選手 / 保護者モード ==========
else:
    # 選手モード限定：送信時の風船演出
    if st.session_state.user_role == "player" and st.session_state.get("just_submitted", False):
        st.toast("記録しました！継続は力なり🔥", icon="👏")
        st.balloons()
        st.session_state["just_submitted"] = False

    my_info = df_players[df_players["name"] == st.session_state.user_name].iloc[0]
    img_val = my_info.get("image_url")
    img_src = img_val if (img_val and str(img_val).startswith("http")) else "https://via.placeholder.com/150"
    
    bmi_val = calculate_bmi(my_info['height'], my_info['weight'])
    streak_count = calculate_streak(st.session_state.user_name, df_cond)
    
    streak_color = "#ff4b4b" if streak_count >= 3 else "#ff9900" if streak_count > 0 else "gray"
    streak_text = f"🔥 {streak_count}日連続入力中！(火〜金)" if streak_count > 0 else "連続入力: 0日 (今日からスタート！)"

    st.markdown(f"""
    <div class="profile-container">
        <div class="profile-photo"><img src="{img_src}"></div>
        <div>
            <h2>{my_info['name']} <small>#{my_info['number']}</small></h2>
            <p>{my_info['height']}cm / {my_info['weight']}kg | <b>BMI: {bmi_val}</b> | Pos: {my_info['position']}</p>
            <p style='color: {streak_color}; font-weight: bold; margin-top: 5px; font-size: 1.1em;'>{streak_text}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ロール（選手か保護者か）によって表示するタブを変える
    if st.session_state.user_role == "player":
        tab1, tab2, tab3, tab4 = st.tabs(["📝 コンディション入力", "📊 コンディション履歴", "🔥 パラメーター", "🔐 パスワード"])
    else:
        # 保護者の場合は、入力とパスワード変更タブを隠す
        st.info("💡 保護者モードではデータの閲覧のみ可能です。毎日のコンディション入力は選手本人の画面から行われます。")
        tab2, tab3 = st.tabs(["📊 成長・コンディション履歴", "🔥 身体能力パラメーター"])

    # --- tab1: コンディション入力 (選手のみ) ---
    if st.session_state.user_role == "player":
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
                    st.session_state["just_submitted"] = True
                    st.rerun()

    # --- tab2: コンディション履歴 (共通) ---
    with tab2:
        my_cond = pd.DataFrame()
        if not df_cond.empty and "player_name" in df_cond.columns:
            my_cond = df_cond[df_cond["player_name"] == st.session_state.user_name].sort_values("date")
            
        if not my_cond.empty:
            if len(my_cond) >= 2:
                curr, prev = my_cond.iloc[-1], my_cond.iloc[-2]
                reasons = [k for k, v in {"疲労急増": curr["fatigue"]-prev["fatigue"]>=3, "睡眠悪化": prev["sleep"]-curr["sleep"]>=3, "体重急減": prev["weight"]-curr["weight"]>=1.5}.items() if v]
                if reasons: st.error(f"⚠️ **要注意アラート**: {', '.join(reasons)}。無理をせずコーチやスタッフに相談してください。")
            
            st.markdown("#### コンディション推移")
            st.plotly_chart(px.line(my_cond.rename(columns={"fatigue": "疲労度", "sleep": "睡眠の質", "weight": "体重"}), x="date", y=["疲労度", "睡眠の質"], range_y=[0,6], markers=True, color_discrete_map=COLOR_MAP), use_container_width=True)
            
            st.markdown("#### 体重推移")
            st.plotly_chart(px.line(my_cond.rename(columns={"weight": "体重"}), x="date", y="体重", markers=True), use_container_width=True)
            
            last_w = my_cond.iloc[-1]["weight"]
            prev_w = my_cond.iloc[-2]["weight"] if len(my_cond) >= 2 else my_info['weight']
            target_w = round((my_info['height'] / 100) ** 2 * 22, 1)
            
            m1, m2 = st.columns(2)
            with m1: st.metric("最新体重", f"{last_w} kg", delta=f"{last_w - prev_w:.1f} kg (前回比)")
            with m2: st.metric("目標体重 (U-18/BMI22基準)", f"{target_w} kg", delta=f"{last_w - target_w:.1f} kg (差分)", delta_color="off")

            st.markdown("<br>", unsafe_allow_html=True)
            progress_val = min(last_w / target_w, 1.0) if target_w > 0 else 0.0
            progress_percent = progress_val * 100
            
            st.markdown(f"**🎯 目標体重までの達成度: {progress_percent:.1f}%**")
            st.progress(progress_val)
            
            if progress_val >= 1.0:
                st.success("🎉 目標体重クリア！素晴らしいフィジカルです！")

        else: 
            st.info("データがまだありません。")

    # --- tab3: パラメーター (共通) ---
    with tab3:
        st.subheader("🔥 身体能力パラメーター")
        st.caption("※チーム内の成績をもとにした相対評価（0〜100）です。")
        
        df_radar = calculate_physical_score(st.session_state.user_name, df_phys)
        if not df_radar.empty and len(df_radar) >= 3:
            fig = px.line_polar(df_radar, r='スコア', theta='テスト', line_close=True, range_r=[0, 100])
            fig.update_traces(fill='toself', line_color='#00FFAA', fillcolor='rgba(0, 255, 170, 0.4)')
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("#### 🏃‍♂️ 最新記録")
            st.dataframe(df_radar[["テスト", "実数値", "単位"]], hide_index=True, use_container_width=True)
        elif not df_radar.empty:
            st.info("レーダーチャートを表示するには、あと少しテスト項目が必要です！")
            st.dataframe(df_radar[["テスト", "実数値", "単位"]], hide_index=True)
        else:
            st.info("まだフィジカルテストの記録がありません。測定日をお楽しみに！")

    # --- tab4: パスワード (選手のみ) ---
    if st.session_state.user_role == "player":
        with tab4:
            with st.form("pw_form"):
                curr_pw, new_pw = st.text_input("現在のパスワード", type="password"), st.text_input("新しいパスワード", type="password")
                if st.form_submit_button("更新"):
                    if hash_password(curr_pw) == my_info['password_hash'] and len(new_pw) >= 4:
                        supabase.table("players").update({"password_hash": hash_password(new_pw)}).eq("id", my_info['id']).execute()
                        st.success("完了！")
                    else: 
                        st.error("不備あり")