from __future__ import annotations

import re

try:
    import sympy as sp
except ModuleNotFoundError:
    sp = None


class SympyAdapter:
    """Incremental bridge from debug strings to structural sympy equations."""

    DERIVATIVE_PATTERN = re.compile(r"d/dt\s+([A-Za-z_][A-Za-z0-9_]*)")
    TOKEN_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
    FUNCTION_CALL_PATTERN = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(")

    def __init__(self) -> None:
        self.available = sp is not None

    def parse_equation(self, equation_text: str) -> tuple[str, str, object | None]:
        if "=" not in equation_text:
            return equation_text.strip(), "0", None

        lhs_text, rhs_text = [part.strip() for part in equation_text.split("=", 1)]
        if not self.available:
            return lhs_text, rhs_text, None

        local_dict = {"Heaviside": sp.Heaviside}
        try:
            lhs_expr = self._to_sympy_expr(lhs_text, local_dict)
            rhs_expr = self._to_sympy_expr(rhs_text, local_dict)
            return lhs_text, rhs_text, sp.Eq(lhs_expr, rhs_expr)
        except (ValueError, TypeError, SyntaxError):
            # Non-parseable pseudo-equations (e.g. stub descriptions like
            # "filtered_white_noise(seed=7)") fall through with sympy_expression=None.
            # Callers that need structural sympy must check for None.
            return lhs_text, rhs_text, None

    def extract_tokens(self, text: str) -> list[str]:
        return sorted(set(self.TOKEN_PATTERN.findall(text)))

    def extract_derivatives(self, text: str) -> list[str]:
        return sorted(set(self.DERIVATIVE_PATTERN.findall(text)))

    def _to_sympy_expr(self, text: str, local_dict: dict[str, object]):
        transformed = self.DERIVATIVE_PATTERN.sub(r"ddt_\1", text)
        transformed = transformed.replace("^", "**")
        transformed = transformed.replace("step(", "Heaviside(")

        # Tokens used as function calls (name followed by '(') must be declared
        # as sp.Function, not sp.Symbol, otherwise sympify raises TypeError.
        function_tokens = set(self.FUNCTION_CALL_PATTERN.findall(transformed))

        for token in sorted(set(self.TOKEN_PATTERN.findall(transformed))):
            if token in {"Heaviside"}:
                continue
            if token in local_dict:
                continue
            if token in function_tokens:
                local_dict[token] = sp.Function(token)
            else:
                local_dict[token] = sp.Symbol(token)

        return sp.sympify(transformed, locals=local_dict)
