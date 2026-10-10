""" import json
import time
from typing import Any, Dict
from langchain_ollama import ChatOllama
from agent.cost_tracker import tracker
from create_review_plan.state import GenericAgentState
from helpers.settings import get_settings
from tools.file_tools import (
    inspect_file_impl,
    extract_text_impl,
    extract_tables_impl,
)


# ============================================================
# LLM SETUP
# ============================================================

settings = get_settings()

llm = ChatOllama(
    model=settings.GENERATION_MODEL_NAME,
    base_url=getattr(
        settings,
        "OLLAMA_BASE_URL",
        #"http://localhost:11434",
        "http://host.docker.internal:11434",
    ),
    temperature=0,
    reasoning=False,
      num_ctx=getattr(settings, "GENERATION_NUM_CTX", 8192),
    )



def _build_task_message(state: GenericAgentState) -> str:
    plan = json.dumps(state.get("process_steps", []), indent=2, default=str)
    required = state.get("required_data", [])
    target = state.get("target_file_path")

    return (
        f"Approved review plan:\n{plan}\n\n"
        f"Target file: {target}\n"
        f"Required data fields per record: {required}\n\n"
        "Execute the plan using your tools, then respond with your final "
        "answer as instructed in your system prompt."
    )


def _parse_records(raw_text: str) -> List[Dict[str, Any]]:
    text = (raw_text or "").strip()

    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    text = text.strip()

    data = json.loads(text)

    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ValueError("Expected a JSON array of records.")

    for index, record in enumerate(data):
        if not isinstance(record, dict):
            raise ValueError(f"Record at position {index} is not an object.")
        record.setdefault("id", str(index))

    return data



# ============================================================
# EXTRACT DATA NODE
# ============================================================

def extract_data_node(state: GenericAgentState) -> Dict[str, Any]:
    
    Extract data from files using the approved review plan.

    Steps:
    1. Inspect the target file.
    2. Extract text/tables.
    3. Send extracted data to the LLM.
    4. Track LLM tokens and execution time.
    5. Return the extraction result.
    

    target_file = state.get("target_file_path")
    review_steps = state.get("process_steps", [])
    required_data = state.get("required_data", [])

    # ========================================================
    # VALIDATION
    # ========================================================

    if not target_file:
        return {
            "execution_status": "FAILED",
            "error_message": "No target file was provided.",
            "is_completed": True,
        }

    if not review_steps:
        return {
            "execution_status": "FAILED",
            "error_message": "No review plan was provided.",
            "is_completed": True,
        }

    print(
        f"\n[EXTRACTION] Starting extraction for: "
        f"{target_file}"
    )

    print(
        f"[EXTRACTION] Processing "
        f"{len(review_steps)} review steps"
    )

    print(
        f"[EXTRACTION] Required data: "
        f"{required_data}"
    )

    try:

        # ====================================================
        # 1. INSPECT FILE
        # ====================================================

        print("\n[EXTRACTION] Inspecting file...")

        inspection = inspect_file_impl(target_file)

        if inspection.get("status") != "success":
            return {
                "execution_status": "FAILED",
                "error_message": (
                    "File inspection failed: "
                    f"{inspection.get('error', 'Unknown error')}"
                ),
                "is_completed": True,
            }

        file_type = inspection.get("file_type")

        print(
            f"[EXTRACTION] File type detected: "
            f"{file_type}"
        )

        # ====================================================
        # 2. EXTRACT RAW DATA
        # ====================================================

        extracted_result = None

        if file_type == "excel":

            print(
                "[EXTRACTION] "
                "Extracting tables from Excel file..."
            )

            extracted_result = extract_tables_impl(
                target_file
            )

        elif file_type == "word":

            print(
                "[EXTRACTION] "
                "Extracting from Word file..."
            )

            extracted_result = {
                "text": extract_text_impl(
                    target_file
                ),
                "tables": extract_tables_impl(
                    target_file
                ),
            }

        elif file_type == "text":

            print(
                "[EXTRACTION] "
                "Extracting text from text file..."
            )

            extracted_result = extract_text_impl(
                target_file
            )

        else:

            return {
                "execution_status": "FAILED",
                "error_message": (
                    f"Unsupported file type: "
                    f"{file_type}"
                ),
                "is_completed": True,
            }

        print(
            "[EXTRACTION] "
            "Raw file extraction completed."
        )

        # ====================================================
        # 3. CREATE LLM PROMPT
        # ====================================================

        print(
            "[EXTRACTION] "
            "Preparing LLM prompt..."
        )

        llm_prompt: str = f
You are a data extraction assistant.

Your job is to organize the extracted information
according to the approved review plan.

APPROVED REVIEW PLAN:
{json.dumps(review_steps, indent=2, default=str)}

REQUIRED DATA:
{json.dumps(required_data, indent=2, default=str)}

EXTRACTED FILE DATA:
{json.dumps(extracted_result, indent=2, default=str)}

Instructions:

1. Use only information contained in the extracted
   file data.
2. Follow the approved review plan.
3. Identify the required data.
4. Organize the information clearly.
5. Do not invent or assume values.
6. If required information is missing, explicitly
   state that it is missing.

Return the extracted information in a clear,
structured format.


        # ====================================================
        # 4. LLM CALL + TIME TRACKING
        # ====================================================

        print(
            "[EXTRACTION] "
            "Sending extracted data to LLM..."
        )

        start_time = time.perf_counter()

        response = llm.invoke(llm_prompt)

        elapsed_time = time.perf_counter() - start_time

        # ====================================================
        # 5. TRACK TOKENS + TIME
        # ====================================================

        tracker.record(
            "extract_data",
            response,
            elapsed_time,
        )

        # ====================================================
        # 6. FORMAT RESULT
        # ====================================================

        formatted_result = json.dumps(
            {
                "status": "success",
                "file": target_file,
                "file_type": file_type,
                "inspection": inspection,
                "data": response.content,
                "required_data": required_data,
                "steps_processed": len(review_steps),
            },
            indent=2,
            default=str,
        )

        print(
            "[EXTRACTION] "
            "Extraction completed successfully."
        )

        print(
            f"[EXTRACTION] Result preview: "
            f"{formatted_result[:500]}..."
        )

        # ====================================================
        # 7. RETURN STATE
        # ====================================================

        return {
        "extracted_data": [
            {
            "source": target_file,
            "result": formatted_result,
            }
        ],
        "execution_status": "EXTRACTION_COMPLETED",
        "is_completed": False,
        "error_message": None,
        }

    # ========================================================
    # ERROR HANDLING
    # ========================================================

    except Exception as exc:

        print(
            f"[EXTRACTION] "
            f"Error during extraction: {exc}"
        )

        import traceback

        traceback.print_exc()

        return {
            "execution_status": "FAILED",
            "error_message": (
                f"Extraction failed: {str(exc)}"
            ),
            "is_completed": True,
        }


# ============================================================
# BUILD CONTEXT
# ============================================================

def build_context(state: GenericAgentState) -> Dict[str, Any]:

    context = {
        "documents": state.get("documents"),
        "policy": state.get("policy"),
        "previous_results": state.get("previous_results"),
        "user_request": state.get("user_request"),
    }

    return {
        "agent_context": context
    } """
