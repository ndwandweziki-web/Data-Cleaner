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

# Premium UI Configuration
st.set_page_config(page_title="Data Janitor Pro Meta-Engine", page_icon="🧬", layout="wide")

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

# --- CRYPTOGRAPHIC SECURITY LAYER ---
USER_DB_FILE = "secure_user_vault.json"
SESSION_LOG_FILE = "active_sessions_tracker.json"

# Default Master Admin credential hash (SHA-256 hash of "123Shelby@")
DEFAULT_ADMIN_HASH = "26777aad87c7342827e73f9aa735b5fcbc54d52651a95a9cf3e314222f0ff73c"
# Default Invitation Code verification hash (SHA-256 hash of "123Shelby@")
DEFAULT_INVITE_HASH = "26777aad87c7342827e73f9aa735b5fcbc54d52651a95a9cf3e314222f0ff73c"

def hash_passkey(passkey):
    return hashlib.sha256(passkey.strip().encode('utf-8')).hexdigest()

def load_secure_vault():
    if not os.path.exists(USER_DB_FILE):
        initial_vault = {"admin": DEFAULT_ADMIN_HASH}
        with open(USER_DB_FILE, "w") as f:
            json.dump(initial_vault, f)
        return initial_vault
    try:
        with open(USER_DB_FILE, "r") as f:
            return json.load(f)
    except:
        return {"admin": DEFAULT_ADMIN_HASH}

def register_secure_user(username, password):
    vault = load_secure_vault()
    vault[username.lower().strip()] = hash_passkey(password)
    with open(USER_DB_FILE, "w") as f:
        json.dump(vault, f)

def track_active_session(username, action="login"):
    current_time = datetime.datetime.now().timestamp()
    sessions = {}
    if os.path.exists(SESSION_LOG_FILE):
        try:
            with open(SESSION_LOG_FILE, "r") as f:
                sessions = json.load(f)
        except:
            sessions = {}
    user_key = username.lower().strip()
    sessions = {u: t for u, t in sessions.items() if (current_time - t) < 900}
    if action == "login":
        if user_key in sessions:
            return False
        sessions[user_key] = current_time
    elif action == "logout":
        if user_key in sessions:
            del sessions[user_key]
    with open(SESSION_LOG_FILE, "w") as f:
        json.dump(sessions, f)
    return True

secure_vault = load_secure_vault()

# --- CORE POLYMORPHIC DATA PROCESSING ENGINE ---

def profile_semantic_types(df):
    """Phase 1: Analyzes data distributions to deduce column intent dynamically."""
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
    """Phase 2: Scans programmatic permutations across numeric axes to map identities."""
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

