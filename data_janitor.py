import streamlit as st
import pandas as pd
import sqlite3
import io

st.set_page_config(page_title="Data Janitor Engine", layout="wide")

st.title("🧼 The Data Janitor & Financial Analytics Engine")
st.write("An automated cloud pipeline built to ingest raw datasets, execute algorithmic scrubbing, and index relational tables.")

# Sidebar Controls for the Pipeline Steps
st.sidebar.header("🛠️ Pipeline Control Panel")
fix_nulls = st.sidebar.checkbox("Algorithmic Null Imputation (Statistical Median)")
drop_dupes = st.sidebar.checkbox("Purge Duplicate Transactions")
standardize_text = st.sidebar.checkbox("Standardize Text Formatting (Proper Case)")
load_to_sql = st.sidebar.checkbox("Index Clean Tables into SQLite DB")

# File Ingestion
uploaded_file = st.file_uploader("Upload raw retail or financial dataset", type=["csv", "xlsx"])

if uploaded_file is not None:
    # Check the format of the incoming file
    is_csv = uploaded_file.name.endswith('.csv')
    
    # 1. EXTRACT
    df = pd.read_csv(uploaded_file) if is_csv else pd.read_excel(uploaded_file)
    
    st.subheader("📊 Ingested Raw Data View")
    st.dataframe(df.head(10))
    
    # 2. TRANSFORM ENGINE
    if fix_nulls:
        numeric_cols = df.select_dtypes(include=['number']).columns
        for col in numeric_cols:
            df[col] = df[col].fillna(df[col].median())
        st.sidebar.success("✔️ Null fields imputed with statistical medians.")
        
    if drop_dupes:
        before_count = len(df)
        df = df.drop_duplicates()
        after_count = len(df)
        st.sidebar.success(f"✔️ Purged {before_count - after_count} duplicate rows.")
        
    if standardize_text:
        string_cols = df.select_dtypes(include=['object']).columns
        for col in string_cols:
            df[col] = df[col].astype(str).str.strip().str.title()
        st.sidebar.success("✔️ Character cases and white spaces standardized.")
        
    # Preview Transformed Data
    st.subheader("✨ Transformed Engine Preview")
    st.dataframe(df.head(10))
    
    # 3. LOAD ENGINE (Backend Database Logging)
    if load_to_sql:
        conn = sqlite3.connect("retail_analytics.db")
        df.to_sql("clean_transactions", conn, if_exists="replace", index=False)
        conn.close()
        st.sidebar.info("🚀 Relational tables indexed in SQLite backend.")

    # 4. EXPORT ENGINE (User Convenience Feature)
    st.markdown("---")
    st.subheader("💾 Download Cleaned Dataset")
    
    if is_csv:
        # Prepare a pristine CSV download stream
        clean_csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Cleaned CSV File",
            data=clean_csv,
            file_name=f"cleaned_{uploaded_file.name}",
            mime="text/csv"
        )
    else:
        # Prepare a pristine Excel download stream using an in-memory buffer
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Clean Data')
        
        st.download_button(
            label="📥 Download Cleaned Excel File",
            data=buffer.getvalue(),
            file_name=f"cleaned_{uploaded_file.name}",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
