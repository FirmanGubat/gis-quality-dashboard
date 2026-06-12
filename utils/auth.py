"""
Autentikasi via Google Sheets menggunakan GSheetsConnection (service account).

Konfigurasi di secrets.toml:
    [connections.gsheets]
    spreadsheet = "https://docs.google.com/spreadsheets/d/..."
    type = "service_account"
    project_id = "..."
    private_key_id = "..."
    private_key = "-----BEGIN RSA PRIVATE KEY-----\\n...\\n-----END RSA PRIVATE KEY-----\\n"
    client_email = "...@....iam.gserviceaccount.com"
    client_id = "..."
    auth_uri = "https://accounts.google.com/o/oauth2/auth"
    token_uri = "https://oauth2.googleapis.com/token"
    auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
    client_x509_cert_url = "..."
    universe_domain = "googleapis.com"

Sheet harus memiliki kolom: username, password, role, nama, opd
"""
import hashlib
import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection


def _hash_password(password: str) -> str:
    """SHA-256 hash. Simpan hash di spreadsheet, bukan plaintext."""
    return hashlib.sha256(password.encode()).hexdigest()


@st.cache_data(ttl=0, show_spinner=False)
def _load_users() -> pd.DataFrame:
    """
    Load data user dari Google Sheets via GSheetsConnection (service account).
    Kolom wajib: username, password, role
    Kolom opsional: nama, opd
    """
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="akun", ttl=0)
        if df is None or df.empty:
            st.error("❌ Spreadsheet kosong atau tidak dapat dibaca.")
            return pd.DataFrame()
        # Normalize kolom
        df.columns = [c.strip().lower() for c in df.columns]
        # Hapus baris kosong
        df = df.dropna(subset=["username", "password"])
        df["username"] = df["username"].astype(str).str.strip()
        df["password"] = df["password"].astype(str).str.strip()
        required = {"username", "password", "role"}
        if not required.issubset(set(df.columns)):
            st.error(
                f"❌ Spreadsheet harus memiliki kolom: {required}. "
                f"Kolom ditemukan: {list(df.columns)}"
            )
            return pd.DataFrame()
        return df
    except Exception as e:
        st.error(f"❌ Gagal load users dari Google Sheets: {e}")
        return pd.DataFrame()


def login(username: str, password: str) -> dict | None:
    """
    Verifikasi login. Return dict user jika berhasil, None jika gagal.
    Mendukung password plaintext dan SHA-256 hash di spreadsheet.
    """
    users = _load_users()
    if users.empty:
        return None

    user_row = users[users["username"].str.strip() == username.strip()]
    if user_row.empty:
        return None

    user = user_row.iloc[0]
    stored_pass = str(user["password"]).strip()

    # Coba match plaintext dulu, lalu hash
    hashed_input = _hash_password(password)
    if stored_pass != password and stored_pass != hashed_input:
        return None

    return {
        "username": user["username"],
        "role": user.get("role", "admin"),
        "nama": user.get("nama", user["username"]),
        "opd": user.get("opd", "-"),
    }


def is_logged_in() -> bool:
    return st.session_state.get("authenticated", False)


def get_current_user() -> dict | None:
    return st.session_state.get("user_data", None)


def do_login(username: str, password: str) -> bool:
    result = login(username, password)
    if result:
        st.session_state["authenticated"] = True
        st.session_state["user_data"] = result
        return True
    return False


def do_logout():
    st.session_state["authenticated"] = False
    st.session_state["user_data"] = None
    st.session_state.pop("authenticated", None)
    st.session_state.pop("user_data", None)