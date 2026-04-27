"""Unit tests for SVG placeholder renderer (T5.3).

Tests cover:
- render_svg: placeholder substitution, partial match, case sensitivity
- extract_placeholders: finding all {{key}} patterns
- _format_param: engineering-friendly number formatting
- load_and_render: file loading + substitution
- render_entry_svg: registry-integrated rendering
- All 11 SVG templates have valid placeholders
"""

from __future__ import annotations

import pytest
from pathlib import Path

from app.core.symbols.renderer import (
    render_svg,
    _xml_escape,
    load_and_render,
    render_entry_svg,
    extract_placeholders,
    _format_param,
)
from app.core.registry import registry, _SYMBOLS_DIR


# ── render_svg tests ──────────────────────────────────────────────────


class TestRenderSvg:
    def test_simple_substitution(self):
        template = '<text>{{name}}</text>'
        result = render_svg(template, {"name": "R1"})
        assert result == "<text>R1</text>"

    def test_multiple_placeholders(self):
        template = '<text>{{name}}</text><text>{{R}}</text>'
        result = render_svg(template, {"name": "R1", "R": "1000"})
        assert result == "<text>R1</text><text>1000</text>"

    def test_unmatched_placeholder_preserved(self):
        template = '<text>{{name}}</text><text>{{R}}</text>'
        result = render_svg(template, {"name": "R1"})
        assert result == "<text>R1</text><text>{{R}}</text>"

    def test_no_placeholders(self):
        template = '<line x1="0" y1="0"/>'
        result = render_svg(template, {"name": "R1"})
        assert result == template

    def test_empty_substitutions(self):
        template = '<text>{{name}}</text>'
        result = render_svg(template, {})
        assert result == template

    def test_duplicate_placeholder(self):
        template = '{{name}} and {{name}}'
        result = render_svg(template, {"name": "X"})
        assert result == "X and X"

    def test_case_sensitive(self):
        template = '{{Name}} {{name}}'
        result = render_svg(template, {"name": "R1"})
        assert result == "{{Name}} R1"

    def test_underscore_in_key(self):
        template = '{{my_param}}'
        result = render_svg(template, {"my_param": "42"})
        assert result == "42"

    def test_preserves_svg_structure(self):
        template = (
            '<svg viewBox="0 0 64 64">\n'
            '  <path d="M0,32 L64,32"/>\n'
            '  <text>{{name}}</text>\n'
            '</svg>'
        )
        result = render_svg(template, {"name": "L1"})
        assert '<path d="M0,32 L64,32"/>' in result
        assert "<text>L1</text>" in result


# ── extract_placeholders tests ────────────────────────────────────────


class TestExtractPlaceholders:
    def test_single(self):
        assert extract_placeholders("{{name}}") == ["name"]

    def test_multiple(self):
        result = extract_placeholders("{{name}} {{R}} {{name}}")
        assert result == ["R", "name"]  # sorted, deduplicated

    def test_none(self):
        assert extract_placeholders("<line/>") == []

    def test_nested_braces_ignored(self):
        # Only matches {{word}} pattern
        assert extract_placeholders("{notaplaceholder}") == []


# ── _format_param tests ──────────────────────────────────────────────


class TestFormatParam:
    def test_integer(self):
        assert _format_param(1000.0) == "1000"

    def test_small_float(self):
        result = _format_param(1e-6)
        assert "e" in result.lower()

    def test_large_float(self):
        result = _format_param(1e6)
        assert "e" in result.lower()

    def test_normal_float(self):
        assert _format_param(0.5) == "0.5"

    def test_one(self):
        assert _format_param(1.0) == "1"

    def test_zero(self):
        assert _format_param(0.0) == "0"


# ── load_and_render tests ────────────────────────────────────────────


class TestLoadAndRender:
    def test_load_resistor(self):
        path = _SYMBOLS_DIR / "electrical" / "resistor.svg"
        result = load_and_render(path, {"name": "R1", "R": "1000"})
        assert "R1" in result
        assert "1000" in result
        assert "<svg" in result

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_and_render("/nonexistent/file.svg", {})


# ── render_entry_svg tests ───────────────────────────────────────────


