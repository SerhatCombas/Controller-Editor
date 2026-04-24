"""Tests for ReducerParityHarness and ReducerParityReport (Wave 1, Commit 6).

Tests that the harness correctly:
- Respects ParityMode (OFF / SHADOW / PRIMARY)
- Returns correct authoritative reducer result per mode
- Detects matrix divergences between legacy and polymorphic reducers
- Returns None report in OFF mode (zero overhead)
- Returns a populated report in SHADOW and PRIMARY modes
"""
from __future__ import annotations

import unittest


def _make_graph():
    """Build a simple single-mass graph for harness tests."""
    from app.core.graph.system_graph import SystemGraph
    from app.core.models.mechanical import Mass, Spring, Damper, MechanicalGround
    from app.core.models.sources import StepForce

    g = SystemGraph()
    m = g.add_component(Mass("mass", mass=2.0))
    k = g.add_component(Spring("spring", stiffness=10.0))
    d = g.add_component(Damper("damper", damping=3.0))
    src = g.add_component(StepForce("force", amplitude=1.0))
    gnd = g.add_component(MechanicalGround("ground"))

    g.connect(m.port("port_a").id, k.port("port_a").id)
    g.connect(m.port("port_a").id, d.port("port_a").id)
    g.connect(m.port("port_a").id, src.port("port").id)
    g.connect(k.port("port_b").id, gnd.port("port").id)
    g.connect(d.port("port_b").id, gnd.port("port").id)
    g.connect(m.port("reference_port").id, gnd.port("port").id)
    g.connect(src.port("reference_port").id, gnd.port("port").id)
    return g


def _make_symbolic_for_legacy(graph):
    from app.core.symbolic.equation_builder import EquationBuilder
    from app.core.symbolic.symbolic_system import SymbolicSystem

    eb = EquationBuilder()
    comp_records = eb._build_component_records(graph)
    var_reg = eb._build_variable_registry(
        graph=graph,
        state_variables=["x_mass", "v_mass"],
        input_variables=["u_force"],
        parameters={},
    )
    deriv_links = {
        v: rec["derivative_id"]
        for v, rec in var_reg.items()
        if rec.get("kind") == "state" and rec.get("derivative_id") is not None
    }
    return SymbolicSystem(
        state_variables=["x_mass", "v_mass"],
        input_variables=["u_force"],
        output_definitions={},
        variable_registry=var_reg,
        metadata={"component_records": comp_records, "derivative_links": deriv_links, "output_records": {}},
    )


# ---------------------------------------------------------------------------
# ReducerParityReport dataclass
# ---------------------------------------------------------------------------

class TestReducerParityReport(unittest.TestCase):

    def test_has_divergence_false_when_all_ok(self):
        from app.core.symbolic.parity_report import MatrixParity, ReducerParityReport
        mp = MatrixParity(
            name="M", shape_legacy=(1, 1), shape_poly=(1, 1),
            shapes_match=True, max_abs_error=0.0,
            within_tolerance=True, tolerance=1e-9,
        )
        report = ReducerParityReport(
            all_within_tolerance=True,
            matrix_parities=[mp],
            issues=[],
        )
        self.assertFalse(report.has_divergence())

    def test_has_divergence_true_when_issue_present(self):
        from app.core.symbolic.parity_report import ReducerParityReport
        report = ReducerParityReport(
            all_within_tolerance=True,
            issues=["Matrix M divergence"],
        )
        self.assertTrue(report.has_divergence())

    def test_has_divergence_true_when_not_within_tolerance(self):
        from app.core.symbolic.parity_report import ReducerParityReport
        report = ReducerParityReport(all_within_tolerance=False, issues=[])
        self.assertTrue(report.has_divergence())

    def test_summary_pass(self):
        from app.core.symbolic.parity_report import ReducerParityReport
        report = ReducerParityReport(
            graph_id="test_graph",
            parity_mode="shadow",
            all_within_tolerance=True,
            state_variables_match=True,
            issues=[],
        )
        summary = report.summary()
        self.assertIn("PASS", summary)
        self.assertIn("test_graph", summary)

    def test_summary_fail(self):
        from app.core.symbolic.parity_report import ReducerParityReport
        report = ReducerParityReport(all_within_tolerance=False, issues=["bad"])
        self.assertIn("FAIL", report.summary())


# ---------------------------------------------------------------------------
# MatrixParity
# ---------------------------------------------------------------------------

class TestMatrixParity(unittest.TestCase):

    def test_frozen(self):
        from app.core.symbolic.parity_report import MatrixParity
        mp = MatrixParity(
            name="M", shape_legacy=(1, 1), shape_poly=(1, 1),
            shapes_match=True, max_abs_error=0.0,
            within_tolerance=True, tolerance=1e-9,
        )
        with self.assertRaises((AttributeError, TypeError)):
            mp.max_abs_error = 99.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ReducerParityHarness — ParityMode.OFF
