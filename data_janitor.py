import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import io
import os
import datetime
import json

# Custom page layout for the web engine
st.set_page_config(page_title="Data Janitor Premium Engine", page_icon="🧼", layout="wide")

# --- DATABASE / LOCAL PERSISTENT STORAGE SIMULATION ---
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

# --- PIPELINE MODULAR ADVANCED CLEANING ENGINE FUNCTIONS ---

def clean_currency_and_strings(df, selected_columns=None):
    """Safely strips currency symbols ONLY from financial vectors to prevent breaking general text."""
    df_clean = df.copy()
    if not selected_columns:
        selected_columns = [col for col in df_clean.columns if any(x in col.lower() for x in ['price', 'spent', 'amount', 'cost'])]
    
    for col in selected_columns:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].astype(str).str.replace('R', '', regex=False)
            df_clean[col] = df_clean[col].str.replace('$', '', regex=False).str.strip()
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
            
    for col in df_clean.select_dtypes(include=['object']).columns:
        if not col.lower().endswith('id') and col not in selected_columns:
            df_clean[col] = df_clean[col].astype(str).str.strip().str.title()
            
    return df_clean

def clean_context_imputation(df):
    """Computes empty entries using cross-column dependencies and enforces zero-bounds."""
    df_clean = df.copy()
    if all(c in df_clean.columns for c in ['Price Per Unit', 'Quantity', 'Total Spent']):
        math_mask = df_clean['Total Spent'].isnull() & df_clean['Price Per Unit'].notnull() & df_clean['Quantity'].notnull()
        df_clean.loc[math_mask, 'Total Spent'] = df_clean.loc[math_mask, 'Price Per Unit'] * df_clean.loc[math_mask, 'Quantity']
        
        for financial_col in ['Price Per Unit', 'Total Spent']:
            if financial_col in df_clean.columns:
                df_clean[financial_col] = df_clean[financial_col].clip(lower=0.0)
            
    if 'Item' in df_clean.columns and 'Category' in df_clean.columns:
        item_mask = df_clean['Item'].isnull() & df_clean['Category'].notnull()
        df_clean.loc[item_mask, 'Item'] = "Unspecified_" + df_clean.loc[item_mask, 'Category'].astype(str)
        df_clean['Item'] = df_clean['Item'].fillna("Unspecified_UnknownCategory")
        
    return df_clean

def display_visual_comparison(original_df, cleaned_df):
    """Renders a side-by-side framework with highlighting showing modified rows."""
    st.markdown("### 🔄 Delta Engine Validation View")
    st.write("Review the differences below. Processed layout datasets are displayed side-by-side.")
    
    orig_sample = original_df.head(10).reset_index(drop=True)
    clean_sample = cleaned_df.head(10).reset_index(drop=True)
    
    col_orig, col_clean = st.columns(2)
    with col_orig:
        st.markdown("**📋 Original Ingested Sample**")
        st.dataframe(orig_sample)
    with col_clean:
        st.markdown("**✨ Cleaned Pipeline Output (Changes Highlighted)**")
        try:
            # Highlight cells where values have changed from the original input
            styled_clean = clean_sample.style.apply(
                lambda x: np.where(orig_sample != clean_sample, 'background-color: rgba(46, 204, 113, 0.25)', ''), 
                axis=None
            )
            st.dataframe(styled_clean)
        except:
            st.dataframe(clean_sample)

# --- STEP 1: GATEKEEPER & ACCESS CONTROL ---
st.sidebar.header("🔑 App Access Control")
user_tier = st.sidebar.radio("Your Current Tier", ["Free / Guest User", "Premium Member / Admin Login", "🌟 Register Custom Passkey"])

has_full_access = False

if user_tier == "Free / Guest User":
    if st.session_state.current_logged_user:
        track_active_session(st.session_state.current_logged_user, action="logout")
        st.session_state.current_logged_user = None
    st.sidebar.info("ℹ️ Free tier limits: Maximum 60 Rows and 60 Columns.")

elif user_tier == "🌟 Register Custom Passkey":
    st.sidebar.subheader("Create Your Custom Access Key")
    reg_user = st.sidebar.text_input("Choose Username")
    reg_pass = st.sidebar.text_input("Create Custom Passkey", type="password")
    invite_code = st.sidebar.text_input("Enter Premium Invitation Verification Code", type="password")
    
    if st.sidebar.button("Register Key 🚀"):
        if invite_code == "123Shelby@":
            if reg_user.strip() != "" and reg_pass.strip() != "":
                save_premium_key(reg_user, reg_pass)
                st.sidebar.success(f"✔️ Key registered for {reg_user}! Select 'Premium Member Login' to sign in.")
            else:
                st.sidebar.error("❌ Username or Passkey fields cannot be left blank.")
        else:
            st.sidebar.error("❌ Invalid Invitation Code. Paid subscription verification failed.")

