"""
Data Janitor Pro: The Autonomous Meta-Engine v5.0
Advanced Self-Correcting Data Cleaning Suite
"""

import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import io
import os
import datetime
import json
import re
import hashlib
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

# ============================================================================
# CONFIG & CONSTANTS
# ============================================================================

SESSION_TIMEOUT = 900  # 15 mins
CHUNK_SIZE = 5000
DATE_REGEX = r'^\d{4}[-/]\d{2}[-/]\d{2}'
DATE_REGEX_ALT = r'\d{2}/'
CURRENCY_SYMS = ['R', '$', '€', '£']
NULL_VARIANTS = ['Nan', 'None', 'Null', '']
NULL_REPLACE = "Unspecified Field"
IQR_MULT = 1.5
NUMERIC_THRESHOLD = 0.6
CURRENCY_THRESHOLD = 0.3
UNIQUE_THRESHOLD = 0.8
DATE_THRESHOLD = 0.5
ALGEBRAIC_RTOL = 1e-2
ALGEBRAIC_ATOL = 1e-2
SAMPLE_LIMIT = 100
DB_FILE = "janitor_enterprise_vault.db"
ANALYTICS_DB = "universal_analytics.db"


# ============================================================================
# SESSION STATE
# ============================================================================

def init_session():
    """Initialize session state variables."""
    if 'audit_log' not in st.session_state:
        st.session_state.audit_log = []
    if 'current_logged_user' not in st.session_state:
        st.session_state.current_logged_user = None
    if 'cleaning_history' not in st.session_state:
        st.session_state.cleaning_history = []


# ============================================================================
# DATABASE OPERATIONS
# ============================================================================

def get_db_connection():
    """Get SQLite connection with WAL mode."""
    conn = sqlite3.connect(DB_FILE, timeout=30.0)
    conn.execute('PRAGMA journal_mode=WAL;')
    return conn


def init_db():
    """Initialize database tables."""
    conn = get_db_connection()
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

    master_hash = "26777aad87c7342827e73f9aa735b5fcbc54d52651a95a9cf3e314222f0ff73c"
    cursor.execute(
        'INSERT OR IGNORE INTO secure_users (username, password_hash) VALUES (?, ?)',
        ('admin', master_hash)
    )
    conn.commit()
    conn.close()


def hash_pwd(pwd: str) -> str:
    """Hash password with SHA256."""
    return hashlib.sha256(pwd.strip().encode('utf-8')).hexdigest()


def auth_user(username: str, password: str) -> bool:
    """Verify user credentials."""
    username = username.lower().strip()
    pwd_hash = hash_pwd(password)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT password_hash FROM secure_users WHERE username = ?',
        (username,)
    )
    row = cursor.fetchone()
    conn.close()

    return row is not None and row[0] == pwd_hash


def manage_session(username: str, action: str = "login") -> bool:
    """Handle user session login/logout."""
    username = username.lower().strip()
    current_time = datetime.datetime.now().timestamp()

    conn = get_db_connection()
    cursor = conn.cursor()

    # Clean expired sessions
    cursor.execute(
        'DELETE FROM active_sessions WHERE ? - last_activity > ?',
        (current_time, SESSION_TIMEOUT)
    )

    if action == "login":
        cursor.execute(
            'SELECT username FROM active_sessions WHERE username = ?',
            (username,)
        )
        if cursor.fetchone():
            conn.close()
            return False

        cursor.execute(
            'INSERT OR REPLACE INTO active_sessions (username, last_activity) VALUES (?, ?)',
            (username, current_time)
        )

    elif action == "logout":
        cursor.execute(
            'DELETE FROM active_sessions WHERE username = ?',
            (username,)
        )

    conn.commit()
    conn.close()
    return True


def save_analytics(df: pd.DataFrame, table_name: str = "sanitized_ledger") -> bool:
    """Save cleaned data to analytics database."""
    try:
        conn = sqlite3.connect(ANALYTICS_DB)
        df.to_sql(table_name, conn, if_exists="replace", index=False)
        conn.close()
        return True
    except Exception as e:
        st.error(f"Analytics save failed: {str(e)}")
        return False


# ============================================================================
# AUTHENTICATION UI
# ============================================================================

