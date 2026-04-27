"""Tests for electrical components (T1.1–T1.6).

All sign convention checks reference SIGN_CONVENTION.md.
"""

from __future__ import annotations

import sympy
import pytest

from app.core.models.electrical.ground import ElectricalGround
from app.core.models.electrical.resistor import Resistor
from app.core.models.electrical.capacitor import Capacitor
from app.core.models.electrical.inductor import Inductor
from app.core.models.electrical.source import (
    IdealSource,
    VoltageSource,
    CurrentSource,
)


# ===================================================================
# ElectricalGround
# ===================================================================


class TestElectricalGround:
    def test_single_port(self):
        g = ElectricalGround("gnd1")
        assert len(g.ports) == 1
        assert g.ports[0].name == "p"

    def test_category_is_reference(self):
        g = ElectricalGround("gnd1")
        assert g.category == "reference"

    def test_port_direction_positive(self):
        g = ElectricalGround("gnd1")
        assert g.ports[0].direction_hint == "positive"

    def test_symbolic_equation_sets_v_zero(self):
        g = ElectricalGround("gnd1")
        eqs = g.symbolic_equations()
        assert len(eqs) == 1
        eq = eqs[0]
        assert eq.rhs == 0
        assert eq.provenance == "ground_reference"

    def test_domain_is_electrical(self):
        g = ElectricalGround("gnd1")
        assert g.domain.name == "electrical"

    def test_constitutive_equations_string(self):
        g = ElectricalGround("gnd1")
        assert len(g.constitutive_equations()) == 1


# ===================================================================
# Resistor
# ===================================================================


class TestResistor:
    def test_two_ports(self):
        r = Resistor("r1", R=100.0)
        assert len(r.ports) == 2

    def test_category_is_passive(self):
        r = Resistor("r1")
        assert r.category == "passive"

    def test_parameter_R(self):
        r = Resistor("r1", R=470.0)
        assert r.parameters["R"] == 470.0

    def test_port_directions(self):
        r = Resistor("r1")
        assert r.ports[0].direction_hint == "positive"
        assert r.ports[1].direction_hint == "negative"

    def test_symbolic_equations_count(self):
        """3 topology (across_diff, KCL, through_alias) + 1 Ohm."""
        r = Resistor("r1")
        eqs = r.symbolic_equations()
        assert len(eqs) == 4

    def test_ohm_law_equation(self):
        r = Resistor("r1", R=100.0)
        eqs = r.symbolic_equations()
        ohm = [eq for eq in eqs if eq.provenance == "Ohm"]
        assert len(ohm) == 1

    def test_ohm_law_residual(self):
        """v_diff - R * through = 0 when substituted correctly."""
        r = Resistor("r1", R=100.0)
        eqs = r.symbolic_equations()
        ohm = [eq for eq in eqs if eq.provenance == "Ohm"][0]
        # v_diff = R * through → residual = v_diff - R*through
        s = r._setup.symbols
        R_sym = r._sym("R")
        # Substitute: v_diff=10, through=0.1, R=100 → 10 - 100*0.1 = 0
        residual = ohm.residual.subs({s["v_diff"]: 10, s["through"]: 0.1, R_sym: 100})
        assert float(residual) == 0.0

    def test_sign_convention_passive(self):
        """Electrical: v_diff = v_a - v_b (v_p - v_n), SIGN_CONVENTION.md §2.1."""
        r = Resistor("r1")
        eqs = r.symbolic_equations()
        ad = [eq for eq in eqs if eq.provenance == "across_diff"][0]
        s = r._setup.symbols
        # v_diff = v_a - v_b (positive minus negative)
        expected = s["v_a"] - s["v_b"]
        assert sympy.simplify(ad.rhs - expected) == 0

    def test_through_alias_is_i_a(self):
        """Electrical: through = i_a (current into positive port)."""
        r = Resistor("r1")
        eqs = r.symbolic_equations()
        ta = [eq for eq in eqs if eq.provenance == "through_alias"][0]
        assert ta.rhs == r._setup.symbols["i_a"]

    def test_no_state_contribution(self):
        r = Resistor("r1")
        assert r.get_state_contribution() is None

    def test_no_derivative_in_equations(self):
        r = Resistor("r1")
        eqs = r.symbolic_equations()
        ohm = [eq for eq in eqs if eq.provenance == "Ohm"][0]
        assert ohm.has_derivative() is False


# ===================================================================
# Capacitor
# ===================================================================


class TestCapacitor:
    def test_two_ports(self):
        c = Capacitor("c1", C=1e-6)
        assert len(c.ports) == 2

    def test_category_is_passive(self):
        c = Capacitor("c1")
        assert c.category == "passive"

    def test_parameter_C(self):
        c = Capacitor("c1", C=4.7e-6)
        assert c.parameters["C"] == 4.7e-6

    def test_symbolic_equations_count(self):
        """3 topology + 1 capacitor constitutive."""
        c = Capacitor("c1")
        eqs = c.symbolic_equations()
        assert len(eqs) == 4

    def test_capacitor_equation_has_derivative(self):
        c = Capacitor("c1")
        eqs = c.symbolic_equations()
        cap_eq = [eq for eq in eqs if eq.provenance == "capacitor"]
        assert len(cap_eq) == 1
        assert cap_eq[0].has_derivative() is True

    def test_capacitor_equation_form(self):
        """through = C × der(v_diff)."""
        c = Capacitor("c1")
        eqs = c.symbolic_equations()
        cap_eq = [eq for eq in eqs if eq.provenance == "capacitor"][0]
        s = c._setup.symbols
        # lhs = through
        assert cap_eq.lhs == s["through"]
        # rhs should contain der(v_diff)
        assert "der" in str(cap_eq.rhs)

    def test_has_state_contribution(self):
        c = Capacitor("c1")
        sc = c.get_state_contribution()
        assert sc is not None
        assert sc.stores_potential_energy is True
        assert sc.dof_count == 1

    def test_initial_conditions(self):
        c = Capacitor("c1")
        assert "v" in c.initial_conditions


