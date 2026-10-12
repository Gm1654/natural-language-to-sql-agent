import streamlit as st
import pandas as pd
import mysql.connector

import app
from agent_graph import run_agent

st.set_page_config(page_title="SQL AI Agent", page_icon="🤖", layout="wide")
st.title("SQL AI Agent")
st.caption("Ask questions about your MySQL database in plain English.")

with st.sidebar:
    st.subheader("Configuration")
    st.write(f"Database: {app.DB_CONFIG['database']}")
    st.write(f"Model: {app.OLLAMA_MODEL}")
    st.write("Execution requires your confirmation.")

for key, default in {
    "question": "",
    "schema": None,
    "schema_error": None,
    "generated_sql": "",
    "result": None,
    "query_error": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

if st.session_state.schema is None and not st.session_state.schema_error:
    try:
        app.check_configuration()
        st.session_state.schema = app.get_schema()
        if not st.session_state.schema.strip():
            st.session_state.schema_error = "No tables found in the selected database."
    except Exception as exc:
        st.session_state.schema_error = str(exc)

if st.session_state.schema_error:
    st.error(f"Database/schema loading failed: {st.session_state.schema_error}")
    st.stop()

question = st.text_area(
    "Your question",
    placeholder="e.g. Which users have a salary greater than 100000?",
    height=100,
)

if st.button("Generate SQL", type="primary"):
    if not question.strip():
        st.warning("Please enter a question.")
    else:
        try:
            with st.spinner("Generating SQL"):
                out = run_agent(question.strip(), st.session_state.schema)

            if out.get("error"):
                st.error(f"SQL generate nahi ho saka: {out['error']}")
            else:
                st.session_state.generated_sql = out["sql"]
                st.session_state.question = question.strip()
                st.session_state.result = None
                st.session_state.query_error = None
        except Exception as exc:
            st.error(f"SQL generation failed: {exc}")

if st.session_state.generated_sql:
    st.subheader("Generated SQL")
    st.code(st.session_state.generated_sql, language="sql")
    st.warning("Review the query before execution.")

    yes_col, no_col = st.columns(2)
    with yes_col:
        if st.button("Yes — Execute Query", type="primary"):
            try:
                with st.spinner("Executing query..."):
                    columns, rows = app.execute_sql(st.session_state.generated_sql)
                st.session_state.result = pd.DataFrame(rows, columns=columns)
                st.session_state.query_error = None
            except (ValueError, mysql.connector.Error) as exc:
                st.session_state.query_error = str(exc)

    with no_col:
        if st.button("No — Cancel"):
            st.session_state.generated_sql = ""
            st.session_state.result = None
            st.session_state.query_error = None
            st.rerun()

if st.session_state.query_error:
    st.error(st.session_state.query_error)

if st.session_state.result is not None:
    st.subheader("Query Results")
    st.dataframe(st.session_state.result, width="stretch", hide_index=True)
    st.caption(f"Rows displayed: {len(st.session_state.result)} (maximum 100)")