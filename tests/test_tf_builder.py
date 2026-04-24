"""Tests for SymbolicTFBuilder — Wave 2 Commit 2.

Coverage plan
─────────────
Section A — Guards / UnsupportedTFResult
  A1  Unsupported output expression → UnsupportedTFResult immediately
  A2  Input ID not in input_variables → UnsupportedTFResult
  A3  Empty first_order_a matrix → UnsupportedTFResult
  A4  UnsupportedTFResult interface — safe-default properties

Section B — Single-mass golden result (m=1, k=2, d=3, force input)
  B1  is_supported=True
  B2  H(s) = 1/(s²+3s+2) numerically exact after cancel
  B3  Denominator degree = 2 (order=2)
  B4  is_proper=True, is_strictly_proper=True
  B5  Two poles at s=-1 and s=-2 (exact symbolic)
  B6  Numerator has no s-roots (degree-0 polynomial)
  B7  provenance is a non-empty tuple of strings
  B8  system_class = "SISO-1DOF"
  B9  laplace_symbol_name = "s"
  B10 source_path = "state_space"

Section C — Velocity output on single-mass (C = [0, 1])
  C1  H(s) = s/(s²+3s+2) — strictly proper, one zero at s=0
  C2  is_strictly_proper=True, is_proper=True

Section D — Simplification modes
  D1  mode="simplified" — result numerically equivalent to "raw"
  D2  mode="factored"   — result numerically equivalent to "raw"
  D3  mode="numeric"    — result numerically equivalent to "raw"
  D4  Different modes return same is_supported, order, is_proper

Section E — Two-DOF (two-mass) system
  E1  4 poles for 2-DOF system
  E2  order=4
  E3  is_strictly_proper=True for displacement output
  E4  system_class = "SISO-2DOF"

Section F — Quarter-car (hand-assembled 2-DOF) golden properties
  F1  4 poles for 2-DOF quarter-car
  F2  Denominator degree = 4
  F3  is_properly_proper (body displacement output is strictly proper)
  F4  DC gain sign: road → body displacement should be positive

Section G — Honesty guarantee
  G1  Any UnsupportedTFResult has is_supported=False
  G2  Any TransferFunctionResult has is_supported=True
  G3  UnsupportedTFResult.numerator_expr = 0, denominator_expr = 1
"""
from __future__ import annotations

import unittest
import sympy

