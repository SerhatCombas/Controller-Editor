from __future__ import annotations

from src.shared.types.component import BaseComponent
from src.shared.types.domain import MECHANICAL_TRANSLATIONAL_DOMAIN
from src.shared.types.port import Port
from src.shared.types.variable import Variable


class MechanicalGround(BaseComponent):
    def __init__(self, component_id: str, *, name: str = "Ground") -> None:
        super().__init__(
            id=component_id,
            name=name,
            domain=MECHANICAL_TRANSLATIONAL_DOMAIN,
            ports=[
                Port(
                    id=f"{component_id}.port",
                    name="port",
                    domain=MECHANICAL_TRANSLATIONAL_DOMAIN,
                    component_id=component_id,
                    across_var=Variable(
                        name=f"v_{component_id}",
                        domain=MECHANICAL_TRANSLATIONAL_DOMAIN,
                        kind="across",
                    ),
                    through_var=Variable(
                        name=f"f_{component_id}",
                        domain=MECHANICAL_TRANSLATIONAL_DOMAIN,
                        kind="through",
                    ),
                )
            ],
            metadata={"role": "reference"},
        )

    def constitutive_equations(self) -> list[str]:
        return [f"v_{self.id} = 0"]