class TestRenderEntrySvg:
    def test_resistor(self):
        entry = registry.get("electrical.resistor")
        svg = render_entry_svg(entry, component_id="R1")
        assert svg is not None
        assert "R1" in svg
        assert "1000" in svg  # default R=1000

    def test_resistor_custom_param(self):
        entry = registry.get("electrical.resistor")
        svg = render_entry_svg(entry, component_id="R2", params={"R": 470.0})
        assert "R2" in svg
        assert "470" in svg

    def test_capacitor(self):
        entry = registry.get("electrical.capacitor")
        svg = render_entry_svg(entry, component_id="C1")
        assert svg is not None
        assert "C1" in svg

    def test_inductor(self):
        entry = registry.get("electrical.inductor")
        svg = render_entry_svg(entry, component_id="L1")
        assert svg is not None
        assert "L1" in svg

    def test_voltage_source(self):
        entry = registry.get("electrical.voltage_source")
        svg = render_entry_svg(entry, component_id="V1")
        assert svg is not None
        assert "V1" in svg

    def test_current_source(self):
        entry = registry.get("electrical.current_source")
        svg = render_entry_svg(entry, component_id="I1")
        assert svg is not None
        assert "I1" in svg

    def test_ground(self):
        entry = registry.get("electrical.ground")
        svg = render_entry_svg(entry, component_id="GND")
        assert svg is not None
        assert "GND" in svg

    def test_spring(self):
        entry = registry.get("translational.spring")
        svg = render_entry_svg(entry, component_id="k1")
        assert svg is not None
        assert "k1" in svg
        assert "1000" in svg  # default k=1000

    def test_damper(self):
        entry = registry.get("translational.damper")
        svg = render_entry_svg(entry, component_id="d1")
        assert svg is not None
        assert "d1" in svg

    def test_mass(self):
        entry = registry.get("translational.mass")
        svg = render_entry_svg(entry, component_id="m1")
        assert svg is not None
        assert "m1" in svg

    def test_fixed(self):
        entry = registry.get("translational.fixed")
        svg = render_entry_svg(entry, component_id="fix1")
        assert svg is not None
        assert "fix1" in svg

    def test_force_source(self):
        entry = registry.get("translational.force_source")
        svg = render_entry_svg(entry, component_id="F1")
        assert svg is not None
        assert "F1" in svg

    def test_fallback_to_entry_name(self):
        entry = registry.get("electrical.resistor")
        svg = render_entry_svg(entry)  # no component_id
        assert "electrical.resistor" in svg

    def test_no_icon_returns_none(self):
        from app.core.registry import ComponentEntry

        class Dummy:
            pass

        entry = ComponentEntry(
            name="NoIcon", component_class=Dummy,
            domain="test", category="test", icon_path=None,
        )
        assert render_entry_svg(entry) is None


# ── All SVG templates validation ─────────────────────────────────────


class TestAllSvgTemplates:
    """Verify every registered component's SVG has at least a {{name}} placeholder."""

    @pytest.fixture(params=[e.name for e in registry.all()])
    def entry(self, request):
        return registry.get(request.param)

    def test_svg_file_exists(self, entry):
        path = entry.icon_abs_path
        assert path is not None, f"{entry.name} has no icon_path"
        assert path.exists(), f"{entry.name} icon not found: {path}"

    def test_has_name_placeholder(self, entry):
        path = entry.icon_abs_path
        template = path.read_text(encoding="utf-8")
        placeholders = extract_placeholders(template)
        assert "name" in placeholders, (
            f"{entry.name} SVG missing {{{{name}}}} placeholder"
        )

    def test_has_param_placeholder_if_params(self, entry):
        """Components with default_params should have matching SVG placeholders."""
        if not entry.default_params:
            pytest.skip("No default params")
        path = entry.icon_abs_path
        template = path.read_text(encoding="utf-8")
        placeholders = extract_placeholders(template)
        for param_key in entry.default_params:
            assert param_key in placeholders, (
                f"{entry.name} SVG missing {{{{{param_key}}}}} placeholder "
                f"(has default_params['{param_key}'])"
            )

    def test_render_succeeds(self, entry):
        """render_entry_svg should not raise for any registered component."""
        svg = render_entry_svg(entry, component_id="test1")
        assert svg is not None
        assert "<svg" in svg


# ── XML escape tests ─────────────────────────────────────────────────


