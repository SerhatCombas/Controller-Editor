"""ComponentRegistry — discoverable component catalog (T5.2).

Provides a central registry for all component classes, supporting:
- Registration with metadata (domain, category, tags, icon path)
- Lookup by domain, category, or free-text search
- Factory instantiation from registry entries

Used by the Model Library Panel to present available components
and by the workspace to instantiate components from user selections.

Usage::

    from app.core.registry import registry

    # Lookup
    electrical = registry.get_by_domain("electrical")
    sources = registry.get_by_category("source")
    results = registry.search("capacitor")

    # Factory
    entry = registry.get("electrical.capacitor")
    component = entry.create("c1", C=1e-6)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Type

from app.core.base.component import BaseComponent

# Base path for SVG symbols
_SYMBOLS_DIR = Path(__file__).parent / "symbols"


@dataclass(frozen=True)
class ComponentEntry:
    """A registered component in the catalog.

    Attributes:
        name: Stable technical ID (e.g. 'electrical.resistor', 'translational.spring').
            Format: ``domain.component_kind``. Used in JSON save/load, compiler
            lookups, and cross-system references. Must never change once established.
        display_name: Human-readable name for UI (e.g. 'Resistor', 'Translational Spring').
        component_class: The BaseComponent subclass or factory function.
        domain: Domain name (e.g. 'electrical', 'translational').
        category: Component category ('passive', 'source', 'sensor', 'reference').
        tags: Searchable tags.
        icon_path: Path to SVG icon file (relative to symbols dir or absolute).
        description: One-line description for UI tooltips.
        default_params: Default parameter kwargs for factory instantiation.
        port_anchors: Visual port positions in SVG coordinate space (0-64).
            Maps port name → (x, y). Used by canvas for snapping, connection
            lines, and hit-testing. Rotate/flip transforms are applied to
            these coordinates at render time — physical port semantics are
            NOT affected by visual transforms.
    """
    name: str
    component_class: Type[BaseComponent] | Callable[..., BaseComponent]
    domain: str
    category: str
    display_name: str = ""
    tags: tuple[str, ...] = ()
    icon_path: str | None = None
    description: str = ""
    default_params: dict[str, Any] = field(default_factory=dict)
    port_anchors: dict[str, tuple[float, float]] = field(default_factory=dict)

    @property
    def label(self) -> str:
        """UI display name. Falls back to name if display_name is empty."""
        return self.display_name or self.name

    def create(self, component_id: str, **kwargs: Any) -> BaseComponent:
        """Instantiate a component, merging default_params with overrides."""
        merged = {**self.default_params, **kwargs}
        return self.component_class(component_id, **merged)

    @property
    def icon_abs_path(self) -> Path | None:
        """Resolve icon path to absolute."""
        if self.icon_path is None:
            return None
        p = Path(self.icon_path)
        if p.is_absolute():
            return p
        return _SYMBOLS_DIR / p


class ComponentRegistry:
    """Central registry for component classes.

    Thread-safe for reads after initial registration (no locking needed
    for the typical use case of register-at-import, query-at-runtime).
    """

    def __init__(self) -> None:
        self._entries: dict[str, ComponentEntry] = {}

    def register(self, entry: ComponentEntry) -> None:
        """Register a component entry. Overwrites if name already exists."""
        self._entries[entry.name] = entry

    def get(self, name: str) -> ComponentEntry | None:
        """Get a specific entry by name."""
        return self._entries.get(name)

    def all(self) -> list[ComponentEntry]:
        """Return all registered entries, sorted by domain then name."""
        return sorted(self._entries.values(), key=lambda e: (e.domain, e.name))

    def get_by_domain(self, domain: str) -> list[ComponentEntry]:
        """Return entries matching a domain name."""
        return [e for e in self._entries.values() if e.domain == domain]

    def get_by_category(self, category: str) -> list[ComponentEntry]:
        """Return entries matching a category."""
        return [e for e in self._entries.values() if e.category == category]

    def search(self, query: str) -> list[ComponentEntry]:
        """Free-text search across name, display_name, domain, category, tags, description."""
        q = query.lower()
        results = []
        for e in self._entries.values():
            searchable = " ".join([
                e.name.lower(),
                e.display_name.lower(),
                e.domain.lower(),
                e.category.lower(),
                " ".join(e.tags).lower(),
                e.description.lower(),
            ])
            if q in searchable:
                results.append(e)
        return sorted(results, key=lambda e: (e.domain, e.name))

    def domains(self) -> list[str]:
        """Return list of unique domain names."""
        return sorted({e.domain for e in self._entries.values()})

    def categories(self) -> list[str]:
        """Return list of unique categories."""
        return sorted({e.category for e in self._entries.values()})

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, name: str) -> bool:
        return name in self._entries


# ---------------------------------------------------------------------------
# Singleton registry instance
# ---------------------------------------------------------------------------
registry = ComponentRegistry()


def _register_defaults() -> None:
    """Register all built-in components."""

    # === Electrical ===
    from app.core.models.electrical.resistor import Resistor
    from app.core.models.electrical.capacitor import Capacitor
    from app.core.models.electrical.inductor import Inductor
    from app.core.models.electrical.ground import ElectricalGround
    from app.core.models.electrical.source import (
        VoltageSource, CurrentSource,
    )

    # Two-port electrical: port_a at left (0,32), port_b at right (64,32)
    _ELEC_TWO_PORT = {"port_a": (0.0, 32.0), "port_b": (64.0, 32.0)}

    registry.register(ComponentEntry(
        name="electrical.resistor", display_name="Resistor",
        component_class=Resistor,
        domain="electrical", category="passive",
        tags=("electrical", "resistor", "passive", "ohm"),
        icon_path="electrical/resistor.svg",
        description="Linear resistor: v = R * i",
        default_params={"R": 1000.0},
        port_anchors=_ELEC_TWO_PORT,
    ))
    registry.register(ComponentEntry(
        name="electrical.capacitor", display_name="Capacitor",
        component_class=Capacitor,
        domain="electrical", category="passive",
        tags=("electrical", "capacitor", "passive", "energy"),
        icon_path="electrical/capacitor.svg",
        description="Linear capacitor: i = C * dv/dt",
        default_params={"C": 1e-6},
        port_anchors=_ELEC_TWO_PORT,
    ))
    registry.register(ComponentEntry(
        name="electrical.inductor", display_name="Inductor",
        component_class=Inductor,
        domain="electrical", category="passive",
        tags=("electrical", "inductor", "passive", "energy"),
        icon_path="electrical/inductor.svg",
        description="Linear inductor: v = L * di/dt",
        default_params={"L": 1e-3},
        port_anchors=_ELEC_TWO_PORT,
    ))
    registry.register(ComponentEntry(
        name="electrical.ground", display_name="Electrical Ground",
        component_class=ElectricalGround,
        domain="electrical", category="reference",
        tags=("electrical", "ground", "reference"),
        icon_path="electrical/ground.svg",
        description="Electrical ground reference: v = 0",
        port_anchors={"p": (32.0, 0.0)},
    ))
    registry.register(ComponentEntry(
        name="electrical.voltage_source", display_name="Voltage Source",
        component_class=VoltageSource,
        domain="electrical", category="source",
        tags=("electrical", "source", "voltage"),
        icon_path="electrical/voltage_source.svg",
        description="Ideal voltage source: v = V",
        default_params={"V": 1.0},
        port_anchors=_ELEC_TWO_PORT,
    ))
    registry.register(ComponentEntry(
        name="electrical.current_source", display_name="Current Source",
        component_class=CurrentSource,
        domain="electrical", category="source",
        tags=("electrical", "source", "current"),
        icon_path="electrical/current_source.svg",
        description="Ideal current source: i = I",
        default_params={"I": 1.0},
        port_anchors=_ELEC_TWO_PORT,
    ))

    # === Translational ===
    from app.core.models.translational.fixed import TranslationalFixed
    from app.core.models.translational.spring import TranslationalSpring
    from app.core.models.translational.damper import TranslationalDamper
    from app.core.models.translational.mass import TranslationalMass
    from app.core.models.translational.source import (
        ForceSource, PositionSource,
    )

    # Two-port translational: flange_a at left (0,32), flange_b at right (64,32)
    _TRANS_TWO_PORT = {"flange_a": (0.0, 32.0), "flange_b": (64.0, 32.0)}

    registry.register(ComponentEntry(
        name="translational.spring", display_name="Translational Spring",
        component_class=TranslationalSpring,
        domain="translational", category="passive",
        tags=("translational", "spring", "elastic", "stiffness"),
        icon_path="translational/spring.svg",
        description="Linear spring: f = k * s_rel",
        default_params={"k": 1000.0},
        port_anchors=_TRANS_TWO_PORT,
    ))
    registry.register(ComponentEntry(
        name="translational.damper", display_name="Translational Damper",
        component_class=TranslationalDamper,
        domain="translational", category="passive",
        tags=("translational", "damper", "viscous", "dissipative"),
        icon_path="translational/damper.svg",
        description="Linear damper: f = d * v_rel",
        default_params={"d": 100.0},
        port_anchors=_TRANS_TWO_PORT,
    ))
    registry.register(ComponentEntry(
        name="translational.mass", display_name="Translational Mass",
        component_class=TranslationalMass,
        domain="translational", category="passive",
        tags=("translational", "mass", "inertial"),
        icon_path="translational/mass.svg",
        description="Sliding mass: m * a = sum(forces)",
        default_params={"m": 1.0},
        port_anchors=_TRANS_TWO_PORT,
    ))
    registry.register(ComponentEntry(
        name="translational.fixed", display_name="Translational Fixed",
        component_class=TranslationalFixed,
        domain="translational", category="reference",
        tags=("translational", "fixed", "ground", "reference"),
        icon_path="translational/fixed.svg",
        description="Fixed reference: s = 0",
        port_anchors={"flange": (64.0, 32.0)},
    ))
    registry.register(ComponentEntry(
        name="translational.force_source", display_name="Force Source",
        component_class=ForceSource,
        domain="translational", category="source",
        tags=("translational", "source", "force"),
        icon_path="translational/force_source.svg",
        description="Ideal force source: f = F",
        default_params={"F": 1.0},
        port_anchors=_TRANS_TWO_PORT,
    ))
    registry.register(ComponentEntry(
        name="translational.position_source", display_name="Position Source",
        component_class=PositionSource,
        domain="translational", category="source",
        tags=("translational", "source", "position"),
        icon_path="translational/position_source.svg",
        description="Ideal position source: s = s0",
        default_params={"s": 0.0},
        port_anchors=_TRANS_TWO_PORT,
    ))


# Auto-register on first import
_register_defaults()