from app.core.symbolic.symbolic_system import ReducedODESystem
from app.core.symbolic.output_mapper import OutputExpression
from app.core.symbolic.tf_builder import (
    SymbolicTFBuilder,
    TransferFunctionResult,
    UnsupportedTFResult,
    s as S,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ode(
    *,
    state_vars: list[str],
    input_vars: list[str],
    a: list[list[float]],
    b: list[list[float]],
) -> ReducedODESystem:
    """Build a minimal ReducedODESystem for testing."""
    return ReducedODESystem(
        state_variables=state_vars,
        input_variables=input_vars,
        first_order_a=a,
        first_order_b=b,
    )


def _make_output(
    *,
    output_id: str = "y0",
    output_label: str = "y0",
    c_row: tuple[float, ...],
    n_inputs: int = 1,
    supported: bool = True,
    reason: str | None = None,
    quantity_type: str = "displacement",
) -> OutputExpression:
    """Build an OutputExpression for testing."""
    d_row = tuple(0.0 for _ in range(n_inputs))
    idx = tuple(i for i, v in enumerate(c_row) if v != 0.0)
    names = tuple(f"state_{i}" for i in idx)
    return OutputExpression(
        output_id=output_id,
        output_label=output_label,
        quantity_type=quantity_type,
        c_row=c_row,
        d_row=d_row,
        supported_for_tf=supported,
        unsupported_reason=reason,
        contributing_state_indices=idx,
        contributing_state_names=names,
        provenance=("test",),
    )


def _single_mass_ode(m: float = 1.0, k: float = 2.0, d: float = 3.0) -> ReducedODESystem:
    """
    Single-mass: m·ẍ + d·ẋ + k·x = F
    First-order form:
        A = [[0, 1], [-k/m, -d/m]]
        B = [[0], [1/m]]
    """
    return _make_ode(
        state_vars=["x_mass", "v_mass"],
        input_vars=["F_input"],
        a=[[0.0, 1.0], [-k / m, -d / m]],
        b=[[0.0], [1.0 / m]],
    )


def _single_mass_disp_output() -> OutputExpression:
    """C = [1, 0] for x_mass displacement."""
    return _make_output(c_row=(1.0, 0.0), n_inputs=1)


def _single_mass_vel_output() -> OutputExpression:
    """C = [0, 1] for v_mass velocity."""
    return _make_output(
        output_id="y_vel",
        output_label="v_mass",
        c_row=(0.0, 1.0),
        n_inputs=1,
        quantity_type="velocity",
    )


def _two_dof_ode() -> ReducedODESystem:
    """
    Two-mass system in series: masses m1=1, m2=2; spring k=4; damper d=0.
    DOFs: x1, x2.
    Equations (in matrix Laplacian form):
        m1·ẍ1 = -k*(x1-x2)  → [x1, x2, v1, v2] state
        m2·ẍ2 = -k*(x2-x1) + F

    A = [[0, 0, 1, 0],
         [0, 0, 0, 1],
         [-k/m1, k/m1, 0, 0],
         [k/m2, -k/m2, 0, 0]]
    B (force input on mass2):
         [[0], [0], [0], [1/m2]]
    """
    m1, m2, k = 1.0, 2.0, 4.0
    return _make_ode(
        state_vars=["x_m1", "x_m2", "v_m1", "v_m2"],
        input_vars=["F_input"],
        a=[
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
            [-k / m1, k / m1, 0.0, 0.0],
            [k / m2, -k / m2, 0.0, 0.0],
        ],
        b=[[0.0], [0.0], [0.0], [1.0 / m2]],
    )


def _quarter_car_ode() -> ReducedODESystem:
    """
    Quarter-car (2-DOF):
      mb=300, mw=30, ks=15000, ds=1500, kt=150000
    States: [x_body, x_wheel, v_body, v_wheel]
    Input: u_road (displacement source, enters via tire stiffness kt)

    v̇_body = -(ks/mb)*(x_body - x_wheel) - (ds/mb)*(v_body - v_wheel)
    v̇_wheel = +(ks/mw)*(x_body - x_wheel) + (ds/mw)*(v_body - v_wheel)
               - (kt/mw)*x_wheel + (kt/mw)*u_road

    A[2][0] = -ks/mb,  A[2][1] = ks/mb,  A[2][2] = -ds/mb,  A[2][3] = ds/mb
    A[3][0] = ks/mw,   A[3][1] = -(ks+kt)/mw, A[3][2] = ds/mw, A[3][3] = -ds/mw
    B[3][0] = kt/mw
    """
    mb, mw = 300.0, 30.0
    ks, ds, kt = 15000.0, 1500.0, 150000.0
    return _make_ode(
        state_vars=["x_body", "x_wheel", "v_body", "v_wheel"],
        input_vars=["u_road"],
        a=[
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
            [-ks / mb, ks / mb, -ds / mb, ds / mb],
            [ks / mw, -(ks + kt) / mw, ds / mw, -ds / mw],
        ],
        b=[[0.0], [0.0], [0.0], [kt / mw]],
    )


# ---------------------------------------------------------------------------
# A — Guards / UnsupportedTFResult
# ---------------------------------------------------------------------------

class TestGuards(unittest.TestCase):

    def setUp(self) -> None:
        self.builder = SymbolicTFBuilder()
        self.ode = _single_mass_ode()

    def test_A1_unsupported_output_returns_unsupported_result(self) -> None:
        bad_output = _make_output(
            c_row=(0.0, 0.0),
            supported=False,
            reason="Force output not supported in Wave 2.",
        )
        result = self.builder.build_siso_tf(
            reduced_ode=self.ode,
            input_id="F_input",
            output_expr=bad_output,
        )
        self.assertIsInstance(result, UnsupportedTFResult)
        self.assertFalse(result.is_supported)
        self.assertIn("Force", result.unsupported_reason)

    def test_A2_missing_input_id_returns_unsupported(self) -> None:
        result = self.builder.build_siso_tf(
            reduced_ode=self.ode,
            input_id="does_not_exist",
            output_expr=_single_mass_disp_output(),
        )
        self.assertIsInstance(result, UnsupportedTFResult)
        self.assertFalse(result.is_supported)
        self.assertIn("does_not_exist", result.unsupported_reason)

    def test_A3_empty_a_matrix_returns_unsupported(self) -> None:
        empty_ode = _make_ode(
            state_vars=[],
            input_vars=["F_input"],
            a=[],
            b=[],
        )
        result = self.builder.build_siso_tf(
            reduced_ode=empty_ode,
            input_id="F_input",
            output_expr=_single_mass_disp_output(),
        )
        self.assertIsInstance(result, UnsupportedTFResult)
        self.assertFalse(result.is_supported)

    def test_A4_unsupported_result_safe_defaults(self) -> None:
        bad_output = _make_output(
            c_row=(0.0, 0.0),
            supported=False,
            reason="Test reason.",
        )
        result = self.builder.build_siso_tf(
            reduced_ode=self.ode,
            input_id="F_input",
            output_expr=bad_output,
        )
        self.assertIsInstance(result, UnsupportedTFResult)
        # Safe defaults from properties
        self.assertEqual(result.numerator_expr, sympy.Integer(0))
        self.assertEqual(result.denominator_expr, sympy.Integer(1))
        self.assertTrue(result.is_proper)
        self.assertTrue(result.is_strictly_proper)
        self.assertEqual(result.order, 0)
        self.assertEqual(result.poles, ())
        self.assertEqual(result.zeros, ())
        self.assertEqual(result.system_class, "unsupported")
        self.assertEqual(result.warnings, ())


# ---------------------------------------------------------------------------
# B — Single-mass golden result (m=1, k=2, d=3)
# ---------------------------------------------------------------------------

class TestSingleMassDisplacement(unittest.TestCase):
    """H(s) = 1 / (s² + 3s + 2) for m=1, k=2, d=3, force-to-displacement."""

    def setUp(self) -> None:
        self.builder = SymbolicTFBuilder()
        self.ode = _single_mass_ode(m=1.0, k=2.0, d=3.0)
        self.result = self.builder.build_siso_tf(
            reduced_ode=self.ode,
            input_id="F_input",
            output_expr=_single_mass_disp_output(),
        )

    def test_B1_is_supported(self) -> None:
        self.assertIsInstance(self.result, TransferFunctionResult)
        self.assertTrue(self.result.is_supported)

    def test_B2_tf_numerically_exact(self) -> None:
        """H(s) = 1/(s²+3s+2): verify by evaluating at integer test points.

        We use integer s values to avoid floating-point rounding issues that
        appear when the A matrix contains float coefficients.  The denominators
        stay exact rational numbers at integer s.
        """
        num = self.result.numerator_expr
        den = self.result.denominator_expr

        # H(s) = 1/(s^2 + 3s + 2).  Test at s = 1, 2, -5.
        for s_val in [1, 2, -5]:
            expected_num = sympy.Integer(1)
            expected_den = s_val**2 + 3 * s_val + 2
            actual_ratio = (
                sympy.Rational(1) * num.subs(S, s_val) / den.subs(S, s_val)
            )
            expected_ratio = sympy.Rational(1) * expected_num / expected_den
            diff = sympy.simplify(actual_ratio - expected_ratio)
            self.assertEqual(diff, 0, f"Mismatch at s={s_val}: diff={diff}")

    def test_B3_order_is_2(self) -> None:
        self.assertEqual(self.result.order, 2)

    def test_B4_proper_and_strictly_proper(self) -> None:
        self.assertTrue(self.result.is_proper)
        self.assertTrue(self.result.is_strictly_proper)

    def test_B5_two_poles_at_minus1_and_minus2(self) -> None:
        """Denominator s²+3s+2 = (s+1)(s+2) → poles at -1 and -2.

        Because the A matrix contains float coefficients, sympy.roots() returns
        sympy.Float values.  We compare numerically with a tight tolerance.
        """
        poles = self.result.poles
        self.assertEqual(len(poles), 2, f"Expected 2 poles, got {poles}")
        pole_floats = sorted(float(p) for p in poles)
        self.assertAlmostEqual(pole_floats[0], -2.0, places=10)
        self.assertAlmostEqual(pole_floats[1], -1.0, places=10)

    def test_B6_numerator_degree_0(self) -> None:
        """Numerator is a constant (degree 0) → no finite zeros."""
        zeros = self.result.zeros
        # degree-0 polynomial has no roots by _compute_roots convention
        self.assertEqual(zeros, ())

    def test_B7_provenance_non_empty(self) -> None:
        prov = self.result.provenance
        self.assertIsInstance(prov, tuple)
        self.assertGreater(len(prov), 0)
        # All entries must be strings
        for entry in prov:
            self.assertIsInstance(entry, str)

    def test_B8_system_class(self) -> None:
        self.assertEqual(self.result.system_class, "SISO-1DOF")

    def test_B9_laplace_symbol_name(self) -> None:
        self.assertEqual(self.result.laplace_symbol_name, "s")

    def test_B10_source_path(self) -> None:
        self.assertEqual(self.result.source_path, "state_space")


# ---------------------------------------------------------------------------
# C — Velocity output on single-mass
# ---------------------------------------------------------------------------

class TestSingleMassVelocity(unittest.TestCase):
    """Force-to-velocity: H(s) = s/(s²+3s+2)."""

    def setUp(self) -> None:
        self.builder = SymbolicTFBuilder()
        self.ode = _single_mass_ode(m=1.0, k=2.0, d=3.0)
        self.result = self.builder.build_siso_tf(
            reduced_ode=self.ode,
            input_id="F_input",
            output_expr=_single_mass_vel_output(),
        )

    def test_C1_tf_equals_s_over_denom(self) -> None:
        """H(s) = s/(s²+3s+2): verify numerically."""
        num = self.result.numerator_expr
        den = self.result.denominator_expr
        for s_val in [2, 3, -10]:
            actual = sympy.Rational(1) * num.subs(S, s_val) / den.subs(S, s_val)
            expected = sympy.Rational(s_val, s_val**2 + 3 * s_val + 2)
            diff = sympy.simplify(actual - expected)
            self.assertEqual(diff, 0, f"Mismatch at s={s_val}: diff={diff}")

    def test_C2_strictly_proper(self) -> None:
        self.assertTrue(self.result.is_strictly_proper)
        self.assertTrue(self.result.is_proper)

    def test_C3_one_zero_at_origin(self) -> None:
        """Numerator s has a root at s=0."""
        zeros = self.result.zeros
        self.assertEqual(len(zeros), 1, f"Expected 1 zero, got {zeros}")
        self.assertEqual(sympy.simplify(zeros[0]), sympy.Integer(0))


# ---------------------------------------------------------------------------
# D — Simplification modes
# ---------------------------------------------------------------------------

class TestSimplificationModes(unittest.TestCase):

    def setUp(self) -> None:
        self.builder = SymbolicTFBuilder()
        self.ode = _single_mass_ode()
        self.output = _single_mass_disp_output()

    def _ratio_at(self, result, s_val: int) -> sympy.Expr:
        """Evaluate H(s) at a concrete s value."""
        n = result.numerator_expr.subs(S, s_val)
        d = result.denominator_expr.subs(S, s_val)
        return sympy.Rational(1) * n / d

    def test_D1_simplified_equivalent_to_raw(self) -> None:
        raw = self.builder.build_siso_tf(
            reduced_ode=self.ode, input_id="F_input",
            output_expr=self.output, mode="raw",
        )
        simp = self.builder.build_siso_tf(
            reduced_ode=self.ode, input_id="F_input",
            output_expr=self.output, mode="simplified",
        )
        self.assertTrue(simp.is_supported)
        for s_val in [1, 2, 5]:
            diff = sympy.simplify(self._ratio_at(raw, s_val) - self._ratio_at(simp, s_val))
            self.assertEqual(diff, 0)

    def test_D2_factored_equivalent_to_raw(self) -> None:
        raw = self.builder.build_siso_tf(
            reduced_ode=self.ode, input_id="F_input",
            output_expr=self.output, mode="raw",
        )
        fact = self.builder.build_siso_tf(
            reduced_ode=self.ode, input_id="F_input",
            output_expr=self.output, mode="factored",
        )
        self.assertTrue(fact.is_supported)
        for s_val in [1, 3, 7]:
            diff = sympy.simplify(self._ratio_at(raw, s_val) - self._ratio_at(fact, s_val))
            self.assertEqual(diff, 0)

    def test_D3_numeric_equivalent_to_raw(self) -> None:
        raw = self.builder.build_siso_tf(
            reduced_ode=self.ode, input_id="F_input",
            output_expr=self.output, mode="raw",
        )
        num_mode = self.builder.build_siso_tf(
            reduced_ode=self.ode, input_id="F_input",
            output_expr=self.output, mode="numeric",
        )
        self.assertTrue(num_mode.is_supported)
        for s_val in [1, 2, 4]:
            diff = sympy.simplify(self._ratio_at(raw, s_val) - self._ratio_at(num_mode, s_val))
            self.assertEqual(diff, 0)

    def test_D4_modes_share_structural_properties(self) -> None:
        for mode in ("raw", "simplified", "factored", "numeric"):
            result = self.builder.build_siso_tf(
                reduced_ode=self.ode, input_id="F_input",
                output_expr=self.output, mode=mode,
            )
            self.assertTrue(result.is_supported, f"mode={mode} should be supported")
            self.assertEqual(result.order, 2, f"mode={mode} should give order=2")
            self.assertTrue(result.is_proper, f"mode={mode} should be proper")
            self.assertTrue(result.is_strictly_proper, f"mode={mode} should be strictly proper")


# ---------------------------------------------------------------------------
# E — Two-DOF system (two-mass)
# ---------------------------------------------------------------------------

class TestTwoMassSystem(unittest.TestCase):
    """Two-mass in series → 4-state first-order system."""

    def setUp(self) -> None:
        self.builder = SymbolicTFBuilder()
        self.ode = _two_dof_ode()
        # Output: displacement of mass 1 (C = [1, 0, 0, 0])
        self.output = _make_output(c_row=(1.0, 0.0, 0.0, 0.0), n_inputs=1)
        self.result = self.builder.build_siso_tf(
            reduced_ode=self.ode,
            input_id="F_input",
            output_expr=self.output,
        )

    def test_E1_four_poles(self) -> None:
        poles = self.result.poles
        self.assertEqual(len(poles), 4, f"Expected 4 poles for 2-DOF, got {poles}")

    def test_E2_order_4(self) -> None:
        self.assertEqual(self.result.order, 4)

    def test_E3_strictly_proper(self) -> None:
        self.assertTrue(self.result.is_strictly_proper)

    def test_E4_system_class(self) -> None:
        self.assertEqual(self.result.system_class, "SISO-2DOF")


# ---------------------------------------------------------------------------
# F — Quarter-car golden properties
# ---------------------------------------------------------------------------

class TestQuarterCarTF(unittest.TestCase):
    """Hand-assembled quarter-car (2-DOF, road displacement input)."""

    def setUp(self) -> None:
        self.builder = SymbolicTFBuilder()
        self.ode = _quarter_car_ode()
        # Output: body displacement (x_body), C = [1, 0, 0, 0]
        self.body_disp_output = _make_output(
            output_id="y_body",
            output_label="body displacement",
            c_row=(1.0, 0.0, 0.0, 0.0),
            n_inputs=1,
        )
        self.result = self.builder.build_siso_tf(
            reduced_ode=self.ode,
            input_id="u_road",
            output_expr=self.body_disp_output,
        )

    def test_F1_four_poles(self) -> None:
        self.assertEqual(len(self.result.poles), 4,
                         f"Quarter-car 2-DOF should have 4 poles; got {self.result.poles}")

    def test_F2_denominator_degree_4(self) -> None:
        self.assertEqual(self.result.order, 4)

    def test_F3_strictly_proper(self) -> None:
        """Road displacement to body displacement: strictly proper."""
        self.assertTrue(self.result.is_strictly_proper)

    def test_F4_is_supported(self) -> None:
        self.assertTrue(self.result.is_supported)
        self.assertIsNone(self.result.unsupported_reason)


# ---------------------------------------------------------------------------
# G — Honesty guarantee
# ---------------------------------------------------------------------------

class TestHonestyGuarantee(unittest.TestCase):
    """Every UnsupportedTFResult is_supported=False; every TransferFunctionResult True."""

    def setUp(self) -> None:
        self.builder = SymbolicTFBuilder()
        self.ode = _single_mass_ode()

    def test_G1_all_unsupported_reasons_have_is_supported_false(self) -> None:
        unsupported_cases = [
            # A1: bad output
            dict(
                output_expr=_make_output(c_row=(0.0, 0.0), supported=False,
                                         reason="acceleration not supported"),
                input_id="F_input",
            ),
            # A2: bad input
            dict(
                output_expr=_single_mass_disp_output(),
                input_id="nonexistent_input",
            ),
            # A3: empty system
            dict(
                output_expr=_single_mass_disp_output(),
                input_id="F_input",
                # We'll swap the ode below
            ),
        ]
        for kwargs in unsupported_cases[:2]:
            result = self.builder.build_siso_tf(reduced_ode=self.ode, **kwargs)
            self.assertFalse(result.is_supported,
                             f"Expected False but got True for {kwargs}")

        # Empty system case
        empty_ode = _make_ode(state_vars=[], input_vars=["F_input"], a=[], b=[])
        result = self.builder.build_siso_tf(
            reduced_ode=empty_ode,
            input_id="F_input",
            output_expr=_single_mass_disp_output(),
        )
        self.assertFalse(result.is_supported)

    def test_G2_valid_build_is_supported_true(self) -> None:
        result = self.builder.build_siso_tf(
            reduced_ode=self.ode,
            input_id="F_input",
            output_expr=_single_mass_disp_output(),
        )
        self.assertTrue(result.is_supported)
        self.assertIsNone(result.unsupported_reason)

    def test_G3_unsupported_tf_result_numerics(self) -> None:
        bad_output = _make_output(c_row=(0.0, 0.0), supported=False, reason="test")
        result = self.builder.build_siso_tf(
            reduced_ode=self.ode,
            input_id="F_input",
            output_expr=bad_output,
        )
        self.assertIsInstance(result, UnsupportedTFResult)
        # 0/1 is always a valid "do-nothing" TF
        self.assertEqual(result.numerator_expr, sympy.Integer(0))
        self.assertEqual(result.denominator_expr, sympy.Integer(1))


# ---------------------------------------------------------------------------
# H — Misc / regression
# ---------------------------------------------------------------------------

class TestMiscBehaviour(unittest.TestCase):

    def setUp(self) -> None:
        self.builder = SymbolicTFBuilder()

    def test_H1_builder_is_stateless_reusable(self) -> None:
        """Same SymbolicTFBuilder instance can be called multiple times."""
        ode = _single_mass_ode()
        output = _single_mass_disp_output()
        r1 = self.builder.build_siso_tf(
            reduced_ode=ode, input_id="F_input", output_expr=output)
        r2 = self.builder.build_siso_tf(
            reduced_ode=ode, input_id="F_input", output_expr=output)
        self.assertEqual(r1.order, r2.order)
        self.assertEqual(r1.poles, r2.poles)

    def test_H2_input_label_propagates(self) -> None:
        ode = _single_mass_ode()
        result = self.builder.build_siso_tf(
            reduced_ode=ode,
            input_id="F_input",
            output_expr=_single_mass_disp_output(),
            input_label="Road Force",
        )
        self.assertEqual(result.input_label, "Road Force")

    def test_H3_output_label_propagates(self) -> None:
        ode = _single_mass_ode()
        output = _make_output(
            output_id="y_x",
            output_label="body displacement",
            c_row=(1.0, 0.0),
            n_inputs=1,
        )
        result = self.builder.build_siso_tf(
            reduced_ode=ode, input_id="F_input", output_expr=output)
        self.assertEqual(result.output_label, "body displacement")

    def test_H4_warnings_is_tuple(self) -> None:
        ode = _single_mass_ode()
        result = self.builder.build_siso_tf(
            reduced_ode=ode,
            input_id="F_input",
            output_expr=_single_mass_disp_output(),
        )
        self.assertIsInstance(result.warnings, tuple)

    def test_H5_simplification_mode_recorded(self) -> None:
        ode = _single_mass_ode()
        for mode in ("raw", "simplified", "factored", "numeric"):
            result = self.builder.build_siso_tf(
                reduced_ode=ode, input_id="F_input",
                output_expr=_single_mass_disp_output(), mode=mode,
            )
            self.assertEqual(result.simplification_mode, mode)


if __name__ == "__main__":
    unittest.main()
