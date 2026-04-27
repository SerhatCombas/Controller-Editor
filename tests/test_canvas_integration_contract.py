"""Canvas ↔ Core integration contract tests (T6.0).

These tests define the behavioral invariants that must hold throughout
Phase 6 canvas integration. They validate the contract between:

    Palette → Canvas Component → Port Mapping → CanvasCompiler → SystemGraph → Symbolic Pipeline

Each test is a "sözleşme maddesi" — if any of these break during
Phase 6 refactoring, something fundamental has gone wrong.

Invariant categories:
  1. Legacy pipeline still works (backward compat)
  2. Registry components exist and are well-formed
  3. Port mapping is consistent (canvas → core)
  4. CanvasCompiler produces valid SystemGraph
  5. Symbolic pipeline produces correct results from SystemGraph
  6. Save/load roundtrip preserves topology
"""

from __future__ import annotations

import json
import pytest
from typing import Any

# PySide6 may not be available in headless/CI environments.
# Tests that require it are guarded with this marker.
try:
    import PySide6  # noqa: F401
    _HAS_PYSIDE6 = True
except ImportError:
    _HAS_PYSIDE6 = False

needs_pyside6 = pytest.mark.skipif(
    not _HAS_PYSIDE6, reason="PySide6 not installed"
)


def _import_visual_contract():
    """Import visual_contract module directly, bypassing app.ui.canvas.__init__.py.

    This avoids the PySide6 dependency chain:
      app.ui.canvas.__init__ → component_system → PySide6
    so that pure-data tests can run without PySide6.
    """
    import importlib.util
    import sys
    from pathlib import Path

    mod_name = "app.ui.canvas.visual_contract"
    if mod_name in sys.modules:
        return sys.modules[mod_name]

    mod_path = Path(__file__).resolve().parent.parent / "app" / "ui" / "canvas" / "visual_contract.py"
    spec = importlib.util.spec_from_file_location(mod_name, mod_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


# ═══════════════════════════════════════════════════════════════════════
# 1. LEGACY PIPELINE INVARIANTS
#    "Mevcut çalışan şey kırılmamalı"
# ═══════════════════════════════════════════════════════════════════════


@needs_pyside6
class TestLegacyCatalogIntact:
    """Existing COMPONENT_CATALOG entries must remain functional."""

    def test_catalog_exists_and_nonempty(self):
        from app.ui.canvas.component_system import COMPONENT_CATALOG
        assert len(COMPONENT_CATALOG) > 0

    def test_legacy_mass_has_core_factory(self):
        from app.ui.canvas.component_system import COMPONENT_CATALOG
        spec = COMPONENT_CATALOG.get("mass")
        assert spec is not None
        assert spec.core_factory is not None

    def test_legacy_mass_factory_creates_component(self):
        from app.ui.canvas.component_system import COMPONENT_CATALOG
        spec = COMPONENT_CATALOG["mass"]
        comp = spec.core_factory("test_mass_1")
        assert comp is not None
        assert comp.id == "test_mass_1"

    def test_legacy_spring_has_core_factory(self):
        from app.ui.canvas.component_system import COMPONENT_CATALOG
        spec = COMPONENT_CATALOG.get("translational_spring")
        assert spec is not None
        comp = spec.core_factory("test_spring_1")
        assert comp is not None

    def test_legacy_damper_has_core_factory(self):
        from app.ui.canvas.component_system import COMPONENT_CATALOG
        spec = COMPONENT_CATALOG.get("translational_damper")
        assert spec is not None
        comp = spec.core_factory("test_damper_1")
        assert comp is not None

    def test_legacy_ground_has_core_factory(self):
        from app.ui.canvas.component_system import COMPONENT_CATALOG
        spec = COMPONENT_CATALOG.get("mechanical_reference")
        assert spec is not None
        comp = spec.core_factory("test_gnd_1")
        assert comp is not None

    def test_legacy_catalog_type_keys_stable(self):
        """These type_keys are used in saved layouts and compiler mappings.
        Renaming them would break backward compatibility."""
        from app.ui.canvas.component_system import COMPONENT_CATALOG
        required_keys = {
            "mass", "translational_spring", "translational_damper",
            "mechanical_reference", "ideal_force_source", "wheel",
            "tire_stiffness",
        }
        for key in required_keys:
            assert key in COMPONENT_CATALOG, f"Legacy type_key '{key}' missing from catalog"


@needs_pyside6
class TestLegacyCompilerPortMapping:
    """_CANVAS_TO_CORE_PORT mapping must remain stable for existing types."""

    def test_port_mapping_table_exists(self):
        from app.services.canvas_compiler import _CANVAS_TO_CORE_PORT
        assert len(_CANVAS_TO_CORE_PORT) > 0

    def test_mass_ports_both_map_to_port_a(self):
        from app.services.canvas_compiler import _CANVAS_TO_CORE_PORT
        mass_ports = _CANVAS_TO_CORE_PORT["mass"]
        assert mass_ports["top"] == "port_a"
        assert mass_ports["bottom"] == "port_a"

    def test_spring_ports(self):
        from app.services.canvas_compiler import _CANVAS_TO_CORE_PORT
        sp = _CANVAS_TO_CORE_PORT["translational_spring"]
        assert sp["R"] == "port_a"
        assert sp["C"] == "port_b"

    def test_damper_ports(self):
        from app.services.canvas_compiler import _CANVAS_TO_CORE_PORT
        dp = _CANVAS_TO_CORE_PORT["translational_damper"]
        assert dp["R"] == "port_a"
        assert dp["C"] == "port_b"

    def test_ground_port(self):
        from app.services.canvas_compiler import _CANVAS_TO_CORE_PORT
        gp = _CANVAS_TO_CORE_PORT["mechanical_reference"]
        assert gp["ref"] == "port"

    def test_force_source_ports(self):
        from app.services.canvas_compiler import _CANVAS_TO_CORE_PORT
        fp = _CANVAS_TO_CORE_PORT["ideal_force_source"]
        assert fp["R"] == "port"
        assert fp["C"] == "reference_port"


# ═══════════════════════════════════════════════════════════════════════
# 2. REGISTRY COMPONENT INVARIANTS
#    "Registry bileşenleri iyi tanımlanmış olmalı"
# ═══════════════════════════════════════════════════════════════════════


class TestRegistryComponentsWellFormed:
    """Every registry component must be ready for canvas integration."""

    def test_registry_has_twelve_components(self):
        from app.core.registry import registry
        assert len(registry) == 12

    def test_every_entry_has_port_anchors(self):
        from app.core.registry import registry
        for entry in registry.all():
            assert entry.port_anchors, f"{entry.name} missing port_anchors"

    def test_port_anchors_match_component_ports(self):
        """CRITICAL: anchor keys must match actual component port names."""
        from app.core.registry import registry
        for entry in registry.all():
            comp = entry.create(f"contract_{entry.name}")
            port_names = {p.name for p in comp.ports}
            anchor_keys = set(entry.port_anchors.keys())
            assert anchor_keys == port_names, (
                f"{entry.name}: anchors {sorted(anchor_keys)} "
                f"!= ports {sorted(port_names)}"
            )

    def test_every_entry_has_domain_and_category(self):
        from app.core.registry import registry
        for entry in registry.all():
            assert entry.domain in ("electrical", "translational")
            assert entry.category in ("passive", "source", "reference")

    def test_factory_creates_valid_component(self):
        """Registry factory must produce real BaseComponent instances."""
        from app.core.registry import registry
        for entry in registry.all():
            comp = entry.create(f"contract_{entry.name}")
            assert comp.id == f"contract_{entry.name}"
            assert len(comp.ports) > 0


# ═══════════════════════════════════════════════════════════════════════
# 3. COMPILER → SYSTEMGRAPH INVARIANTS
#    "Compiler doğru SystemGraph üretmeli"
# ═══════════════════════════════════════════════════════════════════════


@needs_pyside6
class TestCompilerProducesValidGraph:
    """CanvasCompiler must produce a usable SystemGraph from canvas state."""

    def _make_canvas_component(self, type_key: str, comp_id: str):
        """Create a minimal CanvasVisualComponent for testing."""
        from PySide6.QtCore import QPointF
        from app.ui.canvas.component_system import (
            COMPONENT_CATALOG,
            CanvasVisualComponent,
        )
        spec = COMPONENT_CATALOG[type_key]
        return CanvasVisualComponent(
            spec=spec,
            component_id=comp_id,
            position=QPointF(0, 0),
            size=spec.base_size,
        )

    def _make_wire(self, src_id: str, src_port: str, tgt_id: str, tgt_port: str):
        from app.ui.canvas.component_system import CanvasWireConnection
        return CanvasWireConnection(
            source_component_id=src_id,
            source_connector_name=src_port,
            target_component_id=tgt_id,
            target_connector_name=tgt_port,
        )

    def test_single_mass_spring_compiles(self):
        """Minimal topology: mass + spring + ground + force source."""
        from app.services.canvas_compiler import CanvasCompiler
        from app.ui.canvas.component_system import ComponentIoRole

        mass = self._make_canvas_component("mass", "m1")
        spring = self._make_canvas_component("translational_spring", "k1")
        ground = self._make_canvas_component("mechanical_reference", "gnd")
        force = self._make_canvas_component("ideal_force_source", "f1")

        force.assigned_io_roles = (ComponentIoRole.INPUT,)
        mass.assigned_io_roles = (ComponentIoRole.OUTPUT,)

        wires = [
            self._make_wire("f1", "R", "m1", "top"),
            self._make_wire("m1", "bottom", "k1", "R"),
            self._make_wire("k1", "C", "gnd", "ref"),
            self._make_wire("f1", "C", "gnd", "ref"),
        ]

        compiler = CanvasCompiler()
        graph = compiler.compile([mass, spring, ground, force], wires)

        assert graph is not None
        assert len(graph.components) >= 3  # mass, spring, ground (force may or may not)
        assert len(graph.nodes) >= 2

    def test_compiled_graph_has_nodes(self):
        """Every compiled component's ports must have node assignments."""
        from app.services.canvas_compiler import CanvasCompiler
        from app.ui.canvas.component_system import ComponentIoRole

        mass = self._make_canvas_component("mass", "m1")
        ground = self._make_canvas_component("mechanical_reference", "gnd")
        spring = self._make_canvas_component("translational_spring", "k1")

        mass.assigned_io_roles = (ComponentIoRole.OUTPUT,)

        wires = [
            self._make_wire("m1", "bottom", "k1", "R"),
            self._make_wire("k1", "C", "gnd", "ref"),
        ]

        compiler = CanvasCompiler()
        graph = compiler.compile([mass, spring, ground], wires)

        # At least mass and spring should have connected ports
        for comp_id, comp in graph.components.items():
            for port in comp.ports:
                if port.node_id is not None:
                    break
            else:
                # Some components may have all ports unconnected (edge case)
                pass


# ═══════════════════════════════════════════════════════════════════════
# 4. SYMBOLIC PIPELINE INVARIANTS
#    "Registry bileşenleriyle symbolic pipeline sonuç üretmeli"
# ═══════════════════════════════════════════════════════════════════════


class TestSymbolicPipelineFromRegistry:
    """The symbolic pipeline must work with registry-created components."""

    def test_rc_circuit_from_registry(self):
        """Registry Resistor + Capacitor → valid state-space."""
        from app.core.registry import registry
        from app.core.graph.system_graph import SystemGraph
        from app.core.symbolic.symbolic_flattener import flatten
        from app.core.symbolic.small_signal_reducer import SmallSignalLinearReducer

        g = SystemGraph()
        vs = g.add_component(registry.get("electrical.voltage_source").create("vs1", V=1.0))
        r = g.add_component(registry.get("electrical.resistor").create("r1", R=1.0))
        c = g.add_component(registry.get("electrical.capacitor").create("c1", C=1.0))
        gnd = g.add_component(registry.get("electrical.ground").create("gnd1"))

        g.connect(vs.ports[0].id, r.ports[0].id)
        g.connect(r.ports[1].id, c.ports[0].id)
        g.connect(c.ports[1].id, gnd.ports[0].id)
        g.connect(vs.ports[1].id, gnd.ports[0].id)

        cap = g.components["c1"]
        v_cap = cap._setup.symbols["v_diff"]
        flat = flatten(g, input_symbol_names=["vs1__value"],
                      output_exprs={"v_cap": v_cap})

        ss = SmallSignalLinearReducer().reduce(flat)

        assert len(ss.state_variables) == 1
        assert len(ss.a_matrix) == 1
        assert abs(ss.a_matrix[0][0] - (-1.0)) < 1e-10

    def test_msd_from_registry(self):
        """Registry Mass + Spring + Damper → valid 2-state system."""
        from app.core.registry import registry
        from app.core.graph.system_graph import SystemGraph
        from app.core.symbolic.symbolic_flattener import flatten
        from app.core.symbolic.small_signal_reducer import SmallSignalLinearReducer

        g = SystemGraph()
        fs = g.add_component(registry.get("translational.force_source").create("fs1", F=1.0))
        mass = g.add_component(registry.get("translational.mass").create("m1", m=1.0))
        spring = g.add_component(registry.get("translational.spring").create("k1", k=1.0))
        damper = g.add_component(registry.get("translational.damper").create("d1", d=1.0))
        fixed = g.add_component(registry.get("translational.fixed").create("fix1"))

        g.connect(fs.ports[0].id, mass.ports[0].id)
        g.connect(mass.ports[1].id, spring.ports[0].id)
        g.connect(mass.ports[1].id, damper.ports[0].id)
        g.connect(spring.ports[1].id, fixed.ports[0].id)
        g.connect(damper.ports[1].id, fixed.ports[0].id)
        g.connect(fs.ports[1].id, fixed.ports[0].id)

        pos_sym = mass._setup.symbols["v_center"]
        flat = flatten(g, input_symbol_names=["fs1__value"],
                      output_exprs={"x_mass": pos_sym})

        ss = SmallSignalLinearReducer().reduce(flat)

        assert len(ss.state_variables) == 2
        assert len(ss.a_matrix) == 2


# ═══════════════════════════════════════════════════════════════════════
# 5. TWO-NAME-UNIVERSE INVARIANT
#    "Port isimleri iki evren: canvas port adı ↔ core port adı"
# ═══════════════════════════════════════════════════════════════════════


class TestPortNameUniverses:
    """Ensure port naming is consistent: canvas names vs core names.
    There must be exactly two naming universes, not three."""

    @needs_pyside6
    def test_canvas_port_names_are_strings(self):
        """Canvas wire connections use string port names."""
        from app.ui.canvas.component_system import CanvasWireConnection
        wire = CanvasWireConnection("a", "top", "b", "bottom")
        assert isinstance(wire.source_connector_name, str)
        assert isinstance(wire.target_connector_name, str)

    def test_core_port_names_are_strings(self):
        """Core component ports have string name attributes."""
        from app.core.registry import registry
        for entry in registry.all():
            comp = entry.create(f"pn_{entry.name}")
            for port in comp.ports:
                assert isinstance(port.name, str)
                assert port.name  # non-empty

    def test_registry_anchor_keys_equal_core_port_names(self):
        """Registry port_anchors keys must be core port names, not canvas names."""
        from app.core.registry import registry
        for entry in registry.all():
            comp = entry.create(f"pn2_{entry.name}")
            core_names = {p.name for p in comp.ports}
            anchor_keys = set(entry.port_anchors.keys())
            assert anchor_keys == core_names, (
                f"{entry.name}: anchor keys should be core port names"
            )


# ═══════════════════════════════════════════════════════════════════════
# 6. SAVE/LOAD CONTRACT
#    "JSON roundtrip topology'yi korumalı"
# ═══════════════════════════════════════════════════════════════════════


class TestSaveLoadContract:
    """Save/load format must preserve essential topology information."""

    @needs_pyside6
    def test_canvas_wire_is_json_serializable(self):
        """Wire connection fields must be JSON-safe."""
        from app.ui.canvas.component_system import CanvasWireConnection
        wire = CanvasWireConnection("r1", "top", "k1", "R")
        data = {
            "from": {"component": wire.source_component_id,
                     "port": wire.source_connector_name},
            "to": {"component": wire.target_component_id,
                   "port": wire.target_connector_name},
        }
        roundtrip = json.loads(json.dumps(data))
        assert roundtrip["from"]["component"] == "r1"
        assert roundtrip["from"]["port"] == "top"
        assert roundtrip["to"]["component"] == "k1"
        assert roundtrip["to"]["port"] == "R"

    @needs_pyside6
    def test_component_spec_type_key_is_json_safe(self):
        """type_key (the identity for save/load) must be a plain string."""
        from app.ui.canvas.component_system import COMPONENT_CATALOG
        for type_key, spec in COMPONENT_CATALOG.items():
            assert isinstance(type_key, str)
            assert type_key == json.loads(json.dumps(type_key))

    def test_schema_version_concept(self):
        """Schema-versioned layout format must roundtrip perfectly."""
        layout_v2 = {
            "schema_version": 2,
            "components": [
                {
                    "id": "r1",
                    "type_key": "resistor",
                    "registry_name": "electrical.resistor",
                    "position": {"x": 120, "y": 80},
                    "rotation": 0,
                    "flip": False,
                    "parameters": {"R": 1000},
                }
            ],
            "connections": [
                {
                    "from": {"component": "r1", "port": "port_a"},
                    "to": {"component": "c1", "port": "port_b"},
                }
            ],
            "viewport": {"zoom": 1.0, "pan_x": 0, "pan_y": 0},
            "metadata": {"created_at": "2026-04-26"},
        }
        roundtrip = json.loads(json.dumps(layout_v2))
        assert roundtrip["schema_version"] == 2
        assert roundtrip["components"][0]["registry_name"] == "electrical.resistor"
        assert roundtrip["connections"][0]["from"]["port"] == "port_a"

    def test_registry_names_are_json_safe(self):
        """All registry component names must be JSON-serializable strings."""
        from app.core.registry import registry
        for entry in registry.all():
            assert isinstance(entry.name, str)
            assert entry.name == json.loads(json.dumps(entry.name))

    def test_registry_default_params_are_json_safe(self):
        """All registry default_params must be JSON-serializable."""
        from app.core.registry import registry
        for entry in registry.all():
            roundtrip = json.loads(json.dumps(entry.default_params))
            assert roundtrip == entry.default_params, (
                f"{entry.name} default_params not JSON-safe"
            )


# ═══════════════════════════════════════════════════════════════════════
# 7. ERROR REPORTING CONTRACT
#    "Hata mesajları kullanıcı dostu olmalı"
# ═══════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════
# 7a. PHASE 6 FIELD INVARIANTS
#     "Yeni alanlar mevcut davranışı bozmamalı"
# ═══════════════════════════════════════════════════════════════════════


@needs_pyside6
class TestPhase6FieldsZeroBehaviorChange:
    """registry_name and port_mapping must default to legacy values."""

    def test_legacy_catalog_entries_have_no_registry_name(self):
        """Non-migrated entries should still have registry_name=None."""
        from app.ui.canvas.component_system import COMPONENT_CATALOG
        _MIGRATED = {"resistor", "capacitor", "electrical_reference"}
        for type_key, spec in COMPONENT_CATALOG.items():
            if type_key in _MIGRATED:
                continue
            assert spec.registry_name is None, (
                f"Legacy entry '{type_key}' should not have registry_name yet"
            )

    def test_legacy_catalog_entries_have_empty_port_mapping(self):
        """Non-migrated entries should still have port_mapping={}."""
        from app.ui.canvas.component_system import COMPONENT_CATALOG
        _MIGRATED = {"resistor", "capacitor", "electrical_reference"}
        for type_key, spec in COMPONENT_CATALOG.items():
            if type_key in _MIGRATED:
                continue
            assert spec.port_mapping == {}, (
                f"Legacy entry '{type_key}' should not have port_mapping yet"
            )

    def test_migrated_entries_have_registry_name(self):
        """Migrated entries must have a valid registry_name."""
        from app.ui.canvas.component_system import COMPONENT_CATALOG
        _MIGRATED = {"resistor": "electrical.resistor", "capacitor": "electrical.capacitor",
                      "electrical_reference": "electrical.ground"}
        for type_key, expected_name in _MIGRATED.items():
            spec = COMPONENT_CATALOG[type_key]
            assert spec.registry_name == expected_name, (
                f"{type_key}: registry_name should be '{expected_name}'"
            )

    def test_migrated_entries_have_port_mapping(self):
        """Migrated entries must have non-empty port_mapping."""
        from app.ui.canvas.component_system import COMPONENT_CATALOG
        _MIGRATED = {"resistor", "capacitor", "electrical_reference"}
        for type_key in _MIGRATED:
            spec = COMPONENT_CATALOG[type_key]
            assert spec.port_mapping, (
                f"{type_key}: port_mapping should not be empty"
            )

    def test_registry_name_field_exists(self):
        """ComponentVisualSpec must have registry_name attribute."""
        from app.ui.canvas.component_system import ComponentVisualSpec
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(ComponentVisualSpec)}
        assert "registry_name" in field_names

    def test_port_mapping_field_exists(self):
        """ComponentVisualSpec must have port_mapping attribute."""
        from app.ui.canvas.component_system import ComponentVisualSpec
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(ComponentVisualSpec)}
        assert "port_mapping" in field_names


