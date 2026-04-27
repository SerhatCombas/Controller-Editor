from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class EquationRecord:
    display_text: str
    lhs_text: str
    rhs_text: str
    equation_type: str
    sympy_expression: object | None = None
    involved_variables: list[str] = field(default_factory=list)
    involved_parameters: list[str] = field(default_factory=list)
    derivative_variables: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)
