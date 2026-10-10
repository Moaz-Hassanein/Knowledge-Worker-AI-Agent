from typing import Any, Dict, List
from langgraph.types import Command, interrupt
from create_review_plan.state import GenericAgentState, ProcessStep

def _coerce_steps(
    raw_steps: List[Dict[str, Any]]
) -> List[ProcessStep]:
    return [
        ProcessStep(
            step_id=s["step_id"],
            description=s["description"],
            action_type=s["action_type"],
            status=s.get("status", "pending"),
        )
        for s in raw_steps
    ]


def confirm_plan(state: GenericAgentState) -> Command:
    human_response = interrupt(
        {
            "type": "plan_review",
            "message": (
                "Review the generated plan below. "
                "Approve it as-is or edit it before continuing."
            ),
            "plan": state.get("process_steps", []),
        }
    )

    # Make sure the response is a dictionary
    if not isinstance(human_response, dict):
        human_response = {
            "approved": False
        }

    approved = human_response.get(
        "approved",
        False
    )

    # User rejected the plan
    if not approved:
        return Command(
            update={
                "requires_human": True,
                "human_intervention": "Review plan rejected.",
                "execution_status": "FAILED",
                "evaluation_status": "REJECTED",
                "plan_status": "REJECTED"
            },
            goto="__end__",
        )

    edited_plan = human_response.get(
        "edited_plan"
    )

    update: Dict[str, Any] = {
        "requires_human": False,
        "human_intervention": None,
        "execution_status": "EXTRACTING",
        "evaluation_status": "APPROVED",
        "plan_status": "approved",
    }

    # If the human edited the plan
    if (
        isinstance(edited_plan, list)
        and all(isinstance(step, dict) for step in edited_plan)
    ):
        update["process_steps"] = _coerce_steps(
            edited_plan
        )

    steps = update.get("process_steps", state.get("process_steps", []))
    update["process_steps"] = [
        {**step, "status": "in_progress" if index == 0 else "pending"}
        for index, step in enumerate(steps)
    ]

    # Save approved plan
    update["approved_review_plan"] = {
        "status": "approved",
        "steps": update.get(
            "process_steps",
            state.get("process_steps", [])
        ),
    }

    # Continue to extraction
    return Command(update=update)  # Let after_confirm_plan router decide
