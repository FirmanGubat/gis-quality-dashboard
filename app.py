import streamlit as st
from utils.auth import is_logged_in, get_current_user, do_login, do_logout
from utils.history_store import load_history

st.set_page_config(
    page_title="GIS Quality Dashboard",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
:root {
    --bg:#060B14; --surface:#0D1526; --surface2:#131E30;
    --border:#1E2D45; --border2:#243550;
    --primary:#00D4FF; --primary-g:linear-gradient(135deg,#00D4FF,#0080FF);
    --green:#00E676; --amber:#FFB74D; --red:#FF5252; --purple:#CE93D8;
    --text:#E8F0FE; --muted:#607D9A; --muted2:#3D5268;
    --radius:14px; --radius-sm:8px;
    --shadow:0 8px 32px rgba(0,0,0,.5);
}
html,body,[class*="css"]{font-family:'Inter',sans-serif;color:var(--text);}
.stApp{background:var(--bg);}
[data-testid="stSidebar"]{display:none!important;}
[data-testid="collapsedControl"]{display:none!important;}
#MainMenu,footer,header,[data-testid="stDecoration"]{display:none!important;}
.block-container{padding-top:1.5rem!important;padding-bottom:1rem!important;}
::-webkit-scrollbar{width:5px;height:5px;}
::-webkit-scrollbar-track{background:var(--bg);}
::-webkit-scrollbar-thumb{background:var(--border2);border-radius:3px;}

/* Buttons */
.stButton>button{
    background:var(--primary-g)!important; color:#060B14!important;
    border:none!important; border-radius:var(--radius-sm)!important;
    font-weight:700!important; font-size:.85rem!important;
    padding:.55rem 1.2rem!important; transition:all .2s!important;
    box-shadow:0 4px 14px rgba(0,212,255,.25)!important;
}
.stButton>button:hover{transform:translateY(-1px)!important;box-shadow:0 6px 20px rgba(0,212,255,.4)!important;}

/* Inputs */
.stTextInput input,.stDateInput input,.stNumberInput input{
    background:var(--surface2)!important; border:1px solid var(--border2)!important;
    border-radius:var(--radius-sm)!important; color:var(--text)!important;
}
.stTextInput input:focus{border-color:var(--primary)!important;}
.stSelectbox>div>div{background:var(--surface2)!important;border:1px solid var(--border2)!important;border-radius:var(--radius-sm)!important;color:var(--text)!important;}

/* Alerts */
.stSuccess>div{background:rgba(0,230,118,.08)!important;border-left:3px solid var(--green)!important;}
.stWarning>div{background:rgba(255,183,77,.08)!important;border-left:3px solid var(--amber)!important;}
.stError>div{background:rgba(255,82,82,.08)!important;border-left:3px solid var(--red)!important;}
.stInfo>div{background:rgba(0,212,255,.08)!important;border-left:3px solid var(--primary)!important;}

/* Tabs */
.stTabs [data-baseweb="tab-list"]{background:var(--surface2);border-radius:10px;padding:4px;gap:3px;border:1px solid var(--border);}
.stTabs [data-baseweb="tab"]{border-radius:var(--radius-sm);color:var(--muted);font-weight:500;font-size:.85rem;}
.stTabs [aria-selected="true"]{background:var(--primary-g)!important;color:#060B14!important;font-weight:700;}

/* Expander */
.streamlit-expanderHeader{background:var(--surface2)!important;border:1px solid var(--border)!important;border-radius:var(--radius-sm)!important;color:var(--text)!important;}

/* Cards */
.gis-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:1.25rem;margin-bottom:.75rem;box-shadow:var(--shadow);}

/* Metric grid */
.metric-grid{display:flex;gap:.75rem;flex-wrap:wrap;margin:.75rem 0;}
.metric-box{flex:1;min-width:110px;background:var(--surface2);border:1px solid var(--border);border-radius:var(--radius);padding:.9rem 1rem;text-align:center;}
.mval{font-size:1.75rem;font-weight:800;line-height:1.1;}
.mlbl{font-size:.68rem;color:var(--muted);text-transform:uppercase;letter-spacing:.07em;margin-top:.25rem;}
.c-cyan{color:var(--primary);}.c-green{color:var(--green);}.c-amber{color:var(--amber);}.c-red{color:var(--red);}

/* Step header */
.step-header{display:flex;align-items:center;gap:.75rem;margin:1.25rem 0 .6rem;padding-bottom:.5rem;border-bottom:1px solid var(--border);}
.step-num{background:var(--primary-g);color:#060B14;width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:.8rem;flex-shrink:0;}
.step-title{font-size:.92rem;font-weight:700;}

/* Badge */
.badge{display:inline-block;padding:.18rem .55rem;border-radius:99px;font-size:.67rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;}
.badge-cyan{background:rgba(0,212,255,.15);color:var(--primary);border:1px solid rgba(0,212,255,.3);}
.badge-green{background:rgba(0,230,118,.15);color:var(--green);border:1px solid rgba(0,230,118,.3);}

/* Nav panel */
.nav-wrap{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:1.1rem .9rem;box-shadow:var(--shadow);}
.nav-title{font-size:1.1rem;font-weight:800;background:linear-gradient(135deg,#00D4FF,#0080FF);-webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.nav-sub{font-size:.67rem;color:var(--muted);margin-top:.1rem;margin-bottom:.9rem;}
.nav-user{background:var(--surface2);border:1px solid var(--border);border-radius:var(--radius-sm);padding:.75rem .85rem;margin-bottom:.85rem;}
.nav-user-label{font-size:.6rem;color:var(--muted);text-transform:uppercase;letter-spacing:.07em;}
.nav-user-name{font-weight:700;font-size:.875rem;margin:.2rem 0 .1rem;}
.nav-user-opd{font-size:.68rem;color:var(--muted);margin-bottom:.35rem;}
hr{border-color:var(--border)!important;margin:.75rem 0!important;}
</style>
""", unsafe_allow_html=True)

# ── Session state init ────────────────────────────────────────────────────────
if "scoring_history" not in st.session_state or not st.session_state["scoring_history"]:
    st.session_state["scoring_history"] = load_history()
if "active_page" not in st.session_state:
    st.session_state["active_page"] = "dashboard"


# ── Login ─────────────────────────────────────────────────────────────────────
def show_login():
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("""
        <div style="text-align:center;padding:2rem 0 1.5rem;">
            <div style="font-size:2.8rem;">🗺️</div>
            <div style="font-size:1.4rem;font-weight:800;background:linear-gradient(135deg,#00D4FF,#0080FF);
                -webkit-background-clip:text;-webkit-text-fill-color:transparent;margin:.4rem 0 .2rem;">
                GIS Quality Dashboard
            </div>
            <div style="color:var(--muted);font-size:.82rem;">
                Platform Pengecekan Kualitas Data Geospasial
            </div>
        </div>
        """, unsafe_allow_html=True)
        with st.form("login_form"):
            username  = st.text_input("Username", placeholder="Masukkan username")
            password  = st.text_input("Password", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("🚀  Masuk", use_container_width=True)
        if submitted:
            if do_login(username, password):
                st.success("✅ Login berhasil!")
                st.rerun()
            else:
                st.error("❌ Username atau password salah.")


# ── Nav panel ─────────────────────────────────────────────────────────────────
def show_nav(user: dict):
    role_badge = "badge-cyan" if user["role"] == "superadmin" else "badge-green"
    role_label = "Superadmin"  if user["role"] == "superadmin" else "Admin"
    active     = st.session_state["active_page"]

    # Header info — pure HTML, tidak ada button di sini
    st.markdown(f"""
    <div class="nav-wrap">
        <div class="nav-title">🗺️ GIS Quality</div>
        <div class="nav-sub">Data Geospasial Jawa Barat</div>
        <div class="nav-user">
            <div class="nav-user-label">Pengguna Aktif</div>
            <div class="nav-user-name">{user['nama']}</div>
            <div class="nav-user-opd">{user['opd']}</div>
            <span class="badge {role_badge}">{role_label}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Buttons — satu per satu, tanpa HTML bercampur di tengahnya
    pages = [
        ("dashboard", "🏠", "Dashboard"),
        ("check",     "🔬", "Check Scoring"),
        ("rekap",     "📊", "Rekap Scoring"),
    ]
    for page_id, icon, label in pages:
        btn_label = f"{icon}  {label}"
        clicked   = st.button(btn_label, key=f"nav_{page_id}", width="stretch")
        if clicked:
            st.session_state["active_page"] = page_id
            st.rerun()

    st.markdown("---")

    if st.button("⏏️  Logout", key="nav_logout", width="stretch"):
        do_logout()
        st.rerun()

    st.markdown("""
    <div style="font-size:.6rem;color:var(--muted2);text-align:center;margin-top:.5rem;">
        v3.0.0 · GIS Quality Dashboard
    </div>
    """, unsafe_allow_html=True)


# ── Dashboard ─────────────────────────────────────────────────────────────────
def show_dashboard(user: dict):
    history        = st.session_state.get("scoring_history", [])
    total          = len(history)
    avg            = round(sum(h["skor"] for h in history) / total, 1) if history else 0
    sangat_baik    = sum(1 for h in history if h["skor"] > 90)
    perlu_perbaiki = sum(1 for h in history if h["skor"] < 60)

    sc = ("#00E676" if avg > 90 else "#00D4FF" if avg > 75
          else "#FFB74D" if avg >= 60 else "#FF5252")

    st.markdown(f"""
    <h1 style="font-size:1.6rem;font-weight:800;margin:0 0 .2rem;">
        Selamat datang, <span style="background:var(--primary-g);
        -webkit-background-clip:text;-webkit-text-fill-color:transparent;">{user['nama']}</span> 👋
    </h1>
    <p style="color:var(--muted);font-size:.85rem;margin:0 0 1.25rem;">{user['opd']}</p>
    <div class="metric-grid">
        <div class="metric-box"><div class="mval c-cyan">{total}</div><div class="mlbl">Total Penilaian</div></div>
        <div class="metric-box"><div class="mval" style="color:{sc};">{avg}</div><div class="mlbl">Rata-rata Skor</div></div>
        <div class="metric-box"><div class="mval c-green">{sangat_baik}</div><div class="mlbl">Sangat Baik</div></div>
        <div class="metric-box"><div class="mval c-red">{perlu_perbaiki}</div><div class="mlbl">Perlu Diperbaiki</div></div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    for col, (icon, title, desc, color) in zip([c1, c2, c3], [
        ("🔬", "Check Scoring",
         "Cek kualitas data geospasial: duplikasi, topologi, completeness, metadata, KUGI. Hasil langsung bisa didownload sebagai PDF.",
         "#00D4FF"),
        ("📊", "Rekap Scoring",
         "Lihat history semua penilaian, download PDF laporan, atau lakukan penilaian ulang kapan saja.",
         "#00E676"),
        ("📄", "Laporan PDF",
         "Setiap check scoring menghasilkan laporan PDF otomatis sesuai template formulir QC Diskominfo Jabar.",
         "#CE93D8"),
    ]):
        with col:
            st.markdown(f"""
            <div class="gis-card">
                <div style="font-size:1.9rem;margin-bottom:.6rem;">{icon}</div>
                <div style="font-size:.9rem;font-weight:700;color:{color};margin-bottom:.35rem;">{title}</div>
                <div style="color:var(--muted);font-size:.78rem;line-height:1.6;">{desc}</div>
            </div>
            """, unsafe_allow_html=True)

    if history:
        st.markdown("---")
        st.markdown("### 📋 Penilaian Terakhir")
        import pandas as pd
        df = pd.DataFrame(history[-5:][::-1])
        st.dataframe(
            df[["layer_name", "skor", "status", "tanggal"]].rename(columns={
                "layer_name": "Mapset", "skor": "Skor",
                "status": "Status", "tanggal": "Tanggal"
            }),
            use_container_width=True, hide_index=True
        )


# ── Main ──────────────────────────────────────────────────────────────────────
if not is_logged_in():
    show_login()
else:
    user = get_current_user()
    col_nav, col_content = st.columns([1, 4])

    with col_nav:
        show_nav(user)

    with col_content:
        page = st.session_state["active_page"]
        if page == "dashboard":
            show_dashboard(user)
        elif page == "check":
            from pages.topology_check import render
            render(user)
        elif page == "rekap":
            from pages.scoring import render
            render(user)
