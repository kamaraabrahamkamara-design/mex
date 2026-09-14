import io
import hashlib
import pandas as pd
import streamlit as st
from supabase import create_client, Client

# --- SUPABASE CONNECTION ---
# Securely retrieve Supabase credentials from Streamlit secrets
SUPABASE_URL = st.secrets["supabase_url"]
SUPABASE_KEY = st.secrets["supabase_key"]

@st.cache_resource
def get_supabase_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = get_supabase_client()
REQUIRED_COLUMNS = ["id", "class", "subject", "period", "semester", "grade", "password_hash"]

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# --- STREAMLIT UI SETUP ---
st.set_page_config(page_title="Academic Records Portal", layout="wide")

st.title("🏫 Academic Records Portal")
st.write("Welcome to the Student and Admin Grades Management System.")

tab_student, tab_admin = st.tabs(["🎓 Student Portal", "🔐 Admin Dashboard"])

# --- STUDENT PORTAL ---
with tab_student:
    st.header("Student Grade Inquiry")
    
    student_id = st.text_input("Enter Student ID:", key="stu_id_input").strip()
    student_pass = st.text_input("Enter Password:", type="password", key="stu_pass_input").strip()
    
    if st.button("Access Dashboard"):
        if student_id and student_pass:
            hashed_input = hash_password(student_pass)
            
            # Query Supabase for matching ID and password hash
            response = supabase.table("grades").select("*").eq("id", student_id).eq("password_hash", hashed_input).execute()
            
            if response.data:
                st.success(f"✅ Welcome Back Student: {student_id}")
                st.session_state[f"authenticated_{student_id}"] = True
            else:
                st.error("❌ Invalid Student ID or Password.")
        else:
            st.warning("⚠️ Both Student ID and Password are required.")

    if f"authenticated_{student_id}" in st.session_state and st.session_state[f"authenticated_{student_id}"]:
        # Fetch student rows directly from Supabase
        student_data = supabase.table("grades").select("*").eq("id", student_id).execute()
        student_rows = pd.DataFrame(student_data.data)
        
        if not student_rows.empty:
            student_rows['grade'] = pd.to_numeric(student_rows['grade'], errors='coerce')
            
            col1, col2 = st.columns(2)
            with col1:
                semesters = ["All Semesters"] + sorted(student_rows['semester'].dropna().astype(str).unique().tolist())
                selected_semester = st.selectbox("Filter by Semester", semesters)
            with col2:
                periods = ["All Periods"] + sorted(student_rows['period'].dropna().astype(str).unique().tolist())
                selected_period = st.selectbox("Filter by Period", periods)
            
            filtered_df = student_rows.copy()
            if selected_semester != "All Semesters":
                filtered_df = filtered_df[filtered_df['semester'].astype(str) == selected_semester]
            if selected_period != "All Periods":
                filtered_df = filtered_df[filtered_df['period'].astype(str) == selected_period]
                
            st.subheader("📊 Academic Performance Summary")
            metric_col1, metric_col2, metric_col3 = st.columns(3)
            
            current_avg = filtered_df['grade'].mean()
            with metric_col1:
                if pd.isna(current_avg):
                    st.metric(label="Current Filtered Average", value="N/A")
                else:
                    st.metric(label="Current Filtered Average", value=f"{current_avg:.2f}%")
                    
            with metric_col2:
                st.markdown("**Average by Semester**")
                sem_avg = student_rows.groupby('semester')['grade'].mean().reset_index()
                for _, row in sem_avg.iterrows():
                    st.write(f"• **{row['semester']}**: {row['grade']:.2f}%")
                    
            with metric_col3:
                st.markdown("**Average by Period**")
                per_avg = student_rows.groupby('period')['grade'].mean().reset_index()
                for _, row in per_avg.iterrows():
                    st.write(f"• **{row['period']}**: {row['grade']:.2f}%")
            
            st.divider()
            st.subheader("Your Academic Record")
            display_df = filtered_df.drop(columns=['password_hash', 'created_at'], errors='ignore')
            st.dataframe(display_df, use_container_width=True)
            
            # --- DOWNLOAD CONTROLS ---
            dl_col1, dl_col2 = st.columns(2)
            with dl_col1:
                csv_buffer = io.StringIO()
                display_df.to_csv(csv_buffer, index=False)
                st.download_button(
                    label="📥 Download Filtered Transcript (CSV)",
                    data=csv_buffer.getvalue(),
                    file_name=f"Transcript_{student_id}.csv",
                    mime="text/csv"
                )
                
            with dl_col2:
                txt_report = [
                    "=========================================",
                    "         OFFICIAL REPORT CARD            ",
                    "=========================================",
                    f"Student ID : {student_id}"
                ]
                if not display_df.empty:
                    txt_report.append(f"Class      : {display_df['class'].iloc[0]}")
                txt_report.append(f"Filters    : {selected_semester} | {selected_period}")
                txt_report.append("-----------------------------------------")
                
                avg_str = f"{current_avg:.2f}%" if not pd.isna(current_avg) else "N/A"
                txt_report.append(f"Overall Filtered Average: {avg_str}\n\nSummary by Semester:")
                for _, row in sem_avg.iterrows():
                    txt_report.append(f" - {row['semester']}: {row['grade']:.2f}%")
                txt_report.append("\nSummary by Period:")
                for _, row in per_avg.iterrows():
                    txt_report.append(f" - {row['period']}: {row['grade']:.2f}%")
                    
                txt_report.append("-----------------------------------------")
                txt_report.append(f"{'Subject':<18} | {'Semester':<10} | {'Period':<10} | {'Grade':<5}")
                txt_report.append("-" * 53)
                
                for _, row in display_df.iterrows():
                    txt_report.append(f"{str(row['subject']):<18} | {str(row['semester']):<10} | {str(row['period']):<10} | {str(row['grade']):<5}")
                txt_report.append("=========================================")
                
                st.download_button(
                    label="📄 Download Report Card (TXT)",
                    data="\n".join(txt_report),
                    file_name=f"ReportCard_{student_id}.txt",
                    mime="text/plain",
                    key="student_txt_download"
                )
        else:
            st.info("💡 You are authenticated, but no grade records were found in the database.")