class TestXmlEscape:
    def test_ampersand(self):
        assert _xml_escape("R&D") == "R&amp;D"

    def test_lt_gt(self):
        assert _xml_escape("<test>") == "&lt;test&gt;"

    def test_quotes(self):
        assert _xml_escape('say "hello"') == "say &quot;hello&quot;"

    def test_single_quote(self):
        assert _xml_escape("it's") == "it&#x27;s"

    def test_clean_string_unchanged(self):
        assert _xml_escape("R1") == "R1"

    def test_render_escapes_by_default(self):
        template = '<text>{{name}}</text>'
        result = render_svg(template, {"name": 'R<"1">'})
        assert "&lt;" in result
        assert "&gt;" in result
        assert "&quot;" in result
        # Verify valid XML structure preserved
        assert "<text>R&lt;&quot;1&quot;&gt;</text>" == result

    def test_render_escape_off(self):
        template = '<text>{{name}}</text>'
        result = render_svg(template, {"name": "<b>bold</b>"}, escape=False)
        assert "<b>bold</b>" in result

    def test_render_entry_escapes_name(self):
        """render_entry_svg must XML-escape component_id."""
        entry = registry.get("electrical.resistor")
        svg = render_entry_svg(entry, component_id="R&1")
        assert "R&amp;1" in svg
        assert "R&1" not in svg  # raw string must not appear


# ── Port anchor tests ────────────────────────────────────────────────


class TestPortAnchors:
    """Verify port_anchors metadata on all registered components."""

    def test_all_entries_have_port_anchors(self):
        for e in registry.all():
            assert e.port_anchors, f"{e.name} missing port_anchors"

    def test_two_port_electrical_anchors(self):
        """Two-port electrical: port_a at (0,32), port_b at (64,32)."""
        for name in ["electrical.resistor", "electrical.capacitor", "electrical.inductor",
                      "electrical.voltage_source", "electrical.current_source"]:
            entry = registry.get(name)
            assert entry.port_anchors["port_a"] == (0.0, 32.0), name
            assert entry.port_anchors["port_b"] == (64.0, 32.0), name

    def test_ground_single_port(self):
        entry = registry.get("electrical.ground")
        assert len(entry.port_anchors) == 1
        assert entry.port_anchors["p"] == (32.0, 0.0)

    def test_two_port_translational_anchors(self):
        """Two-port translational: flange_a at (0,32), flange_b at (64,32)."""
        for name in ["translational.spring", "translational.damper",
                      "translational.mass", "translational.force_source", "translational.position_source"]:
            entry = registry.get(name)
            assert entry.port_anchors["flange_a"] == (0.0, 32.0), name
            assert entry.port_anchors["flange_b"] == (64.0, 32.0), name

    def test_fixed_single_port(self):
        entry = registry.get("translational.fixed")
        assert len(entry.port_anchors) == 1
        assert entry.port_anchors["flange"] == (64.0, 32.0)

    def test_anchors_within_viewbox(self):
        """All anchor coordinates must be within 0-64 range."""
        for e in registry.all():
            for port_name, (x, y) in e.port_anchors.items():
                assert 0 <= x <= 64, f"{e.name}.{port_name} x={x} out of range"
                assert 0 <= y <= 64, f"{e.name}.{port_name} y={y} out of range"

    def test_anchor_keys_match_component_ports(self):
        """CRITICAL INVARIANT: port_anchors keys must exactly match
        the component's actual port names. A mismatch means the canvas
        will draw connection points that don't correspond to real ports."""
        for e in registry.all():
            comp = e.create(f"inv_test_{e.name}")
            port_names = {p.name for p in comp.ports}
            anchor_keys = set(e.port_anchors.keys())
            assert anchor_keys == port_names, (
                f"{e.name}: port_anchors keys {sorted(anchor_keys)} "
                f"!= component port names {sorted(port_names)}"
            )

    def test_anchor_count_matches_port_count(self):
        """Each component port must have exactly one anchor coordinate."""
        for e in registry.all():
            comp = e.create(f"cnt_test_{e.name}")
            assert len(e.port_anchors) == len(comp.ports), (
                f"{e.name}: {len(e.port_anchors)} anchors "
                f"vs {len(comp.ports)} ports"
            )
