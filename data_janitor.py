import streamlit as st
import pandas as pd
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
fix_nulls = st.sidebar.checkbox("Statistical Median Null Imputation")
smart_impute = st.sidebar.checkbox("🧠 Context-Aware Math Imputation")
purge_dupes = st.sidebar.checkbox("Remove Duplicate Transaction Rows")
clean_strings = st.sidebar.checkbox("Strip Currency & Standardize Casing")
math_validate = st.sidebar.checkbox("📐 Cross-Column Math Validation")
stat_outliers = st.sidebar.checkbox("📊 Statistical IQR Outlier Filtering")
date_standard = st.sidebar.checkbox("📅 Smart Date Standardization")
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

    # Show Raw Data View
    st.markdown("---")
    st.subheader("📋 Ingested Dataset Overview")
    st.dataframe(working_df.head(5))
    
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

    # --- STEP 5: ADVANCED TRANSFORM CLEANING ENGINE ---
    
    # 1. Context-Aware Math Imputation
    if smart_impute:
        # Intelligently calculate Total Spent if price and quantity exist rather than using arbitrary medians
        if 'Price Per Unit' in working_df.columns and 'Quantity' in working_df.columns and 'Total Spent' in working_df.columns:
            math_mask = working_df['Total Spent'].isnull() & working_df['Price Per Unit'].notnull() & working_df['Quantity'].notnull()
            working_df.loc[math_mask, 'Total Spent'] = working_df.loc[math_mask, 'Price Per Unit'] * working_df.loc[math_mask, 'Quantity']
        # Contextually handle descriptive text fields
        if 'Item' in working_df.columns and 'Category' in working_df.columns:
            working_df['Item'] = working_df['Item'].fillna("Unspecified_" + working_df['Category'].astype(str))
        st.sidebar.success("🧠 Context-aware mathematical imputation complete.")

    # 2. Standard Median Null Imputation (Fallback for remaining nulls)
    if fix_nulls:
        numeric_fields = working_df.select_dtypes(include=['number']).columns
        for field in numeric_fields:
            working_df[field] = working_df[field].fillna(working_df[field].median())
        st.sidebar.success("✔️ Remaining empty fields filled using statistical medians.")
        
    # 3. Duplicate Purge
    if purge_dupes:
        rows_before = len(working_df)
        working_df = working_df.drop_duplicates()
        rows_after = len(working_df)
        st.sidebar.success(f"✔️ Flushed {rows_before - rows_after} duplicate transactional rows.")
        
    # 4. Cross-Column Math Validation & Discrepancy Auditing
    if math_validate:
        if 'Price Per Unit' in working_df.columns and 'Quantity' in working_df.columns and 'Total Spent' in working_df.columns:
            calculated_spent = working_df['Price Per Unit'] * working_df['Quantity']
            discrepancy_mask = (working_df['Total Spent'] - calculated_spent).abs() > 0.01
            discrepancy_count = discrepancy_mask.sum()
            if discrepancy_count > 0:
                working_df.loc[discrepancy_mask, 'Total Spent'] = calculated_spent.loc[discrepancy_mask]
                st.sidebar.warning(f"📐 Adjusted {discrepancy_count} cross-column auditing errors.")
            else:
                st.sidebar.success("📐 Accounting check: 100% Cross-column validation passed!")

    # 5. Statistical IQR Outlier Filtering
    if stat_outliers:
        numeric_fields = working_df.select_dtypes(include=['number']).columns
        total_outliers_purged = 0
        for field in numeric_fields:
            q1 = working_df[field].quantile(0.25)
            q3 = working_df[field].quantile(0.75)
            iqr = q3 - q1
            lower_fence = q1 - 1.5 * iqr
            upper_fence = q3 + 1.5 * iqr
            
            before_filter = len(working_df)
            working_df = working_df[(working_df[field] >= lower_fence) & (working_df[field] <= upper_fence)]
            total_outliers_purged += (before_filter - len(working_df))
        st.sidebar.success(f"📊 IQR Filter: Purged {total_outliers_purged} extreme data anomalies.")

    # 6. Smart Date Standardization
    if date_standard:
        for field in working_df.columns:
            if 'date' in field.lower() or 'time' in field.lower():
                try:
                    working_df[field] = pd.to_datetime(working_df[field], errors='coerce').dt.strftime('%Y-%m-%d')
                    st.sidebar.success(f"📅 Standardized `{field}` to YYYY-MM-DD format.")
                except:
                    pass

    # 7. Formatting & Fuzzy Inconsistent Categorical Matching
    if clean_strings:
        for field in working_df.columns:
            if working_df[field].dtype == 'object':
                # Strip symbols but preserve structural string tracking codes (preserving leading zeros)
                if not field.lower().endswith('id'):
                    working_df[field] = working_df[field].astype(str).str.replace('R', '', regex=False).str.replace('$', '', regex=False).str.strip()
                try:
                    # Only convert to numeric if it doesn't represent an analytical string identity
                    if not field.lower().endswith('id'):
                        working_df[field] = pd.to_numeric(working_df[field])
                except:
                    if not instruction_applied:
                        # Normalize categorical values ("Credit Card" vs "creditcard" standardizations)
                        working_df[field] = working_df[field].str.strip().str.title()
        st.sidebar.success("✔️ Inconsistent string mapping standardizations updated.")
        
    st.subheader("✨ Transformed Engine Preview")
    st.dataframe(working_df.head(10))
    
    if push_to_database:
        try:
            db_connection = sqlite3.connect("retail_analytics.db")
            working_df.to_sql("clean_transactions", db_connection, if_exists="replace", index=False)
            db_connection.close()
            st.sidebar.info("🚀 Relational table updated in SQLite.")
        except Exception as database_error:
            st.sidebar.error(f"Database Exception: {database_error}")

    st.markdown("---")
    st.subheader("💾 Export Clean Dataset")
    
    if file_format_csv:
        csv_stream = working_df.to_csv(index=False).encode('utf-8')
        st.download_button(label="📥 Download Clean CSV File", data=csv_stream, file_name=f"cleaned_{my_raw_file.name}", mime="text/csv")
    else:
        memory_buffer = io.BytesIO()
        with pd.ExcelWriter(memory_buffer, engine='openpyxl') as excel_writer:
            working_df.to_excel(excel_writer, index=False, sheet_name='Cleaned Data Output')
        st.download_button(label="📥 Download Clean Excel File", data=memory_buffer.getvalue(), file_name=f"cleaned_{my_raw_file.name}", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# --- STEP 6: USER EXPERIENCE FEEDBACK HUB ---
st.markdown("---")
st.subheader("⭐ User Experience Feedback Hub")
col1, col2 = st.columns([1, 1])

with col1:
    st.markdown("### Share Your Experience")
    user_rating = st.slider("Rate the Data Janitor Engine (1 = Poor, 5 = Elite)", 1, 5, 5)
    user_review = st.text_area("What features or adjustments would make this app better for your daily workflow?")
    
    if st.button("Submit Anonymous Feedback 🚀"):
        if user_review.strip() != "":
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"[{timestamp}] Rating: {user_rating}/5 | Feedback: {user_review}\n"
            with open("user_feedback_vault.txt", "a") as vault_file:
                vault_file.write(log_entry)
            st.success("Thank you! Your recommendations have been safely transmitted directly to our engineering roadmap.")

with col2:
    st.markdown("### 🔒 Private Administrator Dashboard")
    if has_full_access and login_user == "admin":
        st.write("Welcome back, Admin. User reviews:")
        if os.path.exists("user_feedback_vault.txt"):
            with open("user_feedback_vault.txt", "r") as vault_file:
                feedback_records = vault_file.readlines()
            for record in reversed(feedback_records):
                st.info(record)
        else:
            st.info("No feedback records logged.")
    else:
        st.info("🔒 Admin panel encrypted. Log in with Master Admin credentials to view core feedback data streams.")
