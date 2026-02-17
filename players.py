import streamlit as st
import pandas as pd
import os
from PIL import Image
from datetime import date, datetime
import plotly.express as px
import base64
import hashlib
from supabase import create_client, Client

# --- 1. ページ設定 (必ず一番最初に書く) ---
st.set_page_config(page_title="Team Ops Hub", page_icon="⚽", layout="wide")

# --- 2. Supabase接続設定 ---
# secrets.toml から設定を読み込む
try:
    SUPABASE_URL = st.secrets["supabase"]["url"]
    SUPABASE_KEY = st.secrets["supabase"]["key"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"データベース接続エラー: secrets.toml の設定を確認してください。\n{e}")
    st.stop()

# --- 3. 関数定義 ---
def hash_password(password):
    """パスワードをハッシュ化"""
    return hashlib.sha256(str(password).encode()).hexdigest()

def get_base64_image(image_path):
    if image_path and os.path.exists(str(image_path)):
        with open(image_path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    return None

def fetch_table_as_df(table_name):
    """Supabaseから全データを取得してDataFrameにする"""
    try:
        # ID順に並べて取得
        response = supabase.table(table_name).select("*").order("id").execute()
        df = pd.DataFrame(response.data)
        # 日付カラムがあればdatetime型に変換
        if not df.empty and "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"]).dt.date
        return df
    except Exception as e:
        return pd.DataFrame()

# カスタムCSS
st.markdown("""
    <style>
    header[data-testid="stHeader"] { display: none !important; }
    .full-width-header {
        background-color: #01579b; color: white; padding: 20px; margin-bottom: 20px;
        display: flex; justify-content: center; align-items: center; border-radius: 0 0 15px 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .full-width-header h1 { margin: 0; font-size: 2rem; font-weight: 800; }
    .profile-container {
        display: flex; background-color: #f8f9fa; padding: 20px; border-radius: 15px;
        border-left: 10px solid #01579b; margin-bottom: 20px; align-items: center; gap: 20px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .profile-photo {
        width: 120px; height: 120px; border-radius: 50%; overflow: hidden;
        background-color: #eee; border: 3px solid #fff; flex-shrink: 0;
        display: flex; justify-content: center; align-items: center;
    }
    .profile-photo img { width: 100%; height: 100%; object-fit: cover; }
    </style>
    """, unsafe_allow_html=True)

# 定数
COLOR_MAP = {"sleep": "#1f77b4", "fatigue": "#d62728"}
PHYS_TESTS = ["30mスプリント (秒)", "プロアジリティ (秒)", "垂直跳び (cm)", "Yo-Yoテスト (m)"]
IMAGE_DIR = "player_images"
if not os.path.exists(IMAGE_DIR): os.makedirs(IMAGE_DIR)

# セッション状態の初期化
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "user_role" not in st.session_state: st.session_state.user_role = None
if "user_name" not in st.session_state: st.session_state.user_name = None

