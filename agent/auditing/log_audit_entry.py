from datetime import datetime, timezone
from typing import Any, Dict
from langgraph.types import Command
from create_review_plan.state import GenericAgentState

def log_audit_entry(state: GenericAgentState) -> Command:
    records = state.get("extracted_data", [])
    index = state.get("current_record_index", 0)

    if not records:
        return Command(update={"execution_status": "GENERATING_REPORT"}, goto="generate_report")
    record = records[index]

    entry: Dict[str, Any] = {
        "record_id": record.get("id", record.get("record_id", str(index + 1))),
        "record": record,
        "status": state.get("evaluation_status", "ERROR"),
        "reasoning": state.get("evaluation_reasoning", ""),
        "evidence": state.get("evidence", {}),
        "resolved_by_human": bool(state.get("resolved_by_human", False)),
        "flagged_reason": state.get("flagged_reason"),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    audit_entries = state.get("audit_entries", []) + [entry]
    next_index = index + 1
    total = len(records)

    if next_index < total:
        return Command(update={"audit_entries": audit_entries, "current_record_index": next_index}, goto="evaluate_record")
    return Command(update={"audit_entries": audit_entries, "execution_status": "GENERATING_REPORT"}, goto="generate_report")