import streamlit as st
import sqlite3
from dotenv import load_dotenv
import os
from openai import OpenAI

# Load custom CSS
with open("style.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Load environment variables and initialize OpenAI client
load_dotenv()
openai_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=openai_key)

# --- NEW (03_01): SQL safety check ---
def is_safe_sql(query):
    unsafe_keywords = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE"]
    upper_query = query.upper()
    return not any(keyword in upper_query for keyword in unsafe_keywords)

# Function to convert question → SQL
def generate_sql_from_question(question):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an assistant that converts natural language questions into SQL queries. "
                    "Only use the tables and columns that exist in this SQLite schema "
                    "TABLE Appointments(visit_id, patient_id, department_name, patient_name, appointment_date, arrival_time, appointment_time, admission_time);"
                    "TABLE Hospital_Records(patient_id, patient_name, bmi, family_history_of_hypertension, department_name, Days_in_the_hospital);"
                    "TABLA Lab_Results(result_id, visit_id, test_name, test_date, result_value);"
                    "TABLA Outpatient_Visits(visit_id, patient_id, visit_date, doctor_name, reason_for_visit, diagnosis, medication_prescribed, smoker_status);"
                    "TABLA Patients(patient_id, patient_name, date_of_birth	gender, address)."
                    "If the user asks for something impossible in this schema, politely explain the issue and suggest the closest valid SQL "
                    "Return SQL only when possible."
                    
                )
            },
            {"role": "user", "content": question}
        ]
    )

    sql_query = response.choices[0].message.content
    sql_query = sql_query.strip()

    # Remove markdown ``` fences and optional "sql" labels
    if "```" in sql_query:
        parts = sql_query.split("```")
        if len(parts) >= 2:
            inner = parts[1].lstrip()
            if inner.lower().startswith("sql"):
                inner = inner[3:].lstrip()
            sql_query = inner.strip()

    return sql_query

# Run SQL safely
def run_sql_query(query):
    connection = sqlite3.connect("hospital_macondo.db")
    cursor = connection.cursor()

    try:
        cursor.execute(query)
        results = cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        connection.close()
        return results, columns

    except Exception as e:
        connection.close()
        return None, f"SQL error: {str(e)}"   # ← updated per 03_01


# --- Streamlit UI ---
st.set_page_config(page_title="AI SQL Assistant")

st.title("Hospital de Macondo - AI SQL Assistant")
st.write("The hospital database has 5 tables: Patients, Appointments, Hospital_Records, Lab_Results, Outpatient_Visits")
st.write("Ask a question in plain English, and I’ll help you turn it into SQL + Results")
st.write("""HOW TO USE THIS ASSISTANT: 
1. Type a plain-English question about the data; 
2. The AI will convert it into SQL;
3. The SQL will run against the sample database;
4. Results appear below the SQL;....Then, try to generate:
- "Show first 10 patients."
- "Find the patient ID of patients who had an appointment in the pediatrics department"
- "Find out how many days on average the patients spent in the Cardiology department of the hospital"
""")

with st.form("user_question_form"):
    user_question = st.text_input("What would you like to know about your data?")
    submitted = st.form_submit_button("Generate SQL")

if submitted:
    # 1. Generate SQL
    sql = generate_sql_from_question(user_question)
    st.subheader("Generated SQL")
    st.code(sql, language="sql")

    # --- NEW (03_01): Safety filter ---
    if not is_safe_sql(sql):
        st.error("The generated SQL looks unsafe to run. Please try rephrasing your question.")
        st.stop()

    # 2. Run SQL against the database
    results, columns_or_error = run_sql_query(sql)

    st.subheader("Results")

    # 3. Display results or errors
    if results is None:
        st.error(f"Error running SQL: {columns_or_error}")
    else:
        st.dataframe(
            {columns_or_error[i]: [row[i] for row in results] for i in range(len(columns_or_error))}
        )
