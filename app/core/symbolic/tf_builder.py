"""SymbolicTFBuilder — Wave 2 Commit 2.

Builds a SISO symbolic transfer function from a ReducedODESystem and an
OutputExpression:

    H(s) = C(sI − A)⁻¹B + D

where A, B are the first-order state-space matrices and C, D are the row
vectors produced by OutputMapper.

Design decisions (approved before Wave 2):
  1. Plain ``s = sympy.Symbol("s")`` — no Laplace-domain assumptions.
     Avoids assumption-induced divergence in cancel / factor / roots.
  2. Default simplification mode: ``"raw"`` (sympy.cancel only).
     ``"simplified"`` and ``"factored"`` are opt-in; never called automatically.
  3. Public API is SISO: ``build_siso_tf(input_id, output_expression)``.
     Internal function ``_build_siso_entry(c_row, d_row, input_col)`` is
     MIMO-ready (accepts row/column indices), enabling Wave 3 MIMO extension.
  4. Sympy parsing bug in EquationBuilder is known but out of scope —
     TFBuilder consumes ReducedODESystem, never touches EquationBuilder.

TransferFunctionResult fields follow the user-approved schema including
provenance metadata, simplification_mode, is_proper, poles, zeros.

SimplificationMode options
──────────────────────────
  "raw"        cancel() only — fast, mathematically correct, may look verbose
  "simplified" cancel() + sympy.simplify() — slower, cleaner expression
  "factored"   cancel() + sympy.factor() — reveals root structure
  "numeric"    symbolic result + numeric substitution of parameter values
               (preview only — not a replacement for numeric simulation)
"""
from __future__ import annotations

import sympy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from app.core.symbolic.output_mapper import OutputExpression
    from app.core.symbolic.symbolic_system import ReducedODESystem

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

SimplificationMode = Literal["raw", "simplified", "factored", "numeric"]

s = sympy.Symbol("s")   # module-level Laplace variable, plain symbol


@dataclass(frozen=True, slots=True)
class TransferFunctionResult:
    """SISO symbolic transfer function with full provenance.

    Attributes:
        input_id: ID of the input channel (matches ReducedODESystem input).
        output_id: ID of the output channel (matches probe / OutputExpression).
        input_label: Human-readable input label.
        output_label: Human-readable output label.
        numerator_expr: Sympy expression for the TF numerator (in ``s``).
        denominator_expr: Sympy expression for the TF denominator (in ``s``).
        laplace_symbol_name: Always ``"s"`` in Wave 2 (metadata for export).
        simplification_mode: The mode used when this result was built.
        is_proper: True when deg(numerator) ≤ deg(denominator).
        is_strictly_proper: True when deg(numerator) < deg(denominator).
        order: Degree of the denominator polynomial.
        poles: Tuple of sympy expressions (roots of denominator).
            May be empty if sympy.roots() cannot find symbolic roots.
        zeros: Tuple of sympy expressions (roots of numerator).
        is_supported: Always True for a successfully built result.
        unsupported_reason: Always None for a successfully built result.
        system_class: Short descriptor, e.g. ``"SISO-2DOF"``.
        source_path: Always ``"state_space"`` (TF was built from A, B, C, D).
        warnings: Tuple of non-fatal diagnostic messages.
        provenance: Ordered trace of builder decisions.
    """

    # Core TF
    input_id: str
    output_id: str
    input_label: str
    output_label: str
    numerator_expr: sympy.Expr
    denominator_expr: sympy.Expr
    laplace_symbol_name: str

    # Simplification
    simplification_mode: SimplificationMode

    # Properties
    is_proper: bool
    is_strictly_proper: bool
    order: int
    poles: tuple[sympy.Expr, ...]
    zeros: tuple[sympy.Expr, ...]

    # Provenance / support
    is_supported: bool
    unsupported_reason: str | None
    system_class: str
    source_path: str
    warnings: tuple[str, ...]
    provenance: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class UnsupportedTFResult:
    """Returned when TF cannot be built (unsupported output, wrong input, etc.).

    Shares the same structural role as TransferFunctionResult so callers can
    check ``result.is_supported`` without isinstance checks.
    """

    input_id: str
    output_id: str
    input_label: str
    output_label: str
    is_supported: bool          # always False
    unsupported_reason: str
    laplace_symbol_name: str    # always "s"
    source_path: str            # always "state_space"
    provenance: tuple[str, ...]

    # Provide same attributes as TransferFunctionResult with safe defaults
    @property
    def numerator_expr(self) -> sympy.Expr:
        return sympy.Integer(0)

    @property
    def denominator_expr(self) -> sympy.Expr:
        return sympy.Integer(1)

    @property
    def simplification_mode(self) -> str:
        return "raw"

    @property
    def is_proper(self) -> bool:
        return True

    @property
    def is_strictly_proper(self) -> bool:
        return True

    @property
    def order(self) -> int:
        return 0

    @property
    def poles(self) -> tuple:
        return ()

    @property
    def zeros(self) -> tuple:
        return ()

    @property
    def system_class(self) -> str:
        return "unsupported"

    @property
    def warnings(self) -> tuple:
        return ()


