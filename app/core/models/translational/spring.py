"""Translational Spring — linear elastic element.

MSL equivalent: Modelica.Mechanics.Translational.Components.Spring
Pattern: 2-port OnePort pair (add_one_port_pair)

Equation: f = k * s_rel
where s_rel = flange_b.s - flange_a.s (relative displacement)
"""

from __future__ import annotations

from app.core.base.component import BaseComponent
from app.core.base.component_helpers import add_one_port_pair
from app.core.base.equation import SymbolicEquation
from app.core.base.state_contribution import StateContribution


class TranslationalSpring(BaseComponent):
    """Linear spring: through = k * v_diff.

    With translational sign convention (SIGN_CONVENTION.md §3.1):
      v_diff = s_b - s_a  (relative displacement, MSL: s_rel)
      through = f_b       (force at flange_b)
      f_a + f_b = 0       (KCL: action-reaction)

    Constitutive law: f = k * s_rel
    """

    def __init__(
        self,
        component_id: str,
        *,
        k: float,
        name: str = "Spring",
    ) -> None:
        setup = add_one_port_pair(
            component_id=component_id,
            domain_name="translational",
            port_a_name="flange_a",
            port_b_name="flange_b",
            visual_anchor_a=(0.0, 0.5),
            visual_anchor_b=(1.0, 0.5),
        )

        super().__init__(
            id=component_id,
            name=name,
            domain=setup.ports[0].domain,
            ports=setup.ports,
            parameters={"k": k},
            category="passive",
            tags=("translational", "spring", "elastic"),
        )

        self._setup = setup

    def get_state_contribution(self) -> StateContribution:
        return StateContribution(
            stores_inertial_energy=False,
            stores_potential_energy=True,
            state_kind="potential",
            dof_count=1,
            owning_port_name="flange_a",
        )

    def symbolic_equations(self) -> list[SymbolicEquation]:
        v_diff = self._setup.symbols["v_diff"]
        through = self._setup.symbols["through"]
        k_sym = self._sym("k")

        return self._setup.equations + [
            SymbolicEquation(
                lhs=through,
                rhs=k_sym * v_diff,
                provenance="spring_law",
            ),
        ]

    def constitutive_equations(self) -> list[str]:
        k = self.parameters["k"]
        return [
            f"f_{self.id}_flange_a = {k} * (s_{self.id}_flange_b - s_{self.id}_flange_a)",
            f"f_{self.id}_flange_a + f_{self.id}_flange_b = 0",
        ]
