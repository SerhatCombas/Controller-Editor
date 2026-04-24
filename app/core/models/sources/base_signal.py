from __future__ import annotations

from app.core.base.component import BaseComponent
from app.core.base.domain import MECHANICAL_TRANSLATIONAL_DOMAIN
from app.core.base.port import Port
from app.core.base.variable import Variable


class SignalSource(BaseComponent):
    def __init__(self, component_id: str, *, name: str) -> None:
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
                        name=f"v_{component_id}_out",
                        domain=MECHANICAL_TRANSLATIONAL_DOMAIN,
                        kind="across",
                    ),
                    through_var=Variable(
                        name=f"f_{component_id}_out",
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
            metadata={"role": "source", "source_kind": "displacement"},
        )

    def displacement_output(self, _time: float) -> float:
        raise NotImplementedError

    def velocity_output(self, _time: float) -> float:
        raise NotImplementedError
