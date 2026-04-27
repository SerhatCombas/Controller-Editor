"""Translational Fixed — sets position reference to zero.

MSL equivalent: Modelica.Mechanics.Translational.Components.Fixed
Pattern: single-port reference (add_one_port)
"""

from __future__ import annotations

from app.core.base.component import BaseComponent
from app.core.base.component_helpers import add_one_port
from app.core.base.equation import SymbolicEquation

import sympy


class TranslationalFixed(BaseComponent):
    """Translational ground (fixed wall): s = 0 at flange.

    See SIGN_CONVENTION.md §3.4.
    """

    def __init__(self, component_id: str, *, name: str = "Fixed") -> None:
        setup = add_one_port(
            component_id=component_id,
            domain_name="translational",
            port_name="flange",
            direction_hint="a",
            visual_anchor=(0.5, 0.5),
        )

        super().__init__(
            id=component_id,
            name=name,
            domain=setup.ports[0].domain,
            ports=setup.ports,
            category="reference",
            tags=("translational", "fixed", "reference"),
        )

        self._setup = setup

    def symbolic_equations(self) -> list[SymbolicEquation]:
        s = self._setup.symbols["across"]
        return [
            SymbolicEquation(
                lhs=s,
                rhs=sympy.Integer(0),
                provenance="fixed_reference",
            ),
        ]

    def constitutive_equations(self) -> list[str]:
        return [f"s_{self.id}_flange = 0"]
