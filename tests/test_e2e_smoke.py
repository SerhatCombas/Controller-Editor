"""Faz 5MVP-8 — End-to-end smoke test.

Verifies the full pipeline that MainWindowV2 would execute:
  graph factory → CompileAnalyzeService → StaticAnalysisResult
  → TF coefficient extraction → step/bode/pole-zero data readiness

This is a non-PySide6 test — it covers the same logic as clicking
"Compile & Analyze" in MainWindowV2, minus the actual Qt widgets.
"""
from __future__ import annotations

import unittest

import sympy

from app.core.state.app_state_v2 import AnalysisConfig, AppStateV2
from app.services.compile_analyze_service import CompileAnalyzeService
from app.services.static_analysis_backend import GenericStaticBackend
from app.core.symbolic.tf_builder import TransferFunctionResult, s as S
from tests.fixtures.graph_factories import (
    build_single_mass_graph,
    build_two_mass_graph,
)
from tests.fixtures.minimal_wheel_road import build_wheel_road_graph


def _tf_coeffs(tf: TransferFunctionResult):
    """Extract (num_coeffs, den_coeffs) as float lists, highest order first."""
    num_poly = sympy.Poly(tf.numerator_expr, S)
    den_poly = sympy.Poly(tf.denominator_expr, S)
    return (
        [float(c) for c in num_poly.all_coeffs()],
        [float(c) for c in den_poly.all_coeffs()],
    )


class TestSingleMassSmoke(unittest.TestCase):
    """Full pipeline: single-mass → compile → analyze → extract plot data."""

    def setUp(self):
        self.state = AppStateV2()
        self.service = CompileAnalyzeService(self.state)
        ok = self.service.analyze_graph(build_single_mass_graph())
        self.assertTrue(ok, f"Analysis failed: {self.state.analysis_error}")

    def test_state_space_matrices_present(self):
        ss = self.state.analysis_result.state_space
        self.assertEqual(len(ss.a_matrix), 2)
        self.assertEqual(len(ss.b_matrix), 2)
        self.assertGreater(len(ss.c_matrix), 0)

    def test_displacement_tf_coefficients_extractable(self):
        """Extract TF coefficients for scipy.signal consumption."""
        disp_tf = next(
            tf for tf in self.state.analysis_result.transfer_functions
            if tf.output_id == "mass_displacement"
        )
        num, den = _tf_coeffs(disp_tf)
        # H(s) = 1/(2s² + 3s + 10) → num=[0.5], den=[1.0, 1.5, 5.0]
        # (or scaled equivalently)
        self.assertEqual(len(den), 3, "2nd order denominator")
        self.assertGreater(len(num), 0)

    def test_poles_are_numeric(self):
        """Poles can be converted to complex numbers."""
        for pole in self.state.analysis_result.poles:
            c = complex(pole)
            self.assertIsInstance(c, complex)
            self.assertLess(c.real, 0, "Should be stable")

    def test_dc_gain_positive(self):
        """H(0) > 0 for force→displacement."""
        disp_tf = next(
            tf for tf in self.state.analysis_result.transfer_functions
            if tf.output_id == "mass_displacement"
        )
        num_0 = float(disp_tf.numerator_expr.subs(S, 0))
        den_0 = float(disp_tf.denominator_expr.subs(S, 0))
        dc_gain = num_0 / den_0
        self.assertGreater(dc_gain, 0)


class TestTwoMassSmoke(unittest.TestCase):
    """Full pipeline: two-mass → all TFs extractable."""

    def setUp(self):
        self.state = AppStateV2()
        self.service = CompileAnalyzeService(self.state)
        ok = self.service.analyze_graph(build_two_mass_graph())
        self.assertTrue(ok)

    def test_four_states(self):
        self.assertEqual(self.state.n_states, 4)

    def test_all_tfs_have_extractable_coefficients(self):
        for tf in self.state.analysis_result.transfer_functions:
            num, den = _tf_coeffs(tf)
            self.assertGreater(len(den), 0,
                               f"Empty denominator for {tf.output_id}")

    def test_stability_via_poles(self):
        for tf in self.state.analysis_result.transfer_functions:
            for pole in tf.poles:
                self.assertLess(
                    float(sympy.re(pole)), 0,
                    f"Unstable pole in {tf.output_id}: {pole}",
                )


class TestWheelRoadSmoke(unittest.TestCase):
    """Full pipeline: wheel-road 2-DOF → road input TFs."""

    def setUp(self):
        self.state = AppStateV2()
        self.service = CompileAnalyzeService(self.state)
        ok = self.service.analyze_graph(build_wheel_road_graph())
        self.assertTrue(ok)

    def test_four_states(self):
        self.assertEqual(self.state.n_states, 4)

    def test_body_displacement_tf_exists(self):
        body_tfs = [
            tf for tf in self.state.analysis_result.transfer_functions
            if tf.output_id == "body_displacement"
        ]
        self.assertGreater(len(body_tfs), 0)

    def test_unsupported_outputs_tracked(self):
        unsup = self.state.analysis_result.unsupported_outputs
        self.assertGreater(len(unsup), 0, "tire_deflection should be unsupported")

    def test_road_to_body_dc_gain_is_1(self):
        """Static road displacement → body follows 1:1."""
        body_tf = next(
            tf for tf in self.state.analysis_result.transfer_functions
            if tf.output_id == "body_displacement"
        )
        num_0 = float(body_tf.numerator_expr.subs(S, 0))
        den_0 = float(body_tf.denominator_expr.subs(S, 0))
        dc_gain = num_0 / den_0
        self.assertAlmostEqual(dc_gain, 1.0, places=6)


class TestRecompileWorkflow(unittest.TestCase):
    """Simulate user changing the model and recompiling."""

    def test_switch_from_single_to_two_mass(self):
        state = AppStateV2()
        service = CompileAnalyzeService(state)

        # First: single mass
        service.analyze_graph(build_single_mass_graph())
        self.assertEqual(state.n_states, 2)

        # User edits canvas, recompiles with two-mass
        service.analyze_graph(build_two_mass_graph())
        self.assertEqual(state.n_states, 4)
        self.assertTrue(state.is_stable)

    def test_reanalyze_with_selected_output(self):
        state = AppStateV2()
        service = CompileAnalyzeService(state)
        service.analyze_graph(build_single_mass_graph())

        # User selects specific output
        state.analysis_config = AnalysisConfig(
            selected_output_id="mass_displacement",
        )
        ok = service.analyze_current()
        self.assertTrue(ok)
        # Only displacement TFs
        for tf in state.analysis_result.transfer_functions:
            self.assertEqual(tf.output_id, "mass_displacement")


if __name__ == "__main__":
    unittest.main()
