from __future__ import annotations

from pathlib import Path
import unittest

try:
    from PySide6.QtCore import QPointF, QRectF

    from app.ui.canvas.component_system import (
        CanvasVisualComponent,
        ComponentDomain,
        ComponentIoAxis,
        ComponentIoRole,
        ComponentRenderer,
        ComponentVisualCategory,
        Orientation,
        component_svg_asset,
        component_catalog,
        component_spec_for_display_name,
        resolve_component_svg,
    )

    UI_DEPS_AVAILABLE = True
except ModuleNotFoundError:
    UI_DEPS_AVAILABLE = False


@unittest.skipUnless(UI_DEPS_AVAILABLE, "Component system tests require PySide6")
class ComponentSystemTests(unittest.TestCase):
    def test_mass_is_first_gold_standard_mechanical_rigid_component(self):
        mass = component_spec_for_display_name("Mass")
        self.assertEqual(mass.type_key, "mass")
        self.assertEqual(mass.domain, ComponentDomain.MECHANICAL)
        self.assertEqual(mass.category, ComponentVisualCategory.RIGID)
        self.assertEqual(len(mass.connector_ports), 2)
        self.assertTrue(mass.simulation_hooks.supports_translation)
        self.assertFalse(mass.simulation_hooks.supports_deformation)
        self.assertTrue(mass.selection_name_visible)
        self.assertIsNotNone(mass.svg_symbol)
        self.assertEqual(mass.svg_symbol.asset_path, "app/SVG/Mass_Icon_new.svg")
        self.assertEqual(mass.connector_ports[0].name, "top")
        self.assertEqual(mass.connector_ports[1].name, "bottom")
        self.assertEqual(mass.allowed_io_roles, (ComponentIoRole.OUTPUT,))
        self.assertIsNotNone(mass.preferred_symbol_aspect_ratio)

    def test_component_io_role_capabilities_follow_semantic_contract(self):
        reference = component_spec_for_display_name("Mechanical Translational Reference")
        electrical_reference = component_spec_for_display_name("Electrical Reference")
        wheel = component_spec_for_display_name("Wheel")
        disturbance = component_spec_for_display_name("Mechanical Random Reference")
        spring = component_spec_for_display_name("Translational Spring")
        damper = component_spec_for_display_name("Translational Damper")
        dc_source = component_spec_for_display_name("DC Voltage Source")
        resistor = component_spec_for_display_name("Resistor")
        self.assertEqual(reference.allowed_io_roles, ())
        self.assertEqual(electrical_reference.allowed_io_roles, ())
        self.assertEqual(wheel.allowed_io_roles, (ComponentIoRole.INPUT, ComponentIoRole.OUTPUT))
        self.assertEqual(disturbance.allowed_io_roles, (ComponentIoRole.INPUT,))
        self.assertEqual(spring.allowed_io_roles, (ComponentIoRole.OUTPUT,))
        self.assertEqual(damper.allowed_io_roles, (ComponentIoRole.OUTPUT,))
        self.assertEqual(dc_source.allowed_io_roles, (ComponentIoRole.INPUT,))
        self.assertEqual(resistor.allowed_io_roles, ())

    def test_component_preferred_io_axis_semantics_are_exposed(self):
        mass = component_spec_for_display_name("Mass")
        wheel = component_spec_for_display_name("Wheel")
        disturbance = component_spec_for_display_name("Mechanical Random Reference")
        ac_source = component_spec_for_display_name("AC Voltage Source")
        resistor = component_spec_for_display_name("Resistor")
        self.assertEqual(mass.preferred_io_axis, ComponentIoAxis.VERTICAL)
        self.assertEqual(wheel.preferred_io_axis, ComponentIoAxis.VERTICAL)
        self.assertEqual(disturbance.preferred_io_axis, ComponentIoAxis.HORIZONTAL)
        self.assertEqual(ac_source.preferred_io_axis, ComponentIoAxis.HORIZONTAL)
        self.assertEqual(resistor.preferred_io_axis, ComponentIoAxis.HORIZONTAL)

    def test_app_svg_assets_are_mapped_by_component_specs(self):
        mapped_assets = {
            spec.svg_symbol.asset_path
            for spec in component_catalog().values()
            if spec.svg_symbol is not None and spec.svg_symbol.asset_path.startswith("app/SVG/")
        }
        asset_files = {
            f"app/SVG/{path.name}"
            for path in (Path(__file__).resolve().parents[1] / "app" / "SVG").glob("*.svg")
        }
        self.assertTrue(asset_files.issubset(mapped_assets))

    def test_missing_svg_assets_fall_back_safely(self):
        self.assertIsNone(resolve_component_svg("definitely_missing.svg"))
        self.assertIsNone(component_svg_asset("definitely_missing.svg"))

    def test_new_svg_rollout_specs_expose_semantic_defaults(self):
        force_source = component_spec_for_display_name("Ideal Force Source")
        force_sensor = component_spec_for_display_name("Ideal Force Sensor")
        switch = component_spec_for_display_name("Switch")
        voltage_sensor = component_spec_for_display_name("Voltage Sensor")
        self.assertEqual(force_source.domain, ComponentDomain.MECHANICAL)
        self.assertEqual(force_source.allowed_io_roles, (ComponentIoRole.INPUT,))
        self.assertEqual(force_sensor.allowed_io_roles, (ComponentIoRole.OUTPUT,))
        self.assertEqual(switch.domain, ComponentDomain.ELECTRICAL)
        self.assertEqual(len(switch.connector_ports), 2)
        self.assertEqual(voltage_sensor.allowed_io_roles, (ComponentIoRole.OUTPUT,))

    def test_svg_normalization_groups_are_assigned_to_component_families(self):
        mass = component_spec_for_display_name("Mass")
        spring = component_spec_for_display_name("Spring")
        damper = component_spec_for_display_name("Damper")
        resistor = component_spec_for_display_name("Resistor")
        dc_source = component_spec_for_display_name("DC Voltage Source")
        self.assertEqual(mass.svg_symbol.normalization_group, "mechanical_passive_vertical")
        self.assertEqual(spring.svg_symbol.normalization_group, "mechanical_passive_vertical")
        self.assertEqual(damper.svg_symbol.normalization_group, "mechanical_passive_vertical")
        self.assertEqual(resistor.svg_symbol.normalization_group, "electrical_passive")
        self.assertEqual(dc_source.svg_symbol.normalization_group, "electrical_source")

    def test_mechanical_passive_svg_components_share_consistent_fill_ratio(self):
        mass = component_spec_for_display_name("Mass")
        spring = component_spec_for_display_name("Spring")
        damper = component_spec_for_display_name("Damper")
        self.assertAlmostEqual(mass.svg_symbol.fill_ratio, spring.svg_symbol.fill_ratio, delta=0.001)
        self.assertAlmostEqual(spring.svg_symbol.fill_ratio, damper.svg_symbol.fill_ratio, delta=0.001)

    def test_spring_and_damper_use_svg_at_base_size_but_fallback_when_deformed(self):
        renderer = ComponentRenderer()
        spring = CanvasVisualComponent(
            spec=component_spec_for_display_name("Spring"),
            component_id="spring_1",
            position=QPointF(0.0, 0.0),
            size=component_spec_for_display_name("Spring").base_size,
        )
        damper = CanvasVisualComponent(
            spec=component_spec_for_display_name("Damper"),
            component_id="damper_1",
            position=QPointF(0.0, 0.0),
            size=component_spec_for_display_name("Damper").base_size,
        )
        self.assertTrue(renderer._should_draw_svg_symbol(spring, spring.base_rect()))
        self.assertTrue(renderer._should_draw_svg_symbol(damper, damper.base_rect()))
        self.assertFalse(renderer._should_draw_svg_symbol(spring, QRectF(0.0, 0.0, 90.0, 240.0)))
        self.assertFalse(renderer._should_draw_svg_symbol(damper, QRectF(0.0, 0.0, 90.0, 210.0)))

    def test_catalog_exposes_mechanical_and_electrical_components(self):
        spring = component_spec_for_display_name("Spring")
        resistor = component_spec_for_display_name("Resistor")
        self.assertEqual(spring.domain, ComponentDomain.MECHANICAL)
        self.assertEqual(resistor.domain, ComponentDomain.ELECTRICAL)
        self.assertEqual(spring.category, ComponentVisualCategory.DEFORMABLE)
        self.assertEqual(resistor.category, ComponentVisualCategory.RIGID)

    def test_spring_is_first_gold_standard_deformable_mechanical_component(self):
        spring = component_spec_for_display_name("Spring")
        self.assertEqual(spring.type_key, "translational_spring")
        self.assertEqual(spring.domain, ComponentDomain.MECHANICAL)
        self.assertEqual(spring.category, ComponentVisualCategory.DEFORMABLE)
        self.assertEqual(len(spring.connector_ports), 2)
        self.assertFalse(spring.simulation_hooks.supports_translation)
        self.assertTrue(spring.simulation_hooks.supports_deformation)
        self.assertTrue(spring.simulation_hooks.endpoint_deformation)
        self.assertEqual(spring.simulation_hooks.zigzag_segments, 8)
        self.assertIsNotNone(spring.simulation_hooks.rest_length)

    def test_spring_selected_vs_unselected_label_visibility(self):
        spec = component_spec_for_display_name("Spring")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="spring_1",
            position=QPointF(40.0, 50.0),
            size=(90.0, 200.0),
        )
        self.assertIsNone(component.selection_label(selected=False))
        self.assertEqual(component.selection_label(selected=True), "Translational Spring")

    def test_spring_connector_port_presence_and_terminal_labels(self):
        spec = component_spec_for_display_name("Spring")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="spring_1",
            position=QPointF(100.0, 120.0),
            size=(90.0, 200.0),
        )
        rect = component.base_rect()
        ports = component.transformed_connector_ports(rect)
        self.assertEqual(len(ports), 2)
        self.assertEqual(ports[0][0].terminal_label, "R")
        self.assertEqual(ports[1][0].terminal_label, "C")
        self.assertAlmostEqual(ports[0][1].x(), rect.center().x(), delta=0.01)
        self.assertAlmostEqual(ports[1][1].x(), rect.center().x(), delta=0.01)

    def test_spring_rotation_preserves_valid_connector_geometry(self):
        spec = component_spec_for_display_name("Spring")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="spring_1",
            position=QPointF(100.0, 120.0),
            size=(90.0, 200.0),
            orientation=Orientation.DEG_0,
        )
        rect = component.base_rect()
        ports_0 = component.connector_centers(rect)
        component.rotate_counterclockwise()
        ports_270 = component.connector_centers(rect)
        self.assertEqual(component.orientation, Orientation.DEG_270)
        self.assertNotEqual((ports_0[0].x(), ports_0[0].y()), (ports_270[0].x(), ports_270[0].y()))

    def test_spring_deformation_metadata_is_present_and_testable(self):
        spec = component_spec_for_display_name("Spring")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="spring_1",
            position=QPointF(60.0, 70.0),
            size=(90.0, 200.0),
        )
        metadata = component.deformation_metadata()
        self.assertFalse(metadata["supports_translation"])
        self.assertTrue(metadata["supports_deformation"])
        self.assertTrue(metadata["endpoint_deformation"])
        self.assertEqual(metadata["zigzag_segments"], 8)
        self.assertGreater(metadata["rest_length"], 0)
        self.assertEqual(metadata["deformation_scale"], 1.0)

    def test_spring_does_not_claim_rigid_translation_behavior(self):
        spec = component_spec_for_display_name("Spring")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="spring_1",
            position=QPointF(30.0, 30.0),
            size=(90.0, 200.0),
        )
        self.assertFalse(component.is_rigid())
        self.assertTrue(component.is_deformable())
        self.assertFalse(component.supports_translation())
        self.assertTrue(component.supports_deformation())

    def test_damper_is_second_gold_standard_deformable_mechanical_component(self):
        damper = component_spec_for_display_name("Damper")
        self.assertEqual(damper.type_key, "translational_damper")
        self.assertEqual(damper.domain, ComponentDomain.MECHANICAL)
        self.assertEqual(damper.category, ComponentVisualCategory.DEFORMABLE)
        self.assertEqual(len(damper.connector_ports), 2)
        self.assertFalse(damper.simulation_hooks.supports_translation)
        self.assertTrue(damper.simulation_hooks.supports_deformation)
        self.assertTrue(damper.simulation_hooks.endpoint_deformation)
        self.assertGreater(damper.simulation_hooks.piston_ratio, 0.0)
        self.assertGreater(damper.simulation_hooks.cylinder_ratio, 0.0)

    def test_damper_selected_vs_unselected_label_visibility(self):
        spec = component_spec_for_display_name("Damper")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="damper_1",
            position=QPointF(40.0, 50.0),
            size=(90.0, 180.0),
        )
        self.assertIsNone(component.selection_label(selected=False))
        self.assertEqual(component.selection_label(selected=True), "Translational Damper")

    def test_damper_connector_port_presence_and_terminal_labels(self):
        spec = component_spec_for_display_name("Damper")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="damper_1",
            position=QPointF(100.0, 120.0),
            size=(90.0, 180.0),
        )
        rect = component.base_rect()
        ports = component.transformed_connector_ports(rect)
        self.assertEqual(len(ports), 2)
        self.assertEqual(ports[0][0].terminal_label, "R")
        self.assertEqual(ports[1][0].terminal_label, "C")
        self.assertAlmostEqual(ports[0][1].x(), rect.center().x(), delta=0.01)
        self.assertAlmostEqual(ports[1][1].x(), rect.center().x(), delta=0.01)

    def test_damper_rotation_preserves_valid_connector_geometry(self):
        spec = component_spec_for_display_name("Damper")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="damper_1",
            position=QPointF(100.0, 120.0),
            size=(90.0, 180.0),
            orientation=Orientation.DEG_0,
        )
        rect = component.base_rect()
        ports_0 = component.connector_centers(rect)
        component.rotate_clockwise()
        ports_90 = component.connector_centers(rect)
        self.assertEqual(component.orientation, Orientation.DEG_90)
        self.assertNotEqual((ports_0[0].x(), ports_0[0].y()), (ports_90[0].x(), ports_90[0].y()))

    def test_damper_deformation_metadata_is_present_and_testable(self):
        spec = component_spec_for_display_name("Damper")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="damper_1",
            position=QPointF(60.0, 70.0),
            size=(90.0, 180.0),
        )
        metadata = component.deformation_metadata()
        self.assertFalse(metadata["supports_translation"])
        self.assertTrue(metadata["supports_deformation"])
        self.assertTrue(metadata["endpoint_deformation"])
        self.assertGreater(metadata["rest_length"], 0)
        self.assertEqual(metadata["deformation_scale"], 1.0)
        self.assertGreater(metadata["piston_ratio"], 0.0)
        self.assertGreater(metadata["cylinder_ratio"], 0.0)

    def test_damper_does_not_claim_rigid_translation_behavior(self):
        spec = component_spec_for_display_name("Damper")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="damper_1",
            position=QPointF(30.0, 30.0),
            size=(90.0, 180.0),
        )
        self.assertFalse(component.is_rigid())
        self.assertTrue(component.is_deformable())
        self.assertFalse(component.supports_translation())
        self.assertTrue(component.supports_deformation())

    def test_mechanical_reference_is_first_rigid_boundary_component(self):
        reference = component_spec_for_display_name("Mechanical Translational Reference")
        self.assertEqual(reference.type_key, "mechanical_reference")
        self.assertEqual(reference.domain, ComponentDomain.MECHANICAL)
        self.assertEqual(reference.category, ComponentVisualCategory.RIGID)
        self.assertEqual(len(reference.connector_ports), 1)
        self.assertFalse(reference.simulation_hooks.supports_translation)
        self.assertFalse(reference.simulation_hooks.supports_deformation)
        self.assertTrue(reference.simulation_hooks.fixed_reference)
        self.assertTrue(reference.selection_name_visible)

    def test_mechanical_reference_selected_vs_unselected_label_visibility(self):
        spec = component_spec_for_display_name("Mechanical Translational Reference")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="ground_1",
            position=QPointF(60.0, 360.0),
            size=(440.0, 36.0),
        )
        self.assertIsNone(component.selection_label(selected=False))
        self.assertEqual(component.selection_label(selected=True), "Mechanical Translational Reference")

    def test_mechanical_reference_has_single_top_connector_port(self):
        spec = component_spec_for_display_name("Mechanical Translational Reference")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="ground_1",
            position=QPointF(100.0, 420.0),
            size=(440.0, 36.0),
        )
        rect = component.base_rect()
        ports = component.transformed_connector_ports(rect)
        self.assertEqual(len(ports), 1)
        self.assertEqual(ports[0][0].name, "ref")
        self.assertAlmostEqual(ports[0][1].x(), rect.center().x(), delta=0.01)
        self.assertAlmostEqual(ports[0][1].y(), rect.top(), delta=0.01)

    def test_mechanical_reference_rotation_preserves_valid_connector_geometry(self):
        spec = component_spec_for_display_name("Mechanical Translational Reference")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="ground_1",
            position=QPointF(100.0, 420.0),
            size=(440.0, 36.0),
            orientation=Orientation.DEG_0,
        )
        rect = component.base_rect()
        ports_0 = component.connector_centers(rect)
        component.rotate_clockwise()
        ports_90 = component.connector_centers(rect)
        self.assertEqual(component.orientation, Orientation.DEG_90)
        self.assertNotEqual((ports_0[0].x(), ports_0[0].y()), (ports_90[0].x(), ports_90[0].y()))

    def test_mechanical_reference_metadata_is_fixed_and_non_deformable(self):
        spec = component_spec_for_display_name("Mechanical Translational Reference")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="ground_1",
            position=QPointF(80.0, 400.0),
            size=(440.0, 36.0),
        )
        metadata = component.deformation_metadata()
        self.assertFalse(metadata["supports_translation"])
        self.assertFalse(metadata["supports_deformation"])
        self.assertFalse(metadata["endpoint_deformation"])
        self.assertTrue(metadata["fixed_reference"])
        self.assertFalse(component.supports_translation())
        self.assertFalse(component.supports_deformation())
        self.assertTrue(component.is_fixed_reference())
        self.assertTrue(component.is_rigid())
        self.assertFalse(component.is_deformable())

    def test_translational_free_end_is_explicit_free_boundary_component(self):
        free_end = component_spec_for_display_name("Translational Free End")
        self.assertEqual(free_end.type_key, "translational_free_end")
        self.assertEqual(free_end.domain, ComponentDomain.MECHANICAL)
        self.assertEqual(free_end.category, ComponentVisualCategory.RIGID)
        self.assertEqual(len(free_end.connector_ports), 1)
        self.assertFalse(free_end.simulation_hooks.supports_translation)
        self.assertFalse(free_end.simulation_hooks.supports_deformation)
        self.assertFalse(free_end.simulation_hooks.fixed_reference)
        self.assertTrue(free_end.simulation_hooks.free_end)
        self.assertTrue(free_end.selection_name_visible)

    def test_translational_free_end_selected_vs_unselected_label_visibility(self):
        spec = component_spec_for_display_name("Translational Free End")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="free_end_1",
            position=QPointF(60.0, 360.0),
            size=(90.0, 60.0),
        )
        self.assertIsNone(component.selection_label(selected=False))
        self.assertEqual(component.selection_label(selected=True), "Translational Free End")

    def test_translational_free_end_has_single_top_connector_port(self):
        spec = component_spec_for_display_name("Translational Free End")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="free_end_1",
            position=QPointF(100.0, 420.0),
            size=(90.0, 60.0),
        )
        rect = component.base_rect()
        ports = component.transformed_connector_ports(rect)
        self.assertEqual(len(ports), 1)
        self.assertEqual(ports[0][0].name, "free")
        self.assertAlmostEqual(ports[0][1].x(), rect.center().x(), delta=0.01)
        self.assertAlmostEqual(ports[0][1].y(), rect.top(), delta=0.01)

    def test_translational_free_end_rotation_preserves_valid_connector_geometry(self):
        spec = component_spec_for_display_name("Translational Free End")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="free_end_1",
            position=QPointF(100.0, 420.0),
            size=(90.0, 60.0),
            orientation=Orientation.DEG_0,
        )
        rect = component.base_rect()
        ports_0 = component.connector_centers(rect)
        component.rotate_counterclockwise()
        ports_270 = component.connector_centers(rect)
        self.assertEqual(component.orientation, Orientation.DEG_270)
        self.assertNotEqual((ports_0[0].x(), ports_0[0].y()), (ports_270[0].x(), ports_270[0].y()))

    def test_translational_free_end_metadata_is_non_fixed_and_non_deformable(self):
        spec = component_spec_for_display_name("Translational Free End")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="free_end_1",
            position=QPointF(80.0, 400.0),
            size=(90.0, 60.0),
        )
        metadata = component.deformation_metadata()
        self.assertFalse(metadata["supports_translation"])
        self.assertFalse(metadata["supports_deformation"])
        self.assertFalse(metadata["endpoint_deformation"])
        self.assertFalse(metadata["fixed_reference"])
        self.assertTrue(metadata["free_end"])
        self.assertFalse(component.supports_translation())
        self.assertFalse(component.supports_deformation())
        self.assertFalse(component.is_fixed_reference())
        self.assertTrue(component.is_free_end())
        self.assertTrue(component.is_rigid())
        self.assertFalse(component.is_deformable())

    def test_mechanical_family_semantics_are_internally_consistent(self):
        mass = CanvasVisualComponent(
            spec=component_spec_for_display_name("Mass"),
            component_id="mass_1",
            position=QPointF(0.0, 0.0),
            size=(240.0, 90.0),
        )
        spring = CanvasVisualComponent(
            spec=component_spec_for_display_name("Spring"),
            component_id="spring_1",
            position=QPointF(0.0, 0.0),
            size=(90.0, 200.0),
        )
        damper = CanvasVisualComponent(
            spec=component_spec_for_display_name("Damper"),
            component_id="damper_1",
            position=QPointF(0.0, 0.0),
            size=(90.0, 180.0),
        )
        reference = CanvasVisualComponent(
            spec=component_spec_for_display_name("Mechanical Translational Reference"),
            component_id="ground_1",
            position=QPointF(0.0, 0.0),
            size=(440.0, 36.0),
        )
        free_end = CanvasVisualComponent(
            spec=component_spec_for_display_name("Translational Free End"),
            component_id="free_end_1",
            position=QPointF(0.0, 0.0),
            size=(90.0, 60.0),
        )
        self.assertEqual(mass.motion_profile(), "translating")
        self.assertEqual(spring.motion_profile(), "deformable")
        self.assertEqual(damper.motion_profile(), "deformable")
        self.assertEqual(reference.boundary_role(), "fixed_reference")
        self.assertEqual(reference.motion_profile(), "fixed")
        self.assertEqual(free_end.boundary_role(), "free_end")
        self.assertEqual(free_end.motion_profile(), "static")
        self.assertEqual(spring.boundary_role(), "internal")
        self.assertEqual(damper.boundary_role(), "internal")

    def test_electrical_reference_is_first_electrical_boundary_component(self):
        reference = component_spec_for_display_name("Electrical Reference")
        self.assertEqual(reference.type_key, "electrical_reference")
        self.assertEqual(reference.domain, ComponentDomain.ELECTRICAL)
        self.assertEqual(reference.category, ComponentVisualCategory.RIGID)
        self.assertEqual(len(reference.connector_ports), 1)
        self.assertFalse(reference.simulation_hooks.supports_translation)
        self.assertFalse(reference.simulation_hooks.supports_deformation)
        self.assertFalse(reference.simulation_hooks.fixed_reference)
        self.assertTrue(reference.simulation_hooks.electrical_reference)
        self.assertTrue(reference.selection_name_visible)

    def test_electrical_reference_selected_vs_unselected_label_visibility(self):
        spec = component_spec_for_display_name("Electrical Reference")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="eref_1",
            position=QPointF(60.0, 360.0),
            size=(72.0, 72.0),
        )
        self.assertIsNone(component.selection_label(selected=False))
        self.assertEqual(component.selection_label(selected=True), "Electrical Reference")

    def test_electrical_reference_has_single_top_connector_port(self):
        spec = component_spec_for_display_name("Electrical Reference")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="eref_1",
            position=QPointF(100.0, 420.0),
            size=(72.0, 72.0),
        )
        rect = component.base_rect()
        ports = component.transformed_connector_ports(rect)
        self.assertEqual(len(ports), 1)
        self.assertEqual(ports[0][0].name, "ref")
        self.assertAlmostEqual(ports[0][1].x(), rect.center().x(), delta=0.01)
        self.assertAlmostEqual(ports[0][1].y(), rect.top(), delta=0.01)

    def test_electrical_reference_rotation_preserves_valid_connector_geometry(self):
        spec = component_spec_for_display_name("Electrical Reference")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="eref_1",
            position=QPointF(100.0, 420.0),
            size=(72.0, 72.0),
            orientation=Orientation.DEG_0,
        )
        rect = component.base_rect()
        ports_0 = component.connector_centers(rect)
        component.rotate_clockwise()
        ports_90 = component.connector_centers(rect)
        self.assertEqual(component.orientation, Orientation.DEG_90)
        self.assertNotEqual((ports_0[0].x(), ports_0[0].y()), (ports_90[0].x(), ports_90[0].y()))

    def test_electrical_reference_metadata_is_static_and_distinct_from_mechanical_reference(self):
        electrical_spec = component_spec_for_display_name("Electrical Reference")
        mechanical_spec = component_spec_for_display_name("Mechanical Translational Reference")
        electrical = CanvasVisualComponent(
            spec=electrical_spec,
            component_id="eref_1",
            position=QPointF(80.0, 400.0),
            size=(72.0, 72.0),
        )
        mechanical = CanvasVisualComponent(
            spec=mechanical_spec,
            component_id="mref_1",
            position=QPointF(80.0, 500.0),
            size=(440.0, 36.0),
        )
        metadata = electrical.deformation_metadata()
        self.assertFalse(metadata["supports_translation"])
        self.assertFalse(metadata["supports_deformation"])
        self.assertFalse(metadata["fixed_reference"])
        self.assertFalse(metadata["free_end"])
        self.assertTrue(metadata["electrical_reference"])
        self.assertFalse(electrical.supports_translation())
        self.assertFalse(electrical.supports_deformation())
        self.assertFalse(electrical.is_fixed_reference())
        self.assertFalse(electrical.is_free_end())
        self.assertTrue(electrical.is_electrical_reference())
        self.assertEqual(electrical.boundary_role(), "electrical_reference")
        self.assertEqual(electrical.motion_profile(), "static")
        self.assertEqual(mechanical.boundary_role(), "fixed_reference")
        self.assertTrue(mechanical.is_fixed_reference())
        self.assertFalse(mechanical.is_electrical_reference())

    def test_resistor_is_first_rigid_two_port_electrical_passive_component(self):
        resistor = component_spec_for_display_name("Resistor")
        self.assertEqual(resistor.type_key, "resistor")
        self.assertEqual(resistor.domain, ComponentDomain.ELECTRICAL)
        self.assertEqual(resistor.category, ComponentVisualCategory.RIGID)
        self.assertEqual(len(resistor.connector_ports), 2)
        self.assertFalse(resistor.simulation_hooks.supports_translation)
        self.assertFalse(resistor.simulation_hooks.supports_deformation)
        self.assertFalse(resistor.simulation_hooks.fixed_reference)
        self.assertFalse(resistor.simulation_hooks.electrical_reference)
        self.assertFalse(resistor.simulation_hooks.directional)
        self.assertTrue(resistor.simulation_hooks.polarity_visible)

    def test_resistor_selected_vs_unselected_label_visibility(self):
        spec = component_spec_for_display_name("Resistor")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="resistor_1",
            position=QPointF(60.0, 360.0),
            size=(120.0, 56.0),
        )
        self.assertIsNone(component.selection_label(selected=False))
        self.assertEqual(component.selection_label(selected=True), "Resistor")

    def test_resistor_connector_port_presence_and_polarity_labels(self):
        spec = component_spec_for_display_name("Resistor")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="resistor_1",
            position=QPointF(100.0, 420.0),
            size=(120.0, 56.0),
        )
        rect = component.base_rect()
        ports = component.transformed_connector_ports(rect)
        self.assertEqual(len(ports), 2)
        self.assertEqual(ports[0][0].terminal_label, "+")
        self.assertEqual(ports[1][0].terminal_label, "-")
        visual_rect = component.visual_bounds(rect)
        self.assertAlmostEqual(ports[0][1].x(), visual_rect.left() + 8.0, delta=0.01)
        self.assertAlmostEqual(ports[1][1].x(), visual_rect.right() - 8.0, delta=0.01)
        self.assertAlmostEqual(ports[0][1].y(), rect.center().y(), delta=0.01)
        self.assertAlmostEqual(ports[1][1].y(), rect.center().y(), delta=0.01)

    def test_resistor_rotation_preserves_valid_connector_geometry(self):
        spec = component_spec_for_display_name("Resistor")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="resistor_1",
            position=QPointF(100.0, 420.0),
            size=(120.0, 56.0),
            orientation=Orientation.DEG_0,
        )
        rect = component.base_rect()
        ports_0 = component.connector_centers(rect)
        component.rotate_clockwise()
        ports_90 = component.connector_centers(rect)
        self.assertEqual(component.orientation, Orientation.DEG_90)
        self.assertNotEqual((ports_0[0].x(), ports_0[0].y()), (ports_90[0].x(), ports_90[0].y()))

    def test_resistor_metadata_is_rigid_static_and_distinct_from_spring(self):
        resistor_spec = component_spec_for_display_name("Resistor")
        spring_spec = component_spec_for_display_name("Spring")
        resistor = CanvasVisualComponent(
            spec=resistor_spec,
            component_id="resistor_1",
            position=QPointF(80.0, 400.0),
            size=(120.0, 56.0),
        )
        spring = CanvasVisualComponent(
            spec=spring_spec,
            component_id="spring_1",
            position=QPointF(80.0, 500.0),
            size=(90.0, 200.0),
        )
        metadata = resistor.deformation_metadata()
        self.assertFalse(metadata["supports_translation"])
        self.assertFalse(metadata["supports_deformation"])
        self.assertFalse(metadata["fixed_reference"])
        self.assertFalse(metadata["electrical_reference"])
        self.assertFalse(metadata["directional"])
        self.assertTrue(metadata["polarity_visible"])
        self.assertFalse(resistor.supports_translation())
        self.assertFalse(resistor.supports_deformation())
        self.assertFalse(resistor.is_directional())
        self.assertTrue(resistor.polarity_visible())
        self.assertEqual(resistor.boundary_role(), "internal")
        self.assertEqual(resistor.motion_profile(), "static")
        self.assertEqual(spring.motion_profile(), "deformable")
        self.assertTrue(spring.supports_deformation())

    def test_capacitor_is_second_rigid_two_port_electrical_passive_component(self):
        capacitor = component_spec_for_display_name("Capacitor")
        self.assertEqual(capacitor.type_key, "capacitor")
        self.assertEqual(capacitor.domain, ComponentDomain.ELECTRICAL)
        self.assertEqual(capacitor.category, ComponentVisualCategory.RIGID)
        self.assertEqual(len(capacitor.connector_ports), 2)
        self.assertFalse(capacitor.simulation_hooks.supports_translation)
        self.assertFalse(capacitor.simulation_hooks.supports_deformation)
        self.assertFalse(capacitor.simulation_hooks.fixed_reference)
        self.assertFalse(capacitor.simulation_hooks.electrical_reference)
        self.assertFalse(capacitor.simulation_hooks.directional)
        self.assertTrue(capacitor.simulation_hooks.polarity_visible)

    def test_capacitor_selected_vs_unselected_label_visibility(self):
        spec = component_spec_for_display_name("Capacitor")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="capacitor_1",
            position=QPointF(60.0, 360.0),
            size=(120.0, 56.0),
        )
        self.assertIsNone(component.selection_label(selected=False))
        self.assertEqual(component.selection_label(selected=True), "Capacitor")

    def test_capacitor_connector_port_presence_and_polarity_labels(self):
        spec = component_spec_for_display_name("Capacitor")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="capacitor_1",
            position=QPointF(100.0, 420.0),
            size=(120.0, 56.0),
        )
        rect = component.base_rect()
        ports = component.transformed_connector_ports(rect)
        self.assertEqual(len(ports), 2)
        self.assertEqual(ports[0][0].terminal_label, "+")
        self.assertEqual(ports[1][0].terminal_label, "-")
        self.assertAlmostEqual(ports[0][1].x(), rect.left(), delta=0.01)
        self.assertAlmostEqual(ports[1][1].x(), rect.right(), delta=0.01)
        self.assertAlmostEqual(ports[0][1].y(), rect.center().y(), delta=0.01)
        self.assertAlmostEqual(ports[1][1].y(), rect.center().y(), delta=0.01)

    def test_capacitor_rotation_preserves_valid_connector_geometry(self):
        spec = component_spec_for_display_name("Capacitor")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="capacitor_1",
            position=QPointF(100.0, 420.0),
            size=(120.0, 56.0),
            orientation=Orientation.DEG_0,
        )
        rect = component.base_rect()
        ports_0 = component.connector_centers(rect)
        component.rotate_counterclockwise()
        ports_270 = component.connector_centers(rect)
        self.assertEqual(component.orientation, Orientation.DEG_270)
        self.assertNotEqual((ports_0[0].x(), ports_0[0].y()), (ports_270[0].x(), ports_270[0].y()))

    def test_capacitor_metadata_is_rigid_static_and_distinct_from_resistor_and_spring(self):
        capacitor_spec = component_spec_for_display_name("Capacitor")
        resistor_spec = component_spec_for_display_name("Resistor")
        spring_spec = component_spec_for_display_name("Spring")
        capacitor = CanvasVisualComponent(
            spec=capacitor_spec,
            component_id="capacitor_1",
            position=QPointF(80.0, 400.0),
            size=(120.0, 56.0),
        )
        resistor = CanvasVisualComponent(
            spec=resistor_spec,
            component_id="resistor_1",
            position=QPointF(80.0, 500.0),
            size=(120.0, 56.0),
        )
        spring = CanvasVisualComponent(
            spec=spring_spec,
            component_id="spring_1",
            position=QPointF(80.0, 600.0),
            size=(90.0, 200.0),
        )
        metadata = capacitor.deformation_metadata()
        self.assertFalse(metadata["supports_translation"])
        self.assertFalse(metadata["supports_deformation"])
        self.assertFalse(metadata["fixed_reference"])
        self.assertFalse(metadata["electrical_reference"])
        self.assertFalse(metadata["directional"])
        self.assertTrue(metadata["polarity_visible"])
        self.assertFalse(capacitor.supports_translation())
        self.assertFalse(capacitor.supports_deformation())
        self.assertFalse(capacitor.is_directional())
        self.assertTrue(capacitor.polarity_visible())
        self.assertEqual(capacitor.boundary_role(), "internal")
        self.assertEqual(capacitor.motion_profile(), "static")
        self.assertEqual(resistor.boundary_role(), "internal")
        self.assertEqual(resistor.motion_profile(), "static")
        self.assertEqual(spring.motion_profile(), "deformable")
        self.assertTrue(spring.supports_deformation())

    def test_inductor_is_third_rigid_two_port_electrical_passive_component(self):
        inductor = component_spec_for_display_name("Inductor")
        self.assertEqual(inductor.type_key, "inductor")
        self.assertEqual(inductor.domain, ComponentDomain.ELECTRICAL)
        self.assertEqual(inductor.category, ComponentVisualCategory.RIGID)
        self.assertEqual(len(inductor.connector_ports), 2)
        self.assertFalse(inductor.simulation_hooks.supports_translation)
        self.assertFalse(inductor.simulation_hooks.supports_deformation)
        self.assertFalse(inductor.simulation_hooks.fixed_reference)
        self.assertFalse(inductor.simulation_hooks.electrical_reference)
        self.assertFalse(inductor.simulation_hooks.directional)
        self.assertTrue(inductor.simulation_hooks.polarity_visible)

    def test_inductor_selected_vs_unselected_label_visibility(self):
        spec = component_spec_for_display_name("Inductor")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="inductor_1",
            position=QPointF(60.0, 360.0),
            size=(120.0, 56.0),
        )
        self.assertIsNone(component.selection_label(selected=False))
        self.assertEqual(component.selection_label(selected=True), "Inductor")

    def test_inductor_connector_port_presence_and_polarity_labels(self):
        spec = component_spec_for_display_name("Inductor")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="inductor_1",
            position=QPointF(100.0, 420.0),
            size=(120.0, 56.0),
        )
        rect = component.base_rect()
        ports = component.transformed_connector_ports(rect)
        self.assertEqual(len(ports), 2)
        self.assertEqual(ports[0][0].terminal_label, "+")
        self.assertEqual(ports[1][0].terminal_label, "-")
        self.assertAlmostEqual(ports[0][1].x(), rect.left(), delta=0.01)
        self.assertAlmostEqual(ports[1][1].x(), rect.right(), delta=0.01)
        self.assertAlmostEqual(ports[0][1].y(), rect.center().y(), delta=0.01)
        self.assertAlmostEqual(ports[1][1].y(), rect.center().y(), delta=0.01)

    def test_inductor_rotation_preserves_valid_connector_geometry(self):
        spec = component_spec_for_display_name("Inductor")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="inductor_1",
            position=QPointF(100.0, 420.0),
            size=(120.0, 56.0),
            orientation=Orientation.DEG_0,
        )
        rect = component.base_rect()
        ports_0 = component.connector_centers(rect)
        component.rotate_clockwise()
        ports_90 = component.connector_centers(rect)
        self.assertEqual(component.orientation, Orientation.DEG_90)
        self.assertNotEqual((ports_0[0].x(), ports_0[0].y()), (ports_90[0].x(), ports_90[0].y()))

    def test_inductor_metadata_is_rigid_static_and_distinct_from_resistor_capacitor_and_spring(self):
        inductor_spec = component_spec_for_display_name("Inductor")
        resistor_spec = component_spec_for_display_name("Resistor")
        capacitor_spec = component_spec_for_display_name("Capacitor")
        spring_spec = component_spec_for_display_name("Spring")
        inductor = CanvasVisualComponent(
            spec=inductor_spec,
            component_id="inductor_1",
            position=QPointF(80.0, 400.0),
            size=(120.0, 56.0),
        )
        resistor = CanvasVisualComponent(
            spec=resistor_spec,
            component_id="resistor_1",
            position=QPointF(80.0, 500.0),
            size=(120.0, 56.0),
        )
        capacitor = CanvasVisualComponent(
            spec=capacitor_spec,
            component_id="capacitor_1",
            position=QPointF(80.0, 600.0),
            size=(120.0, 56.0),
        )
        spring = CanvasVisualComponent(
            spec=spring_spec,
            component_id="spring_1",
            position=QPointF(80.0, 700.0),
            size=(90.0, 200.0),
        )
        metadata = inductor.deformation_metadata()
        self.assertFalse(metadata["supports_translation"])
        self.assertFalse(metadata["supports_deformation"])
        self.assertFalse(metadata["fixed_reference"])
        self.assertFalse(metadata["electrical_reference"])
        self.assertFalse(metadata["directional"])
        self.assertTrue(metadata["polarity_visible"])
        self.assertFalse(inductor.supports_translation())
        self.assertFalse(inductor.supports_deformation())
        self.assertFalse(inductor.is_directional())
        self.assertTrue(inductor.polarity_visible())
        self.assertEqual(inductor.boundary_role(), "internal")
        self.assertEqual(inductor.motion_profile(), "static")
        self.assertEqual(resistor.motion_profile(), "static")
        self.assertEqual(capacitor.motion_profile(), "static")
        self.assertEqual(spring.motion_profile(), "deformable")
        self.assertTrue(spring.supports_deformation())

    def test_diode_is_first_directional_rigid_two_port_electrical_component(self):
        diode = component_spec_for_display_name("Diode")
        self.assertEqual(diode.type_key, "diode")
        self.assertEqual(diode.domain, ComponentDomain.ELECTRICAL)
        self.assertEqual(diode.category, ComponentVisualCategory.RIGID)
        self.assertEqual(len(diode.connector_ports), 2)
        self.assertFalse(diode.simulation_hooks.supports_translation)
        self.assertFalse(diode.simulation_hooks.supports_deformation)
        self.assertFalse(diode.simulation_hooks.fixed_reference)
        self.assertFalse(diode.simulation_hooks.electrical_reference)
        self.assertTrue(diode.simulation_hooks.directional)
        self.assertTrue(diode.simulation_hooks.polarity_visible)

    def test_diode_selected_vs_unselected_label_visibility(self):
        spec = component_spec_for_display_name("Diode")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="diode_1",
            position=QPointF(60.0, 360.0),
            size=(120.0, 56.0),
        )
        self.assertIsNone(component.selection_label(selected=False))
        self.assertEqual(component.selection_label(selected=True), "Diode")

    def test_diode_connector_port_presence_and_polarity_labels(self):
        spec = component_spec_for_display_name("Diode")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="diode_1",
            position=QPointF(100.0, 420.0),
            size=(120.0, 56.0),
        )
        rect = component.base_rect()
        ports = component.transformed_connector_ports(rect)
        self.assertEqual(len(ports), 2)
        self.assertEqual(ports[0][0].terminal_label, "+")
        self.assertEqual(ports[1][0].terminal_label, "-")
        self.assertAlmostEqual(ports[0][1].x(), rect.left(), delta=0.01)
        self.assertAlmostEqual(ports[1][1].x(), rect.right(), delta=0.01)
        self.assertAlmostEqual(ports[0][1].y(), rect.center().y(), delta=0.01)
        self.assertAlmostEqual(ports[1][1].y(), rect.center().y(), delta=0.01)

    def test_diode_rotation_preserves_valid_connector_geometry(self):
        spec = component_spec_for_display_name("Diode")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="diode_1",
            position=QPointF(100.0, 420.0),
            size=(120.0, 56.0),
            orientation=Orientation.DEG_0,
        )
        rect = component.base_rect()
        ports_0 = component.connector_centers(rect)
        component.rotate_counterclockwise()
        ports_270 = component.connector_centers(rect)
        self.assertEqual(component.orientation, Orientation.DEG_270)
        self.assertNotEqual((ports_0[0].x(), ports_0[0].y()), (ports_270[0].x(), ports_270[0].y()))

    def test_diode_metadata_is_directional_and_distinct_from_passive_family_and_spring(self):
        diode_spec = component_spec_for_display_name("Diode")
        resistor_spec = component_spec_for_display_name("Resistor")
        capacitor_spec = component_spec_for_display_name("Capacitor")
        inductor_spec = component_spec_for_display_name("Inductor")
        spring_spec = component_spec_for_display_name("Spring")
        diode = CanvasVisualComponent(
            spec=diode_spec,
            component_id="diode_1",
            position=QPointF(80.0, 400.0),
            size=(120.0, 56.0),
        )
        resistor = CanvasVisualComponent(
            spec=resistor_spec,
            component_id="resistor_1",
            position=QPointF(80.0, 500.0),
            size=(120.0, 56.0),
        )
        capacitor = CanvasVisualComponent(
            spec=capacitor_spec,
            component_id="capacitor_1",
            position=QPointF(80.0, 600.0),
            size=(120.0, 56.0),
        )
        inductor = CanvasVisualComponent(
            spec=inductor_spec,
            component_id="inductor_1",
            position=QPointF(80.0, 700.0),
            size=(120.0, 56.0),
        )
        spring = CanvasVisualComponent(
            spec=spring_spec,
            component_id="spring_1",
            position=QPointF(80.0, 800.0),
            size=(90.0, 200.0),
        )
        metadata = diode.deformation_metadata()
        self.assertFalse(metadata["supports_translation"])
        self.assertFalse(metadata["supports_deformation"])
        self.assertFalse(metadata["fixed_reference"])
        self.assertFalse(metadata["electrical_reference"])
        self.assertTrue(metadata["directional"])
        self.assertTrue(metadata["polarity_visible"])
        self.assertFalse(diode.supports_translation())
        self.assertFalse(diode.supports_deformation())
        self.assertTrue(diode.is_directional())
        self.assertTrue(diode.polarity_visible())
        self.assertEqual(diode.boundary_role(), "internal")
        self.assertEqual(diode.motion_profile(), "static")
        self.assertFalse(resistor.is_directional())
        self.assertFalse(capacitor.is_directional())
        self.assertFalse(inductor.is_directional())
        self.assertEqual(spring.motion_profile(), "deformable")
        self.assertTrue(spring.supports_deformation())

    def test_dc_voltage_source_is_first_rigid_directional_source_component(self):
        source = component_spec_for_display_name("DC Voltage Source")
        self.assertEqual(source.type_key, "dc_voltage_source")
        self.assertEqual(source.domain, ComponentDomain.ELECTRICAL)
        self.assertEqual(source.category, ComponentVisualCategory.RIGID)
        self.assertEqual(len(source.connector_ports), 2)
        self.assertFalse(source.simulation_hooks.supports_translation)
        self.assertFalse(source.simulation_hooks.supports_deformation)
        self.assertFalse(source.simulation_hooks.fixed_reference)
        self.assertFalse(source.simulation_hooks.electrical_reference)
        self.assertTrue(source.simulation_hooks.directional)
        self.assertTrue(source.simulation_hooks.polarity_visible)
        self.assertTrue(source.simulation_hooks.source_component)

    def test_dc_voltage_source_selected_vs_unselected_label_visibility(self):
        spec = component_spec_for_display_name("DC Voltage Source")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="dc_source_1",
            position=QPointF(60.0, 360.0),
            size=(120.0, 72.0),
        )
        self.assertIsNone(component.selection_label(selected=False))
        self.assertEqual(component.selection_label(selected=True), "DC Voltage Source")

    def test_dc_voltage_source_connector_port_presence_and_polarity_labels(self):
        spec = component_spec_for_display_name("DC Voltage Source")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="dc_source_1",
            position=QPointF(100.0, 420.0),
            size=(120.0, 72.0),
        )
        rect = component.base_rect()
        ports = component.transformed_connector_ports(rect)
        self.assertEqual(len(ports), 2)
        self.assertEqual(ports[0][0].terminal_label, "+")
        self.assertEqual(ports[1][0].terminal_label, "-")
        self.assertAlmostEqual(ports[0][1].x(), rect.left(), delta=0.01)
        self.assertAlmostEqual(ports[1][1].x(), rect.right(), delta=0.01)
        self.assertAlmostEqual(ports[0][1].y(), rect.center().y(), delta=0.01)
        self.assertAlmostEqual(ports[1][1].y(), rect.center().y(), delta=0.01)

    def test_dc_voltage_source_rotation_preserves_valid_connector_geometry(self):
        spec = component_spec_for_display_name("DC Voltage Source")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="dc_source_1",
            position=QPointF(100.0, 420.0),
            size=(120.0, 72.0),
            orientation=Orientation.DEG_0,
        )
        rect = component.base_rect()
        ports_0 = component.connector_centers(rect)
        component.rotate_clockwise()
        ports_90 = component.connector_centers(rect)
        self.assertEqual(component.orientation, Orientation.DEG_90)
        self.assertNotEqual((ports_0[0].x(), ports_0[0].y()), (ports_90[0].x(), ports_90[0].y()))

    def test_dc_voltage_source_metadata_is_directional_source_and_distinct_from_diode_and_passives(self):
        source_spec = component_spec_for_display_name("DC Voltage Source")
        diode_spec = component_spec_for_display_name("Diode")
        resistor_spec = component_spec_for_display_name("Resistor")
        source = CanvasVisualComponent(
            spec=source_spec,
            component_id="dc_source_1",
            position=QPointF(80.0, 400.0),
            size=(120.0, 72.0),
        )
        diode = CanvasVisualComponent(
            spec=diode_spec,
            component_id="diode_1",
            position=QPointF(80.0, 500.0),
            size=(120.0, 56.0),
        )
        resistor = CanvasVisualComponent(
            spec=resistor_spec,
            component_id="resistor_1",
            position=QPointF(80.0, 600.0),
            size=(120.0, 56.0),
        )
        metadata = source.deformation_metadata()
        self.assertFalse(metadata["supports_translation"])
        self.assertFalse(metadata["supports_deformation"])
        self.assertFalse(metadata["fixed_reference"])
        self.assertFalse(metadata["electrical_reference"])
        self.assertTrue(metadata["directional"])
        self.assertTrue(metadata["polarity_visible"])
        self.assertTrue(metadata["source_component"])
        self.assertFalse(source.supports_translation())
        self.assertFalse(source.supports_deformation())
        self.assertTrue(source.is_directional())
        self.assertTrue(source.polarity_visible())
        self.assertTrue(source.is_source_component())
        self.assertEqual(source.boundary_role(), "internal")
        self.assertEqual(source.motion_profile(), "static")
        self.assertTrue(diode.is_directional())
        self.assertFalse(diode.is_source_component())
        self.assertFalse(resistor.is_directional())
        self.assertFalse(resistor.is_source_component())

    def test_ac_voltage_source_is_second_rigid_directional_source_component(self):
        source = component_spec_for_display_name("AC Voltage Source")
        self.assertEqual(source.type_key, "ac_voltage_source")
        self.assertEqual(source.domain, ComponentDomain.ELECTRICAL)
        self.assertEqual(source.category, ComponentVisualCategory.RIGID)
        self.assertEqual(len(source.connector_ports), 2)
        self.assertFalse(source.simulation_hooks.supports_translation)
        self.assertFalse(source.simulation_hooks.supports_deformation)
        self.assertFalse(source.simulation_hooks.fixed_reference)
        self.assertFalse(source.simulation_hooks.electrical_reference)
        self.assertTrue(source.simulation_hooks.directional)
        self.assertTrue(source.simulation_hooks.polarity_visible)
        self.assertTrue(source.simulation_hooks.source_component)
        self.assertEqual(source.simulation_hooks.source_type, "ac")

    def test_ac_voltage_source_selected_vs_unselected_label_visibility(self):
        spec = component_spec_for_display_name("AC Voltage Source")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="ac_source_1",
            position=QPointF(60.0, 360.0),
            size=(120.0, 72.0),
        )
        self.assertIsNone(component.selection_label(selected=False))
        self.assertEqual(component.selection_label(selected=True), "AC Voltage Source")

    def test_ac_voltage_source_connector_port_presence_and_polarity_labels(self):
        spec = component_spec_for_display_name("AC Voltage Source")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="ac_source_1",
            position=QPointF(100.0, 420.0),
            size=(120.0, 72.0),
        )
        rect = component.base_rect()
        ports = component.transformed_connector_ports(rect)
        self.assertEqual(len(ports), 2)
        self.assertEqual(ports[0][0].terminal_label, "+")
        self.assertEqual(ports[1][0].terminal_label, "-")
        self.assertAlmostEqual(ports[0][1].x(), rect.left(), delta=0.01)
        self.assertAlmostEqual(ports[1][1].x(), rect.right(), delta=0.01)
        self.assertAlmostEqual(ports[0][1].y(), rect.center().y(), delta=0.01)
        self.assertAlmostEqual(ports[1][1].y(), rect.center().y(), delta=0.01)

    def test_ac_voltage_source_rotation_preserves_valid_connector_geometry(self):
        spec = component_spec_for_display_name("AC Voltage Source")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="ac_source_1",
            position=QPointF(100.0, 420.0),
            size=(120.0, 72.0),
            orientation=Orientation.DEG_0,
        )
        rect = component.base_rect()
        ports_0 = component.connector_centers(rect)
        component.rotate_counterclockwise()
        ports_270 = component.connector_centers(rect)
        self.assertEqual(component.orientation, Orientation.DEG_270)
        self.assertNotEqual((ports_0[0].x(), ports_0[0].y()), (ports_270[0].x(), ports_270[0].y()))

    def test_ac_voltage_source_metadata_is_directional_source_and_distinct_from_dc_source_diode_and_passives(self):
        ac_spec = component_spec_for_display_name("AC Voltage Source")
        dc_spec = component_spec_for_display_name("DC Voltage Source")
        diode_spec = component_spec_for_display_name("Diode")
        resistor_spec = component_spec_for_display_name("Resistor")
        source = CanvasVisualComponent(
            spec=ac_spec,
            component_id="ac_source_1",
            position=QPointF(80.0, 400.0),
            size=(120.0, 72.0),
        )
        dc_source = CanvasVisualComponent(
            spec=dc_spec,
            component_id="dc_source_1",
            position=QPointF(80.0, 500.0),
            size=(120.0, 72.0),
        )
        diode = CanvasVisualComponent(
            spec=diode_spec,
            component_id="diode_1",
            position=QPointF(80.0, 600.0),
            size=(120.0, 56.0),
        )
        resistor = CanvasVisualComponent(
            spec=resistor_spec,
            component_id="resistor_1",
            position=QPointF(80.0, 700.0),
            size=(120.0, 56.0),
        )
        metadata = source.deformation_metadata()
        self.assertFalse(metadata["supports_translation"])
        self.assertFalse(metadata["supports_deformation"])
        self.assertFalse(metadata["fixed_reference"])
        self.assertFalse(metadata["electrical_reference"])
        self.assertTrue(metadata["directional"])
        self.assertTrue(metadata["polarity_visible"])
        self.assertTrue(metadata["source_component"])
        self.assertEqual(metadata["source_type"], "ac")
        self.assertTrue(source.is_directional())
        self.assertTrue(source.is_source_component())
        self.assertEqual(source.source_type(), "ac")
        self.assertEqual(source.boundary_role(), "internal")
        self.assertEqual(source.motion_profile(), "static")
        self.assertEqual(dc_source.source_type(), "dc")
        self.assertTrue(diode.is_directional())
        self.assertFalse(diode.is_source_component())
        self.assertFalse(resistor.is_source_component())

    def test_mass_selected_vs_unselected_label_visibility(self):
        spec = component_spec_for_display_name("Mass")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="mass_1",
            position=QPointF(40.0, 50.0),
            size=(240.0, 90.0),
        )
        self.assertIsNone(component.selection_label(selected=False))
        self.assertEqual(component.selection_label(selected=True), "Mass")
        self.assertTrue(component.has_svg_symbol())

    def test_mass_connector_port_presence_and_placement(self):
        spec = component_spec_for_display_name("Mass")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="mass_1",
            position=QPointF(100.0, 120.0),
            size=(240.0, 90.0),
        )
        rect = component.base_rect()
        ports = component.connector_centers(rect)
        self.assertEqual(len(ports), 2)
        self.assertAlmostEqual(ports[0].x(), rect.center().x(), delta=0.01)
        self.assertAlmostEqual(ports[1].x(), rect.center().x(), delta=0.01)
        self.assertLess(ports[0].y(), rect.top())
        self.assertGreater(ports[1].y(), rect.bottom())
        visual_rect = component.visual_bounds(rect)
        self.assertAlmostEqual(ports[0].y(), visual_rect.top() - 6.0, delta=0.01)
        self.assertAlmostEqual(ports[1].y(), visual_rect.bottom() + 6.0, delta=0.01)

    def test_mass_rotation_updates_connector_geometry(self):
        spec = component_spec_for_display_name("Mass")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="mass_1",
            position=QPointF(100.0, 120.0),
            size=(240.0, 90.0),
            orientation=Orientation.DEG_0,
        )
        rect = component.base_rect()
        ports_0 = component.connector_centers(rect)
        component.rotate_clockwise()
        ports_90 = component.connector_centers(rect)
        self.assertEqual(component.orientation, Orientation.DEG_90)
        self.assertNotEqual((ports_0[0].x(), ports_0[0].y()), (ports_90[0].x(), ports_90[0].y()))

    def test_mass_connector_hit_regions_support_wire_start_and_snap_across_rotations(self):
        spec = component_spec_for_display_name("Mass")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="mass_1",
            position=QPointF(100.0, 120.0),
            size=(240.0, 90.0),
            orientation=Orientation.DEG_0,
        )
        rect = component.base_rect()
        hit_rects_0 = component.connector_hit_rects(rect)
        self.assertEqual(component.connector_hit_test(rect, hit_rects_0[0][1].center()).name, "top")
        self.assertEqual(component.connector_hit_test(rect, hit_rects_0[1][1].center()).name, "bottom")

        component.rotate_clockwise()
        rect = component.base_rect()
        hit_rects_90 = component.connector_hit_rects(rect)
        self.assertEqual(component.connector_hit_test(rect, hit_rects_90[0][1].center()).name, "top")

        component.rotate_clockwise()
        rect = component.base_rect()
        hit_rects_180 = component.connector_hit_rects(rect)
        self.assertEqual(component.connector_hit_test(rect, hit_rects_180[0][1].center()).name, "top")

        component.rotate_clockwise()
        rect = component.base_rect()
        hit_rects_270 = component.connector_hit_rects(rect)
        self.assertEqual(component.connector_hit_test(rect, hit_rects_270[1][1].center()).name, "bottom")

    def test_mass_connector_debug_geometry_exposes_top_bottom_ports(self):
        spec = component_spec_for_display_name("Mass")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="mass_1",
            position=QPointF(100.0, 120.0),
            size=(240.0, 90.0),
        )
        debug_ports = component.connector_debug_geometry(component.base_rect())
        self.assertEqual([item["name"] for item in debug_ports], ["top", "bottom"])
        self.assertAlmostEqual(debug_ports[0]["center"].x(), component.base_rect().center().x(), delta=0.01)
        visual_rect = component.visual_bounds(component.base_rect())
        self.assertAlmostEqual(debug_ports[1]["center"].y(), visual_rect.bottom() + 6.0, delta=0.01)

    def test_mass_simulation_visual_hooks_remain_translation_only(self):
        spec = component_spec_for_display_name("Mass")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="mass_1",
            position=QPointF(30.0, 30.0),
            size=(240.0, 90.0),
        )
        self.assertTrue(component.is_rigid())
        self.assertFalse(component.is_deformable())
        self.assertTrue(component.supports_translation())
        self.assertFalse(component.supports_deformation())

    def test_mass_symbol_render_rect_preserves_preferred_aspect_ratio(self):
        spec = component_spec_for_display_name("Mass")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="mass_1",
            position=QPointF(30.0, 30.0),
            size=(360.0, 140.0),
        )
        renderer = ComponentRenderer()
        rect = component.base_rect()
        symbol_rect = renderer.symbol_render_rect(component, rect)
        self.assertAlmostEqual(symbol_rect.center().x(), rect.center().x(), delta=0.01)
        self.assertAlmostEqual(symbol_rect.center().y(), rect.center().y(), delta=0.01)
        self.assertAlmostEqual(
            symbol_rect.width() / symbol_rect.height(),
            spec.preferred_symbol_aspect_ratio,
            delta=0.05,
        )

    def test_selection_label_rect_is_kept_separate_from_symbol_rect(self):
        spec = component_spec_for_display_name("Mass")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="mass_1",
            position=QPointF(50.0, 60.0),
            size=(320.0, 140.0),
        )
        renderer = ComponentRenderer()
        rect = component.base_rect()
        symbol_rect = renderer.symbol_render_rect(component, rect)
        label_rect, _ = renderer.selection_label_rect(component, rect, "Mass")
        self.assertFalse(label_rect.intersects(symbol_rect))

    def test_rotation_updates_port_positions(self):
        spring_spec = component_spec_for_display_name("Spring")
        component = CanvasVisualComponent(
            spec=spring_spec,
            component_id="spring_1",
            position=QPointF(100.0, 100.0),
            size=(90.0, 200.0),
            orientation=Orientation.DEG_0,
        )
        rect = QRectF(100.0, 100.0, 90.0, 200.0)
        port_positions_0 = [point for _, point in component.transformed_connector_ports(rect)]
        component.rotate_clockwise()
        port_positions_90 = [point for _, point in component.transformed_connector_ports(rect)]
        self.assertNotEqual((port_positions_0[0].x(), port_positions_0[0].y()), (port_positions_90[0].x(), port_positions_90[0].y()))
        self.assertEqual(component.orientation, Orientation.DEG_90)

    def test_selection_overlay_expands_component_bounds(self):
        spec = component_spec_for_display_name("Mass")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="mass_1",
            position=QPointF(50.0, 60.0),
            size=(240.0, 90.0),
        )
        rect = component.base_rect()
        overlay = component.selection_overlay_rect(rect)
        self.assertGreater(overlay.width(), rect.width())
        self.assertGreater(overlay.height(), rect.height())
        self.assertLess(overlay.width() - component.visual_bounds(rect).width(), 20.0)
        self.assertLess(overlay.height() - component.visual_bounds(rect).height(), 20.0)

    def test_pilot_components_define_presentation_style(self):
        for name in ("Mass", "Translational Spring", "Translational Damper", "Resistor"):
            spec = component_spec_for_display_name(name)
            self.assertIsNotNone(spec.presentation.preferred_size)
            self.assertIn(spec.presentation.terminal_anchor_mode, {"bounds_edge", "visual_terminal"})
            self.assertGreater(spec.presentation.art_scale, 1.0)

    def test_mechanical_pilot_set_disables_background_emphasis(self):
        for name in ("Mass", "Translational Spring", "Translational Damper"):
            spec = component_spec_for_display_name(name)
            self.assertEqual(spec.presentation.emphasis_fill_opacity, 0.0)

    def test_mass_connectors_use_terminal_aware_visual_geometry(self):
        spec = component_spec_for_display_name("Mass")
        component = CanvasVisualComponent(
            spec=spec,
            component_id="mass_1",
            position=QPointF(50.0, 60.0),
            size=spec.presentation.preferred_size or spec.base_size,
        )
        rect = component.base_rect()
        visual_rect = component.visual_bounds(rect)
        ports = component.transformed_connector_ports(rect)
        self.assertAlmostEqual(ports[0][1].x(), visual_rect.center().x(), delta=0.01)
        self.assertAlmostEqual(ports[1][1].x(), visual_rect.center().x(), delta=0.01)
        self.assertAlmostEqual(ports[0][1].y(), visual_rect.top() - 6.0, delta=0.01)
        self.assertAlmostEqual(ports[1][1].y(), visual_rect.bottom() + 6.0, delta=0.01)

    def test_spring_and_damper_terminal_anchors_are_inside_visual_bounds(self):
        for name in ("Spring", "Damper"):
            spec = component_spec_for_display_name(name)
            component = CanvasVisualComponent(
                spec=spec,
                component_id=f"{spec.type_key}_1",
                position=QPointF(120.0, 120.0),
                size=spec.presentation.preferred_size or spec.base_size,
            )
            rect = component.base_rect()
            visual_rect = component.visual_bounds(rect)
            ports = component.transformed_connector_ports(rect)
            self.assertAlmostEqual(ports[0][1].x(), visual_rect.center().x(), delta=0.01)
            self.assertAlmostEqual(ports[1][1].x(), visual_rect.center().x(), delta=0.01)
            self.assertAlmostEqual(ports[0][1].y(), visual_rect.top(), delta=0.01)
            self.assertAlmostEqual(ports[1][1].y(), visual_rect.bottom(), delta=0.01)

    def test_mass_symbol_rect_is_visually_more_dominant_than_spring_and_damper(self):
        renderer = ComponentRenderer()
        mass = CanvasVisualComponent(
            spec=component_spec_for_display_name("Mass"),
            component_id="mass_1",
            position=QPointF(20.0, 20.0),
            size=component_spec_for_display_name("Mass").presentation.preferred_size,
        )
        spring = CanvasVisualComponent(
            spec=component_spec_for_display_name("Spring"),
            component_id="spring_1",
            position=QPointF(20.0, 20.0),
            size=component_spec_for_display_name("Spring").presentation.preferred_size,
        )
        damper = CanvasVisualComponent(
            spec=component_spec_for_display_name("Damper"),
            component_id="damper_1",
            position=QPointF(20.0, 20.0),
            size=component_spec_for_display_name("Damper").presentation.preferred_size,
        )
        mass_rect = renderer.symbol_render_rect(mass, mass.base_rect())
        spring_rect = renderer.symbol_render_rect(spring, spring.base_rect())
        damper_rect = renderer.symbol_render_rect(damper, damper.base_rect())
        self.assertGreater(mass_rect.width() * mass_rect.height(), spring_rect.width() * spring_rect.height())
        self.assertGreater(mass_rect.width() * mass_rect.height(), damper_rect.width() * damper_rect.height())

    def test_pilot_set_produces_no_background_emphasis_rect(self):
        renderer = ComponentRenderer()
        for name in ("Mass", "Spring", "Damper"):
            spec = component_spec_for_display_name(name)
            component = CanvasVisualComponent(
                spec=spec,
                component_id=f"{spec.type_key}_1",
                position=QPointF(20.0, 20.0),
                size=spec.presentation.preferred_size,
            )
            self.assertTrue(renderer.emphasis_rect(component, component.base_rect()).isEmpty())

    def test_mechanical_random_reference_uses_deterministic_road_profile_when_static(self):
        renderer = ComponentRenderer()
        component = CanvasVisualComponent(
            spec=component_spec_for_display_name("Mechanical Random Reference"),
            component_id="road_input_1",
            position=QPointF(0.0, 0.0),
            size=(130.0, 80.0),
        )
        rect = component.base_rect()
        first = [(round(point.x(), 3), round(point.y(), 3)) for point in renderer.road_profile_points(rect, phase=0.0)]
        second = [(round(point.x(), 3), round(point.y(), 3)) for point in renderer.road_profile_points(rect, phase=0.0)]
        self.assertEqual(first, second)
        self.assertGreater(len(first), 6)

    def test_mechanical_random_reference_road_profile_animates_by_phase(self):
        renderer = ComponentRenderer()
        component = CanvasVisualComponent(
            spec=component_spec_for_display_name("Mechanical Random Reference"),
            component_id="road_input_1",
            position=QPointF(0.0, 0.0),
            size=(130.0, 80.0),
        )
        rect = component.base_rect()
        idle = [(round(point.x(), 3), round(point.y(), 3)) for point in renderer.road_profile_points(rect, phase=0.0)]
        animated = [(round(point.x(), 3), round(point.y(), 3)) for point in renderer.road_profile_points(rect, phase=0.9)]
        self.assertNotEqual(idle, animated)


if __name__ == "__main__":
    unittest.main()