elif user_tier == "Premium Member / Admin Login":
    login_user = st.sidebar.text_input("Username").lower().strip()
    login_pass = st.sidebar.text_input("Enter Passkey", type="password")
    
    if login_user and login_pass:
        if login_user in premium_vault and premium_vault[login_user] == login_pass:
            if st.session_state.current_logged_user == login_user:
                has_full_access = True
                st.sidebar.success(f"🔥 Welcome back, {login_user.title()}! Constraints removed.")
            else:
                allowed = track_active_session(login_user, action="login")
                if allowed:
                    st.session_state.current_logged_user = login_user
                    has_full_access = True
                    st.sidebar.success(f"🔥 Success! Logged in as {login_user.title()}. Constraints removed.")
                else:
                    st.sidebar.error("🚨 Access Denied: Account active on another window/device.")
        else:
            if login_pass != "":
                st.sidebar.error("❌ Invalid Username or Passkey entry.")

# --- STEP 2: MAIN INTERFACE DISPLAY ---
st.title("🧼 Automated Data Cleaner & Relational Analytics Dashboard")
st.write("A customized Python data engine built to handle messy business spreadsheets and load them into relational SQL tables.")

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Advanced Cleaning Suite")
fix_nulls = st.sidebar.checkbox("Statistical Median Null Imputation", value=True)
smart_impute = st.sidebar.checkbox("🧠 Context-Aware Math Imputation", value=True)
purge_dupes = st.sidebar.checkbox("Remove Duplicate Transaction Rows", value=True)
clean_strings = st.sidebar.checkbox("Strip Currency & Standardize Casing", value=True)
math_validate = st.sidebar.checkbox("📐 Cross-Column Math Validation", value=True)
stat_outliers = st.sidebar.checkbox("📊 Statistical IQR Outlier Filtering")
date_standard = st.sidebar.checkbox("📅 Smart Date Standardization", value=True)
push_to_database = st.sidebar.checkbox("Index Clean Tables into Backend SQLite")

my_raw_file = st.file_uploader("Drop your messy retail dataset here", type=["csv", "xlsx"])

