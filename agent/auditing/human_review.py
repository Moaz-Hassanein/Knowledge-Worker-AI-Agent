from typing import Any, Dict

from langgraph.types import Command, interrupt

from create_review_plan.state import GenericAgentState


def human_review(state: GenericAgentState) -> Command:
    records = state.get("extracted_data", [])
    idx = state.get("current_record_index", 0)
    record = records[idx] if idx < len(records) else {}

    # This is set by evaluate_record right before routing here, so it's
    # either "AMBIGUOUS" (policy gap / missing info) or
    # "NEEDS_INTERVENTION" (policy is clear but requires a human step,
    # e.g. supervisor sign-off or escalation).
    flagged_reason = state.get("evaluation_status", "AMBIGUOUS")

    if flagged_reason == "NEEDS_INTERVENTION":
        message = (
            "The policy requires a human step (sign-off, escalation, or "
            "manual review) for this record. Confirm the outcome, and "
            "optionally propose a standing policy update."
        )
        reasoning_label = "Needs human intervention (policy requires sign-off/escalation)"
    else:
        message = (
            "The policy doesn't clearly cover this record, or information "
            "needed to decide is missing. Decide whether it's valid or "
            "invalid, and optionally propose a standing policy update."
        )
        reasoning_label = "Ambiguous policy"

    human_response = interrupt(
        {
            "type": "record_review",
            "message": message,
            "agent_status": flagged_reason,
            "record": record,
            "agent_reasoning": state.get("evaluation_reasoning", ""),
            "active_policy": state.get("active_policy", ""),
        }
    )

    status = human_response.get("status", "INVALID").upper()
    reasoning = str(human_response.get("reasoning", "") or "").strip()
    propose_update = bool(human_response.get("propose_rule_update"))
    proposed_rule_text = human_response.get("proposed_rule_text")

    intervention: Dict[str, Any] = {
        "reason": state.get("evaluation_reasoning", ""),
        "flagged_reason": flagged_reason,
        "question_to_human": "Is this record valid, invalid, or does a rule need to change?",
        "human_response": reasoning,
        "rule_update_proposed": propose_update,
        "proposed_rule_text": proposed_rule_text,
        "resolved": True,
    }

    update: Dict[str, Any] = {
        "evaluation_status": status,
        "evaluation_reasoning": (
            f"{reasoning_label} -- resolved by human: {reasoning}"
            if reasoning
            else f"{reasoning_label} -- resolved by human."
        ),
        "requires_human": False,
        "human_intervention": intervention,
        "resolved_by_human": True,
        "flagged_reason": flagged_reason,
    }

    if propose_update and proposed_rule_text:
        return Command(update=update, goto="update_policy")

    return Command(update=update, goto="log_audit_entry")