import json
import time
import os
from typing import Any, Dict, List
#from tools.vision_tools import extract_from_image
from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent
#from langchain.agents import create_agent
from agent.cost_tracker import tracker
from create_review_plan.state import GenericAgentState
from helpers.settings import get_settings
from agent.prompt import SYSTEM_PROMPT
from tools.review_step import TOOLS


MAX_EXTRACTION_ATTEMPTS = 2


def _record_react_usage(messages: list[Any], elapsed_time: float) -> None:
    """Record every usage-bearing LLM turn returned by the ReAct agent."""
    usage_messages = []
    for message in messages:
        usage = getattr(message, "usage_metadata", None) or {}
        metadata = getattr(message, "response_metadata", None) or {}
        has_usage = bool(usage) or any(
            key in metadata for key in ("prompt_eval_count", "eval_count")
        )
        if has_usage:
            usage_messages.append(message)

    if not usage_messages:
        return

    for index, message in enumerate(usage_messages):
        tracker.record(
            node_name="extract_data",
            response=message,
            elapsed_time=elapsed_time if index == len(usage_messages) - 1 else 0.0,
        )

settings = get_settings()


def _get_llm() -> ChatOllama:
    ollama_base_url = os.getenv(
        "OLLAMA_BASE_URL",
        "http://localhost:11434"
    )

    return ChatOllama(
        model=settings.GENERATION_MODEL_NAME,
        base_url=ollama_base_url,
        temperature=0,
        reasoning=False,
        num_ctx=getattr(
            settings,
            "GENERATION_NUM_CTX",
            8192,
        ),
    )
      

def _build_task_message(state: GenericAgentState) -> str:
    plan = json.dumps(
        state.get("process_steps", []),
        indent=2,
        default=str,
    )

    required_data = state.get("required_data", [])
    target_file = state.get("target_file_path")

    return f"""
Approved review plan:

{plan}

Target file:
{target_file}

Required data fields:
{json.dumps(required_data, indent=2)}

Execute the approved review plan using the available tools.

Use the target file above as the source of truth.

For each required data item:
1. Identify where the information exists in the target file.
2. Extract the actual values.
3. Do not invent missing values.
4. Use calculator when an exact calculation is required.
5. Use validate_extracted_data when appropriate.

Return the final answer as a JSON array of records only.

Each record should be a JSON object.

Example:

[
  {{
    "Product": "Laptop",
    "Previous Inventory": 100,
    "Sales": 20,
    "Dispatches": 10,
    "Incoming Shipments": 10,
    "Physical Inventory": 89
  }}
]

Do not use markdown code fences.
Do not include explanations outside the JSON array.
"""


