"""End-to-end test: RLC circuit → state-space (T3.2).

Circuit:
    VoltageSource(V) ─── Resistor(R) ─── Inductor(L) ─── Capacitor(C) ��── Ground
                                                          └── loop back to GND

Expected state-space (2 states: v_C and i_L):
    H(s) = 1 / (LCs² + RCs + 1)   — second-order underdamped system

With R=1, L=1, C=1:
    A = [[0, 1], [-1, -1]]   (approximately)
    States: v_C (capacitor voltage), i_L (inductor current proxy = through)
"""

from __future__ import annotations

import pytest

from app.core.graph.system_graph import SystemGraph
from app.core.models.electrical.ground import ElectricalGround
from app.core.models.electrical.resistor import Resistor
from app.core.models.electrical.capacitor import Capacitor
from app.core.models.electrical.inductor import Inductor
from app.core.models.electrical.source import VoltageSource
from app.core.symbolic.symbolic_flattener import flatten
from app.core.symbolic.small_signal_reducer import SmallSignalLinearReducer


def build_rlc_series(R=1.0, L=1.0, C=1.0, V=1.0) -> SystemGraph:
    """Build series RLC: Vs ─ R ─ L ─ C ─ GND, with Vs- also to GND."""
    g = SystemGraph()

    vs = g.add_component(VoltageSource("vs1", V=V))
    r = g.add_component(Resistor("r1", R=R))
    ind = g.add_component(Inductor("l1", L=L))
    cap = g.add_component(Capacitor("c1", C=C))
    gnd = g.add_component(ElectricalGround("gnd1"))

    # Vs+ ── R+
    g.connect(vs.ports[0].id, r.ports[0].id)
    # R- ── L+
    g.connect(r.ports[1].id, ind.ports[0].id)
    # L- ── C+
    g.connect(ind.ports[1].id, cap.ports[0].id)
    # C- ── GND
    g.connect(cap.ports[1].id, gnd.ports[0].id)
    # Vs- ── GND (close loop)
    g.connect(vs.ports[1].id, gnd.ports[0].id)

    return g


class TestRLCBuild:
    def test_five_components(self):
        g = build_rlc_series()
        assert len(g.components) == 5

    def test_four_nodes(self):
        """Vs+/R+, R-/L+, L-/C+, C-/GND/Vs-."""
        g = build_rlc_series()
        assert len(g.nodes) == 4

    def test_all_connected(self):
        g = build_rlc_series()
        for comp in g.components.values():
            for port in comp.ports:
                assert port.node_id is not None


class TestRLCReduce:
    def _reduce_rlc(self, R=1.0, L=1.0, C=1.0):
        g = build_rlc_series(R=R, L=L, C=C)
        cap = g.components["c1"]
        v_cap = cap._setup.symbols["v_diff"]

        flat = flatten(
            g,
            input_symbol_names=["vs1__value"],
            output_exprs={"v_cap": v_cap},
        )
        reducer = SmallSignalLinearReducer()
        return reducer.reduce(flat)

    def test_two_states(self):
        """RLC has 2 energy-storage elements → 2 states."""
        ss = self._reduce_rlc()
        assert len(ss.state_variables) == 2

    def test_single_input(self):
        ss = self._reduce_rlc()
        assert len(ss.input_variables) == 1

    def test_single_output(self):
        ss = self._reduce_rlc()
        assert len(ss.output_variables) == 1

    def test_a_matrix_2x2(self):
        ss = self._reduce_rlc()
        assert len(ss.a_matrix) == 2
        assert len(ss.a_matrix[0]) == 2

    def test_b_matrix_2x1(self):
        ss = self._reduce_rlc()
        assert len(ss.b_matrix) == 2
        assert len(ss.b_matrix[0]) == 1

    def test_eigenvalues_stable(self):
        """All eigenvalues should have negative real part (stable system)."""
        import numpy as np
        ss = self._reduce_rlc(R=1.0, L=1.0, C=1.0)
        A = np.array(ss.a_matrix)
        eigenvalues = np.linalg.eigvals(A)
        for ev in eigenvalues:
            assert ev.real < 0, f"Unstable eigenvalue: {ev}"

    def test_eigenvalues_complex_underdamped(self):
        """With R=1, L=1, C=1 the system is underdamped (complex eigenvalues)."""
        import numpy as np
        ss = self._reduce_rlc(R=1.0, L=1.0, C=1.0)
        A = np.array(ss.a_matrix)
        eigenvalues = np.linalg.eigvals(A)
        # At least one eigenvalue should have nonzero imaginary part
        has_complex = any(abs(ev.imag) > 1e-10 for ev in eigenvalues)
        assert has_complex, f"Expected underdamped, got eigenvalues: {eigenvalues}"

    def test_dc_gain_unity(self):
        """DC gain of V_C / V_in should be 1 (at DC, C is open, all voltage drops across C)."""
        import numpy as np
        ss = self._reduce_rlc(R=1.0, L=1.0, C=1.0)
        A = np.array(ss.a_matrix)
        B = np.array(ss.b_matrix)
        C = np.array(ss.c_matrix)
        D = np.array(ss.d_matrix)
        # DC gain = -C * A^-1 * B + D
        dc_gain = -C @ np.linalg.inv(A) @ B + D
        assert abs(dc_gain[0, 0] - 1.0) < 1e-8, f"DC gain = {dc_gain[0,0]}, expected 1.0"

    def test_different_parameters(self):
        """With R=10, L=0.1, C=0.01: still 2 states, stable."""
        import numpy as np
        ss = self._reduce_rlc(R=10.0, L=0.1, C=0.01)
        assert len(ss.state_variables) == 2
        A = np.array(ss.a_matrix)
        eigenvalues = np.linalg.eigvals(A)
        for ev in eigenvalues:
            assert ev.real < 0, f"Unstable: {ev}"
