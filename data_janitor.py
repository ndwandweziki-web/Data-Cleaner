import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import io
import os
import datetime
import json
import re

# Premium UI Configuration
st.set_page_config(page_title="Polymorphic Meta-Engine v2.0", page_icon="🧬", layout="wide")

# --- APP ACCESS CONTROL & SESSION TRACKING ---
USER_DB_FILE = "premium_users_vault.json"
SESSION_LOG_FILE = "active_sessions_tracker.json"

def load_premium_keys():
    default_vault = {"admin": "123Shelby@"}
    if not os.path.exists(USER_DB_FILE):
        with open(USER_DB_FILE, "w") as f:
            json.dump(default_vault, f)
        return default_vault
    try:
        with open(USER_DB_FILE, "r") as f:
            return json.load(f)
    except:
        return default_vault

def save_premium_key(username, new_password):
    vault = load_premium_keys()
    vault[username.lower().strip()] = new_password.strip()
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

premium_vault = load_premium_keys()
if 'current_logged_user' not in st.session_state:
    st.session_state.current_logged_user = None

# --- CORE POLYMORPHIC DATA PROCESSING ENGINE ---

def profile_semantic_types(df):
    """
    Phase 1: Analyzes data distributions to deduce column intent without relying on column names.
    Returns a dictionary mapping column names to their discovered semantic category.
    """
    profiles = {}
    for col in df.columns:
        # Cast a sample to string for regex checks
        sample_str = df[col].dropna().head(100).astype(str).str.strip()
        if sample_str.empty:
            profiles[col] = "empty"
            continue
            
        # Check for Date/Time signatures
        date_hits = sample_str.apply(lambda x: 1 if re.match(r'^\d{4}[-/]\d{2}[-/]\d{2}', x) or re.search(r'\d{2}/', x) else 0).sum()
        if date_hits / len(sample_str) > 0.5:
            profiles[col] = "date"
            continue

        # Check for mixed currency string noise
        currency_hits = sample_str.apply(lambda x: 1 if any(symbol in x for symbol in ['R', '$', '€', '£']) else 0).sum()
        
        # Coerce column to see if it's fundamentally numerical
        numeric_coerced = pd.to_numeric(df[col].astype(str).str.replace(r'[R\$\s,]', '', regex=True), errors='coerce')
        valid_numeric_ratio = numeric_coerced.notnull().sum() / len(df[col])
        
        if valid_numeric_ratio > 0.6 or currency_hits / len(sample_str) > 0.3:
            profiles[col] = "numeric"
            continue
            
        # Differentiate between unique relational system codes and descriptive text fields
        unique_ratio = df[col].nunique() / len(df[col]) if len(df[col]) > 0 else 0
        if unique_ratio > 0.8 and any(token in col.lower() for token in ['id', 'key', 'code', 'pk']):
            profiles[col] = "system_key"
        else:
            profiles[col] = "categorical_text"
            
    return profiles

def discover_algebraic_identities(df, numeric_columns):
    """
    Phase 2: Runs programmatic permutations across all numerical vectors to find linear equations.
    Deduces relationships like: Col_A * Col_B = Col_C or Col_A + Col_B = Col_C
    """
    identities = []
    if len(numeric_columns) < 3:
        return identities

    # Sample non-null validation rows to test integrity formulas
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
                
                # Test Multiplicative Rule: A * B == C
                if np.allclose(A * B, C, rtol=1e-2, atol=1e-2):
                    identities.append(('multiply', cols[i], cols[j], cols[k]))
                    return identities # Return earliest complete matching matrix rule
                # Test Additive Rule: A + B == C
                if np.allclose(A + B, C, rtol=1e-2, atol=1e-2):
                    identities.append(('add', cols[i], cols[j], cols[k]))
                    return identities
    return identities

def execute_polymorphic_cleaning(df, config_flags):
    """
    Executes universal parsing optimizations driven completely by semantic layout logic.
    """
    df_clean = df.copy()
    semantic_map = profile_semantic_types(df_clean)
    
    # Identify localized sub-vectors
    numeric_cols = [c for c, t in semantic_map.items() if t == "numeric"]
    text_cols = [c for c, t in semantic_map.items() if t == "categorical_text"]
    date_cols = [c for c, t in semantic_map.items() if t == "date"]

    # 1. Strip currency and non-numeric artifacts safely
    if config_flags['clean_strings']:
        for col in numeric_cols:
            df_clean[col] = df_clean[col].astype(str).str.replace(r'[R\$\s,€£]', '', regex=True)
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')

        # Human-Readable Optimization Loop for encoded system tokens (e.g., Item_10_PAT -> Item 10)
        for col in text_cols:
            if df_clean[col].astype(str).str.contains('_').sum() / len(df_clean) > 0.4:
                df_clean[col] = df_clean[col].astype(str).str.replace('_', ' ', regex=False)
                try:
                    df_clean[col] = df_clean[col].str.split().str[0] + ' ' + df_clean[col].str.split().str[1]
                except:
                    pass
            df_clean[col] = df_clean[col].astype(str).str.strip().str.title()

    # 2. Dynamic Identity Discovery and Algebraic Imputation Loop
    if config_flags['smart_impute'] and len(numeric_cols) >= 3:
        rules = discover_algebraic_identities(df_clean, numeric_cols)
        for rule_type, colA, colB, colC in rules:
            if rule_type == 'multiply':
                # Reconstruct C (Total)
                mask_c = df_clean[colC].isnull() & df_clean[colA].notnull() & df_clean[colB].notnull()
                df_clean.loc[mask_c, colC] = df_clean.loc[mask_c, colA] * df_clean.loc[mask_c, colB]
                # Reconstruct A (Price)
                mask_a = df_clean[colA].isnull() & df_clean[colC].notnull() & df_clean[colB].notnull() & (df_clean[colB] > 0)
                df_clean.loc[mask_a, colA] = df_clean.loc[mask_a, colC] / df_clean.loc[mask_a, colB]
                # Reconstruct B (Quantity)
                mask_b = df_clean[colB].isnull() & df_clean[colC].notnull() & df_clean[colA].notnull() & (df_clean[colA] > 0)
                df_clean.loc[mask_b, colB] = df_clean.loc[mask_b, colC] / df_clean.loc[mask_b, colA]

    # 3. Handle remaining null records using statistical metrics
    if config_flags['fix_nulls']:
        for col in numeric_cols:
            df_clean[col] = df_clean[col].fillna(df_clean[col].median())
        for col in text_cols:
            df_clean[col] = df_clean[col].replace(['Nan', 'None', 'Null', ''], np.nan)
            df_clean[col] = df_clean[col].fillna("Unspecified Field")

    # 4. Standardize any field discovered to be a date vector
    if config_flags['date_standard']:
        for col in date_cols:
            df_clean[col] = pd.to_datetime(df_clean[col], errors='coerce').dt.strftime('%Y-%m-%d')

    # 5. Drop duplicate historical profiles
    if config_flags['purge_dupes']:
        df_clean = df_clean.drop_duplicates()

    return df_clean

