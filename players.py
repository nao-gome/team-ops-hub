import streamlit as st
import pandas as pd
import os
from PIL import Image
from datetime import date, timedelta
import plotly.express as px
import base64
import hashlib

# --- 0. セキュリティ関数 ---
def hash_password(password):
    """パスワードをSHA-256でハッシュ化して保護"""
    return hashlib.sha256(str(password).encode()).hexdigest()

# --- 1. ページ設定 ---
st.set_page_config(page_title="選手コンディション管理", page_icon="⚽", layout="wide")

def get_base64_image(image_path):
    if os.path.exists(str(image_path)):
        with open(image_path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    return None

# カスタムCSS
st.markdown("""
    <style>
    header[data-testid="stHeader"] { display: none !important; }
    .block-container { padding-top: 0 !important; }
    .full-width-header {
        background-color: #01579b; color: white; width: 100vw; position: relative;
        left: 50%; right: 50%; margin-left: -50vw; margin-right: -50vw; margin-bottom: 2rem;
        box-shadow: 0 4px 10px rgba(0,0,0,0.3); display: flex; justify-content: center; align-items: center; min-height: 120px;
    }
    .full-width-header h1 { margin: 0 !important; font-size: 2.8rem; font-weight: 800; letter-spacing: 0.15em; }
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
    div.stButton > button { height: 100px; font-size: 22px !important; font-weight: 800 !important; border-radius: 12px; }
    button[kind="primary"] { background-color: #e1f5fe !important; color: #01579b !important; border-color: #81d4fa !important; }
    .leaderboard-card {
        background-color: #ffffff; padding: 12px; border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-bottom: 8px; border-top: 4px solid #01579b;
    }
    .bmi-box {
        margin-bottom: 20px; padding: 20px; background: #e3f2fd; border-radius: 12px; 
        border: 2px solid #01579b; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. データ準備 ---
MASTER_FILE, CONDITION_FILE, PHYSICAL_FILE = "player_master.csv", "daily_condition.csv", "physical_tests.csv"
IMAGE_DIR = "player_images"
if not os.path.exists(IMAGE_DIR): os.makedirs(IMAGE_DIR)

if os.path.exists(MASTER_FILE):
    df_players = pd.read_csv(MASTER_FILE)
    if not df_players.empty and len(str(df_players.iloc[0]["パスワード"])) != 64:
        df_players["パスワード"] = df_players["パスワード"].apply(hash_password)
        df_players.to_csv(MASTER_FILE, index=False, encoding="utf-8-sig")
else: df_players = pd.DataFrame(columns=["背番号", "名前", "ポジション", "学年", "身長", "体重", "画像パス", "パスワード"])

df_cond = pd.read_csv(CONDITION_FILE) if os.path.exists(CONDITION_FILE) else pd.DataFrame(columns=["日付", "名前", "体重", "疲労度", "睡眠の質", "怪我痛み", "痛み詳細"])
if not df_cond.empty: df_cond["日付"] = pd.to_datetime(df_cond["日付"]).dt.date

df_phys = pd.read_csv(PHYSICAL_FILE) if os.path.exists(PHYSICAL_FILE) else pd.DataFrame(columns=["日付", "名前", "テスト種目", "数値"])
if not df_phys.empty: df_phys["日付"] = pd.to_datetime(df_phys["日付"]).dt.date

COLOR_MAP = {"睡眠の質": "#1f77b4", "疲労度": "#d62728"} #
PHYS_TESTS = ["30mスプリント (秒)", "プロアジリティ (秒)", "垂直跳び (cm)", "Yo-Yoテスト (m)"]

if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "user_role" not in st.session_state: st.session_state.user_role = None
if "user_name" not in st.session_state: st.session_state.user_name = None
if "show_form" not in st.session_state: st.session_state.show_form = None
if "selected_player_name" not in st.session_state: st.session_state.selected_player_name = None

# --- 3. ログイン画面 ---
if not st.session_state.authenticated:
    st.markdown('<div class="full-width-header"><h1>⚽ LOGIN</h1></div>', unsafe_allow_html=True)
    with st.container(border=True):
        u_id = st.text_input("名前")
        u_pw = st.text_input("パスワード", type="password")
        if st.button("ログイン", width="stretch"):
            if u_id == "admin" and u_pw == st.secrets.get("admin_password", "admin123"):
                st.session_state.authenticated, st.session_state.user_role, st.session_state.user_name = True, "admin", "管理者"; st.rerun()
            h_pw = hash_password(u_pw)
            pm = df_players[(df_players["名前"] == u_id) & (df_players["パスワード"].astype(str) == h_pw)]
            if not pm.empty:
                st.session_state.authenticated, st.session_state.user_role, st.session_state.user_name = True, "player", u_id; st.rerun()
            else: st.error("ログイン情報が正しくありません")
    st.stop()

# --- 4. 共通ヘッダー ---
st.markdown(f'<div class="full-width-header"><h1>⚽ {st.session_state.user_name} モード</h1></div>', unsafe_allow_html=True)

# --- 5. サイドバー (管理者機能) ---
with st.sidebar:
    st.write(f"👤: **{st.session_state.user_name}**")
    if st.button("ログアウト", key="lo_btn"): st.session_state.authenticated = False; st.rerun()
    st.divider()
    if st.session_state.user_role == "admin" and not df_players.empty:
        st.header("🛠️ 選手・テスト管理")
        plist = df_players["名前"].tolist()
        s_idx = plist.index(st.session_state.selected_player_name) if st.session_state.selected_player_name in plist else 0
        edit_target = st.selectbox("選手を選択", plist, index=s_idx)
        st.session_state.selected_player_name = edit_target
        row = df_players[df_players["名前"] == edit_target].iloc[0]
        
        with st.expander("📝 プロフィール修正(5項目)"):
            with st.form("edit_p"):
                e_na = st.text_input("名前", row["名前"])
                e_no = st.number_input("背番号", value=int(row["背番号"]))
                e_hi = st.number_input("身長 (cm)", value=float(row["身長"]))
                e_we = st.number_input("体重 (kg)", value=float(row["体重"]))
                e_pw = st.text_input("新パスワード(変更時のみ)")
                if st.form_submit_button("選手情報を更新"):
                    idx = df_players[df_players["名前"] == edit_target].index[0]
                    final_pw = hash_password(e_pw) if e_pw else row["パスワード"]
                    df_players.loc[idx, ["名前","背番号","身長","体重","パスワード"]] = [e_na, e_no, e_hi, e_we, final_pw]
                    df_players.to_csv(MASTER_FILE, index=False, encoding="utf-8-sig"); st.rerun()

        with st.expander("🏆 フィジカルテスト記録入力"):
            with st.form("add_ph"):
                t_t, t_v, t_d = st.selectbox("種目", PHYS_TESTS), st.number_input("数値", step=0.01), st.date_input("測定日")
                if st.form_submit_button("保存"):
                    new_ph = pd.DataFrame([{"日付": t_d, "名前": edit_target, "テスト種目": t_t, "数値": t_v}])
                    df_phys = pd.concat([df_phys, new_ph], ignore_index=True); df_phys.to_csv(PHYSICAL_FILE, index=False); st.success("保存完了"); st.rerun()

# --- 6. メインコンテンツ ---
if st.session_state.user_role == "admin":
    # 管理者ビュー
    col1, col2 = st.columns(2)
    with col1:
        if st.button("➕\n新規選手登録", width="stretch", key="btn_reg"):
            st.session_state.show_form = "p" if st.session_state.show_form != "p" else None; st.rerun()
    with col2:
        if st.button("📝\n体調代行入力", width="stretch", key="btn_cond"):
            st.session_state.show_form = "c" if st.session_state.show_form != "c" else None; st.rerun()
    
    # 登録・代行入力フォームの表示
    if st.session_state.show_form == "p":
        with st.form("new_p", clear_on_submit=True):
            st.subheader("👤 選手新規登録")
            c1, c2 = st.columns(2)
            with c1:
                n_na, n_no, n_pw = st.text_input("名前"), st.number_input("番号", 1, 99), st.text_input("PW", "1234")
            with c2:
                n_po, n_hi, n_we = st.selectbox("Pos", ["GK","DF","MF","FW"]), st.number_input("身長", 170.0), st.number_input("体重", 60.0); n_up = st.file_uploader("写真を選択")
            if st.form_submit_button("登録"):
                path = os.path.join(IMAGE_DIR, f"{n_no}_{n_na}.jpg") if n_up else ""
                if n_up: Image.open(n_up).convert("RGB").resize((300, 300)).save(path)
                new_entry = pd.DataFrame([{"背番号":n_no,"名前":n_na,"ポジション":n_po,"学年":"高3","身長":n_hi,"体重":n_we,"画像パス":path,"パスワード":hash_password(n_pw)}])
                df_players = pd.concat([df_players, new_entry], ignore_index=True); df_players.to_csv(MASTER_FILE, index=False, encoding="utf-8-sig"); st.session_state.show_form=None; st.rerun()

    elif st.session_state.show_form == "c":
        with st.container(border=True):
            st.subheader("📝 管理者代行入力")
            c_na = st.selectbox("選手を選択", df_players["名前"].tolist())
            f_col1, f_col2 = st.columns(2)
            with f_col1:
                c_we = st.number_input("本日の体重 (kg)", value=60.0, step=0.1)
                c_pn = st.radio("怪我・痛みの有無", ["いいえ", "はい"], horizontal=True, key="admin_pn")
                c_dt = st.text_input("痛みの詳細") if c_pn == "はい" else ""
            with f_col2:
                c_fa, c_sl = st.slider("疲労度 (1-5)", 1, 5, 3), st.slider("睡眠 (1-5)", 1, 5, 3)
            if st.button("データを保存", width="stretch"):
                new_c = pd.DataFrame([{"日付": date.today(), "名前": c_na, "体重": c_we, "疲労度": c_fa, "睡眠の質": c_sl, "怪我痛み": c_pn, "痛み詳細": c_dt}])
                df_cond = pd.concat([df_cond, new_c], ignore_index=True); df_cond.to_csv(CONDITION_FILE, index=False, encoding="utf-8-sig"); st.success("保存完了"); st.session_state.show_form = None; st.rerun()

    st.markdown("---")
    t1, t2, t3, t4, t5 = st.tabs(["📋 選手名簿", "📈 個別推移管理", "📊 チーム状況", "🏆 フィジカルテストボード", "✅ 未入力者"])
    
    with t1:
        cls = st.columns(4)
        for i, (idx, row) in enumerate(df_players.iterrows()):
            with cls[i%4]:
                with st.container(border=True):
                    if pd.notnull(row['画像パス']) and os.path.exists(str(row['画像パス'])): st.image(str(row['画像パス']), use_container_width=True)
                    st.markdown(f"### #{row['背番号']} {row['名前']}")
                    if st.button(f"詳細：{row['名前']}", key=f"v_{idx}", width="stretch"): st.session_state.selected_player_name = row['名前']; st.rerun()
    with t2:
        if st.session_state.selected_player_name:
            p_n = st.session_state.selected_player_name
            p_c = df_cond[df_cond["名前"] == p_n].sort_values("日付")
            st.write(f"### {p_n} 選手の分析データ")
            if not p_c.empty: st.plotly_chart(px.line(p_c, x="日付", y=["疲労度", "睡眠の質"], title="体調推移", markers=True, range_y=[0,6], color_discrete_map=COLOR_MAP))
            p_ph = df_phys[df_phys["名前"] == p_n].sort_values("日付")
            if not p_ph.empty:
                t_s = st.selectbox("種目", PHYS_TESTS)
                st.plotly_chart(px.line(p_ph[p_ph["テスト種目"]==t_s], x="日付", y="数値", title=f"{t_s}推移", markers=True))
            with st.expander("🗑️ 削除"):
                cat = st.radio("種類", ["体調","テスト"], horizontal=True, key="admin_del_cat")
                if cat=="体調" and not p_c.empty:
                    d_d = st.selectbox("日付", p_c["日付"].unique(), key="dc_admin")
                    if st.button("体調削除"): df_cond = df_cond.drop(df_cond[(df_cond["名前"]==p_n)&(df_cond["日付"]==d_d)].index); df_cond.to_csv(CONDITION_FILE, index=False); st.rerun()
                elif cat=="テスト" and not p_ph.empty:
                    d_i = st.selectbox("記録", p_ph.index, format_func=lambda x: f"{p_ph.loc[x,'日付']} {p_ph.loc[x,'テスト種目']}", key="dp_admin")
                    if st.button("テスト削除"): df_phys = df_phys.drop(d_i); df_phys.to_csv(PHYSICAL_FILE, index=False); st.rerun()
        else: st.info("選手名簿から選手を選択してください")

    with t3:
        st.subheader("🚨 本日のアラート")
        today = date.today()
        today_c = df_cond[df_cond["日付"]==today]
        alert_fatigue = today_c[(today_c["疲労度"]>=4)|(today_c["怪我痛み"]=="はい")]
        weight_alerts = []
        for _, r in today_c.iterrows():
            past = df_cond[(df_cond["名前"] == r["名前"]) & (df_cond["日付"] < today)].sort_values("日付")
            if not past.empty:
                lw = past.iloc[-1]["体重"]
                dr = ((lw - r["体重"]) / lw) * 100
                if dr >= 2.0: weight_alerts.append({"名前": r["名前"], "率": dr, "現": r["体重"], "前": lw})
        st.metric("要注意選手", f"{len(alert_fatigue) + len(weight_alerts)}名")
        for _, r in alert_fatigue.iterrows(): st.error(f"● {r['名前']} - 疲労:{r['疲労度']} / 痛み:{r['怪我痛み']} ({r['痛み詳細']})")
        for wa in weight_alerts: st.warning(f"⚠️ {wa['名前']} - **急激な体重減少 ({wa['率']:.1f}%)** [現:{wa['現']}kg / 前:{wa['前']}kg]")
        if not df_cond.empty:
            tavg = df_cond.groupby("日付")[["疲労度", "睡眠の質"]].mean().reset_index()
            st.plotly_chart(px.line(tavg, x="日付", y=["疲労度", "睡眠の質"], title="チーム平均コンディション", markers=True, range_y=[0, 6], color_discrete_map=COLOR_MAP))
    with t4:
        st.subheader("🏆 フィジカルランキング & 成長分析")
        lcls = st.columns(4)
        for i, test in enumerate(PHYS_TESTS):
            with lcls[i]:
                st.markdown(f"#### {test}")
                td = df_phys[df_phys["テスト種目"]==test]
                if not td.empty:
                    asc = True if "秒" in test else False
                    rank = td.sort_values("数値", ascending=asc).drop_duplicates("名前").head(5)
                    for rk, (_, r) in enumerate(rank.iterrows(), 1):
                        hist = td[td["名前"]==r['名前']].sort_values("日付")
                        gt = ""
                        if len(hist)>=2:
                            diff = hist.iloc[-1]["数値"] - hist.iloc[-2]["数値"]
                            clr = "green" if (diff<0 if asc else diff>0) else "red"
                            gt = f" <span style='color:{clr}; font-size:0.8rem;'>({'+' if diff>0 else ''}{diff:.2f})</span>"
                        st.markdown(f'<div class="leaderboard-card"><b>{rk}位: {r["名前"]}</b><br><span style="font-size:1.2rem; color:#01579b;">{r["数値"]}</span>{gt}</div>', unsafe_allow_html=True)
    with t5:
        sub = df_cond[df_cond["日付"]==date.today()]["名前"].tolist()
        not_s = [p for p in df_players["名前"].tolist() if p not in sub]
        if not not_s: st.success("全員入力済です！")
        else:
            cs = st.columns(4)
            for i, n in enumerate(not_s):
                with cs[i%4]: st.warning(f"・ {n}")

else:
    # 選手ビュー
    my_info = df_players[df_players["名前"] == st.session_state.user_name].iloc[0]
    img_tag = "https://via.placeholder.com/150"
    b64 = get_base64_image(str(my_info['画像パス']))
    if b64: img_tag = f"data:image/jpeg;base64,{b64}"
    st.markdown(f'<div class="profile-container"><div class="profile-photo"><img src="{img_tag}" /></div><div class="profile-details"><h2>{my_info["名前"]} <span style="font-size:1.2rem; color:#666;">#{my_info["背番号"]}</span></h2><b>身長:</b> {my_info["身長"]}cm | <b>体重:</b> {my_info["体重"]}kg</div></div>', unsafe_allow_html=True)
    tp1, tp2, tp3 = st.tabs(["📝 今日の体調入力", "📈 自分の履歴", "🏆 ランキング"])
    with tp1:
        latest_c = df_cond[df_cond["名前"] == st.session_state.user_name].sort_values("日付", ascending=False)
        cur_w = latest_c.iloc[0]["体重"] if not latest_c.empty else my_info['体重']
        with st.container(border=True):
            p_c1, p_c2 = st.columns(2)
            with p_c1:
                p_we = st.number_input("体重 (kg)", value=float(cur_w), step=0.1)
                p_pn = st.radio("怪我・痛み", ["いいえ", "はい"], horizontal=True, key="p_pn_user")
                p_dt = st.text_input("詳細") if p_pn == "はい" else ""
            with p_c2:
                p_fa, p_sl = st.slider("疲労度", 1, 5, 3), st.slider("睡眠", 1, 5, 3)
            if st.button("送信", width="stretch", type="primary"):
                n_c = pd.DataFrame([{"日付": date.today(), "名前": st.session_state.user_name, "体重": p_we, "疲労度": p_fa, "睡眠の質": p_sl, "怪我痛み": p_pn, "痛み詳細": p_dt}])
                df_cond = pd.concat([df_cond, n_c], ignore_index=True); df_cond.to_csv(CONDITION_FILE, index=False, encoding="utf-8-sig"); st.success("完了"); st.rerun()
    with tp2:
        mc = df_cond[df_cond["名前"]==st.session_state.user_name].sort_values("日付")
        if not mc.empty:
            hm = my_info['身長']/100; lw = mc.iloc[-1]["体重"]; bmi = lw/(hm**2); t_min, t_max = 21.0, 23.0; w_min, w_max = t_min*(hm**2), t_max*(hm**2)
            st_txt, s_clr, t_msg = ("適正", "#28a745", "維持しましょう") if t_min <= bmi <= t_max else (("低め", "orange", f"目標:あと+{w_min-lw:.1f}kg") if bmi < t_min else ("高め", "#FF4B4B", f"目標:あと-{lw-w_max:.1f}kg"))
            st.markdown(f'<div class="bmi-box"><h4 style="margin:0; color:#01579b;">📊 BMI判定 (本日:{lw}kg)</h4><span style="font-size:1.8rem; font-weight:bold; color:{s_clr};">{bmi:.1f}</span> <span style="font-size:1.2rem; font-weight:bold; color:{s_clr};">{st_txt}</span><br><p style="margin:10px 0; background:white; padding:10px; border-radius:5px;">{t_msg}</p></div>', unsafe_allow_html=True)
            st.plotly_chart(px.line(mc, x="日付", y=["疲労度", "睡眠の質"], title="体調推移", markers=True, range_y=[0,6], color_discrete_map=COLOR_MAP), use_container_width=True)
        mp = df_phys[df_phys["名前"]==st.session_state.user_name].sort_values("日付")
        if not mp.empty:
            st.markdown("---"); ut = st.selectbox("種目", PHYS_TESTS, key="us_t")
            st.plotly_chart(px.line(mp[mp["テスト種目"]==ut], x="日付", y="数値", title=f"{ut}推移", markers=True), use_container_width=True)
        with st.expander("⚙️ 削除"):
            udcat = st.radio("削除対象", ["体調","テスト"], horizontal=True, key="ud_u")
            if udcat=="体調" and not mc.empty:
                ud = st.selectbox("日付", mc["日付"].unique(), key="ud_u_d")
                if st.button("体調削除"): df_cond = df_cond.drop(df_cond[(df_cond["名前"]==st.session_state.user_name)&(df_cond["日付"]==ud)].index); df_cond.to_csv(CONDITION_FILE, index=False); st.rerun()
            elif udcat=="テスト" and not mp.empty:
                ui = st.selectbox("テスト記録", mp.index, format_func=lambda x: f"{mp.loc[x,'日付']} {mp.loc[x,'テスト種目']}", key="ui_u_d")
                if st.button("テスト削除"): df_phys = df_phys.drop(ui); df_phys.to_csv(PHYSICAL_FILE, index=False); st.rerun()
    with tp3:
        st.subheader("🏆 ランキング")
        lcls = st.columns(4)
        for i, test in enumerate(PHYS_TESTS):
            with lcls[i]:
                td = df_phys[df_phys["テスト種目"]==test]
                if not td.empty:
                    asc = True if "秒" in test else False; top = td.sort_values("数値", ascending=asc).iloc[0]; st.metric("1位", top["名前"], f"{top['数値']}")
                    myh = td[td["名前"]==st.session_state.user_name].sort_values("日付")
                    if not myh.empty:
                        cur = myh.iloc[-1]["数値"]
                        if len(myh)>=2:
                            diff = cur - myh.iloc[-2]["数値"]
                            st.metric("あなた", f"{cur}", delta=f"{diff:.2f}", delta_color="normal" if (diff<0 if asc else diff>0) else "inverse")
                        else: st.write(f"最新: {cur}")