def execute_polymorphic_cleaning(df, config_flags):
    """Executes universal parsing optimizations driven completely by semantic layout logic."""
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
        log_audit_event("Scrubbed Text Noise from Numeric Classes", f"Targeted: {numeric_cols}")

        for col in text_cols:
            if df_clean[col].astype(str).str.contains('_').sum() / len(df_clean) > 0.4:
                df_clean[col] = df_clean[col].astype(str).str.replace('_', ' ', regex=False)
                try:
                    df_clean[col] = df_clean[col].str.split().str[0] + ' ' + df_clean[col].str.split().str[1]
                except:
                    pass
            df_clean[col] = df_clean[col].astype(str).str.strip().str.title()
        log_audit_event("Standardized Nominal Text Fields to Human-Readable Format")

    # 2. Dynamic Algebraic Imputation Loop
    if config_flags['smart_impute'] and len(numeric_cols) >= 3:
        rules = discover_algebraic_identities(df_clean, numeric_cols)
        for rule_type, colA, colB, colC in rules:
            if rule_type == 'multiply':
                mask_c = df_clean[colC].isnull() & df_clean[colA].notnull() & df_clean[colB].notnull()
                df_clean.loc[mask_c, colC] = df_clean.loc[mask_c, colA] * df_clean.loc[mask_c, colB]
                
                mask_a = df_clean[colA].isnull() & df_clean[colC].notnull() & df_clean[colB].notnull() & (df_clean[colB] > 0)
                df_clean.loc[mask_a, colA] = df_clean.loc[mask_a, colC] / df_clean.loc[mask_a, colB]
                
                mask_b = df_clean[colB].isnull() & df_clean[colC].notnull() & df_clean[colA].notnull() & (df_clean[colA] > 0)
                df_clean.loc[mask_b, colB] = df_clean.loc[mask_b, colC] / df_clean.loc[mask_b, colA]
                
                log_audit_event("Algebraic Imputation Triggered", f"Applied Multiplicative Rule Matrix: {colA} * {colB} = {colC}")

    # 3. Statistical IQR Outlier Filtering Engine
    if config_flags['stat_outliers']:
        initial_count = len(df_clean)
        for col in numeric_cols:
            q1 = df_clean[col].quantile(0.25)
            q3 = df_clean[col].quantile(0.75)
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            df_clean = df_clean[(df_clean[col] >= lower_bound) & (df_clean[col] <= upper_bound)]
        dropped_rows = initial_count - len(df_clean)
        log_audit_event("Statistical Outlier Filtering", f"Purged {dropped_rows} anomaly vectors violating 1.5 IQR bounds.")

    # 4. Handle remaining null records via population medians
    if config_flags['fix_nulls']:
        for col in numeric_cols:
            null_count = int(df_clean[col].isnull().sum())
            if null_count > 0:
                df_clean[col] = df_clean[col].fillna(df_clean[col].median())
                log_audit_event("Median Imputation Execution", f"Imputed {null_count} nulls in numeric column: `{col}`")
        for col in text_cols:
            df_clean[col] = df_clean[col].replace(['Nan', 'None', 'Null', ''], np.nan).fillna("Unspecified Field")

    # 5. Standardize Dates
    if config_flags['date_standard']:
        for col in date_cols:
            df_clean[col] = pd.to_datetime(df_clean[col], errors='coerce').dt.strftime('%Y-%m-%d')
        log_audit_event("Chronological Metric Standardization", f"Formatted columns: {date_cols}")

    # 6. Drop Duplicates
    if config_flags['purge_dupes']:
        dupe_count = int(df_clean.duplicated().sum())
        df_clean = df_clean.drop_duplicates()
        if dupe_count > 0:
            log_audit_event("Deduplication Sweep", f"Removed {dupe_count} duplicate row vectors.")

    return df_clean

# --- USER INTERFACE ACCESS SYSTEM ---
st.sidebar.header("🔑 Cryptographic Authentication")
user_tier = st.sidebar.radio("Authorization Node", ["Free / Guest User", "Premium Member / Admin Login", "🌟 Register Secure Passkey"])

has_full_access = False

if user_tier == "Free / Guest User":
    if st.session_state.current_logged_user:
        track_active_session(st.session_state.current_logged_user, action="logout")
        st.session_state.current_logged_user = None
    st.sidebar.info("ℹ️ Free tier limited to maximum 60 rows × 60 columns processing slice.")

elif user_tier == "🌟 Register Secure Passkey":
    reg_user = st.sidebar.text_input("Choose Username")
    reg_pass = st.sidebar.text_input("Create Private Passkey", type="password")
    invite_code = st.sidebar.text_input("Enterprise Verification Pass", type="password")
    if st.sidebar.button("Register Key Node 🚀"):
        if hash_passkey(invite_code) == DEFAULT_INVITE_HASH:
            if reg_user.strip() and reg_pass.strip():
                register_secure_user(reg_user, reg_pass)
                st.sidebar.success("✔️ Cryptographic signature saved. Proceed to Login.")
            else:
                st.sidebar.error("❌ Fields cannot be empty.")
        else:
            st.sidebar.error("❌ Verification failed: Unauthorized invitation code signature.")