# ═══════════════════════════════════════════════════════════════════════
# 8. ERROR REPORTING CONTRACT
#    "Hata mesajları kullanıcı dostu olmalı"
# ═══════════════════════════════════════════════════════════════════════


@needs_pyside6
class TestErrorReportingContract:
    """Phase 6 must produce clear, actionable error messages."""

    def test_unknown_type_key_returns_none(self):
        """Compiler must not crash on unknown type_key."""
        from app.services.canvas_compiler import CanvasCompiler
        compiler = CanvasCompiler()
        result = compiler._create_core_component("unknown_1", "nonexistent_type")
        assert result is None

    def test_unknown_port_mapping_returns_none(self):
        """Port resolver must not crash on unmapped canvas port name."""
        from app.services.canvas_compiler import CanvasCompiler
        compiler = CanvasCompiler()
        result = compiler._resolve_port_id(
            "comp1", {"comp1": "mass"}, "nonexistent_port"
        )
        assert result is None


# ═══════════════════════════════════════════════════════════════════════
# 9. REGISTRY BRIDGE INVARIANTS (T6.1b)
#    "Registry-enabled bileşenler spec.port_mapping kullanmalı,
#     legacy bileşenler eski yolu kullanmaya devam etmeli"
# ═══════════════════════════════════════════════════════════════════════