# --- GATEKEEPER SIDEBAR INTERFACE ---
st.sidebar.header("🔑 Engine Access Validation")
user_tier = st.sidebar.radio("Authorization Status", ["Free / Guest User", "Premium Member / Admin Login", "🌟 Register Custom Passkey"])

has_full_access = False

if user_tier == "Free / Guest User":
    if st.session_state.current_logged_user:
        track_active_session(st.session_state.current_logged_user, action="logout")
        st.session_state.current_logged_user = None
    st.sidebar.info("ℹ️ Free tier limited to maximum 60 rows × 60 columns processing slice.")

elif user_tier == "🌟 Register Custom Passkey":
    reg_user = st.sidebar.text_input("Choose Username")
    reg_pass = st.sidebar.text_input("Create Custom Passkey", type="password")
    invite_code = st.sidebar.text_input("Verification Code", type="password")
    if st.sidebar.button("Register Engine Access Key 🚀"):
        if invite_code == "123Shelby@":
            if reg_user.strip() and reg_pass.strip():
                save_premium_key(reg_user, reg_pass)
                st.sidebar.success("✔️ Key registered! Select 'Premium Member Login' to verify.")
            else:
                st.sidebar.error("❌ Credentials cannot be empty.")
        else:
            st.sidebar.error("❌ Verification failed.")

elif user_tier == "Premium Member / Admin Login":
    login_user = st.sidebar.text_input("Username").lower().strip()
    login_pass = st.sidebar.text_input("Enter Passkey", type="password")
    if login_user and login_pass:
        if login_user in premium_vault and premium_vault[login_user] == login_pass:
            if st.session_state.current_logged_user == login_user:
                has_full_access = True
                st.sidebar.success(f"🔥 Welcome back {login_user.title()}! Access granted.")
            else:
                if track_active_session(login_user, action="login"):
                    st.session_state.current_logged_user = login_user
                    has_full_access = True
                    st.sidebar.success(f"🔥 Success! Logged in as {login_user.title()}.")
                else:
                    st.sidebar.error("🚨 Active Session Blocked: Session running elsewhere.")
        else:
            if login_pass != "":
                st.sidebar.error("❌ Invalid authorization key.")

# --- MAIN DASHBOARD WINDOW ---
st.title("🧬 Autonomous Polymorphic Meta-Engine")
st.write("An advanced self-correcting ingestion framework built to automatically profile, audit, and clean unstructured tables.")

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Meta-Pipeline Settings")
flags = {
    'fix_nulls': st.sidebar.checkbox("Statistical Median Null Imputation", value=True),
    'smart_impute': st.sidebar.checkbox("🧠 Polymorphic Identity Extraction", value=True),
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
        st.warning(f"⚠️ **Free Tier Slicer Triggered!** File size restricted down from {total_rows}x{total_cols} to 60x60 constraints.")
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
    m3.metric("Discovered Missing Cells", int(working_df.isnull().sum().sum()))
    m4.metric("Discovered Redundant Duplicates", int(working_df.duplicated().sum()))

    # Processing Core Action
    st.markdown("---")
    st.subheader("⚙️ Meta-Pipeline Operational Log")
    if st.button("⚡ Trigger Universal Polymorphic Scrubbing"):
        prog = st.progress(0)
        log_txt = st.empty()
        
        log_txt.text("Phase 1: Running heuristic vector token scanning...")
        prog.progress(30)
        
        log_txt.text("Phase 2: Calculating algebraic relationship correlation arrays...")
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
            st.sidebar.info("🚀 Indexed into local SQLite.")
        except Exception as dbe:
            st.sidebar.error(f"Database Exception: {dbe}")

    st.markdown("---")
    st.subheader("💾 Export Sanitized Frame")
    if is_csv:
        st.download_button("📥 Download Universal Clean CSV", data=working_df.to_csv(index=False).encode('utf-8'), file_name=f"sanitized_{my_raw_file.name}", mime="text/csv")
    else:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as w:
            working_df.to_excel(w, index=False, sheet_name='Sanitized Frame')
        st.download_button("📥 Download Universal Clean Excel", data=buf.getvalue(), file_name=f"sanitized_{my_raw_file.name}", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# Feedback Terminal Block
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
