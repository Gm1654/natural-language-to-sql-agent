import os
import re
import time
from pathlib import Path

import mysql.connector
import requests
from dotenv import load_dotenv

# -------------------------------
# 1. Load .env from project folder
# -------------------------------

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE, override=True)

# -------------------------------
# 2. MySQL configuration
# -------------------------------

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "database": os.getenv("MYSQL_DATABASE", "startersql"),
    "user": os.getenv("MYSQL_USER", "nl2sql_reader"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "connection_timeout": 5,
}

# -------------------------------
# 3. Ollama configuration
# -------------------------------

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen3.5:4b"


def check_configuration():
    print("\n--- Configuration Check ---")
    print("App folder:", BASE_DIR)
    print(".env exists:", ENV_FILE.is_file())
    print("MySQL host:", DB_CONFIG["host"])
    print("MySQL database:", DB_CONFIG["database"])
    print("MySQL user:", repr(DB_CONFIG["user"]))
    print("Password loaded:", bool(DB_CONFIG["password"]))
    print("Password length:", len(DB_CONFIG["password"]))

    if not DB_CONFIG["password"]:
        raise RuntimeError(
            "MYSQL_PASSWORD is empty. Check the .env file."
        )


# -------------------------------
# 4. Test MySQL connection
# -------------------------------

def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


def test_mysql():
    print("\n--- Testing MySQL Connection ---")

    try:
        connection = get_connection()

        cursor = connection.cursor()
        cursor.execute("SELECT DATABASE(), CURRENT_USER()")
        result = cursor.fetchone()

        print("MySQL connection successful!")
        print("Selected database:", result[0])
        print("Authenticated MySQL account:", result[1])

        cursor.close()
        connection.close()
        return True

    except mysql.connector.Error as error:
        print("MySQL connection failed.")
        print("Error:", error)
        return False


# -------------------------------
# 5. Read database schema
# -------------------------------

def get_schema():
    started = time.perf_counter()
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

        rows = cursor.fetchall()
        schema = {}

        for table_name, column_name, data_type in rows:
            schema.setdefault(table_name, []).append(
                f"{column_name} ({data_type})"
            )

        schema_text = "\n".join(
            f"{table}: {', '.join(columns)}"
            for table, columns in schema.items()
        )
        elapsed = time.perf_counter() - started
        print(
            f"[timing] schema_load={elapsed:.3f}s "
            f"tables={len(schema)} columns={sum(map(len, schema.values()))} "
            f"schema_chars={len(schema_text):,}"
        )
        return schema_text

    finally:
        connection.close()


# -------------------------------
# 6. Generate SQL using Ollama
# -------------------------------

OLLAMA_CALL_COUNT = 0


def get_relevant_schema(question, schema):
    question_words = re.findall(r"[a-z0-9]+", question.casefold())
    relevant_tables = []

    for line in schema.splitlines():
        table_name, separator, _ = line.partition(": ")
        if not separator:
            continue

        table_words = re.findall(r"[a-z0-9]+", table_name.casefold())
        width = len(table_words)
        if width and any(
            question_words[index:index + width] == table_words
            for index in range(len(question_words) - width + 1)
        ):
            relevant_tables.append(line)

    return "\n".join(relevant_tables) if relevant_tables else schema