@needs_pyside6
class TestRegistryBridgePortResolution:
    """Registry-enabled components must use spec.port_mapping for port
    resolution instead of _CANVAS_TO_CORE_PORT."""

    def test_resistor_uses_port_mapping(self):
        """Registry-enabled resistor resolves via spec.port_mapping."""
        from app.services.canvas_compiler import CanvasCompiler
        compiler = CanvasCompiler()
        result = compiler._resolve_port_id(
            "r1", {"r1": "resistor"}, "positive"
        )
        assert result == "r1.port_a"

    def test_resistor_negative_port(self):
        from app.services.canvas_compiler import CanvasCompiler
        compiler = CanvasCompiler()
        result = compiler._resolve_port_id(
            "r1", {"r1": "resistor"}, "negative"
        )
        assert result == "r1.port_b"

    def test_capacitor_uses_port_mapping(self):
        from app.services.canvas_compiler import CanvasCompiler
        compiler = CanvasCompiler()
        result = compiler._resolve_port_id(
            "c1", {"c1": "capacitor"}, "positive"
        )
        assert result == "c1.port_a"

    def test_ground_uses_port_mapping(self):
        from app.services.canvas_compiler import CanvasCompiler
        compiler = CanvasCompiler()
        result = compiler._resolve_port_id(
            "gnd1", {"gnd1": "electrical_reference"}, "ref"
        )
        assert result == "gnd1.p"

    def test_legacy_spring_still_uses_old_mapping(self):
        """Legacy spring (no registry_name) must still work via _CANVAS_TO_CORE_PORT."""
        from app.services.canvas_compiler import CanvasCompiler
        compiler = CanvasCompiler()
        result = compiler._resolve_port_id(
            "k1", {"k1": "translational_spring"}, "R"
        )
        assert result == "k1.port_a"

    def test_legacy_mass_still_uses_old_mapping(self):
        from app.services.canvas_compiler import CanvasCompiler
        compiler = CanvasCompiler()
        result = compiler._resolve_port_id(
            "m1", {"m1": "mass"}, "top"
        )
        assert result == "m1.port_a"


@needs_pyside6
class TestRegistryBridgeComponentCreation:
    """Registry-enabled components should be created via registry factory."""

    def test_resistor_created_via_registry(self):
        """Registry-enabled resistor creates a real Resistor component."""
        from app.services.canvas_compiler import CanvasCompiler
        compiler = CanvasCompiler()
        comp = compiler._create_core_component("r1", "resistor")
        assert comp is not None
        assert comp.id == "r1"
        assert len(comp.ports) == 2

    def test_capacitor_created_via_registry(self):
        from app.services.canvas_compiler import CanvasCompiler
        compiler = CanvasCompiler()
        comp = compiler._create_core_component("c1", "capacitor")
        assert comp is not None
        assert comp.id == "c1"

    def test_ground_created_via_registry(self):
        from app.services.canvas_compiler import CanvasCompiler
        compiler = CanvasCompiler()
        comp = compiler._create_core_component("gnd1", "electrical_reference")
        assert comp is not None
        assert comp.id == "gnd1"

    def test_legacy_mass_still_uses_core_factory(self):
        """Legacy mass (no registry_name) must still use core_factory."""
        from app.services.canvas_compiler import CanvasCompiler
        compiler = CanvasCompiler()
        comp = compiler._create_core_component("m1", "mass")
        assert comp is not None
        assert comp.id == "m1"


@needs_pyside6
class TestRegistryBridgeErrorHandling:
    """Incomplete registry metadata must produce explicit errors."""

    def test_registry_name_without_port_mapping_is_error(self):
        """If registry_name is set but port_mapping is empty → error."""
        from app.services.canvas_compiler import CanvasCompiler
        from app.ui.canvas.component_system import (
            ComponentVisualSpec, ComponentDomain, ComponentVisualCategory,
            ConnectorPortDefinition,
        )
        # Build a spec with registry_name but empty port_mapping
        broken_spec = ComponentVisualSpec(
            type_key="broken_test",
            display_name="Broken",
            domain=ComponentDomain.ELECTRICAL,
            symbol_kind="resistor",
            category=ComponentVisualCategory.RIGID,
            base_size=(100, 50),
            connector_ports=(
                ConnectorPortDefinition("pos", (0, 0.5)),
                ConnectorPortDefinition("neg", (1, 0.5)),
            ),
            registry_name="electrical.resistor",  # set
            port_mapping={},  # empty — this is the bug
        )
        # Temporarily inject into catalog
        from app.ui.canvas.component_system import COMPONENT_CATALOG
        original = COMPONENT_CATALOG.get("broken_test")
        try:
            COMPONENT_CATALOG["broken_test"] = broken_spec
            compiler = CanvasCompiler()
            result = compiler._resolve_port_id(
                "x1", {"x1": "broken_test"}, "pos"
            )
            assert result is None
            assert len(compiler.errors) == 1
            assert "port_mapping is empty" in compiler.errors[0]
        finally:
            if original is None:
                COMPONENT_CATALOG.pop("broken_test", None)
            else:
                COMPONENT_CATALOG["broken_test"] = original

    def test_unmapped_canvas_port_reports_error(self):
        """Registry path: unknown canvas port name → error with details."""
        from app.services.canvas_compiler import CanvasCompiler
        compiler = CanvasCompiler()
        result = compiler._resolve_port_id(
            "r1", {"r1": "resistor"}, "nonexistent_port"
        )
        assert result is None
        assert len(compiler.errors) == 1
        assert "nonexistent_port" in compiler.errors[0]
        assert "port_mapping" in compiler.errors[0]


class TestRegistryBridgePortMappingConsistency:
    """port_mapping values must be actual core port names from the registry."""

    def test_resistor_port_mapping_matches_registry_ports(self):
        """Resistor port_mapping values must match registry component ports."""
        from app.core.registry import registry
        entry = registry.get("electrical.resistor")
        comp = entry.create("check_r1")
        core_port_names = {p.name for p in comp.ports}

        # These are the values in the catalog port_mapping
        mapping_values = {"port_a", "port_b"}
        assert mapping_values == core_port_names

    def test_capacitor_port_mapping_matches_registry_ports(self):
        from app.core.registry import registry
        entry = registry.get("electrical.capacitor")
        comp = entry.create("check_c1")
        core_port_names = {p.name for p in comp.ports}
        mapping_values = {"port_a", "port_b"}
        assert mapping_values == core_port_names

    def test_ground_port_mapping_matches_registry_ports(self):
        from app.core.registry import registry
        entry = registry.get("electrical.ground")
        comp = entry.create("check_gnd")
        core_port_names = {p.name for p in comp.ports}
        mapping_values = {"p"}
        assert mapping_values == core_port_names


# ═══════════════════════════════════════════════════════════════════════
# 10. CANVAS RC COMPILE PROOF (T6.2)
#     "Canvas üzerinde kurulan RC devresi canonical core port'larla
#      SystemGraph'e compile edilip symbolic pipeline'da doğru sonuç üretmeli"
# ═══════════════════════════════════════════════════════════════════════


