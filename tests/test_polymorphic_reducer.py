"""Tests for PolymorphicDAEReducer (Wave 1, Commit 4).

Tests the reducer in isolation using stub components, then with real single-mass
and two-mass templates for integration verification.

Parity against the legacy DAEReducer is handled in test_reducer_parity.py (Commit 5).
"""
from __future__ import annotations

import unittest


# ---------------------------------------------------------------------------
# Stub helpers (duplicate-free — same pattern as test_input_router.py)
# ---------------------------------------------------------------------------

class _StubPort:
    def __init__(self, name: str, node_id: str | None = None):
        self.name = name
        self.node_id = node_id


class _StubGraph:
    def __init__(self):
        self.components: dict = {}

    def add(self, comp) -> object:
        self.components[comp.id] = comp
        return comp


def _make_empty_symbolic():
    from app.core.symbolic.symbolic_system import SymbolicSystem
    return SymbolicSystem(
        output_definitions={},
        metadata={"component_records": {}, "derivative_links": {}, "output_records": {}},
    )


# ---------------------------------------------------------------------------
# Isolated unit tests using simple real components
# ---------------------------------------------------------------------------

class TestPolymorphicReducerUnit(unittest.TestCase):
    """Reducer unit tests with real Mass / Spring / Damper instances."""

    def _setup_single_mass(self):
        """Build a minimal single-mass graph (no template dependency)."""
        from app.core.graph.system_graph import SystemGraph
        from app.core.models.mechanical import Mass, Spring, Damper, MechanicalGround
        from app.core.models.sources import StepForce

        graph = SystemGraph()
        mass = graph.add_component(Mass("mass", mass=2.0))
        spring = graph.add_component(Spring("spring", stiffness=10.0))
        damper = graph.add_component(Damper("damper", damping=3.0))
        source = graph.add_component(StepForce("force", amplitude=1.0))
        ground = graph.add_component(MechanicalGround("ground"))

        graph.connect(mass.port("port_a").id, spring.port("port_a").id)
        graph.connect(mass.port("port_a").id, damper.port("port_a").id)
        graph.connect(mass.port("port_a").id, source.port("port").id)
        graph.connect(spring.port("port_b").id, ground.port("port").id)
        graph.connect(damper.port("port_b").id, ground.port("port").id)
        graph.connect(mass.port("reference_port").id, ground.port("port").id)
        graph.connect(source.port("reference_port").id, ground.port("port").id)

        return graph

    def test_single_mass_node_index_has_one_dof(self):
        from app.core.symbolic.polymorphic_dae_reducer import PolymorphicDAEReducer
        graph = self._setup_single_mass()
        reducer = PolymorphicDAEReducer()
        components = list(reducer._iter_components(graph))
        node_order, node_index = reducer._build_node_index(components)
        self.assertEqual(len(node_order), 1)
        self.assertEqual(len(node_index), 1)

    def test_single_mass_mass_matrix_diagonal(self):
        from app.core.symbolic.polymorphic_dae_reducer import PolymorphicDAEReducer
        graph = self._setup_single_mass()
        sym = _make_empty_symbolic()
        reduced = PolymorphicDAEReducer().reduce(graph, sym)
        self.assertEqual(len(reduced.mass_matrix), 1)
        self.assertAlmostEqual(reduced.mass_matrix[0][0], 2.0)

    def test_single_mass_stiffness_matrix_diagonal(self):
        from app.core.symbolic.polymorphic_dae_reducer import PolymorphicDAEReducer
        graph = self._setup_single_mass()
        sym = _make_empty_symbolic()
        reduced = PolymorphicDAEReducer().reduce(graph, sym)
        self.assertAlmostEqual(reduced.stiffness_matrix[0][0], 10.0)

    def test_single_mass_damping_matrix_diagonal(self):
        from app.core.symbolic.polymorphic_dae_reducer import PolymorphicDAEReducer
        graph = self._setup_single_mass()
        sym = _make_empty_symbolic()
        reduced = PolymorphicDAEReducer().reduce(graph, sym)
        self.assertAlmostEqual(reduced.damping_matrix[0][0], 3.0)

    def test_single_mass_input_matrix_shape(self):
        """Single force source → B is 1×1 (force input only)."""
        from app.core.symbolic.polymorphic_dae_reducer import PolymorphicDAEReducer
        graph = self._setup_single_mass()
        sym = _make_empty_symbolic()
        reduced = PolymorphicDAEReducer().reduce(graph, sym)
        # input_matrix is (dof × n_inputs); for 1 DOF + 1 force: shape (1, 1) ... but
        # it goes into B bottom half so first_order_b is (2, 1)
        self.assertAlmostEqual(reduced.input_matrix[0][0], 1.0)

    def test_single_mass_first_order_a_shape(self):
        """A matrix for 1-DOF system is 2×2."""
        from app.core.symbolic.polymorphic_dae_reducer import PolymorphicDAEReducer
        graph = self._setup_single_mass()
        sym = _make_empty_symbolic()
        reduced = PolymorphicDAEReducer().reduce(graph, sym)
        self.assertEqual(len(reduced.first_order_a), 2)
        self.assertEqual(len(reduced.first_order_a[0]), 2)

    def test_single_mass_first_order_b_shape(self):
        """B matrix for 1-DOF system is 2×1."""
        from app.core.symbolic.polymorphic_dae_reducer import PolymorphicDAEReducer
        graph = self._setup_single_mass()
        sym = _make_empty_symbolic()
        reduced = PolymorphicDAEReducer().reduce(graph, sym)
        self.assertEqual(len(reduced.first_order_b), 2)
        self.assertEqual(len(reduced.first_order_b[0]), 1)

    def test_single_mass_state_variables(self):
        from app.core.symbolic.polymorphic_dae_reducer import PolymorphicDAEReducer
        graph = self._setup_single_mass()
        sym = _make_empty_symbolic()
        reduced = PolymorphicDAEReducer().reduce(graph, sym)
        self.assertEqual(len(reduced.state_variables), 2)
        x_states = [s for s in reduced.state_variables if s.startswith("x_")]
        v_states = [s for s in reduced.state_variables if s.startswith("v_")]
        self.assertEqual(len(x_states), 1)
        self.assertEqual(len(v_states), 1)

    def test_single_mass_input_variables(self):
        from app.core.symbolic.polymorphic_dae_reducer import PolymorphicDAEReducer
        graph = self._setup_single_mass()
        sym = _make_empty_symbolic()
        reduced = PolymorphicDAEReducer().reduce(graph, sym)
        self.assertEqual(len(reduced.input_variables), 1)
        self.assertIn("f_force_out", reduced.input_variables)

    def test_single_mass_metadata_reduction_type(self):
        from app.core.symbolic.polymorphic_dae_reducer import PolymorphicDAEReducer
        graph = self._setup_single_mass()
        sym = _make_empty_symbolic()
        reduced = PolymorphicDAEReducer().reduce(graph, sym)
        self.assertEqual(
            reduced.metadata.get("reduction_type"),
            "polymorphic_linear_mechanical",
        )

    def test_no_class_name_in_reducer_source(self):
        """Confirm the reducer module does not contain any class-name string checks."""
        import inspect
        from app.core.symbolic import polymorphic_dae_reducer
        source = inspect.getsource(polymorphic_dae_reducer)
        for forbidden in ('"Mass"', '"Wheel"', '"Spring"', '"Damper"',
                          "'Mass'", "'Wheel'", "'Spring'", "'Damper'",
                          'record["type"]', "record['type']"):
            self.assertNotIn(
                forbidden, source,
                msg=f"Reducer contains forbidden class-name check: {forbidden!r}",
            )


