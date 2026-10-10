import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import gradio as gr
from dotenv import load_dotenv
from langgraph.types import Command

from agent.auditing.session_log import log_event, new_session_id
from agent.graph import graph

try:
    from langfuse.langchain import CallbackHandler
except ImportError:
    class CallbackHandler:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs):
            pass


load_dotenv()


def _new_session() -> Dict[str, Any]:
    thread_id = str(uuid.uuid4())
    session_id = new_session_id()
    return {
        "thread_config": {
            "configurable": {"thread_id": thread_id},
            "callbacks": [CallbackHandler()],
        },
        "session_id": session_id,
        "result": None,
        "pending": None,
    }


def _file_path(file_value: Any, label: str) -> str:
    if not file_value:
        raise ValueError(f"Please attach the {label} file.")
    path = getattr(file_value, "name", file_value)
    path = str(path)
    if not Path(path).is_file():
        raise ValueError(f"The {label} file could not be found: {path}")
    return path


def _json_text(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, default=str)


def _interrupt_payload(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    interrupts = result.get("__interrupt__")
    if not interrupts:
        return None
    interrupt = interrupts[0]
    return getattr(interrupt, "value", interrupt)


def _status_message(result: Dict[str, Any], pending: Optional[Dict[str, Any]]) -> str:
    if pending:
        if pending.get("type") == "plan_review":
            return "Human action required: choose Yes to approve the plan or No to edit it."
        return (
            "Human action required: the record is unclear or needs manual review. "
            "Choose valid or invalid."
        )
    status = result.get("execution_status", "UNKNOWN") if result else "UNKNOWN"
    return f"Pipeline status: {status}"


def _view_for_result(result: Dict[str, Any], session: Dict[str, Any]):
    pending = _interrupt_payload(result)
    session["result"] = result
    session["pending"] = pending

    plan = pending.get("plan", []) if pending and pending.get("type") == "plan_review" else []
    record = pending.get("record", {}) if pending and pending.get("type") == "record_review" else {}
    reasoning = ""
    if pending and pending.get("type") == "record_review":
        reasoning = "\n\n".join(
            part
            for part in (
                pending.get("message", ""),
                f"Agent status: {pending.get('agent_status', 'UNKNOWN')}",
                f"Agent reasoning: {pending.get('agent_reasoning', '')}",
            )
            if part
        )

    report_path = result.get("report_path") if not pending else None
    final_json = result if not pending else {}
    return (
        session,
        _status_message(result, pending),
        _json_text(plan),
        _json_text(record),
        reasoning,
        gr.update(visible=bool(pending and pending.get("type") == "plan_review")),
        gr.update(visible=bool(pending and pending.get("type") == "record_review")),
        final_json,
        report_path if report_path and Path(report_path).is_file() else None,
    )


def start_review(requirement, required_data, process_file, policy_file, target_file):
    try:
        process_path = _file_path(process_file, "review process")
        policy_path = _file_path(policy_file, "review policy")
        target_path = _file_path(target_file, "target")
        fields = [line.strip() for line in str(required_data).splitlines() if line.strip()]
        if not fields:
            raise ValueError("Enter at least one required data field.")
        if not str(requirement).strip():
            raise ValueError("Enter a review requirement.")

        session = _new_session()
        config = session["thread_config"]
        config["configurable"].update(
            {
                "review_process_path": process_path,
                "review_policy_path": policy_path,
                "target_file_path": target_path,
                "use_case_description": requirement,
                "required_data": fields,
            }
        )
        log_event(
            session["session_id"],
            "session_started",
            {
                "requirement": requirement,
                "required_data": fields,
                "process_path": process_path,
                "policy_path": policy_path,
                "target_path": target_path,
            },
        )
        result = graph.invoke(
            {
                "target_file_path": target_path,
                "use_case_description": requirement,
                "required_data": fields,
                "session_id": session["session_id"],
            },
            config=config,
        )
        return _view_for_result(result, session)
    except Exception as exc:
        return (
            {},
            f"Error: {exc}",
            "[]",
            "{}",
            "",
            gr.update(visible=False),
            gr.update(visible=False),
            {"error": str(exc)},
            None,
        )


def resume_plan(plan_text, session):
    try:
        plan = json.loads(plan_text or "[]")
        if not isinstance(plan, list):
            raise ValueError("The plan must be a JSON list of steps.")
        result = graph.invoke(
            Command(resume={"approved": True, "edited_plan": plan}),
            config=session["thread_config"],
        )
        return _view_for_result(result, session)
    except Exception as exc:
        return _error_view(session, exc)


def show_plan_editor(plan_text, session):
    """Switch from plan approval to step-by-step plan editing."""
    try:
        plan = json.loads(plan_text or "[]")
        if not isinstance(plan, list):
            raise ValueError("The plan must be a JSON list of steps.")
        step_ids = [str(step.get("step_id")) for step in plan]
        return (
            session,
            "Plan was not approved as-is. Choose a step ID and enter its new description.",
            gr.update(visible=False),
            gr.update(visible=True),
            gr.update(choices=step_ids, value=step_ids[0] if step_ids else None),
            "",
            gr.update(visible=False),
            {"plan": plan},
            None,
        )
    except Exception as exc:
        return _error_view(session, exc)


def update_plan_step(step_id, description, plan_text, session):
    """Apply one edited description while keeping the plan in the editor."""
    try:
        if not step_id:
            raise ValueError("Choose a step ID first.")
        if not str(description).strip():
            raise ValueError("Enter a new description.")
        plan = json.loads(plan_text or "[]")
        selected = next(
            (step for step in plan if str(step.get("step_id")) == str(step_id)),
            None,
        )
        if selected is None:
            raise ValueError(f"No plan step has ID {step_id}.")
        selected["description"] = str(description).strip()
        return (
            session,
            f"Step {step_id} updated. Edit another step or continue with this plan.",
            _json_text(plan),
            gr.update(),
            gr.update(),
            "",
            gr.update(visible=True),
            {"plan": plan},
            None,
        )
    except Exception as exc:
        return _error_view(session, exc)


def load_step_description(step_id, plan_text):
    if not step_id:
        return ""
    try:
        plan = json.loads(plan_text or "[]")
        selected = next(
            (step for step in plan if str(step.get("step_id")) == str(step_id)),
            None,
        )
        return selected.get("description", "") if selected else ""
    except (TypeError, json.JSONDecodeError):
        return ""


def _error_view(session, exc):
    return (
        session,
        f"Error: {exc}",
        gr.update(),
        gr.update(),
        gr.update(),
        gr.update(),
        gr.update(),
        {"error": str(exc)},
        None,
    )


def resume_record(status, reasoning, propose_update, proposed_rule, session):
    try:
        if status not in {"valid", "invalid"}:
            raise ValueError("Choose valid or invalid before continuing.")
        result = graph.invoke(
            Command(
                resume={
                    "status": status,
                    "reasoning": reasoning or "",
                    "propose_rule_update": bool(propose_update),
                    "proposed_rule_text": proposed_rule or "",
                }
            ),
            config=session["thread_config"],
        )
        return _view_for_result(result, session)
    except Exception as exc:
        return _error_view(session, exc)


def build_app() -> gr.Blocks:
    with gr.Blocks(title="Knowledge Worker Review") as app:
        session = gr.State({})
        gr.Markdown("# Knowledge Worker Review")
        gr.Markdown("Attach the review inputs, then complete any human decisions requested by the agent.")

        with gr.Row():
            with gr.Column(scale=2):
                requirement = gr.Textbox(label="Review requirement", lines=4)
                required_data = gr.Textbox(
                    label="Required data fields (one per line)", lines=6
                )
            with gr.Column(scale=1):
                process_file = gr.File(label="Review process", type="filepath")
                policy_file = gr.File(label="Review policy", type="filepath")
                target_file = gr.File(label="Target file", type="filepath")

        start = gr.Button("Start review", variant="primary")
        status = gr.Markdown("Attach the files and start a review.")

        with gr.Group(visible=False) as plan_group:
            gr.Markdown("## Review plan")
            plan_editor = gr.Code(label="Generated review plan", language="json", lines=12)
            with gr.Row():
                approve_plan = gr.Button("Yes - approve plan", variant="primary")
                edit_plan = gr.Button("No - edit plan")
            with gr.Group(visible=False) as plan_edit_group:
                step_id = gr.Dropdown(label="Step ID", choices=[])
                step_description = gr.Textbox(label="New step description", lines=3)
                update_step = gr.Button("Update step")
                continue_plan = gr.Button("Continue with edited plan", variant="primary")

        with gr.Group(visible=False) as record_group:
            gr.Markdown("## Human review")
            record_view = gr.JSON(label="Flagged record")
            agent_reasoning = gr.Textbox(label="Agent reasoning", interactive=False, lines=4)
            decision = gr.Dropdown(["valid", "invalid"], label="Decision")
            decision_reasoning = gr.Textbox(label="Reasoning", lines=3)
            propose_update = gr.Checkbox(label="Propose a standing policy update")
            proposed_rule = gr.Textbox(label="Proposed policy rule", lines=3)
            submit_record = gr.Button("Submit decision", variant="primary")

        final_result = gr.JSON(label="Result")
        report_file = gr.File(label="Generated report")

        outputs = [
            session,
            status,
            plan_editor,
            record_view,
            agent_reasoning,
            plan_group,
            record_group,
            final_result,
            report_file,
        ]
        start.click(start_review, [requirement, required_data, process_file, policy_file, target_file], outputs)
        approve_plan.click(resume_plan, [plan_editor, session], outputs)
        edit_plan.click(
            show_plan_editor,
            [plan_editor, session],
            [session, status, approve_plan, plan_edit_group, step_id, step_description, continue_plan, final_result, report_file],
        )
        update_step.click(
            update_plan_step,
            [step_id, step_description, plan_editor, session],
            [session, status, plan_editor, approve_plan, step_id, step_description, continue_plan, final_result, report_file],
        )
        step_id.change(
            load_step_description,
            [step_id, plan_editor],
            step_description,
        )
        step_description.submit(
            update_plan_step,
            [step_id, step_description, plan_editor, session],
            [session, status, plan_editor, approve_plan, step_id, step_description, continue_plan, final_result, report_file],
        )
        continue_plan.click(resume_plan, [plan_editor, session], outputs)
        submit_record.click(
            resume_record,
            [decision, decision_reasoning, propose_update, proposed_rule, session],
            outputs,
        )

    return app


if __name__ == "__main__":
    build_app().launch(
        server_name=os.getenv("GRADIO_SERVER_NAME", "127.0.0.1"),
        server_port=int(os.getenv("GRADIO_SERVER_PORT", "7860")),
    ) 