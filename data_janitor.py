import streamlit as st
import pandas as pd
import sqlite3
import io

# Custom page layout for the web engine
st.set_page_config(page_title="Data Cleaner Portfolio", layout="wide")

# --- STEP 1: GATEKEEPER & ACCESS PRIVILEGES ---
st.sidebar.header("🔑 App Access Control")
user_tier = st.sidebar.radio("Your Current Tier", ["Free / Guest User", "Admin / Premium Login"])

has_full_access = False

if user_tier == "Admin / Premium Login":
    entered_pass = st.sidebar.text_input("Enter Passkey", type="password")
    
    # Custom administrative passkey verification
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
    
    # Try-except safeguard to ensure unreadable formats don't crash the web portal
    try:
        loaded_df = pd.read_csv(my_raw_file) if file_format_csv else pd.read_excel(my_raw_file)
    except Exception as read_error:
        st.error(f"❌ File Reading Disruption: Structure is corrupted. Details: {read_error}")
        st.stop()
        
    # --- STEP 3: OUTSIDER LIMITATION RULES ---
    total_dataset_rows = len(loaded_df)
    
    if not has_full_access and total_dataset_rows > 50:
        st.warning(f"⚠️ Free Tier Restriction: File contains {total_dataset_rows} rows. Caps apply at 50 rows.")
        st.info("💡 Enter the Admin Passkey in the sidebar panel to unlock unlimited enterprise processing rows.")
        # Slice out a preview block for non-paying outsiders
        working_df = loaded_df.head(50).copy()
        st.subheader("📊 Ingested Dataset Overview (Restricted Free Tier Preview)")
    else:
        working_df = loaded_df.copy()
        st.subheader(f"📊 Ingested Dataset Overview (Processing Mode: {total_dataset_rows} Rows Active)")
        
    st.dataframe(working_df.head(10))
    
    # --- STEP 4: CUSTOM TRANSFORM CLEANING LOGIC ---
    if fix_nulls:
        # Pull numeric columns to prevent string transformation conflicts
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
        # Loop over object columns to strip financial notations and whitespaces
        for field in working_df.columns:
            if working_df[field].dtype == 'object':
                working_df[field] = working_df[field].astype(str).str.replace('R', '', regex=False).str.replace('$', '', regex=False).str.strip()
                # Attempt conversion back to numeric if column noise is removed
                try:
                    working_df[field] = pd.to_numeric(working_df[field])
                except:
                    # Enforce proper string formatting for categories and names
                    working_df[field] = working_df[field].str.title()
        st.sidebar.success("✔️ Currency labels stripped and string casing standardized.")
        
    # Display the final transformed overview on screen
    st.subheader("✨ Transformed Engine Preview")
    st.dataframe(working_df.head(10))
    
    # --- STEP 5: BACKEND SQL INTEGRATION ---
    if push_to_database:
        try:
            db_connection = sqlite3.connect("retail_analytics.db")
            working_df.to_sql("clean_transactions", db_connection, if_exists="replace", index=False)
            db_connection.close()
            st.sidebar.info("🚀 Relational table updated in SQLite.")
        except Exception as database_error:
            st.sidebar.error(f"Database Exception: {database_error}")

    # --- STEP 6: OUTPUT GENERATION MATCHING INPUT FORMAT ---
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
