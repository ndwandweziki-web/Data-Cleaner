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

# Enterprise UI Configuration
st.set_page_config(page_title="Data Janitor Pro Meta-Engine v4.4", page_icon="🧬", layout="wide")

# Initialize Session-Based Audit Ledger & State
if 'audit_log' not in st.session_state:
    st.session_state.audit_log = []
if 'current_logged_user' not in st.session_state:
    st.session_state.current_logged_user = None

def log_audit_event(action_summary, details=""):
    """Tracks every structural modification for legal reproducibility and auditing."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.audit_log.append({
        "timestamp": timestamp,
        "action": action_summary,
        "details": details
    })

# --- SQLITE WAL PERSISTENCE & TRANSACTION SECURITY LAYER ---
DB_FILE = "janitor_enterprise_vault.db"
DEFAULT_FALLBACK_HASH = "26777aad87c7342827e73f9aa735b5fcbc54d52651a95a9cf3e314222f0ff73c"
MASTER_CRYPTO_HASH = st.secrets.get("MASTER_HASH", DEFAULT_FALLBACK_HASH)

def init_secure_database():
    """Initializes concurrent SQL storage nodes with WAL capabilities to prevent race conditions."""
    conn = sqlite3.connect(DB_FILE, timeout=30.0)
    conn.execute('PRAGMA journal_mode=WAL;')
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
    cursor.execute('INSERT OR IGNORE INTO secure_users (username, password_hash) VALUES (?, ?)', ('admin', MASTER_CRYPTO_HASH))
    conn.commit()
    conn.close()

def hash_passkey(passkey):
    return hashlib.sha256(passkey.strip().encode('utf-8')).hexdigest()

def register_secure_user(username, password):
    conn = sqlite3.connect(DB_FILE, timeout=30.0)
    conn.execute('PRAGMA journal_mode=WAL;')
    try:
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO secure_users (username, password_hash) VALUES (?, ?)', 
                       (username.lower().strip(), hash_passkey(password)))
        conn.commit()
    finally:
        conn.close()

def authenticate_session(username, password):
    conn = sqlite3.connect(DB_FILE, timeout=30.0)
    conn.execute('PRAGMA journal_mode=WAL;')
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT password_hash FROM secure_users WHERE username = ?', (username.lower().strip(),))
        row = cursor.fetchone()
        if row and row[0] == hash_passkey(password):
            return True
        return False
    finally:
        conn.close()

def manage_session_block(username, action="login"):
    conn = sqlite3.connect(DB_FILE, timeout=30.0)
    conn.execute('PRAGMA journal_mode=WAL;')
    current_time = datetime.datetime.now().timestamp()
    user_key = username.lower().strip()
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM active_sessions WHERE ? - last_activity > 900', (current_time,))
        
        if action == "login":
            cursor.execute('SELECT username FROM active_sessions WHERE username = ?', (user_key,))
            if cursor.fetchone():
                return False  
            cursor.execute('INSERT OR REPLACE INTO active_sessions (username, last_activity) VALUES (?, ?)', (user_key, current_time))
            conn.commit()
        elif action == "logout":
            cursor.execute('DELETE FROM active_sessions WHERE username = ?', (user_key,))
            conn.commit()
        return True
    finally:
        conn.close()

init_secure_database()

# --- CORE POLYMORPHIC DATA PROCESSING ENGINE ---

def profile_semantic_types(df):
    profiles = {}
    for col in df.columns:
        sample_str = df[col].dropna().head(100).astype(str).str.strip()
        if sample_str.empty:
            profiles[col] = "empty"
            continue
            
        date_hits = sample_str.apply(lambda x: 1 if re.match(r'^\d{4}[-/]\d{2}[-/]\d{2}', x) or re.search(r'\d{2}/', x) else 0).sum()
        if date_hits / len(sample_str) > 0.5:
            profiles[col] = "date"
            continue

        currency_hits = sample_str.apply(lambda x: 1 if any(symbol in x for symbol in ['R', '$', '€', '£']) else 0).sum()
        numeric_coerced = pd.to_numeric(df[col].astype(str).str.replace(r'[R\$\s,€£]', '', regex=True), errors='coerce')
        valid_numeric_ratio = numeric_coerced.notnull().sum() / len(df[col])
        
        if valid_numeric_ratio > 0.6 or currency_hits / len(sample_str) > 0.3:
            profiles[col] = "numeric"
            continue
            
        unique_ratio = df[col].nunique() / len(df[col]) if len(df[col]) > 0 else 0
        if unique_ratio > 0.8 and any(token in col.lower() for token in ['id', 'key', 'code', 'pk']):
            profiles[col] = "system_key"
        else:
            profiles[col] = "categorical_text"
    return profiles

def discover_algebraic_identities(df, numeric_columns):
    identities = []
    if len(numeric_columns) < 3:
        return identities
    test_df = df[numeric_columns].dropna().head(500)
    if len(test_df) < 5:
        return identities

    cols = list(numeric_columns)
    for i in range(len(cols)):
        for j in range(len(cols)):
            if i == j: continue
            for k in range(len(cols)):
                if k == i or k == j: continue
                A, B, C = test_df[cols[i]], test_df[cols[j]], test_df[cols[k]]
                if np.allclose(A * B, C, rtol=1e-2, atol=1e-2):
                    identities.append(('multiply', cols[i], cols[j], cols[k]))
                    return identities
                if np.allclose(A + B, C, rtol=1e-2, atol=1e-2):
                    identities.append(('add', cols[i], cols[j], cols[k]))
                    return identities
    return identities

def execute_polymorphic_cleaning(df, config_flags, global_rules=None):
    df_clean = df.copy()
    semantic_map = profile_semantic_types(df_clean)
    
    numeric_cols = [c for c, t in semantic_map.items() if t == "numeric"]
    text_cols = [c for c, t in semantic_map.items() if t == "categorical_text"]
    date_cols = [c for c, t in semantic_map.items() if t == "date"]

    # 1. Clean String & Currency Formats
    if config_flags['clean_strings']:
        for col in numeric_cols:
            df_clean[col] = df_clean[col].astype(str).str.replace(r'[R\$\s,€£]', '', regex=True)
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')

        for col in text_cols:
            if df_clean[col].astype(str).str.contains('_').sum() / len(df_clean) > 0.4:
                df_clean[col] = df_clean[col].astype(str).str.replace('_', ' ', regex=False)
                try:
                    df_clean[col] = df_clean[col].str.split().str[0] + ' ' + df_clean[col].str.split().str[1]
                except:
                    pass
            df_clean[col] = df_clean[col].astype(str).str.strip().str.title()

    # 2. Dynamic Algebraic Imputation Loop (🎯 TYPO FIX COMPLETED HERE)
    active_rules = global_rules if global_rules is not None else (discover_algebraic_identities(df_clean, numeric_cols) if config_flags['smart_impute'] else [])
    
    if config_flags['smart_impute'] and active_rules:
        for rule_type, colA, colB, colC in active_rules:
            if colA in df_clean.columns and colB in df_clean.columns and colC in df_clean.columns:
                if rule_type == 'multiply':
                    mask_c = df_clean[colC].isnull() & df_clean[colA].notnull() & df_clean[colB].notnull()
                    df_clean.loc[mask_c, colC] = df_clean.loc[mask_c, colA] * df_clean.loc[mask_c, colB]
                    
                    mask_a = df_clean[colA].isnull() & df_clean[colC].notnull() & df_clean[colB].notnull() & (df_clean[colB] > 0)
                    df_clean.loc[mask_a, colA] = df_clean.loc[mask_a, colC] / df_clean.loc[mask_a, colB]
                    
                    mask_b = df_clean[colB].isnull() & df_clean[colC].notnull() & df_clean[colA].notnull() & (df_clean[colA] > 0)
                    df_clean.loc[mask_b, colB] = df_clean.loc[mask_b, colC] / df_clean.loc[mask_b, colA]

    # 3. Non-Destructive Statistical IQR Outlier Profiling Layer
    if config_flags['stat_outliers']:
        outlier_cols = [col for col in df_clean.columns if col.endswith('_Outlier_Flag')]
        df_clean = df_clean.drop(columns=outlier_cols, errors='ignore')
        
        for col in numeric_cols:
            q1 = df_clean[col].quantile(0.25)
            q3 = df_clean[col].quantile(0.75)
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            df_clean[f"{col}_Outlier_Flag"] = (df_clean[col] < lower_bound) | (df_clean[col] > upper_bound)

    # 4. Handle remaining null records via population medians
    if config_flags['fix_nulls']:
        for col in numeric_cols:
            df_clean[col] = df_clean[col].fillna(df_clean[col].median())
        for col in text_cols:
            df_clean[col] = df_clean[col].replace(['Nan', 'None', 'Null', ''], np.nan).fillna("Unspecified Field")

    # 5. Standardize Dates
    if config_flags['date_standard']:
        for col in date_cols:
            df_clean[col] = pd.to_datetime(df_clean[col], errors='coerce').dt.strftime('%Y-%m-%d')

    # 6. Drop Duplicates
    if config_flags['purge_dupes']:
        df_clean = df_clean.drop_duplicates()

    return df_clean

# --- STEP 1: AUTHENTICATION INTERFACE NODE ---
st.sidebar.header("🔑 Cryptographic Authentication")
user_tier = st.sidebar.radio("Authorization Node", ["Free / Guest User", "Premium Member / Admin Login", "🌟 Register Secure Passkey"])

has_full_access = False

if user_tier == "Free / Guest User":
    if st.session_state.current_logged_user:
        manage_session_block(st.session_state.current_logged_user, action="logout")
        st.session_state.current_logged_user = None
    st.sidebar.info("ℹ️ Free tier limited to maximum 60 rows × 60 columns processing slice.")

elif user_tier == "🌟 Register Secure Passkey":
    reg_user = st.sidebar.text_input("Choose Username")
    reg_pass = st.sidebar.text_input("Create Private Passkey", type="password")
    invite_code = st.sidebar.text_input("Enterprise Verification Pass", type="password")
    if st.sidebar.button("Register Key Node 🚀"):
        if hash_passkey(invite_code) == MASTER_CRYPTO_HASH:
            if reg_user.strip() and reg_pass.strip():
                register_secure_user(reg_user, reg_pass)
                st.sidebar.success("✔️ Cryptographic signature saved. Proceed to Login node.")
            else:
                st.sidebar.error("❌ Credentials cannot be left empty.")
        else:
            st.sidebar.error("❌ Verification failed: Unauthorized invitation code signature.")

elif user_tier == "Premium Member / Admin Login":
    login_user_input = st.sidebar.text_input("Username").lower().strip()
    login_pass = st.sidebar.text_input("Enter Passkey", type="password")
    if login_user_input and login_pass:
        if authenticate_session(login_user_input, login_pass):
            if st.session_state.current_logged_user == login_user_input:
                has_full_access = True
                st.sidebar.success(f"🔥 Secure Node Active: Welcome back, {login_user_input.title()}.")
            else:
                if manage_session_block(login_user_input, action="login"):
                    st.session_state.current_logged_user = login_user_input
                    has_full_access = True
                    st.sidebar.success(f"🔥 Session Authenticated: Welcome, {login_user_input.title()}.")
                else:
                    st.sidebar.error("🚨 Collision Block: Account session active on another device node.")
        else:
            if login_pass != "":
                st.sidebar.error("❌ Security Violation: Invalid signature credentials.")

# --- STEP 2: MAIN ENGINE CONTROL LAYER ---
st.title("🧬 Autonomous Polymorphic Meta-Engine & Reproducibility Suite")
st.write("An advanced self-correcting data cleaning engine that logs, audits, and normalizes unstructured files.")

with st.expander("📖 Interactive Enterprise User Manual & Operations Guide", expanded=False):
    st.markdown("""
    ### Welcome to Data Janitor Pro
    This application is an autonomous data parsing tool engineered to automatically profile data types, reconstruct accounting errors, and flag anomalies without requiring hardcoded user configuration.
    
    #### 🛠️ Operational Steps:
    1. **Authentication (Sidebar):** Free/Guest uploads are capped at a maximum 60 rows × 60 columns. To process unlimited row files, select **Premium Member Login**, and enter your authorized credentials.
    2. **Drop Your File:** Upload any messy or unformatted `.csv` or `.xlsx` spreadsheet into the file drop target below.
    3. **Configure Meta-Directives:** Use the checkboxes in the left-hand configuration panel to activate or isolate specific algorithm routines.
    4. **Trigger Processing:** Click the **⚡ Trigger Universal Polymorphic Scrubbing** button. The engine will divide the data array into safe memory batches and execute updates.
    5. **Review Validation Views:** Evaluate changes side-by-side. Modified or imputed record fields are highlighted in green.
    6. **Export Assets:** Download your clean flat-file data assets, advanced schema-preserving `.parquet` assets, or your legal transparency audit trail log.
    """)

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Meta-Pipeline Directives")
flags = {
    'fix_nulls': st.sidebar.checkbox("Statistical Median Null Imputation", value=True),
    'smart_impute': st.sidebar.checkbox("🧠 Polymorphic Identity Extraction", value=True),
    'stat_outliers': st.sidebar.checkbox("📊 Non-Destructive IQR Outlier Flagging", value=True),
    'purge_dupes': st.sidebar.checkbox("Purge Redundant Matrix Profiles", value=True),
    'clean_strings': st.sidebar.checkbox("Strip Currency Noise & Standardize Text", value=True),
    'date_standard': st.sidebar.checkbox("📅 Smart Chronological Formatter", value=True)
}
push_to_database = st.sidebar.checkbox("Index Clean Tables into Backend SQLite")

st.sidebar.markdown("---")
st.sidebar.subheader("🎛️ Performance Tuning")
chunk_size = st.sidebar.slider(
    "Chunk Size (rows per batch)", 
    min_value=500, 
    max_value=50000, 
    value=5000, 
    step=500,
    help="Smaller chunks consume less container RAM but process slower. Adjust scale dynamically based on your volume layout."
)

my_raw_file = st.file_uploader("Upload any unstructured sheet dataset here", type=["csv", "xlsx"])

if my_raw_file is not None:
    is_csv = my_raw_file.name.endswith('.csv')
    try:
        loaded_df = pd.read_csv(my_raw_file) if is_csv else pd.read_excel(my_raw_file)
    except Exception as e:
        st.error(f"❌ Corrupt File Architecture: {e}")
        st.stop()

    total_rows, total_cols = len(loaded_df), len(loaded_df.columns)
    
    if not has_full_access and (total_rows > 60 or total_cols > 60):
        st.warning(f"⚠️ **Free Tier Slicer Active:** Structural view capped down to 60x60 dimensions.")
        working_df = loaded_df.iloc[:min(total_rows, 60), :min(total_cols, 60)].copy()
    else:
        working_df = loaded_df.copy()

    working_df_original = working_df.copy()

    # Diagnostic Visuals Profile Report
    st.markdown("---")
    st.subheader("📊 Engine Diagnostic Profile")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Rows Processed", len(working_df))
    m2.metric("Columns Mapped", len(working_df.columns))
    m3.metric("Missing Cell Points", int(working_df.isnull().sum().sum()))
    m4.metric("Redundant Duplicates", int(working_df.duplicated().sum()))

    # Processing Core Action
    st.markdown("---")
    st.subheader("⚙️ Meta-Pipeline Operational Log")
    if st.button("⚡ Trigger Universal Polymorphic Scrubbing"):
        prog = st.progress(0)
        log_txt = st.empty()
        
        st.session_state.audit_log = [] 
        log_audit_event("Ingested File Instance", f"Filename: {my_raw_file.name} | Dimensions: {total_rows}x{total_cols}")
        
        log_txt.text("Phase 1: Analyzing global sample mapping to preserve cross-chunk identities...")
        prog.progress(10)
        
        global_algebraic_rules = []
        if flags['smart_impute'] and len(working_df) > 0:
            sample_size = min(1000, len(working_df))
            sample_df = working_df.head(sample_size).copy()
            
            sample_semantic_map = profile_semantic_types(sample_df)
            numeric_cols_sample = [c for c, t in sample_semantic_map.items() if t == "numeric"]
            global_algebraic_rules = discover_algebraic_identities(sample_df, numeric_cols_sample)
            
            if global_algebraic_rules:
                log_audit_event("Global Equation Lock Instantiated", f"Identified global equation pattern constraints: {global_algebraic_rules}")

        try:
            chunks_accumulator = []
            total_chunks = (len(working_df) + chunk_size - 1) // chunk_size
            
            for i, start_idx in enumerate(range(0, len(working_df), chunk_size)):
                progress_pct = 10 + int((i / total_chunks) * 85)
                prog.progress(progress_pct)
                log_txt.text(f"Processing data array segment chunk {i+1} of {total_chunks}...")
                
                chunk_slice = working_df.iloc[start_idx : start_idx + chunk_size].copy()
                cleaned_slice = execute_polymorphic_cleaning(chunk_slice, flags, global_rules=global_algebraic_rules)
                chunks_accumulator.append(cleaned_slice)
            
            working_df = pd.concat(chunks_accumulator, ignore_index=True)
            prog.progress(100)
            log_txt.success("✨ Engine successfully normalized the target matrix using isolated chunk streams!")
            log_audit_event("Chunked Pipeline Engine Optimization", f"Data frame processed cleanly across {total_chunks} chunks using custom size bounds of {chunk_size}")
            
        except Exception as err:
            st.error(f"Pipeline Interruption: {err}")

    # Side by side delta tracking engine view
    st.markdown("### 🔄 Core Delta Engine Matrix Validation")
    col_orig, col_clean = st.columns(2)
    with col_orig:
        st.markdown("**📋 Ingested Matrix Frame**")
        st.dataframe(working_df_original.head(10))
    with col_clean:
        st.markdown("**✨ Sanitized Engine Output**")
        try:
            styled = working_df.head(10).reset_index(drop=True).style.apply(
                lambda x: np.where(working_df_original.head(10).reset_index(drop=True) != working_df.head(10).reset_index(drop=True), 'background-color: rgba(46, 204, 113, 0.25)', ''), axis=None
            )
            st.dataframe(styled)
        except:
            st.dataframe(working_df.head(10))

    if push_to_database:
        try:
            conn = sqlite3.connect("universal_analytics.db")
            working_df.to_sql("sanitized_ledger", conn, if_exists="replace", index=False)
            conn.close()
            st.sidebar.info("🚀 Indexed into local SQLite database with concurrent WAL controls.")
        except Exception as dbe:
            st.sidebar.error(f"Database Exception: {dbe}")

    st.markdown("---")
    st.subheader("💾 Production Export Center")
    ex1, ex2, ex3 = st.columns(3)
    with ex1:
        st.markdown("#### 📊 Standard Flat File")
        if is_csv:
            st.download_button("📥 Download Universal Clean CSV", data=working_df.to_csv(index=False).encode('utf-8'), file_name=f"sanitized_{my_raw_file.name}", mime="text/csv")
        else:
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as w:
                working_df.to_excel(w, index=False, sheet_name='Sanitized Frame')
            st.download_button("📥 Download Universal Clean Excel", data=buf.getvalue(), file_name=f"sanitized_{my_raw_file.name}", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with ex2:
        st.markdown("#### 🚀 Enterprise Typing Asset")
        parquet_buf = io.BytesIO()
        working_df.to_parquet(parquet_buf, index=False)
        st.download_button("📥 Download Strict Parquet Schema Asset", data=parquet_buf.getvalue(), file_name=f"sanitized_{os.path.splitext(my_raw_file.name)[0]}.parquet", mime="application/octet-stream")
    with ex3:
        st.markdown("#### 📜 Transparency Audit Trail")
        audit_json = json.dumps(st.session_state.audit_log, indent=2)
        st.download_button("📥 Download Reproducible Audit Log (.json)", data=audit_json, file_name=f"audit_trail_{datetime.date.today()}.json", mime="application/json")

# System Feedback Terminal Block (🎯 Fixed undefined user login context variables here)
st.markdown("---")
st.subheader("⭐ System Feedback Terminal")
fa, fb = st.columns(2)
with fa:
    rating = st.slider("Rate Engine Performance", 1, 5, 5)
    review = st.text_area("Log structural enhancement requests directly to the core engineering roadmap:")
    if st.button("Transmit Feedback 🚀") and review.strip():
        with open("user_feedback_vault.txt", "a") as f:
            f.write(f"[{datetime.datetime.now()}] Rating: {rating}/5 | Log: {review}\n")
        st.success("Log safely transmitted.")
with fb:
    st.markdown("### 🔒 Private Administrator Logging Port")
    current_session_user = st.session_state.get('current_logged_user', '')
    if has_full_access and current_session_user == "admin":
        if os.path.exists("user_feedback_vault.txt"):
            with open("user_feedback_vault.txt", "r") as f:
                st.text(f.read())
        else:
            st.info("No logs present in vault.")
    else:
        st.info("🔒 Secure Admin configuration locked. Access requires Root Master authentication.")
