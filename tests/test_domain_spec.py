"""Tests for DomainSpec registry (T0.1)."""

from __future__ import annotations

import pytest

from app.core.base.domain import (
    DOMAIN_SPECS,
    ELECTRICAL_DOMAIN,
    MECHANICAL_TRANSLATIONAL_DOMAIN,
    Domain,
    DomainSpec,
    get_domain_spec,
)


# ---------------------------------------------------------------------------
# Registry completeness
# ---------------------------------------------------------------------------


def test_registry_has_four_domains():
    assert set(DOMAIN_SPECS.keys()) == {"electrical", "translational", "rotational", "thermal"}


def test_all_specs_are_domain_spec_instances():
    for spec in DOMAIN_SPECS.values():
        assert isinstance(spec, DomainSpec)


# ---------------------------------------------------------------------------
# DomainSpec is frozen (immutable)
# ---------------------------------------------------------------------------


def test_domain_spec_is_frozen():
    spec = DOMAIN_SPECS["electrical"]
    with pytest.raises(AttributeError):
        spec.name = "hacked"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Flange kinds are 2-tuples
# ---------------------------------------------------------------------------


def test_flange_kinds_are_pairs():
    for name, spec in DOMAIN_SPECS.items():
        assert len(spec.flange_kinds) == 2, f"{name}: expected 2 flange kinds"


# ---------------------------------------------------------------------------
# Power-conjugate invariant: effort × flow = power (W) — ALWAYS
# This is NOT across × through for mechanical domains!
# ---------------------------------------------------------------------------

EFFORT_FLOW_PAIRS = {
    #              (effort_unit, flow_unit)
    "electrical":    ("V",   "A"),       # V · A = W
    "translational": ("N",   "m/s"),     # N · (m/s) = W
    "rotational":    ("N·m", "rad/s"),   # (N·m) · (rad/s) = W
    "thermal":       ("K",   "W"),       # not a true power domain
}


def test_power_conjugate_effort_flow():
    """effort × flow = power must hold.  This is NOT across × through for mechanical!"""
    for name, (expected_effort, expected_flow) in EFFORT_FLOW_PAIRS.items():
        spec = DOMAIN_SPECS[name]
        assert spec.effort_unit == expected_effort, f"{name}: effort_unit mismatch"
        assert spec.flow_unit == expected_flow, f"{name}: flow_unit mismatch"


# ---------------------------------------------------------------------------
# Connector variables (across/through) — Modelica connector semantics
# ---------------------------------------------------------------------------

CONNECTOR_VARS = {
    #              (across_var, through_var, across_unit, through_unit)
    "electrical":    ("v",   "i",   "V",   "A"),
    "translational": ("s",   "f",   "m",   "N"),     # across=position, NOT velocity
    "rotational":    ("phi", "tau", "rad", "N·m"),    # across=angle, NOT angular velocity
    "thermal":       ("T",   "Phi", "K",   "W"),
}


def test_connector_variables():
    """across/through are Modelica connector variables, not power-conjugate pair."""
    for name, (a_var, t_var, a_unit, t_unit) in CONNECTOR_VARS.items():
        spec = DOMAIN_SPECS[name]
        assert spec.across_var == a_var, f"{name}: across_var"
        assert spec.through_var == t_var, f"{name}: through_var"
        assert spec.across_unit == a_unit, f"{name}: across_unit"
        assert spec.through_unit == t_unit, f"{name}: through_unit"


# ---------------------------------------------------------------------------
# power_order: 0 = effort≡across, 1 = flow=der(across)
# ---------------------------------------------------------------------------


def test_power_order():
    assert DOMAIN_SPECS["electrical"].power_order == 0,    "electrical: effort≡across"
    assert DOMAIN_SPECS["translational"].power_order == 1, "translational: flow=der(across)"
    assert DOMAIN_SPECS["rotational"].power_order == 1,    "rotational: flow=der(across)"
    assert DOMAIN_SPECS["thermal"].power_order == 0,       "thermal: no derivative"


def test_electrical_across_equals_effort():
    """For electrical, across≡effort and through≡flow."""
    spec = DOMAIN_SPECS["electrical"]
    assert spec.across_var == spec.effort_var
    assert spec.through_var == spec.flow_var


def test_translational_across_differs_from_effort():
    """For translational, across=position ≠ effort=force, flow=velocity ≠ through=force."""
    spec = DOMAIN_SPECS["translational"]
    assert spec.across_var != spec.effort_var   # s ≠ f
    assert spec.flow_var != spec.through_var     # v ≠ f


# ---------------------------------------------------------------------------
# to_domain() bridge — backward compatibility
# ---------------------------------------------------------------------------


def test_electrical_to_domain():
    legacy = DOMAIN_SPECS["electrical"].to_domain()
    assert isinstance(legacy, Domain)
    assert legacy.name == "electrical"
    assert legacy.across_variable == "voltage"
    assert legacy.through_variable == "current"


def test_translational_to_domain():
    """Legacy Domain: across_variable='velocity', through_variable='force'.

    This matches the existing MECHANICAL_TRANSLATIONAL_DOMAIN constant,
    NOT the Modelica connector convention (across=position, through=force).
    """
    legacy = DOMAIN_SPECS["translational"].to_domain()
    assert isinstance(legacy, Domain)
    assert legacy.name == "translational"
    assert legacy.across_variable == "velocity"
    assert legacy.through_variable == "force"


def test_to_domain_matches_existing_electrical_constant():
    """DomainSpec['electrical'].to_domain() should produce equivalent of ELECTRICAL_DOMAIN."""
    legacy = DOMAIN_SPECS["electrical"].to_domain()
    assert legacy.name == ELECTRICAL_DOMAIN.name
    assert legacy.across_variable == ELECTRICAL_DOMAIN.across_variable
    assert legacy.through_variable == ELECTRICAL_DOMAIN.through_variable


# ---------------------------------------------------------------------------
# get_domain_spec() lookup
# ---------------------------------------------------------------------------


def test_get_domain_spec_found():
    spec = get_domain_spec("electrical")
    assert spec is DOMAIN_SPECS["electrical"]


def test_get_domain_spec_not_found():
    with pytest.raises(KeyError):
        get_domain_spec("hydraulic")


# ---------------------------------------------------------------------------
# Legacy constants untouched
# ---------------------------------------------------------------------------


def test_legacy_constants_unchanged():
    assert MECHANICAL_TRANSLATIONAL_DOMAIN.name == "mechanical_translational"
    assert MECHANICAL_TRANSLATIONAL_DOMAIN.across_variable == "velocity"
    assert MECHANICAL_TRANSLATIONAL_DOMAIN.through_variable == "force"

    assert ELECTRICAL_DOMAIN.name == "electrical"
    assert ELECTRICAL_DOMAIN.across_variable == "voltage"
    assert ELECTRICAL_DOMAIN.through_variable == "current"