elif user_tier == "Premium Member / Admin Login":
    login_user = st.sidebar.text_input("Username").lower().strip()
    login_pass = st.sidebar.text_input("Enter Passkey", type="password")
    if login_user and login_pass:
        hashed_input = hash_passkey(login_pass)
        if login_user in secure_vault and secure_vault[login_user] == hashed_input:
            if st.session_state.current_logged_user == login_user:
                has_full_access = True
                st.sidebar.success(f"🔥 Secure Node Active: Welcome back, {login_user.title()}.")
            else:
                if track_active_session(login_user, action="login"):
                    st.session_state.current_logged_user = login_user
                    has_full_access = True
                    st.sidebar.success(f"🔥 Session Authenticated: Welcome, {login_user.title()}.")
                else:
                    st.sidebar.error("🚨 Collision Block: Account session active on another device node.")
        else:
            if login_pass != "":
                st.sidebar.error("❌ Security Violation: Invalid signature credentials.")

# --- MAIN ENGINE CONTROL LAYER ---
st.title("🧬 Advanced Polymorphic Meta-Engine & Reproducibility Suite")
st.write("An autonomous, self-correcting data cleaning engine that logs, audits, and normalizes unstructured files.")

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Meta-Pipeline Directives")
flags = {
    'fix_nulls': st.sidebar.checkbox("Statistical Median Null Imputation", value=True),
    'smart_impute': st.sidebar.checkbox("🧠 Polymorphic Identity Extraction", value=True),
    'stat_outliers': st.sidebar.checkbox("📊 Statistical IQR Outlier Purge", value=True),
    'purge_dupes': st.sidebar.checkbox("Purge Redundant Matrix Profiles", value=True),
    'clean_strings': st.sidebar.checkbox("Strip Currency Noise & Standardize Text", value=True),
    'date_standard': st.sidebar.checkbox("📅 Smart Chronological Formatter", value=True)
}
push_to_database = st.sidebar.checkbox("Index Clean Tables into Backend SQLite")

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

    # Diagnostic Visuals Report
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
        
        st.session_state.audit_log = [] # Clear history on fresh execution
        log_audit_event("Ingested File Instance", f"Filename: {my_raw_file.name} | Dimensions: {total_rows}x{total_cols}")
        
        log_txt.text("Phase 1: Running semantic heuristic vector scans...")
        prog.progress(30)
        
        log_txt.text("Phase 2: Calculating algebraic permutation matrices...")
        prog.progress(60)
        
        try:
            working_df = execute_polymorphic_cleaning(working_df, flags)
            prog.progress(100)
            log_txt.success("✨ Engine successfully normalized the target matrix with zero exceptions!")
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
            st.sidebar.info("🚀 Indexed into local SQLite database.")
        except Exception as dbe:
            st.sidebar.error(f"Database Exception: {dbe}")

    st.markdown("---")
    st.subheader("💾 Production Export Center")
    ex1, ex2 = st.columns(2)
    with ex1:
        st.markdown("#### 📊 Dataset Asset")
        if is_csv:
            st.download_button("📥 Download Universal Clean CSV", data=working_df.to_csv(index=False).encode('utf-8'), file_name=f"sanitized_{my_raw_file.name}", mime="text/csv")
        else:
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as w:
                working_df.to_excel(w, index=False, sheet_name='Sanitized Frame')
            st.download_button("📥 Download Universal Clean Excel", data=buf.getvalue(), file_name=f"sanitized_{my_raw_file.name}", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with ex2:
        st.markdown("#### 📜 Transparency Audit Trail")
        audit_json = json.dumps(st.session_state.audit_log, indent=2)
        st.download_button("📥 Download Reproducible Audit Log (.json)", data=audit_json, file_name=f"audit_trail_{datetime.date.today()}.json", mime="application/json")

# System Feedback Terminal Block
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
    st.markdown("### 🔒 Encrypted Root Panel")
    if has_full_access and login_user == "admin":
        if os.path.exists("user_feedback_vault.txt"):
            with open("user_feedback_vault.txt", "r") as f:
                st.text(f.read())
        else:
            st.info("No logs present in vault.")
    else:
        st.info("🔒 Secure Admin configuration locked. Access requires Root Master authentication.")
