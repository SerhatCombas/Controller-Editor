from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Connection:
    id: str
    port_a: str
    port_b: str
    label: str | None = None
