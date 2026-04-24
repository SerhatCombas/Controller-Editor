from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.base.component import BaseComponent
from app.core.base.domain import MECHANICAL_TRANSLATIONAL_DOMAIN
from app.core.base.port import Port
from app.core.base.variable import Variable

if TYPE_CHECKING:
    from app.core.base.contribution import MatrixContribution


class Damper(BaseComponent):
    def __init__(self, component_id: str, *, damping: float, name: str = "Damper") -> None:
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
            parameters={"damping": damping},
        )

    def constitutive_equations(self) -> list[str]:
        d = self.parameters["damping"]
        return [
            f"f_{self.id}_a = {d} * (v_{self.id}_a - v_{self.id}_b)",
            f"f_{self.id}_a + f_{self.id}_b = 0",
        ]

    # ------------------------------------------------------------------
    # Wave 1 polymorphic interface
    # ------------------------------------------------------------------

    # Damper is purely dissipative — no energy storage, no state contribution.
    # get_state_contribution() returns None (inherited BaseComponent default).

    def contribute_damping(self, node_index: dict[str, int]) -> list[MatrixContribution]:
        """Graph-Laplacian damping entries: D[i,i]+=d, D[j,j]+=d, D[i,j]-=d, D[j,i]-=d.

        Ground nodes (absent from node_index) are eliminated automatically.
        """
        import sympy
        from app.core.base.contribution import MatrixContribution

        port_a = self.port("port_a")
        port_b = self.port("port_b")

        i = node_index.get(port_a.node_id) if port_a.node_id else None
        j = node_index.get(port_b.node_id) if port_b.node_id else None

        d_sym = sympy.Symbol(f"d_{self.id}")
        d_val = self.parameters["damping"]
        node_ids = tuple(n for n in (port_a.node_id, port_b.node_id) if n is not None)
        contribs: list[MatrixContribution] = []

        if i is not None:
            contribs.append(MatrixContribution(
                row=i, col=i, value=d_sym,
                component_id=self.id,
                contribution_kind="damping",
                connected_node_ids=node_ids,
                physical_meaning=(
                    f"Self-damping of {self.name} (d={d_val} N·s/m) at DOF {i}"
                ),
                equation_reference=f"D[{i},{i}] += d_{self.id}",
            ))
        if j is not None:
            contribs.append(MatrixContribution(
                row=j, col=j, value=d_sym,
                component_id=self.id,
                contribution_kind="damping",
                connected_node_ids=node_ids,
                physical_meaning=(
                    f"Self-damping of {self.name} (d={d_val} N·s/m) at DOF {j}"
                ),
                equation_reference=f"D[{j},{j}] += d_{self.id}",
            ))
        if i is not None and j is not None:
            contribs.append(MatrixContribution(
                row=i, col=j, value=-d_sym,
                component_id=self.id,
                contribution_kind="damping",
                connected_node_ids=node_ids,
                physical_meaning=(
                    f"Coupling damping of {self.name} between DOF {i} and DOF {j}"
                ),
                equation_reference=f"D[{i},{j}] -= d_{self.id}",
            ))
            contribs.append(MatrixContribution(
                row=j, col=i, value=-d_sym,
                component_id=self.id,
                contribution_kind="damping",
                connected_node_ids=node_ids,
                physical_meaning=(
                    f"Coupling damping of {self.name} between DOF {j} and DOF {i}"
                ),
                equation_reference=f"D[{j},{i}] -= d_{self.id}",
            ))

        return contribs