# ---------------------------------------------------------------------------
# SymbolicTFBuilder
# ---------------------------------------------------------------------------

class SymbolicTFBuilder:
    """Build SISO symbolic transfer functions from ReducedODESystem + OutputMapper.

    Usage::

        builder = SymbolicTFBuilder()
        result = builder.build_siso_tf(
            reduced_ode=ode,
            input_id="u_road_source",
            output_expr=mapper.map(body_displacement_probe, ode),
        )
        if result.is_supported:
            print(result.numerator_expr)
            print(result.denominator_expr)

    Notes:
        - The builder is stateless; the same instance is safe to reuse.
        - Default ``mode="raw"`` applies only ``sympy.cancel()``.
          Pass ``mode="simplified"`` or ``mode="factored"`` for cleaner
          but slower symbolic output.
        - Poles and zeros are computed via ``sympy.Poly.all_roots()``
          when possible; empty tuples are returned on failure.
    """

    def build_siso_tf(
        self,
        *,
        reduced_ode: "ReducedODESystem",
        input_id: str,
        output_expr: "OutputExpression",
        mode: SimplificationMode = "raw",
        input_label: str = "",
    ) -> TransferFunctionResult | UnsupportedTFResult:
        """Build H(s) for one (input, output) pair.

        Args:
            reduced_ode: A fully assembled ReducedODESystem.
            input_id: ID of the input channel (must be in
                ``reduced_ode.input_variables``).
            output_expr: OutputExpression from OutputMapper.  If
                ``output_expr.supported_for_tf`` is False, an
                UnsupportedTFResult is returned immediately.
            mode: Simplification mode (default ``"raw"``).
            input_label: Human-readable label for the input (optional).

        Returns:
            ``TransferFunctionResult`` on success or ``UnsupportedTFResult``
            when the output is not supported.
        """
        prov: list[str] = [
            f"input_id={input_id!r}",
            f"output_id={output_expr.output_id!r}",
            f"mode={mode!r}",
            f"n_states={len(reduced_ode.state_variables)}",
            f"n_inputs={len(reduced_ode.input_variables)}",
        ]

        # Guard 1: output not supported for TF
        if not output_expr.supported_for_tf:
            prov.append(f"ABORT: output not supported: {output_expr.unsupported_reason}")
            return UnsupportedTFResult(
                input_id=input_id,
                output_id=output_expr.output_id,
                input_label=input_label or input_id,
                output_label=output_expr.output_label,
                is_supported=False,
                unsupported_reason=output_expr.unsupported_reason or "Unknown",
                laplace_symbol_name="s",
                source_path="state_space",
                provenance=tuple(prov),
            )

        # Guard 2: input not found
        try:
            input_col = reduced_ode.input_variables.index(input_id)
        except ValueError:
            reason = (
                f"Input '{input_id}' not found in ReducedODESystem.input_variables "
                f"({reduced_ode.input_variables!r})."
            )
            prov.append(f"ABORT: {reason}")
            return UnsupportedTFResult(
                input_id=input_id,
                output_id=output_expr.output_id,
                input_label=input_label or input_id,
                output_label=output_expr.output_label,
                is_supported=False,
                unsupported_reason=reason,
                laplace_symbol_name="s",
                source_path="state_space",
                provenance=tuple(prov),
            )

        # Guard 3: A matrix must be present
        if not reduced_ode.first_order_a:
            reason = "ReducedODESystem has no first_order_a matrix (empty system)."
            prov.append(f"ABORT: {reason}")
            return UnsupportedTFResult(
                input_id=input_id,
                output_id=output_expr.output_id,
                input_label=input_label or input_id,
                output_label=output_expr.output_label,
                is_supported=False,
                unsupported_reason=reason,
                laplace_symbol_name="s",
                source_path="state_space",
                provenance=tuple(prov),
            )

        prov.append(f"input_col={input_col}")
        c_row = list(output_expr.c_row)
        d_row = list(output_expr.d_row)

        return self._build_siso_entry(
            reduced_ode=reduced_ode,
            c_row=c_row,
            d_row=d_row,
            input_col=input_col,
            input_id=input_id,
            input_label=input_label or input_id,
            output_id=output_expr.output_id,
            output_label=output_expr.output_label,
            mode=mode,
            prov=prov,
        )

    # ------------------------------------------------------------------
    # Internal: MIMO-ready entry point
    # ------------------------------------------------------------------

    def _build_siso_entry(
        self,
        *,
        reduced_ode: "ReducedODESystem",
        c_row: list[float],
        d_row: list[float],
        input_col: int,
        input_id: str,
        input_label: str,
        output_id: str,
        output_label: str,
        mode: SimplificationMode,
        prov: list[str],
    ) -> TransferFunctionResult | UnsupportedTFResult:
        """Core algebra: H(s) = C(sI−A)⁻¹B_col + D_col.

        This function accepts explicit row/column indices and is designed so
        that a Wave 3 MIMO wrapper can iterate over (i, j) pairs and call it
        for each entry of the full transfer matrix.
        """
        n = len(reduced_ode.first_order_a)
        prov.append(f"state_dim={n}")

        # Build sympy A matrix
        A_sym = sympy.Matrix(reduced_ode.first_order_a)
        prov.append("A matrix converted to sympy.Matrix")

        # Build (sI − A)
        sI_minus_A = s * sympy.eye(n) - A_sym
        prov.append("(sI-A) assembled")

        # Extract the input column from B
        B_sym = sympy.Matrix(reduced_ode.first_order_b)
        b_col = B_sym.col(input_col)   # n×1 column vector
        prov.append(f"B col {input_col} extracted")

        # C row as 1×n matrix (sympy rational entries for clean arithmetic)
        C_sym = sympy.Matrix([sympy.Rational(v) for v in c_row]).T  # 1×n
        prov.append("C row assembled")

        # D scalar for this (output, input) pair
        d_val = sympy.Rational(d_row[input_col]) if input_col < len(d_row) else sympy.Integer(0)
        prov.append(f"D scalar = {d_val}")

        # Solve (sI−A)·x = b_col for x using Cramer's rule via adjugate:
        #   (sI−A)⁻¹ = adj(sI−A) / det(sI−A)
        # Avoids sympy.Matrix.inv() which can time out on large systems.
        det_sym = sI_minus_A.det()
        adj_sym = sI_minus_A.adjugate()
        prov.append("det and adjugate computed")

        # H(s) = C·adj·b / det + D
        #      = (C·adj·b + D·det) / det
        numerator_raw = (C_sym * adj_sym * b_col)[0, 0] + d_val * det_sym
        denominator_raw = det_sym
        prov.append("H(s) raw numerator and denominator assembled")

        # Simplification
        warnings: list[str] = []
        num, den = self._simplify(
            numerator_raw, denominator_raw, mode, prov, warnings
        )

        # Degree analysis
        num_poly = sympy.Poly(num, s)
        den_poly = sympy.Poly(den, s)
        num_deg = num_poly.degree()
        den_deg = den_poly.degree()
        is_proper = num_deg <= den_deg
        is_strictly_proper = num_deg < den_deg
        prov.append(
            f"deg(num)={num_deg}, deg(den)={den_deg}, "
            f"proper={is_proper}, strictly_proper={is_strictly_proper}"
        )

        if not is_proper:
            warnings.append(
                f"Transfer function is improper: deg(numerator)={num_deg} > "
                f"deg(denominator)={den_deg}.  Check C row and D term."
            )

        # Poles and zeros
        poles = self._compute_roots(den_poly, "poles", prov, warnings)
        zeros = self._compute_roots(num_poly, "zeros", prov, warnings)

        # System class descriptor
        n_dof = len(reduced_ode.state_variables) // 2
        system_class = f"SISO-{n_dof}DOF"

        return TransferFunctionResult(
            input_id=input_id,
            output_id=output_id,
            input_label=input_label,
            output_label=output_label,
            numerator_expr=num,
            denominator_expr=den,
            laplace_symbol_name="s",
            simplification_mode=mode,
            is_proper=is_proper,
            is_strictly_proper=is_strictly_proper,
            order=den_deg,
            poles=poles,
            zeros=zeros,
            is_supported=True,
            unsupported_reason=None,
            system_class=system_class,
            source_path="state_space",
            warnings=tuple(warnings),
            provenance=tuple(prov),
        )

    # ------------------------------------------------------------------
    # Simplification
    # ------------------------------------------------------------------

    def _simplify(
        self,
        num: sympy.Expr,
        den: sympy.Expr,
        mode: SimplificationMode,
        prov: list[str],
        warnings: list[str],
    ) -> tuple[sympy.Expr, sympy.Expr]:
        """Apply cancel() always, then optional additional simplification."""
        # cancel() is always applied — reduces common factors between num/den
        try:
            h = sympy.cancel(sympy.Rational(1) * num / den)
            # Re-extract num and den from the cancelled form
            num_c, den_c = sympy.fraction(h)
            prov.append("cancel() applied")
        except Exception as exc:  # pragma: no cover
            warnings.append(f"cancel() failed ({exc}); returning raw form")
            num_c, den_c = num, den

        if mode == "raw":
            return num_c, den_c

        if mode == "simplified":
            try:
                num_c = sympy.simplify(num_c)
                den_c = sympy.simplify(den_c)
                prov.append("simplify() applied")
            except Exception as exc:
                warnings.append(f"simplify() failed ({exc}); using cancel result")
            return num_c, den_c

        if mode == "factored":
            try:
                num_c = sympy.factor(num_c)
                den_c = sympy.factor(den_c)
                prov.append("factor() applied")
            except Exception as exc:
                warnings.append(f"factor() failed ({exc}); using cancel result")
            return num_c, den_c

        if mode == "numeric":
            # Numeric mode: expressions are already numeric (floats from A, B)
            # so cancel is sufficient; add a note in provenance
            prov.append("numeric mode: float coefficients already in expressions")
            return num_c, den_c

        # Unknown mode — fall back to raw
        warnings.append(f"Unknown mode {mode!r}; using raw output")
        return num_c, den_c

    # ------------------------------------------------------------------
    # Root finding
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_roots(
        poly: sympy.Poly,
        label: str,
        prov: list[str],
        warnings: list[str],
    ) -> tuple[sympy.Expr, ...]:
        """Compute roots of a sympy Poly; return empty tuple on failure."""
        try:
            if poly.degree() == 0:
                prov.append(f"{label}: degree-0 polynomial, no roots")
                return ()
            roots_dict = sympy.roots(poly, multiple=False)
            result: list[sympy.Expr] = []
            for root_val, mult in roots_dict.items():
                result.extend([root_val] * mult)
            prov.append(f"{label}: {len(result)} roots found")
            return tuple(result)
        except Exception as exc:
            warnings.append(
                f"{label.capitalize()} computation failed ({exc}); "
                "returning empty tuple."
            )
            prov.append(f"{label}: root computation failed")
            return ()
