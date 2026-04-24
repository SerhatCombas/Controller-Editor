"""Probe dataclasses — Wave 3A update (P1: output_kind + quantity_key).

Two-level probe intent (Wave 3 decision):
  ``output_kind``   — coarse OutputKind enum: how the output is derived
  ``quantity_key``  — fine string: which physical quantity within that kind

Both fields are optional (default None / "") for full backward compatibility
with Wave 2 code that constructs probes without them.  New code (template
builders, UI) should set both explicitly.

Legacy field
────────────
``quantity`` (plain string, Wave 2) is kept unchanged and remains the primary
dispatch key inside ``OutputMapper.map()``.  ``output_kind`` is a typed
overlay that OutputMapper will prefer once all probes carry it (Wave 3B).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.symbolic.output_kind import OutputKind


@dataclass(slots=True)
class BaseProbe:
    id: str
    name: str
    quantity: str
    target_component_id: str | None = None
    target_node_id: str | None = None
    # Wave 3A — P1: typed output intent (optional for backward compat)
    output_kind: "OutputKind | None" = field(default=None)
    quantity_key: str = field(default="")

    def measurement_equation(self) -> str:
        target = self.target_component_id or self.target_node_id or "unknown"
        return f"{self.id} measures {self.quantity} at {target}"


@dataclass(slots=True)
class RelativeProbe(BaseProbe):
    reference_component_id: str | None = None

    def measurement_equation(self) -> str:
        return (
            f"{self.id} measures relative {self.quantity} between "
            f"{self.target_component_id} and {self.reference_component_id}"
        )
