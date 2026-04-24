from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.base.component import BaseComponent
from app.core.base.domain import MECHANICAL_TRANSLATIONAL_DOMAIN
from app.core.base.port import Port
from app.core.base.variable import Variable

if TYPE_CHECKING:
    from app.core.base.contribution import MatrixContribution
    from app.core.base.state_contribution import StateContribution


class Spring(BaseComponent):
    def __init__(self, component_id: str, *, stiffness: float, name: str = "Spring") -> None:
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
                    id=f"{component_id}.port_b",
                    name="port_b",
                    domain=MECHANICAL_TRANSLATIONAL_DOMAIN,
                    component_id=component_id,
                    across_var=Variable(
                        name=f"v_{component_id}_b",
                        domain=MECHANICAL_TRANSLATIONAL_DOMAIN,
                        kind="across",
                    ),
                    through_var=Variable(
                        name=f"f_{component_id}_b",
                        domain=MECHANICAL_TRANSLATIONAL_DOMAIN,
                        kind="through",
                    ),
                ),
            ],
            parameters={"stiffness": stiffness},
            initial_conditions={"x_rel": 0.0},
        )

    def constitutive_equations(self) -> list[str]:
        k = self.parameters["stiffness"]
        return [
            f"d/dt x_rel_{self.id} = v_{self.id}_a - v_{self.id}_b",
            f"f_{self.id}_a = {k} * x_rel_{self.id}",
            f"f_{self.id}_a + f_{self.id}_b = 0",
        ]

    # ------------------------------------------------------------------
    # Wave 1 polymorphic interface
    # ------------------------------------------------------------------

    def get_state_contribution(self) -> StateContribution:
        """Spring stores elastic (potential) energy via relative displacement state."""
        from app.core.base.state_contribution import StateContribution
        return StateContribution(
            stores_inertial_energy=False,
            stores_potential_energy=True,
            state_kind="potential",
            dof_count=1,
            owning_port_name="port_a",
        )

    def contribute_stiffness(self, node_index: dict[str, int]) -> list[MatrixContribution]:
        """Graph-Laplacian stiffness entries: K[i,i]+=k, K[j,j]+=k, K[i,j]-=k, K[j,i]-=k.

        Ground nodes (absent from node_index) are eliminated automatically:
        only entries whose row *and* col are both active DOFs are emitted.
        """
        import sympy
        from app.core.base.contribution import MatrixContribution

        port_a = self.port("port_a")
        port_b = self.port("port_b")

        i = node_index.get(port_a.node_id) if port_a.node_id else None
        j = node_index.get(port_b.node_id) if port_b.node_id else None

        k_sym = sympy.Symbol(f"k_{self.id}")
        k_val = self.parameters["stiffness"]
        node_ids = tuple(n for n in (port_a.node_id, port_b.node_id) if n is not None)
        contribs: list[MatrixContribution] = []

        if i is not None:
            contribs.append(MatrixContribution(
                row=i, col=i, value=k_sym,
                component_id=self.id,
                contribution_kind="stiffness",
                connected_node_ids=node_ids,
                physical_meaning=(
                    f"Self-stiffness of {self.name} (k={k_val} N/m) at DOF {i}"
                ),
                equation_reference=f"K[{i},{i}] += k_{self.id}",
            ))
        if j is not None:
            contribs.append(MatrixContribution(
                row=j, col=j, value=k_sym,
                component_id=self.id,
                contribution_kind="stiffness",
                connected_node_ids=node_ids,
                physical_meaning=(
                    f"Self-stiffness of {self.name} (k={k_val} N/m) at DOF {j}"
                ),
                equation_reference=f"K[{j},{j}] += k_{self.id}",
            ))
        if i is not None and j is not None:
            contribs.append(MatrixContribution(
                row=i, col=j, value=-k_sym,
                component_id=self.id,
                contribution_kind="stiffness",
                connected_node_ids=node_ids,
                physical_meaning=(
                    f"Coupling stiffness of {self.name} between DOF {i} and DOF {j}"
                ),
                equation_reference=f"K[{i},{j}] -= k_{self.id}",
            ))
            contribs.append(MatrixContribution(
                row=j, col=i, value=-k_sym,
                component_id=self.id,
                contribution_kind="stiffness",
                connected_node_ids=node_ids,
                physical_meaning=(
                    f"Coupling stiffness of {self.name} between DOF {j} and DOF {i}"
                ),
                equation_reference=f"K[{j},{i}] -= k_{self.id}",
            ))

        return contribs
