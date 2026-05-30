"""
Data Janitor Pro: The Autonomous Meta-Engine v5.0
Advanced Self-Correcting Data Cleaning Suite
"""

import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import datetime
import json
import re
import hashlib
from typing import Dict, List, Tuple

# ============================================================================
# CONFIG
# ============================================================================

SESSION_TIMEOUT = 900
CHUNK_SIZE = 5000
DATE_REGEX = r'^\d{4}[-/]\d{2}[-/]\d{2}'
CURRENCY_SYMS = ['R', '$', '€', '£']
NULL_REPLACE = "Unspecified Field"
IQR_MULT = 1.5
NUMERIC_THRESHOLD = 0.6
CURRENCY_THRESHOLD = 0.3
UNIQUE_THRESHOLD = 0.8
DATE_THRESHOLD = 0.5
ALGEBRAIC_RTOL = 1e-2
ALGEBRAIC_ATOL = 1e-2
SAMPLE_LIMIT = 100
DB_FILE = "janitor_vault.db"

# ============================================================================
# SESSION INIT
# ============================================================================

def init_session():
    """Initialize session state."""
    if 'audit_log' not in st.session_state:
        st.session_state.audit_log = []
    if 'current_logged_user' not in st.session_state:
        st.session_state.current_logged_user = None
    if 'df_current' not in st.session_state:
        st.session_state.df_current = None
    if 'cleaning_history' not in st.session_state:
        st.session_state.cleaning_history = []

init_session()

# ============================================================================
# DATABASE
# ============================================================================

def get_db():
    """Get database connection."""
    conn = sqlite3.connect(DB_FILE, timeout=30.0)
    conn.execute('PRAGMA journal_mode=WAL;')
    return conn

def setup_db():
    """Initialize database tables."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS secure_users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS active_sessions (
            username TEXT PRIMARY KEY,
            last_activity REAL NOT NULL
        )
    ''')

    # Insert default admin
    master_hash = "26777aad87c7342827e73f9aa735b5fcbc54d52651a95a9cf3e314222f0ff73c"
    cursor.execute(
        'INSERT OR IGNORE INTO secure_users VALUES (?, ?)',
        ('admin', master_hash)
    )
    conn.commit()
    conn.close()

try:
    setup_db()
except Exception as e:
    st.error(f"Database error: {e}")

# ============================================================================
# AUTH
# ============================================================================

def hash_pwd(pwd: str) -> str:
    """Hash password."""
    return hashlib.sha256(pwd.strip().encode()).hexdigest()

def auth_user(username: str, password: str) -> bool:
    """Authenticate user."""
    username = username.lower().strip()
    pwd_hash = hash_pwd(password)

    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT password_hash FROM secure_users WHERE username = ?', (username,))
        row = cursor.fetchone()
        conn.close()
        return row is not None and row[0] == pwd_hash
    except Exception:
        return False

def manage_session(username: str, action: str = "login") -> bool:
    """Manage user sessions."""
    username = username.lower().strip()
    current_time = datetime.datetime.now().timestamp()

    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('DELETE FROM active_sessions WHERE ? - last_activity > ?',
                      (current_time, SESSION_TIMEOUT))

        if action == "login":
            cursor.execute('SELECT username FROM active_sessions WHERE username = ?', (username,))
            if cursor.fetchone():
                conn.close()
                return False
            cursor.execute('INSERT OR REPLACE INTO active_sessions VALUES (?, ?)',
                          (username, current_time))

        elif action == "logout":
            cursor.execute('DELETE FROM active_sessions WHERE username = ?', (username,))

        conn.commit()
        conn.close()
        return True
    except Exception:
        return False

def log_audit(action: str, details: str = ""):
    """Log audit event."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.audit_log.append({
        "timestamp": timestamp,
        "action": action,
        "details": details
    })

# ============================================================================
# LOGIN UI
# ============================================================================

def render_login() -> bool:
    """Render admin login panel."""
    st.sidebar.header("🔐 System Console")
    show_admin = st.sidebar.checkbox("Open Administrator Portal")

    if not show_admin:
        return False

    username = st.sidebar.text_input("Admin Username").lower().strip()
    password = st.sidebar.text_input("Master Passkey", type="password")

    if not (username and password):
        return False

    if auth_user(username, password):
        if st.session_state.current_logged_user == username:
            st.sidebar.success("✅ Root Node Active.")
            return True

        if manage_session(username, action="login"):
            st.session_state.current_logged_user = username
            st.sidebar.success("✅ Root Node Active.")
            log_audit("LOGIN", f"User: {username}")
            return True
        else:
            st.sidebar.error("⚠️ Session collision detected.")
            return False
    else:
        st.sidebar.error("❌ Access Denied.")
        log_audit("LOGIN_FAIL", f"User: {username}")
        return False

