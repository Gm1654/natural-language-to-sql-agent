import os
import re
from pathlib import Path

import mysql.connector
import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
load_dotenv(ENV_FILE, override=True)

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "database": os.getenv("MYSQL_DATABASE", "startersql"),
    "user": os.getenv("MYSQL_USER", "nl2sql_reader"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "connection_timeout": 5,
}

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:4b")

SYSTEM_PROMPT = (
    "Generate exactly one MySQL SELECT statement; its first token "
    "must be SELECT. Never use INSERT, UPDATE, DELETE, DROP, ALTER, "
    "CREATE, TRUNCATE, REPLACE, GRANT, REVOKE, CALL, LOAD_FILE, "
    "INTO OUTFILE, or INTO DUMPFILE; never generate multiple "
    "statements. Use only the supplied schema. If it is insufficient, "
    "say so instead of guessing. Return SQL only, without Markdown, "
    "explanation, or reasoning."
)


def check_configuration():
    if not DB_CONFIG["password"]:
        raise RuntimeError("MYSQL_PASSWORD is empty. Check the .env file.")


def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


def get_schema():
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s
            ORDER BY TABLE_NAME, ORDINAL_POSITION
            """,
            (DB_CONFIG["database"],),
        )
        schema = {}
        for table_name, column_name, data_type in cursor.fetchall():
            schema.setdefault(table_name, []).append(f"{column_name} ({data_type})")
        return "\n".join(
            f"{table}: {', '.join(columns)}" for table, columns in schema.items()
        )
    finally:
        connection.close()


def get_relevant_schema(question, schema):
    question_words = re.findall(r"[a-z0-9]+", question.casefold())
    relevant = []
    for line in schema.splitlines():
        table_name, sep, _ = line.partition(": ")
        if not sep:
            continue
        table_words = re.findall(r"[a-z0-9]+", table_name.casefold())
        width = len(table_words)
        if width and any(
            question_words[i:i + width] == table_words
            for i in range(len(question_words) - width + 1)
        ):
            relevant.append(line)
    return "\n".join(relevant) if relevant else schema


def generate_sql(question, schema, schema_question=None):
    relevant_schema = get_relevant_schema(schema_question or question, schema)
    prompt = f"Schema:\n{relevant_schema}\n\nQuestion:\n{question}"

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "think": False,
            "stream": False,
            "options": {"temperature": 0, "num_ctx": 4096},
        },
        timeout=180,
    )
    response.raise_for_status()
    answer = response.json()["message"]["content"].strip()

    if answer.startswith("```"):
        lines = answer.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        answer = "\n".join(lines).strip()
    return answer


def validate_sql(sql):
    # Keyword checks are only a guardrail; a read-only MySQL user is the real security boundary.
    cleaned = sql.strip().rstrip(";").strip()
    upper_sql = cleaned.upper()

    if not upper_sql.startswith("SELECT "):
        raise ValueError("Blocked: only SELECT queries are allowed.")
    if ";" in cleaned:
        raise ValueError("Blocked: multiple SQL statements are not allowed.")

    forbidden = [
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE",
        "REPLACE", "GRANT", "REVOKE", "CALL", "LOAD_FILE", "INTO OUTFILE",
        "INTO DUMPFILE",
    ]
    for word in forbidden:
        if re.search(r"\b" + re.escape(word) + r"\b", upper_sql):
            raise ValueError(f"Blocked: forbidden keyword {word}.")
    return cleaned


def execute_sql(sql):
    """Returns (columns, rows). Read-only transaction, max 100 rows."""
    connection = get_connection()
    try:
        connection.start_transaction(readonly=True)
        cursor = connection.cursor()
        cursor.execute(sql)
        if cursor.description is None:
            raise ValueError("Query did not return a result set.")
        columns = [c[0] for c in cursor.description]
        rows = cursor.fetchmany(100)
        cursor.close()
        connection.rollback()
        return columns, rows
    finally:
        connection.close()