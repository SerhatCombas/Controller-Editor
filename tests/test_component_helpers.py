"""Tests for MSL-derived component helpers (T0.4)."""

from __future__ import annotations

import sympy

from app.core.base.component_helpers import (
    PortSetup,
    add_one_port,
    add_one_port_pair,
    add_rigid_pair,
)
from app.core.base.equation import SymbolicEquation, der


# ===================================================================
# add_one_port
# ===================================================================


class TestAddOnePort:
    def test_returns_port_setup(self):
        result = add_one_port("gnd1", "electrical")
        assert isinstance(result, PortSetup)

    def test_single_port(self):
        result = add_one_port("gnd1", "electrical")
        assert len(result.ports) == 1

    def test_port_direction_hint_defaults_to_first_flange(self):
        result = add_one_port("gnd1", "electrical")
        assert result.ports[0].direction_hint == "positive"

    def test_custom_direction_hint(self):
        result = add_one_port("gnd1", "electrical", direction_hint="negative")
        assert result.ports[0].direction_hint == "negative"

    def test_no_topology_equations(self):
        result = add_one_port("gnd1", "electrical")
        assert result.equations == []

    def test_across_symbol_exists(self):
        result = add_one_port("gnd1", "electrical")
        assert "across" in result.symbols
        assert isinstance(result.symbols["across"], sympy.Symbol)

    def test_port_domain_is_electrical(self):
        result = add_one_port("gnd1", "electrical")
        assert result.ports[0].domain.name == "electrical"

    def test_translational_domain(self):
        result = add_one_port("fix1", "translational")
        assert result.ports[0].direction_hint == "a"
        assert result.ports[0].domain.name == "translational"

    def test_visual_anchor(self):
        result = add_one_port("gnd1", "electrical", visual_anchor=(0.5, 1.0))
        assert result.ports[0].visual_anchor == (0.5, 1.0)


# ===================================================================
# add_one_port_pair
# ===================================================================


class TestAddOnePortPair:
    def test_returns_two_ports(self):
        result = add_one_port_pair("r1", "electrical")
        assert len(result.ports) == 2

    def test_port_a_is_positive(self):
        result = add_one_port_pair("r1", "electrical")
        assert result.ports[0].direction_hint == "positive"
        assert result.ports[0].is_positive is True

    def test_port_b_is_negative(self):
        result = add_one_port_pair("r1", "electrical")
        assert result.ports[1].direction_hint == "negative"
        assert result.ports[1].is_negative is True

    def test_three_topology_equations(self):
        result = add_one_port_pair("r1", "electrical")
        assert len(result.equations) == 3

    def test_has_across_diff_equation(self):
        result = add_one_port_pair("r1", "electrical")
        provenances = [eq.provenance for eq in result.equations]
        assert "across_diff" in provenances

    def test_has_kcl_equation(self):
        result = add_one_port_pair("r1", "electrical")
        provenances = [eq.provenance for eq in result.equations]
        assert "KCL" in provenances

    def test_has_through_alias(self):
        result = add_one_port_pair("r1", "electrical")
        provenances = [eq.provenance for eq in result.equations]
        assert "through_alias" in provenances

    def test_kcl_equation_correct(self):
        """KCL: i_a + i_b = 0"""
        result = add_one_port_pair("r1", "electrical")
        kcl = [eq for eq in result.equations if eq.provenance == "KCL"][0]
        assert kcl.rhs == 0
        # lhs should be i_a + i_b
        assert result.symbols["i_a"] in kcl.lhs.free_symbols
        assert result.symbols["i_b"] in kcl.lhs.free_symbols

    def test_across_diff_equation_correct(self):
        """Electrical: v_diff = v_a - v_b (= v_positive - v_negative, MSL convention)."""
        result = add_one_port_pair("r1", "electrical")
        ad = [eq for eq in result.equations if eq.provenance == "across_diff"][0]
        assert ad.lhs == result.symbols["v_diff"]
        # rhs = v_a - v_b (positive minus negative)
        expected = result.symbols["v_a"] - result.symbols["v_b"]
        assert sympy.simplify(ad.rhs - expected) == 0

    def test_all_six_symbols_present(self):
        result = add_one_port_pair("r1", "electrical")
        expected_keys = {"v_a", "v_b", "i_a", "i_b", "v_diff", "through"}
        assert set(result.symbols.keys()) == expected_keys

    def test_electrical_through_alias_is_i_a(self):
        """Electrical: through = i_a (current into positive port, MSL: i = p.i)."""
        result = add_one_port_pair("r1", "electrical")
        ta = [eq for eq in result.equations if eq.provenance == "through_alias"][0]
        assert ta.rhs == result.symbols["i_a"]

    def test_translational_pair(self):
        result = add_one_port_pair("s1", "translational")
        assert result.ports[0].direction_hint == "a"
        assert result.ports[1].direction_hint == "b"
        assert result.ports[0].domain.name == "translational"

    def test_translational_across_diff_is_b_minus_a(self):
        """Translational: v_diff = v_b - v_a (= s_b - s_a, MSL: s_rel)."""
        result = add_one_port_pair("s1", "translational")
        ad = [eq for eq in result.equations if eq.provenance == "across_diff"][0]
        expected = result.symbols["v_b"] - result.symbols["v_a"]
        assert sympy.simplify(ad.rhs - expected) == 0

    def test_translational_through_alias_is_i_b(self):
        """Translational: through = i_b (force at flange_b, MSL: f = flange_b.f)."""
        result = add_one_port_pair("s1", "translational")
        ta = [eq for eq in result.equations if eq.provenance == "through_alias"][0]
        assert ta.rhs == result.symbols["i_b"]

    def test_visual_anchors(self):
        result = add_one_port_pair(
            "r1", "electrical",
            visual_anchor_a=(0.0, 0.5),
            visual_anchor_b=(1.0, 0.5),
        )
        assert result.ports[0].visual_anchor == (0.0, 0.5)
        assert result.ports[1].visual_anchor == (1.0, 0.5)


