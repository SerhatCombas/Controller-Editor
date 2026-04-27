"""Matrix contribution records used by the polymorphic reducer.

This module is part of Wave 1. Components produce instances of
`MatrixContribution` from their `contribute_mass`, `contribute_damping`,
`contribute_stiffness`, and related methods. The polymorphic reducer
consumes those lists and writes them into the reduced ODE matrices.

The dataclass intentionally carries provenance metadata (component_id,
contribution_kind, connected_node_ids, physical_meaning) beyond the raw
numeric value, because:

1. Parity debugging across legacy and polymorphic reducers benefits from
   being able to attribute a specific cell delta to a specific component.
2. The future symbolic transfer function builder needs to know which
   physical parameter a coefficient originated from.
3. The UI can eventually surface "which component contributed this
   coefficient?" when a user hovers over a matrix cell.

Keeping the provenance fields from day one prevents a lossy schema that
would otherwise force a painful retro-fit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ContributionKind = Literal["mass", "damping", "stiffness", "input_B"]


@dataclass(frozen=True, slots=True)
class MatrixContribution:
    """A single additive contribution from a component to one matrix cell.

    Attributes:
        row: Zero-based row index in the target matrix.
        col: Zero-based column index in the target matrix.
        value: Numeric coefficient to add into the cell.
        component_id: Identifier of the component that produced this entry.
        contribution_kind: Which matrix family this entry belongs to
            ("mass", "damping", "stiffness", or "input_B").
        connected_node_ids: Node ids of the local topology that generated
            this contribution. For a Spring linking nodes (na, nb) this is
            ("na", "nb"); for a Mass at node n it is ("n",).
        physical_meaning: Short human-readable explanation used for
            debugging, parity reports, and UI tooltips.
        equation_reference: Optional pointer back to the constitutive
            equation text or identifier that produced this entry.
    """

    row: int
    col: int
    value: float
    component_id: str
    contribution_kind: ContributionKind
    connected_node_ids: tuple[str, ...] = ()
    physical_meaning: str = ""
    equation_reference: str | None = None
