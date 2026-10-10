
import ast
import operator
from typing import Union

from langchain_core.tools import tool


# Allowed mathematical operators
OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}


def evaluate_expression(node):
    """
    Safely evaluate a mathematical expression.
    Only numbers and basic arithmetic operators are allowed.
    """

    # Number
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value

        raise ValueError("Only numbers are allowed.")

    # Unary + or -
    if isinstance(node, ast.UnaryOp):
        value = evaluate_expression(node.operand)

        if isinstance(node.op, ast.USub):
            return -value

        if isinstance(node.op, ast.UAdd):
            return value

        raise ValueError("Unsupported unary operator.")

    # Binary operation
    if isinstance(node, ast.BinOp):

        left = evaluate_expression(node.left)
        right = evaluate_expression(node.right)

        operation = OPERATORS.get(type(node.op))

        if operation is None:
            raise ValueError("Unsupported mathematical operator.")

        if isinstance(node.op, ast.Div) and right == 0:
            raise ValueError("Division by zero.")

        return operation(left, right)

    raise ValueError(
        "Invalid expression. Only mathematical expressions are allowed."
    )


@tool
def calculator(expression: str) -> Union[int, float]:
    """
    General-purpose calculator.

    Evaluate a mathematical expression containing numbers
    and basic arithmetic operators.

    Supported:
        + addition
        - subtraction
        * multiplication
        / division
        % modulo
        ** power
        parentheses

    Examples:
        calculator("100 - 20 - 10 + 10")
        calculator("50 * 20")
        calculator("(100 + 50) * 0.14")
        calculator("500 + 500 * 0.14")

    The agent must determine the correct mathematical
    expression from the review process and policy.
    """

    try:
        tree = ast.parse(expression, mode="eval")

        result = evaluate_expression(tree.body)

        return result

    except Exception as e:
        raise ValueError(
            f"Could not calculate expression '{expression}': {e}"
        )

