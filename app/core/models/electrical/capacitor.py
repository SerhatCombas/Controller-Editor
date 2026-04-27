"""Capacitor — i = C × dv/dt.

MSL equivalent: Modelica.Electrical.Analog.Basic.Capacitor
Pattern: OnePort pair (add_one_port_pair)
Bond-graph: C-element (stores potential energy)
Mechanical analog: Spring (C ↔ 1/k)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.base.component import BaseComponent
from app.core.base.component_helpers import add_one_port_pair
from app.core.base.equation import SymbolicEquation, der

if TYPE_CHECKING:
    from app.core.base.state_contribution import StateContribution


class Capacitor(BaseComponent):
    """Ideal capacitor: through = C × der(v_diff).

    State variable: v_diff (voltage across capacitor).
    See SIGN_CONVENTION.md §3.1.
    """

    def __init__(
        self,
        component_id: str,
        *,
        C: float = 1e-6,
        name: str = "Capacitor",
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
            parameters={"C": C},
            initial_conditions={"v": 0.0},
            category="passive",
            tags=("electrical", "capacitor", "passive", "C-element", "energy-storage"),
        )

        self._setup = setup

    def symbolic_equations(self) -> list[SymbolicEquation]:
        s = self._setup.symbols
        C = self._sym("C")
        return self._setup.equations + [
            SymbolicEquation(
                lhs=s["through"],
                rhs=C * der(s["v_diff"]),
                provenance="capacitor",
            ),
        ]

    def constitutive_equations(self) -> list[str]:
        C = self.parameters["C"]
        return [f"i_{self.id} = {C} * d/dt v_{self.id}"]

    def get_state_contribution(self) -> StateContribution:
        from app.core.base.state_contribution import StateContribution
        return StateContribution(
            stores_inertial_energy=False,
            stores_potential_energy=True,
            state_kind="potential",
            dof_count=1,
            owning_port_name="port_a",
        )
