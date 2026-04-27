"""Tests for Port enrichment — direction_hint & visual_anchor (T0.2)."""

from __future__ import annotations

import pytest

from app.core.base.domain import ELECTRICAL_DOMAIN, MECHANICAL_TRANSLATIONAL_DOMAIN
from app.core.base.port import Port


# ---------------------------------------------------------------------------
# Backward compatibility — existing code creates Ports without new fields
# ---------------------------------------------------------------------------


def _make_port(**overrides) -> Port:
    defaults = dict(
        id="p1",
        name="port_a",
        domain=MECHANICAL_TRANSLATIONAL_DOMAIN,
        component_id="comp1",
    )
    defaults.update(overrides)
    return Port(**defaults)


def test_default_direction_hint_is_none():
    p = _make_port()
    assert p.direction_hint is None


def test_default_visual_anchor_is_none():
    p = _make_port()
    assert p.visual_anchor is None


def test_existing_port_creation_still_works():
    """All existing Port() calls in the codebase use only id/name/domain/component_id + optionals."""
    p = Port(
        id="p1",
        name="port_a",
        domain=ELECTRICAL_DOMAIN,
        component_id="r1",
        node_id="n1",
    )
    assert p.node_id == "n1"
    assert p.direction_hint is None
    assert p.visual_anchor is None


# ---------------------------------------------------------------------------
# direction_hint
# ---------------------------------------------------------------------------


def test_electrical_positive_hint():
    p = _make_port(domain=ELECTRICAL_DOMAIN, direction_hint="positive")
    assert p.direction_hint == "positive"
    assert p.is_positive is True
    assert p.is_negative is False


def test_electrical_negative_hint():
    p = _make_port(domain=ELECTRICAL_DOMAIN, direction_hint="negative")
    assert p.is_positive is False
    assert p.is_negative is True


def test_mechanical_a_hint():
    p = _make_port(direction_hint="a")
    assert p.is_positive is True
    assert p.is_negative is False


def test_mechanical_b_hint():
    p = _make_port(direction_hint="b")
    assert p.is_positive is False
    assert p.is_negative is True


def test_no_hint_is_neither_positive_nor_negative():
    p = _make_port()
    assert p.is_positive is False
    assert p.is_negative is False


# ---------------------------------------------------------------------------
# visual_anchor
# ---------------------------------------------------------------------------


def test_visual_anchor_set():
    p = _make_port(visual_anchor=(0.0, 0.5))
    assert p.visual_anchor == (0.0, 0.5)


def test_visual_anchor_right_side():
    p = _make_port(visual_anchor=(1.0, 0.5))
    assert p.visual_anchor[0] == 1.0


# ---------------------------------------------------------------------------
# validate_compatibility still works
# ---------------------------------------------------------------------------


def test_compatibility_same_domain():
    p1 = _make_port(id="p1", direction_hint="a")
    p2 = _make_port(id="p2", direction_hint="b")
    # Should not raise
    p1.validate_compatibility(p2)


def test_compatibility_different_domain_raises():
    p1 = _make_port(id="p1", domain=ELECTRICAL_DOMAIN)
    p2 = _make_port(id="p2", domain=MECHANICAL_TRANSLATIONAL_DOMAIN)
    with pytest.raises(ValueError, match="Incompatible port domains"):
        p1.validate_compatibility(p2)
