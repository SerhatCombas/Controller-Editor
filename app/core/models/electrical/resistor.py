"""Resistor — Ohm's law: v = R × i.

MSL equivalent: Modelica.Electrical.Analog.Basic.Resistor
Pattern: OnePort pair (add_one_port_pair)
Bond-graph: R-element
"""

from __future__ import annotations

from app.core.base.component import BaseComponent
from app.core.base.component_helpers import add_one_port_pair
from app.core.base.equation import SymbolicEquation


class Resistor(BaseComponent):
    """Ideal resistor: v_diff = R × through.

    See SIGN_CONVENTION.md §3.1.
    """

    def __init__(
        self,
        component_id: str,
        *,
        R: float = 1.0,
        name: str = "Resistor",
    ) -> None:
        setup = add_one_port_pair(
            component_id=component_id,
            domain_name="electrical",
            visual_anchor_a=(0.0, 0.5),
            visual_anchor_b=(1.0, 0.5),
        )

        super().__init__(
            id=component_id,
            name=name,
            domain=setup.ports[0].domain,
            ports=setup.ports,
            parameters={"R": R},
            category="passive",
            tags=("electrical", "resistor", "passive", "R-element"),
        )

        self._setup = setup

    def symbolic_equations(self) -> list[SymbolicEquation]:
        s = self._setup.symbols
        R = self._sym("R")
        return self._setup.equations + [
            SymbolicEquation(
                lhs=s["v_diff"],
                rhs=R * s["through"],
                provenance="Ohm",
            ),
        ]

    def constitutive_equations(self) -> list[str]:
        R = self.parameters["R"]
        return [f"v_{self.id} = {R} * i_{self.id}"]
