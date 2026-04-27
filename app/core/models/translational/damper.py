"""Translational Damper — linear viscous element.

MSL equivalent: Modelica.Mechanics.Translational.Components.Damper
Pattern: 2-port OnePort pair (add_one_port_pair)

Equation: f = d * v_rel = d * der(s_rel)
where s_rel = flange_b.s - flange_a.s (relative displacement)
      v_rel = der(s_rel) (relative velocity)
"""

from __future__ import annotations

from app.core.base.component import BaseComponent
from app.core.base.component_helpers import add_one_port_pair
from app.core.base.equation import SymbolicEquation, der


class TranslationalDamper(BaseComponent):
    """Linear damper: through = d * der(v_diff).

    With translational sign convention (SIGN_CONVENTION.md §3.1):
      v_diff = s_b - s_a  (relative displacement)
      through = f_b       (force at flange_b)
      f_a + f_b = 0       (KCL: action-reaction)

    Constitutive law: f = d * der(s_rel) = d * v_rel

    Note: This component does NOT introduce a state variable.
    The der(v_diff) appears in the equation but v_diff is NOT
    the state — it's an algebraic variable that gets eliminated.
    The state comes from whatever stores energy (Spring → position,
    Mass → velocity).
    """

    def __init__(
        self,
        component_id: str,
        *,
        d: float,
        name: str = "Damper",
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
            parameters={"d": d},
            category="passive",
            tags=("translational", "damper", "dissipative"),
        )

        self._setup = setup

    def symbolic_equations(self) -> list[SymbolicEquation]:
        v_diff = self._setup.symbols["v_diff"]
        through = self._setup.symbols["through"]
        d_sym = self._sym("d")

        return self._setup.equations + [
            SymbolicEquation(
                lhs=through,
                rhs=d_sym * der(v_diff),
                provenance="damper_law",
            ),
        ]

    def constitutive_equations(self) -> list[str]:
        d = self.parameters["d"]
        return [
            f"f_{self.id}_flange_a = {d} * d/dt (s_{self.id}_flange_b - s_{self.id}_flange_a)",
            f"f_{self.id}_flange_a + f_{self.id}_flange_b = 0",
        ]
