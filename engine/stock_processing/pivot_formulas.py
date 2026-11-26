"""Evaluate the arithmetic subset of PivotTable calculated-field formulas."""

from __future__ import annotations

import re

_NUMBER = re.compile(r"\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


class PivotFormulaError(ValueError):
    """Raised for calculated fields outside the supported arithmetic."""


def _tokens(formula: str, names: list[str]):
    ordered = sorted(names, key=len, reverse=True)
    position = 0
    while position < len(formula):
        character = formula[position]
        if character.isspace():
            position += 1
        elif character in "+-*/()":
            yield character, character
            position += 1
        elif character == "'":
            end = formula.find("'", position + 1)
            name = formula[position + 1 : end]
            if end < 0 or name not in names:
                raise PivotFormulaError(f"Unknown field in calculated field: {formula}")
            yield "field", name
            position = end + 1
        else:
            name = next((item for item in ordered if formula.startswith(item, position)), None)
            number = _NUMBER.match(formula, position)
            if name is not None and (number is None or len(name) > len(number[0])):
                yield "field", name
                position += len(name)
            elif number:
                yield "number", float(number[0])
                position = number.end()
            else:
                raise PivotFormulaError(
                    f"Unsupported calculated field '{formula}'; only + - * / and parentheses are supported."
                )


def evaluate(formula: str, names: list[str], resolve):
    """Return the result, or ``None`` when Excel would show a division error."""
    tokens = list(_tokens(formula.lstrip("="), names))
    position = 0

    def peek():
        return tokens[position][0] if position < len(tokens) else None

    def take():
        nonlocal position
        if position >= len(tokens):
            raise PivotFormulaError(f"Incomplete calculated field: {formula}")
        position += 1
        return tokens[position - 1]

    def factor():
        kind, value = take()
        if kind in "+-":
            result = factor()
            return -result if kind == "-" else result
        if kind == "(":
            result = expression()
            if take()[0] != ")":
                raise PivotFormulaError(f"Unbalanced calculated field: {formula}")
            return result
        if kind == "field":
            resolved = resolve(value)
            if resolved is None:
                raise ZeroDivisionError
            return resolved
        if kind == "number":
            return value
        raise PivotFormulaError(f"Unsupported calculated field: {formula}")

    def term():
        result = factor()
        while peek() in ("*", "/"):
            result = result * factor() if take()[0] == "*" else result / factor()
        return result

    def expression():
        result = term()
        while peek() in ("+", "-"):
            result = result + term() if take()[0] == "+" else result - term()
        return result

    try:
        result = expression()
    except ZeroDivisionError:
        return None
    if position != len(tokens):
        raise PivotFormulaError(f"Unsupported calculated field: {formula}")
    return result
