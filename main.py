import argparse
import json
import uuid
import os
from pathlib import Path
from typing import cast

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from matplotlib import text
from agent.graph import graph
from create_review_plan.state import GenericAgentState
from agent.auditing.session_log import new_session_id, log_event, LOG_DIR
from dotenv import load_dotenv
import argparse
from tools.file_tools import (
    inspect_file_impl,
    extract_text_impl,
    extract_tables_impl,
)


try:
    from langfuse.langchain import CallbackHandler
except ImportError:
    class CallbackHandler:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs):
            pass

load_dotenv()


print(
    "LANGFUSE_PUBLIC_KEY loaded:",
    bool(os.getenv("LANGFUSE_PUBLIC_KEY"))
)

print(
    "LANGFUSE_SECRET_KEY loaded:",
    bool(os.getenv("LANGFUSE_SECRET_KEY"))
)

from agent.cost_tracker import tracker
langfuse_handler = CallbackHandler()

def resolve_input_path(value: str) -> str:
    path = Path(value)

    if path.is_file():
        return str(path)

    input_path = Path("input") / value

    if input_path.is_file():
        return str(input_path)

    return value


def run_pipeline(
    requirement: str,
    required_data: list[str],
    review_process_path: str,
    review_policy_path: str,
    target_file_path: str,
    thread_config: RunnableConfig,
    session_id: str,
):
    initial_state = cast(
        GenericAgentState,
        #target_file_path = state.get("target_file_path")
        #review_steps = state.get("review_steps")
        {
            "target_file_path": target_file_path,
            "use_case_description": requirement,
            "required_data": required_data,
            "session_id": session_id,
        },
    )
    print("\n========== DEBUG TARGET FILE ==========")
    print("target_file_path argument:", target_file_path)
    print("initial_state target_file_path:", initial_state.get("target_file_path"))
    print("=======================================\n")

    return graph.invoke(
        initial_state,
        config=thread_config,
    )
#########################################################
def load_file(file_path: str):
    """Load a file using the existing file tools."""

    file_info = inspect_file_impl(file_path)
    file_type = file_info.get("file_type")
    text = extract_text_impl(file_path) if file_type in {"word", "text"} else None
    tables = extract_tables_impl(file_path) if file_type in {"word", "excel"} else None

    return {
        "file_info": file_info,
        "text": text,
        "tables": tables,
    }
