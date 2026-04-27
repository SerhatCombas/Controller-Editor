from __future__ import annotations

from dataclasses import dataclass, field

from src.shared.types.domain import Domain
from src.shared.types.port import Port


@dataclass(slots=True)
class Node:
    id: str
    domain: Domain
    port_ids: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)

    def attach_port(self, port_id: str) -> None:
        if port_id not in self.port_ids:
            self.port_ids.append(port_id)

    def across_constraint(self) -> str:
        return f"All connected {self.domain.across_variable} variables at node {self.id} are equal."

    def through_balance_constraint(self) -> str:
        return (
            f"Sum of {self.domain.through_variable} variables at node {self.id} equals zero."
        )

    def explicit_across_equations(self, ports: list[Port]) -> list[str]:
        if len(ports) < 2:
            return []
        anchor = ports[0]
        equations: list[str] = []
        for port in ports[1:]:
            if anchor.across_var is not None and port.across_var is not None:
                equations.append(f"{anchor.across_var.name} - {port.across_var.name} = 0")
        return equations

    def explicit_through_equation(self, ports: list[Port]) -> str | None:
        symbols = [port.through_var.name for port in ports if port.through_var is not None]
        if not symbols:
            return None
        return " + ".join(symbols) + " = 0"