# ---------------------------------------------------------------------------
# Two-mass system
# ---------------------------------------------------------------------------

class TestPolymorphicReducerTwoMass(unittest.TestCase):

    def _setup_two_mass(self):
        from app.core.graph.system_graph import SystemGraph
        from app.core.models.mechanical import Mass, Spring, Damper, MechanicalGround
        from app.core.models.sources import StepForce

        graph = SystemGraph()
        m1 = graph.add_component(Mass("m1", mass=1.0))
        m2 = graph.add_component(Mass("m2", mass=2.0))
        k1 = graph.add_component(Spring("k1", stiffness=100.0))
        k2 = graph.add_component(Spring("k2", stiffness=200.0))
        d1 = graph.add_component(Damper("d1", damping=5.0))
        src = graph.add_component(StepForce("f_in", amplitude=1.0))
        gnd = graph.add_component(MechanicalGround("ground"))

        # Topology: ground – k1 – m1 – k2 – m2 – d1 – ground; force on m2
        graph.connect(m1.port("port_a").id, k1.port("port_a").id)
        graph.connect(m1.port("port_a").id, k2.port("port_a").id)
        graph.connect(m2.port("port_a").id, k2.port("port_b").id)
        graph.connect(m2.port("port_a").id, d1.port("port_a").id)
        graph.connect(m2.port("port_a").id, src.port("port").id)
        graph.connect(k1.port("port_b").id, gnd.port("port").id)
        graph.connect(d1.port("port_b").id, gnd.port("port").id)
        graph.connect(m1.port("reference_port").id, gnd.port("port").id)
        graph.connect(m2.port("reference_port").id, gnd.port("port").id)
        graph.connect(src.port("reference_port").id, gnd.port("port").id)

        return graph

    def test_two_mass_dof_count(self):
        from app.core.symbolic.polymorphic_dae_reducer import PolymorphicDAEReducer
        graph = self._setup_two_mass()
        sym = _make_empty_symbolic()
        reduced = PolymorphicDAEReducer().reduce(graph, sym)
        self.assertEqual(len(reduced.node_order), 2)

    def test_two_mass_a_matrix_4x4(self):
        from app.core.symbolic.polymorphic_dae_reducer import PolymorphicDAEReducer
        graph = self._setup_two_mass()
        sym = _make_empty_symbolic()
        reduced = PolymorphicDAEReducer().reduce(graph, sym)
        self.assertEqual(len(reduced.first_order_a), 4)
        self.assertEqual(len(reduced.first_order_a[0]), 4)

    def test_two_mass_mass_matrix_diagonal_values(self):
        from app.core.symbolic.polymorphic_dae_reducer import PolymorphicDAEReducer
        graph = self._setup_two_mass()
        sym = _make_empty_symbolic()
        reduced = PolymorphicDAEReducer().reduce(graph, sym)
        M = reduced.mass_matrix
        masses = sorted([M[i][i] for i in range(2)])
        self.assertAlmostEqual(masses[0], 1.0)
        self.assertAlmostEqual(masses[1], 2.0)

    def test_two_mass_k2_coupling_off_diagonal(self):
        """k2 connects m1 and m2 → K[i,j] and K[j,i] must be negative."""
        from app.core.symbolic.polymorphic_dae_reducer import PolymorphicDAEReducer
        graph = self._setup_two_mass()
        sym = _make_empty_symbolic()
        reduced = PolymorphicDAEReducer().reduce(graph, sym)
        K = reduced.stiffness_matrix
        # Off-diagonal elements should be non-zero (coupling spring present)
        off_diags = [K[0][1], K[1][0]]
        self.assertTrue(any(v != 0.0 for v in off_diags), "Expected k2 coupling in K matrix")
        self.assertAlmostEqual(K[0][1], K[1][0])
        self.assertLess(K[0][1], 0.0)  # coupling is negative in Laplacian form

    def test_two_mass_state_variable_count(self):
        from app.core.symbolic.polymorphic_dae_reducer import PolymorphicDAEReducer
        graph = self._setup_two_mass()
        sym = _make_empty_symbolic()
        reduced = PolymorphicDAEReducer().reduce(graph, sym)
        self.assertEqual(len(reduced.state_variables), 4)  # x1, x2, v1, v2

    def test_two_mass_b_matrix_has_one_input(self):
        from app.core.symbolic.polymorphic_dae_reducer import PolymorphicDAEReducer
        graph = self._setup_two_mass()
        sym = _make_empty_symbolic()
        reduced = PolymorphicDAEReducer().reduce(graph, sym)
        self.assertEqual(len(reduced.input_variables), 1)


# ---------------------------------------------------------------------------
# Symbol substitution helper
# ---------------------------------------------------------------------------

class TestSymbolSubstitution(unittest.TestCase):

    def test_sympy_symbol_substituted_to_float(self):
        from app.core.symbolic.polymorphic_dae_reducer import PolymorphicDAEReducer
        import sympy
        reducer = PolymorphicDAEReducer()
        sym = sympy.Symbol("m_mass_1")
        subs = {sym: 5.0}
        result = reducer._eval(sym, subs)
        self.assertAlmostEqual(result, 5.0)

    def test_plain_float_passthrough(self):
        from app.core.symbolic.polymorphic_dae_reducer import PolymorphicDAEReducer
        reducer = PolymorphicDAEReducer()
        self.assertAlmostEqual(reducer._eval(3.14, {}), 3.14)

    def test_sympy_expression_evaluated(self):
        from app.core.symbolic.polymorphic_dae_reducer import PolymorphicDAEReducer
        import sympy
        reducer = PolymorphicDAEReducer()
        k = sympy.Symbol("k_s")
        expr = k * 2
        subs = {k: 100.0}
        self.assertAlmostEqual(reducer._eval(expr, subs), 200.0)


if __name__ == "__main__":
    unittest.main()
