"""CanvasSerializer — v2 JSON save/load for canvas layouts.

Produces a stable, versioned JSON format that uses:
  - ``type_key`` as primary component identity (not display_name)
  - ``registry_name`` for components migrated to the registry
  - Canvas connector names in connections (visual port names)
  - ``schema_version`` for forward compatibility

Backward compatibility
──────────────────────
The ``load()`` method auto-detects v1 (display_name-based, no schema_version)
vs v2 format and handles both transparently.  The ``save()`` method always
writes v2.

Roundtrip guarantee
───────────────────
For any canvas state *S*:
  ``load(save(S))`` produces a canvas state *S'* such that
  ``compile(S') == compile(S)`` — i.e. the SystemGraph topology is identical.

Port naming decision (v2 → v3 migration note)
──────────────────────────────────────────────
v2 stores **canvas connector names** ("positive", "negative", "R", "C", "ref")
in the ``connections[].from.port`` / ``connections[].to.port`` fields.  This is
the visual/UI-layer name, not the canonical core port name ("port_a", "port_b",
"p", "flange_a").

This was a deliberate choice for v2: the canvas UI still works entirely with
visual connector names, so storing them directly avoids an extra reverse-mapping
layer on load.  The compiler handles canvas→core resolution at compile time.

**v3 should consider** one of:
  (a) Storing canonical core port names only: ``"port": "port_a"``
  (b) Dual fields: ``"canvas_port": "positive", "core_port": "port_a"``

Option (b) is preferred — it preserves visual intent for the UI while also
giving the compiler a pre-resolved core port, making the save file more
self-documenting and robust against port_mapping table changes.

Registry ID naming (future note)
────────────────────────────────
Current format: ``domain.kind`` (e.g. ``electrical.resistor``,
``translational.spring``).  When the domain count grows, a three-level
scheme ``domain.subdomain.kind`` may be cleaner:
``mechanical.translational.mass``, ``mechanical.rotational.inertia``.
Current two-level IDs are stable and will not break — the three-level
scheme would be additive, not a rename.
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.ui.canvas.component_system import (
        CanvasVisualComponent,
        CanvasWireConnection,
    )

SCHEMA_VERSION = 2


# ---------------------------------------------------------------------------
# Save (canvas → JSON dict)
# ---------------------------------------------------------------------------

def save(
    components: list[CanvasVisualComponent],
    wires: list[CanvasWireConnection],
    *,
    viewport: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Serialize canvas state to a v2 JSON-safe dict.

    Args:
        components: All visual components on the canvas.
        wires:      All wire connections.
        viewport:   Optional viewport state (zoom, pan_x, pan_y).

    Returns:
        A JSON-serializable dict with schema_version=2.
    """
    comp_list: list[dict[str, Any]] = []
    for cv in components:
        entry: dict[str, Any] = {
            "id": cv.component_id,
            "type_key": cv.spec.type_key,
            "position": {
                "x": cv.position.x(),
                "y": cv.position.y(),
            },
            "size": list(cv.size),
            "orientation": cv.orientation.value,
        }

        # Registry metadata (only for migrated components)
        if cv.spec.registry_name is not None:
            entry["registry_name"] = cv.spec.registry_name

        # Instance name (user-assigned label)
        if cv.instance_name is not None:
            entry["instance_name"] = cv.instance_name

        # IO roles
        from app.ui.canvas.component_system import ComponentIoRole
        if cv.assigned_io_roles:
            entry["assigned_io_roles"] = [r.value for r in cv.assigned_io_roles]
        if cv.input_role_order is not None:
            entry["input_role_order"] = cv.input_role_order
        if cv.output_role_order is not None:
            entry["output_role_order"] = cv.output_role_order

        # Deletable flag (only save if non-default)
        if not cv.deletable:
            entry["deletable"] = False

        comp_list.append(entry)

    # Connections: resolve canvas port names → core port names
    conn_list: list[dict[str, Any]] = []
    for wire in wires:
        conn_list.append({
            "from": {
                "component": wire.source_component_id,
                "port": wire.source_connector_name,
            },
            "to": {
                "component": wire.target_component_id,
                "port": wire.target_connector_name,
            },
        })

    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "components": comp_list,
        "connections": conn_list,
    }

    if viewport is not None:
        result["viewport"] = viewport

    return result


# ---------------------------------------------------------------------------
# Load (JSON dict → canvas objects)
# ---------------------------------------------------------------------------