# ============================================================================
# TYPE DETECTION
# ============================================================================

def detect_type(series: pd.Series) -> str:
    """Detect column semantic type."""
    sample = series.dropna().head(SAMPLE_LIMIT).astype(str).str.strip()

    if sample.empty:
        return "empty"

    # Date check
    date_pattern = re.compile(DATE_REGEX)
    date_matches = sum(1 for x in sample if date_pattern.match(x))
    if len(sample) > 0 and date_matches / len(sample) > DATE_THRESHOLD:
        return "date"

    # Numeric/currency check
    currency_matches = sum(1 for x in sample if any(sym in x for sym in CURRENCY_SYMS))
    numeric_clean = pd.to_numeric(
        series.astype(str).str.replace(r'[R\$\s,€£]', '', regex=True),
        errors='coerce'
    )
    valid_ratio = numeric_clean.notnull().sum() / len(series) if len(series) > 0 else 0

    if (valid_ratio > NUMERIC_THRESHOLD or
            currency_matches / len(sample) > CURRENCY_THRESHOLD):
        return "numeric"

    # System key check
    unique_ratio = series.nunique() / len(series) if len(series) > 0 else 0
    col_lower = (series.name or "").lower()

    if unique_ratio > UNIQUE_THRESHOLD and any(
        token in col_lower for token in ['id', 'key', 'code', 'pk']
    ):
        return "system_key"

    return "categorical_text"

def profile_types(df: pd.DataFrame) -> Dict[str, str]:
    """Profile all columns."""
    return {col: detect_type(df[col]) for col in df.columns}

# ============================================================================
# CLEANING FUNCTIONS
# ============================================================================

def discover_identities(df: pd.DataFrame, numeric_cols: List[str]) -> List[Tuple]:
    """Discover algebraic relationships."""
    identities = []

    if len(numeric_cols) < 3:
        return identities

    test_df = df[numeric_cols].dropna().head(500)
    if len(test_df) < 5:
        return identities

    cols = list(numeric_cols)

    for i in range(len(cols)):
        for j in range(len(cols)):
            if i == j:
                continue
            for k in range(len(cols)):
                if k == i or k == j:
                    continue

                col_a, col_b, col_c = cols[i], cols[j], cols[k]
                val_a = test_df[col_a].values
                val_b = test_df[col_b].values
                val_c = test_df[col_c].values

                if np.allclose(val_a * val_b, val_c, rtol=ALGEBRAIC_RTOL, atol=ALGEBRAIC_ATOL):
                    identities.append(("multiply", col_a, col_b, col_c))

                elif np.allclose(val_a + val_b, val_c, rtol=ALGEBRAIC_RTOL, atol=ALGEBRAIC_ATOL):
                    identities.append(("add", col_a, col_b, col_c))

    return identities

def clean_numeric(df: pd.DataFrame, numeric_cols: List[str]) -> pd.DataFrame:
    """Clean numeric columns."""
    df_clean = df.copy()

    for col in numeric_cols:
        df_clean[col] = (
            df_clean[col]
            .astype(str)
            .str.replace(r'[R\$\s,€£]', '', regex=True)
        )
        df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')

    return df_clean

def clean_text(df: pd.DataFrame, text_cols: List[str]) -> pd.DataFrame:
    """Clean text columns."""
    df_clean = df.copy()

    for col in text_cols:
        underscore_ratio = df_clean[col].astype(str).str.contains('_').sum() / len(df_clean)
        if underscore_ratio > 0.4:
            df_clean[col] = df_clean[col].astype(str).str.replace('_', ' ', regex=False)

        df_clean[col] = df_clean[col].astype(str).str.strip().str.title()

    return df_clean