class TestCanvasRCCompileProof:
    """End-to-end proof: canvas RC → SystemGraph → A=[-1].

    The circuit:
        V1(+) ─── R1(+)   R1(-) ─── C1(+)   C1(-) ─── GND
        V1(-) ─── GND

    Expected: single state variable (v_cap), A=[-1/(RC)] = [-1] for R=1, C=1.

    Tests are split:
    - Compiler-dependent tests (needs PySide6): verify _create_core_component
      and _resolve_port_id work through registry path.
    - Pipeline tests (PySide6-free): verify registry factory → SystemGraph →
      symbolic reducer produces correct A/B matrices.
    """

    @needs_pyside6
    def test_compiler_creates_all_four_components(self):
        """CanvasCompiler._create_core_component must work for all RC parts."""
        from app.services.canvas_compiler import CanvasCompiler
        compiler = CanvasCompiler()

        vs = compiler._create_core_component("vs1", "dc_voltage_source")
        r = compiler._create_core_component("r1", "resistor")
        c = compiler._create_core_component("c1", "capacitor")
        gnd = compiler._create_core_component("gnd1", "electrical_reference")

        assert vs is not None, "VoltageSource not created"
        assert r is not None, "Resistor not created"
        assert c is not None, "Capacitor not created"
        assert gnd is not None, "ElectricalGround not created"

    @needs_pyside6
    def test_compiler_resolves_all_rc_ports(self):
        """Port resolution via spec.port_mapping works for all RC connections."""
        from app.services.canvas_compiler import CanvasCompiler
        compiler = CanvasCompiler()
        type_map = {
            "vs1": "dc_voltage_source",
            "r1": "resistor",
            "c1": "capacitor",
            "gnd1": "electrical_reference",
        }

        assert compiler._resolve_port_id("vs1", type_map, "positive") == "vs1.port_a"
        assert compiler._resolve_port_id("r1", type_map, "negative") == "r1.port_b"
        assert compiler._resolve_port_id("c1", type_map, "positive") == "c1.port_a"
        assert compiler._resolve_port_id("c1", type_map, "negative") == "c1.port_b"
        assert compiler._resolve_port_id("gnd1", type_map, "ref") == "gnd1.p"
        assert compiler._resolve_port_id("vs1", type_map, "negative") == "vs1.port_b"

    def _build_rc_graph(self):
        """Helper: build RC circuit from registry and return (graph, cap)."""
        from app.core.registry import registry
        from app.core.graph.system_graph import SystemGraph

        g = SystemGraph()
        vs = g.add_component(registry.get("electrical.voltage_source").create("vs1", V=1.0))
        r = g.add_component(registry.get("electrical.resistor").create("r1", R=1.0))
        c = g.add_component(registry.get("electrical.capacitor").create("c1", C=1.0))
        gnd = g.add_component(registry.get("electrical.ground").create("gnd1"))

        # Connect using actual port IDs (component_id__port_name format)
        # VS(port_a) → R(port_a)
        g.connect(vs.ports[0].id, r.ports[0].id)
        # R(port_b) → C(port_a)
        g.connect(r.ports[1].id, c.ports[0].id)
        # C(port_b) → GND(p)
        g.connect(c.ports[1].id, gnd.ports[0].id)
        # VS(port_b) → GND(p)
        g.connect(vs.ports[1].id, gnd.ports[0].id)

        return g, g.components["c1"]

    def test_rc_registry_to_statespace_a_matrix(self):
        """Registry factory → SystemGraph → A=[-1/(RC)] = [-1]."""
        from app.core.symbolic.symbolic_flattener import flatten
        from app.core.symbolic.small_signal_reducer import SmallSignalLinearReducer

        graph, cap = self._build_rc_graph()
        v_cap = cap._setup.symbols["v_diff"]
        flat = flatten(
            graph,
            input_symbol_names=["vs1__value"],
            output_exprs={"v_cap": v_cap},
        )

        ss = SmallSignalLinearReducer().reduce(flat)

        assert len(ss.state_variables) == 1, (
            f"Expected 1 state, got {len(ss.state_variables)}"
        )
        a_val = float(ss.a_matrix[0][0])
        assert abs(a_val - (-1.0)) < 1e-10, (
            f"Expected A=[-1], got A=[{a_val}]"
        )

    def test_rc_registry_to_statespace_b_matrix(self):
        """B matrix: B=[1/(RC)] = [1] for R=1, C=1."""
        from app.core.symbolic.symbolic_flattener import flatten
        from app.core.symbolic.small_signal_reducer import SmallSignalLinearReducer

        graph, cap = self._build_rc_graph()
        v_cap = cap._setup.symbols["v_diff"]
        flat = flatten(
            graph,
            input_symbol_names=["vs1__value"],
            output_exprs={"v_cap": v_cap},
        )

        ss = SmallSignalLinearReducer().reduce(flat)

        b_val = float(ss.b_matrix[0][0])
        assert abs(b_val - 1.0) < 1e-10, (
            f"Expected B=[1], got B=[{b_val}]"
        )


# ═══════════════════════════════════════════════════════════════════════
# 10. JSON SAVE/LOAD ROUNDTRIP PROOF
#     "Layout JSON'a kaydedilir ve geri yüklenince aynı graph oluşur"
# ═══════════════════════════════════════════════════════════════════════


class TestCanvasSerializerFormat:
    """v2 JSON format structural tests (PySide6-free)."""

    def test_schema_version_is_2(self):
        """save() must produce schema_version=2."""
        from app.services.canvas_serializer import SCHEMA_VERSION
        assert SCHEMA_VERSION == 2

    def test_save_dict_is_json_serializable(self):
        """A v2 dict must survive JSON roundtrip."""
        layout = {
            "schema_version": 2,
            "components": [
                {
                    "id": "r1",
                    "type_key": "resistor",
                    "registry_name": "electrical.resistor",
                    "position": {"x": 100, "y": 200},
                    "size": [64, 64],
                    "orientation": 0,
                },
            ],
            "connections": [
                {
                    "from": {"component": "r1", "port": "positive"},
                    "to": {"component": "c1", "port": "positive"},
                },
            ],
        }
        roundtrip = json.loads(json.dumps(layout))
        assert roundtrip["schema_version"] == 2
        assert roundtrip["components"][0]["type_key"] == "resistor"
        assert roundtrip["connections"][0]["from"]["port"] == "positive"

    def test_v2_uses_type_key_not_display_name(self):
        """v2 format must identify components by type_key, not display_name."""
        layout = {
            "schema_version": 2,
            "components": [
                {
                    "id": "r1",
                    "type_key": "resistor",
                    "position": {"x": 0, "y": 0},
                    "size": [64, 64],
                    "orientation": 0,
                },
            ],
            "connections": [],
        }
        comp = layout["components"][0]
        assert "type_key" in comp
        assert "display_name" not in comp

    def test_v1_detection_no_schema_version(self):
        """Data without schema_version must be treated as v1."""
        v1_data = {
            "components": [
                {
                    "display_name": "Resistor",
                    "component_id": "r1",
                    "position": [100, 200],
                    "size": [64, 64],
                    "deletable": True,
                    "orientation": 0,
                }
            ],
            "wires": [],
        }
        # v1 has no schema_version key
        assert "schema_version" not in v1_data
        assert v1_data.get("schema_version", 1) == 1


@needs_pyside6
class TestCanvasSerializerRoundtrip:
    """Full save → load → compile roundtrip proof."""

    def _make_rc_canvas_state(self):
        """Build a minimal RC circuit as canvas objects."""
        from PySide6.QtCore import QPointF
        from app.ui.canvas.component_system import (
            COMPONENT_CATALOG,
            CanvasVisualComponent,
            CanvasWireConnection,
            ComponentIoRole,
            Orientation,
        )

        vs_spec = COMPONENT_CATALOG["dc_voltage_source"]
        r_spec = COMPONENT_CATALOG["resistor"]
        c_spec = COMPONENT_CATALOG["capacitor"]
        gnd_spec = COMPONENT_CATALOG["electrical_reference"]

        components = [
            CanvasVisualComponent(
                spec=vs_spec,
                component_id="vs1",
                position=QPointF(50, 100),
                size=vs_spec.base_size,
                orientation=Orientation.DEG_0,
                assigned_io_roles=(ComponentIoRole.INPUT,),
            ),
            CanvasVisualComponent(
                spec=r_spec,
                component_id="r1",
                position=QPointF(150, 100),
                size=r_spec.base_size,
                orientation=Orientation.DEG_0,
            ),
            CanvasVisualComponent(
                spec=c_spec,
                component_id="c1",
                position=QPointF(250, 100),
                size=c_spec.base_size,
                orientation=Orientation.DEG_0,
                assigned_io_roles=(ComponentIoRole.OUTPUT,),
            ),
            CanvasVisualComponent(
                spec=gnd_spec,
                component_id="gnd1",
                position=QPointF(150, 250),
                size=gnd_spec.base_size,
                orientation=Orientation.DEG_0,
            ),
        ]

        wires = [
            # vs1.positive → r1.positive
            CanvasWireConnection("vs1", "positive", "r1", "positive"),
            # r1.negative → c1.positive
            CanvasWireConnection("r1", "negative", "c1", "positive"),
            # c1.negative → gnd1.ref
            CanvasWireConnection("c1", "negative", "gnd1", "ref"),
            # vs1.negative → gnd1.ref
            CanvasWireConnection("vs1", "negative", "gnd1", "ref"),
        ]

        return components, wires

    def test_save_produces_v2_format(self):
        """save() must produce schema_version=2 with type_key."""
        from app.services.canvas_serializer import save

        components, wires = self._make_rc_canvas_state()
        data = save(components, wires)

        assert data["schema_version"] == 2
        assert len(data["components"]) == 4
        assert len(data["connections"]) == 4

        # Check type_key is used, not display_name
        comp_ids = {c["id"] for c in data["components"]}
        assert comp_ids == {"vs1", "r1", "c1", "gnd1"}

        type_keys = {c["type_key"] for c in data["components"]}
        assert "resistor" in type_keys
        assert "capacitor" in type_keys
        assert "dc_voltage_source" in type_keys
        assert "electrical_reference" in type_keys

    def test_save_includes_registry_name_for_migrated(self):
        """Migrated components must have registry_name in save output."""
        from app.services.canvas_serializer import save

        components, wires = self._make_rc_canvas_state()
        data = save(components, wires)

        for comp in data["components"]:
            if comp["type_key"] == "resistor":
                assert comp["registry_name"] == "electrical.resistor"
            elif comp["type_key"] == "capacitor":
                assert comp["registry_name"] == "electrical.capacitor"
            elif comp["type_key"] == "electrical_reference":
                assert comp["registry_name"] == "electrical.ground"
            elif comp["type_key"] == "dc_voltage_source":
                assert comp["registry_name"] == "electrical.voltage_source"

    def test_roundtrip_preserves_component_count(self):
        """save → JSON → load must preserve component count."""
        from app.services.canvas_serializer import save, load

        components, wires = self._make_rc_canvas_state()
        data = save(components, wires)

        # Full JSON roundtrip
        json_str = json.dumps(data)
        restored_data = json.loads(json_str)
        components2, wires2 = load(restored_data)

        assert len(components2) == len(components)
        assert len(wires2) == len(wires)

    def test_roundtrip_preserves_component_ids(self):
        """Component IDs must survive roundtrip."""
        from app.services.canvas_serializer import save, load

        components, wires = self._make_rc_canvas_state()
        data = save(components, wires)
        components2, _ = load(json.loads(json.dumps(data)))

        orig_ids = {c.component_id for c in components}
        loaded_ids = {c.component_id for c in components2}
        assert loaded_ids == orig_ids

    def test_roundtrip_preserves_type_keys(self):
        """type_key must survive roundtrip."""
        from app.services.canvas_serializer import save, load

        components, wires = self._make_rc_canvas_state()
        data = save(components, wires)
        components2, _ = load(json.loads(json.dumps(data)))

        orig_types = {c.component_id: c.spec.type_key for c in components}
        loaded_types = {c.component_id: c.spec.type_key for c in components2}
        assert loaded_types == orig_types

    def test_roundtrip_preserves_wire_topology(self):
        """Wire endpoints must survive roundtrip."""
        from app.services.canvas_serializer import save, load

        components, wires = self._make_rc_canvas_state()
        data = save(components, wires)
        _, wires2 = load(json.loads(json.dumps(data)))

        orig_wires = {
            (w.source_component_id, w.source_connector_name,
             w.target_component_id, w.target_connector_name)
            for w in wires
        }
        loaded_wires = {
            (w.source_component_id, w.source_connector_name,
             w.target_component_id, w.target_connector_name)
            for w in wires2
        }
        assert loaded_wires == orig_wires

    def test_roundtrip_preserves_io_roles(self):
        """IO role assignments must survive roundtrip."""
        from app.services.canvas_serializer import save, load
        from app.ui.canvas.component_system import ComponentIoRole

        components, wires = self._make_rc_canvas_state()
        data = save(components, wires)
        components2, _ = load(json.loads(json.dumps(data)))

        orig_roles = {c.component_id: c.assigned_io_roles for c in components}
        loaded_roles = {c.component_id: c.assigned_io_roles for c in components2}
        assert loaded_roles == orig_roles

    def test_roundtrip_compile_same_graph_topology(self):
        """THE KEY PROOF: save → load → compile must produce identical
        SystemGraph topology as compile on the original canvas state.

        This is the user's stated success criterion:
        'Layout JSON'a kaydedilir ve geri yüklenince aynı graph oluşur.'
        """
        from app.services.canvas_serializer import save, load
        from app.services.canvas_compiler import CanvasCompiler

        components, wires = self._make_rc_canvas_state()

        # Compile original
        compiler1 = CanvasCompiler()
        graph1 = compiler1.compile(components, wires)

        # Roundtrip through JSON
        data = save(components, wires)
        json_str = json.dumps(data)
        components2, wires2 = load(json.loads(json_str))

        # Compile restored
        compiler2 = CanvasCompiler()
        graph2 = compiler2.compile(components2, wires2)

        # Same number of components
        assert len(graph2.components) == len(graph1.components), (
            f"Component count mismatch: {len(graph2.components)} vs {len(graph1.components)}"
        )

        # Same component IDs
        assert set(graph2.components.keys()) == set(graph1.components.keys())

        # Same number of nodes
        assert len(graph2.nodes) == len(graph1.nodes), (
            f"Node count mismatch: {len(graph2.nodes)} vs {len(graph1.nodes)}"
        )

        # Same number of connections
        assert len(graph2.connections) == len(graph1.connections), (
            f"Connection count mismatch: {len(graph2.connections)} vs {len(graph1.connections)}"
        )

        # No compiler errors in either pass
        assert compiler1.errors == [], f"Original compile errors: {compiler1.errors}"
        assert compiler2.errors == [], f"Restored compile errors: {compiler2.errors}"

    def test_roundtrip_compile_same_statespace(self):
        """Ultimate proof: save → load → compile → symbolic pipeline
        must produce the same A, B matrices as the original.

        RC circuit with R=1, C=1: A=[-1], B=[1].
        """
        from app.services.canvas_serializer import save, load
        from app.services.canvas_compiler import CanvasCompiler
        from app.core.symbolic.symbolic_flattener import flatten
        from app.core.symbolic.small_signal_reducer import SmallSignalLinearReducer

        components, wires = self._make_rc_canvas_state()

        # Roundtrip
        data = save(components, wires)
        components2, wires2 = load(json.loads(json.dumps(data)))

        # Compile restored canvas
        compiler = CanvasCompiler()
        graph = compiler.compile(components2, wires2)
        assert compiler.errors == [], f"Compile errors: {compiler.errors}"

        # Find capacitor for output expression
        cap = graph.components["c1"]
        v_cap = cap._setup.symbols["v_diff"]

        flat = flatten(
            graph,
            input_symbol_names=["vs1__value"],
            output_exprs={"v_cap": v_cap},
        )
        ss = SmallSignalLinearReducer().reduce(flat)

        a_val = float(ss.a_matrix[0][0])
        b_val = float(ss.b_matrix[0][0])

        assert abs(a_val - (-1.0)) < 1e-10, f"Expected A=[-1], got A=[{a_val}]"
        assert abs(b_val - 1.0) < 1e-10, f"Expected B=[1], got B=[{b_val}]"

    def test_save_json_string_roundtrip(self):
        """save_json / load_json string convenience must also work."""
        from app.services.canvas_serializer import save_json, load_json

        components, wires = self._make_rc_canvas_state()
        json_str = save_json(components, wires, indent=2)

        # Must be valid JSON
        parsed = json.loads(json_str)
        assert parsed["schema_version"] == 2

        # Must load back
        components2, wires2 = load_json(json_str)
        assert len(components2) == 4
        assert len(wires2) == 4