def load(
    data: dict[str, Any],
) -> tuple[list[CanvasVisualComponent], list[CanvasWireConnection]]:
    """Deserialize a JSON dict into canvas objects.

    Handles both v1 (display_name-based) and v2 (type_key-based) formats.

    Returns:
        (components, wires) tuple ready for canvas use.
    """
    version = data.get("schema_version", 1)

    if version == 1:
        return _load_v1(data)
    elif version == 2:
        return _load_v2(data)
    else:
        raise ValueError(f"Unknown schema_version: {version}")


def _load_v2(
    data: dict[str, Any],
) -> tuple[list[CanvasVisualComponent], list[CanvasWireConnection]]:
    """Load v2 format (type_key-based)."""
    from PySide6.QtCore import QPointF

    from app.ui.canvas.component_system import (
        COMPONENT_CATALOG,
        CanvasVisualComponent,
        CanvasWireConnection,
        ComponentIoRole,
        Orientation,
    )

    components: list[CanvasVisualComponent] = []
    for cd in data.get("components", []):
        type_key = cd["type_key"]
        spec = COMPONENT_CATALOG.get(type_key)
        if spec is None:
            continue  # Skip unknown component types gracefully

        roles_raw = cd.get("assigned_io_roles", [])
        assigned_roles = tuple(ComponentIoRole(v) for v in roles_raw)

        components.append(CanvasVisualComponent(
            spec=spec,
            component_id=cd["id"],
            instance_name=cd.get("instance_name"),
            position=QPointF(float(cd["position"]["x"]), float(cd["position"]["y"])),
            size=tuple(cd["size"]),
            deletable=cd.get("deletable", True),
            orientation=Orientation(cd.get("orientation", 0)),
            assigned_io_roles=assigned_roles,
            input_role_order=cd.get("input_role_order"),
            output_role_order=cd.get("output_role_order"),
        ))

    wires: list[CanvasWireConnection] = []
    for wd in data.get("connections", []):
        wires.append(CanvasWireConnection(
            source_component_id=wd["from"]["component"],
            source_connector_name=wd["from"]["port"],
            target_component_id=wd["to"]["component"],
            target_connector_name=wd["to"]["port"],
        ))

    return components, wires


def _load_v1(
    data: dict[str, Any],
) -> tuple[list[CanvasVisualComponent], list[CanvasWireConnection]]:
    """Load v1 format (display_name-based, legacy model_canvas.py format).

    Converts the old format to the same output objects as v2.
    """
    from PySide6.QtCore import QPointF

    from app.ui.canvas.component_system import (
        CanvasVisualComponent,
        CanvasWireConnection,
        ComponentIoRole,
        Orientation,
        component_spec_for_display_name,
    )

    components: list[CanvasVisualComponent] = []
    for cd in data.get("components", []):
        role_values = cd.get("assigned_io_roles")
        if isinstance(role_values, list):
            assigned_roles = tuple(ComponentIoRole(v) for v in role_values)
        else:
            role_value = cd.get("assigned_io_role")
            assigned_roles = () if role_value is None else (ComponentIoRole(role_value),)

        components.append(CanvasVisualComponent(
            spec=component_spec_for_display_name(str(cd["display_name"])),
            component_id=str(cd["component_id"]),
            instance_name=cd.get("instance_name"),
            position=QPointF(float(cd["position"][0]), float(cd["position"][1])),
            size=(float(cd["size"][0]), float(cd["size"][1])),
            deletable=bool(cd["deletable"]),
            orientation=Orientation(int(cd["orientation"])),
            assigned_io_roles=assigned_roles,
            input_role_order=cd.get("input_role_order"),
            output_role_order=cd.get("output_role_order"),
        ))

    wires: list[CanvasWireConnection] = []
    for wd in data.get("wires", []):
        wires.append(CanvasWireConnection(
            source_component_id=str(wd["source_component_id"]),
            source_connector_name=str(wd["source_connector_name"]),
            target_component_id=str(wd["target_component_id"]),
            target_connector_name=str(wd["target_connector_name"]),
        ))

    return components, wires


# ---------------------------------------------------------------------------
# Convenience: JSON string I/O
# ---------------------------------------------------------------------------

def save_json(
    components: list[CanvasVisualComponent],
    wires: list[CanvasWireConnection],
    *,
    viewport: dict[str, float] | None = None,
    indent: int = 2,
) -> str:
    """Serialize canvas state to a JSON string."""
    return json.dumps(save(components, wires, viewport=viewport), indent=indent)


def load_json(
    json_str: str,
) -> tuple[list[CanvasVisualComponent], list[CanvasWireConnection]]:
    """Deserialize a JSON string into canvas objects."""
    return load(json.loads(json_str))