# ---------------------------------------------------------------------------

class TestHarnessOff(unittest.TestCase):

    def _harness(self):
        from app.core.symbolic.reducer_parity_harness import ReducerParityHarness
        from app.core.state.feature_flags import FeatureFlags, ParityMode
        flags = FeatureFlags(parity_mode=ParityMode.OFF)
        return ReducerParityHarness(flags=flags)

    def test_off_returns_none_report(self):
        graph = _make_graph()
        sym = _make_symbolic_for_legacy(graph)
        _, report = self._harness().reduce(graph, sym)
        self.assertIsNone(report)

    def test_off_returns_legacy_result(self):
        from app.core.symbolic.symbolic_system import ReducedODESystem
        graph = _make_graph()
        sym = _make_symbolic_for_legacy(graph)
        result, _ = self._harness().reduce(graph, sym)
        self.assertIsInstance(result, ReducedODESystem)

    def test_off_mass_matrix_correct(self):
        graph = _make_graph()
        sym = _make_symbolic_for_legacy(graph)
        result, _ = self._harness().reduce(graph, sym)
        self.assertAlmostEqual(result.mass_matrix[0][0], 2.0)


# ---------------------------------------------------------------------------
# ReducerParityHarness — ParityMode.SHADOW
# ---------------------------------------------------------------------------

class TestHarnessShadow(unittest.TestCase):

    def _harness(self):
        from app.core.symbolic.reducer_parity_harness import ReducerParityHarness
        from app.core.state.feature_flags import FeatureFlags, ParityMode
        flags = FeatureFlags(parity_mode=ParityMode.SHADOW)
        return ReducerParityHarness(flags=flags)

    def test_shadow_returns_report(self):
        from app.core.symbolic.parity_report import ReducerParityReport
        graph = _make_graph()
        sym = _make_symbolic_for_legacy(graph)
        _, report = self._harness().reduce(graph, sym)
        self.assertIsNotNone(report)
        self.assertIsInstance(report, ReducerParityReport)

    def test_shadow_authoritative_is_legacy(self):
        """In SHADOW mode, legacy reducer's result is returned."""
        from app.core.symbolic.dae_reducer import DAEReducer
        graph = _make_graph()
        sym = _make_symbolic_for_legacy(graph)
        result, _ = self._harness().reduce(graph, sym)
        # Legacy produces M=[[2.0]]
        self.assertAlmostEqual(result.mass_matrix[0][0], 2.0)
        self.assertEqual(result.metadata.get("reduction_type"), "linear_mechanical_template")

    def test_shadow_report_parity_mode(self):
        graph = _make_graph()
        sym = _make_symbolic_for_legacy(graph)
        _, report = self._harness().reduce(graph, sym)
        self.assertEqual(report.parity_mode, "shadow")

    def test_shadow_single_mass_all_pass(self):
        """Single-mass system: both reducers produce identical results → no issues."""
        graph = _make_graph()
        sym = _make_symbolic_for_legacy(graph)
        _, report = self._harness().reduce(graph, sym, graph_id="single_mass")
        self.assertFalse(report.has_divergence(), msg=f"Unexpected divergence: {report.issues}")
        self.assertTrue(report.all_within_tolerance)
        self.assertEqual(report.issues, [])

    def test_shadow_report_has_six_matrices(self):
        """Report covers M, D, K, B, A, b."""
        graph = _make_graph()
        sym = _make_symbolic_for_legacy(graph)
        _, report = self._harness().reduce(graph, sym)
        matrix_names = {mp.name for mp in report.matrix_parities}
        self.assertEqual(matrix_names, {"M", "D", "K", "B", "A", "b"})

    def test_shadow_graph_id_propagated(self):
        graph = _make_graph()
        sym = _make_symbolic_for_legacy(graph)
        _, report = self._harness().reduce(graph, sym, graph_id="my_test_graph")
        self.assertEqual(report.graph_id, "my_test_graph")

    def test_shadow_state_variables_match(self):
        graph = _make_graph()
        sym = _make_symbolic_for_legacy(graph)
        _, report = self._harness().reduce(graph, sym)
        self.assertTrue(report.state_variables_match)


# ---------------------------------------------------------------------------
# ReducerParityHarness — ParityMode.PRIMARY
# ---------------------------------------------------------------------------