def generate_sql(question, schema):
    global OLLAMA_CALL_COUNT
    OLLAMA_CALL_COUNT += 1
    call_started = time.perf_counter()
    relevant_schema = get_relevant_schema(question, schema)
    prompt = f"Schema:\n{relevant_schema}\n\nQuestion:\n{question}"

    system_prompt = (
        "Generate exactly one MySQL SELECT statement; its first token "
        "must be SELECT. Never use INSERT, UPDATE, DELETE, DROP, ALTER, "
        "CREATE, TRUNCATE, REPLACE, GRANT, REVOKE, CALL, LOAD_FILE, "
        "INTO OUTFILE, or INTO DUMPFILE; never generate multiple "
        "statements. Use only the supplied schema. If it is insufficient, "
        "say so instead of guessing. Return SQL only, without Markdown, "
        "explanation, or reasoning."
    )
    prompt_chars = len(prompt) + len(system_prompt)
    print(
        f"[timing] ollama_request_start call={OLLAMA_CALL_COUNT} model={OLLAMA_MODEL!r} "
        f"schema_chars={len(relevant_schema):,} prompt_chars={prompt_chars:,}"
    )

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                # Qwen3 defaults to reasoning, which can spend many tokens before SQL.
                "think": False,
                "stream": False,
                # NL-to-SQL needs only a short response and a small context window.
                "options": {"temperature": 0, "num_ctx": 4096}
            },
            timeout=180,
        )
        request_elapsed = time.perf_counter() - call_started
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException:
        print(f"[timing] ollama_request_failed elapsed={time.perf_counter() - call_started:.3f}s")
        raise

    answer = payload["message"]["content"].strip()
    total_duration = payload.get("total_duration")
    load_duration = payload.get("load_duration")
    prompt_eval_count = payload.get("prompt_eval_count")
    prompt_eval_duration = payload.get("prompt_eval_duration")
    eval_count = payload.get("eval_count")
    eval_duration = payload.get("eval_duration")

    def seconds(ns):
        return f"{ns / 1_000_000_000:.3f}s" if isinstance(ns, (int, float)) else "n/a"

    tokens_per_second = (
        f"{eval_count / (eval_duration / 1_000_000_000):.2f}"
        if isinstance(eval_count, (int, float))
        and isinstance(eval_duration, (int, float))
        and eval_duration > 0
        else "n/a"
    )
    print(
        f"[timing] ollama_http={request_elapsed:.3f}s "
        f"server_total={seconds(total_duration)} model_load={seconds(load_duration)} "
        f"prompt_eval={seconds(prompt_eval_duration)} prompt_tokens={prompt_eval_count or 'n/a'} "
        f"generation={seconds(eval_duration)} generated_tokens={eval_count or 'n/a'} "
        f"generation_rate={tokens_per_second} tokens/s"
    )

    # Remove Markdown code fences, if present.
    if answer.startswith("```"):
        lines = answer.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        answer = "\n".join(lines).strip()

    return answer


# -------------------------------
# 7. Basic SQL safety checks
# -------------------------------

def validate_sql(sql):
    cleaned = sql.strip().rstrip(";").strip()
    upper_sql = cleaned.upper()

    if not upper_sql.startswith("SELECT "):
        raise ValueError("Blocked: only SELECT queries are allowed.")

    if ";" in cleaned:
        raise ValueError("Blocked: multiple SQL statements are not allowed.")

    forbidden = [
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER",
        "CREATE", "TRUNCATE", "REPLACE", "GRANT",
        "REVOKE", "CALL", "LOAD_FILE", "INTO OUTFILE",
        "INTO DUMPFILE"
    ]

    for word in forbidden:
        if re.search(r"\b" + re.escape(word) + r"\b", upper_sql):
            raise ValueError(f"Blocked: forbidden keyword {word}.")

    return cleaned


# -------------------------------
# 8. Execute read-only query
# -------------------------------

def execute_sql(sql):
    query_started = time.perf_counter()
    connection = get_connection()

    try:
        # This is an additional safeguard, not a substitute
        # for a genuinely read-only MySQL account.
        connection.start_transaction(readonly=True)

        cursor = connection.cursor()
        cursor.execute(sql)
        query_elapsed = time.perf_counter() - query_started

        if cursor.description is None:
            raise ValueError("The query did not return a result set.")

        columns = [item[0] for item in cursor.description]
        rows = cursor.fetchmany(100)
        print(f"[timing] mysql_execute_and_fetch={time.perf_counter() - query_started:.3f}s execute={query_elapsed:.3f}s")

        print("\n--- Query Results (maximum 100 rows) ---")
        print(" | ".join(columns))
        print("-" * 80)

        for row in rows:
            print(" | ".join(str(value) for value in row))

        print(f"\nRows displayed: {len(rows)}")

        cursor.close()
        connection.rollback()

    finally:
        connection.close()


# -------------------------------
# 9. Main application
# -------------------------------

def main():
    check_configuration()

    if not test_mysql():
        return

    try:
        schema = get_schema()

        if not schema.strip():
            print("No tables found in the selected database.")
            return

        print("\n--- Natural Language to SQL Agent ---")
        print("Database:", DB_CONFIG["database"])
        print("Type 'exit' to quit.")

        while True:
            question = input("\nAsk a question: ").strip()

            if question.lower() in {"exit", "quit"}:
                print("Goodbye!")
                break

            if not question:
                continue

            try:
                sql = generate_sql(question, schema)
                sql = validate_sql(sql)

                print("\nGenerated SQL:")
                print(sql)

                confirm = input(
                    "\nExecute this query? (yes/no): "
                ).strip().lower()

                if confirm == "yes":
                    execute_sql(sql)
                else:
                    print("Query cancelled.")

            except requests.RequestException as error:
                print("Ollama request failed:", error)

            except (ValueError, mysql.connector.Error) as error:
                print("Error:", error)

    except mysql.connector.Error as error:
        print("Database error:", error)
print("Password loaded:", bool(DB_CONFIG["password"]))
print("Password length:", len(DB_CONFIG["password"]))        


if __name__ == "__main__":
    main()
