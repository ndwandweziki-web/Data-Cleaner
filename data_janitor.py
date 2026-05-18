import streamlit as st
import pandas as pd
import sqlite3
import io
import os
import datetime

# Custom page layout for the web engine
st.set_page_config(page_title="Data Cleaner Portfolio", layout="wide")

# --- STEP 1: GATEKEEPER & ACCESS PRIVILEGES ---
st.sidebar.header("🔑 App Access Control")
user_tier = st.sidebar.radio("Your Current Tier", ["Free / Guest User", "Admin / Premium Login"])

has_full_access = False

if user_tier == "Admin / Premium Login":
    entered_pass = st.sidebar.text_input("Enter Passkey", type="password")
    
    if entered_pass == "123Shelby@":
        st.sidebar.success("🔥 Admin access granted. Rows limit removed!")
        has_full_access = True
    elif entered_pass != "":
        st.sidebar.error("❌ Locked out. Stick to Free Tier rules.")

# --- STEP 2: MAIN INTERFACE DISPLAY ---
st.title("🧼 Automated Data Cleaner & Relational Analytics Dashboard")
st.write("A customized Python data engine built to handle messy business spreadsheets and load them into relational SQL tables.")

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Cleaning Operations Panel")
fix_nulls = st.sidebar.checkbox("Statistical Median Null Imputation")
purge_dupes = st.sidebar.checkbox("Remove Duplicate Transaction Rows")
clean_strings = st.sidebar.checkbox("Strip Currency (R / $) & Standardize Casing")
push_to_database = st.sidebar.checkbox("Index Clean Tables into Backend SQLite")

# File uploader section supporting CSV and Excel spreadsheets
my_raw_file = st.file_uploader("Drop your messy retail dataset here", type=["csv", "xlsx"])

if my_raw_file is not None:
    file_format_csv = my_raw_file.name.endswith('.csv')
    
    try:
        loaded_df = pd.read_csv(my_raw_file) if file_format_csv else pd.read_excel(my_raw_file)
    except Exception as read_error:
        st.error(f"❌ File Reading Disruption: Structure is corrupted. Details: {read_error}")
        st.stop()
        
    total_dataset_rows = len(loaded_df)
    
    if not has_full_access and total_dataset_rows > 50:
        st.warning(f"⚠️ Free Tier Restriction: File contains {total_dataset_rows} rows. Caps apply at 50 rows.")
        st.info("💡 Enter the Admin Passkey in the sidebar panel to unlock unlimited enterprise processing rows.")
        working_df = loaded_df.head(50).copy()
        st.subheader("📊 Ingested Dataset Overview (Restricted Free Tier Preview)")
    else:
        working_df = loaded_df.copy()
        st.subheader(f"📊 Ingested Dataset Overview (Processing Mode: {total_dataset_rows} Rows Active)")
        
    st.dataframe(working_df.head(10))
    
    if fix_nulls:
        numeric_fields = working_df.select_dtypes(include=['number']).columns
        for field in numeric_fields:
            working_df[field] = working_df[field].fillna(working_df[field].median())
        st.sidebar.success("✔️ Empty fields filled using column statistical medians.")
        
    if purge_dupes:
        rows_before = len(working_df)
        working_df = working_df.drop_duplicates()
        rows_after = len(working_df)
        st.sidebar.success(f"✔️ Flushed {rows_before - rows_after} duplicate transactional rows.")
        
    if clean_strings:
        for field in working_df.columns:
            if working_df[field].dtype == 'object':
                working_df[field] = working_df[field].astype(str).str.replace('R', '', regex=False).str.replace('$', '', regex=False).str.strip()
                try:
                    working_df[field] = pd.to_numeric(working_df[field])
                except:
                    working_df[field] = working_df[field].str.title()
        st.sidebar.success("✔️ Currency labels stripped and string casing standardized.")
        
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
        st.download_button(
            label="📥 Download Clean CSV File",
            data=csv_stream,
            file_name=f"cleaned_{my_raw_file.name}",
            mime="text/csv"
        )
    else:
        memory_buffer = io.BytesIO()
        with pd.ExcelWriter(memory_buffer, engine='openpyxl') as excel_writer:
            working_df.to_excel(excel_writer, index=False, sheet_name='Cleaned Data Output')
        
        st.download_button(
            label="📥 Download Clean Excel File",
            data=memory_buffer.getvalue(),
            file_name=f"cleaned_{my_raw_file.name}",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# --- STEP 3: WORLD-CLASS USER REVIEW & ADMIN INSIGHTS SYSTEM ---
st.markdown("---")
st.subheader("⭐ User Experience Feedback Hub")

# Create two visual columns: one for users to review, one for the Admin dashboard
col1, col2 = st.columns([1, 1])

with col1:
    st.markdown("### Share Your Experience")
    st.write("Help us make this engine the most powerful tool on the market. Leave a rating and recommend new cleaning features!")
    
    # Interactive Feedback Inputs
    user_rating = st.slider("Rate the Data Janitor Engine (1 = Poor, 5 = Elite)", 1, 5, 5)
    user_review = st.text_area("What features or adjustments would make this app better for your daily workflow?")
    
    if st.button("Submit Anonymous Feedback 🚀"):
        if user_review.strip() != "":
            # Save feedback to a local hidden text vault
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"[{timestamp}] Rating: {user_rating}/5 | Feedback: {user_review}\n"
            
            with open("user_feedback_vault.txt", "a") as vault_file:
                vault_file.write(log_entry)
                
            st.success("Thank you! Your recommendations have been safely transmitted directly to our engineering roadmap.")
        else:
            st.error("Please enter a text suggestion or feature recommendation before clicking submit.")

with col2:
    st.markdown("### 🔒 Private Administrator Dashboard")
    if has_full_access:
        st.write("Welcome back, Admin. Below are the raw, unedited feature requests and performance ratings submitted by your users:")
        
        if os.path.exists("user_feedback_vault.txt"):
            with open("user_feedback_vault.txt", "r") as vault_file:
                feedback_records = vault_file.readlines()
            
            # Show reviews in reverse order so the newest are always at the top
            for record in reversed(feedback_records):
                if "Rating: 5" in record or "Rating: 4" in record:
                    st.info(record)
                else:
                    st.warning(record)
        else:
            st.info("No feedback has been submitted by users yet. System logs are completely clear.")
    else:
        st.info("🔒 Admin panel encrypted. Log in with your Master Passkey in the left panel to review user scores and workflow recommendations.")
