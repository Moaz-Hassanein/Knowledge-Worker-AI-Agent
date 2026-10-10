import json
import time
from typing import Any, Dict, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from helpers.settings import get_settings
from create_review_plan.state import GenericAgentState
from agent.cost_tracker import tracker

MAX_EVAL_ATTEMPTS = 2

EVALUATE_SYSTEM_PROMPT = """You are the evaluation module of an audit agent.

You will be given three things:
1. The confirmed audit plan (the steps this audit is supposed to follow).
2. The current active policy (the rules records must comply with).
3. One record extracted from the target file.

Using the plan as context for what this audit is checking, and the policy
as the standard to check against, decide whether this record is:
  - "valid"              -- it clearly complies with the policy, with no
                            escalation, sign-off, or manual review
                            required
  - "invalid"            -- it clearly violates the policy in a way the
                            policy says must be rejected outright, with
                            no path to approval (e.g. "must be
                            rejected", "cannot be approved under any
                            circumstances")
  - "needs_intervention" -- the policy explicitly calls for supervisor
                            sign-off, manual review, investigation, or
                            escalation before a final decision can be
                            made. Use this even when you can tell
                            exactly which policy clause applies and
                            why -- the policy itself is clear, it just
                            requires a human step before payment/approval.
  - "ambiguous"           -- ONLY use this when:
                            * information needed to decide is missing, OR
                            * the policy doesn't clearly cover this case
                            at all (no clause applies)

Do NOT use "ambiguous" for a case where the policy clearly applies and
tells you a supervisor/manager needs to sign off or review it -- that is
"needs_intervention", a different category. "ambiguous" means the policy
itself gives you nothing to go on; "needs_intervention" means the policy
is clear but requires a human step by design.

Respond with JSON ONLY, no markdown fences, no commentary, nothing before
or after the JSON, shaped exactly like this:
{"status": "valid", "reasoning": "short explanation", "evidence": {"key": "value"}}

"evidence" must pull out the specific fields from the record that drove
your decision -- not the whole record, just what mattered."""


def _get_eval_llm() -> ChatOllama:
    settings = get_settings()
    return ChatOllama(
        model=settings.GENERATION_MODEL_NAME,
        base_url=getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434"),
        temperature=0.0,
        num_predict=getattr(settings, "GENERATION_DEFAULT_MAX_TOKENS", 1024),
        # Qwen 3/3.5 are "thinking" models: by default their reasoning
        # tokens go to a separate channel and can consume the entire
        # num_predict budget before any real answer is written, leaving
        # response.content empty. reasoning=False disables that.
        reasoning=False,
    )


def _parse_eval_json(raw_text: str) -> Dict[str, Any]:
    text = (raw_text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    text = text.strip()

    data = json.loads(text)
    if data.get("status") not in ("valid", "invalid", "ambiguous", "needs_intervention"):
        raise ValueError(f"Unexpected status: {data.get('status')!r}")

    if not isinstance(data.get("evidence"), dict):
        data["evidence"] = {}
    if not isinstance(data.get("reasoning"), str):
        data["reasoning"] = str(data.get("reasoning", ""))

    return data


def _build_prompt(state: GenericAgentState, record: Dict[str, Any]) -> str:
    plan_context = json.dumps(state.get("process_steps", []), indent=2, default=str)
    policy_context = state.get("active_policy", "")
    record_context = json.dumps(record, indent=2, default=str)

    return (
        f"Confirmed audit plan:\n{plan_context}\n\n"
        f"Active policy:\n{policy_context}\n\n"
        f"Record to evaluate (record_id={record.get('id')}):\n"
        f"{record_context}"
    )


def evaluate_record(state: GenericAgentState) -> Dict[str, Any]:
    records = state.get("extracted_data", [])
    idx = state.get("current_record_index", 0)

    if idx >= len(records):
        return {
            "execution_status": "FAILED",
            "error_message": "evaluate_record: current_record_index is out of range.",
            "is_completed": True,
        }

    record = records[idx]
    prompt = _build_prompt(state, record)
    messages = [SystemMessage(content=EVALUATE_SYSTEM_PROMPT), HumanMessage(content=prompt)]

    print(f"Evaluating record {idx + 1}/{len(records)} (record_id={record.get('id')})...")

    llm = _get_eval_llm()
    last_error: Optional[Exception] = None

    for attempt in range(1, MAX_EVAL_ATTEMPTS + 1):
        start_time = time.perf_counter()
        response = llm.invoke(messages)
        tracker.record(
            node_name="evaluate_record",
            response=response,
            elapsed_time=time.perf_counter() - start_time,
        )
        try:
            content = response.content
            if isinstance(content, str):
                raw_text = content
            else:
                raw_text = "".join(
                    part
                    if isinstance(part, str)
                    else str(part.get("text", ""))
                    if isinstance(part, dict)
                    else str(part)
                    for part in content
                )
            result = _parse_eval_json(raw_text)
            return {
                "evaluation_status": result["status"].upper(),
                "evaluation_reasoning": result.get("reasoning", ""),
                "evidence": result.get("evidence", {}),
                # Reset here, once per record, before we know whether this
                # record will need human_review. human_review sets these
                # True/populated if it runs; otherwise they stay
                # False/None for this record all the way to
                # log_audit_entry.
                "resolved_by_human": False,
                "flagged_reason": None,
            }
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            if attempt < MAX_EVAL_ATTEMPTS:
                messages = messages + [
                    HumanMessage(
                        content=(
                            "Your previous response could not be parsed as the "
                            "required JSON object. Respond again with JSON ONLY, "
                            "no markdown fences, no commentary."
                        )
                    )
                ]

    return {
        "evaluation_status": "AMBIGUOUS",
        "evaluation_reasoning": (
            f"Automatic evaluation failed to produce valid JSON after "
            f"{MAX_EVAL_ATTEMPTS} attempts ({last_error}); routed to human."
        ),
        "evidence": {},
        "resolved_by_human": False,
        "flagged_reason": None,
    }


def route_after_evaluate(state: GenericAgentState) -> str:
    if state.get("execution_status") == "FAILED":
        return "generate_report"
    if state.get("evaluation_status") in ("AMBIGUOUS", "NEEDS_INTERVENTION"):
        return "human_review"
    return "log_audit_entry"