####################################################
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the knowledge-worker review pipeline."
    )

    parser.add_argument(
        "--requirement",
        required=True,
    )

    parser.add_argument(
        "--required-data",
        nargs="+",
        required=True,
        metavar="FIELD",
        help="One or more data fields the agent must extract.",
    )

    parser.add_argument(
        "--process",
        required=True,
        help="Path to the review process text file.",
    )

    parser.add_argument(
        "--policy",
        required=True,
        help="Path to the review policy text, DOCX, or TXT file.",
    )

    parser.add_argument(
        "--target",
        required=True,
        help="Path to the XLSX, DOCX, or TXT target file.",
    )

    args = parser.parse_args()

    args.process = resolve_input_path(args.process)
    args.policy = resolve_input_path(args.policy)
    args.target = resolve_input_path(args.target)

    for path in (args.process, args.policy, args.target):
        if not Path(path).is_file():
            parser.error(f"File does not exist: {path}")

    process_data = load_file(args.process)#
    policy_data = load_file(args.policy)#
    target_data = load_file(args.target)#

    # -----------------------------------
    # PRINT INPUTS
    # -----------------------------------

    print("\n=== RAW CLI ARGUMENTS ===")
    print("requirement:", args.requirement)
    print("required_data:", args.required_data)
    print("process:", args.process)
    print("policy:", args.policy)
    print("target:", args.target)

    # ---------------------------------------------------------
    # Resolve input paths
    # ---------------------------------------------------------

    # ---------------------------------------------------------
    # Create ONE thread ID for the entire execution
    # ---------------------------------------------------------

    thread_id = str(uuid.uuid4())

    # This is the equivalent of the thread_config
    # from your second file.
    
    thread_config = cast(
        RunnableConfig,
        {
            "configurable": {
                "thread_id": thread_id,

                # These are available to your graph/nodes
                # through the config.
                "review_process_path": args.process,
                "review_policy_path": args.policy,
                "target_file_path": args.target,
                "use_case_description": args.requirement,
                "required_data": args.required_data,
            },

            "callbacks": [
                langfuse_handler,
            ],
        },
    )

    session_id = new_session_id()

    log_event(
        session_id,
        "session_started",
        {
            "requirement": args.requirement,
            "required_data": args.required_data,
            "process_path": args.process,
            "policy_path": args.policy,
            "target_path": args.target,
        },
    )

    # ---------------------------------------------------------
    # Start pipeline
    # ---------------------------------------------------------

    print("=" * 70)
    print("       KNOWLEDGE WORKER REVIEW PIPELINE")
    print("=" * 70)
    print(f"\nSession log: {LOG_DIR}/session_{session_id}.jsonl")
    print("\nStarting Extract Data Agent...\n")

    result = run_pipeline(
        args.requirement,
        args.required_data,
        args.process,
        args.policy,
        args.target,
        thread_config,
        session_id=session_id,
    )

    # ---------------------------------------------------------
    # HUMAN APPROVAL
    # ---------------------------------------------------------

    while "__interrupt__" in result:

        # Get the actual interrupt object
        interrupt_obj = result["__interrupt__"][0]

        # Get the payload from the interrupt
        interrupt_payload = interrupt_obj.value

        if interrupt_payload.get("type") == "record_review":
            print("\nRECORD REQUIRES HUMAN REVIEW")
            print(json.dumps(interrupt_payload.get("record", {}), indent=2, default=str))
            print(f"\nAgent reasoning: {interrupt_payload.get('agent_reasoning', '')}")
            status = input("Decision (valid/invalid): ").strip().lower()
            while status not in {"valid", "invalid"}:
                status = input("Please enter valid or invalid: ").strip().lower()
            reasoning = input("Reasoning (optional): ").strip()
            result = graph.invoke(
                Command(resume={"status": status, "reasoning": reasoning}),
                config=thread_config,
            )
            continue

        plan = interrupt_payload.get(
            "plan",
            result.get("process_steps", []),
        )

        print("\n")
        print("=" * 70)
        print("                 REVIEW PLAN")
        print("=" * 70)

        print(
            json.dumps(
                plan,
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        )

        print("=" * 70)

        answer = input(
            "\nApprove this plan as-is? (yes/no): "
        ).strip().lower()

        # -----------------------------------------------------
        # APPROVE
        # -----------------------------------------------------

        if answer in ("yes", "y"):

            human_response = {
                "approved": True
            }

            print("\nPlan approved.")
            print("Continuing extraction...\n")

        # -----------------------------------------------------
        # EDIT
        # -----------------------------------------------------

        else:

            # IMPORTANT:
            # Use the plan extracted from the interrupt.
            # Your previous code had:
            #
            #     edited = plan
            #
            # but "plan" was never defined.
            #
            # Now it is defined above.

            edited = [
                dict(step)
                for step in plan
            ]

            print(
                "\nPlan was not approved as-is."
            )

            print(
                "Enter the step_id you want to edit, "
                "and its new description."
            )

            print(
                "Press Enter with no step_id when you're "
                "done editing.\n"
            )

            while True:

                step_id_str = input(
                    "step_id to edit (or Enter to finish): "
                ).strip()

                if not step_id_str:
                    break

                try:
                    step_id = int(step_id_str)

                except ValueError:
                    print("Please enter a number.")
                    continue

                match = next(
                    (
                        step
                        for step in edited
                        if step["step_id"] == step_id
                    ),
                    None,
                )

                if match is None:
                    print(
                        f"No step with step_id {step_id}. "
                        "Try again."
                    )
                    continue

                new_desc = input(
                    f"New description for step {step_id} "
                    f'(current: "{match["description"]}"): '
                ).strip()

                if new_desc:
                    match["description"] = new_desc

            human_response = {
                "approved": True,
                "edited_plan": edited,
            }

            print("\nUpdated plan approved.")
            print("Continuing extraction...\n")

        # -----------------------------------------------------
        # RESUME THE SAME GRAPH THREAD
        # -----------------------------------------------------

        result = graph.invoke(
            Command(
                resume=human_response
            ),
            config=thread_config,
        )

    # ---------------------------------------------------------
    # FINAL RESULT
    # ---------------------------------------------------------
    log_event(
        session_id,
        "session_completed",
        {
            "execution_status": result.get("execution_status"),
            "summary": result.get("summary"),
            "report_path": result.get("report_path"),
            "error_message": result.get("error_message"),
        },
    )
    print("\n")
    print("=" * 70)
    print("                    FINAL RESULT")
    print("=" * 70)

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )

if __name__ == "__main__":
    main()
    tracker.print_summary()
    tracker.flush()

