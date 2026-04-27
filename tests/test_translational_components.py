"""Unit tests for new translational mechanical components (T4.1-T4.4).

Mirrors test_electrical_components.py structure.
"""

from __future__ import annotations

import pytest
import sympy

from app.core.base.equation import SymbolicEquation, der
from app.core.models.translational.fixed import TranslationalFixed
from app.core.models.translational.spring import TranslationalSpring
from app.core.models.translational.damper import TranslationalDamper
from app.core.models.translational.mass import TranslationalMass
from app.core.models.translational.source import (
    ForceSource,
    PositionSource,
    TranslationalIdealSource,
)


# ── TranslationalFixed ────────────────────────────────────────────────


class TestTranslationalFixed:
    def test_one_port(self):
        f = TranslationalFixed("f1")
        assert len(f.ports) == 1

    def test_port_name(self):
        f = TranslationalFixed("f1")
        assert f.ports[0].name == "flange"

    def test_domain_translational(self):
        f = TranslationalFixed("f1")
        assert f.domain.name == "translational"

    def test_direction_hint_a(self):
        f = TranslationalFixed("f1")
        assert f.ports[0].direction_hint == "a"

    def test_category_reference(self):
        f = TranslationalFixed("f1")
        assert f.category == "reference"

    def test_symbolic_equations_sets_zero(self):
        f = TranslationalFixed("f1")
        eqs = f.symbolic_equations()
        assert len(eqs) == 1
        assert eqs[0].rhs == 0


# ── TranslationalSpring ──────────────────────────────────────────────


class TestTranslationalSpring:
    def test_two_ports(self):
        s = TranslationalSpring("k1", k=100.0)
        assert len(s.ports) == 2

    def test_port_names(self):
        s = TranslationalSpring("k1", k=100.0)
        names = {p.name for p in s.ports}
        assert names == {"flange_a", "flange_b"}

    def test_direction_hints(self):
        s = TranslationalSpring("k1", k=100.0)
        hints = {p.name: p.direction_hint for p in s.ports}
        assert hints["flange_a"] == "a"
        assert hints["flange_b"] == "b"

    def test_parameter_k(self):
        s = TranslationalSpring("k1", k=100.0)
        assert s.parameters["k"] == 100.0

    def test_category_passive(self):
        s = TranslationalSpring("k1", k=100.0)
        assert s.category == "passive"

    def test_state_contribution_potential(self):
        s = TranslationalSpring("k1", k=100.0)
        sc = s.get_state_contribution()
        assert sc.stores_potential_energy is True
        assert sc.stores_inertial_energy is False

    def test_symbolic_equations_count(self):
        """3 setup (across_diff, KCL, through_alias) + 1 spring_law = 4."""
        s = TranslationalSpring("k1", k=100.0)
        eqs = s.symbolic_equations()
        assert len(eqs) == 4

    def test_spring_law_present(self):
        s = TranslationalSpring("k1", k=100.0)
        eqs = s.symbolic_equations()
        spring_eqs = [e for e in eqs if e.provenance == "spring_law"]
        assert len(spring_eqs) == 1

    def test_no_derivative_in_spring(self):
        """Spring law is algebraic (no der())."""
        s = TranslationalSpring("k1", k=100.0)
        eqs = s.symbolic_equations()
        spring_eq = [e for e in eqs if e.provenance == "spring_law"][0]
        assert not spring_eq.has_derivative()

    def test_mechanical_sign_convention(self):
        """v_diff = v_b - v_a (translational, power_order=1)."""
        s = TranslationalSpring("k1", k=100.0)
        eqs = s.symbolic_equations()
        across_eq = [e for e in eqs if e.provenance == "across_diff"][0]
        v_a = s._setup.symbols["v_a"]
        v_b = s._setup.symbols["v_b"]
        # rhs should be v_b - v_a
        assert across_eq.rhs == v_b - v_a


# ── TranslationalDamper ──────────────────────────────────────────────