def _parse_records(raw_text: str) -> List[Dict[str, Any]]:
    text = str(raw_text or "").strip()

    if not text:
        raise ValueError("The extraction agent returned an empty response.")

    # Remove markdown fences if the model ignores the instruction.
    if text.startswith("```"):
        lines = text.splitlines()

        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    data = json.loads(text)

    # Allow a single object and normalize it into a list.
    if isinstance(data, dict):
        data = [data]

    if not isinstance(data, list):
        raise ValueError(
            "The extraction agent must return a JSON array of records."
        )

    records: List[Dict[str, Any]] = []

    for index, record in enumerate(data):
        if not isinstance(record, dict):
            raise ValueError(
                f"Record {index + 1} is not a JSON object."
            )

        record = dict(record)

        # Give downstream audit logic a stable record identifier.
        record.setdefault("record_id", index + 1)

        records.append(record)

    return records


def extract_data_node(
    state: GenericAgentState,
) -> Dict[str, Any]:

    target_file = state.get("target_file_path")
    review_steps = state.get("process_steps", [])

    if not target_file:
        return {
            "execution_status": "FAILED",
            "error_message": (
                "extract_data: state['target_file_path'] is empty."
            ),
            "is_completed": True,
        }

    if not review_steps:
        return {
            "execution_status": "FAILED",
            "error_message": (
                "extract_data: state['process_steps'] is empty."
            ),
            "is_completed": True,
        }

    print("\n======================================")
    print("          EXTRACT DATA AGENT")
    print("======================================")
    print(f"Target file: {target_file}")
    print(f"Review steps: {len(review_steps)}")
    print("Starting ReAct extraction agent...\n")

    try:
        llm = _get_llm()

        react_agent = create_react_agent(
            llm,
            tools=TOOLS,
            prompt=SYSTEM_PROMPT,
        )

        conversation = [
            HumanMessage(
                content=_build_task_message(state)
            )
        ]

        last_error = None

        for attempt in range(
            1,
            MAX_EXTRACTION_ATTEMPTS + 1,
        ):

            print(
                f"Extraction attempt "
                f"{attempt}/{MAX_EXTRACTION_ATTEMPTS}"
            )

            start_time = time.perf_counter()
            result = react_agent.invoke(
                {
                    "messages": conversation
                }
            )
            _record_react_usage(
                result.get("messages", []),
                time.perf_counter() - start_time,
            )

            messages = result.get(
                "messages",
                [],
            )

            print("\n========== REACT TRACE ==========")

            for i, message in enumerate(messages):

                message_type = type(message).__name__
                content = getattr(
                    message,
                    "content",
                    "",
                )

                print(
                    f"\n--- Message {i + 1} "
                    f"({message_type}) ---"
                )
                print(content)

            print("\n==================================\n")

            final_message = (
                messages[-1]
                if messages
                else None
            )

            raw_content = (
                getattr(
                    final_message,
                    "content",
                    "",
                )
                if final_message
                else ""
            )

            try:

                records = _parse_records(
                    raw_content
                )

                print(
                    f"Successfully extracted "
                    f"{len(records)} record(s)."
                )

                return {
                    "extracted_data": records,
                    "current_record_index": 0,
                    "messages": messages,
                    "process_steps": [
                        {**step, "status": "completed"}
                        for step in review_steps
                    ],
                    "plan_status": "completed",
                    "execution_status": (
                        "EXTRACTION_COMPLETED"
                    ),
                    "error_message": None,
                    "is_completed": False,
                }

            except (
                json.JSONDecodeError,
                ValueError,
                TypeError,
            ) as exc:

                last_error = exc

                print(
                    "\nFailed to parse final "
                    f"extraction output: {exc}"
                )

                if attempt < MAX_EXTRACTION_ATTEMPTS:

                    conversation = messages + [
                        HumanMessage(
                            content=(
                                "Your previous final answer "
                                "was not valid JSON.\n\n"
                                "Return ONLY a valid JSON array "
                                "of record objects.\n"
                                "Do not use markdown fences.\n"
                                "Do not include any explanation."
                            )
                        )
                    ]

        return {
            "execution_status": "FAILED",
            "error_message": (
                "extract_data: failed to obtain valid "
                f"JSON records after "
                f"{MAX_EXTRACTION_ATTEMPTS} attempts. "
                f"Last error: {last_error}"
            ),
            "is_completed": True,
        }

    except Exception as exc:

        print(
            "\nExtraction agent failed:"
        )
        print(repr(exc))

        return {
            "execution_status": "FAILED",
            "error_message": (
                f"extract_data: {exc}"
            ),
            "is_completed": True,
        }


def build_context(
    state: GenericAgentState,
) -> Dict[str, Any]:

    context = {
        "documents": state.get("documents"),
        "policy": state.get("review_policy"),
        "previous_results": state.get(
            "previous_results"
        ),
        "user_request": state.get(
            "use_case_description"
        ),
    }

    return {
        "agent_context": context
    }