# ===================================================================
# Inductor
# ===================================================================


class TestInductor:
    def test_two_ports(self):
        ind = Inductor("l1", L=1e-3)
        assert len(ind.ports) == 2

    def test_parameter_L(self):
        ind = Inductor("l1", L=10e-3)
        assert ind.parameters["L"] == 10e-3

    def test_symbolic_equations_count(self):
        """3 topology + 1 inductor constitutive."""
        ind = Inductor("l1")
        eqs = ind.symbolic_equations()
        assert len(eqs) == 4

    def test_inductor_equation_has_derivative(self):
        ind = Inductor("l1")
        eqs = ind.symbolic_equations()
        ind_eq = [eq for eq in eqs if eq.provenance == "inductor"]
        assert len(ind_eq) == 1
        assert ind_eq[0].has_derivative() is True

    def test_inductor_equation_form(self):
        """v_diff = L × der(through)."""
        ind = Inductor("l1")
        eqs = ind.symbolic_equations()
        ind_eq = [eq for eq in eqs if eq.provenance == "inductor"][0]
        s = ind._setup.symbols
        assert ind_eq.lhs == s["v_diff"]
        assert "der" in str(ind_eq.rhs)

    def test_has_state_contribution(self):
        ind = Inductor("l1")
        sc = ind.get_state_contribution()
        assert sc is not None
        assert sc.stores_inertial_energy is True
        assert sc.dof_count == 1

    def test_initial_conditions(self):
        ind = Inductor("l1")
        assert "i" in ind.initial_conditions


# ===================================================================
# IdealSource / VoltageSource / CurrentSource
# ===================================================================


class TestVoltageSource:
    def test_category_is_source(self):
        vs = VoltageSource("vs1", V=5.0)
        assert vs.category == "source"

    def test_source_kind(self):
        vs = VoltageSource("vs1")
        assert vs.source_kind == "prescribed_across"

    def test_symbolic_equations_count(self):
        """3 topology + 1 prescribed_across."""
        vs = VoltageSource("vs1")
        eqs = vs.symbolic_equations()
        assert len(eqs) == 4

    def test_prescribes_v_diff(self):
        vs = VoltageSource("vs1", V=5.0)
        eqs = vs.symbolic_equations()
        src = [eq for eq in eqs if eq.provenance == "prescribed_across"]
        assert len(src) == 1
        s = vs._setup.symbols
        assert src[0].lhs == s["v_diff"]

    def test_no_derivative(self):
        vs = VoltageSource("vs1")
        eqs = vs.symbolic_equations()
        src = [eq for eq in eqs if eq.provenance == "prescribed_across"][0]
        assert src.has_derivative() is False

    def test_no_state_contribution(self):
        vs = VoltageSource("vs1")
        assert vs.get_state_contribution() is None


class TestCurrentSource:
    def test_source_kind(self):
        cs = CurrentSource("cs1")
        assert cs.source_kind == "prescribed_through"

    def test_prescribes_through(self):
        cs = CurrentSource("cs1", I=0.01)
        eqs = cs.symbolic_equations()
        src = [eq for eq in eqs if eq.provenance == "prescribed_through"]
        assert len(src) == 1
        s = cs._setup.symbols
        assert src[0].lhs == s["through"]


class TestIdealSourceGeneric:
    def test_factory_returns_ideal_source(self):
        vs = VoltageSource("vs1")
        cs = CurrentSource("cs1")
        assert isinstance(vs, IdealSource)
        assert isinstance(cs, IdealSource)

    def test_tags_contain_source_kind(self):
        vs = VoltageSource("vs1")
        assert "prescribed_across" in vs.tags
        cs = CurrentSource("cs1")
        assert "prescribed_through" in cs.tags


# ===================================================================
# Cross-component: all have electrical domain
# ===================================================================


class TestAllElectricalDomain:
    def test_all_components_electrical(self):
        components = [
            ElectricalGround("gnd1"),
            Resistor("r1"),
            Capacitor("c1"),
            Inductor("l1"),
            VoltageSource("vs1"),
            CurrentSource("cs1"),
        ]
        for comp in components:
            assert comp.domain.name == "electrical", f"{comp.name} domain mismatch"

    def test_all_have_symbolic_equations(self):
        components = [
            ElectricalGround("gnd1"),
            Resistor("r1"),
            Capacitor("c1"),
            Inductor("l1"),
            VoltageSource("vs1"),
            CurrentSource("cs1"),
        ]
        for comp in components:
            eqs = comp.symbolic_equations()
            assert len(eqs) >= 1, f"{comp.name} has no equations"

    def test_all_have_constitutive_equations(self):
        components = [
            ElectricalGround("gnd1"),
            Resistor("r1"),
            Capacitor("c1"),
            Inductor("l1"),
            VoltageSource("vs1"),
            CurrentSource("cs1"),
        ]
        for comp in components:
            eqs = comp.constitutive_equations()
            assert len(eqs) >= 1, f"{comp.name} has no string equations"
