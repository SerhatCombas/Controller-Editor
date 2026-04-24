"""ReducerParityReport — structured output of the Wave 1 reducer parity harness.

This dataclass is returned by ReducerParityHarness.compare() and records
whether the legacy DAEReducer and the PolymorphicDAEReducer agree on M / D / K
and the first-order A / B matrices for a given system graph.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class MatrixParity:
    """Parity result for a single named matrix.

    Attributes:
        name: Matrix name (e.g. "M", "D", "K", "A", "B").
        shape_legacy: Tuple (rows, cols) for the legacy reducer output.
        shape_poly: Tuple (rows, cols) for the polymorphic reducer output.
        shapes_match: True if both matrices have identical dimensions.
        max_abs_error: Maximum absolute element-wise error. ``float('inf')``
            if shapes differ. 0.0 for an empty / zero-dimension matrix.
        within_tolerance: True if ``max_abs_error <= tolerance``.
        tolerance: The tolerance value used in the comparison.
    """

    name: str
    shape_legacy: tuple[int, int]
    shape_poly: tuple[int, int]
    shapes_match: bool
    max_abs_error: float
    within_tolerance: bool
    tolerance: float


@dataclass
class ReducerParityReport:
    """Full parity report comparing DAEReducer vs PolymorphicDAEReducer.

    Produced by ``ReducerParityHarness.compare()``; consumed by logging,
    the shadow-mode CI gate, and the fuzz parity test (Commit 8).

    Attributes:
        graph_id: Optional identifier for the graph under test.
        parity_mode: The ``ParityMode`` that was active during this comparison.
        matrix_parities: Ordered list of per-matrix parity results.
        state_variables_match: True if both reducers agree on state variable names.
        legacy_state_variables: State variable list from the legacy reducer.
        poly_state_variables: State variable list from the polymorphic reducer.
        node_order_length_match: True if both reducers found the same DOF count.
        all_within_tolerance: True only if *every* matrix parity passes.
        issues: Human-readable strings describing any divergences.
        metadata: Arbitrary extra diagnostic info.
    """

    graph_id: str = ""
    parity_mode: str = "off"
    matrix_parities: list[MatrixParity] = field(default_factory=list)
    state_variables_match: bool = True
    legacy_state_variables: list[str] = field(default_factory=list)
    poly_state_variables: list[str] = field(default_factory=list)
    node_order_length_match: bool = True
    all_within_tolerance: bool = True
    issues: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)

    def has_divergence(self) -> bool:
        """Return True if any matrix or structural divergence was detected."""
        return not self.all_within_tolerance or bool(self.issues)

    def summary(self) -> str:
        """Return a one-line human-readable summary."""
        status = "PASS" if not self.has_divergence() else "FAIL"
        n_matrices = len(self.matrix_parities)
        n_passed = sum(1 for mp in self.matrix_parities if mp.within_tolerance)
        return (
            f"[{status}] graph={self.graph_id!r} mode={self.parity_mode!r} "
            f"matrices={n_passed}/{n_matrices} ok "
            f"states_match={self.state_variables_match}"
        )
