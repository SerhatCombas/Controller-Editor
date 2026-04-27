"""TF golden tests — Wave 3A update.

Uses real templates (PolymorphicDAEReducer + OutputMapper + SymbolicTFBuilder)
to verify that the full pipeline produces physically correct transfer functions.

Three golden systems
────────────────────
  single_mass  m=2, k=10, d=3, force input
      H_disp(s)  = 1/(2s²+3s+10)
      H_accel(s) = s²/(2s²+3s+10)  [Wave 3A: DERIVED_DYNAMIC, D≠0]
      H_force(s) = k·H_disp(s) = 10/(2s²+3s+10)  [Wave 3A: DERIVED_ALGEBRAIC]

  two_mass     m1=2, m2=1; k_g=20, d_g=5, k_c=8, d_c=2; force on mass_1
      order=4, 4 poles, is_strictly_proper (displacement output)

  quarter_car  mb=300, mw=40; ks=15000, ds=1200; kt=180000
      road→body_disp: order=4, 4 poles, is_strictly_proper
      road→body_accel: proper (D≠0), supported (Wave 3A)
      force → UnsupportedTFResult without graph (Gate-6 honesty check)
      tire_deflection → UnsupportedTFResult (reference not a DOF)

Physical invariants checked
───────────────────────────
  * Pole count = system order = 2 × DOF count
  * All physical (passive) poles have Re(pole) < 0
  * Displacement-output TFs are strictly proper
  * Acceleration TFs are proper (not strictly proper) — direct feedthrough via D
  * DC gain of acceleration = 0 (static force → zero acceleration at steady state)
  * Force TFs proportional to displacement TFs (F = k·x relationship)
  * DC gain (s→0) of body displacement from road input > 0 (road rises → body rises)
"""
from __future__ import annotations

import unittest
import sympy

from tests.fixtures.graph_factories import build_single_mass_template_def as build_single_mass_template
from tests.fixtures.graph_factories import build_two_mass_template_def as build_two_mass_template
from tests.fixtures.minimal_wheel_road import build_wheel_road_graph
from app.core.templates.template_definition import TemplateDefinition
from app.core.symbolic.polymorphic_dae_reducer import PolymorphicDAEReducer


def _build_quarter_car_fixture():
    graph = build_wheel_road_graph()
    return TemplateDefinition(
        id="quarter_car", name="Quarter-Car Suspension", graph=graph,
        default_input_id="road_source", default_output_id="body_displacement",
    )

build_quarter_car_template = _build_quarter_car_fixture
from app.core.symbolic.output_mapper import OutputMapper
from app.core.symbolic.tf_builder import (
    SymbolicTFBuilder,
    TransferFunctionResult,
    UnsupportedTFResult,
    s as S,
)


# ---------------------------------------------------------------------------
# Minimal SymbolicSystem stub (bypasses EquationBuilder sandbox bug)
# ---------------------------------------------------------------------------

class _StubSymbolicSystem:
    output_definitions: dict = {}
    algebraic_constraints: list = []
    metadata: dict = {}


# ---------------------------------------------------------------------------
# Pipeline helper
# ---------------------------------------------------------------------------

def _build_ode(template_fn):
    """Run template → PolymorphicDAEReducer → ReducedODESystem."""
    template = template_fn()
    reducer = PolymorphicDAEReducer()
    return reducer.reduce(template.graph, _StubSymbolicSystem()), template.graph


def _map(probe, ode, graph=None):
    return OutputMapper().map(probe, ode, graph=graph)


def _build_tf(ode, input_id, probe, graph=None):
    output_expr = _map(probe, ode, graph=graph)
    builder = SymbolicTFBuilder()
    return builder.build_siso_tf(
        reduced_ode=ode,
        input_id=input_id,
        output_expr=output_expr,
    ), output_expr


def _dc_gain(result: TransferFunctionResult) -> float:
    """Evaluate H(0) — DC gain."""
    num_at_0 = float(result.numerator_expr.subs(S, 0))
    den_at_0 = float(result.denominator_expr.subs(S, 0))
    return num_at_0 / den_at_0


