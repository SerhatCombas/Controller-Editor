"""Electrical Ground — sets voltage reference to zero.

MSL equivalent: Modelica.Electrical.Analog.Basic.Ground
Pattern: single-port reference (add_one_port)
"""

from __future__ import annotations

from src.shared.types.component import BaseComponent
from src.shared.utils.component_helpers import add_one_port
from src.shared.types.equation import SymbolicEquation

import sympy


class ElectricalGround(BaseComponent):
    """Electrical ground: v = 0 at port p.

    See SIGN_CONVENTION.md §3.4.
    """

    def __init__(self, component_id: str, *, name: str = "Ground") -> None:
        setup = add_one_port(
            component_id=component_id,
            domain_name="electrical",
            port_name="p",
            direction_hint="positive",
            visual_anchor=(0.5, 0.0),
        )

        super().__init__(
            id=component_id,
            name=name,
            domain=setup.ports[0].domain,
            ports=setup.ports,
            category="reference",
            tags=("electrical", "ground", "reference"),
        )

        self._setup = setup

    def symbolic_equations(self) -> list[SymbolicEquation]:
        v = self._setup.symbols["across"]
        return [
            SymbolicEquation(
                lhs=v,
                rhs=sympy.Integer(0),
                provenance="ground_reference",
            ),
        ]

    def constitutive_equations(self) -> list[str]:
        return [f"v_{self.id}_p = 0"]
