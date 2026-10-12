from typing import TypedDict
from langgraph.graph import StateGraph, END
import requests
import app

MAX_ATTEMPTS = 3


class State(TypedDict, total=False):
    question: str
    schema: str
    sql: str
    error: str
    attempts: int


def generate_node(state: State):
    question = state["question"]
    if state.get("error"):
        question = (
            f"{state['question']}\n\n"
            f"Pichhli query: {state.get('sql', '')}\n"
            f"Error: {state['error']}\n"
            "Ise theek karke sirf ek corrected SELECT query dein."
        )
    try:
        sql = app.generate_sql(
            question,
            state["schema"],
            schema_question=state["question"],
        )
    except requests.RequestException as exc:
        return {
            "error": f"Could not connect to Ollama: {exc}",
            "attempts": state.get("attempts", 0) + 1,
        }
    return {"sql": sql, "attempts": state.get("attempts", 0) + 1, "error": ""}


def validate_node(state: State):
    if state.get("error"):
        return {"error": state["error"]}
    try:
        return {"sql": app.validate_sql(state["sql"]), "error": ""}
    except ValueError as exc:
        return {"error": str(exc)}


def route_after_validate(state: State):
    if not state.get("error"):
        return END
    if state.get("attempts", 0) < MAX_ATTEMPTS:
        return "generate"
    return END


graph = StateGraph(State)
graph.add_node("generate", generate_node)
graph.add_node("validate", validate_node)
graph.set_entry_point("generate")
graph.add_edge("generate", "validate")
graph.add_conditional_edges("validate", route_after_validate)

sql_graph = graph.compile()


def run_agent(question: str, schema: str) -> dict:
    return sql_graph.invoke({
        "question": question,
        "schema": schema,
        "attempts": 0,
        "error": "",
    })