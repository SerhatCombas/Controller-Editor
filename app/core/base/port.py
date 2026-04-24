from __future__ import annotations

from dataclasses import dataclass

from app.core.base.domain import Domain
from app.core.base.variable import Variable


@dataclass(slots=True)
class Port:
    id: str
    name: str
    domain: Domain
    component_id: str
    node_id: str | None = None
    across_var: Variable | None = None
    through_var: Variable | None = None
    required: bool = True

    def connect_to(self, node_id: str) -> None:
        self.node_id = node_id

    def validate_compatibility(self, other: "Port") -> None:
        if self.domain.name != other.domain.name:
            raise ValueError(
                f"Incompatible port domains: {self.domain.name} cannot connect to {other.domain.name}"
            )
