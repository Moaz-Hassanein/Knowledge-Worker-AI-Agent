import json
import time
from typing import Any, Dict, List
from agent.cost_tracker import tracker
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_ollama import ChatOllama
from agent.auditing.session_log import log_event
from helpers.settings import get_settings
from create_review_plan.state import GenericAgentState, ProcessStep


PLAN_SYSTEM_PROMPT = """You are the planning module of a knowledge-worker automation agent.

You will be given a use case, required data fields, and one or more review
process descriptions written by a human in plain language. Select only the
process sections relevant to the use case and required data, then convert
them into an ordered list of concrete execution steps. Do not include steps
from unrelated workflows.

Respond with JSON ONLY -- no markdown fences, no commentary, nothing before
or after the JSON. The JSON must be an array of objects shaped exactly like
this:

[
  {"step_id": 1, "description": "short, concrete description of the step", "action_type": "read_data"},
  {"step_id": 2, "description": "...", "action_type": "compare_policy"}
]

step_id starts at 1 and increases by 1 for each step, in the order the
steps should be executed. action_type should be one of: read_data,
extract, calculate, compare_policy, escalate, other -- pick whichever
best fits each step.
"""


def _get_planning_llm() -> ChatOllama:
    settings = get_settings()

    return ChatOllama(
        model=settings.GENERATION_MODEL_NAME,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=settings.GENERATION_DEFAULT_TEMPERATURE,
        num_predict=settings.GENERATION_DEFAULT_MAX_TOKENS,
        reasoning=False,
    )


def _generate_plan_text(review_process: str, session_id: str) -> str:

    llm = _get_planning_llm()
    start_time = time.perf_counter()

    messages = [
        SystemMessage(content=PLAN_SYSTEM_PROMPT),
        HumanMessage(content=f"Review process description:\n{review_process}"),
    ]
    response = llm.invoke(messages)
    log_event(session_id, "planning_llm_call", {
        "request": [m.content for m in messages],
        "response": str(response.content or "")
    })
    text = str(response.content or "").strip()
    tracker.record(
            node_name="create_review_plan",
            response=response,
            elapsed_time=time.perf_counter() - start_time,
        )

    

    if text:
        return text


    for value in (response.additional_kwargs or {}).values():
        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


def _parse_plan_json(raw_text: str) -> List[ProcessStep]:
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().lower() in {"```", "```json"}:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    text = text.strip()

    steps_json = json.loads(text)

    return [
        ProcessStep(
            step_id=item["step_id"],
            description=item["description"],
            action_type=item["action_type"],
            status="pending",
        )
        for item in steps_json
    ]


def create_review_plan(state: GenericAgentState, config: RunnableConfig) -> Dict[str, Any]:
    review_process = state.get("review_process")
    session_id = state.get("session_id", "unknown")
    use_case = state.get("use_case_description", "")
    required_data = state.get("required_data", [])
    if not review_process:
        return {
            "execution_status": "FAILED",
            "error_message": (
                "create_review_plan: state['review_process'] is empty. "
                "Did parse_review_docs run first?"
            ),
            "is_completed": True,
        }

    try:
        raw_text = _generate_plan_text(
            f"Use case:\n{use_case}\n\nRequired data:\n{required_data}\n\n"
            f"Review process:\n{review_process}",
            session_id,
        )

        print("\n========== RAW PLAN OUTPUT ==========")
        print(repr(raw_text))
        print("====================================\n")

        steps = _parse_plan_json(raw_text)
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        return {
            "execution_status": "FAILED",
            "error_message": (
                f"create_review_plan: failed to parse the model's plan output: {exc}"
            ),
            "is_completed": True,
        }

    if not steps:
        return {
            "execution_status": "FAILED",
            "error_message": "create_review_plan: the model returned an empty plan.",
            "is_completed": True,
        }

    return {
        "process_steps": steps,
        "current_step_index": 0,
        "execution_status": "PLAN_READY",
        "requires_human": True,
        "human_intervention": None,
    }