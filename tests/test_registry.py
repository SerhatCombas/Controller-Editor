"""Unit tests for ComponentRegistry and ComponentEntry (T5.2).

Tests cover:
- ComponentEntry creation, factory instantiation, icon path resolution
- ComponentRegistry CRUD: register, get, all, domains, categories
- Lookup: get_by_domain, get_by_category
- Free-text search across name, tags, description
- Default registration: 12 components across 2 domains, 3 categories
- Overwrite behavior on duplicate registration
"""

from __future__ import annotations

import pytest
from pathlib import Path

from app.core.registry import (
    ComponentEntry,
    ComponentRegistry,
    registry,
    _SYMBOLS_DIR,
)
from app.core.base.component import BaseComponent


# ── Fixtures ──────────────────────────────────────────────────────────


class DummyComponent(BaseComponent):
    """Minimal component for factory tests."""

    def __init__(self, component_id: str, **kwargs):
        self._id = component_id
        self._kwargs = kwargs

    @property
    def id(self) -> str:
        return self._id


def _make_entry(**overrides) -> ComponentEntry:
    defaults = dict(
        name="TestComp",
        component_class=DummyComponent,
        domain="test_domain",
        category="passive",
        tags=("tag1", "tag2"),
        icon_path="test/icon.svg",
        description="A test component",
        default_params={"x": 1.0},
    )
    defaults.update(overrides)
    return ComponentEntry(**defaults)


# ── ComponentEntry tests ──────────────────────────────────────────────


class TestComponentEntry:
    def test_frozen(self):
        entry = _make_entry()
        with pytest.raises(AttributeError):
            entry.name = "changed"

    def test_create_factory(self):
        entry = _make_entry(default_params={"x": 1.0})
        comp = entry.create("c1")
        assert comp.id == "c1"
        assert comp._kwargs == {"x": 1.0}

    def test_create_factory_override(self):
        entry = _make_entry(default_params={"x": 1.0, "y": 2.0})
        comp = entry.create("c2", x=99.0)
        assert comp._kwargs["x"] == 99.0
        assert comp._kwargs["y"] == 2.0

    def test_icon_abs_path_relative(self):
        entry = _make_entry(icon_path="electrical/resistor.svg")
        assert entry.icon_abs_path == _SYMBOLS_DIR / "electrical/resistor.svg"

    def test_icon_abs_path_absolute(self):
        entry = _make_entry(icon_path="/absolute/path/icon.svg")
        assert entry.icon_abs_path == Path("/absolute/path/icon.svg")

    def test_icon_abs_path_none(self):
        entry = _make_entry(icon_path=None)
        assert entry.icon_abs_path is None

    def test_default_tags_empty(self):
        entry = ComponentEntry(
            name="Bare",
            component_class=DummyComponent,
            domain="d",
            category="c",
        )
        assert entry.tags == ()
        assert entry.default_params == {}
        assert entry.description == ""


# ── ComponentRegistry (fresh instance) tests ──────────────────────────


class TestComponentRegistryFresh:
    def _fresh(self) -> ComponentRegistry:
        return ComponentRegistry()

    def test_empty_initially(self):
        r = self._fresh()
        assert len(r) == 0

    def test_register_and_get(self):
        r = self._fresh()
        entry = _make_entry(name="A")
        r.register(entry)
        assert r.get("A") is entry

    def test_get_missing_returns_none(self):
        r = self._fresh()
        assert r.get("missing") is None

    def test_contains(self):
        r = self._fresh()
        r.register(_make_entry(name="X"))
        assert "X" in r
        assert "Y" not in r

    def test_len(self):
        r = self._fresh()
        r.register(_make_entry(name="A"))
        r.register(_make_entry(name="B"))
        assert len(r) == 2

    def test_overwrite(self):
        r = self._fresh()
        r.register(_make_entry(name="A", description="v1"))
        r.register(_make_entry(name="A", description="v2"))
        assert len(r) == 1
        assert r.get("A").description == "v2"

    def test_all_sorted(self):
        r = self._fresh()
        r.register(_make_entry(name="B", domain="z"))
        r.register(_make_entry(name="A", domain="a"))
        r.register(_make_entry(name="C", domain="a"))
        names = [e.name for e in r.all()]
        assert names == ["A", "C", "B"]

    def test_get_by_domain(self):
        r = self._fresh()
        r.register(_make_entry(name="E1", domain="electrical"))
        r.register(_make_entry(name="M1", domain="mechanical"))
        r.register(_make_entry(name="E2", domain="electrical"))
        elec = r.get_by_domain("electrical")
        assert len(elec) == 2
        assert all(e.domain == "electrical" for e in elec)

    def test_get_by_category(self):
        r = self._fresh()
        r.register(_make_entry(name="P1", category="passive"))
        r.register(_make_entry(name="S1", category="source"))
        r.register(_make_entry(name="P2", category="passive"))
        passives = r.get_by_category("passive")
        assert len(passives) == 2

    def test_domains(self):
        r = self._fresh()
        r.register(_make_entry(name="A", domain="x"))
        r.register(_make_entry(name="B", domain="y"))
        r.register(_make_entry(name="C", domain="x"))
        assert r.domains() == ["x", "y"]

    def test_categories(self):
        r = self._fresh()
        r.register(_make_entry(name="A", category="passive"))
        r.register(_make_entry(name="B", category="source"))
        assert r.categories() == ["passive", "source"]

    def test_search_by_name(self):
        r = self._fresh()
        r.register(_make_entry(name="Resistor", domain="e", tags=()))
        r.register(_make_entry(name="Capacitor", domain="e", tags=()))
        results = r.search("resist")
        assert len(results) == 1
        assert results[0].name == "Resistor"

    def test_search_by_tag(self):
        r = self._fresh()
        r.register(_make_entry(name="A", tags=("ohm", "passive")))
        r.register(_make_entry(name="B", tags=("capacitance",)))
        results = r.search("ohm")
        assert len(results) == 1
        assert results[0].name == "A"

    def test_search_by_description(self):
        r = self._fresh()
        r.register(_make_entry(name="A", description="Linear resistor: v = R * i"))
        r.register(_make_entry(name="B", description="Capacitor: i = C * dv/dt"))
        results = r.search("dv/dt")
        assert len(results) == 1
        assert results[0].name == "B"

    def test_search_case_insensitive(self):
        r = self._fresh()
        r.register(_make_entry(name="Resistor"))
        assert len(r.search("RESISTOR")) == 1
        assert len(r.search("resistor")) == 1

    def test_search_no_results(self):
        r = self._fresh()
        r.register(_make_entry(name="A"))
        assert r.search("nonexistent") == []


