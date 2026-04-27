from __future__ import annotations

from dataclasses import dataclass

from src.shared.types.domain import Domain
from src.shared.types.variable import Variable


@dataclass(slots=True)
class Port:
    """A connection point on a component.

    New in T0.2
    -----------
    direction_hint : str | None
        MSL-derived port polarity/direction. Values depend on domain:
        - Electrical: ``'positive'`` / ``'negative'``  (MSL PositivePin / NegativePin)
        - Translational: ``'a'`` / ``'b'``  (MSL Flange_a / Flange_b)
        - Rotational: ``'a'`` / ``'b'``
        - Thermal: ``'a'`` / ``'b'``
        Default ``None`` keeps backward compatibility with existing components.

    visual_anchor : tuple[float, float] | None
        Normalized (x, y) position on the component SVG symbol where this
        port attaches.  Range 0.0–1.0 for both axes (origin = top-left).
        ``None`` means the UI should use a layout-engine default.
        Aligns with Component Visual Symbol Guidelines §6.
    """

    id: str
    name: str
    domain: Domain
    component_id: str
    node_id: str | None = None
    across_var: Variable | None = None
    through_var: Variable | None = None
    required: bool = True
    direction_hint: str | None = None
    visual_anchor: tuple[float, float] | None = None

    # -- connection ---------------------------------------------------------

    def connect_to(self, node_id: str) -> None:
        self.node_id = node_id

    # -- validation ---------------------------------------------------------

    def validate_compatibility(self, other: "Port") -> None:
        if self.domain.name != other.domain.name:
            raise ValueError(
                f"Incompatible port domains: {self.domain.name} cannot connect to {other.domain.name}"
            )

    # -- helpers ------------------------------------------------------------

    @property
    def is_positive(self) -> bool:
        """True if this port has positive/a-side polarity."""
        return self.direction_hint in ("positive", "a")

    @property
    def is_negative(self) -> bool:
        """True if this port has negative/b-side polarity."""
        return self.direction_hint in ("negative", "b")