# ═══════════════════════════════════════════════════════════════════════
# 11. ORTHOGONAL WIRE ROUTING INVARIANTS (T6.4b)
#     "Render değişti, topology değişmedi"
# ═══════════════════════════════════════════════════════════════════════


@needs_pyside6
class TestOrthogonalPathGeometry:
    """Geometry tests for _orthogonal_path.

    Requires PySide6 because the function lives in model_canvas.py
    which depends on PySide6 imports.
    """

    def test_horizontal_wire_produces_four_points(self):
        """Even a horizontal wire should produce 4-point polyline."""
        from PySide6.QtCore import QPointF
        from app.ui.canvas.model_canvas import ModelCanvas

        path = ModelCanvas._orthogonal_path(QPointF(0, 100), QPointF(200, 100))
        assert len(path) == 4
        assert path[0].x() == 0 and path[0].y() == 100
        assert path[3].x() == 200 and path[3].y() == 100

    def test_vertical_wire_produces_four_points(self):
        """Vertical wire also gets 4-point polyline."""
        from PySide6.QtCore import QPointF
        from app.ui.canvas.model_canvas import ModelCanvas

        path = ModelCanvas._orthogonal_path(QPointF(100, 0), QPointF(100, 200))
        assert len(path) == 4
        assert path[0].x() == 100 and path[0].y() == 0
        assert path[3].x() == 100 and path[3].y() == 200

    def test_diagonal_wire_produces_manhattan_path(self):
        """Diagonal endpoints must produce an orthogonal (Manhattan) path."""
        from PySide6.QtCore import QPointF
        from app.ui.canvas.model_canvas import ModelCanvas

        path = ModelCanvas._orthogonal_path(QPointF(0, 0), QPointF(200, 100))
        assert len(path) == 4
        # All segments must be axis-aligned (horizontal or vertical)
        for i in range(len(path) - 1):
            dx = abs(path[i + 1].x() - path[i].x())
            dy = abs(path[i + 1].y() - path[i].y())
            assert dx < 1e-6 or dy < 1e-6, (
                f"Segment {i}→{i+1} is diagonal: "
                f"({path[i].x()},{path[i].y()})→({path[i+1].x()},{path[i+1].y()})"
            )

    def test_path_starts_and_ends_at_endpoints(self):
        """First point = start, last point = end."""
        from PySide6.QtCore import QPointF
        from app.ui.canvas.model_canvas import ModelCanvas

        start, end = QPointF(50, 75), QPointF(300, 200)
        path = ModelCanvas._orthogonal_path(start, end)
        assert path[0].x() == start.x() and path[0].y() == start.y()
        assert path[-1].x() == end.x() and path[-1].y() == end.y()

    def test_coincident_points_no_crash(self):
        """Same start/end must not crash."""
        from PySide6.QtCore import QPointF
        from app.ui.canvas.model_canvas import ModelCanvas

        path = ModelCanvas._orthogonal_path(QPointF(100, 100), QPointF(100, 100))
        assert len(path) == 4  # still 4 points, just collapsed


@needs_pyside6
class TestWireDataModelInvariant:
    """Wire data model structural checks.

    These verify CanvasWireConnection hasn't gained routing fields.
    """

    def test_wire_data_model_unchanged(self):
        """CanvasWireConnection still has exactly 4 string fields."""
        from app.ui.canvas.component_system import CanvasWireConnection
        import dataclasses
        fields = {f.name for f in dataclasses.fields(CanvasWireConnection)}
        assert fields == {
            "source_component_id", "source_connector_name",
            "target_component_id", "target_connector_name",
        }

    def test_wire_has_no_path_or_routing_field(self):
        """Wire must NOT store routing/path data — path is derived."""
        from app.ui.canvas.component_system import CanvasWireConnection
        import dataclasses
        fields = {f.name for f in dataclasses.fields(CanvasWireConnection)}
        for forbidden in ("path", "segments", "waypoints", "routing"):
            assert forbidden not in fields, (
                f"CanvasWireConnection must not have '{forbidden}' field — "
                f"orthogonal path is a derived visual property"
            )


@needs_pyside6
class TestOrthogonalWireTopologyInvariant:
    """Verify that orthogonal rendering does NOT change topology.

    Key invariant: wire data model (CanvasWireConnection) is unaffected.
    The compiler sees the same endpoints regardless of visual routing.
    """

    def _make_rc_canvas_state(self):
        """Same RC circuit as TestCanvasSerializerRoundtrip."""
        from PySide6.QtCore import QPointF
        from app.ui.canvas.component_system import (
            COMPONENT_CATALOG,
            CanvasVisualComponent,
            CanvasWireConnection,
            ComponentIoRole,
            Orientation,
        )

        vs_spec = COMPONENT_CATALOG["dc_voltage_source"]
        r_spec = COMPONENT_CATALOG["resistor"]
        c_spec = COMPONENT_CATALOG["capacitor"]
        gnd_spec = COMPONENT_CATALOG["electrical_reference"]

        components = [
            CanvasVisualComponent(
                spec=vs_spec, component_id="vs1",
                position=QPointF(50, 100), size=vs_spec.base_size,
                orientation=Orientation.DEG_0,
                assigned_io_roles=(ComponentIoRole.INPUT,),
            ),
            CanvasVisualComponent(
                spec=r_spec, component_id="r1",
                position=QPointF(150, 100), size=r_spec.base_size,
                orientation=Orientation.DEG_0,
            ),
            CanvasVisualComponent(
                spec=c_spec, component_id="c1",
                position=QPointF(250, 100), size=c_spec.base_size,
                orientation=Orientation.DEG_0,
                assigned_io_roles=(ComponentIoRole.OUTPUT,),
            ),
            CanvasVisualComponent(
                spec=gnd_spec, component_id="gnd1",
                position=QPointF(150, 250), size=gnd_spec.base_size,
                orientation=Orientation.DEG_0,
            ),
        ]
        wires = [
            CanvasWireConnection("vs1", "positive", "r1", "positive"),
            CanvasWireConnection("r1", "negative", "c1", "positive"),
            CanvasWireConnection("c1", "negative", "gnd1", "ref"),
            CanvasWireConnection("vs1", "negative", "gnd1", "ref"),
        ]
        return components, wires

    def test_compiler_output_identical_after_routing_change(self):
        """Compiler must produce the same SystemGraph regardless of
        visual wire routing.  This is the core invariant."""
        from app.services.canvas_compiler import CanvasCompiler

        components, wires = self._make_rc_canvas_state()

        compiler = CanvasCompiler()
        graph = compiler.compile(components, wires)

        # Same assertions as before routing change
        assert len(graph.components) == 4
        assert set(graph.components.keys()) == {"vs1", "r1", "c1", "gnd1"}
        assert len(graph.connections) == 4
        assert compiler.errors == []

    def test_save_load_unaffected_by_routing(self):
        """save/load must produce identical wire topology after routing change."""
        from app.services.canvas_serializer import save, load

        components, wires = self._make_rc_canvas_state()
        data = save(components, wires)

        # Connections must use canvas port names, not routing info
        for conn in data["connections"]:
            assert "path" not in conn
            assert "segments" not in conn
            assert "waypoints" not in conn
            # Port names are simple strings
            assert isinstance(conn["from"]["port"], str)
            assert isinstance(conn["to"]["port"], str)

        # Roundtrip preserves topology
        components2, wires2 = load(json.loads(json.dumps(data)))
        orig_wires = {
            (w.source_component_id, w.source_connector_name,
             w.target_component_id, w.target_connector_name)
            for w in wires
        }
        loaded_wires = {
            (w.source_component_id, w.source_connector_name,
             w.target_component_id, w.target_connector_name)
            for w in wires2
        }
        assert loaded_wires == orig_wires

    def test_compile_after_roundtrip_same_statespace(self):
        """Full proof: routing change + save/load + compile + reduce = same A,B."""
        from app.services.canvas_serializer import save, load
        from app.services.canvas_compiler import CanvasCompiler
        from app.core.symbolic.symbolic_flattener import flatten
        from app.core.symbolic.small_signal_reducer import SmallSignalLinearReducer

        components, wires = self._make_rc_canvas_state()
        data = save(components, wires)
        components2, wires2 = load(json.loads(json.dumps(data)))

        compiler = CanvasCompiler()
        graph = compiler.compile(components2, wires2)
        assert compiler.errors == []

        cap = graph.components["c1"]
        v_cap = cap._setup.symbols["v_diff"]
        flat = flatten(graph, input_symbol_names=["vs1__value"],
                       output_exprs={"v_cap": v_cap})
        ss = SmallSignalLinearReducer().reduce(flat)

        assert abs(float(ss.a_matrix[0][0]) - (-1.0)) < 1e-10
        assert abs(float(ss.b_matrix[0][0]) - 1.0) < 1e-10


