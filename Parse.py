from pathlib import Path
from typing import Any, Dict

from langchain_core.runnables import RunnableConfig

from create_review_plan.state import GenericAgentState
from tools.file_tools import extract_text_impl


def _read_text_file(path: str, label: str) -> str:
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"{label} not found at path: {path}")

    if not file_path.is_file():
        raise OSError(f"{label} path exists but is not a file: {path}")

    if file_path.suffix.lower() == ".docx":
        extracted = extract_text_impl(path)
        if extracted.get("status") == "success":
            contents = "\n".join(extracted.get("paragraphs", [])).strip()
        else:
            try:
                contents = file_path.read_text(encoding="utf-8").strip()
            except UnicodeDecodeError:
                raise ValueError(extracted.get("error", f"Unable to read {label}."))
    else:
        contents = file_path.read_text(encoding="utf-8").strip()

    if not contents:
        raise ValueError(f"{label} at {path} is empty.")

    return contents


def parse_review_docs(state: GenericAgentState, config: RunnableConfig) -> Dict[str, Any]:
    configurable = config.get("configurable", {})
    process_path = configurable.get("review_process_path")
    policy_path = configurable.get("review_policy_path")
    target_file_path = configurable.get("target_file_path", state.get("target_file_path", ""))
    use_case_description = configurable.get("use_case_description", state.get("use_case_description"))
    required_data = configurable.get("required_data", state.get("required_data", []))

    if not process_path or not policy_path:
        return {
            "execution_status": "FAILED",
            "error_message": (
                "Missing required config: 'review_process_path' and "
                "'review_policy_path' must both be supplied in "
                "config['configurable']."),
            "is_completed": True,
        }

    try:
        review_process_text = _read_text_file(process_path, "review_process")
        review_policy_text = _read_text_file(policy_path, "review_policy")
    except (FileNotFoundError, OSError, ValueError) as exc:
        return {
            "execution_status": "FAILED",
            "error_message": str(exc),
            "is_completed": True
        }

    return {
        "review_process": review_process_text,
        "review_policy": review_policy_text,
        "policy_file_path": policy_path,
        "target_file_path": target_file_path,
        "use_case_description": use_case_description,
        "required_data": required_data,

        "active_policy": review_policy_text,
        "process_steps": [],
        "current_step_index": 0,

        "audit_in_progress": "",

        "evaluation_status": "PENDING",
        "evaluation_reasoning": "",
        "evidence": {},

        "requires_human": False,
        "human_intervention": None,

        "audit_entries": [],
        "report_path": None,
        "summary": {},

        "execution_status": "PLANNING",
        "is_completed": False,
        "error_message": None
    }