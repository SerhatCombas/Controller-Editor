"""ReducerParityHarness — Wave 1 shadow architecture migration tool.

Runs the legacy DAEReducer and the PolymorphicDAEReducer on the same graph,
compares their outputs, and produces a ReducerParityReport.

ParityMode semantics:
  OFF      → only the legacy reducer runs; harness returns legacy result directly
             (no comparison, zero overhead, production default)
  SHADOW   → both reducers run; legacy result is authoritative; any divergence
             is captured in the report and can be logged / CI-gated
  PRIMARY  → polymorphic reducer is authoritative; legacy runs as the validator

This harness is the only place in Wave 1 where both reducers run concurrently.
All other code paths use only one reducer, determined by ParityMode.

Boundary rules (enforced by design, not runtime checks):
  - ReducerParityHarness  → invokes both reducers, compares outputs
  - PolymorphicDAEReducer → pure algebra, no knowledge of the harness
  - DAEReducer            → legacy path, untouched by Wave 1 (except this file)
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

from app.core.state.feature_flags import DEFAULT_FLAGS, FeatureFlags, ParityMode
from app.core.symbolic.dae_reducer import DAEReducer
from app.core.symbolic.parity_report import MatrixParity, ReducerParityReport
from app.core.symbolic.polymorphic_dae_reducer import PolymorphicDAEReducer
from app.core.symbolic.symbolic_system import ReducedODESystem, SymbolicSystem

if TYPE_CHECKING:
    pass

DEFAULT_TOLERANCE = 1e-9


class ReducerParityHarness:
    """Wraps both reducers and compares their outputs under FeatureFlags control.

    Usage::

        flags = FeatureFlags(parity_mode=ParityMode.SHADOW, ...)
        harness = ReducerParityHarness(flags=flags)
        authoritative, report = harness.reduce(graph, symbolic_system)

    When ``parity_mode=OFF``, ``report`` is always ``None`` (zero overhead).
    When ``parity_mode=SHADOW``, ``report`` contains the full comparison.
    When ``parity_mode=PRIMARY``, the polymorphic reducer is authoritative.
    """

    def __init__(
        self,
        flags: FeatureFlags = DEFAULT_FLAGS,
        tolerance: float = DEFAULT_TOLERANCE,
        legacy_reducer: DAEReducer | None = None,
        poly_reducer: PolymorphicDAEReducer | None = None,
    ) -> None:
        self._flags = flags
        self._tolerance = tolerance
        self._legacy = legacy_reducer or DAEReducer()
        self._poly = poly_reducer or PolymorphicDAEReducer()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reduce(
        self,
        graph: object,
        symbolic_system: SymbolicSystem,
        *,
        graph_id: str = "",
    ) -> tuple[ReducedODESystem, ReducerParityReport | None]:
        """Run reducer(s) and return (authoritative_result, optional_report).

        Args:
            graph: SystemGraph instance.
            symbolic_system: Output of EquationBuilder (needed by legacy reducer).
            graph_id: Optional label for the graph — included in the report.

        Returns:
            A tuple (ReducedODESystem, ReducerParityReport | None).
            The report is None when parity_mode == OFF.
        """
        mode = self._flags.parity_mode

        if mode == ParityMode.OFF:
            # Zero overhead: only legacy runs
            result = self._legacy.reduce(graph, symbolic_system)
            return result, None

        if mode == ParityMode.SHADOW:
            # Both run; legacy is authoritative
            legacy_result = self._legacy.reduce(graph, symbolic_system)
            poly_result = self._poly.reduce(graph, symbolic_system)
            report = self._build_report(
                legacy_result, poly_result, graph_id=graph_id
            )
            return legacy_result, report

        if mode == ParityMode.PRIMARY:
            # Polymorphic is authoritative.  Legacy runs as validator; if it
            # fails (e.g. incomplete SymbolicSystem) we log a degraded report
            # but still return the correct polymorphic result.
            poly_result = self._poly.reduce(graph, symbolic_system)
            try:
                legacy_result = self._legacy.reduce(graph, symbolic_system)
                report = self._build_report(
                    legacy_result, poly_result, graph_id=graph_id
                )
            except Exception as exc:  # noqa: BLE001
                # Legacy validation unavailable — degenerate report
                report = ReducerParityReport(
                    graph_id=graph_id,
                    parity_mode=mode.value,
                    matrix_parities=[],
                    state_variables_match=False,
                    legacy_state_variables=[],
                    poly_state_variables=list(poly_result.state_variables),
                    node_order_length_match=False,
                    all_within_tolerance=False,
                    issues=[f"Legacy reducer unavailable in PRIMARY mode: {exc}"],
                    metadata={"primary_degraded": True},
                )
            return poly_result, report

        # Unreachable, but safe fallback
        result = self._legacy.reduce(graph, symbolic_system)
        return result, None

    # ------------------------------------------------------------------
    # Report construction
    # ------------------------------------------------------------------

    def _build_report(
        self,
        legacy: ReducedODESystem,
        poly: ReducedODESystem,
        *,
        graph_id: str,
    ) -> ReducerParityReport:
        matrix_parities = [
            self._compare_matrix("M", legacy.mass_matrix, poly.mass_matrix),
            self._compare_matrix("D", legacy.damping_matrix, poly.damping_matrix),
            self._compare_matrix("K", legacy.stiffness_matrix, poly.stiffness_matrix),
            self._compare_matrix("B", legacy.input_matrix, poly.input_matrix),
            self._compare_matrix("A", legacy.first_order_a, poly.first_order_a),
            self._compare_matrix("b", legacy.first_order_b, poly.first_order_b),
        ]

        state_variables_match = sorted(legacy.state_variables) == sorted(poly.state_variables)
        node_order_length_match = len(legacy.node_order) == len(poly.node_order)

        issues: list[str] = []
        for mp in matrix_parities:
            if not mp.shapes_match:
                issues.append(
                    f"Matrix {mp.name!r} shape mismatch: "
                    f"legacy={mp.shape_legacy} poly={mp.shape_poly}"
                )
            elif not mp.within_tolerance:
                issues.append(
                    f"Matrix {mp.name!r} divergence: max_abs_error={mp.max_abs_error:.3e} "
                    f"(tolerance={mp.tolerance:.1e})"
                )
        if not state_variables_match:
            issues.append(
                f"State variable names differ: "
                f"legacy={legacy.state_variables!r} poly={poly.state_variables!r}"
            )
        if not node_order_length_match:
            issues.append(
                f"DOF count mismatch: legacy={len(legacy.node_order)} poly={len(poly.node_order)}"
            )

        all_within_tolerance = (
            all(mp.within_tolerance for mp in matrix_parities)
            and state_variables_match
            and node_order_length_match
        )

        return ReducerParityReport(
            graph_id=graph_id,
            parity_mode=self._flags.parity_mode.value,
            matrix_parities=matrix_parities,
            state_variables_match=state_variables_match,
            legacy_state_variables=list(legacy.state_variables),
            poly_state_variables=list(poly.state_variables),
            node_order_length_match=node_order_length_match,
            all_within_tolerance=all_within_tolerance,
            issues=issues,
            metadata={
                "tolerance": self._tolerance,
                "legacy_reduction_type": legacy.metadata.get("reduction_type", "unknown"),
                "poly_reduction_type": poly.metadata.get("reduction_type", "unknown"),
            },
        )

    # ------------------------------------------------------------------
    # Matrix comparison helper
    # ------------------------------------------------------------------

    def _compare_matrix(
        self,
        name: str,
        legacy: list[list[float]],
        poly: list[list[float]],
    ) -> MatrixParity:
        rows_l, cols_l = self._shape(legacy)
        rows_p, cols_p = self._shape(poly)
        shapes_match = (rows_l, cols_l) == (rows_p, cols_p)

        if not shapes_match or (rows_l == 0 and cols_l == 0):
            max_err = 0.0 if (rows_l == 0 and rows_p == 0) else float("inf")
            return MatrixParity(
                name=name,
                shape_legacy=(rows_l, cols_l),
                shape_poly=(rows_p, cols_p),
                shapes_match=shapes_match,
                max_abs_error=max_err,
                within_tolerance=shapes_match and max_err <= self._tolerance,
                tolerance=self._tolerance,
            )

        max_err = 0.0
        for row_l, row_p in zip(legacy, poly):
            for vl, vp in zip(row_l, row_p):
                diff = abs(vl - vp)
                if math.isnan(diff):
                    max_err = float("inf")
                elif diff > max_err:
                    max_err = diff

        return MatrixParity(
            name=name,
            shape_legacy=(rows_l, cols_l),
            shape_poly=(rows_p, cols_p),
            shapes_match=True,
            max_abs_error=max_err,
            within_tolerance=max_err <= self._tolerance,
            tolerance=self._tolerance,
        )

    @staticmethod
    def _shape(matrix: list[list[float]]) -> tuple[int, int]:
        if not matrix:
            return (0, 0)
        return (len(matrix), len(matrix[0]))
