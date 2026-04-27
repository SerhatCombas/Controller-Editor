from __future__ import annotations

from typing import TYPE_CHECKING

from src.shared.types.component import BaseComponent
from src.shared.types.domain import MECHANICAL_TRANSLATIONAL_DOMAIN
from src.shared.types.port import Port
from src.shared.types.variable import Variable

if TYPE_CHECKING:
    from src.shared.types.contribution import MatrixContribution
    from src.shared.types.state_contribution import StateContribution


class Mass(BaseComponent):
    def __init__(self, component_id: str, *, mass: float, name: str = "Mass") -> None:
        super().__init__(
            id=component_id,
            name=name,
            domain=MECHANICAL_TRANSLATIONAL_DOMAIN,
            ports=[
                Port(
                    id=f"{component_id}.port_a",
                    name="port_a",
                    domain=MECHANICAL_TRANSLATIONAL_DOMAIN,
                    component_id=component_id,
                    across_var=Variable(
                        name=f"v_{component_id}_a",
                        domain=MECHANICAL_TRANSLATIONAL_DOMAIN,
                        kind="across",
                    ),
                    through_var=Variable(
                        name=f"f_{component_id}_a",
                        domain=MECHANICAL_TRANSLATIONAL_DOMAIN,
                        kind="through",
                    ),
                ),
                Port(
                    id=f"{component_id}.reference_port",
                    name="reference_port",
                    domain=MECHANICAL_TRANSLATIONAL_DOMAIN,
                    component_id=component_id,
                    across_var=Variable(
                        name=f"v_{component_id}_ref",
                        domain=MECHANICAL_TRANSLATIONAL_DOMAIN,
                        kind="across",
                    ),
                    through_var=Variable(
                        name=f"f_{component_id}_ref",
                        domain=MECHANICAL_TRANSLATIONAL_DOMAIN,
                        kind="through",
                    ),
                ),
            ],
            parameters={"mass": mass},
            initial_conditions={"x": 0.0, "v": 0.0},
        )

    def get_states(self) -> list[str]:
        return [f"x_{self.id}", f"v_{self.id}"]

    def constitutive_equations(self) -> list[str]:
        m = self.parameters["mass"]
        return [
            f"d/dt x_{self.id} = v_{self.id}",
            f"v_{self.id} = v_{self.id}_a - v_{self.id}_ref",
            f"{m} * d/dt v_{self.id} = f_{self.id}_a - f_{self.id}_ref",
        ]

    # ------------------------------------------------------------------
    # Wave 1 polymorphic interface
    # ------------------------------------------------------------------

    def get_state_contribution(self) -> StateContribution:
        from src.shared.types.state_contribution import StateContribution
        return StateContribution(
            stores_inertial_energy=True,
            stores_potential_energy=False,
            state_kind="inertial",
            dof_count=1,
            owning_port_name="port_a",
        )

    def contribute_mass(self, node_index: dict[str, int]) -> list[MatrixContribution]:
        """Diagonal mass-matrix entry: M[i,i] += m."""
        import sympy
        from src.shared.types.contribution import MatrixContribution

        port = self.port("port_a")
        if port.node_id is None or port.node_id not in node_index:
            return []

        i = node_index[port.node_id]
        m_sym = sympy.Symbol(f"m_{self.id}")
        return [
            MatrixContribution(
                row=i,
                col=i,
                value=m_sym,
                component_id=self.id,
                contribution_kind="mass",
                connected_node_ids=(port.node_id,),
                physical_meaning=(
                    f"Inertial resistance of {self.name} (m={self.parameters['mass']} kg) at DOF {i}"
                ),
                equation_reference=f"M[{i},{i}] += m_{self.id}",
            )
        ]