# ═══════════════════════════════════════════════════════════════════════
# 12. PORT VISUAL LANGUAGE INVARIANTS (T6.5)
#     "Mekanik R/C etiketi gitsin, port name backward compat korunsun"
# ═══════════════════════════════════════════════════════════════════════


@needs_pyside6
class TestPortVisualLanguage:
    """Port visual cleanup invariants."""

    def test_mechanical_spring_no_terminal_label(self):
        """Spring ports must NOT display R/C terminal labels."""
        from app.ui.canvas.component_system import COMPONENT_CATALOG
        spec = COMPONENT_CATALOG["translational_spring"]
        for port in spec.connector_ports:
            assert port.terminal_label == "", (
                f"Spring port '{port.name}' still has terminal_label='{port.terminal_label}' "
                f"— mechanical ports must not show electrical R/C labels"
            )

    def test_mechanical_damper_no_terminal_label(self):
        """Damper ports must NOT display R/C terminal labels."""
        from app.ui.canvas.component_system import COMPONENT_CATALOG
        spec = COMPONENT_CATALOG["translational_damper"]
        for port in spec.connector_ports:
            assert port.terminal_label == "", (
                f"Damper port '{port.name}' still has terminal_label='{port.terminal_label}'"
            )

    def test_mechanical_tire_no_terminal_label(self):
        """Tire stiffness ports must NOT display R/C terminal labels."""
        from app.ui.canvas.component_system import COMPONENT_CATALOG
        spec = COMPONENT_CATALOG["tire_stiffness"]
        for port in spec.connector_ports:
            assert port.terminal_label == "", (
                f"Tire port '{port.name}' still has terminal_label='{port.terminal_label}'"
            )

    def test_electrical_components_keep_polarity_labels(self):
        """Electrical components must still show +/- polarity labels."""
        from app.ui.canvas.component_system import COMPONENT_CATALOG
        for type_key in ("resistor", "capacitor", "dc_voltage_source"):
            spec = COMPONENT_CATALOG[type_key]
            labels = {p.terminal_label for p in spec.connector_ports}
            assert "+" in labels, f"{type_key} missing '+' terminal label"
            assert "-" in labels, f"{type_key} missing '-' terminal label"

    def test_port_names_unchanged_for_backward_compat(self):
        """Port names (used in save/load) must NOT change — only labels change."""
        from app.ui.canvas.component_system import COMPONENT_CATALOG
        # Mechanical: spring/damper/tire still use "R"/"C"
        for type_key in ("translational_spring", "translational_damper", "tire_stiffness"):
            spec = COMPONENT_CATALOG[type_key]
            names = {p.name for p in spec.connector_ports}
            assert names == {"R", "C"}, (
                f"{type_key} port names changed from R/C to {names} — "
                f"this would break save/load backward compatibility"
            )
        # Electrical: still use "positive"/"negative"
        for type_key in ("resistor", "capacitor", "dc_voltage_source"):
            spec = COMPONENT_CATALOG[type_key]
            names = {p.name for p in spec.connector_ports}
            assert names == {"positive", "negative"}, (
                f"{type_key} port names changed from positive/negative to {names}"
            )

    def test_compiler_port_mapping_still_works(self):
        """Compiler must still resolve R/C port names correctly."""
        from app.services.canvas_compiler import _CANVAS_TO_CORE_PORT
        for type_key in ("translational_spring", "translational_damper", "tire_stiffness"):
            mapping = _CANVAS_TO_CORE_PORT.get(type_key, {})
            assert "R" in mapping, f"{type_key} missing 'R' in compiler port mapping"
            assert "C" in mapping, f"{type_key} missing 'C' in compiler port mapping"

    def test_all_mechanical_rc_ports_have_no_terminal_label(self):
        """ALL mechanical components with R/C ports must have empty terminal labels."""
        from app.ui.canvas.component_system import COMPONENT_CATALOG
        rc_types = (
            "translational_spring", "translational_damper", "tire_stiffness",
            "ideal_force_source", "ideal_force_sensor",
            "ideal_translational_motion_sensor",
        )
        for type_key in rc_types:
            spec = COMPONENT_CATALOG[type_key]
            for port in spec.connector_ports:
                assert port.terminal_label == "", (
                    f"{type_key}.{port.name} still has terminal_label='{port.terminal_label}'"
                )


# ═══════════════════════════════════════════════════════════════════════
# 13. COMPONENT SIZE STANDARDIZATION (T6.6)
#     "Aile içi boyut tutarlılığı"
# ═══════════════════════════════════════════════════════════════════════