# ---------------------------------------------------------------------------
# Single-mass golden tests
# ---------------------------------------------------------------------------

class TestSingleMassGolden(unittest.TestCase):
    """
    Template: m=2, k=10, d=3, one force input.
    Expected H_disp(s) = 0.5/(s²+1.5s+5) = 1/(2s²+3s+10).
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.ode, cls.graph = _build_ode(build_single_mass_template)
        cls.input_id = "f_input_force_out"
        cls.disp_probe = cls.graph.probes["mass_displacement"]
        cls.accel_probe = cls.graph.probes["mass_acceleration"]
        cls.force_probe = cls.graph.probes["spring_force"]
        cls.builder = SymbolicTFBuilder()
        cls.mapper = OutputMapper()

    def _build(self, probe):
        return self.builder.build_siso_tf(
            reduced_ode=self.ode,
            input_id=self.input_id,
            output_expr=self.mapper.map(probe, self.ode),
        )

    # --- Structural checks ---

    def test_SM_01_displacement_output_is_supported(self) -> None:
        result = self._build(self.disp_probe)
        self.assertIsInstance(result, TransferFunctionResult)
        self.assertTrue(result.is_supported)

    def test_SM_02_order_2(self) -> None:
        result = self._build(self.disp_probe)
        self.assertEqual(result.order, 2)

    def test_SM_03_strictly_proper(self) -> None:
        result = self._build(self.disp_probe)
        self.assertTrue(result.is_strictly_proper)

    def test_SM_04_two_poles(self) -> None:
        result = self._build(self.disp_probe)
        self.assertEqual(len(result.poles), 2)

    def test_SM_05_all_poles_stable(self) -> None:
        """All poles of a passive (energy-dissipating) system are stable Re<0."""
        result = self._build(self.disp_probe)
        for pole in result.poles:
            real_part = float(sympy.re(pole))
            self.assertLess(real_part, 0.0,
                            f"Unstable pole {pole!r}: Re={real_part}")

    def test_SM_06_tf_ratio_at_s1(self) -> None:
        """H(1) = 0.5/(1+1.5+5) = 0.5/7.5 = 1/15."""
        result = self._build(self.disp_probe)
        num_val = float(result.numerator_expr.subs(S, 1))
        den_val = float(result.denominator_expr.subs(S, 1))
        h_at_1 = num_val / den_val
        expected = 0.5 / 7.5  # = 1/15
        self.assertAlmostEqual(h_at_1, expected, places=10)

    def test_SM_07_tf_ratio_at_s2(self) -> None:
        """H(2) = 0.5/(4+3+5) = 0.5/12 = 1/24."""
        result = self._build(self.disp_probe)
        num_val = float(result.numerator_expr.subs(S, 2))
        den_val = float(result.denominator_expr.subs(S, 2))
        h_at_2 = num_val / den_val
        expected = 0.5 / 12.0
        self.assertAlmostEqual(h_at_2, expected, places=10)

    def test_SM_08_positive_dc_gain(self) -> None:
        """H(0) = 0.5/5 = 0.1 (positive: static force → positive displacement)."""
        result = self._build(self.disp_probe)
        dc = _dc_gain(result)
        self.assertAlmostEqual(dc, 0.1, places=10)

    def test_SM_09_system_class_1DOF(self) -> None:
        result = self._build(self.disp_probe)
        self.assertEqual(result.system_class, "SISO-1DOF")

    # --- Wave 3A: acceleration output (DERIVED_DYNAMIC, now supported) ---

    def test_SM_10_acceleration_probe_is_supported(self) -> None:
        """Wave 3A: acceleration uses c_row=A[vel_idx], d_row=B[vel_idx] → supported."""
        result = self._build(self.accel_probe)
        self.assertIsInstance(result, TransferFunctionResult)
        self.assertTrue(result.is_supported)

    def test_SM_10b_acceleration_tf_is_proper_not_strictly(self) -> None:
        """H_accel(s) = s²/(2s²+3s+10): proper but not strictly (D≠0)."""
        result = self._build(self.accel_probe)
        self.assertTrue(result.is_proper)
        self.assertFalse(result.is_strictly_proper)

    def test_SM_10c_acceleration_dc_gain_is_zero(self) -> None:
        """H_accel(0) = 0: static force causes zero steady-state acceleration."""
        result = self._build(self.accel_probe)
        num_at_0 = float(result.numerator_expr.subs(S, 0))
        self.assertAlmostEqual(num_at_0, 0.0, places=10)

    def test_SM_10d_acceleration_tf_numerator_at_s1(self) -> None:
        """H_accel(1) = 1/(2+3+10) = 1/15 (same ratio as H_disp since ÿ = s²·x in s-domain)."""
        result = self._build(self.accel_probe)
        num_val = float(result.numerator_expr.subs(S, 1))
        den_val = float(result.denominator_expr.subs(S, 1))
        self.assertAlmostEqual(num_val / den_val, 1.0 / 15.0, places=10)

    # --- Gate-6: force without graph is unsupported ---

    def test_SM_11_force_probe_returns_unsupported_without_graph(self) -> None:
        """Gate-6: spring force without graph context must return UnsupportedTFResult."""
        result = self._build(self.force_probe)
        self.assertIsInstance(result, UnsupportedTFResult)
        self.assertFalse(result.is_supported)

    def test_SM_12_force_without_graph_has_zero_c_row(self) -> None:
        """Gate-6 honesty: force without graph → zero C row."""
        expr = self.mapper.map(self.force_probe, self.ode)
        self.assertFalse(expr.supported_for_tf)
        self.assertTrue(all(v == 0.0 for v in expr.c_row),
                        f"Non-zero C row for {self.force_probe.name}: {expr.c_row}")

    # --- Wave 3A: force output with graph (DERIVED_ALGEBRAIC) ---

    def test_SM_13_spring_force_with_graph_is_supported(self) -> None:
        """Wave 3A: spring force F=k·x is supported when graph is provided."""
        result = self.builder.build_siso_tf(
            reduced_ode=self.ode,
            input_id=self.input_id,
            output_expr=self.mapper.map(self.force_probe, self.ode, graph=self.graph),
        )
        self.assertIsInstance(result, TransferFunctionResult)
        self.assertTrue(result.is_supported)

    def test_SM_13b_spring_force_dc_gain_positive(self) -> None:
        """H_force(0) = k/k_eff = 10/10 = 1.0 (static force → static spring force)."""
        result = self.builder.build_siso_tf(
            reduced_ode=self.ode,
            input_id=self.input_id,
            output_expr=self.mapper.map(self.force_probe, self.ode, graph=self.graph),
        )
        dc = _dc_gain(result)
        # H_force(s) = k · H_disp(s) = 10/(2s²+3s+10) → H_force(0) = 10/10 = 1.0
        self.assertAlmostEqual(dc, 1.0, places=8)


# ---------------------------------------------------------------------------
# Two-mass golden tests
# ---------------------------------------------------------------------------

class TestTwoMassGolden(unittest.TestCase):
    """
    Template: m1=2, m2=1; spring/damper from ground + coupling.
    Force applied to mass_1.
    4-state system → order 4.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.ode, cls.graph = _build_ode(build_two_mass_template)
        cls.input_id = "f_input_force_out"
        # Infer displacement probes from state_variable names
        # state_variables = ['x_mass_1', 'x_mass_2', 'v_mass_1', 'v_mass_2']

    def _c_row_for_state(self, state_name: str) -> tuple[float, ...]:
        """Build a C row that picks out one state variable."""
        svs = self.ode.state_variables
        c = tuple(1.0 if sv == state_name else 0.0 for sv in svs)
        return c

    def _make_output_expr(self, state_name: str):
        from app.core.symbolic.output_mapper import OutputExpression
        c = self._c_row_for_state(state_name)
        d = tuple(0.0 for _ in self.ode.input_variables)
        idx = tuple(i for i, v in enumerate(c) if v != 0.0)
        names = tuple(self.ode.state_variables[i] for i in idx)
        return OutputExpression(
            output_id=state_name,
            output_label=state_name,
            quantity_type="displacement",
            c_row=c,
            d_row=d,
            supported_for_tf=True,
            unsupported_reason=None,
            contributing_state_indices=idx,
            contributing_state_names=names,
            provenance=("test",),
        )

    def test_TM_01_order_4_for_mass1_disp(self) -> None:
        output = self._make_output_expr("x_mass_1")
        builder = SymbolicTFBuilder()
        result = builder.build_siso_tf(
            reduced_ode=self.ode,
            input_id=self.input_id,
            output_expr=output,
        )
        self.assertTrue(result.is_supported)
        self.assertEqual(result.order, 4, f"Two-mass should give order 4, got {result.order}")

    def test_TM_02_four_poles(self) -> None:
        output = self._make_output_expr("x_mass_2")
        result = SymbolicTFBuilder().build_siso_tf(
            reduced_ode=self.ode,
            input_id=self.input_id,
            output_expr=output,
        )
        self.assertEqual(len(result.poles), 4,
                         f"Expected 4 poles for 2-DOF, got {result.poles}")

    def test_TM_03_strictly_proper_displacement_output(self) -> None:
        output = self._make_output_expr("x_mass_1")
        result = SymbolicTFBuilder().build_siso_tf(
            reduced_ode=self.ode,
            input_id=self.input_id,
            output_expr=output,
        )
        self.assertTrue(result.is_strictly_proper,
                        "Displacement output of force-input system must be strictly proper")

    def test_TM_04_all_poles_stable(self) -> None:
        """Passive mass-spring-damper with positive k,d: all poles Re<0."""
        output = self._make_output_expr("x_mass_1")
        result = SymbolicTFBuilder().build_siso_tf(
            reduced_ode=self.ode,
            input_id=self.input_id,
            output_expr=output,
        )
        for pole in result.poles:
            real_part = float(sympy.re(pole))
            self.assertLess(real_part, 0.0,
                            f"Unstable pole {pole!r}: Re={real_part}")

    def test_TM_05_system_class_2DOF(self) -> None:
        output = self._make_output_expr("x_mass_1")
        result = SymbolicTFBuilder().build_siso_tf(
            reduced_ode=self.ode,
            input_id=self.input_id,
            output_expr=output,
        )
        self.assertEqual(result.system_class, "SISO-2DOF")

    def test_TM_06_mass2_disp_tf_is_supported(self) -> None:
        output = self._make_output_expr("x_mass_2")
        result = SymbolicTFBuilder().build_siso_tf(
            reduced_ode=self.ode,
            input_id=self.input_id,
            output_expr=output,
        )
        self.assertTrue(result.is_supported)
        self.assertEqual(result.order, 4)


