# Natural Language to SQL Agent

An AI-powered agent that converts plain English questions into SQL queries and retrieves results from a MySQL database through a simple Streamlit interface.

Ask questions about your data in natural language, review the generated SQL, and decide whether to execute it.

## Features

- **Natural Language to SQL:** Convert everyday English questions into SQL queries.
- **Local LLM Integration:** Generate SQL using Qwen through Ollama.
- **MySQL Integration:** Connect to a MySQL database and retrieve real query results.
- **Human-in-the-Loop:** Review generated SQL before approving or cancelling execution.
- **SQL Validation:** Apply checks before executing generated queries.
- **Read-Only Execution:** Use read-only transactions for query execution.
- **Interactive UI:** Ask questions and view results through Streamlit.
- **Query Results:** Display database results in a readable table.

## How It Works

1. Enter a question in plain English.
2. The agent retrieves the database schema.
3. The local language model generates an SQL query.
4. The generated query is displayed for review.
5. Approve or cancel the query.
6. If approved, the query runs against MySQL and the results are displayed.

## Tech Stack

- **Python** — Application logic
- **Ollama** — Local language model runtime
- **Qwen 3.5 4B** — SQL generation
- **MySQL** — Database
- **Streamlit** — Web interface
- **mysql-connector-python** — Database connectivity

## Example

**Question:**

Which users earn more than the average salary?

**Generated SQL:**

```sql
SELECT *
FROM users
WHERE salary > (
    SELECT AVG(salary)
    FROM users
);
```

The agent generates the query and lets the user review it before execution.

## Requirements

- Python 3.10 or a compatible version
- MySQL Server
- Ollama
- A compatible Qwen model pulled in Ollama

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/natural-language-to-sql-agent.git
cd natural-language-to-sql-agent
```

### 2. Install dependencies

```bash
python -m venv venv
```

Activate the virtual environment.

**Windows:**

```bash
venv\Scripts\activate
```

Install the required packages:

```bash
pip install streamlit mysql-connector-python python-dotenv requests pandas
```

### 3. Set up Ollama

Install Ollama from [ollama.com](https://ollama.com/) and download the model used by the application:

```bash
ollama pull qwen3.5:4b
```

Make sure Ollama is running before starting the application.

### 4. Configure MySQL

Create a `.env` file in the project root and add your database settings using the variable names expected by `app.py`.

Example configuration:

```env
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=your_database
DB_USER=your_readonly_user
DB_PASSWORD=your_password
```

**Important:** These environment variable names are examples. Match them to the names your application actually reads.

Use a dedicated MySQL account with only the permissions the application needs. Never commit your `.env` file or database credentials.

### 5. Run the application

```bash
python -m streamlit run main.py
```

Open the local URL displayed in your terminal.

## Security Notes

AI-generated SQL can be incorrect or unsafe. This project includes SQL validation and user confirmation before execution, but these checks are not a complete security guarantee.

- Use a dedicated, least-privilege MySQL account.
- Keep database credentials in environment variables.
- Review generated SQL before approving execution.
- Do not expose the database publicly.
- Test SQL validation against potentially destructive and unauthorized queries.

## Current Scope

The current version focuses on generating and executing SQL queries against a configured MySQL database. Query accuracy depends on the model, database schema, and wording of the question.

## Future Improvements

- Improve schema-aware query generation.
- Add automated SQL accuracy and safety tests.
- Improve error handling and query explanations.
- Add query history and execution-time metrics.
- Support more complex database schemas.

## Author

**Ghulam e Mustafa**

AI Automation & Agent Development

