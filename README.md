# Natural Language to SQL Agent

Ask questions in plain language and generate corresponding MySQL queries. The
application uses a local Ollama model, validates generated SQL, and lets you
review and approve a query before it runs against your database.

## Features

- Local LLM SQL generation with Ollama and `qwen3.5:4b`.
- LangGraph flow that generates SQL, validates it, and retries invalid output.
- SELECT-only checks and read-only MySQL transactions.
- User confirmation before executing a generated query.
- Results displayed in a Streamlit interface, capped at 100 rows.

## Architecture

```text
main.py (Streamlit UI)
    |  question / confirmation
    v
agent_graph.py (LangGraph: generate -> validate -> retry)
    |                         |
    v                         +--> app.py (Ollama SQL generation)
app.py (schema, validation, MySQL execution)
```

`app.py` owns database configuration, schema lookup, Ollama requests, SQL
validation, and read-only query execution. `agent_graph.py` coordinates
generation and validation retries. `main.py` provides the Streamlit UI and
requires confirmation before execution.

## Setup

### Requirements

- Python 3.10 or newer
- MySQL Server and a database
- [Ollama](https://ollama.com/) installed and running locally

### Install Python dependencies

Clone the repository and create a virtual environment:

```powershell
git clone https://github.com/Gm1654/natural-language-to-sql-agent.git
cd natural-language-to-sql-agent
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Install and prepare Ollama

Install Ollama, then pull the model used by default:

```powershell
ollama pull qwen3.5:4b
```

Keep Ollama running while using the application. To select a different Ollama
model, set `OLLAMA_MODEL` in `.env`.

### Configure MySQL

Create a dedicated account with read-only permissions. For example, replace
`your_database` and the credentials with your own values:

```sql
CREATE USER 'nl2sql_reader'@'localhost' IDENTIFIED BY 'use-a-strong-password';
GRANT SELECT ON `your_database`.* TO 'nl2sql_reader'@'localhost';
```

Create a `.env` file in the project root:

```env
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=your_database
MYSQL_USER=nl2sql_reader
MYSQL_PASSWORD=use-a-strong-password
OLLAMA_MODEL=qwen3.5:4b
```

The application defaults `OLLAMA_MODEL` to `qwen3.5:4b` if it is omitted.

## Run

With the virtual environment active and MySQL and Ollama available:

```powershell
streamlit run main.py
```

Open the local URL printed by Streamlit.

## Security notes

- Use a dedicated MySQL account that has **SELECT-only** access to the target
  database. The account's database permissions are the actual security
  boundary; SQL keyword checks and read-only transactions are additional
  safeguards, not substitutes for least privilege.
- Never commit `.env` or share its database credentials. If credentials have
  ever been committed or exposed, rotate the MySQL password immediately.
- Review the generated SQL and confirm it in the UI before execution.

## Limitations

- SQL validation uses simple keyword checks rather than a complete MySQL
  parser. It can reject otherwise valid SQL when names or functions contain
  blocked keywords (for example `REPLACE()` or identifiers containing
  `CALL`), and it is not a security boundary.
- The default Ollama endpoint is local. Deploying this application for remote
  users requires a hosted LLM endpoint and a hosted, appropriately secured
  MySQL database.
- SQL quality depends on the model, available schema, and wording of the
  question.

## Troubleshooting

- **`ModuleNotFoundError`:** Activate the project virtual environment and run
  `pip install -r requirements.txt` again.
- **Ollama connection refused:** Start Ollama, verify it is listening at
  `http://localhost:11434`, and run `ollama pull qwen3.5:4b`.
- **MySQL `Access denied`:** Check `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`,
  and `MYSQL_PASSWORD` in `.env`. Confirm that the MySQL account can connect
  from that host and has `SELECT` privileges on `MYSQL_DATABASE`.