# ---------------------------------------------------------------------------
# Quarter-car golden tests
# ---------------------------------------------------------------------------

class TestQuarterCarGolden(unittest.TestCase):
    """
    Template: mb=300, mw=40, ks=15000, ds=1200, kt=180000.
    Two inputs: r_road_source (disp), f_body_force_out (force).
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.ode, cls.graph = _build_ode(build_quarter_car_template)
        cls.road_input_id = "r_road_source"
        cls.force_input_id = "f_body_force_out"
        cls.mapper = OutputMapper()
        cls.builder = SymbolicTFBuilder()

        cls.body_disp_probe = cls.graph.probes["body_displacement"]
        cls.wheel_disp_probe = cls.graph.probes["wheel_displacement"]
        cls.body_accel_probe = cls.graph.probes["body_acceleration"]
        cls.susp_force_probe = cls.graph.probes["suspension_force"]
        cls.susp_defl_probe = cls.graph.probes["suspension_deflection"]
        cls.tire_defl_probe = cls.graph.probes["tire_deflection"]

    def _build(self, input_id, probe) -> TransferFunctionResult | UnsupportedTFResult:
        return self.builder.build_siso_tf(
            reduced_ode=self.ode,
            input_id=input_id,
            output_expr=self.mapper.map(probe, self.ode),
        )

    # --- Road to body ---

    def test_QC_01_road_to_body_disp_is_supported(self) -> None:
        result = self._build(self.road_input_id, self.body_disp_probe)
        self.assertIsInstance(result, TransferFunctionResult)
        self.assertTrue(result.is_supported)

    def test_QC_02_road_to_body_order_4(self) -> None:
        result = self._build(self.road_input_id, self.body_disp_probe)
        self.assertEqual(result.order, 4,
                         "Quarter-car 2-DOF: road→body should be 4th order")

    def test_QC_03_road_to_body_strictly_proper(self) -> None:
        result = self._build(self.road_input_id, self.body_disp_probe)
        self.assertTrue(result.is_strictly_proper)

    def test_QC_04_road_to_body_four_poles(self) -> None:
        result = self._build(self.road_input_id, self.body_disp_probe)
        self.assertEqual(len(result.poles), 4)

    def test_QC_05_road_to_body_all_poles_stable(self) -> None:
        result = self._build(self.road_input_id, self.body_disp_probe)
        for pole in result.poles:
            real_part = float(sympy.re(pole))
            self.assertLess(real_part, 0.0,
                            f"Unstable pole {pole!r}: Re={real_part}")

    def test_QC_06_road_to_body_positive_dc_gain(self) -> None:
        """DC gain > 0: sustained road height elevation → body rises."""
        result = self._build(self.road_input_id, self.body_disp_probe)
        self.assertIsInstance(result, TransferFunctionResult)
        dc = _dc_gain(result)
        self.assertGreater(dc, 0.0,
                           f"DC gain should be positive (road up → body up), got {dc}")

    def test_QC_07_road_to_body_dc_gain_equals_1(self) -> None:
        """DC gain of road→body for a fully rigid system should be 1.0 (statics).
        With damper ds>0 and both springs, the static body displacement
        equals the road displacement (stiffness ratio 1 at DC).
        H(0) = B[j][0] * (−A)^{-1} * C^T  evaluated at static equilibrium.
        For a grounded-reference system: numerator(0)/denominator(0) = 1."""
        result = self._build(self.road_input_id, self.body_disp_probe)
        dc = _dc_gain(result)
        self.assertAlmostEqual(dc, 1.0, places=6,
                               msg=f"DC gain road→body should be 1.0, got {dc}")

    # --- Road to wheel ---

    def test_QC_08_road_to_wheel_disp_is_supported(self) -> None:
        result = self._build(self.road_input_id, self.wheel_disp_probe)
        self.assertIsInstance(result, TransferFunctionResult)
        self.assertTrue(result.is_supported)

    def test_QC_09_road_to_wheel_order_4(self) -> None:
        result = self._build(self.road_input_id, self.wheel_disp_probe)
        self.assertEqual(result.order, 4)

    def test_QC_10_road_to_wheel_strictly_proper(self) -> None:
        result = self._build(self.road_input_id, self.wheel_disp_probe)
        self.assertTrue(result.is_strictly_proper)

    # --- Suspension deflection (relative: x_body - x_wheel) ---

    def test_QC_11_suspension_deflection_is_supported(self) -> None:
        """x_body - x_wheel: both are active DOFs → supported."""
        result = self._build(self.road_input_id, self.susp_defl_probe)
        self.assertIsInstance(result, TransferFunctionResult,
                              "suspension_deflection (body-wheel relative) must be supported")
        self.assertTrue(result.is_supported)

    def test_QC_12_suspension_deflection_order_4(self) -> None:
        result = self._build(self.road_input_id, self.susp_defl_probe)
        self.assertEqual(result.order, 4)

    # --- Wave 3A: acceleration output (DERIVED_DYNAMIC, now supported) ---

    def test_QC_13_acceleration_probe_is_supported(self) -> None:
        """Wave 3A: body acceleration uses c_row=A[vel_idx], d_row=B[vel_idx] → supported."""
        result = self._build(self.road_input_id, self.body_accel_probe)
        self.assertIsInstance(result, TransferFunctionResult)
        self.assertTrue(result.is_supported)

    def test_QC_13b_acceleration_tf_is_proper(self) -> None:
        """Body acceleration TF is proper (D≠0 → not strictly proper)."""
        result = self._build(self.road_input_id, self.body_accel_probe)
        self.assertTrue(result.is_proper)

    def test_QC_13c_acceleration_c_row_from_a_matrix(self) -> None:
        """Body acceleration c_row = first_order_a[vel_body_mass_idx]."""
        expr = self.mapper.map(self.body_accel_probe, self.ode)
        vel_idx = self.ode.state_variables.index("v_body_mass")
        for i, (cv, av) in enumerate(
            zip(expr.c_row, self.ode.first_order_a[vel_idx])
        ):
            self.assertAlmostEqual(cv, float(av), places=10,
                msg=f"c_row[{i}] mismatch for body acceleration")

    # --- Gate-6: force without graph is unsupported ---

    def test_QC_14_force_probe_returns_unsupported_without_graph(self) -> None:
        """Gate-6: spring force without graph context must return UnsupportedTFResult."""
        result = self._build(self.road_input_id, self.susp_force_probe)
        self.assertIsInstance(result, UnsupportedTFResult)
        self.assertFalse(result.is_supported)

    def test_QC_15_tire_deflection_returns_unsupported(self) -> None:
        """Tire deflection = x_wheel - x_road_source.
        road_source is a source (not a DOF) → requires D feedthrough → unsupported."""
        result = self._build(self.road_input_id, self.tire_defl_probe)
        self.assertIsInstance(result, UnsupportedTFResult)
        self.assertFalse(result.is_supported)

    def test_QC_16_gate6_zero_c_rows_for_unsupported(self) -> None:
        """Gate-6 honesty: force/tire_defl (without graph) have zero C rows."""
        for probe in [self.susp_force_probe, self.tire_defl_probe]:
            expr = self.mapper.map(probe, self.ode)
            self.assertFalse(expr.supported_for_tf,
                             f"Expected unsupported for {probe.name}")
            self.assertTrue(all(v == 0.0 for v in expr.c_row),
                            f"Non-zero C row for unsupported probe {probe.name}: {expr.c_row}")

    # --- Wave 3A: suspension force with graph (DERIVED_ALGEBRAIC) ---

    def test_QC_19_suspension_force_with_graph_is_supported(self) -> None:
        """Wave 3A: suspension spring force is supported when graph is provided."""
        result = self.builder.build_siso_tf(
            reduced_ode=self.ode,
            input_id=self.road_input_id,
            output_expr=self.mapper.map(
                self.susp_force_probe, self.ode, graph=self.graph
            ),
        )
        self.assertIsInstance(result, TransferFunctionResult)
        self.assertTrue(result.is_supported)

    def test_QC_19b_suspension_force_tf_order(self) -> None:
        """Suspension force TF road→F_susp: order = 4 (same denominator as body_disp)."""
        result = self.builder.build_siso_tf(
            reduced_ode=self.ode,
            input_id=self.road_input_id,
            output_expr=self.mapper.map(
                self.susp_force_probe, self.ode, graph=self.graph
            ),
        )
        self.assertIsInstance(result, TransferFunctionResult)
        self.assertEqual(result.order, 4)

    # --- Force input ---

    def test_QC_17_force_to_body_disp_is_supported(self) -> None:
        result = self._build(self.force_input_id, self.body_disp_probe)
        self.assertIsInstance(result, TransferFunctionResult)
        self.assertTrue(result.is_supported)
        self.assertEqual(result.order, 4)

    def test_QC_18_system_class_2DOF(self) -> None:
        result = self._build(self.road_input_id, self.body_disp_probe)
        self.assertEqual(result.system_class, "SISO-2DOF")


if __name__ == "__main__":
    unittest.main()
