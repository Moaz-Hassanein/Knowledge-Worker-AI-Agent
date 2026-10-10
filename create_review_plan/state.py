from typing import Any, Dict, List, Literal, Optional
from typing_extensions import TypedDict


class ProcessStep(TypedDict):
    step_id: int
    description: str
    action_type: str
    status: Literal["pending", "in_progress", "completed", "skipped"]


class GenericAgentState(TypedDict, total=False):
    review_process: str
    review_policy: str
    target_file_path: str
    use_case_description: Optional[str]
    required_data: List[str]

    active_policy: str
    policy_file_path: str#
    process_steps: List[ProcessStep]
    
    current_step_index: int

    plan_status: str#

    # ReAct extraction agent scratchpad (think/act/observe messages)
    messages: List[Any]#


    audit_in_progress: str
    current_record_index: int#
    evaluation_status: str
    evaluation_reasoning: str
    evidence: Dict[str, Any]

    requires_human: bool
    human_intervention: Optional[Dict[str, Any]]
    resolved_by_human: bool#
    flagged_reason: Optional[str]#

    audit_entries: List[Dict[str, Any]]
    report_path: Optional[str]
    summary: Dict[str, Any]

    execution_status: str
    is_completed: bool
    error_message: Optional[str]

    approved_review_plan: Dict[str, Any]
    extracted_data: List[Dict[str, Any]]
    validation_results: List[Dict[str, Any]]
    final_result: Dict[str, Any]