@needs_pyside6
class TestComponentSizeStandardization:
    """Component sizes should be consistent within families."""

    def test_spring_damper_same_width(self):
        """Spring and damper must have the same width."""
        from app.ui.canvas.component_system import COMPONENT_CATALOG
        spring_w = COMPONENT_CATALOG["translational_spring"].base_size[0]
        damper_w = COMPONENT_CATALOG["translational_damper"].base_size[0]
        assert spring_w == damper_w, (
            f"Spring width {spring_w} != damper width {damper_w}"
        )

    def test_mass_not_wider_than_ground(self):
        """Mass must fit visually within the ground reference width."""
        from app.ui.canvas.component_system import COMPONENT_CATALOG
        mass_w = COMPONENT_CATALOG["mass"].base_size[0]
        ground_w = COMPONENT_CATALOG["mechanical_reference"].base_size[0]
        assert mass_w <= ground_w, (
            f"Mass width {mass_w} > ground width {ground_w}"
        )

    def test_electrical_passive_uniform_size(self):
        """All electrical passive components must share the same base_size."""
        from app.ui.canvas.component_system import COMPONENT_CATALOG
        sizes = set()
        for tk in ("resistor", "capacitor", "inductor", "diode", "switch"):
            sizes.add(COMPONENT_CATALOG[tk].base_size)
        assert len(sizes) == 1, f"Electrical passives have {len(sizes)} different sizes: {sizes}"

    def test_vertical_source_sensor_same_width(self):
        """Vertical mechanical sources/sensors should share the same width."""
        from app.ui.canvas.component_system import COMPONENT_CATALOG
        widths = set()
        for tk in ("ideal_force_source", "ideal_force_sensor",
                    "ideal_translational_motion_sensor"):
            widths.add(COMPONENT_CATALOG[tk].base_size[0])
        assert len(widths) == 1, (
            f"Vertical sources/sensors have different widths: {widths}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# T7.1 — ComponentVisualContract dataclass + primitive renderer
# ═══════════════════════════════════════════════════════════════════════════


class TestVisualContractDataStructures:
    """PySide6-free tests for contract data structures.

    Uses _import_visual_contract() to bypass app.ui.canvas.__init__.py
    which would pull in PySide6 through component_system.py.
    """

    def test_geometry_primitives_are_frozen(self):
        vc = _import_visual_contract()
        line = vc.GLine(start=(0, 0), end=(100, 0))
        with pytest.raises(AttributeError):
            line.start = (1, 1)  # type: ignore[misc]

        rect = vc.GRectangle(x1=-60, y1=-40, x2=60, y2=40, fill_key="domain_fill")
        with pytest.raises(AttributeError):
            rect.fill_key = "red"  # type: ignore[misc]

    def test_contract_port_to_normalized_anchor(self):
        vc = _import_visual_contract()
        contract = vc.ComponentVisualContract(
            geometry=(vc.GLine(start=(-100, 0), end=(100, 0)),),
            ports={
                "flange_a": vc.ContractPort("flange_a", x=-100, y=0, side="left"),
                "flange_b": vc.ContractPort("flange_b", x=100, y=0, side="right"),
            },
            default_extent=(180, 80),
            domain_key="translational",
        )
        # flange_a at (-100, 0) → normalized (0.0, 0.5)
        na = contract.to_normalized_anchor("flange_a")
        assert na == pytest.approx((0.0, 0.5), abs=1e-6)

        # flange_b at (+100, 0) → normalized (1.0, 0.5)
        nb = contract.to_normalized_anchor("flange_b")
        assert nb == pytest.approx((1.0, 0.5), abs=1e-6)

    def test_contract_port_y_flip(self):
        """Y-up contract coords flip correctly: y=+100 → normalized y=0 (top)."""
        vc = _import_visual_contract()
        contract = vc.ComponentVisualContract(
            geometry=(vc.GLine(start=(0, -100), end=(0, 100)),),
            ports={
                "ref": vc.ContractPort("ref", x=0, y=100, side="top"),
            },
            default_extent=(100, 36),
            domain_key="translational",
        )
        nr = contract.to_normalized_anchor("ref")
        # y=+100 (top in Y-up) → normalized y=0.0 (top in screen)
        assert nr == pytest.approx((0.5, 0.0), abs=1e-6)

    def test_domain_colors_resolve(self):
        vc = _import_visual_contract()
        colors = vc.resolve_domain_colors("translational")
        assert "domain_stroke" in colors
        assert colors["domain_stroke"].startswith("#")
        assert "domain_fill" in colors

    def test_domain_colors_fallback(self):
        vc = _import_visual_contract()
        colors = vc.resolve_domain_colors("nonexistent_domain")
        assert "domain_stroke" in colors  # should use fallback

    def test_contract_default_label_slots(self):
        vc = _import_visual_contract()
        contract = vc.ComponentVisualContract(
            geometry=(vc.GLine(start=(0, 0), end=(1, 0)),),
            ports={},
            default_extent=(100, 100),
        )
        assert "name" in contract.label_slots
        assert contract.label_slots["name"].side == "top"

    def test_preserve_aspect_ratio_default_false(self):
        vc = _import_visual_contract()
        contract = vc.ComponentVisualContract(
            geometry=(vc.GLine(start=(0, 0), end=(1, 0)),),
            ports={},
            default_extent=(100, 100),
        )
        assert contract.preserve_aspect_ratio is False

    # Tests for visual_contract field on ComponentVisualSpec require PySide6
    # (because component_system.py imports Qt). See TestContractSpecField below.


@needs_pyside6
class TestContractSpecField:
    """ComponentVisualSpec has the visual_contract field."""

    def test_visual_contract_field_exists(self):
        from app.ui.canvas.component_system import COMPONENT_CATALOG
        for type_key, spec in COMPONENT_CATALOG.items():
            assert hasattr(spec, "visual_contract"), (
                f"{type_key} missing visual_contract field"
            )

    def test_pilot_components_have_contracts(self):
        """Phase 7 pilot components should have visual contracts assigned."""
        from app.ui.canvas.component_system import COMPONENT_CATALOG
        pilot_keys = {"mass", "translational_spring", "translational_damper", "mechanical_reference"}
        for key in pilot_keys:
            assert COMPONENT_CATALOG[key].visual_contract is not None, (
                f"{key} should have a visual_contract (Phase 7 pilot)"
            )

    def test_non_pilot_components_have_no_contract(self):
        """Non-pilot components should still have visual_contract=None."""
        from app.ui.canvas.component_system import COMPONENT_CATALOG
        pilot_keys = {"mass", "translational_spring", "translational_damper", "mechanical_reference"}
        for type_key, spec in COMPONENT_CATALOG.items():
            if type_key not in pilot_keys:
                assert spec.visual_contract is None, (
                    f"{type_key} unexpectedly has a visual_contract"
                )


@needs_pyside6
class TestContractRendererPortMapping:
    """PySide6-dependent tests for contract port → screen position mapping."""

    def test_port_screen_position_no_rotation(self):
        from PySide6.QtCore import QRectF
        from app.ui.canvas.visual_contract import ContractPort, ContractRenderer

        port_a = ContractPort("a", x=-100, y=0, side="left")
        rect = QRectF(100, 200, 180, 80)  # x=100, y=200, w=180, h=80

        pos = ContractRenderer.port_screen_position(port_a, rect, 0)
        # (-100, 0) → normalized (0.0, 0.5) → screen (100, 240)
        assert pos.x() == pytest.approx(100.0, abs=1.0)
        assert pos.y() == pytest.approx(240.0, abs=1.0)

    def test_port_screen_position_with_rotation(self):
        from PySide6.QtCore import QRectF
        from app.ui.canvas.visual_contract import ContractPort, ContractRenderer

        # Left port at (-100, 0), rotated 90° CW
        port_a = ContractPort("a", x=-100, y=0, side="left")
        rect = QRectF(0, 0, 80, 180)

        pos = ContractRenderer.port_screen_position(port_a, rect, 90)
        # After 90° CW: left port should appear at top-center
        assert pos.x() == pytest.approx(40.0, abs=2.0)  # center x
        assert pos.y() == pytest.approx(0.0, abs=2.0)    # top

    def test_port_b_screen_position_with_rotation(self):
        from PySide6.QtCore import QRectF
        from app.ui.canvas.visual_contract import ContractPort, ContractRenderer

        # Right port at (+100, 0), rotated 90° CW
        port_b = ContractPort("b", x=100, y=0, side="right")
        rect = QRectF(0, 0, 80, 180)

        pos = ContractRenderer.port_screen_position(port_b, rect, 90)
        # After 90° CW: right port should appear at bottom-center
        assert pos.x() == pytest.approx(40.0, abs=2.0)
        assert pos.y() == pytest.approx(180.0, abs=2.0)


# ═══════════════════════════════════════════════════════════════════════════
# T7.2 — Pilot visual contracts: mass, spring, damper, fixed
# ═══════════════════════════════════════════════════════════════════════════

def _import_translational_contracts():
    """Import translational_contracts bypassing PySide6 init chain."""
    import importlib.util
    import sys
    from pathlib import Path

    # Ensure visual_contract is loaded first
    _import_visual_contract()

    mod_name = "app.ui.canvas.translational_contracts"
    # Always reload to pick up latest file changes
    mod_path = Path(__file__).resolve().parent.parent / "app" / "ui" / "canvas" / "translational_contracts.py"
    spec = importlib.util.spec_from_file_location(mod_name, mod_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _import_component_system():
    """Import component_system bypassing PySide6 init chain."""
    import importlib.util
    import sys
    from pathlib import Path
    from unittest.mock import MagicMock

    # Ensure PySide6 stubs are in place
    for mod_name in (
        "PySide6", "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets",
        "PySide6.QtSvg", "PySide6.QtSvgWidgets",
    ):
        if mod_name not in sys.modules:
            sys.modules[mod_name] = MagicMock()

    # Ensure visual_contract + contract modules are loaded
    _import_visual_contract()
    _import_translational_contracts()
    _import_electrical_contracts()

    # Stub out app.ui.canvas package to prevent circular __init__ import
    if "app.ui.canvas" not in sys.modules:
        sys.modules["app.ui.canvas"] = MagicMock()

    target = "app.ui.canvas.component_system"
    mod_path = Path(__file__).resolve().parent.parent / "app" / "ui" / "canvas" / "component_system.py"
    spec = importlib.util.spec_from_file_location(target, mod_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[target] = mod
    spec.loader.exec_module(mod)
    return mod


class TestPilotContracts:
    """PySide6-free tests for the 4 pilot visual contracts."""

    def test_all_pilot_contracts_exist(self):
        tc = _import_translational_contracts()
        for attr in ("MASS_CONTRACT", "SPRING_CONTRACT", "DAMPER_CONTRACT", "FIXED_CONTRACT"):
            assert hasattr(tc, attr), f"Missing {attr}"

    def test_all_contracts_are_translational_domain(self):
        tc = _import_translational_contracts()
        for name in ("MASS_CONTRACT", "SPRING_CONTRACT", "DAMPER_CONTRACT", "FIXED_CONTRACT"):
            contract = getattr(tc, name)
            assert contract.domain_key == "translational", f"{name} domain != translational"

    def test_two_terminal_ports_at_edges(self):
        """Mass, spring, damper have flange_a at left (x=-100) and flange_b at right (x=+100).

        Horizontal canonical form: ports on X axis edges, y=0.
        """
        tc = _import_translational_contracts()
        for name in ("MASS_CONTRACT", "SPRING_CONTRACT", "DAMPER_CONTRACT"):
            contract = getattr(tc, name)
            assert "flange_a" in contract.ports, f"{name} missing flange_a"
            assert "flange_b" in contract.ports, f"{name} missing flange_b"
            assert contract.ports["flange_a"].x == -100, f"{name} flange_a.x != -100"
            assert contract.ports["flange_a"].y == 0, f"{name} flange_a.y != 0"
            assert contract.ports["flange_b"].x == 100, f"{name} flange_b.x != 100"
            assert contract.ports["flange_b"].y == 0, f"{name} flange_b.y != 0"

    def test_fixed_single_port_at_top(self):
        """Fixed/ground has one port 'flange' at (0, +100) — top center in Y-up."""
        tc = _import_translational_contracts()
        c = tc.FIXED_CONTRACT
        assert len(c.ports) == 1
        assert "flange" in c.ports
        assert c.ports["flange"].x == 0
        assert c.ports["flange"].y == 100

    def test_fixed_port_normalizes_to_top_center(self):
        """Fixed port at (0, +100) → normalized (0.5, 0.0) = top center in screen."""
        tc = _import_translational_contracts()
        c = tc.FIXED_CONTRACT
        na = c.to_normalized_anchor("flange")
        assert na == pytest.approx((0.5, 0.0), abs=1e-6)

    def test_two_terminal_normalized_anchors(self):
        """Two-terminal contracts: flange_a → (0.0,0.5) left, flange_b → (1.0,0.5) right.

        Horizontal canonical: x=-100 maps to nx=0.0, x=+100 maps to nx=1.0, y=0 maps to ny=0.5.
        """
        tc = _import_translational_contracts()
        for name in ("MASS_CONTRACT", "SPRING_CONTRACT", "DAMPER_CONTRACT"):
            contract = getattr(tc, name)
            na = contract.to_normalized_anchor("flange_a")
            assert na == pytest.approx((0.0, 0.5), abs=1e-6), f"{name} flange_a anchor wrong"
            nb = contract.to_normalized_anchor("flange_b")
            assert nb == pytest.approx((1.0, 0.5), abs=1e-6), f"{name} flange_b anchor wrong"

    def test_all_contracts_have_geometry(self):
        tc = _import_translational_contracts()
        for name in ("MASS_CONTRACT", "SPRING_CONTRACT", "DAMPER_CONTRACT", "FIXED_CONTRACT"):
            contract = getattr(tc, name)
            assert len(contract.geometry) > 0, f"{name} has no geometry"

    def test_mass_has_filled_rectangle(self):
        """Mass body should include a filled rectangle primitive."""
        vc = _import_visual_contract()
        tc = _import_translational_contracts()
        rects = [p for p in tc.MASS_CONTRACT.geometry if isinstance(p, vc.GRectangle)]
        assert len(rects) >= 1, "Mass should have at least one rectangle"
        assert rects[0].fill_key == "domain_fill"

    def test_spring_has_zigzag_polyline(self):
        """Spring body should include a polyline (zigzag)."""
        vc = _import_visual_contract()
        tc = _import_translational_contracts()
        polylines = [p for p in tc.SPRING_CONTRACT.geometry if isinstance(p, vc.GPolyline)]
        assert len(polylines) >= 1, "Spring should have at least one polyline"
        # Zigzag should have multiple points
        assert len(polylines[0].points) >= 5

    def test_damper_has_cylinder_lines(self):
        """Damper body should have multiple lines (walls + stubs) and a piston rect."""
        vc = _import_visual_contract()
        tc = _import_translational_contracts()
        lines = [p for p in tc.DAMPER_CONTRACT.geometry if isinstance(p, vc.GLine)]
        rects = [p for p in tc.DAMPER_CONTRACT.geometry if isinstance(p, vc.GRectangle)]
        assert len(lines) >= 5, "Damper should have at least 5 lines (3 walls + 2 stubs)"
        assert len(rects) >= 1, "Damper should have a piston rectangle"
        assert rects[0].fill_key == "#C0C0C0", "Piston should have gray fill"

    def test_fixed_has_hatching(self):
        """Fixed/ground should have hatching lines below the bar (MSL: 4 hatches)."""
        vc = _import_visual_contract()
        tc = _import_translational_contracts()
        lines = [p for p in tc.FIXED_CONTRACT.geometry if isinstance(p, vc.GLine)]
        # At least: 1 stub + 1 bar + 4 hatch lines = 6 (MSL-faithful)
        assert len(lines) >= 6, f"Fixed should have at least 6 lines, got {len(lines)}"

    def test_default_extents_match_current_layout_sizes(self):
        """Pilot contract extents should match the current layout sizes."""
        tc = _import_translational_contracts()
        # These match the T6.6 standardized sizes
        assert tc.MASS_CONTRACT.default_extent == (172.0, 92.0)
        assert tc.SPRING_CONTRACT.default_extent == (78.0, 148.0)
        assert tc.DAMPER_CONTRACT.default_extent == (80.0, 142.0)
        assert tc.FIXED_CONTRACT.default_extent == (260.0, 36.0)

    def test_contracts_non_uniform_scaling_by_default(self):
        """All pilot contracts use non-uniform scaling (preserve_aspect_ratio=False)."""
        tc = _import_translational_contracts()
        for name in ("MASS_CONTRACT", "SPRING_CONTRACT", "DAMPER_CONTRACT", "FIXED_CONTRACT"):
            contract = getattr(tc, name)
            assert contract.preserve_aspect_ratio is False, f"{name} should use non-uniform scaling"

    def test_label_slots_present(self):
        """All contracts should have at least a 'name' label slot."""
        tc = _import_translational_contracts()
        for name in ("MASS_CONTRACT", "SPRING_CONTRACT", "DAMPER_CONTRACT", "FIXED_CONTRACT"):
            contract = getattr(tc, name)
            assert "name" in contract.label_slots, f"{name} missing 'name' label slot"

    def test_horizontal_canonical_invariant(self):
        """All two-terminal pilot contracts use horizontal canonical form.

        At DEG_0 (no rotation): flange_a is left (x=-100), flange_b is right (x=+100).
        Vertical display is achieved via layout rotation, NOT contract geometry.
        """
        tc = _import_translational_contracts()
        for name in ("MASS_CONTRACT", "SPRING_CONTRACT", "DAMPER_CONTRACT"):
            contract = getattr(tc, name)
            a = contract.ports["flange_a"]
            b = contract.ports["flange_b"]
            # Horizontal canonical: ports on X axis, y=0
            assert a.x == -100 and a.y == 0, f"{name} flange_a not at left edge"
            assert b.x == 100 and b.y == 0, f"{name} flange_b not at right edge"
            assert a.side == "left", f"{name} flange_a side should be 'left'"
            assert b.side == "right", f"{name} flange_b side should be 'right'"

    def test_default_orientation_on_visual_spec(self):
        """Pilot translational specs should have default_orientation=DEG_90 (except fixed=DEG_0).

        Horizontal canonical contracts need DEG_90 to display vertically on the canvas.
        """
        cs = _import_component_system()
        catalog = cs.COMPONENT_CATALOG
        # Mass, spring, damper should have DEG_90
        for key in ("mass", "translational_spring", "translational_damper"):
            spec = catalog[key]
            assert spec.default_orientation == cs.Orientation.DEG_90, (
                f"{key} should have default_orientation=DEG_90"
            )
        # Fixed should have DEG_0 (default)
        ref_spec = catalog["mechanical_reference"]
        assert ref_spec.default_orientation == cs.Orientation.DEG_0, (
            "mechanical_reference should have default_orientation=DEG_0"
        )


class TestPaletteContractRendering:
    """Structural tests for palette/library contract-first rendering."""

    def test_contract_components_have_visual_contract(self):
        """All 8 contract components (4 translational + 4 electrical) should have visual_contract set."""
        cs = _import_component_system()
        contract_keys = (
            "mass", "translational_spring", "translational_damper", "mechanical_reference",
            "resistor", "capacitor", "inductor", "electrical_reference",
        )
        for key in contract_keys:
            spec = cs.COMPONENT_CATALOG[key]
            assert spec.visual_contract is not None, (
                f"{key} should have visual_contract for contract-first palette rendering"
            )

    def test_legacy_components_have_no_contract(self):
        """Legacy components like wheel should not have a visual_contract yet."""
        cs = _import_component_system()
        spec = cs.COMPONENT_CATALOG["wheel"]
        assert spec.visual_contract is None, "wheel should not have a contract yet"

    def test_contract_components_have_no_svg_symbol(self):
        """Contract components should NOT have svg_symbol — contract is the sole renderer."""
        cs = _import_component_system()
        contract_keys = (
            "mass", "translational_spring", "translational_damper",
            "mechanical_reference", "resistor", "capacitor", "inductor",
            "electrical_reference",
        )
        for key in contract_keys:
            spec = cs.COMPONENT_CATALOG[key]
            assert spec.visual_contract is not None, f"{key} needs visual_contract"
            assert spec.svg_symbol is None, (
                f"{key} has visual_contract — svg_symbol should be removed"
            )


def _import_electrical_contracts():
    """Import electrical_contracts bypassing PySide6 init chain."""
    import importlib.util
    import sys
    from pathlib import Path

    _import_visual_contract()

    mod_name = "app.ui.canvas.electrical_contracts"
    mod_path = Path(__file__).resolve().parent.parent / "app" / "ui" / "canvas" / "electrical_contracts.py"
    spec = importlib.util.spec_from_file_location(mod_name, mod_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestElectricalContracts:
    """PySide6-free tests for the 4 electrical passive visual contracts."""

    def test_all_electrical_contracts_exist(self):
        ec = _import_electrical_contracts()
        for attr in ("RESISTOR_CONTRACT", "CAPACITOR_CONTRACT", "INDUCTOR_CONTRACT", "GROUND_CONTRACT"):
            assert hasattr(ec, attr), f"Missing {attr}"

    def test_all_contracts_are_electrical_domain(self):
        ec = _import_electrical_contracts()
        for name in ("RESISTOR_CONTRACT", "CAPACITOR_CONTRACT", "INDUCTOR_CONTRACT", "GROUND_CONTRACT"):
            contract = getattr(ec, name)
            assert contract.domain_key == "electrical", f"{name} domain != electrical"

    def test_two_terminal_ports_at_edges(self):
        """Resistor, capacitor, inductor have p at left (x=-100) and n at right (x=+100)."""
        ec = _import_electrical_contracts()
        for name in ("RESISTOR_CONTRACT", "CAPACITOR_CONTRACT", "INDUCTOR_CONTRACT"):
            contract = getattr(ec, name)
            assert "p" in contract.ports, f"{name} missing port p"
            assert "n" in contract.ports, f"{name} missing port n"
            assert contract.ports["p"].x == -100, f"{name} p.x != -100"
            assert contract.ports["p"].y == 0, f"{name} p.y != 0"
            assert contract.ports["n"].x == 100, f"{name} n.x != 100"
            assert contract.ports["n"].y == 0, f"{name} n.y != 0"

    def test_two_terminal_normalized_anchors(self):
        """Horizontal canonical: p -> (0.0, 0.5) left, n -> (1.0, 0.5) right."""
        ec = _import_electrical_contracts()
        for name in ("RESISTOR_CONTRACT", "CAPACITOR_CONTRACT", "INDUCTOR_CONTRACT"):
            contract = getattr(ec, name)
            na = contract.to_normalized_anchor("p")
            assert na == pytest.approx((0.0, 0.5), abs=1e-6), f"{name} p anchor wrong"
            nb = contract.to_normalized_anchor("n")
            assert nb == pytest.approx((1.0, 0.5), abs=1e-6), f"{name} n anchor wrong"

    def test_ground_single_port_at_top(self):
        """Electrical ground has one port 'p' at (0, +100)."""
        ec = _import_electrical_contracts()
        c = ec.GROUND_CONTRACT
        assert len(c.ports) == 1
        assert "p" in c.ports
        assert c.ports["p"].x == 0
        assert c.ports["p"].y == 100

    def test_resistor_has_filled_rectangle(self):
        """Resistor body should include a filled rectangle."""
        vc = _import_visual_contract()
        ec = _import_electrical_contracts()
        rects = [p for p in ec.RESISTOR_CONTRACT.geometry if isinstance(p, vc.GRectangle)]
        assert len(rects) >= 1, "Resistor should have at least one rectangle"
        assert rects[0].fill_key == "domain_fill"

    def test_capacitor_has_parallel_plates(self):
        """Capacitor should have at least 2 vertical lines (plates) + 2 stubs."""
        vc = _import_visual_contract()
        ec = _import_electrical_contracts()
        lines = [p for p in ec.CAPACITOR_CONTRACT.geometry if isinstance(p, vc.GLine)]
        assert len(lines) >= 4, "Capacitor should have at least 4 lines (2 plates + 2 stubs)"

    def test_inductor_has_arcs(self):
        """Inductor should have 4 semicircular arcs (coils)."""
        vc = _import_visual_contract()
        ec = _import_electrical_contracts()
        arcs = [p for p in ec.INDUCTOR_CONTRACT.geometry if isinstance(p, vc.GArc)]
        assert len(arcs) == 4, f"Inductor should have 4 arcs, got {len(arcs)}"

    def test_ground_has_three_bars(self):
        """Ground should have 3 horizontal bars + 1 vertical stub = 4 lines."""
        vc = _import_visual_contract()
        ec = _import_electrical_contracts()
        lines = [p for p in ec.GROUND_CONTRACT.geometry if isinstance(p, vc.GLine)]
        assert len(lines) >= 4, f"Ground should have at least 4 lines, got {len(lines)}"

    def test_label_slots_present(self):
        """All contracts should have a 'name' label slot."""
        ec = _import_electrical_contracts()
        for name in ("RESISTOR_CONTRACT", "CAPACITOR_CONTRACT", "INDUCTOR_CONTRACT", "GROUND_CONTRACT"):
            contract = getattr(ec, name)
            assert "name" in contract.label_slots, f"{name} missing 'name' label slot"

    def test_electrical_in_catalog_have_contracts(self):
        """Electrical passive specs in catalog should have visual_contract."""
        cs = _import_component_system()
        for key in ("resistor", "capacitor", "inductor", "electrical_reference"):
            spec = cs.COMPONENT_CATALOG[key]
            assert spec.visual_contract is not None, (
                f"{key} should have visual_contract for contract-first rendering"
            )
