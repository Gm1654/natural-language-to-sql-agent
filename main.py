
import streamlit as st
import pandas as pd
import mysql.connector

import app


st.set_page_config(
    page_title="SQL AI Agent",
    page_icon="🤖",
    layout="wide",
)

st.title("SQL AI Agent")
st.caption("Ask questions about your MySQL database in plain English.")

with st.sidebar:
    st.subheader("Configuration")
    st.write(f"Database: {app.DB_CONFIG['database']}")
    st.write(f"Model: {app.OLLAMA_MODEL}")
    st.write("Execution requires your confirmation.")

# Automatically load schema once per Streamlit session.
if "schema" not in st.session_state:
    st.session_state.schema = None

if "schema_error" not in st.session_state:
    st.session_state.schema_error = None

if "generated_sql" not in st.session_state:
    st.session_state.generated_sql = ""

if "result" not in st.session_state:
    st.session_state.result = None

if "query_error" not in st.session_state:
    st.session_state.query_error = None

if st.session_state.schema is None and not st.session_state.schema_error:
    try:
        app.check_configuration()
        st.session_state.schema = app.get_schema()

        if not st.session_state.schema.strip():
            st.session_state.schema_error = (
                "No tables found in the selected database."
            )
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
            with st.spinner("Generating SQL with Ollama..."):
                sql = app.generate_sql(
                    question.strip(),
                    st.session_state.schema,
                )

            st.session_state.generated_sql = sql
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
                safe_sql = app.validate_sql(
                    st.session_state.generated_sql
                )

                with st.spinner("Executing query..."):
                    connection = app.get_connection()

                    try:
                        connection.start_transaction(readonly=True)
                        cursor = connection.cursor()
                        cursor.execute(safe_sql)

                        if cursor.description is None:
                            raise ValueError(
                                "Query did not return a result set."
                            )

                        columns = [
                            column[0] for column in cursor.description
                        ]
                        rows = cursor.fetchmany(100)

                        st.session_state.result = pd.DataFrame(
                            rows,
                            columns=columns,
                        )
                        st.session_state.query_error = None

                        cursor.close()
                        connection.rollback()

                    finally:
                        connection.close()

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
    st.dataframe(
        st.session_state.result,
        use_container_width=True,
        hide_index=True,
    )
    st.caption(
        f"Rows displayed: {len(st.session_state.result)} "
        "(maximum 100)"
    )
