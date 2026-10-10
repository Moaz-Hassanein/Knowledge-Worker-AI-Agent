from typing import Any, Dict, List, TypedDict


class GenericAgentState(TypedDict, total=False):
    # Original user/use-case requirement
    requirement: str

    # Result produced by the Parse stage
    parsed_requirements: Dict[str, Any]

    # Result produced by Create Review Plan stage
    review_plan: Dict[str, Any]

    # Human-approved review plan
    approved_review_plan: Dict[str, Any]

    # Files available to the Extract Data agent
    files: List[str]
    #
    agent_context: Dict[str, Any]
    # Data discovered during extraction
    extracted_data: List[Dict[str, Any]]

    # Validation results
    validation_results: List[Dict[str, Any]]

    # Final answer
    final_result: Dict[str, Any]

    # Conversation/messages for the ReAct agent
    messages: List[Any]
    #output
    report_path: str