# ── Singleton registry (default registrations) ───────────────────────


class TestDefaultRegistry:
    """Tests on the module-level singleton registry with auto-registered components."""

    def test_twelve_components(self):
        assert len(registry) == 12

    def test_two_domains(self):
        assert registry.domains() == ["electrical", "translational"]

    def test_three_categories(self):
        assert registry.categories() == ["passive", "reference", "source"]

    def test_six_electrical(self):
        assert len(registry.get_by_domain("electrical")) == 6

    def test_six_translational(self):
        assert len(registry.get_by_domain("translational")) == 6

    def test_electrical_passives(self):
        elec = registry.get_by_domain("electrical")
        passives = [e for e in elec if e.category == "passive"]
        names = sorted(e.name for e in passives)
        assert names == ["electrical.capacitor", "electrical.inductor", "electrical.resistor"]

    def test_translational_passives(self):
        trans = registry.get_by_domain("translational")
        passives = [e for e in trans if e.category == "passive"]
        names = sorted(e.name for e in passives)
        assert names == ["translational.damper", "translational.mass", "translational.spring"]

    def test_sources(self):
        sources = registry.get_by_category("source")
        names = sorted(e.name for e in sources)
        assert names == [
            "electrical.current_source", "electrical.voltage_source",
            "translational.force_source", "translational.position_source",
        ]

    def test_references(self):
        refs = registry.get_by_category("reference")
        names = sorted(e.name for e in refs)
        assert names == ["electrical.ground", "translational.fixed"]

    def test_search_capacitor(self):
        results = registry.search("capacitor")
        assert any(e.name == "electrical.capacitor" for e in results)

    def test_search_spring(self):
        results = registry.search("spring")
        assert any(e.name == "translational.spring" for e in results)

    def test_search_force(self):
        results = registry.search("force")
        assert any(e.name == "translational.force_source" for e in results)

    def test_resistor_has_icon(self):
        r = registry.get("electrical.resistor")
        assert r.icon_path == "electrical/resistor.svg"

    def test_resistor_default_params(self):
        r = registry.get("electrical.resistor")
        assert r.default_params == {"R": 1000.0}

    def test_mass_default_params(self):
        m = registry.get("translational.mass")
        assert m.default_params == {"m": 1.0}

    def test_factory_creates_real_component(self):
        """Registry factory should create actual component instances."""
        entry = registry.get("electrical.resistor")
        comp = entry.create("r_test", R=470.0)
        assert comp.id == "r_test"
        # Should be a real Resistor with ports
        assert len(comp.ports) == 2

    def test_factory_spring(self):
        entry = registry.get("translational.spring")
        comp = entry.create("k_test", k=500.0)
        assert comp.id == "k_test"
        assert len(comp.ports) == 2

    def test_all_entries_have_domain(self):
        for e in registry.all():
            assert e.domain in ("electrical", "translational")

    def test_all_entries_have_category(self):
        for e in registry.all():
            assert e.category in ("passive", "source", "reference")

    def test_all_entries_have_icon(self):
        for e in registry.all():
            assert e.icon_path is not None, f"{e.name} missing icon_path"

    def test_all_entries_have_description(self):
        for e in registry.all():
            assert e.description, f"{e.name} missing description"