def render_login_panel() -> bool:
    """Render admin login in sidebar. Returns True if authenticated."""
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
            log_audit("LOGIN_SUCCESS", f"User: {username}")
            return True
        else:
            st.sidebar.error("⚠️ Collision Block: Account session active on another device.")
            return False
    else:
        st.sidebar.error("❌ Access Denied.")
        log_audit("LOGIN_FAILED", f"Attempted user: {username}")
        return False


def logout_user():
    """Logout current user."""
    if st.session_state.current_logged_user:
        manage_session(st.session_state.current_logged_user, action="logout")
        log_audit("LOGOUT", f"User: {st.session_state.current_logged_user}")
        st.session_state.current_logged_user = None


# ============================================================================
# AUDIT LOGGING
# ============================================================================

def log_audit(action: str, details: str = ""):
    """Log audit event."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    event = {
        "timestamp": timestamp,
        "action": action,
        "details": details
    }
    st.session_state.audit_log.append(event)


def export_audit_log() -> str:
    """Export audit log as JSON."""
    return json.dumps(st.session_state.audit_log, indent=2)


# ============================================================================
# DATA PROFILING & TYPE DETECTION
# ============================================================================

def detect_column_type(series: pd.Series) -> str:
    """Detect semantic type of a column."""
    sample = series.dropna().head(SAMPLE_LIMIT).astype(str).str.strip()

    if sample.empty:
        return "empty"

    # Check for date
    date_pattern = re.compile(DATE_REGEX)
    date_alt_pattern = re.compile(DATE_REGEX_ALT)

    date_matches = sum(
        1 for x in sample
        if date_pattern.match(x) or date_alt_pattern.search(x)
    )

    if len(sample) > 0 and date_matches / len(sample) > DATE_THRESHOLD:
        return "date"

    # Check for numeric/currency
    currency_matches = sum(
        1 for x in sample
        if any(sym in x for sym in CURRENCY_SYMS)
    )

    numeric_clean = pd.to_numeric(
        series.astype(str).str.replace(r'[R\$\s,€£]', '', regex=True),
        errors='coerce'
    )
    valid_numeric = numeric_clean.notnull().sum() / len(series) if len(series) > 0 else 0

    if (valid_numeric > NUMERIC_THRESHOLD or
            currency_matches / len(sample) > CURRENCY_THRESHOLD):
        return "numeric"

    # Check for system key
    unique_ratio = series.nunique() / len(series) if len(series) > 0 else 0
    col_lower = series.name.lower() if series.name else ""

    if unique_ratio > UNIQUE_THRESHOLD and any(
        token in col_lower for token in ['id', 'key', 'code', 'pk']
    ):
        return "system_key"

    return "categorical_text"


def profile_df_types(df: pd.DataFrame) -> Dict[str, str]:
    """Profile all columns and return type mapping."""
    profiles = {}
    for col in df.columns:
        profiles[col] = detect_column_type(df[col])
    return profiles


# ============================================================================
# ALGEBRAIC IDENTITY DISCOVERY
# ============================================================================

def discover_algebraic_identities(
    df: pd.DataFrame,
    numeric_cols: List[str]
) -> List[Tuple[str, str, str, str]]:
    """
    Discover algebraic relationships in numeric columns.
    Returns list of (rule_type, col_a, col_b, col_c) tuples.
    """
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

                # Check multiply relationship
                if np.allclose(val_a * val_b, val_c, rtol=ALGEBRAIC_RTOL, atol=ALGEBRAIC_ATOL):
                    identities.append(("multiply", col_a, col_b, col_c))

                # Check add relationship
                elif np.allclose(val_a + val_b, val_c, rtol=ALGEBRAIC_RTOL, atol=ALGEBRAIC_ATOL):
                    identities.append(("add", col_a, col_b, col_c))

    return identities


# ============================================================================
# NUMERIC CLEANING
# ============================================================================

def clean_numeric(df: pd.DataFrame, numeric_cols: List[str]) -> pd.DataFrame:
    """Clean numeric columns by removing currency symbols."""
    df_clean = df.copy()

    for col in numeric_cols:
        df_clean[col] = (
            df_clean[col]
            .astype(str)
            .str.replace(r'[R\$\s,€£]', '', regex=True)
        )
        df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')

    return df_clean


# ============================================================================
# TEXT CLEANING
# ============================================================================

def clean_text(df: pd.DataFrame, text_cols: List[str]) -> pd.DataFrame:
    """Clean text columns by standardizing formatting."""
    df_clean = df.copy()

    for col in text_cols:
        # Replace underscores if common
        underscore_ratio = df_clean[col].astype(str).str.contains('_').sum() / len(df_clean)
        if underscore_ratio > 0.4:
            df_clean[col] = df_clean[col].astype(str).str.replace('_', ' ', regex=False)

        # Clean whitespace and title case
        df_clean[col] = df_clean[col].astype(str).str.strip().str.title()

    return df_clean


# ============================================================================
# NULL VALUE IMPUTATION
# ============================================================================

def impute_nulls(
    df: pd.DataFrame,
    col_type_map: Dict[str, str],
    algebraic_ids: List[Tuple[str, str, str, str]]
) -> pd.DataFrame:
    """Impute null values based on column type and algebraic rules."""
    df_impute = df.copy()

    # Use algebraic rules for imputation
    for rule_type, col_a, col_b, col_c in algebraic_ids:
        mask_a = df_impute[col_a].isna()
        mask_b = df_impute[col_b].isna()
        mask_c = df_impute[col_c].isna()

        if rule_type == "multiply":
            # Impute col_a = col_c / col_b
            imputable_a = mask_a & ~mask_b & ~mask_c & (df_impute[col_b] != 0)
            df_impute.loc[imputable_a, col_a] = df_impute.loc[imputable_a, col_c] / df_impute.loc[imputable_a, col_b]

            # Impute col_b = col_c / col_a
            imputable_b = mask_b & ~mask_a & ~mask_c & (df_impute[col_a] != 0)
            df_impute.loc[imputable_b, col_b] = df_impute.loc[imputable_b, col_c] / df_impute.loc[imputable_b, col_a]

            # Impute col_c = col_a * col_b
            imputable_c = mask_c & ~mask_a & ~mask_b
            df_impute.loc[imputable_c, col_c] = df_impute.loc[imputable_c, col_a] * df_impute.loc[imputable_c, col_b]

        elif rule_type == "add":
            # Impute col_a = col_c - col_b
            imputable_a = mask_a & ~mask_b & ~mask_c
            df_impute.loc[imputable_a, col_a] = df_impute.loc[imputable_a, col_c] - df_impute.loc[imputable_a, col_b]

            # Impute col_b = col_c - col_a
            imputable_b = mask_b & ~mask_a & ~mask_c
            df_impute.loc[imputable_b, col_b] = df_impute.loc[imputable_b, col_c] - df_impute.loc[imputable_b, col_a]

            # Impute col_c = col_a + col_b
            imputable_c = mask_c & ~mask_a & ~mask_b
            df_impute.loc[imputable_c, col_c] = df_impute.loc[imputable_c, col_a] + df_impute.loc[imputable_c, col_b]

    # Handle remaining nulls with strategic imputation
    for col in df_impute.columns:
        if col_type_map[col] == "numeric":
            df_impute[col].fillna(df_impute[col].median(), inplace=True)
        elif col_type_map[col] == "categorical_text":
            df_impute[col].fillna(NULL_REPLACE, inplace=True)
        elif col_type_map[col] == "system_key":
            df_impute[col].fillna("UNKNOWN_KEY", inplace=True)

    return df_impute


# ============================================================================
# OUTLIER DETECTION
# ============================================================================

def flag_outliers(df: pd.DataFrame, numeric_cols: List[str]) -> pd.DataFrame:
    """Flag outliers using IQR method."""
    df_flag = df.copy()

    for col in numeric_cols:
        Q1 = df_flag[col].quantile(0.25)
        Q3 = df_flag[col].quantile(0.75)
        IQR = Q3 - Q1

        lower_bound = Q1 - IQR_MULT * IQR
        upper_bound = Q3 + IQR_MULT * IQR

        outliers = (df_flag[col] < lower_bound) | (df_flag[col] > upper_bound)
        df_flag[f'{col}_outlier_flag'] = outliers