class TestTranslationalDamper:
    def test_two_ports(self):
        d = TranslationalDamper("d1", d=10.0)
        assert len(d.ports) == 2

    def test_parameter_d(self):
        d = TranslationalDamper("d1", d=10.0)
        assert d.parameters["d"] == 10.0

    def test_category_passive(self):
        d = TranslationalDamper("d1", d=10.0)
        assert d.category == "passive"

    def test_symbolic_equations_count(self):
        """3 setup + 1 damper_law = 4."""
        d = TranslationalDamper("d1", d=10.0)
        eqs = d.symbolic_equations()
        assert len(eqs) == 4

    def test_damper_law_has_derivative(self):
        """Damper law: f = d * der(s_rel) — contains der()."""
        d = TranslationalDamper("d1", d=10.0)
        eqs = d.symbolic_equations()
        damper_eq = [e for e in eqs if e.provenance == "damper_law"][0]
        assert damper_eq.has_derivative()


# ── TranslationalMass ────────────────────────────────────────────────


class TestTranslationalMass:
    def test_two_ports(self):
        m = TranslationalMass("m1", m=1.0)
        assert len(m.ports) == 2

    def test_parameter_m(self):
        m = TranslationalMass("m1", m=1.0)
        assert m.parameters["m"] == 1.0

    def test_state_contribution_inertial(self):
        m = TranslationalMass("m1", m=1.0)
        sc = m.get_state_contribution()
        assert sc.stores_inertial_energy is True
        assert sc.state_kind == "inertial"

    def test_symbolic_equations_count(self):
        """2 rigid (v_a=v_center, v_b=v_center) + 1 velocity_def + 1 newton = 4."""
        m = TranslationalMass("m1", m=1.0)
        eqs = m.symbolic_equations()
        assert len(eqs) == 4

    def test_has_velocity_def(self):
        m = TranslationalMass("m1", m=1.0)
        eqs = m.symbolic_equations()
        vel_eqs = [e for e in eqs if e.provenance == "velocity_def"]
        assert len(vel_eqs) == 1

    def test_has_newton(self):
        m = TranslationalMass("m1", m=1.0)
        eqs = m.symbolic_equations()
        newton_eqs = [e for e in eqs if e.provenance == "newton_second_law"]
        assert len(newton_eqs) == 1

    def test_newton_has_derivative(self):
        """Newton's law contains der(velocity)."""
        m = TranslationalMass("m1", m=1.0)
        eqs = m.symbolic_equations()
        newton_eq = [e for e in eqs if e.provenance == "newton_second_law"][0]
        assert newton_eq.has_derivative()

    def test_no_kcl_in_rigid(self):
        """Rigid pair does NOT generate KCL — critical MSL difference."""
        m = TranslationalMass("m1", m=1.0)
        eqs = m.symbolic_equations()
        kcl_eqs = [e for e in eqs if "KCL" in e.provenance]
        assert len(kcl_eqs) == 0


# ── ForceSource / PositionSource ─────────────────────────────────────


class TestForceSource:
    def test_source_kind(self):
        fs = ForceSource("fs1", F=10.0)
        assert fs.source_kind == "prescribed_through"

    def test_parameter_value(self):
        fs = ForceSource("fs1", F=10.0)
        assert fs.parameters["value"] == 10.0

    def test_category_source(self):
        fs = ForceSource("fs1", F=10.0)
        assert fs.category == "source"

    def test_symbolic_equations_count(self):
        """3 setup + 1 prescribed = 4."""
        fs = ForceSource("fs1", F=10.0)
        eqs = fs.symbolic_equations()
        assert len(eqs) == 4


class TestPositionSource:
    def test_source_kind(self):
        ps = PositionSource("ps1", s=0.5)
        assert ps.source_kind == "prescribed_across"


# ── All translational domain ─────────────────────────────────────────


class TestAllTranslationalDomain:
    def test_all_components_translational(self):
        components = [
            TranslationalFixed("f1"),
            TranslationalSpring("k1", k=100.0),
            TranslationalDamper("d1", d=10.0),
            TranslationalMass("m1", m=1.0),
            ForceSource("fs1", F=1.0),
        ]
        for c in components:
            assert c.domain.name == "translational"

    def test_all_have_symbolic_equations(self):
        components = [
            TranslationalFixed("f1"),
            TranslationalSpring("k1", k=100.0),
            TranslationalDamper("d1", d=10.0),
            TranslationalMass("m1", m=1.0),
            ForceSource("fs1", F=1.0),
        ]
        for c in components:
            eqs = c.symbolic_equations()
            assert len(eqs) > 0, f"{c.name} has no symbolic equations"
