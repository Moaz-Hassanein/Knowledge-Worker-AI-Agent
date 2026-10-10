""" from Knowledge_Workers.Knowledge_Workers.src.graph import builder
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from pathlib import Path
from agent.extraction_agent import extract_data_node
from agent.extraction_agent import build_context
from create_review_plan.ConfirmPlan import confirm_plan
from create_review_plan.Plan import create_review_plan
from create_review_plan.state import GenericAgentState
from Parse import parse_review_docs
from report import generate_report


def build_graph():

    builder = StateGraph(GenericAgentState)

    # ============================================================
    # NODES
    # ============================================================

    builder.add_node("parse_review_docs", parse_review_docs)
    builder.add_node("create_review_plan", create_review_plan)
    builder.add_node("confirm_plan", confirm_plan)
    builder.add_node("build_context", build_context)
    builder.add_node("extract_data", extract_data_node)
    builder.add_node("generate_report", generate_report)

    # ============================================================
    # START
    # ============================================================

    builder.add_edge(
        START,
        "parse_review_docs"
    )

    # ============================================================
    # PARSE -> CREATE REVIEW PLAN
    # ============================================================

    builder.add_conditional_edges(
        "parse_review_docs",
        after_parse,
        {
            "create_review_plan": "create_review_plan",
            END: END,
        },
    )

    # ============================================================
    # CREATE REVIEW PLAN -> CONFIRM PLAN
    # ============================================================

    builder.add_conditional_edges(
        "create_review_plan",
        after_create_plan,
        {
            "confirm_plan": "confirm_plan",
            END: END,
        },
    )

    # ============================================================
    # CONFIRM PLAN -> BUILD CONTEXT
    # ============================================================

    builder.add_conditional_edges(
        "confirm_plan",
        after_confirm_plan,
        {
            "build_context": "build_context",
            END: END,
        },
    )

    # ============================================================
    # BUILD CONTEXT -> EXTRACT DATA
    # ============================================================

    builder.add_edge(
        "build_context",
        "extract_data"
    )

    # ============================================================
    # REPORT -> END
    # ============================================================

    builder.add_edge(
        "generate_report",
        END
    )

    return builder.compile(
        checkpointer=MemorySaver()
    )


# ================================================================
# ROUTERS
# ================================================================

def after_parse(state: GenericAgentState) -> str:

    if state.get("execution_status") == "FAILED":
        return END

    return "create_review_plan"


def after_create_plan(state: GenericAgentState) -> str:

    if state.get("execution_status") == "FAILED":
        return END

    return "confirm_plan"


def after_confirm_plan(state: GenericAgentState) -> str:
    
    Route after the human confirms or rejects the plan.
    

    if state.get("execution_status") == "FAILED":
        return END

    if state.get("evaluation_status") == "APPROVED":
        return "build_context"

    return END


# ================================================================
# BUILD GRAPH
# ================================================================

graph = build_graph()


# ================================================================
# VISUALIZATION
# ================================================================

png_data = graph.get_graph().draw_mermaid_png()

with open("/tmp/graph.png", "wb") as f:
#with open("graph.png", "wb") as f:
    f.write(png_data)

print("Graph saved to graph.png")


__all__ = ["build_graph", "graph"]

 """


from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from create_review_plan.state import GenericAgentState

from Parse import parse_review_docs
from create_review_plan.Plan import create_review_plan
from create_review_plan.ConfirmPlan import confirm_plan
from agent.auditing.generate_report import generate_report
from agent.extraction_agent import (
    build_context,
    extract_data_node,
)

from agent.auditing import (
    evaluate_record,
    human_review,
    update_policy,
    log_audit_entry,
)
from agent.auditing.evaluate_record import route_after_evaluate
from agent.auditing.evaluate_record import evaluate_record
from agent.auditing.human_review import human_review
from agent.auditing.update_policy import update_policy
from agent.auditing.log_audit_entry import log_audit_entry
from agent.auditing.generate_report import generate_report
#from report import generate_report


def _write_report_docx_node(state: GenericAgentState):
    """Adapt the report generator to LangGraph's state-node API."""
    return generate_report(state)


def build_graph():

    builder = StateGraph(GenericAgentState)

    # -----------------------------
    # Main pipeline nodes
    # -----------------------------

    builder.add_node("parse_review_docs",parse_review_docs,)

    builder.add_node("create_review_plan",create_review_plan,)

    builder.add_node("confirm_plan",confirm_plan,)

    builder.add_node("build_context",build_context,)

    builder.add_node("extract_data",extract_data_node,)

    # -----------------------------
    # Audit loop
    # -----------------------------

    builder.add_node("evaluate_record",evaluate_record,)

    builder.add_node("human_review",human_review,)

    builder.add_node("update_policy",update_policy,)

    builder.add_node("log_audit_entry",log_audit_entry,)

    builder.add_node("generate_report",generate_report,
)

    # -----------------------------
    # Main flow
    # -----------------------------

    builder.add_edge(
        START,
        "parse_review_docs",
    )

    builder.add_conditional_edges(
        "parse_review_docs",
        after_parse,
        {
            "create_review_plan": "create_review_plan",
            END: END,
        },
    )

    builder.add_conditional_edges(
        "create_review_plan",
        after_create_plan,
        {
            "confirm_plan": "confirm_plan",
            END: END,
        },
    )

    builder.add_conditional_edges(
        "confirm_plan",
        after_confirm_plan,
        {
            "build_context": "build_context",
            END: END,
        },
    )

    builder.add_edge(
        "build_context",
        "extract_data",
    )

    builder.add_conditional_edges(
        "extract_data",
        after_extract,
        {
            "evaluate_record": "evaluate_record",
            "generate_report": "generate_report",
            END: END,
        },
    )

    # -----------------------------
    # Per-record audit loop
    # -----------------------------

    builder.add_conditional_edges(
        "evaluate_record",
        route_after_evaluate,
        {
            "human_review": "human_review",
            "log_audit_entry": "log_audit_entry",
            "generate_report": "generate_report",
            END: END,
        },
    )

    # Human review can update the policy
    builder.add_edge(
        "update_policy",
        "log_audit_entry",
    )

    # -----------------------------
    # Report
    # -----------------------------

    builder.add_edge(
        "generate_report",
        END,
    )

    # -----------------------------
    # Checkpointing for HITL
    # -----------------------------

    return builder.compile(
        checkpointer=MemorySaver()
    )


def after_parse(state):

    if state.get("execution_status") == "FAILED":
        return END

    return "create_review_plan"


def after_create_plan(state):

    if state.get("execution_status") == "FAILED":
        return END

    return "confirm_plan"


def after_confirm_plan(state):

    if state.get("execution_status") == "FAILED":
        return END

    if state.get("evaluation_status") == "APPROVED":
        return "build_context"

    return END


def after_extract(state):

    if state.get("execution_status") == "FAILED":
        return "generate_report"

    if not state.get("extracted_data"):
        return "generate_report"

    return "evaluate_record"


graph = build_graph()


# Optional graph visualization
try:
    png_data = graph.get_graph().draw_mermaid_png()

    from pathlib import Path

    graph_path = Path(__file__).resolve().parents[1] / "graph.png"
    with graph_path.open("wb") as f:
        f.write(png_data)

    print(f"Graph saved to {graph_path}")

except Exception as exc:
    print(f"Could not save graph image: {exc}")


__all__ = [
    "build_graph",
    "graph",
]