# --- 4. ログイン画面 ---
if not st.session_state.authenticated:
    st.markdown('<div class="full-width-header"><h1>⚽ LOGIN</h1></div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.info("初回は管理者(admin)でログインして選手を登録してください")
        u_id = st.text_input("名前 (Name)")
        u_pw = st.text_input("パスワード", type="password")
        
        if st.button("ログイン", use_container_width=True):
            # A. 管理者ログイン (secrets.tomlのパスワードを使用)
            if u_id == "admin" and u_pw == st.secrets.get("admin_password", "admin123"):
                st.session_state.authenticated = True
                st.session_state.user_role = "admin"
                st.session_state.user_name = "管理者"
                st.rerun()
            
            # B. 選手ログイン (SupabaseのDBと照合)
            h_pw = hash_password(u_pw)
            try:
                # 名前とハッシュ化パスワードが一致する選手を探す
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

# --- 5. メイン画面 (ログイン後) ---
st.markdown(f'<div class="full-width-header"><h1>⚽ {st.session_state.user_name} モード</h1></div>', unsafe_allow_html=True)

# サイドバー（ログアウト機能）
with st.sidebar:
    st.write(f"Login: **{st.session_state.user_name}**")
    if st.button("ログアウト"):
        st.session_state.authenticated = False
        st.rerun()

# データを最新状態で取得（毎回DBからロード）
df_players = fetch_table_as_df("players")
df_cond = fetch_table_as_df("conditions")
df_phys = fetch_table_as_df("physical_tests")

# ========== 管理者モード ==========
if st.session_state.user_role == "admin":
    # タブ設定
    t1, t2, t3, t4 = st.tabs(["📋 選手名簿", "📈 分析", "🏆 ランキング", "🛠️ 登録・入力"])

    # 1. 選手名簿 & 削除
    with t1:
        st.subheader("登録選手一覧")
        if not df_players.empty:
            for i, row in df_players.iterrows():
                # カード形式で表示
                with st.expander(f"#{row['number']} {row['name']} ({row['position']})"):
                    c1, c2 = st.columns([1, 3])
                    with c1:
                        # 画像表示（ローカルにあれば）
                        if row.get('image_url') and os.path.exists(row['image_url']):
                            st.image(row['image_url'])
                        else:
                            st.write("No Image")
                    with c2:
                        st.write(f"身長: {row['height']}cm / 体重: {row['weight']}kg")
                        st.caption(f"登録日: {str(row['created_at'])[:10]}")
                        
                        # 削除ボタン
                        if st.button("この選手を削除", key=f"del_{row['id']}"):
                            # DBから削除 (Cascade設定済みなので関連データも消える)
                            try:
                                supabase.table("players").delete().eq("name", row['name']).execute()
                                st.success(f"{row['name']} を削除しました")
                                st.rerun()
                            except Exception as e:
                                st.error(f"削除エラー: {e}")
        else:
            st.info("選手がまだ登録されていません。「登録・入力」タブから追加してください。")

    # 2. データ分析
    with t2:
        if not df_players.empty:
            target = st.selectbox("分析する選手を選択", df_players["name"].tolist())
            
            # 体調グラフ
            p_cond = df_cond[df_cond["player_name"] == target].sort_values("date") if not df_cond.empty else pd.DataFrame()
            if not p_cond.empty:
                st.markdown("##### コンディション推移")
                st.plotly_chart(px.line(p_cond, x="date", y=["fatigue", "sleep"], markers=True, range_y=[0,6], color_discrete_map=COLOR_MAP))
            else:
                st.info("体調データがありません")

            # テストグラフ
            p_phys = df_phys[df_phys["player_name"] == target].sort_values("date") if not df_phys.empty else pd.DataFrame()
            if not p_phys.empty:
                st.markdown("##### フィジカルテスト推移")
                t_kind = st.selectbox("種目を選択", PHYS_TESTS)
                p_test = p_phys[p_phys["test_name"] == t_kind]
                if not p_test.empty:
                    st.plotly_chart(px.line(p_test, x="date", y="value", markers=True, title=t_kind))
                else:
                    st.info("この種目のデータはまだありません")
        else:
            st.warning("選手データがありません")

    # 3. ランキング
    with t3:
        st.subheader("種目別トップ5")
        if not df_phys.empty:
            cols = st.columns(2)
            for i, test in enumerate(PHYS_TESTS):
                with cols[i%2]:
                    st.markdown(f"**{test}**")
                    asc = True if "秒" in test else False
                    sub = df_phys[df_phys["test_name"] == test]
                    if not sub.empty:
                        # 最高記録を取得
                        rank = sub.sort_values("value", ascending=asc).drop_duplicates("player_name").head(5)
                        st.dataframe(rank[["player_name", "value", "date"]].reset_index(drop=True), hide_index=True)
                    else:
                        st.caption("データなし")
        else:
            st.info("テストデータがありません")

    # 4. 登録・入力
    with t4:
        c1, c2 = st.columns(2)
        
        # A. 新規選手登録フォーム
        with c1:
            st.subheader("👤 新規選手登録")
            with st.form("reg_player", clear_on_submit=True):
                n_name = st.text_input("名前 (フルネーム)")
                col_a, col_b = st.columns(2)
                with col_a:
                    n_num = st.number_input("背番号", step=1, value=10)
                    n_pos = st.selectbox("ポジション", ["GK", "DF", "MF", "FW"])
                with col_b:
                    n_h = st.number_input("身長 (cm)", value=170.0)
                    n_w = st.number_input("体重 (kg)", value=60.0)
                
                n_pw = st.text_input("選手用パスワード", "1234")
                n_img = st.file_uploader("プロフィール画像")
                
                # ★修正箇所: ボタンを必ずフォーム内に配置
                submitted = st.form_submit_button("選手を登録")
                
                if submitted:
                    if n_name:
                        # 画像保存処理
                        path = ""
                        if n_img:
                            path = os.path.join(IMAGE_DIR, f"{n_num}_{n_name}.jpg")
                            with open(path, "wb") as f:
                                f.write(n_img.getbuffer())
                        
                        # DBへインサート
                        data = {
                            "name": n_name, "number": n_num, "position": n_pos,
                            "height": n_h, "weight": n_w,
                            "password_hash": hash_password(n_pw), "image_url": path
                        }
                        try:
                            supabase.table("players").insert(data).execute()
                            st.success(f"{n_name} をデータベースに登録しました！")
                            # rerunはフォーム送信後に行うと良い
                        except Exception as e:
                            st.error(f"登録エラー: {e}")
                    else:
                        st.error("名前を入力してください")

        # B. テスト記録入力フォーム
        with c2:
            st.subheader("🏆 テスト記録入力")
            with st.form("reg_test", clear_on_submit=True):
                # 選手がいる場合のみ選択肢を表示
                if not df_players.empty:
                    t_player = st.selectbox("選手", df_players["name"].tolist())
                    t_name = st.selectbox("種目", PHYS_TESTS)
                    t_val = st.number_input("数値 (秒/cm/m)", step=0.01)
                    t_date = st.date_input("測定日", date.today())
                    
                    # ★修正箇所: ボタンをフォーム内に配置
                    submitted_test = st.form_submit_button("記録を保存")
                    
                    if submitted_test:
                        data = {
                            "player_name": t_player, "test_name": t_name,
                            "value": t_val, "date": str(t_date)
                        }
                        try:
                            supabase.table("physical_tests").insert(data).execute()
                            st.success(f"{t_player} の記録を保存しました")
                        except Exception as e:
                            st.error(f"保存エラー: {e}")
                else:
                    st.info("先に選手を登録してください")
                    # エラー回避のためダミーボタンを配置
                    st.form_submit_button("登録不可", disabled=True)

# ========== 選手モード ==========
else:
    # 自分の情報を取得
    if df_players.empty:
        st.error("データが見つかりません。管理者に問い合わせてください。")
        st.stop()

    my_info_df = df_players[df_players["name"] == st.session_state.user_name]
    if my_info_df.empty:
        st.error("ユーザー情報が見つかりません")
        st.stop()
        
    my_info = my_info_df.iloc[0]
    
    # プロフィール表示
    img_path = my_info.get("image_url", "")
    img_base64 = get_base64_image(img_path)
    img_src = f"data:image/jpeg;base64,{img_base64}" if img_base64 else "https://via.placeholder.com/150"
    
    st.markdown(f"""
    <div class="profile-container">
        <div class="profile-photo"><img src="{img_src}"></div>
        <div>
            <h2>{my_info['name']} <small>#{my_info['number']}</small></h2>
            <p>身長: {my_info['height']}cm | 体重: {my_info['weight']}kg | Pos: {my_info['position']}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["📝 今日のコンディション", "📊 自分のデータ"])

    with tab1:
        st.subheader("今日の体調を入力")
        with st.form("daily_input"):
            c1, c2 = st.columns(2)
            with c1:
                in_w = st.number_input("今日の体重 (kg)", value=float(my_info['weight']), step=0.1)
                in_inj = st.radio("怪我・痛み", ["なし", "あり"], horizontal=True)
                in_inj_dt = st.text_input("痛みの詳細 (部位など)") if in_inj == "あり" else ""
            with c2:
                in_fat = st.slider("疲労度 (1:元気 - 5:限界)", 1, 5, 3)
                in_slp = st.slider("睡眠の質 (1:悪い - 5:最高)", 1, 5, 3)
            
            # ★修正箇所: ボタンは必ずフォーム内
            submitted_daily = st.form_submit_button("送信する", use_container_width=True)
            
            if submitted_daily:
                data = {
                    "player_name": st.session_state.user_name,
                    "date": str(date.today()),
                    "weight": in_w, "fatigue": in_fat, "sleep": in_slp,
                    "injury": in_inj, "injury_detail": in_inj_dt
                }
                try:
                    supabase.table("conditions").insert(data).execute()
                    st.success("体調を記録しました！お疲れ様です。")
                except Exception as e:
                    st.error(f"送信エラー: {e}")

    with tab2:
        # 自分のデータをフィルタリング
        my_cond = df_cond[df_cond["player_name"] == st.session_state.user_name].sort_values("date") if not df_cond.empty else pd.DataFrame()
        
        if not my_cond.empty:
            st.markdown("#### 体調の変化")
            st.plotly_chart(px.line(my_cond, x="date", y=["fatigue", "sleep"], range_y=[0,6], markers=True))
            
            # 最新の体重
            last_w = my_cond.iloc[-1]["weight"]
            diff = last_w - my_info['weight']
            st.metric("最新体重", f"{last_w} kg", delta=f"{diff:.1f} kg")
        else:
            st.info("まだ記録がありません")