# --- ADMIN DASHBOARD ---
with tab_admin:
    st.header("Administrative Access Gate")
    if "admin_authenticated" not in st.session_state:
        st.session_state["admin_authenticated"] = False
        
    if not st.session_state["admin_authenticated"]:
        admin_user = st.text_input("Username:")
        admin_pass = st.text_input("Password:", type="password")
        if st.button("Authenticate Admin"):
            if admin_user == "admin" and admin_pass == "password123":
                st.session_state["admin_authenticated"] = True
                st.rerun()
            else:
                st.error("❌ Invalid Admin Username or Password.")
    else:
        st.success("✅ Admin Authentication Successful. Live database loaded below.")
        if st.button("🚪 Logout Admin Panel"):
            st.session_state["admin_authenticated"] = False
            st.rerun()
            
        st.divider()
        st.subheader("Bulk Record Upload")
        uploaded_file = st.file_uploader("Upload grades update file (.csv)", type=["csv"])
        
        if uploaded_file is not None:
            try:
                uploaded_df = pd.read_csv(uploaded_file)
                uploaded_df.columns = [c.strip().lower() for c in uploaded_df.columns]
                
                missing = [col for col in REQUIRED_COLUMNS if col not in uploaded_df.columns]
                if missing:
                    st.error(f"❌ Upload Rejected. Missing target secure columns: {', '.join(missing)}")
                else:
                    final_df = uploaded_df[REQUIRED_COLUMNS]
                    records = final_df.to_dict(orient="records")
                    
                    # Upsert rows into Supabase
                    supabase.table("grades").insert(records).execute()
                    st.toast(f"🎉 Success! Records uploaded to Supabase.", icon="🔥")
            except Exception as e:
                st.error(f"❌ Engine parsing error: {str(e)}")
                
        st.subheader("📝 Live Master Records Editor")
        st.caption("Double-click any cell to edit data, insert rows, or delete records. Remember to save changes below.")
        
        # Load complete records from database
        master_data = supabase.table("grades").select("*").execute()
        master_df = pd.DataFrame(master_data.data)
        
        if not master_df.empty:
            # Drop metadata column if present
            if 'created_at' in master_df.columns:
                master_df = master_df.drop(columns=['created_at'])
                
            edited_df = st.data_editor(
                master_df, 
                use_container_width=True, 
                num_rows="dynamic",
                key="admin_records_editor"
            )
            
            admin_col1, admin_col2 = st.columns(2)
            
            with admin_col1:
                if st.button("💾 Save Table Changes"):
                    try:
                        # Auto-fill password hashes for new entries
                        for index, row in edited_df.iterrows():
                            if pd.isna(row['password_hash']) or str(row['password_hash']).strip() == "":
                                edited_df.at[index, 'password_hash'] = hash_password(str(row['id']))
                        
                        updated_records = edited_df.to_dict(orient="records")
                        
                        # Sync logic: clear database table and rewrite fresh set
                        supabase.table("grades").delete().neq("id", "").execute() 
                        if updated_records:
                            supabase.table("grades").insert(updated_records).execute()
                            
                        st.success("🎉 Database saved successfully to Supabase!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error saving: {str(e)}")
            
            with admin_col2:
                admin_csv_buffer = io.StringIO()
                master_df.to_csv(admin_csv_buffer, index=False)
                st.download_button(
                    label="📥 Download Master Database (CSV)",
                    data=admin_csv_buffer.getvalue(),
                    file_name="master_grades_database.csv",
                    mime="text/csv",
                    key="admin_download_btn"
                )
        else:
            st.info("💡 The Supabase database table is currently empty.")