if my_raw_file is not None:
    file_format_csv = my_raw_file.name.endswith('.csv')
    
    try:
        loaded_df = pd.read_csv(my_raw_file) if file_format_csv else pd.read_excel(my_raw_file)
    except Exception as read_error:
        st.error(f"❌ File Reading Disruption: Structure is corrupted. Details: {read_error}")
        st.stop()
        
    total_raw_rows = len(loaded_df)
    total_raw_cols = len(loaded_df.columns)
    
    # --- STEP 3: AUTOMATED 60-ROW & 60-COLUMN SLICER FOR GUESTS ---
    if not has_full_access:
        if total_raw_rows > 60 or total_raw_cols > 60:
            st.warning(f"⚠️ **Free Tier Limit Applied!** Original file size was **{total_raw_rows} rows × {total_raw_cols} columns**. Sliced down to maximum constraints of **60 rows × 60 columns**.")
            row_cutoff = min(total_raw_rows, 60)
            col_cutoff = min(total_raw_cols, 60)
            working_df = loaded_df.iloc[:row_cutoff, :col_cutoff].copy()
        else:
            working_df = loaded_df.copy()
    else:
        working_df = loaded_df.copy()

    # Create a completely untouched anchor duplicate of original ingestion state to calculate delta highlights
    working_df_original = working_df.copy()

    # --- AUTOMATED DATA HEALTH DIAGNOSTIC REPORT ---
    st.markdown("---")
    st.subheader("📊 Automated Data Health & Integrity Report")
    
    total_nulls = int(working_df.isnull().sum().sum())
    total_duplicates = int(working_df.duplicated().sum())
    total_columns = len(working_df.columns)
    current_rows = len(working_df)
    
    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    with metric_col1:
        st.metric(label="Total Rows Ingested", value=current_rows)
    with metric_col2:
        st.metric(label="Columns Detected", value=total_columns)
    with metric_col3:
        st.metric(label="Missing (Null) Cells", value=total_nulls, delta="- Action Required" if total_nulls > 0 else "Clean", delta_color="inverse" if total_nulls > 0 else "normal")
    with metric_col4:
        st.metric(label="Duplicate Rows Found", value=total_duplicates, delta="- Action Required" if total_duplicates > 0 else "Clean", delta_color="inverse" if total_duplicates > 0 else "normal")

    # --- STEP 4: CUSTOM AI COMMAND CENTER ---
    st.markdown("---")
    st.subheader("🤖 Custom AI Command Center")
    user_instruction = st.text_input("Give a custom cleaning order (e.g., 'drop column Location', 'uppercase Category')", placeholder="Type your instruction here...")
    
    instruction_applied = False
    custom_message = ""
    
    if user_instruction:
        cmd = user_instruction.lower().strip()
        try:
            if "drop column" in cmd or "delete column" in cmd or "remove column" in cmd:
                col_to_drop = user_instruction.split()[-1]
                matched_cols = [c for c in working_df.columns if c.lower() == col_to_drop.lower()]
                if matched_cols:
                    working_df = working_df.drop(columns=matched_cols)
                    custom_message = f"🎯 AI Command Executed: Successfully dropped column `{matched_cols[0]}`!"
                    instruction_applied = True
            elif "uppercase" in cmd:
                col_to_upper = user_instruction.split()[-1]
                matched_cols = [c for c in working_df.columns if c.lower() == col_to_upper.lower()]
                if matched_cols:
                    working_df[matched_cols[0]] = working_df[matched_cols[0]].astype(str).str.upper()
                    custom_message = f"🎯 AI Command Executed: Transformed column `{matched_cols[0]}` to UPPERCASE!"
                    instruction_applied = True
            elif "clear nulls" in cmd or "fix nulls" in cmd:
                working_df = working_df.dropna()
                custom_message = "🎯 AI Command Executed: Purged rows containing missing cells completely!"
                instruction_applied = True
        except Exception as ai_err:
            custom_message = f"❌ Failed to parse instruction. Error detail: {ai_err}"

    if custom_message:
        st.info(custom_message)

    # --- STEP 5: AUTOMATED MODULAR PIPELINE EXECUTION WITH PROGRESS INDICATORS ---
    st.markdown("---")
    st.subheader("⚙️ Processing Engine Execution Log")
    
    if st.button("⚡ Run Industrial Clean Engines"):
        cleaning_progress = st.progress(0)
        status_text = st.empty()
        
        try:
            # Phase 1: Currency Processing
            status_text.text("🧼 Isolating and scrubbing mixed currency formats...")
            if clean_strings:
                working_df = clean_currency_and_strings(working_df)
            cleaning_progress.progress(25)
            
            # Phase 2: Context Mathematical Alignments
            status_text.text("🧠 Re-calculating empty metrics and enforcing non-negative boundaries...")
            if smart_impute:
                working_df = clean_context_imputation(working_df)
            cleaning_progress.progress(50)
            
            # Phase 3: Cross-Column Math Checks
            status_text.text("📐 Executing financial cross-column audits...")
            if math_validate:
                if 'Price Per Unit' in working_df.columns and 'Quantity' in working_df.columns and 'Total Spent' in working_df.columns:
                    calculated_spent = working_df['Price Per Unit'] * working_df['Quantity']
                    discrepancy_mask = (working_df['Total Spent'] - calculated_spent).abs() > 0.01
                    working_df.loc[discrepancy_mask, 'Total Spent'] = calculated_spent.loc[discrepancy_mask]
            cleaning_progress.progress(70)
            
            # Phase 4: Remaining Logic & Outliers
            status_text.text("📊 Applying IQR outlier logic and processing dates...")
            if fix_nulls:
                numeric_fields = working_df.select_dtypes(include=['number']).columns
                for field in numeric_fields:
                    working_df[field] = working_df[field].fillna(working_df[field].median())
            
            if purge_dupes:
                working_df = working_df.drop_duplicates()
                
            if stat_outliers:
                numeric_fields = working_df.select_dtypes(include=['number']).columns
                for field in numeric_fields:
                    q1 = working_df[field].quantile(0.25)
                    q3 = working_df[field].quantile(0.75)
                    iqr = q3 - q1
                    working_df = working_df[(working_df[field] >= (q1 - 1.5 * iqr)) & (working_df[field] <= (q3 + 1.5 * iqr))]
                    
            if date_standard:
                for field in working_df.columns:
                    if 'date' in field.lower() or 'time' in field.lower():
                        working_df[field] = pd.to_datetime(working_df[field], errors='coerce').dt.strftime('%Y-%m-%d')
            
            cleaning_progress.progress(100)
            status_text.success("✨ Industrial scrubbing pipeline executed successfully with 0 exceptions!")
            
        except Exception as pipeline_error:
            st.error(f"❌ Critical Exception during processing step: {pipeline_error}")

    # --- VISUAL COMPARISON INTERFACE ---
    display_visual_comparison(working_df_original, working_df)
    
    # --- STEP 6: SQL BACKEND INDEXING ---
    if push_to_database:
        try:
            db_connection = sqlite3.connect("retail_analytics.db")
            working_df.to_sql("clean_transactions", db_connection, if_exists="replace", index=False)
            db_connection.close()
            st.sidebar.info("🚀 Relational table updated in SQLite.")
        except Exception as database_error:
            st.sidebar.error(f"Database Exception: {database_error}")

    # --- STEP 7: SECURE SPREADSHEET EXPORT ENGINE ---
    st.markdown("---")
    st.subheader("💾 Export Clean Dataset")
    
    if file_format_csv:
        csv_stream = working_df.to_csv(index=False).encode('utf-8')
        st.download_button(label="📥 Download Clean CSV File", data=csv_stream, file_name=f"cleaned_{my_raw_file.name}", mime="text/csv")
    else:
        memory_buffer = io.BytesIO()
        with pd.ExcelWriter(memory_buffer, engine='openpyxl') as excel_writer:
            working_df.to_excel(excel_writer, index=False, sheet_name='Cleaned Data Output')
        st.download_button(label="📥 Download Clean Excel File", data=memory_buffer.getvalue(), file_name=f"cleaned_{my_raw_file.name}",
