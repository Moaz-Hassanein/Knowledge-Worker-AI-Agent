import json
from typing import Any, Dict
import numpy
from langchain_core.tools import tool
#from tools.vision_tools import extract_from_image
from tools.file_tools import (
    inspect_file_impl,
    extract_text_impl,
    extract_tables_impl,
    read_excel_range_impl,
    search_file_impl,
)


@tool
def inspect_file(file_path: str) -> str:
    """
    Inspect a file before extracting data.

    Use this tool to understand the structure of DOCX,
    XLSX, or TXT files.

    For Excel it returns sheet names and dimensions.

    For Word it returns paragraph count, table count,
    and headings.

    For TXT it returns basic file information.
    """

    result = inspect_file_impl(file_path)

    return json.dumps(
        result,
        indent=2,
        default=str,
    )


@tool
def search_file(
    file_path: str,
    query: str,
) -> str:
    """
    Search inside a DOCX, XLSX, or TXT file.

    Use this when you need to find a specific keyword,
    rule, product, field, or requirement.

    Do not use this as the primary extraction method
    when structured Excel data is required.
    """

    result = search_file_impl(
        file_path=file_path,
        query=query,
    )

    return json.dumps(
        result,
        indent=2,
        default=str,
    )


@tool
def extract_text(file_path: str) -> str:
    """
    Extract text from DOCX or TXT files.

    Use this when the review plan requires textual
    information from a Word or text file.
    """

    result = extract_text_impl(file_path)

    return json.dumps(
        result,
        indent=2,
        default=str,
    )


@tool
def extract_tables(file_path: str) -> str:
    """
    Extract structured tables from DOCX or XLSX.

    Use this when the review plan requires table data.
    """

    result = extract_tables_impl(file_path)

    return json.dumps(
        result,
        indent=2,
        default=str,
    )


@tool
def read_excel_range(
    file_path: str,
    sheet_name: str,
    cell_range: str,
) -> str:
    """
    Read a specific range from an Excel worksheet.

    Example:
        sheet_name = Inventory
        cell_range = A1:D50

    Prefer this over extracting an entire large workbook.
    """

    result = read_excel_range_impl(
        file_path=file_path,
        sheet_name=sheet_name,
        cell_range=cell_range,
    )

    return json.dumps(
        result,
        indent=2,
        default=str,
    )


@tool
def execute_review_step(
    step_description: str,
    file_paths,
) -> str:
    """
    Execute an approved extraction step from the review plan.

    This is the main high-level extraction tool.

    file_paths can be:
    - A JSON list string: '["input/inventory.xlsx"]'
    - A Python list: ["input/inventory.xlsx"]

    Example:
        step_description:
        "Extract current inventory and sales."

        file_paths:
        ["input/inventory.xlsx"]
    """

    try:
        # Handle both string (JSON) and list inputs
        if isinstance(file_paths, str):
            files = json.loads(file_paths)
        elif isinstance(file_paths, list):
            files = file_paths
        else:
            return json.dumps(
                {
                    "status": "error",
                    "error": "file_paths must be a list or JSON string.",
                }
            )

        if not isinstance(files, list):
            return json.dumps(
                {
                    "status": "error",
                    "error": "file_paths must be a list.",
                }
            )

    except (json.JSONDecodeError, TypeError) as e:
        return json.dumps(
            {
                "status": "error",
                "error": f"file_paths parsing error: {str(e)}",
            }
        )

    extracted = []

    for file_path in files:

        inspection = inspect_file_impl(file_path)

        if inspection.get("status") != "success":

            extracted.append(
                {
                    "file": file_path,
                    "status": "error",
                    "inspection": inspection,
                }
            )

            continue

        file_type = inspection.get(
            "file_type"
        )

        if file_type == "excel":

            result = extract_tables_impl(
                file_path
            )

        elif file_type == "word":

            result = {
                "text": extract_text_impl(
                    file_path
                ),
                "tables": extract_tables_impl(
                    file_path
                ),
            }

        elif file_type == "text":

            result = extract_text_impl(
                file_path
            )

        else:

            result = {
                "status": "error",
                "error": (
                    f"Unsupported file type: "
                    f"{file_type}"
                ),
            }

        extracted.append(
            {
                "file": file_path,
                "result": result,
            }
        )

    return json.dumps(
        {
            "status": "success",
            "step": step_description,
            "files": extracted,
        },
        indent=2,
        default=str,
    )


@tool
def validate_extracted_data(
    extracted_data: str,
    required_fields: str,
) -> str:
    """
    Validate extracted data against required fields.

    extracted_data:
        JSON string containing the extracted result.

    required_fields:
        JSON list of required field names.

    The tool checks whether required fields can be found
    in the extracted result.

    It does not invent missing information.
    """

    try:

        data = json.loads(extracted_data)

    except json.JSONDecodeError:

        return json.dumps(
            {
                "status": "error",
                "valid": False,
                "error": (
                    "extracted_data is not valid JSON."
                ),
            },
            indent=2,
        )

    try:

        fields = json.loads(required_fields)

    except json.JSONDecodeError:

        return json.dumps(
            {
                "status": "error",
                "valid": False,
                "error": (
                    "required_fields must be "
                    "a JSON list."
                ),
            },
            indent=2,
        )

    serialized = json.dumps(
        data,
        default=str,
    ).lower()

    found = []
    missing = []

    for field in fields:

        field_lower = str(field).lower()

        if field_lower in serialized:
            found.append(field)
        else:
            missing.append(field)

    valid = len(missing) == 0

    return json.dumps(
        {
            "status": "success",
            "valid": valid,
            "required_fields": fields,
            "found_fields": found,
            "missing_fields": missing,
            "message": (
                "All required fields were found."
                if valid
                else "Some required fields are missing."
            ),
        },
        indent=2,
    )

@tool
def calculator(expression: str) -> float:
    """
    General-purpose mathematical calculator for the review agent.

    Use this tool whenever an exact numerical calculation is
    required during a review.

    The agent must determine:
    - what needs to be calculated
    - which values should be used
    - the mathematical formula
    - the correct order of operations

    The agent must then convert that reasoning into a valid
    mathematical expression and provide the expression to this tool.

    The calculator performs ONLY arithmetic.
    It does not determine business rules, interpret policies,
    select data, or decide whether a review passes or fails.

    Supported operations include:
    - addition (+)
    - subtraction (-)
    - multiplication (*)
    - division (/)
    - percentages
    - powers (**)
    - parentheses

    Examples:
        "100 - 20 - 10 + 10"
        "25 * 10"
        "(500 * 15) / 100"
        "(89 - 80) / 80 * 100"
        "(100 + 50) * 0.14"

    Input must be a mathematical expression containing
    numerical values and supported mathematical operators.

    Return the exact numerical result.
    """
    return float(eval(expression))

TOOLS = [
    inspect_file,
    search_file,
    extract_text,
    extract_tables,
    read_excel_range,
    execute_review_step,
    validate_extracted_data,
    calculator,
]