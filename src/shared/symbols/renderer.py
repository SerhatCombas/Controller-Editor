"""SVG template renderer — placeholder substitution (T5.3).

Implements MSL's ``Text(textString="%name")`` pattern in Python.

SVG template files contain ``{{name}}``, ``{{R}}``, ``{{C}}`` etc.
placeholders inside ``<text>`` elements.  At render time these are
replaced with the component's instance name and current parameter values.

Usage::

    from src.shared.symbols.renderer import render_svg, render_entry_svg

    # Direct template rendering
    svg = render_svg(template_str, {"name": "R1", "R": "1 kΩ"})

    # Registry-integrated rendering
    entry = registry.get("Resistor")
    svg = render_entry_svg(entry, component_id="R1", params={"R": 1000.0})
"""

from __future__ import annotations

import re
from html import escape as _html_escape
from pathlib import Path
from typing import Any

from src.shared.utils.registry import ComponentEntry

# Pattern: {{key}} — non-greedy, alphanumeric + underscore
_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


def _xml_escape(value: str) -> str:
    """Escape a string for safe embedding in SVG/XML.

    Handles: & → &amp;  < → &lt;  > → &gt;  " → &quot;  ' → &#x27;
    """
    return _html_escape(value, quote=True).replace("'", "&#x27;")


def render_svg(
    template: str,
    substitutions: dict[str, str],
    *,
    escape: bool = True,
) -> str:
    """Replace ``{{key}}`` placeholders in an SVG template string.

    Parameters
    ----------
    template:
        Raw SVG string containing ``{{key}}`` placeholders.
    substitutions:
        Mapping of placeholder key → display value.
        Keys are matched case-sensitively.
        Unmatched placeholders are left as-is.
    escape:
        If True (default), XML-escape substitution values to prevent
        injection or broken SVG from special characters like <, >, &.

    Returns
    -------
    SVG string with substitutions applied.
    """

    def _replace(match: re.Match) -> str:
        key = match.group(1)
        value = substitutions.get(key)
        if value is None:
            return match.group(0)
        return _xml_escape(value) if escape else value

    return _PLACEHOLDER_RE.sub(_replace, template)


def load_and_render(
    svg_path: Path | str,
    substitutions: dict[str, str],
) -> str:
    """Load an SVG template file and apply substitutions.

    Parameters
    ----------
    svg_path:
        Absolute or relative path to the SVG template file.
    substitutions:
        Mapping of placeholder key → display value.

    Returns
    -------
    Rendered SVG string.

    Raises
    ------
    FileNotFoundError:
        If the SVG file does not exist.
    """
    path = Path(svg_path)
    template = path.read_text(encoding="utf-8")
    return render_svg(template, substitutions)


def _format_param(value: float) -> str:
    """Format a numeric parameter for display.

    Uses engineering-friendly formatting:
    - Integers shown without decimal (e.g. 1000 → "1000")
    - Small floats shown in scientific notation (e.g. 1e-6 → "1e-06")
    - Others shown with minimal decimal places
    """
    if value == int(value) and abs(value) < 1e6:
        return str(int(value))
    if abs(value) < 0.01 or abs(value) >= 1e6:
        return f"{value:.2e}"
    return f"{value:g}"


def render_entry_svg(
    entry: ComponentEntry,
    component_id: str | None = None,
    params: dict[str, Any] | None = None,
) -> str | None:
    """Render an SVG for a registry entry with instance name and parameters.

    Builds a substitution dict from:
    - ``name``: component_id or entry.name
    - Each key in ``params`` (or entry.default_params): formatted value

    Parameters
    ----------
    entry:
        A ComponentEntry from the registry.
    component_id:
        Instance name (e.g. "R1"). Falls back to entry.name.
    params:
        Parameter values to display. Falls back to entry.default_params.

    Returns
    -------
    Rendered SVG string, or None if the entry has no icon_path.
    """
    icon_path = entry.icon_abs_path
    if icon_path is None or not icon_path.exists():
        return None

    subs: dict[str, str] = {"name": component_id or entry.name}

    effective_params = {**entry.default_params, **(params or {})}
    for key, value in effective_params.items():
        if isinstance(value, (int, float)):
            subs[key] = _format_param(value)
        else:
            subs[key] = str(value)

    return load_and_render(icon_path, subs)


def extract_placeholders(template: str) -> list[str]:
    """Extract all placeholder keys from an SVG template.

    Returns
    -------
    Sorted list of unique placeholder key names found in the template.
    """
    return sorted(set(_PLACEHOLDER_RE.findall(template)))