class TestHarnessPrimary(unittest.TestCase):

    def _harness(self):
        from app.core.symbolic.reducer_parity_harness import ReducerParityHarness
        from app.core.state.feature_flags import FeatureFlags, ParityMode
        flags = FeatureFlags(parity_mode=ParityMode.PRIMARY)
        return ReducerParityHarness(flags=flags)

    def test_primary_returns_poly_result(self):
        """In PRIMARY mode, polymorphic reducer's result is returned."""
        graph = _make_graph()
        sym = _make_symbolic_for_legacy(graph)
        result, _ = self._harness().reduce(graph, sym)
        # Polymorphic reducer tags its output with reduction_type
        self.assertEqual(result.metadata.get("reduction_type"), "polymorphic_linear_mechanical")

    def test_primary_returns_report(self):
        from app.core.symbolic.parity_report import ReducerParityReport
        graph = _make_graph()
        sym = _make_symbolic_for_legacy(graph)
        _, report = self._harness().reduce(graph, sym)
        self.assertIsNotNone(report)
        self.assertIsInstance(report, ReducerParityReport)

    def test_primary_single_mass_no_divergence(self):
        graph = _make_graph()
        sym = _make_symbolic_for_legacy(graph)
        _, report = self._harness().reduce(graph, sym)
        self.assertFalse(report.has_divergence(), msg=f"Unexpected divergence: {report.issues}")


# ---------------------------------------------------------------------------
# ReducerParityHarness — divergence detection
# ---------------------------------------------------------------------------

class TestHarnessDivergenceDetection(unittest.TestCase):
    """Inject a broken reducer to confirm the harness catches divergences."""

    def test_harness_catches_mass_matrix_divergence(self):
        from app.core.symbolic.reducer_parity_harness import ReducerParityHarness
        from app.core.symbolic.dae_reducer import DAEReducer
        from app.core.symbolic.polymorphic_dae_reducer import PolymorphicDAEReducer
        from app.core.state.feature_flags import FeatureFlags, ParityMode
        from app.core.symbolic.symbolic_system import ReducedODESystem

        class _BrokenPoly(PolymorphicDAEReducer):
            """Returns wrong mass matrix (99.0 instead of 2.0)."""
            def reduce(self, graph, symbolic_system):
                result = super().reduce(graph, symbolic_system)
                # Patch: corrupt the mass matrix
                broken_m = [[99.0]]  # should be [[2.0]]
                return ReducedODESystem(
                    state_variables=result.state_variables,
                    input_variables=result.input_variables,
                    output_definitions=result.output_definitions,
                    mass_matrix=broken_m,
                    damping_matrix=result.damping_matrix,
                    stiffness_matrix=result.stiffness_matrix,
                    input_matrix=result.input_matrix,
                    first_order_a=result.first_order_a,
                    first_order_b=result.first_order_b,
                    node_order=result.node_order,
                    metadata=result.metadata,
                )

        flags = FeatureFlags(parity_mode=ParityMode.SHADOW)
        harness = ReducerParityHarness(
            flags=flags,
            poly_reducer=_BrokenPoly(),
        )
        graph = _make_graph()
        sym = _make_symbolic_for_legacy(graph)
        _, report = harness.reduce(graph, sym)

        self.assertTrue(report.has_divergence())
        m_parity = next(mp for mp in report.matrix_parities if mp.name == "M")
        self.assertFalse(m_parity.within_tolerance)
        self.assertGreater(m_parity.max_abs_error, 90.0)
        self.assertTrue(any("M" in issue for issue in report.issues))


# ---------------------------------------------------------------------------
# FeatureFlags injection — verify DEFAULT_FLAGS wires to OFF mode
# ---------------------------------------------------------------------------

class TestFeatureFlagsInjection(unittest.TestCase):

    def test_default_flags_gives_primary_mode_harness(self):
        """Wave 2 cutover: DEFAULT_FLAGS.parity_mode == PRIMARY."""
        from app.core.symbolic.reducer_parity_harness import ReducerParityHarness
        from app.core.state.feature_flags import DEFAULT_FLAGS, ParityMode
        h = ReducerParityHarness(flags=DEFAULT_FLAGS)
        # After Wave 2 PRIMARY cutover, default is PRIMARY
        self.assertEqual(h._flags.parity_mode, ParityMode.PRIMARY)

    def test_development_flags_gives_shadow_mode_harness(self):
        from app.core.symbolic.reducer_parity_harness import ReducerParityHarness
        from app.core.state.feature_flags import DEVELOPMENT_FLAGS, ParityMode
        h = ReducerParityHarness(flags=DEVELOPMENT_FLAGS)
        self.assertEqual(h._flags.parity_mode, ParityMode.SHADOW)

    def test_report_metadata_includes_tolerance(self):
        from app.core.symbolic.reducer_parity_harness import ReducerParityHarness
        from app.core.state.feature_flags import FeatureFlags, ParityMode
        h = ReducerParityHarness(
            flags=FeatureFlags(parity_mode=ParityMode.SHADOW),
            tolerance=1e-6,
        )
        graph = _make_graph()
        sym = _make_symbolic_for_legacy(graph)
        _, report = h.reduce(graph, sym)
        self.assertAlmostEqual(report.metadata["tolerance"], 1e-6)


if __name__ == "__main__":
    unittest.main()
