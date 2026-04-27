"""Translational Mass — inertial element (Newton's second law).

MSL equivalent: Modelica.Mechanics.Translational.Components.Mass
Pattern: 2-port rigid pair (add_rigid_pair) — NO KCL

Equations:
    flange_a.s = s        (rigid coupling)
    flange_b.s = s        (rigid coupling)
    v = der(s)            (velocity definition)
    m * der(v) = f_a + f_b   (Newton's second law)

Two state variables: s (position) and v (velocity).
"""

from __future__ import annotations

from app.core.base.component import BaseComponent
from app.core.base.component_helpers import add_rigid_pair
from app.core.base.equation import SymbolicEquation, der
from app.core.base.state_contribution import StateContribution

import sympy


class TranslationalMass(BaseComponent):
    """Sliding mass: m * a = sum(forces).

    Uses add_rigid_pair → both flanges share the same position (v_center).
    Mass writes Newton's law itself — no KCL from the skeleton.

    States: v_center (position s) and velocity (v = der(s)).
    """

    def __init__(
        self,
        component_id: str,
        *,
        m: float,
        name: str = "Mass",
    ) -> None:
        setup = add_rigid_pair(
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
            parameters={"m": m},
            category="passive",
            tags=("translational", "mass", "inertial"),
        )

        self._setup = setup

    def get_state_contribution(self) -> StateContribution:
        return StateContribution(
            stores_inertial_energy=True,
            stores_potential_energy=False,
            state_kind="inertial",
            dof_count=1,
            owning_port_name="flange_a",
        )

    def symbolic_equations(self) -> list[SymbolicEquation]:
        v_center = self._setup.symbols["v_center"]
        f_a = self._setup.symbols["f_a"]
        f_b = self._setup.symbols["f_b"]
        m_sym = self._sym("m")

        # Velocity state variable
        velocity = sympy.Symbol(f"{self.id}__velocity", real=True)

        return self._setup.equations + [
            # Velocity definition: der(s) = v
            SymbolicEquation(
                lhs=der(v_center),
                rhs=velocity,
                provenance="velocity_def",
            ),
            # Newton's second law: m * der(v) = f_a + f_b
            SymbolicEquation(
                lhs=m_sym * der(velocity),
                rhs=f_a + f_b,
                provenance="newton_second_law",
            ),
        ]

    def constitutive_equations(self) -> list[str]:
        m = self.parameters["m"]
        return [
            f"d/dt s_{self.id} = v_{self.id}",
            f"{m} * d/dt v_{self.id} = f_{self.id}_flange_a + f_{self.id}_flange_b",
        ]
