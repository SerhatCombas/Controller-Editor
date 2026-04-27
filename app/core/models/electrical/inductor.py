"""Inductor — v = L × di/dt.

MSL equivalent: Modelica.Electrical.Analog.Basic.Inductor
Pattern: OnePort pair (add_one_port_pair)
Bond-graph: I-element (stores inertial/kinetic energy)
Mechanical analog: Mass (L ↔ m)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.base.component import BaseComponent
from app.core.base.component_helpers import add_one_port_pair
from app.core.base.equation import SymbolicEquation, der

if TYPE_CHECKING:
    from app.core.base.state_contribution import StateContribution


class Inductor(BaseComponent):
    """Ideal inductor: v_diff = L × der(through).

    State variable: through (current through inductor).
    See SIGN_CONVENTION.md §3.1.
    """

    def __init__(
        self,
        component_id: str,
        *,
        L: float = 1e-3,
        name: str = "Inductor",
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
            parameters={"L": L},
            initial_conditions={"i": 0.0},
            category="passive",
            tags=("electrical", "inductor", "passive", "I-element", "energy-storage"),
        )

        self._setup = setup

    def symbolic_equations(self) -> list[SymbolicEquation]:
        s = self._setup.symbols
        L = self._sym("L")
        return self._setup.equations + [
            SymbolicEquation(
                lhs=s["v_diff"],
                rhs=L * der(s["through"]),
                provenance="inductor",
            ),
        ]

    def constitutive_equations(self) -> list[str]:
        L = self.parameters["L"]
        return [f"v_{self.id} = {L} * d/dt i_{self.id}"]

    def get_state_contribution(self) -> StateContribution:
        from app.core.base.state_contribution import StateContribution
        return StateContribution(
            stores_inertial_energy=True,
            stores_potential_energy=False,
            state_kind="inertial",
            dof_count=1,
            owning_port_name="port_a",
        )