def impute_nulls(df: pd.DataFrame, col_type_map: Dict[str, str], algebraic_ids: List[Tuple]) -> pd.DataFrame:
    """Impute null values."""
    df_impute = df.copy()

    for rule_type, col_a, col_b, col_c in algebraic_ids:
        mask_a = df_impute[col_a].isna()
        mask_b = df_impute[col_b].isna()
        mask_c = df_impute[col_c].isna()

        if rule_type == "multiply":
            imputable_a = mask_a & ~mask_b & ~mask_c & (df_impute[col_b] != 0)
            df_impute.loc[imputable_a, col_a] = df_impute.loc[imputable_a, col_c] / df_impute.loc[imputable_a, col_b]

            imputable_b = mask_b & ~mask_a & ~mask_c & (df_impute[col_a] != 0)
            df_impute.loc[imputable_b, col_b] = df_impute.loc[imputable_b, col_c] / df_impute.loc[imputable_b, col_a]

            imputable_c = mask_c & ~mask_a & ~mask_b
            df_impute.loc[imputable_c, col_c] = df_impute.loc[imputable_c, col_a] * df_impute.loc[imputable_c, col_b]

        elif rule_type == "add":
            imputable_a = mask_a & ~mask_b & ~mask_c
            df_impute.loc[imputable_a, col_a] = df_impute.loc[imputable_a, col_c] - df_impute.loc[imputable_a, col_b]

            imputable_b = mask_b & ~mask_a & ~mask_c
            df_impute.loc[imputable_b, col_b] = df_impute.loc[imputable_b, col_c] - df_impute.loc[imputable_b, col_a]

            imputable_c = mask_c & ~mask_a & ~mask_b
            df_impute.loc[imputable_c, col_c] = df_impute.loc[imputable_c, col_a] + df_impute.loc[imputable_c, col_b]

    for col in df_impute.columns:
        if col_type_map[col] == "numeric":
            df_impute[col].fillna(df_impute[col].median(), inplace=True)
        elif col_type_map[col] == "categorical_text":
            df_impute[col].fillna(NULL_REPLACE, inplace=True)
        elif col_type_map[col] == "system_key":
            df_impute[col].fillna("UNKNOWN_KEY", inplace=True)

    return df_impute

def flag_outliers(df: pd.DataFrame, numeric_cols: List[str]) -> pd.DataFrame:
    """Flag outliers using IQR."""
    df_flag = df.copy()

    for col in numeric_cols:
        Q1 = df_flag[col].quantile(0.25)
        Q3 = df_flag[col].quantile(0.75)
        IQR = Q3 - Q1

        lower_bound = Q1 - IQR_MULT * IQR
        upper_bound = Q3 + IQR_MULT * IQR

        outliers = (df_flag[col] < lower_bound) | (df_flag[col] > upper_bound)
        df_flag[f'{col}_outlier_flag'] = outliers

    return df_flag

def execute_cleaning(df: pd.DataFrame, numeric_cols: List[str], text_cols: List[str]) -> pd.DataFrame:
    """Execute full cleaning pipeline."""
    df_clean = df.copy()
    
    col_types = profile_types(df_clean)
    
    df_clean = clean_numeric(df_clean, numeric_cols)
    df_clean = clean_text(df_clean, text_cols)
    
    algebraic_ids = discover_identities(df_clean, numeric_cols)
    df_clean = impute_nulls(df_clean, col_types, algebraic_ids)
    
    df_clean = flag_outliers(df_clean, numeric_cols)
    
    return df_clean

# ============================================================================
# UI LAYOUT
# ============================================================================

st.set_page_config(page_title="Data Janitor Pro", page_icon="🧹", layout="wide")
st.title("🧹 Data Janitor Pro: Meta-Engine v5.0")

is_admin = render_login()

uploaded_file = st.file_uploader("Upload CSV or Excel file", type=["csv", "xlsx"])

if uploaded_file:
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    st.subheader("📊 Data Preview")
    st.dataframe(df.head(20))

    st.subheader("📈 Data Profile")
    col_types = profile_types(df)
    type_summary = pd.DataFrame(list(col_types.items()), columns=["Column", "Detected Type"])
    st.dataframe(type_summary)

    numeric_cols = [col for col, ctype in col_types.items() if ctype == "numeric"]
    text_cols = [col for col, ctype in col_types.items() if ctype in ["categorical_text", "system_key"]]

    st.subheader("🔧 Cleaning Options")
    col1, col2 = st.columns(2)

    with col1:
        clean_numeric_flag = st.checkbox("Clean numeric columns", value=True)
        clean_text_flag = st.checkbox("Clean text columns", value=True)
        impute_flag = st.checkbox("Impute null values", value=True)

    with col2:
        flag_outliers_flag = st.checkbox("Flag outliers", value=True)
        show_algebraic = st.checkbox("Show algebraic identities", value=False)

    if st.button("🚀 Execute Cleaning Pipeline"):
        with st.spinner("Cleaning data..."):
            df_cleaned = execute_cleaning(df, numeric_cols, text_cols)
            st.session_state.df_current = df_cleaned
            log_audit("CLEANING_EXECUTED", f"Columns processed: {len(df.columns)}")

        st.success("✅
