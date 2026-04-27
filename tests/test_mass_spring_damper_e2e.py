"""End-to-end test: Mass-Spring-Damper → state-space (T4.5).

System topology:
    ForceSource ─── Mass ─── Spring ─── Fixed
                      └────── Damper ──┘

More precisely (MSL connection style):
    ForceSource.flange_b ─── Mass.flange_a
    ForceSource.flange_a ─── Fixed.flange      (close loop)
    Mass.flange_b ─── Spring.flange_a, Damper.flange_a  (parallel)
    Spring.flange_b, Damper.flange_b ─── Fixed.flange

Expected state-space (2 states: position x, velocity v):
    dx/dt = v
    dv/dt = -(k/m)*x - (d/m)*v + (1/m)*F

    A = [[0, 1], [-k/m, -d/m]]
    B = [[0], [1/m]]

With m=1, k=1, d=1:
    A = [[0, 1], [-1, -1]]
    B = [[0], [1]]

Bond-graph analogy verification:
    This is IDENTICAL to the RLC circuit with R=1, L=1, C=1!
    (Same eigenvalues, same characteristic polynomial s² + s + 1 = 0)
"""

from __future__ import annotations

import pytest
import numpy as np

from app.core.graph.system_graph import SystemGraph
from app.core.models.translational.fixed import TranslationalFixed
from app.core.models.translational.spring import TranslationalSpring
from app.core.models.translational.damper import TranslationalDamper
from app.core.models.translational.mass import TranslationalMass
from app.core.models.translational.source import ForceSource
from app.core.symbolic.symbolic_flattener import flatten
from app.core.symbolic.small_signal_reducer import SmallSignalLinearReducer


def build_msd(m=1.0, k=1.0, d=1.0, F=1.0) -> SystemGraph:
    """Build mass-spring-damper: ForceSource ─ Mass ─ Spring||Damper ─ Fixed."""
    g = SystemGraph()

    fs = g.add_component(ForceSource("fs1", F=F))
    mass = g.add_component(TranslationalMass("m1", m=m))
    spring = g.add_component(TranslationalSpring("k1", k=k))
    damper = g.add_component(TranslationalDamper("d1", d=d))
    fixed = g.add_component(TranslationalFixed("fix1"))

    # ForceSource.flange_a → Mass.flange_a  (force enters mass positively)
    g.connect(fs.ports[0].id, mass.ports[0].id)
    # Mass.flange_b → Spring.flange_a
    g.connect(mass.ports[1].id, spring.ports[0].id)
    # Mass.flange_b → Damper.flange_a (same node as spring.flange_a)
    g.connect(mass.ports[1].id, damper.ports[0].id)
    # Spring.flange_b → Fixed.flange
    g.connect(spring.ports[1].id, fixed.ports[0].id)
    # Damper.flange_b → Fixed.flange (same node)
    g.connect(damper.ports[1].id, fixed.ports[0].id)
    # ForceSource.flange_b → Fixed.flange (close loop)
    g.connect(fs.ports[1].id, fixed.ports[0].id)

    return g


class TestMSDBuild:
    def test_five_components(self):
        g = build_msd()
        assert len(g.components) == 5

    def test_three_nodes(self):
        """ForceSource.flange_a/Fixed (ground), ForceSource.flange_b/Mass.flange_a,
        Mass.flange_b/Spring.flange_a/Damper.flange_a, Spring.flange_b/Damper.flange_b/Fixed."""
        g = build_msd()
        # At least 3 distinct nodes
        assert len(g.nodes) >= 3

    def test_all_connected(self):
        g = build_msd()
        for comp in g.components.values():
            for port in comp.ports:
                assert port.node_id is not None