# ===================================================================
# add_rigid_pair
# ===================================================================


class TestAddRigidPair:
    def test_returns_two_ports(self):
        result = add_rigid_pair("m1", "translational")
        assert len(result.ports) == 2

    def test_no_kcl(self):
        """Critical: rigid pair does NOT have KCL — this is the MSL structural difference."""
        result = add_rigid_pair("m1", "translational")
        provenances = [eq.provenance for eq in result.equations]
        assert "KCL" not in provenances

    def test_has_rigid_coupling(self):
        result = add_rigid_pair("m1", "translational")
        provenances = [eq.provenance for eq in result.equations]
        assert "rigid_a" in provenances
        assert "rigid_b" in provenances

    def test_exactly_two_equations(self):
        """Only rigid coupling, no KCL, no through_alias."""
        result = add_rigid_pair("m1", "translational")
        assert len(result.equations) == 2

    def test_rigid_coupling_means_same_velocity(self):
        """v_a = v_center AND v_b = v_center"""
        result = add_rigid_pair("m1", "translational")
        rigid_a = [eq for eq in result.equations if eq.provenance == "rigid_a"][0]
        rigid_b = [eq for eq in result.equations if eq.provenance == "rigid_b"][0]
        # Both rhs should be v_center
        assert rigid_a.rhs == result.symbols["v_center"]
        assert rigid_b.rhs == result.symbols["v_center"]
        # lhs should be v_a and v_b
        assert rigid_a.lhs == result.symbols["v_a"]
        assert rigid_b.lhs == result.symbols["v_b"]

    def test_five_symbols_present(self):
        result = add_rigid_pair("m1", "translational")
        expected_keys = {"v_a", "v_b", "f_a", "f_b", "v_center"}
        assert set(result.symbols.keys()) == expected_keys

    def test_force_symbols_available_for_newton(self):
        """Component uses f_a and f_b to write m * a = f_a + f_b."""
        result = add_rigid_pair("m1", "translational")
        f_a = result.symbols["f_a"]
        f_b = result.symbols["f_b"]
        v_center = result.symbols["v_center"]
        m = sympy.Symbol("m1__m", real=True)

        # Component would write: m * der(v_center) = f_a + f_b
        newton = SymbolicEquation(
            lhs=m * der(v_center),
            rhs=f_a + f_b,
            provenance="Newton",
        )
        assert newton.has_derivative() is True
        assert f_a in newton.free_symbols()
        assert f_b in newton.free_symbols()


# ===================================================================
# Cross-domain consistency
# ===================================================================


class TestCrossDomain:
    def test_all_domains_work_with_one_port_pair(self):
        for domain in ("electrical", "translational", "rotational", "thermal"):
            result = add_one_port_pair(f"comp_{domain}", domain)
            assert len(result.ports) == 2
            assert len(result.equations) == 3

    def test_all_domains_work_with_rigid_pair(self):
        for domain in ("electrical", "translational", "rotational", "thermal"):
            result = add_rigid_pair(f"comp_{domain}", domain)
            assert len(result.ports) == 2
            assert len(result.equations) == 2
            # No KCL in any domain's rigid pair
            assert all(eq.provenance != "KCL" for eq in result.equations)
