"""End-to-end test: RC circuit → state-space (T2 + T3.1).

Circuit:
    VoltageSource(V=1) ─── Resistor(R=1) ─── Capacitor(C=1) ─── Ground

Expected state-space (single state = v_C):
    dx/dt = -1/(RC) * x + 1/(RC) * u
    y = x

With R=1, C=1:
    A = [[-1]], B = [[1]], C = [[1]], D = [[0]]
    H(s) = 1 / (s + 1)  — first-order low-pass
"""

from __future__ import annotations

import pytest
import sympy

from app.core.graph.system_graph import SystemGraph
from app.core.models.electrical.ground import ElectricalGround
from app.core.models.electrical.resistor import Resistor
from app.core.models.electrical.capacitor import Capacitor
from app.core.models.electrical.source import VoltageSource
from app.core.symbolic.symbolic_flattener import flatten
from app.core.symbolic.small_signal_reducer import SmallSignalLinearReducer


def build_rc_circuit(R: float = 1.0, C: float = 1.0, V: float = 1.0) -> SystemGraph:
    """Build: Vs ─ R ─ C ─ GND."""
    g = SystemGraph()

    vs = g.add_component(VoltageSource("vs1", V=V))
    r = g.add_component(Resistor("r1", R=R))
    c = g.add_component(Capacitor("c1", C=C))
    gnd = g.add_component(ElectricalGround("gnd1"))

    # Vs.positive ── R.positive (node: n_top)
    g.connect(vs.ports[0].id, r.ports[0].id)
    # R.negative ── C.positive (node: n_mid)
    g.connect(r.ports[1].id, c.ports[0].id)
    # C.negative ── GND.p (node: n_gnd)
    g.connect(c.ports[1].id, gnd.ports[0].id)
    # Vs.negative ── GND.p (also node: n_gnd — close the loop)
    g.connect(vs.ports[1].id, gnd.ports[0].id)

    return g


class TestRCCircuitBuild:
    """Test that the circuit topology is set up correctly."""

    def test_four_components(self):
        g = build_rc_circuit()
        assert len(g.components) == 4

    def test_three_nodes(self):
        """Vs+/R+ share a node, R-/C+ share a node, C-/GND/Vs- share a node."""
        g = build_rc_circuit()
        assert len(g.nodes) == 3

    def test_all_ports_connected(self):
        g = build_rc_circuit()
        for comp in g.components.values():
            for port in comp.ports:
                assert port.node_id is not None, f"{comp.name}:{port.name} unconnected"


class TestRCCircuitFlatten:
    """Test that flattening produces sensible equations."""

    def test_flatten_produces_equations(self):
        g = build_rc_circuit()
        flat = flatten(g, input_symbol_names=["vs1__value"])
        assert len(flat.equations) > 0

    def test_flatten_finds_state(self):
        g = build_rc_circuit()
        flat = flatten(g, input_symbol_names=["vs1__value"])
        # Capacitor introduces a state (v_diff under der())
        assert len(flat.state_symbols) >= 1

    def test_flatten_finds_input(self):
        g = build_rc_circuit()
        flat = flatten(g, input_symbol_names=["vs1__value"])
        assert len(flat.input_symbols) == 1

    def test_flatten_finds_parameters(self):
        g = build_rc_circuit()
        flat = flatten(g, input_symbol_names=["vs1__value"])
        # R=1.0, C=1.0, V=1.0 → at least 3 parameters
        assert len(flat.parameter_map) >= 2


class TestRCCircuitReduce:
    """Test full reduction to state-space."""

    def _reduce_rc(self, R=1.0, C=1.0):
        g = build_rc_circuit(R=R, C=C)

        # Output = capacitor voltage (v_diff of capacitor)
        c_comp = g.components["c1"]
        v_diff_sym = c_comp._setup.symbols["v_diff"]

        flat = flatten(
            g,
            input_symbol_names=["vs1__value"],
            output_exprs={"v_cap": v_diff_sym},
        )

        reducer = SmallSignalLinearReducer()
        return reducer.reduce(flat)

    def test_single_state(self):
        ss = self._reduce_rc()
        assert len(ss.state_variables) == 1

    def test_single_input(self):
        ss = self._reduce_rc()
        assert len(ss.input_variables) == 1

    def test_single_output(self):
        ss = self._reduce_rc()
        assert len(ss.output_variables) == 1

    def test_a_matrix_value(self):
        """A = [[-1/(RC)]] = [[-1]] for R=1, C=1."""
        ss = self._reduce_rc(R=1.0, C=1.0)
        assert len(ss.a_matrix) == 1
        assert len(ss.a_matrix[0]) == 1
        assert abs(ss.a_matrix[0][0] - (-1.0)) < 1e-10

    def test_b_matrix_value(self):
        """B = [[1/(RC)]] = [[1]] for R=1, C=1."""
        ss = self._reduce_rc(R=1.0, C=1.0)
        assert abs(ss.b_matrix[0][0] - 1.0) < 1e-10

    def test_c_matrix_value(self):
        """C = [[1]] — output is the state itself."""
        ss = self._reduce_rc(R=1.0, C=1.0)
        assert abs(ss.c_matrix[0][0] - 1.0) < 1e-10

    def test_d_matrix_value(self):
        """D = [[0]] — no direct feedthrough."""
        ss = self._reduce_rc(R=1.0, C=1.0)
        assert abs(ss.d_matrix[0][0]) < 1e-10

    def test_different_values(self):
        """A = [[-1/(RC)]] = [[-10]] for R=10, C=0.01."""
        ss = self._reduce_rc(R=10.0, C=0.01)
        expected_a = -1.0 / (10.0 * 0.01)  # -10.0
        assert abs(ss.a_matrix[0][0] - expected_a) < 1e-10

    def test_metadata_reducer_name(self):
        ss = self._reduce_rc()
        assert ss.metadata["reducer"] == "SmallSignalLinearReducer"