class TestMSDReduce:
    def _reduce_msd(self, m=1.0, k=1.0, d=1.0):
        g = build_msd(m=m, k=k, d=d)
        mass = g.components["m1"]
        # Output = mass position (v_center from rigid pair)
        pos_sym = mass._setup.symbols["v_center"]

        flat = flatten(
            g,
            input_symbol_names=["fs1__value"],
            output_exprs={"x_mass": pos_sym},
        )
        reducer = SmallSignalLinearReducer()
        return reducer.reduce(flat)

    def test_two_states(self):
        """Mass-spring-damper has 2 energy-storage → 2 states."""
        ss = self._reduce_msd()
        assert len(ss.state_variables) == 2

    def test_single_input(self):
        ss = self._reduce_msd()
        assert len(ss.input_variables) == 1

    def test_single_output(self):
        ss = self._reduce_msd()
        assert len(ss.output_variables) == 1

    def test_a_matrix_2x2(self):
        ss = self._reduce_msd()
        assert len(ss.a_matrix) == 2
        assert len(ss.a_matrix[0]) == 2

    def test_b_matrix_2x1(self):
        ss = self._reduce_msd()
        assert len(ss.b_matrix) == 2
        assert len(ss.b_matrix[0]) == 1

    def test_eigenvalues_stable(self):
        """All eigenvalues should have negative real part."""
        ss = self._reduce_msd(m=1.0, k=1.0, d=1.0)
        A = np.array(ss.a_matrix)
        eigenvalues = np.linalg.eigvals(A)
        for ev in eigenvalues:
            assert ev.real < 0, f"Unstable eigenvalue: {ev}"

    def test_eigenvalues_underdamped(self):
        """With m=1, k=1, d=1: underdamped (complex eigenvalues)."""
        ss = self._reduce_msd(m=1.0, k=1.0, d=1.0)
        A = np.array(ss.a_matrix)
        eigenvalues = np.linalg.eigvals(A)
        has_complex = any(abs(ev.imag) > 1e-10 for ev in eigenvalues)
        assert has_complex, f"Expected underdamped, got: {eigenvalues}"

    def test_characteristic_polynomial(self):
        """Char poly should be s² + (d/m)s + (k/m) = s² + s + 1 for unit values."""
        ss = self._reduce_msd(m=1.0, k=1.0, d=1.0)
        A = np.array(ss.a_matrix)
        # Characteristic polynomial: det(sI - A) = s² + trace(-A)*s + det(A)
        # For [[0,1],[-1,-1]]: trace = -1, so coeff of s = 1; det = 0*(-1) - 1*(-1) = 1
        trace_A = np.trace(A)
        det_A = np.linalg.det(A)
        assert abs(trace_A - (-1.0)) < 1e-10, f"trace(A) = {trace_A}, expected -1"
        assert abs(det_A - 1.0) < 1e-10, f"det(A) = {det_A}, expected 1"

    def test_dc_gain(self):
        """DC gain of position/force should be 1/k = 1.0 for k=1."""
        ss = self._reduce_msd(m=1.0, k=1.0, d=1.0)
        A = np.array(ss.a_matrix)
        B = np.array(ss.b_matrix)
        C = np.array(ss.c_matrix)
        D = np.array(ss.d_matrix)
        dc_gain = -C @ np.linalg.inv(A) @ B + D
        assert abs(dc_gain[0, 0] - 1.0) < 1e-8, f"DC gain = {dc_gain[0,0]}, expected 1.0"

    def test_different_parameters(self):
        """With m=2, k=10, d=4: still 2 states, stable."""
        ss = self._reduce_msd(m=2.0, k=10.0, d=4.0)
        assert len(ss.state_variables) == 2
        A = np.array(ss.a_matrix)
        eigenvalues = np.linalg.eigvals(A)
        for ev in eigenvalues:
            assert ev.real < 0, f"Unstable: {ev}"


class TestBondGraphAnalogy:
    """The mass-spring-damper (m=1,k=1,d=1) and RLC circuit (R=1,L=1,C=1)
    should have identical eigenvalues — proof of bond-graph duality."""

    def _get_msd_eigenvalues(self):
        g = build_msd(m=1.0, k=1.0, d=1.0)
        mass = g.components["m1"]
        pos_sym = mass._setup.symbols["v_center"]
        flat = flatten(g, input_symbol_names=["fs1__value"],
                      output_exprs={"x": pos_sym})
        ss = SmallSignalLinearReducer().reduce(flat)
        return np.sort(np.linalg.eigvals(np.array(ss.a_matrix)))

    def _get_rlc_eigenvalues(self):
        from app.core.models.electrical.ground import ElectricalGround
        from app.core.models.electrical.resistor import Resistor
        from app.core.models.electrical.capacitor import Capacitor
        from app.core.models.electrical.inductor import Inductor
        from app.core.models.electrical.source import VoltageSource

        g = SystemGraph()
        vs = g.add_component(VoltageSource("vs1", V=1.0))
        r = g.add_component(Resistor("r1", R=1.0))
        ind = g.add_component(Inductor("l1", L=1.0))
        cap = g.add_component(Capacitor("c1", C=1.0))
        gnd = g.add_component(ElectricalGround("gnd1"))

        g.connect(vs.ports[0].id, r.ports[0].id)
        g.connect(r.ports[1].id, ind.ports[0].id)
        g.connect(ind.ports[1].id, cap.ports[0].id)
        g.connect(cap.ports[1].id, gnd.ports[0].id)
        g.connect(vs.ports[1].id, gnd.ports[0].id)

        cap_comp = g.components["c1"]
        v_cap = cap_comp._setup.symbols["v_diff"]
        flat = flatten(g, input_symbol_names=["vs1__value"],
                      output_exprs={"v_cap": v_cap})
        ss = SmallSignalLinearReducer().reduce(flat)
        return np.sort(np.linalg.eigvals(np.array(ss.a_matrix)))

    def test_same_eigenvalues(self):
        """MSD and RLC eigenvalues must match (bond-graph analogy)."""
        msd_eigs = self._get_msd_eigenvalues()
        rlc_eigs = self._get_rlc_eigenvalues()
        # Sort by real part, then imaginary
        for msd_e, rlc_e in zip(msd_eigs, rlc_eigs):
            assert abs(msd_e - rlc_e) < 1e-8, (
                f"Eigenvalue mismatch: MSD={msd_e}, RLC={rlc_e}"
            )

    def test_same_characteristic_polynomial(self):
        """Both systems: s² + s + 1 = 0."""
        msd_eigs = self._get_msd_eigenvalues()
        rlc_eigs = self._get_rlc_eigenvalues()
        # Sum of eigenvalues = -trace = -(coeff of s)
        msd_sum = sum(msd_eigs)
        rlc_sum = sum(rlc_eigs)
        assert abs(msd_sum - rlc_sum) < 1e-8
        # Product of eigenvalues = det = constant term
        msd_prod = np.prod(msd_eigs)
        rlc_prod = np.prod(rlc_eigs)
        assert abs(msd_prod - rlc_prod) < 1e-8
