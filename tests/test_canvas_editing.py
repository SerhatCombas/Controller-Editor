from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from PySide6.QtGui import QImage, QKeyEvent, QMouseEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QMessageBox, QAbstractItemView, QLineEdit
    from PySide6.QtCore import QPoint, QPointF, Qt

    from app.ui.canvas.component_system import CanvasVisualComponent, CanvasWireConnection, ComponentIoRole, Orientation, component_spec_for_display_name
    from app.ui.canvas.model_canvas import ModelCanvas
    from app.ui.canvas.scene_animation_mapper import ComponentVisualOverride, SceneAnimationContext, SceneAnimationMapper
    from app.ui.main_window import MainWindow
    from app.ui.panels.model_panel import ModelPanel

    UI_DEPS_AVAILABLE = True
except ModuleNotFoundError:
    UI_DEPS_AVAILABLE = False


@unittest.skipUnless(UI_DEPS_AVAILABLE, "Canvas editing tests require PySide6")
class CanvasEditingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self._saved_layouts_path = Path(self._temp_dir.name) / "saved_layouts.json"

    def tearDown(self):
        self._temp_dir.cleanup()

    def _make_panel(self, *, persistent: bool = False) -> ModelPanel:
        return ModelPanel(saved_layouts_path=self._saved_layouts_path if persistent else None)

    def _widget_point_for_scene(self, canvas: ModelCanvas, scene_point: QPointF) -> QPointF:
        canvas.resize(900, 700)
        canvas._update_view_transform()
        scale = canvas._base_scale * canvas._zoom
        return QPointF(
            scene_point.x() * scale + canvas._view_offset.x(),
            scene_point.y() * scale + canvas._view_offset.y(),
        )

    def _left_click(self, canvas: ModelCanvas, scene_point: QPointF) -> None:
        widget_point = self._widget_point_for_scene(canvas, scene_point)
        event = QMouseEvent(
            QMouseEvent.MouseButtonPress,
            widget_point,
            widget_point,
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier,
        )
        canvas.mousePressEvent(event)

    def _right_click(self, canvas: ModelCanvas, scene_point: QPointF) -> None:
        widget_point = self._widget_point_for_scene(canvas, scene_point)
        event = QMouseEvent(
            QMouseEvent.MouseButtonPress,
            widget_point,
            widget_point,
            Qt.RightButton,
            Qt.RightButton,
            Qt.NoModifier,
        )
        canvas.mousePressEvent(event)

    def _select_input_signal(self, window: MainWindow, signal_id: str) -> None:
        combo = window.controller_panel.input_source
        index = combo.findData(signal_id)
        self.assertGreaterEqual(index, 0)
        combo.setCurrentIndex(index)
        self.app.processEvents()

    def _set_output_checked(self, window: MainWindow, signal_id: str, checked: bool) -> None:
        for index in range(window.controller_panel.output_signal_list.count()):
            item = window.controller_panel.output_signal_list.item(index)
            if item.data(Qt.UserRole) == signal_id:
                item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
                self.app.processEvents()
                return
        self.fail(f"Output signal not found: {signal_id}")

    def _mark_scene_input(self, window: MainWindow, component_index: int) -> None:
        window.model_panel.canvas.select_component(component_index)
        self.assertTrue(window.model_panel.canvas.assign_selected_component_io_role(ComponentIoRole.INPUT))
        self.app.processEvents()

    def _mark_scene_output(self, window: MainWindow, component_index: int) -> None:
        window.model_panel.canvas.select_component(component_index)
        self.assertTrue(window.model_panel.canvas.assign_selected_component_io_role(ComponentIoRole.OUTPUT))
        self.app.processEvents()

    def _clear_scene_role(self, window: MainWindow, component_index: int) -> None:
        window.model_panel.canvas.select_component(component_index)
        self.assertTrue(window.model_panel.canvas.assign_selected_component_io_role(None))
        self.app.processEvents()

    def _move_mouse(self, canvas: ModelCanvas, scene_point: QPointF) -> None:
        widget_point = self._widget_point_for_scene(canvas, scene_point)
        event = QMouseEvent(
            QMouseEvent.MouseMove,
            widget_point,
            widget_point,
            Qt.NoButton,
            Qt.NoButton,
            Qt.NoModifier,
        )
        canvas.mouseMoveEvent(event)

    def _drag_mouse(self, canvas: ModelCanvas, scene_point: QPointF) -> None:
        widget_point = self._widget_point_for_scene(canvas, scene_point)
        event = QMouseEvent(
            QMouseEvent.MouseMove,
            widget_point,
            widget_point,
            Qt.NoButton,
            Qt.LeftButton,
            Qt.NoModifier,
        )
        canvas.mouseMoveEvent(event)

    def _release_left(self, canvas: ModelCanvas, scene_point: QPointF) -> None:
        widget_point = self._widget_point_for_scene(canvas, scene_point)
        event = QMouseEvent(
            QMouseEvent.MouseButtonRelease,
            widget_point,
            widget_point,
            Qt.LeftButton,
            Qt.NoButton,
            Qt.NoModifier,
        )
        canvas.mouseReleaseEvent(event)

    def _press_left(self, canvas: ModelCanvas, scene_point: QPointF) -> None:
        self._left_click(canvas, scene_point)

    def _left_drag_sequence(self, canvas: ModelCanvas, start_scene_point: QPointF, end_scene_point: QPointF) -> None:
        self._press_left(canvas, start_scene_point)
        self._drag_mouse(canvas, end_scene_point)
        self._release_left(canvas, end_scene_point)

    def _layout_item_center(self, layout_list, item) -> QPoint:
        rect = layout_list.visualItemRect(item)
        return rect.center()

    def _middle_press_widget(self, canvas: ModelCanvas, widget_point: QPointF) -> None:
        event = QMouseEvent(
            QMouseEvent.MouseButtonPress,
            widget_point,
            widget_point,
            Qt.MiddleButton,
            Qt.MiddleButton,
            Qt.NoModifier,
        )
        canvas.mousePressEvent(event)

    def _middle_drag_widget(self, canvas: ModelCanvas, widget_point: QPointF) -> None:
        event = QMouseEvent(
            QMouseEvent.MouseMove,
            widget_point,
            widget_point,
            Qt.NoButton,
            Qt.MiddleButton,
            Qt.NoModifier,
        )
        canvas.mouseMoveEvent(event)

    def _middle_release_widget(self, canvas: ModelCanvas, widget_point: QPointF) -> None:
        event = QMouseEvent(
            QMouseEvent.MouseButtonRelease,
            widget_point,
            widget_point,
            Qt.MiddleButton,
            Qt.NoButton,
            Qt.NoModifier,
        )
        canvas.mouseReleaseEvent(event)

    def test_click_selection_payload_updates_property_panel(self):
        panel = ModelPanel()
        panel.load_default_model()
        panel.canvas.select_component(1)
        details = panel.canvas.selected_component_details()
        panel.property_editor.set_component(details)
        self.assertEqual(panel.property_editor.name_value.text(), "Mass")
        self.assertEqual(panel.property_editor.id_value.text(), "body_mass")
        self.assertEqual(panel.property_editor.category_value.text(), "rigid")
        self.assertEqual(panel.property_editor.boundary_value.text(), "internal")
        self.assertEqual(panel.property_editor.motion_value.text(), "translating")
        self.assertIn("Locked", panel.property_editor.status_value.text())

    def test_model_panel_starts_with_empty_workspace(self):
        panel = ModelPanel()
        self.assertEqual(panel.canvas.visible_component_names(), [])
        self.assertEqual(panel.canvas.selected_component_details()["name"], "No selection")

    def test_long_multi_selection_id_does_not_expand_left_panel_or_shrink_workspace(self):
        panel = self._make_panel()
        panel.resize(1600, 980)
        panel.show()
        panel.canvas._components = [
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Mass"),
                component_id="mass_component_with_very_long_identifier_alpha",
                position=QPointF(120.0, 120.0),
                size=(220.0, 90.0),
                deletable=True,
            ),
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Mass"),
                component_id="mass_component_with_very_long_identifier_beta",
                position=QPointF(420.0, 180.0),
                size=(220.0, 90.0),
                deletable=True,
            ),
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Mass"),
                component_id="mass_component_with_very_long_identifier_gamma",
                position=QPointF(720.0, 240.0),
                size=(220.0, 90.0),
                deletable=True,
            ),
        ]
        self.app.processEvents()
        sidebar_width_before = panel.sidebar.width()
        canvas_width_before = panel.canvas.width()
        panel.canvas.select_components([0, 1, 2])
        panel.property_editor.set_component(panel.canvas.selected_component_details())
        self.app.processEvents()
        self.assertEqual(panel.sidebar.width(), sidebar_width_before)
        self.assertEqual(panel.canvas.width(), canvas_width_before)
        self.assertIn("mass_component_with_very_long_identifier_alpha", panel.property_editor.id_value.text())
        self.assertTrue(panel.property_editor.id_value.has_horizontal_scrollbar())
        self.assertTrue(panel.property_editor.id_value.has_horizontal_overflow())

    def test_single_selection_property_panel_still_renders_normally(self):
        panel = self._make_panel()
        panel.load_default_model()
        panel.canvas.select_component(1)
        panel.property_editor.set_component(panel.canvas.selected_component_details())
        self.app.processEvents()
        self.assertEqual(panel.property_editor.name_value.text(), "Mass")
        self.assertEqual(panel.property_editor.id_value.text(), "body_mass")

    def test_main_window_does_not_auto_load_default_layout(self):
        with patch("app.ui.main_window.default_saved_layouts_path", return_value=self._saved_layouts_path):
            window = MainWindow()
        self.assertEqual(window.model_panel.canvas.visible_component_names(), [])
        self.assertEqual(window.app_state.simulation.model_template, "blank")

    def test_main_window_title_is_controller_editor(self):
        with patch("app.ui.main_window.default_saved_layouts_path", return_value=self._saved_layouts_path):
            window = MainWindow()
        self.assertEqual(window.windowTitle(), "Controller Editor")

    def test_analysis_panel_starts_empty_before_first_simulation(self):
        with patch("app.ui.main_window.default_saved_layouts_path", return_value=self._saved_layouts_path):
            window = MainWindow()
        self.assertEqual(
            window.analysis_panel.plot_state_snapshot(),
            {"live": False, "step": False, "bode": False, "pole_zero": False},
        )

    def test_analysis_panel_populates_after_simulation_run(self):
        with patch("app.ui.main_window.default_saved_layouts_path", return_value=self._saved_layouts_path):
            window = MainWindow()
        window.model_panel.load_default_model()
        self._mark_scene_input(window, 0)
        self._mark_scene_output(window, 1)
        window.start_simulation()
        window._advance_simulation()
        state = window.analysis_panel.plot_state_snapshot()
        self.assertTrue(state["live"])
        self.assertTrue(state["step"])
        self.assertTrue(state["bode"])
        self.assertTrue(state["pole_zero"])

    def test_simulation_requires_explicit_input_and_output_selection(self):
        with patch("app.ui.main_window.default_saved_layouts_path", return_value=self._saved_layouts_path):
            window = MainWindow()
        window.model_panel.load_default_model()
        self.assertFalse(window.controller_panel.start_button.isEnabled())
        self._mark_scene_input(window, 0)
        self.assertFalse(window.controller_panel.start_button.isEnabled())
        self._mark_scene_output(window, 1)
        self.assertTrue(window.controller_panel.start_button.isEnabled())

    def test_scene_input_assignment_updates_controller_selection_state(self):
        with patch("app.ui.main_window.default_saved_layouts_path", return_value=self._saved_layouts_path):
            window = MainWindow()
        window.model_panel.load_default_model()
        self._mark_scene_input(window, 0)
        self.assertEqual(window.controller_panel.input_source.currentData(), "road")
        self.assertEqual(window.app_state.selection.input_component_id, "road_source")
        self.assertIn("Mechanical Random Reference", window.controller_panel.scene_input_status.text())

    def test_scene_output_assignment_updates_controller_output_selection(self):
        with patch("app.ui.main_window.default_saved_layouts_path", return_value=self._saved_layouts_path):
            window = MainWindow()
        window.model_panel.load_default_model()
        self._mark_scene_output(window, 1)
        self.assertEqual(window.controller_panel.selected_output_signals(), ["body_displacement"])
        self.assertIn("Mass", window.controller_panel.scene_output_status.text())

    def test_spring_output_assignment_updates_controller_and_equation_binding(self):
        with patch("app.ui.main_window.default_saved_layouts_path", return_value=self._saved_layouts_path):
            window = MainWindow()
        window.model_panel.load_default_model()
        self._mark_scene_input(window, 0)
        self._mark_scene_output(window, 3)
        self.assertEqual(window.controller_panel.selected_output_signals(), ["suspension_deflection"])
        self.assertIn("Suspension deflection", window.controller_panel.scene_output_status.text())
        html = window.equation_panel.browser.toPlainText()
        self.assertIn("Suspension deflection", html)

    def test_simulation_requires_marked_scene_input_even_if_signal_exists_in_catalog(self):
        with patch("app.ui.main_window.default_saved_layouts_path", return_value=self._saved_layouts_path):
            window = MainWindow()
        window.model_panel.load_default_model()
        self._mark_scene_output(window, 1)
        self.assertFalse(window.controller_panel.start_button.isEnabled())
        self.assertIsNone(window.app_state.selection.input_component_id)

    def test_multiple_scene_inputs_propagate_into_app_state(self):
        with patch("app.ui.main_window.default_saved_layouts_path", return_value=self._saved_layouts_path):
            window = MainWindow()
        window.model_panel.load_default_model()
        force_source = CanvasVisualComponent(
            spec=component_spec_for_display_name("Ideal Force Source"),
            component_id="force_source_1",
            position=QPointF(780.0, 140.0),
            size=(110.0, 150.0),
            deletable=True,
        )
        window.model_panel.canvas._components.append(force_source)
        self._mark_scene_input(window, 0)
        self._mark_scene_input(window, len(window.model_panel.canvas._components) - 1)
        self._mark_scene_output(window, 1)
        self.assertEqual(window.app_state.selection.input_signals, ("road", "body_force"))
        self.assertEqual(window.app_state.selection.input_component_ids, ("road_source", "force_source_1"))
        self.assertTrue(window.controller_panel.start_button.isEnabled())

    def test_analysis_input_without_runtime_channel_fails_honestly_in_equation_panel(self):
        with patch("app.ui.main_window.default_saved_layouts_path", return_value=self._saved_layouts_path):
            window = MainWindow()
        window.model_panel.load_default_model()
        self._mark_scene_input(window, 4)
        self._mark_scene_output(window, 1)
        html = window.equation_panel.browser.toPlainText()
        self.assertIn("not yet supported", html)
        self.assertFalse(window.controller_panel.start_button.isEnabled())

    def test_invalid_simulation_start_keeps_results_empty(self):
        with patch("app.ui.main_window.default_saved_layouts_path", return_value=self._saved_layouts_path):
            window = MainWindow()
        window.model_panel.load_default_model()
        window.start_simulation()
        self.assertFalse(window._has_simulation_run)
        self.assertEqual(window.analysis_panel.plot_state_snapshot(), {"live": False, "step": False, "bode": False, "pole_zero": False})

    def test_single_selected_output_produces_one_plotted_series(self):
        with patch("app.ui.main_window.default_saved_layouts_path", return_value=self._saved_layouts_path):
            window = MainWindow()
        window.model_panel.load_default_model()
        self._mark_scene_input(window, 0)
        self._mark_scene_output(window, 1)
        window.start_simulation()
        window._advance_simulation()
        snapshot = window.analysis_panel.series_snapshot()
        self.assertEqual(snapshot["live"]["count"], 1)
        self.assertEqual(snapshot["live"]["labels"], ["Body displacement"])

    def test_multiple_selected_outputs_produce_distinct_series_and_legend(self):
        with patch("app.ui.main_window.default_saved_layouts_path", return_value=self._saved_layouts_path):
            window = MainWindow()
        window.model_panel.load_default_model()
        self._mark_scene_input(window, 0)
        self._mark_scene_output(window, 1)
        self._mark_scene_output(window, 4)
        window.start_simulation()
        window._advance_simulation()
        snapshot = window.analysis_panel.series_snapshot()
        self.assertEqual(snapshot["live"]["count"], 2)
        self.assertEqual(snapshot["live"]["labels"], ["Body displacement", "Wheel displacement"])
        self.assertEqual(len(set(snapshot["live"]["colors"])), 2)

    def test_changing_selected_outputs_removes_stale_curves(self):
        with patch("app.ui.main_window.default_saved_layouts_path", return_value=self._saved_layouts_path):
            window = MainWindow()
        window.model_panel.load_default_model()
        self._mark_scene_input(window, 0)
        self._mark_scene_output(window, 1)
        self._mark_scene_output(window, 4)
        window.start_simulation()
        window._advance_simulation()
        self.assertEqual(window.analysis_panel.series_snapshot()["live"]["count"], 2)
        window.stop_simulation()
        self._clear_scene_role(window, 4)
        window.start_simulation()
        window._advance_simulation()
        snapshot = window.analysis_panel.series_snapshot()
        self.assertEqual(snapshot["live"]["count"], 1)
        self.assertEqual(snapshot["live"]["labels"], ["Body displacement"])

    def test_clearing_only_input_role_updates_app_state_and_run_readiness(self):
        with patch("app.ui.main_window.default_saved_layouts_path", return_value=self._saved_layouts_path):
            window = MainWindow()
        window.model_panel.load_default_model()
        self._mark_scene_input(window, 0)
        self._mark_scene_output(window, 1)
        self.assertTrue(window.controller_panel.start_button.isEnabled())
        window.model_panel.canvas.select_component(0)
        self.assertTrue(window.model_panel.canvas.clear_selected_component_io_role(ComponentIoRole.INPUT))
        self.app.processEvents()
        self.assertEqual(window.app_state.selection.input_signals, ())
        self.assertEqual(window.app_state.selection.input_component_ids, ())
        self.assertFalse(window.controller_panel.start_button.isEnabled())
        self.assertEqual(window.controller_panel.scene_input_status.text(), "No scene input selected.")

    def test_clearing_only_output_role_updates_app_state_and_analysis_binding(self):
        with patch("app.ui.main_window.default_saved_layouts_path", return_value=self._saved_layouts_path):
            window = MainWindow()
        window.model_panel.load_default_model()
        self._mark_scene_input(window, 0)
        self._mark_scene_output(window, 1)
        self.assertEqual(window.app_state.selection.output_signals, ("body_displacement",))
        window.model_panel.canvas.select_component(1)
        self.assertTrue(window.model_panel.canvas.clear_selected_component_io_role(ComponentIoRole.OUTPUT))
        self.app.processEvents()
        self.assertEqual(window.app_state.selection.output_signals, ())
        self.assertEqual(window.app_state.selection.output_component_ids, ())
        self.assertFalse(window.controller_panel.start_button.isEnabled())
        self.assertEqual(window.controller_panel.scene_output_status.text(), "No scene outputs selected.")

    def test_switching_template_updates_available_signal_list(self):
        with patch("app.ui.main_window.default_saved_layouts_path", return_value=self._saved_layouts_path):
            window = MainWindow()
        window.model_panel.load_layout_by_id("default_two_mass")
        labels = window.controller_panel.available_signal_labels()
        self.assertIn("External force F(t)", labels["inputs"])
        self.assertIn("Mass 1 displacement", labels["outputs"])
        self.assertIn("Mass 2 displacement", labels["outputs"])
        self.assertNotIn("Body displacement", labels["outputs"])

    def test_switching_template_clears_incompatible_scene_input_selection(self):
        with patch("app.ui.main_window.default_saved_layouts_path", return_value=self._saved_layouts_path):
            window = MainWindow()
        window.model_panel.load_layout_by_id("default_quarter_car")
        self._mark_scene_input(window, 0)
        self.assertEqual(window.app_state.selection.input_component_id, "road_source")
        window.model_panel.load_layout_by_id("default_single_mass")
        self.assertIsNone(window.controller_panel.input_source.currentData())
        self.assertIsNone(window.app_state.selection.input_component_id)
        self.assertFalse(window.controller_panel.start_button.isEnabled())
        self.assertEqual(window.controller_panel.scene_input_status.text(), "No scene input selected.")

    def test_scene_input_selection_survives_visual_refresh(self):
        with patch("app.ui.main_window.default_saved_layouts_path", return_value=self._saved_layouts_path):
            window = MainWindow()
        window.model_panel.load_default_model()
        self._mark_scene_input(window, 0)
        window._refresh_canvas()
        self.app.processEvents()
        self.assertEqual(window.app_state.selection.input_component_id, "road_source")
        self.assertEqual(window.controller_panel.input_source.currentData(), "road")

    def test_saved_layout_load_does_not_reuse_incompatible_output_selection(self):
        with patch("app.ui.main_window.default_saved_layouts_path", return_value=self._saved_layouts_path):
            window = MainWindow()
        window.model_panel.load_layout_by_id("default_quarter_car")
        self._mark_scene_input(window, 0)
        self._mark_scene_output(window, 1)
        window.model_panel.load_layout_by_id("default_single_mass")
        self.assertFalse(window.controller_panel.start_button.isEnabled())
        self.assertIsNone(window.app_state.selection.input_component_id)
        self.assertEqual(window.controller_panel.selected_output_signals(), [])

    def test_layout_sections_exist_for_default_and_saved_layouts(self):
        panel = ModelPanel()
        self.assertEqual(panel.layout_section_titles(), ["Default Layouts", "Saved Layouts"])
        self.assertIn("Quarter-Car Suspension", panel.default_layout_titles())
        self.assertEqual(panel.saved_layout_titles(), [])
        self.assertEqual(panel.new_workspace_button.text(), "New Workspace")
        self.assertEqual(panel.save_layout_button.text(), "Save Layout")
        self.assertFalse(hasattr(panel, "load_button"))

    def test_double_clicking_default_layout_loads_workspace(self):
        panel = ModelPanel()
        item = panel.default_layouts_list.item(0)
        panel.default_layouts_list.itemDoubleClicked.emit(item)
        self.assertIn("Mass", panel.canvas.visible_component_names())
        self.assertEqual(len(panel.canvas._components), 8)

    def test_loading_default_layout_updates_main_window_runtime_template(self):
        with patch("app.ui.main_window.default_saved_layouts_path", return_value=self._saved_layouts_path):
            window = MainWindow()
        window.model_panel.load_layout_by_id("default_single_mass")
        self.assertEqual(window.app_state.simulation.model_template, "single_mass")
        self.assertEqual(window.simulation_service.runtime_diagnostics()["template_id"], "single_mass")

    def test_loading_saved_known_layout_updates_main_window_runtime_template(self):
        with patch("app.ui.main_window.default_saved_layouts_path", return_value=self._saved_layouts_path):
            window = MainWindow()
        window.model_panel.load_layout_by_id("default_two_mass")
        window.model_panel.save_current_layout("Saved Two Mass")
        window.model_panel.new_workspace()
        item = window.model_panel.saved_layouts_list.item(0)
        window.model_panel.saved_layouts_list.itemDoubleClicked.emit(item)
        self.assertEqual(window.app_state.simulation.model_template, "two_mass")
        self.assertEqual(window.simulation_service.runtime_diagnostics()["template_id"], "two_mass")

    def test_default_layouts_use_real_palette_component_display_names(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        self.assertIn("Mechanical Random Reference", canvas.visible_component_names())
        self.assertIn("Translational Damper", canvas.visible_component_names())
        self.assertIn("Translational Spring", canvas.visible_component_names())
        self.assertIn("Wheel", canvas.visible_component_names())
        canvas.load_single_mass_layout()
        self.assertIn("Mechanical Translational Reference", canvas.visible_component_names())
        self.assertIn("Translational Spring", canvas.visible_component_names())
        self.assertIn("Translational Damper", canvas.visible_component_names())

    def test_double_clicking_saved_layout_loads_workspace(self):
        panel = ModelPanel()
        panel.load_default_model()
        panel.save_current_layout("Saved Quarter Car")
        panel.canvas.clear_workspace()
        item = panel.saved_layouts_list.item(0)
        panel.saved_layouts_list.itemDoubleClicked.emit(item)
        self.assertIn("Mass", panel.canvas.visible_component_names())
        self.assertEqual(len(panel.canvas._components), 8)

    def test_loading_layout_clears_previous_workspace_first(self):
        panel = ModelPanel()
        panel.load_layout_by_id("default_quarter_car")
        self.assertEqual(len(panel.canvas._components), 8)
        panel.load_layout_by_id("default_single_mass")
        self.assertEqual(len(panel.canvas._components), 5)
        self.assertEqual(panel.canvas.visible_component_names().count("Mass"), 1)

    def test_repeated_layout_loading_does_not_stack_scenes(self):
        panel = ModelPanel()
        panel.load_layout_by_id("default_two_mass")
        first_count = len(panel.canvas._components)
        panel.load_layout_by_id("default_two_mass")
        second_count = len(panel.canvas._components)
        self.assertEqual(first_count, second_count)

    def test_new_workspace_action_empties_canvas(self):
        panel = ModelPanel()
        panel.load_layout_by_id("default_quarter_car")
        self.assertGreater(len(panel.canvas._components), 0)
        panel.new_workspace()
        self.assertEqual(panel.canvas.visible_component_names(), [])
        self.assertEqual(panel.canvas.persistent_wires(), [])
        self.assertEqual(panel.canvas.support_visual_mode(), "blank")

    def test_new_workspace_action_clears_selection_and_transient_state(self):
        panel = ModelPanel()
        panel.load_layout_by_id("default_two_mass")
        source_mass = panel.canvas._components[1]
        target_mass = panel.canvas._components[2]
        source_port = source_mass.connector_centers(panel.canvas._dynamic_rect(source_mass))[1]
        target_port = target_mass.connector_centers(panel.canvas._dynamic_rect(target_mass))[0]
        self._left_click(panel.canvas, source_port)
        self._left_click(panel.canvas, target_port)
        panel.canvas.select_component(1)
        panel.canvas._hovered_target_connector = None
        panel.new_workspace()
        self.assertEqual(panel.canvas.selected_component_details()["name"], "No selection")
        self.assertFalse(panel.canvas.wire_preview_active())
        self.assertIsNone(panel.canvas.selected_wire_snapshot())
        self.assertFalse(panel.canvas.pan_mode_active())
        self.assertEqual(panel.canvas.support_visual_mode(), "blank")

    def test_new_workspace_does_not_modify_layout_libraries(self):
        panel = ModelPanel()
        panel.load_default_model()
        panel.save_current_layout("Saved Quarter Car")
        default_before = panel.default_layout_titles()
        saved_before = panel.saved_layout_titles()
        panel.new_workspace()
        self.assertEqual(panel.default_layout_titles(), default_before)
        self.assertEqual(panel.saved_layout_titles(), saved_before)

    def test_layout_can_be_loaded_after_new_workspace(self):
        panel = ModelPanel()
        panel.load_layout_by_id("default_quarter_car")
        panel.new_workspace()
        self.assertEqual(panel.canvas.visible_component_names(), [])
        panel.load_layout_by_id("default_single_mass")
        self.assertIn("Mass", panel.canvas.visible_component_names())
        self.assertEqual(len(panel.canvas._components), 5)

    def test_save_layout_adds_new_item_under_saved_layouts(self):
        panel = self._make_panel(persistent=True)
        panel.load_layout_by_id("default_single_mass")
        saved = panel.save_current_layout("My Layout")
        self.assertEqual(saved.name, "My Layout")
        self.assertIn("My Layout", panel.saved_layout_titles())
        self.assertTrue(self._saved_layouts_path.exists())

    def test_save_layout_rejects_empty_name(self):
        panel = ModelPanel()
        panel.load_layout_by_id("default_single_mass")
        with self.assertRaises(ValueError):
            panel.save_current_layout("   ")

    def test_prompt_save_layout_rejects_empty_name(self):
        panel = ModelPanel()
        with patch("app.ui.panels.model_panel.QInputDialog.getText", return_value=("   ", True)), patch(
            "app.ui.panels.model_panel.QMessageBox.warning"
        ) as warning:
            saved = panel.prompt_save_layout()
        self.assertIsNone(saved)
        warning.assert_called_once()

    def test_prompt_save_layout_overwrites_duplicate_on_confirmation(self):
        panel = ModelPanel()
        panel.load_layout_by_id("default_single_mass")
        panel.save_current_layout("Duplicate")
        panel.new_workspace()
        panel.load_layout_by_id("default_quarter_car")
        with patch("app.ui.panels.model_panel.QInputDialog.getText", return_value=("Duplicate", True)), patch(
            "app.ui.panels.model_panel.QMessageBox.question", return_value=QMessageBox.Yes
        ):
            saved = panel.prompt_save_layout()
        self.assertIsNotNone(saved)
        self.assertEqual(panel.saved_layout_titles().count("Duplicate"), 1)
        item = panel.saved_layouts_list.item(0)
        panel.saved_layouts_list.itemDoubleClicked.emit(item)
        self.assertEqual(len(panel.canvas._components), 8)

    def test_prompt_save_layout_does_not_overwrite_when_declined(self):
        panel = ModelPanel()
        panel.load_layout_by_id("default_single_mass")
        panel.save_current_layout("Duplicate")
        panel.new_workspace()
        panel.load_layout_by_id("default_quarter_car")
        with patch("app.ui.panels.model_panel.QInputDialog.getText", return_value=("Duplicate", True)), patch(
            "app.ui.panels.model_panel.QMessageBox.question", return_value=QMessageBox.No
        ):
            saved = panel.prompt_save_layout()
        self.assertIsNone(saved)
        self.assertEqual(panel.saved_layout_titles().count("Duplicate"), 1)

    def test_save_layout_does_not_reload_or_clear_workspace(self):
        panel = ModelPanel()
        panel.load_layout_by_id("default_single_mass")
        before_names = panel.canvas.visible_component_names()
        before_count = len(panel.canvas._components)
        panel.save_current_layout("Stable Save")
        self.assertEqual(panel.canvas.visible_component_names(), before_names)
        self.assertEqual(len(panel.canvas._components), before_count)

    def test_saved_layouts_expose_rename_and_delete_actions_only(self):
        panel = self._make_panel(persistent=True)
        panel.load_layout_by_id("default_single_mass")
        saved = panel.save_current_layout("Editable Layout")
        self.assertEqual(panel.saved_layout_action_titles(saved.id), ["Rename", "Delete"])
        self.assertEqual(panel.default_layout_action_titles("default_quarter_car"), [])

    def test_first_click_selects_saved_layout(self):
        panel = self._make_panel(persistent=True)
        panel.load_layout_by_id("default_single_mass")
        panel.save_current_layout("Selectable Layout")
        panel.show()
        panel.saved_layouts_list.show()
        self.app.processEvents()
        item = panel.saved_layouts_list.item(0)
        QTest.mouseClick(panel.saved_layouts_list.viewport(), Qt.LeftButton, pos=self._layout_item_center(panel.saved_layouts_list, item))
        self.assertIs(panel.saved_layouts_list.currentItem(), item)
        self.assertEqual(panel.saved_layouts_list.state(), QAbstractItemView.NoState)

    def test_second_single_click_on_selected_saved_layout_enters_rename_mode(self):
        panel = self._make_panel(persistent=True)
        panel.load_layout_by_id("default_single_mass")
        panel.save_current_layout("Rename Me")
        panel.show()
        panel.saved_layouts_list.show()
        self.app.processEvents()
        item = panel.saved_layouts_list.item(0)
        position = self._layout_item_center(panel.saved_layouts_list, item)
        QTest.mouseClick(panel.saved_layouts_list.viewport(), Qt.LeftButton, pos=position)
        QTest.mouseClick(panel.saved_layouts_list.viewport(), Qt.LeftButton, pos=position)
        QTest.qWait(self.app.styleHints().mouseDoubleClickInterval() + 50)
        self.app.processEvents()
        self.assertEqual(panel.saved_layouts_list.state(), QAbstractItemView.EditingState)

    def test_enter_confirms_inline_saved_layout_rename(self):
        panel = self._make_panel(persistent=True)
        panel.load_layout_by_id("default_single_mass")
        saved = panel.save_current_layout("Rename Me")
        panel.show()
        panel.saved_layouts_list.show()
        self.app.processEvents()
        item = panel.saved_layouts_list.item(0)
        position = self._layout_item_center(panel.saved_layouts_list, item)
        QTest.mouseClick(panel.saved_layouts_list.viewport(), Qt.LeftButton, pos=position)
        QTest.mouseClick(panel.saved_layouts_list.viewport(), Qt.LeftButton, pos=position)
        QTest.qWait(self.app.styleHints().mouseDoubleClickInterval() + 50)
        editor = panel.saved_layouts_list.findChild(QLineEdit)
        self.assertIsNotNone(editor)
        editor.selectAll()
        QTest.keyClicks(editor, "Renamed Inline")
        QTest.keyClick(editor, Qt.Key_Return)
        self.app.processEvents()
        self.assertEqual(panel.saved_layout_titles(), ["Renamed Inline"])
        reloaded = self._make_panel(persistent=True)
        self.assertEqual(reloaded.saved_layout_titles(), ["Renamed Inline"])
        self.assertEqual(reloaded.saved_layouts[0].id, saved.id)

    def test_escape_cancels_inline_saved_layout_rename(self):
        panel = self._make_panel(persistent=True)
        panel.load_layout_by_id("default_single_mass")
        panel.save_current_layout("Rename Me")
        panel.show()
        panel.saved_layouts_list.show()
        self.app.processEvents()
        item = panel.saved_layouts_list.item(0)
        position = self._layout_item_center(panel.saved_layouts_list, item)
        QTest.mouseClick(panel.saved_layouts_list.viewport(), Qt.LeftButton, pos=position)
        QTest.mouseClick(panel.saved_layouts_list.viewport(), Qt.LeftButton, pos=position)
        QTest.qWait(self.app.styleHints().mouseDoubleClickInterval() + 50)
        editor = panel.saved_layouts_list.findChild(QLineEdit)
        self.assertIsNotNone(editor)
        editor.selectAll()
        QTest.keyClicks(editor, "Cancelled Rename")
        QTest.keyClick(editor, Qt.Key_Escape)
        self.app.processEvents()
        self.assertEqual(panel.saved_layout_titles(), ["Rename Me"])

    def test_double_click_on_saved_layout_still_loads_instead_of_renaming(self):
        panel = self._make_panel(persistent=True)
        panel.load_layout_by_id("default_single_mass")
        panel.save_current_layout("Load Me")
        panel.new_workspace()
        panel.show()
        panel.saved_layouts_list.show()
        self.app.processEvents()
        item = panel.saved_layouts_list.item(0)
        position = self._layout_item_center(panel.saved_layouts_list, item)
        QTest.mouseClick(panel.saved_layouts_list.viewport(), Qt.LeftButton, pos=position)
        QTest.mouseDClick(panel.saved_layouts_list.viewport(), Qt.LeftButton, pos=position)
        QTest.qWait(self.app.styleHints().mouseDoubleClickInterval() + 50)
        self.app.processEvents()
        self.assertEqual(panel.saved_layouts_list.state(), QAbstractItemView.NoState)
        self.assertIn("Mass", panel.canvas.visible_component_names())

    def test_default_layouts_do_not_support_inline_rename_mode(self):
        panel = self._make_panel(persistent=True)
        panel.show()
        panel.default_layouts_list.show()
        self.app.processEvents()
        item = panel.default_layouts_list.item(0)
        position = self._layout_item_center(panel.default_layouts_list, item)
        QTest.mouseClick(panel.default_layouts_list.viewport(), Qt.LeftButton, pos=position)
        QTest.mouseClick(panel.default_layouts_list.viewport(), Qt.LeftButton, pos=position)
        QTest.qWait(self.app.styleHints().mouseDoubleClickInterval() + 50)
        self.app.processEvents()
        self.assertEqual(panel.default_layouts_list.state(), QAbstractItemView.NoState)

    def test_rename_saved_layout_updates_visible_name(self):
        panel = self._make_panel(persistent=True)
        panel.load_layout_by_id("default_single_mass")
        saved = panel.save_current_layout("Original Name")
        renamed = panel.rename_saved_layout(saved.id, "Renamed Layout")
        self.assertEqual(renamed.id, saved.id)
        self.assertEqual(panel.saved_layout_titles(), ["Renamed Layout"])

    def test_rename_saved_layout_rejects_empty_name(self):
        panel = ModelPanel()
        panel.load_layout_by_id("default_single_mass")
        saved = panel.save_current_layout("Original Name")
        with self.assertRaises(ValueError):
            panel.rename_saved_layout(saved.id, "   ")

    def test_rename_saved_layout_rejects_duplicate_name(self):
        panel = ModelPanel()
        panel.load_layout_by_id("default_single_mass")
        first = panel.save_current_layout("Layout One")
        panel.save_current_layout("Layout Two")
        with self.assertRaises(ValueError):
            panel.rename_saved_layout(first.id, "Layout Two")

    def test_prompt_rename_saved_layout_rejects_empty_name(self):
        panel = ModelPanel()
        panel.load_layout_by_id("default_single_mass")
        saved = panel.save_current_layout("Original Name")
        with patch("app.ui.panels.model_panel.QInputDialog.getText", return_value=("   ", True)), patch(
            "app.ui.panels.model_panel.QMessageBox.warning"
        ) as warning:
            renamed = panel.prompt_rename_saved_layout(saved.id)
        self.assertIsNone(renamed)
        warning.assert_called_once()

    def test_prompt_rename_saved_layout_rejects_duplicate_name(self):
        panel = ModelPanel()
        panel.load_layout_by_id("default_single_mass")
        first = panel.save_current_layout("Layout One")
        panel.save_current_layout("Layout Two")
        with patch("app.ui.panels.model_panel.QInputDialog.getText", return_value=("Layout Two", True)), patch(
            "app.ui.panels.model_panel.QMessageBox.warning"
        ) as warning:
            renamed = panel.prompt_rename_saved_layout(first.id)
        self.assertIsNone(renamed)
        warning.assert_called_once()
        self.assertEqual(panel.saved_layout_titles(), ["Layout One", "Layout Two"])

    def test_delete_saved_layout_removes_item_from_list(self):
        panel = self._make_panel(persistent=True)
        panel.load_layout_by_id("default_single_mass")
        saved = panel.save_current_layout("Disposable Layout")
        deleted = panel.delete_saved_layout(saved.id)
        self.assertTrue(deleted)
        self.assertEqual(panel.saved_layout_titles(), [])

    def test_prompt_delete_saved_layout_honors_confirmation(self):
        panel = ModelPanel()
        panel.load_layout_by_id("default_single_mass")
        saved = panel.save_current_layout("Disposable Layout")
        with patch("app.ui.panels.model_panel.QMessageBox.question", return_value=QMessageBox.No):
            deleted = panel.prompt_delete_saved_layout(saved.id)
        self.assertFalse(deleted)
        self.assertEqual(panel.saved_layout_titles(), ["Disposable Layout"])
        with patch("app.ui.panels.model_panel.QMessageBox.question", return_value=QMessageBox.Yes):
            deleted = panel.prompt_delete_saved_layout(saved.id)
        self.assertTrue(deleted)
        self.assertEqual(panel.saved_layout_titles(), [])

    def test_deleting_saved_layout_does_not_corrupt_current_workspace(self):
        panel = self._make_panel(persistent=True)
        panel.load_layout_by_id("default_single_mass")
        saved = panel.save_current_layout("Disposable Layout")
        before_names = panel.canvas.visible_component_names()
        before_count = len(panel.canvas._components)
        deleted = panel.delete_saved_layout(saved.id)
        self.assertTrue(deleted)
        self.assertEqual(panel.canvas.visible_component_names(), before_names)
        self.assertEqual(len(panel.canvas._components), before_count)

    def test_saved_layouts_reload_from_persistent_storage_on_startup(self):
        first_panel = self._make_panel(persistent=True)
        first_panel.load_layout_by_id("default_single_mass")
        first_panel.save_current_layout("Persistent Layout")
        second_panel = self._make_panel(persistent=True)
        self.assertEqual(second_panel.saved_layout_titles(), ["Persistent Layout"])

    def test_rename_updates_persisted_saved_layout_data(self):
        first_panel = self._make_panel(persistent=True)
        first_panel.load_layout_by_id("default_single_mass")
        saved = first_panel.save_current_layout("Persistent Layout")
        first_panel.rename_saved_layout(saved.id, "Renamed Persistent Layout")
        second_panel = self._make_panel(persistent=True)
        self.assertEqual(second_panel.saved_layout_titles(), ["Renamed Persistent Layout"])

    def test_delete_removes_persisted_saved_layout_data(self):
        first_panel = self._make_panel(persistent=True)
        first_panel.load_layout_by_id("default_single_mass")
        saved = first_panel.save_current_layout("Persistent Layout")
        first_panel.delete_saved_layout(saved.id)
        second_panel = self._make_panel(persistent=True)
        self.assertEqual(second_panel.saved_layout_titles(), [])

    def test_blank_workspace_contains_no_random_reference(self):
        canvas = ModelCanvas()
        canvas.clear_workspace()
        self.assertEqual(canvas.visible_component_names(), [])
        self.assertEqual(canvas.support_visual_mode(), "blank")

    def test_quarter_car_layout_still_loads_random_reference_explicitly(self):
        panel = ModelPanel()
        panel.load_layout_by_id("default_quarter_car")
        self.assertIn("Mechanical Random Reference", panel.canvas.visible_component_names())

    def test_middle_mouse_press_enters_pan_mode_and_changes_cursor(self):
        canvas = ModelCanvas()
        start = QPointF(320.0, 240.0)
        self._middle_press_widget(canvas, start)
        self.assertTrue(canvas.pan_mode_active())
        self.assertEqual(canvas.cursor().shape(), Qt.ClosedHandCursor)

    def test_middle_mouse_drag_changes_viewport_offset(self):
        canvas = ModelCanvas()
        canvas.resize(900, 700)
        before = canvas.view_offset_snapshot()
        start = QPointF(320.0, 240.0)
        end = QPointF(390.0, 290.0)
        self._middle_press_widget(canvas, start)
        self._middle_drag_widget(canvas, end)
        after = canvas.view_offset_snapshot()
        self.assertNotEqual((before.x(), before.y()), (after.x(), after.y()))
        self.assertEqual(canvas.pan_offset_snapshot(), QPointF(70.0, 50.0))

    def test_middle_mouse_release_exits_pan_mode_and_restores_cursor(self):
        canvas = ModelCanvas()
        start = QPointF(320.0, 240.0)
        end = QPointF(380.0, 260.0)
        self._middle_press_widget(canvas, start)
        self._middle_drag_widget(canvas, end)
        self._middle_release_widget(canvas, end)
        self.assertFalse(canvas.pan_mode_active())
        self.assertEqual(canvas.cursor().shape(), Qt.ArrowCursor)

    def test_pan_mode_does_not_trigger_selection_or_wiring(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("two_mass")
        source_mass = canvas._components[1]
        target_mass = canvas._components[2]
        source_port = self._widget_point_for_scene(canvas, source_mass.connector_centers(canvas._dynamic_rect(source_mass))[1])
        target_port = self._widget_point_for_scene(canvas, target_mass.connector_centers(canvas._dynamic_rect(target_mass))[0])
        self._middle_press_widget(canvas, source_port)
        self._middle_drag_widget(canvas, target_port)
        self.assertEqual(canvas.selected_component_details()["name"], "No selection")
        self.assertFalse(canvas.wire_preview_active())
        self.assertIsNone(canvas.selected_wire_snapshot())

    def test_resize_and_component_drag_do_not_start_during_pan_mode(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("single_mass")
        canvas.select_component(1)
        component = canvas._components[1]
        before = canvas._component_rect(component)
        handle = next(handle for handle in canvas.selected_resize_handles_snapshot() if handle["corner"] == "bottom_right")
        start = handle["rect"].center()
        end = QPointF(start.x() + 80.0, start.y() + 60.0)
        self._middle_press_widget(canvas, start)
        self._middle_drag_widget(canvas, end)
        self._middle_release_widget(canvas, end)
        after = canvas._component_rect(component)
        self.assertEqual(before, after)

    def test_component_drag_can_move_beyond_old_scene_extent(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("single_mass")
        component = canvas._components[1]
        start = canvas._dynamic_rect(component).center()
        self._left_drag_sequence(canvas, start, QPointF(2150.0, start.y()))
        self.assertGreater(component.position.x(), 1500.0)

    def test_empty_canvas_left_drag_starts_marquee_mode(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("single_mass")
        start = QPointF(40.0, 40.0)
        self._press_left(canvas, start)
        self._drag_mouse(canvas, QPointF(260.0, 220.0))
        snapshot = canvas.marquee_selection_snapshot()
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["mode"], "containment")
        self.assertTrue(snapshot["fill_enabled"])

    def test_downward_drag_selects_only_fully_contained_components(self):
        canvas = ModelCanvas()
        canvas._components = [
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Mass"),
                component_id="mass_a",
                position=QPointF(120.0, 120.0),
                size=(220.0, 90.0),
                deletable=True,
            ),
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Mass"),
                component_id="mass_b",
                position=QPointF(360.0, 150.0),
                size=(220.0, 90.0),
                deletable=True,
            ),
        ]
        first_rect = canvas._components[0].selection_overlay_rect(canvas._dynamic_rect(canvas._components[0]))
        self._left_drag_sequence(canvas, first_rect.topLeft() - QPointF(10.0, 10.0), first_rect.bottomRight() + QPointF(10.0, 10.0))
        self.assertEqual(canvas.selected_component_ids_snapshot(), ["mass_a"])
        self.assertEqual(canvas.selected_component_details()["name"], "Mass")

    def test_upward_drag_selects_intersected_components(self):
        canvas = ModelCanvas()
        canvas._components = [
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Mass"),
                component_id="mass_a",
                position=QPointF(120.0, 120.0),
                size=(220.0, 90.0),
                deletable=True,
            ),
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Mass"),
                component_id="mass_b",
                position=QPointF(360.0, 150.0),
                size=(220.0, 90.0),
                deletable=True,
            ),
        ]
        self._left_drag_sequence(canvas, QPointF(590.0, 270.0), QPointF(250.0, 110.0))
        self.assertEqual(canvas.selected_component_ids_snapshot(), ["mass_a", "mass_b"])
        self.assertEqual(canvas.selected_component_details()["selection_state"], "Multi-selected")

    def test_crossing_marquee_uses_orange_without_fill(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("single_mass")
        start = QPointF(320.0, 280.0)
        self._press_left(canvas, start)
        self._drag_mouse(canvas, QPointF(180.0, 120.0))
        snapshot = canvas.marquee_selection_snapshot()
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["mode"], "crossing")
        self.assertFalse(snapshot["fill_enabled"])
        self.assertEqual(snapshot["color"], "#f97316")

    def test_marquee_does_not_start_during_resize_wiring_or_pan(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("single_mass")
        canvas.select_component(1)
        resize_handle = next(handle for handle in canvas.selected_resize_handles_snapshot() if handle["corner"] == "bottom_right")
        self._press_left(canvas, resize_handle["rect"].center())
        self._drag_mouse(canvas, QPointF(resize_handle["rect"].center().x() + 40.0, resize_handle["rect"].center().y() + 40.0))
        self.assertIsNone(canvas.marquee_selection_snapshot())
        self._release_left(canvas, QPointF(resize_handle["rect"].center().x() + 40.0, resize_handle["rect"].center().y() + 40.0))

        source_component = canvas._components[1]
        source_port = source_component.connector_centers(canvas._dynamic_rect(source_component))[0]
        self._left_click(canvas, source_port)
        self._drag_mouse(canvas, QPointF(source_port.x() + 100.0, source_port.y() + 100.0))
        self.assertTrue(canvas.wire_preview_active())
        self.assertIsNone(canvas.marquee_selection_snapshot())
        self._right_click(canvas, QPointF(source_port.x() + 100.0, source_port.y() + 100.0))

        widget_start = QPointF(320.0, 240.0)
        widget_end = QPointF(420.0, 310.0)
        self._middle_press_widget(canvas, widget_start)
        self._middle_drag_widget(canvas, widget_end)
        self.assertIsNone(canvas.marquee_selection_snapshot())
        self._middle_release_widget(canvas, widget_end)

    def test_marquee_selection_works_with_resized_and_rotated_components(self):
        canvas = ModelCanvas()
        canvas._components = [
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Mass"),
                component_id="mass_1",
                position=QPointF(150.0, 140.0),
                size=(220.0, 90.0),
                deletable=True,
            ),
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Mass"),
                component_id="mass_2",
                position=QPointF(420.0, 170.0),
                size=(220.0, 90.0),
                deletable=True,
                orientation=Orientation.DEG_90,
            ),
        ]
        canvas.select_component(0)
        bottom_right = next(handle for handle in canvas.selected_resize_handles_snapshot() if handle["corner"] == "bottom_right")
        self._left_drag_sequence(
            canvas,
            bottom_right["rect"].center(),
            QPointF(bottom_right["rect"].center().x() + 70.0, bottom_right["rect"].center().y() + 40.0),
        )
        first_rect = canvas._components[0].selection_overlay_rect(canvas._dynamic_rect(canvas._components[0]))
        second_rect = canvas._components[1].selection_overlay_rect(canvas._dynamic_rect(canvas._components[1]))
        union = first_rect.united(second_rect)
        self._left_drag_sequence(canvas, union.bottomRight() + QPointF(20.0, 20.0), union.topLeft() - QPointF(20.0, 20.0))
        self.assertEqual(canvas.selected_component_ids_snapshot(), ["mass_1", "mass_2"])

    def test_marquee_selection_clears_after_mouse_release(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("single_mass")
        self._press_left(canvas, QPointF(40.0, 40.0))
        self._drag_mouse(canvas, QPointF(260.0, 220.0))
        self.assertIsNotNone(canvas.marquee_selection_snapshot())
        self._release_left(canvas, QPointF(260.0, 220.0))
        self.assertIsNone(canvas.marquee_selection_snapshot())

    def test_dragging_one_selected_component_moves_whole_group(self):
        canvas = ModelCanvas()
        canvas._components = [
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Mass"),
                component_id="mass_a",
                position=QPointF(120.0, 120.0),
                size=(220.0, 90.0),
                deletable=True,
            ),
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Mass"),
                component_id="mass_b",
                position=QPointF(420.0, 180.0),
                size=(220.0, 90.0),
                deletable=True,
            ),
        ]
        canvas.select_components([0, 1])
        before_a = QPointF(canvas._components[0].position)
        before_b = QPointF(canvas._components[1].position)
        rect = canvas._components[0].selection_overlay_rect(canvas._dynamic_rect(canvas._components[0]))
        start = rect.center()
        end = QPointF(start.x() + 80.0, start.y() + 55.0)
        self._left_drag_sequence(canvas, start, end)
        after_a = canvas._components[0].position
        after_b = canvas._components[1].position
        self.assertAlmostEqual(after_a.x() - before_a.x(), 80.0, delta=1.0)
        self.assertAlmostEqual(after_a.y() - before_a.y(), 55.0, delta=1.0)
        self.assertAlmostEqual(after_b.x() - before_b.x(), 80.0, delta=1.0)
        self.assertAlmostEqual(after_b.y() - before_b.y(), 55.0, delta=1.0)
        self.assertAlmostEqual(after_b.x() - after_a.x(), before_b.x() - before_a.x(), delta=0.2)
        self.assertAlmostEqual(after_b.y() - after_a.y(), before_b.y() - before_a.y(), delta=0.2)

    def test_multi_selection_delete_removes_all_selected_components_and_wires(self):
        canvas = ModelCanvas()
        canvas._components = [
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Mass"),
                component_id="mass_a",
                position=QPointF(120.0, 120.0),
                size=(220.0, 90.0),
                deletable=True,
            ),
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Mass"),
                component_id="mass_b",
                position=QPointF(420.0, 180.0),
                size=(220.0, 90.0),
                deletable=True,
            ),
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Mechanical Translational Reference"),
                component_id="ground_c",
                position=QPointF(760.0, 260.0),
                size=(440.0, 36.0),
                deletable=True,
            ),
        ]
        canvas._wires = [
            CanvasWireConnection(
                source_component_id="mass_a",
                source_connector_name="top",
                target_component_id="mass_b",
                target_connector_name="bottom",
            ),
            CanvasWireConnection(
                source_component_id="mass_b",
                source_connector_name="top",
                target_component_id="ground_c",
                target_connector_name="top",
            ),
        ]
        canvas.select_components([0, 1])
        event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier)
        canvas.keyPressEvent(event)
        self.assertEqual(canvas.visible_component_names(), ["Mechanical Translational Reference"])
        self.assertEqual(canvas.persistent_wires(), [])
        self.assertEqual(canvas.selected_component_ids_snapshot(), [])
        self.assertEqual(canvas.selected_component_details()["name"], "No selection")

    def test_single_selection_drag_behavior_still_works(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("single_mass")
        canvas.select_component(1)
        component = canvas._components[1]
        before = QPointF(component.position)
        start = component.selection_overlay_rect(canvas._dynamic_rect(component)).center()
        end = QPointF(start.x() + 60.0, start.y() + 30.0)
        self._left_drag_sequence(canvas, start, end)
        self.assertAlmostEqual(component.position.x() - before.x(), 60.0, delta=2.0)
        self.assertAlmostEqual(component.position.y() - before.y(), 30.0, delta=2.0)

    def test_grid_rendering_covers_visible_viewport_region(self):
        canvas = ModelCanvas()
        canvas.resize(900, 700)
        snapshot = canvas.grid_render_snapshot()
        self.assertTrue(snapshot["covers_visible_rect"])

    def test_panning_changes_visible_grid_region_seamlessly(self):
        canvas = ModelCanvas()
        canvas.resize(900, 700)
        before = canvas.grid_render_snapshot()
        start = QPointF(320.0, 240.0)
        end = QPointF(450.0, 340.0)
        self._middle_press_widget(canvas, start)
        self._middle_drag_widget(canvas, end)
        self._middle_release_widget(canvas, end)
        after = canvas.grid_render_snapshot()
        self.assertTrue(after["covers_visible_rect"])
        self.assertNotEqual(before["visible_rect"], after["visible_rect"])

    def test_new_components_start_without_assigned_io_role(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        self.assertIsNone(canvas._components[1].assigned_io_role)
        self.assertEqual(canvas.selected_component_details()["name"], "No selection")

    def test_component_palette_exposes_mechanical_and_electrical_groups(self):
        panel = ModelPanel()
        self.assertEqual(panel.palette.group_titles(), ["Mechanical", "Electrical"])
        # 4-level hierarchy: Domain → Subdomain → Category → Item
        self.assertEqual(panel.palette.subgroup_titles("Mechanical"), ["Translational", "Rotational"])
        self.assertEqual(panel.palette.subgroup_titles("Electrical"), ["Analog", "Digital"])
        self.assertTrue(panel.library_sections["Mechanical"].is_expanded())
        self.assertFalse(panel.library_sections["Electrical"].is_expanded())

    def test_component_palette_groups_can_expand_and_collapse(self):
        panel = ModelPanel()
        electrical = panel.library_sections["Electrical"]
        self.assertFalse(electrical.is_expanded())
        self.assertTrue(electrical.content.isHidden())
        electrical.toggle_button.click()
        self.assertTrue(electrical.is_expanded())
        self.assertFalse(electrical.content.isHidden())
        electrical.toggle_button.click()
        self.assertFalse(electrical.is_expanded())
        self.assertTrue(electrical.content.isHidden())

    def test_component_palette_populates_expected_items_under_groups(self):
        panel = ModelPanel()
        mechanical_items = panel.palette.group_items("Mechanical")
        electrical_items = panel.palette.group_items("Electrical")
        # Backend-ready components in 4-level hierarchy
        self.assertIn("Mass", mechanical_items)
        self.assertIn("Translational Spring", mechanical_items)
        self.assertIn("Mechanical Translational Reference", mechanical_items)
        self.assertIn("Ideal Force Source", mechanical_items)
        self.assertIn("Electrical Reference", electrical_items)
        self.assertIn("Resistor", electrical_items)
        self.assertIn("DC Voltage Source", electrical_items)
        self.assertIn("DC Current Source", electrical_items)

    def test_palette_items_appear_in_correct_4level_groups(self):
        panel = ModelPanel()
        self.assertIn("Mass", panel.palette.group_items("Mechanical/Translational/Components"))
        self.assertIn("Ideal Force Source", panel.palette.group_items("Mechanical/Translational/Sources"))
        self.assertIn("Resistor", panel.palette.group_items("Electrical/Analog/Components"))
        self.assertIn("DC Voltage Source", panel.palette.group_items("Electrical/Analog/Sources"))

    def test_component_palette_icons_load_and_scroll_area_remains_stable(self):
        panel = ModelPanel()
        components_section = panel.palette.section("Mechanical/Translational/Components")
        self.assertIsNotNone(components_section)
        mechanical_list = components_section.library
        icon_item = mechanical_list.item(0)
        self.assertFalse(icon_item.icon().isNull())
        self.assertTrue(panel.palette_scroll.widgetResizable())
        self.assertIsNotNone(panel.palette_scroll.widget())

    def test_component_palette_search_bar_exists(self):
        panel = ModelPanel()
        self.assertEqual(panel.palette_search.placeholderText(), "Search components...")

    def test_component_palette_search_filters_across_groups(self):
        panel = ModelPanel()
        panel.palette_search.setText("resistor")
        self.assertIn("Resistor", panel.palette.visible_group_items("Electrical/Analog/Components"))
        self.assertEqual(panel.palette.visible_group_items("Mechanical"), [])
        panel.palette_search.setText("force")
        self.assertIn("Ideal Force Source", panel.palette.visible_group_items("Mechanical/Translational/Sources"))

    def test_clearing_palette_search_restores_hierarchical_view(self):
        panel = ModelPanel()
        panel.palette_search.setText("resistor")
        self.assertEqual(panel.palette.visible_group_items("Mechanical"), [])
        panel.palette_search.clear()
        self.assertIn("Mass", panel.palette.group_items("Mechanical/Translational/Components"))
        self.assertIn("Resistor", panel.palette.visible_group_items("Electrical"))

    def test_new_hierarchical_palette_sections_expose_expected_leaf_items(self):
        panel = ModelPanel()
        self.assertIn("Ideal Force Source", panel.palette.group_items("Mechanical/Translational/Sources"))
        self.assertIn("DC Voltage Source", panel.palette.group_items("Electrical/Analog/Sources"))
        self.assertIn("Electrical Reference", panel.palette.group_items("Electrical/Analog/Components"))
        # Empty categories should have no items
        self.assertEqual(panel.palette.group_items("Mechanical/Translational/Sensors"), [])
        self.assertEqual(panel.palette.group_items("Mechanical/Rotational"), [])

    def test_property_panel_distinguishes_fixed_and_free_boundaries(self):
        panel = ModelPanel()
        panel.canvas._components = [
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Mechanical Translational Reference"),
                component_id="ground_1",
                position=QPointF(120.0, 420.0),
                size=(440.0, 36.0),
                deletable=True,
            ),
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Translational Free End"),
                component_id="free_end_1",
                position=QPointF(220.0, 320.0),
                size=(90.0, 60.0),
                deletable=True,
            ),
        ]
        panel.canvas.select_component(0)
        panel.property_editor.set_component(panel.canvas.selected_component_details())
        self.assertEqual(panel.property_editor.category_value.text(), "rigid")
        self.assertEqual(panel.property_editor.boundary_value.text(), "fixed_reference")
        self.assertEqual(panel.property_editor.motion_value.text(), "fixed")
        panel.canvas.select_component(1)
        panel.property_editor.set_component(panel.canvas.selected_component_details())
        self.assertEqual(panel.property_editor.category_value.text(), "rigid")
        self.assertEqual(panel.property_editor.boundary_value.text(), "free_end")
        self.assertEqual(panel.property_editor.motion_value.text(), "static")

    def test_property_panel_distinguishes_electrical_reference_from_mechanical_reference(self):
        panel = ModelPanel()
        panel.canvas._components = [
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Mechanical Translational Reference"),
                component_id="ground_1",
                position=QPointF(120.0, 420.0),
                size=(440.0, 36.0),
                deletable=True,
            ),
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Electrical Reference"),
                component_id="eref_1",
                position=QPointF(260.0, 320.0),
                size=(72.0, 72.0),
                deletable=True,
            ),
        ]
        panel.canvas.select_component(0)
        panel.property_editor.set_component(panel.canvas.selected_component_details())
        self.assertEqual(panel.property_editor.domain_value.text(), "mechanical")
        self.assertEqual(panel.property_editor.boundary_value.text(), "fixed_reference")
        panel.canvas.select_component(1)
        panel.property_editor.set_component(panel.canvas.selected_component_details())
        self.assertEqual(panel.property_editor.domain_value.text(), "electrical")
        self.assertEqual(panel.property_editor.category_value.text(), "rigid")
        self.assertEqual(panel.property_editor.boundary_value.text(), "electrical_reference")
        self.assertEqual(panel.property_editor.motion_value.text(), "static")

    def test_property_panel_shows_resistor_as_internal_static_electrical_component(self):
        panel = ModelPanel()
        panel.canvas._components = [
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Resistor"),
                component_id="resistor_1",
                position=QPointF(200.0, 320.0),
                size=(120.0, 56.0),
                deletable=True,
            ),
        ]
        panel.canvas.select_component(0)
        panel.property_editor.set_component(panel.canvas.selected_component_details())
        self.assertEqual(panel.property_editor.name_value.text(), "Resistor")
        self.assertEqual(panel.property_editor.domain_value.text(), "electrical")
        self.assertEqual(panel.property_editor.category_value.text(), "rigid")
        self.assertEqual(panel.property_editor.boundary_value.text(), "internal")
        self.assertEqual(panel.property_editor.motion_value.text(), "static")
        self.assertEqual(panel.property_editor.port_value.text(), "2")

    def test_property_panel_shows_capacitor_as_internal_static_electrical_component(self):
        panel = ModelPanel()
        panel.canvas._components = [
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Capacitor"),
                component_id="capacitor_1",
                position=QPointF(200.0, 320.0),
                size=(120.0, 56.0),
                deletable=True,
            ),
        ]
        panel.canvas.select_component(0)
        panel.property_editor.set_component(panel.canvas.selected_component_details())
        self.assertEqual(panel.property_editor.name_value.text(), "Capacitor")
        self.assertEqual(panel.property_editor.domain_value.text(), "electrical")
        self.assertEqual(panel.property_editor.category_value.text(), "rigid")
        self.assertEqual(panel.property_editor.boundary_value.text(), "internal")
        self.assertEqual(panel.property_editor.motion_value.text(), "static")
        self.assertEqual(panel.property_editor.port_value.text(), "2")

    def test_property_panel_shows_inductor_as_internal_static_electrical_component(self):
        panel = ModelPanel()
        panel.canvas._components = [
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Inductor"),
                component_id="inductor_1",
                position=QPointF(200.0, 320.0),
                size=(120.0, 56.0),
                deletable=True,
            ),
        ]
        panel.canvas.select_component(0)
        panel.property_editor.set_component(panel.canvas.selected_component_details())
        self.assertEqual(panel.property_editor.name_value.text(), "Inductor")
        self.assertEqual(panel.property_editor.domain_value.text(), "electrical")
        self.assertEqual(panel.property_editor.category_value.text(), "rigid")
        self.assertEqual(panel.property_editor.boundary_value.text(), "internal")
        self.assertEqual(panel.property_editor.motion_value.text(), "static")
        self.assertEqual(panel.property_editor.port_value.text(), "2")

    def test_property_panel_shows_diode_as_internal_static_directional_electrical_component(self):
        panel = ModelPanel()
        panel.canvas._components = [
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Diode"),
                component_id="diode_1",
                position=QPointF(200.0, 320.0),
                size=(120.0, 56.0),
                deletable=True,
            ),
        ]
        panel.canvas.select_component(0)
        panel.property_editor.set_component(panel.canvas.selected_component_details())
        self.assertEqual(panel.property_editor.name_value.text(), "Diode")
        self.assertEqual(panel.property_editor.domain_value.text(), "electrical")
        self.assertEqual(panel.property_editor.category_value.text(), "rigid")
        self.assertEqual(panel.property_editor.boundary_value.text(), "internal")
        self.assertEqual(panel.property_editor.motion_value.text(), "static")
        self.assertEqual(panel.property_editor.directional_value.text(), "True")
        self.assertEqual(panel.property_editor.port_value.text(), "2")

    def test_property_panel_shows_dc_source_as_directional_source_component(self):
        panel = ModelPanel()
        panel.canvas._components = [
            CanvasVisualComponent(
                spec=component_spec_for_display_name("DC Voltage Source"),
                component_id="dc_source_1",
                position=QPointF(200.0, 320.0),
                size=(120.0, 72.0),
                deletable=True,
            ),
        ]
        panel.canvas.select_component(0)
        panel.property_editor.set_component(panel.canvas.selected_component_details())
        self.assertEqual(panel.property_editor.name_value.text(), "DC Voltage Source")
        self.assertEqual(panel.property_editor.domain_value.text(), "electrical")
        self.assertEqual(panel.property_editor.category_value.text(), "rigid")
        self.assertEqual(panel.property_editor.boundary_value.text(), "internal")
        self.assertEqual(panel.property_editor.motion_value.text(), "static")
        self.assertEqual(panel.property_editor.directional_value.text(), "True")
        self.assertEqual(panel.property_editor.source_value.text(), "True")
        self.assertEqual(panel.property_editor.source_type_value.text(), "dc")
        self.assertEqual(panel.property_editor.port_value.text(), "2")

    def test_property_panel_shows_ac_source_as_directional_source_component(self):
        panel = ModelPanel()
        panel.canvas._components = [
            CanvasVisualComponent(
                spec=component_spec_for_display_name("AC Voltage Source"),
                component_id="ac_source_1",
                position=QPointF(200.0, 320.0),
                size=(120.0, 72.0),
                deletable=True,
            ),
        ]
        panel.canvas.select_component(0)
        panel.property_editor.set_component(panel.canvas.selected_component_details())
        self.assertEqual(panel.property_editor.name_value.text(), "AC Voltage Source")
        self.assertEqual(panel.property_editor.domain_value.text(), "electrical")
        self.assertEqual(panel.property_editor.category_value.text(), "rigid")
        self.assertEqual(panel.property_editor.boundary_value.text(), "internal")
        self.assertEqual(panel.property_editor.motion_value.text(), "static")
        self.assertEqual(panel.property_editor.directional_value.text(), "True")
        self.assertEqual(panel.property_editor.source_value.text(), "True")
        self.assertEqual(panel.property_editor.source_type_value.text(), "ac")
        self.assertEqual(panel.property_editor.port_value.text(), "2")

    def test_delete_key_removes_selected_custom_component(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        canvas._components.append(
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Spring"),
                component_id="custom_spring_1",
                position=canvas._components[-1].position,
                size=(120.0, 60.0),
                deletable=True,
            )
        )
        canvas.select_component(len(canvas._components) - 1)
        before_count = len(canvas._components)
        event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier)
        canvas.keyPressEvent(event)
        self.assertEqual(len(canvas._components), before_count - 1)
        self.assertEqual(canvas.selected_component_details()["name"], "No selection")

    def test_context_menu_delete_action_deletes_custom_component(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        canvas._components.append(
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Damper"),
                component_id="custom_damper_1",
                position=canvas._components[-1].position,
                size=(120.0, 60.0),
                deletable=True,
            )
        )
        target_index = len(canvas._components) - 1
        menu = canvas.build_context_menu(target_index)
        delete_action = menu.actions()[0]
        self.assertTrue(delete_action.isEnabled())
        before_count = len(canvas._components)
        delete_action.trigger()
        self.assertEqual(len(canvas._components), before_count - 1)
        self.assertIn("Click a component to select it.", canvas.selected_component_details()["status_text"])

    def test_clicking_empty_canvas_clears_selection(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        canvas.select_component(0)
        canvas.clear_selection()
        details = canvas.selected_component_details()
        self.assertEqual(details["name"], "No selection")
        self.assertEqual(details["ports"], 0)

    def test_locked_template_component_cannot_be_deleted(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        canvas.select_component(1)
        before_count = len(canvas._components)
        deleted = canvas.delete_selected_component()
        self.assertFalse(deleted)
        self.assertEqual(len(canvas._components), before_count)
        self.assertIn("Delete unavailable", canvas.selected_component_details()["status_text"])

    def test_quarter_car_support_mode_uses_road_and_hides_ground_symbol(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("quarter_car")
        self.assertEqual(canvas.support_visual_mode(), "road")
        self.assertLess(canvas.wheel_display_scale(), 0.7)
        self.assertGreater(canvas.road_visual_smoothing(), 0.5)
        self.assertIn("Wheel", canvas.visible_component_names())
        self.assertIn("Mechanical Random Reference", canvas.visible_component_names())
        self.assertIn("Mechanical Translational Reference", canvas.visible_component_names())

    def test_single_mass_support_mode_uses_ground_and_hides_road(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("single_mass")
        self.assertEqual(canvas.support_visual_mode(), "ground")
        self.assertEqual(canvas.wheel_display_scale(), 1.0)
        self.assertEqual(canvas.road_visual_smoothing(), 0.0)
        self.assertIn("Mechanical Translational Reference", canvas.visible_component_names())
        self.assertNotIn("Wheel", canvas.visible_component_names())

    def test_two_mass_support_mode_uses_ground_and_hides_road(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("two_mass")
        self.assertEqual(canvas.support_visual_mode(), "ground")
        self.assertEqual(canvas.wheel_display_scale(), 1.0)
        self.assertEqual(canvas.road_visual_smoothing(), 0.0)
        self.assertIn("Mechanical Translational Reference", canvas.visible_component_names())
        self.assertNotIn("Wheel", canvas.visible_component_names())

    def test_quarter_car_disturbance_input_uses_real_component_with_static_road_profile_before_simulation(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        disturbance = next(component for component in canvas._components if component.spec.display_name == "Mechanical Random Reference")
        rect = canvas._dynamic_rect(disturbance)
        self.assertFalse(canvas._road_profile_is_animated())
        profile = [(round(point.x(), 3), round(point.y(), 3)) for point in canvas._renderer.road_profile_points(rect, phase=canvas._road_profile_phase())]
        self.assertGreater(len(profile), 6)
        self.assertEqual(profile, [(round(point.x(), 3), round(point.y(), 3)) for point in canvas._renderer.road_profile_points(rect, phase=canvas._road_profile_phase())])
        self.assertEqual(disturbance.spec.type_key, "mechanical_random_reference")

    def test_quarter_car_disturbance_input_animates_when_simulation_visualization_updates(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        disturbance = next(component for component in canvas._components if component.spec.display_name == "Mechanical Random Reference")
        rect = canvas._dynamic_rect(disturbance)
        idle = [(round(point.x(), 3), round(point.y(), 3)) for point in canvas._renderer.road_profile_points(rect, phase=canvas._road_profile_phase())]
        canvas.update_visualization(
            {
                "road_x": [0.2, 0.4, 0.6, 0.8],
                "road_y": [0.01, -0.015, 0.02, -0.01],
                "wheel_rotation": 0.7,
            }
        )
        self.assertTrue(canvas._road_profile_is_animated())
        animated = [(round(point.x(), 3), round(point.y(), 3)) for point in canvas._renderer.road_profile_points(rect, phase=canvas._road_profile_phase())]
        self.assertNotEqual(idle, animated)

    def test_user_built_quarter_car_like_scene_uses_mapper_for_deformables_and_road_owner(self):
        canvas = ModelCanvas()
        canvas._components = [
            CanvasVisualComponent(component_spec_for_display_name("Mechanical Random Reference"), "road_1", QPointF(120.0, 610.0), (130.0, 80.0), True),
            CanvasVisualComponent(component_spec_for_display_name("Mass"), "mass_1", QPointF(470.0, 110.0), (228.0, 108.0), True),
            CanvasVisualComponent(component_spec_for_display_name("Translational Damper"), "damper_1", QPointF(410.0, 265.0), (80.0, 142.0), True),
            CanvasVisualComponent(component_spec_for_display_name("Translational Spring"), "spring_1", QPointF(630.0, 260.0), (78.0, 148.0), True),
            CanvasVisualComponent(component_spec_for_display_name("Wheel"), "wheel_1", QPointF(470.0, 470.0), (230.0, 230.0), True),
            CanvasVisualComponent(component_spec_for_display_name("Tire Stiffness"), "tire_1", QPointF(515.0, 705.0), (130.0, 90.0), True),
        ]
        canvas._wires = [
            CanvasWireConnection("mass_1", "bottom", "damper_1", "R"),
            CanvasWireConnection("mass_1", "bottom", "spring_1", "R"),
            CanvasWireConnection("damper_1", "C", "wheel_1", "top"),
            CanvasWireConnection("spring_1", "C", "wheel_1", "top"),
            CanvasWireConnection("wheel_1", "bottom", "tire_1", "R"),
            CanvasWireConnection("road_1", "output", "tire_1", "C"),
        ]
        canvas.update_visualization(
            {
                "template_id": "blank",
                "runtime_outputs": {
                    "body_displacement": 0.01,
                    "wheel_displacement": 0.024,
                },
                "road_x": [0.2, 0.4, 0.6, 0.8],
                "road_y": [0.01, -0.015, 0.02, -0.01],
                "wheel_rotation": 0.7,
            }
        )
        self.assertEqual(canvas.workspace_template_hint(), "quarter_car")
        self.assertIsNotNone(canvas._scene_animation_result)
        self.assertIn("spring_1", canvas._scene_animation_result.component_overrides)
        self.assertIn("damper_1", canvas._scene_animation_result.component_overrides)
        self.assertEqual(canvas.road_render_snapshot()["road_owner_component_id"], "road_1")

    def test_scene_animation_mapper_returns_structured_component_overrides(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        mapper = SceneAnimationMapper()
        result = mapper.map(
            SceneAnimationContext(
                template_id="quarter_car",
                components=tuple(canvas._components),
                wires=tuple(canvas._wires),
                animation={
                    "runtime_outputs": {
                        "body_displacement": 0.01,
                        "wheel_displacement": 0.02,
                    }
                },
            )
        )
        self.assertIsInstance(result.component_overrides.get("body_mass"), ComponentVisualOverride)
        self.assertIsInstance(result.component_overrides.get("suspension_spring"), ComponentVisualOverride)
        self.assertEqual(result.road_owner_component_id, "road_source")

    def test_quarter_car_tire_visual_stays_visible_before_simulation_and_hides_during_active_road_playback(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        tire = next(component for component in canvas._components if component.spec.type_key == "tire_stiffness")
        self.assertTrue(canvas._component_visible_in_current_visual_mode(tire))
        self.assertEqual(len(canvas.persistent_wires()), 8)

        canvas.update_visualization(
            {
                "road_x": [0.2, 0.4, 0.6, 0.8],
                "road_y": [0.015, -0.01, 0.02, -0.012],
                "road_height": 0.01,
                "wheel_rotation": 0.4,
            }
        )
        self.assertFalse(canvas._component_visible_in_current_visual_mode(tire))
        hidden_wires = [
            wire
            for wire in canvas.persistent_wires()
            if not canvas._wire_visible_in_current_visual_mode(wire)
        ]
        self.assertEqual(len(hidden_wires), 2)

    def test_quarter_car_active_road_surface_tracks_wheel_contact_during_simulation(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        canvas.update_visualization(
            {
                "wheel_displacement": 0.012,
                "road_height": 0.008,
                "road_x": [0.2, 0.4, 0.6, 0.8, 1.0],
                "road_y": [0.008, 0.012, -0.006, 0.015, -0.004],
                "wheel_rotation": 0.9,
            }
        )
        snapshot = canvas.road_render_snapshot()
        self.assertTrue(snapshot["active"])
        self.assertIsNotNone(snapshot["contact_gap"])
        self.assertLessEqual(snapshot["contact_gap"], 45.0)

    def test_quarter_car_body_mass_moves_with_body_displacement_during_simulation(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        body_mass = next(component for component in canvas._components if component.component_id == "body_mass")
        base_rect = canvas._dynamic_rect(body_mass)
        canvas.update_visualization({"body_displacement": 0.012})
        moved_rect = canvas._dynamic_rect(body_mass)
        self.assertGreater(moved_rect.y(), base_rect.y())

    def test_quarter_car_simulation_preserves_rest_layout_spacing(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        body_mass = next(component for component in canvas._components if component.component_id == "body_mass")
        wheel = next(component for component in canvas._components if component.component_id == "wheel_mass")
        spring = next(component for component in canvas._components if component.component_id == "suspension_spring")
        base_mass_rect = canvas._dynamic_rect(body_mass)
        base_wheel_rect = canvas._dynamic_rect(wheel)
        base_gap = base_wheel_rect.top() - base_mass_rect.bottom()

        canvas.update_visualization(
            {
                "template_id": "quarter_car",
                "runtime_outputs": {
                    "body_displacement": 0.008,
                    "wheel_displacement": 0.02,
                },
            }
        )
        moved_mass_rect = canvas._dynamic_rect(body_mass)
        moved_wheel_rect = canvas._dynamic_rect(wheel)
        moved_gap = moved_wheel_rect.top() - moved_mass_rect.bottom()
        spring_rect = canvas._dynamic_rect(spring)

        self.assertGreater(moved_gap, 40.0)
        self.assertNotAlmostEqual(moved_gap, 0.0, delta=1.0)
        self.assertLess(abs(moved_gap - base_gap), 80.0)
        self.assertAlmostEqual(spring_rect.center().x(), spring.position.x() + spring.size[0] / 2.0, delta=20.0)

    def test_active_road_surface_does_not_vertically_shift_with_suspension_motion(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        payload = {
            "road_x": [0.2, 0.4, 0.6, 0.8, 1.0],
            "road_y": [0.008, 0.012, -0.006, 0.015, -0.004],
            "wheel_rotation": 0.9,
        }
        canvas.update_visualization(payload | {"wheel_displacement": 0.0, "body_displacement": 0.0})
        first = [(round(point.x(), 3), round(point.y(), 3)) for point in canvas.road_render_snapshot()["points"]]
        canvas.update_visualization(payload | {"wheel_displacement": 0.02, "body_displacement": -0.01})
        second = [(round(point.x(), 3), round(point.y(), 3)) for point in canvas.road_render_snapshot()["points"]]
        self.assertEqual(first, second)

    def test_ctrl_r_rotates_selected_component_clockwise(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("single_mass")
        canvas.select_component(2)
        event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_R, Qt.ControlModifier)
        canvas.keyPressEvent(event)
        self.assertIn(90, canvas.component_orientations())

    def test_mass_connector_hit_testing_survives_svg_integration_and_simulation_translation(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        mass = canvas._components[1]
        self.assertEqual(mass.spec.display_name, "Mass")
        self.assertTrue(mass.has_svg_symbol())

        base_rect = canvas._dynamic_rect(mass)
        top_port = mass.connector_centers(base_rect)[0]
        bottom_port = mass.connector_centers(base_rect)[1]
        self.assertEqual(mass.connector_hit_test(base_rect, top_port).name, "top")
        self.assertEqual(mass.connector_hit_test(base_rect, bottom_port).name, "bottom")
        self.assertLess(top_port.y(), base_rect.top())
        self.assertGreater(bottom_port.y(), base_rect.bottom())

        canvas.update_visualization({"body_displacement": 0.01})
        translated_rect = canvas._dynamic_rect(mass)
        translated_top = mass.connector_centers(translated_rect)[0]
        translated_bottom = mass.connector_centers(translated_rect)[1]
        self.assertEqual(mass.connector_hit_test(translated_rect, translated_top).name, "top")
        self.assertEqual(mass.connector_hit_test(translated_rect, translated_bottom).name, "bottom")

        mass.rotate_clockwise()
        rotated_rect = canvas._dynamic_rect(mass)
        rotated_ports = mass.connector_centers(rotated_rect)
        self.assertEqual(mass.connector_hit_test(rotated_rect, rotated_ports[0]).name, "top")
        self.assertEqual(mass.connector_hit_test(rotated_rect, rotated_ports[1]).name, "bottom")

    def test_single_mass_simulation_animates_in_place_without_geometry_collapse(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("single_mass")
        mass = next(component for component in canvas._components if component.component_id == "mass")
        spring = next(component for component in canvas._components if component.component_id == "spring")
        damper = next(component for component in canvas._components if component.component_id == "damper")
        ground = next(component for component in canvas._components if component.component_id == "ground")

        base_mass_rect = canvas._dynamic_rect(mass)
        base_spring_rect = canvas._dynamic_rect(spring)
        base_damper_rect = canvas._dynamic_rect(damper)
        ground_rect = canvas._dynamic_rect(ground)

        canvas.update_visualization(
            {
                "template_id": "single_mass",
                "runtime_outputs": {
                    "mass_displacement": 0.014,
                    "body_displacement": 0.014,
                },
            }
        )
        moved_mass_rect = canvas._dynamic_rect(mass)
        moved_spring_rect = canvas._dynamic_rect(spring)
        moved_damper_rect = canvas._dynamic_rect(damper)

        self.assertGreater(moved_mass_rect.y(), base_mass_rect.y())
        self.assertGreater(moved_spring_rect.height(), 40.0)
        self.assertGreater(moved_damper_rect.height(), 40.0)
        self.assertFalse(moved_spring_rect.intersects(moved_mass_rect))
        self.assertFalse(moved_damper_rect.intersects(moved_mass_rect))
        self.assertGreater(ground_rect.top() - moved_spring_rect.bottom(), -25.0)
        self.assertAlmostEqual(moved_spring_rect.left(), base_spring_rect.left(), delta=20.0)
        self.assertAlmostEqual(moved_damper_rect.left(), base_damper_rect.left(), delta=20.0)

    def test_two_mass_simulation_moves_both_masses_without_stacking(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("two_mass")
        mass_1 = next(component for component in canvas._components if component.component_id == "mass_1")
        mass_2 = next(component for component in canvas._components if component.component_id == "mass_2")
        coupling_spring = next(component for component in canvas._components if component.component_id == "spring_coupling")

        base_mass_1 = canvas._dynamic_rect(mass_1)
        base_mass_2 = canvas._dynamic_rect(mass_2)

        canvas.update_visualization(
            {
                "template_id": "two_mass",
                "runtime_outputs": {
                    "mass_1_displacement": 0.008,
                    "mass_2_displacement": 0.022,
                    "body_displacement": 0.008,
                    "wheel_displacement": 0.022,
                },
            }
        )
        moved_mass_1 = canvas._dynamic_rect(mass_1)
        moved_mass_2 = canvas._dynamic_rect(mass_2)
        moved_coupling = canvas._dynamic_rect(coupling_spring)

        self.assertGreater(moved_mass_1.y(), base_mass_1.y())
        self.assertGreater(moved_mass_2.y(), base_mass_2.y())
        self.assertGreater(moved_mass_2.top() - moved_mass_1.bottom(), 40.0)
        self.assertGreater(moved_coupling.height(), 40.0)

    def test_single_mass_large_runtime_displacement_is_clamped_before_ground_overlap(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("single_mass")
        mass = next(component for component in canvas._components if component.component_id == "mass")
        ground = next(component for component in canvas._components if component.component_id == "ground")

        canvas.update_visualization(
            {
                "template_id": "single_mass",
                "runtime_outputs": {
                    "mass_displacement": 0.5,
                    "body_displacement": 0.5,
                },
            }
        )
        moved_mass_rect = canvas._dynamic_rect(mass)
        ground_rect = canvas._dynamic_rect(ground)
        self.assertLess(moved_mass_rect.bottom(), ground_rect.top())
        self.assertGreaterEqual(ground_rect.top() - moved_mass_rect.bottom(), 20.0)

    def test_two_mass_large_runtime_displacements_keep_rigid_bodies_separated(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("two_mass")
        mass_1 = next(component for component in canvas._components if component.component_id == "mass_1")
        mass_2 = next(component for component in canvas._components if component.component_id == "mass_2")
        ground = next(component for component in canvas._components if component.component_id == "ground")

        canvas.update_visualization(
            {
                "template_id": "two_mass",
                "runtime_outputs": {
                    "mass_1_displacement": 0.18,
                    "mass_2_displacement": 0.22,
                    "body_displacement": 0.18,
                    "wheel_displacement": 0.22,
                },
            }
        )
        moved_mass_1 = canvas._dynamic_rect(mass_1)
        moved_mass_2 = canvas._dynamic_rect(mass_2)
        ground_rect = canvas._dynamic_rect(ground)
        self.assertLess(moved_mass_1.bottom(), moved_mass_2.top())
        self.assertLess(moved_mass_2.bottom(), ground_rect.top())
        self.assertGreaterEqual(moved_mass_2.top() - moved_mass_1.bottom(), 20.0)
        self.assertGreaterEqual(ground_rect.top() - moved_mass_2.bottom(), 20.0)

    def test_new_svg_components_can_be_placed_with_valid_connector_geometry(self):
        canvas = ModelCanvas()
        canvas._components = [
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Ideal Force Source"),
                component_id="force_source_1",
                position=QPointF(120.0, 120.0),
                size=(110.0, 150.0),
                deletable=True,
            ),
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Switch"),
                component_id="switch_1",
                position=QPointF(320.0, 120.0),
                size=(120.0, 56.0),
                deletable=True,
            ),
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Electrical Reference"),
                component_id="eref_1",
                position=QPointF(520.0, 120.0),
                size=(72.0, 72.0),
                deletable=True,
            ),
        ]
        for component in canvas._components:
            rect = canvas._dynamic_rect(component)
            ports = component.connector_centers(rect)
            self.assertEqual(len(ports), len(component.spec.connector_ports))
            self.assertTrue(component.has_svg_symbol())

    def test_drop_instantiates_component_with_authoritative_base_size(self):
        canvas = ModelCanvas()
        dropped = canvas._instantiate_drop_component("Mass", 2, QPointF(300.0, 240.0))
        self.assertEqual(dropped.size, dropped.spec.presentation.preferred_size)
        self.assertAlmostEqual(dropped.base_rect().center().x(), 300.0, delta=0.01)
        self.assertAlmostEqual(dropped.base_rect().center().y(), 240.0, delta=0.01)

    def test_symbol_rect_is_stable_between_initial_drop_and_repaint(self):
        canvas = ModelCanvas()
        component = canvas._instantiate_drop_component("Resistor", 2, QPointF(280.0, 200.0))
        rect = component.base_rect()
        first = canvas._renderer.symbol_render_rect(component, rect)
        second = canvas._renderer.symbol_render_rect(component, rect)
        self.assertEqual(first, second)

    def test_mechanical_passive_components_use_consistent_normalized_fill_ratios(self):
        canvas = ModelCanvas()
        components = [
            canvas._instantiate_drop_component("Mass", 2, QPointF(200.0, 180.0)),
            canvas._instantiate_drop_component("Translational Spring", 2, QPointF(420.0, 240.0)),
            canvas._instantiate_drop_component("Translational Damper", 2, QPointF(620.0, 240.0)),
        ]
        fill_ratios = [component.spec.svg_symbol.fill_ratio for component in components]
        self.assertAlmostEqual(fill_ratios[0], fill_ratios[1], delta=0.001)
        self.assertAlmostEqual(fill_ratios[1], fill_ratios[2], delta=0.001)

    def test_pilot_set_symbol_rects_are_stable_on_first_placement(self):
        canvas = ModelCanvas()
        components = [
            canvas._instantiate_drop_component("Mass", 2, QPointF(200.0, 180.0)),
            canvas._instantiate_drop_component("Translational Spring", 2, QPointF(420.0, 240.0)),
            canvas._instantiate_drop_component("Translational Damper", 2, QPointF(620.0, 240.0)),
        ]
        for component in components:
            rect = component.base_rect()
            first = canvas._renderer.symbol_render_rect(component, rect)
            second = canvas._renderer.symbol_render_rect(component, rect)
            self.assertEqual(first, second)

    def test_connector_debug_snapshot_exposes_mass_top_bottom_anchors(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        canvas.set_connector_debug_visible(True)
        self.assertTrue(canvas.connector_debug_visible())

        snapshot = canvas.connector_debug_snapshot(1)
        self.assertEqual(len(snapshot), 1)
        debug_ports = snapshot[0]["debug_ports"]
        self.assertEqual([port["name"] for port in debug_ports], ["top", "bottom"])
        self.assertAlmostEqual(debug_ports[0]["center"].x(), canvas._dynamic_rect(canvas._components[1]).center().x(), delta=0.01)

    def test_clicking_connector_starts_preview_wire_and_mouse_move_updates_endpoint(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        mass = canvas._components[1]
        start = mass.connector_centers(canvas._dynamic_rect(mass))[0]
        self._left_click(canvas, start)
        self.assertTrue(canvas.wire_preview_active())
        preview = canvas.wire_preview_snapshot()
        self.assertEqual(preview["source_component_id"], "body_mass")
        self.assertEqual(preview["source_connector_name"], "top")

        new_cursor = QPointF(start.x() + 120.0, start.y() + 40.0)
        self._move_mouse(canvas, new_cursor)
        moved_preview = canvas.wire_preview_snapshot()
        self.assertAlmostEqual(moved_preview["current_scene_pos"].x(), new_cursor.x(), delta=1.0)
        self.assertAlmostEqual(moved_preview["current_scene_pos"].y(), new_cursor.y(), delta=1.0)

    def test_hovering_valid_second_connector_activates_highlight(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("two_mass")
        source_mass = canvas._components[1]
        target_mass = canvas._components[2]
        source_port = source_mass.connector_centers(canvas._dynamic_rect(source_mass))[1]
        target_port = target_mass.connector_centers(canvas._dynamic_rect(target_mass))[0]

        self._left_click(canvas, source_port)
        self._move_mouse(canvas, target_port)

        hovered = canvas.hovered_target_connector_snapshot()
        self.assertEqual(hovered["component_id"], "mass_2")
        self.assertEqual(hovered["connector_name"], "top")

    def test_moving_away_from_connector_removes_hover_highlight(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("two_mass")
        source_mass = canvas._components[1]
        target_mass = canvas._components[2]
        source_port = source_mass.connector_centers(canvas._dynamic_rect(source_mass))[1]
        target_port = target_mass.connector_centers(canvas._dynamic_rect(target_mass))[0]

        self._left_click(canvas, source_port)
        self._move_mouse(canvas, target_port)
        self.assertIsNotNone(canvas.hovered_target_connector_snapshot())

        self._move_mouse(canvas, QPointF(50.0, 50.0))
        self.assertIsNone(canvas.hovered_target_connector_snapshot())

    def test_invalid_targets_do_not_highlight_during_wiring(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        mass = canvas._components[1]
        start = mass.connector_centers(canvas._dynamic_rect(mass))[0]
        other_same_component = mass.connector_centers(canvas._dynamic_rect(mass))[1]

        self._left_click(canvas, start)
        self._move_mouse(canvas, other_same_component)
        self.assertIsNone(canvas.hovered_target_connector_snapshot())

        self._move_mouse(canvas, QPointF(40.0, 40.0))
        self.assertIsNone(canvas.hovered_target_connector_snapshot())

    def test_clicking_second_connector_creates_persistent_wire(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("two_mass")
        baseline = len(canvas.persistent_wires())
        source_mass = canvas._components[1]
        target_mass = canvas._components[2]
        source_port = source_mass.connector_centers(canvas._dynamic_rect(source_mass))[1]
        target_port = target_mass.connector_centers(canvas._dynamic_rect(target_mass))[0]
        canvas.select_component(1)

        self._left_click(canvas, source_port)
        self._left_click(canvas, target_port)

        self.assertFalse(canvas.wire_preview_active())
        wires = canvas.persistent_wires()
        self.assertEqual(len(wires), baseline + 1)
        self.assertEqual(wires[-1].source_component_id, "mass_1")
        self.assertEqual(wires[-1].source_connector_name, "bottom")
        self.assertEqual(wires[-1].target_component_id, "mass_2")
        self.assertEqual(wires[-1].target_connector_name, "top")
        self.assertEqual(canvas.selected_component_details()["component_id"], "mass_1")
        self.assertIsNone(canvas.selected_wire_snapshot())

    def test_wire_snaps_to_rotated_mass_connector_centers(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("two_mass")
        baseline = len(canvas.persistent_wires())
        source_mass = canvas._components[1]
        target_mass = canvas._components[2]
        target_mass.rotate_clockwise()

        source_port = source_mass.connector_centers(canvas._dynamic_rect(source_mass))[1]
        target_port = target_mass.connector_centers(canvas._dynamic_rect(target_mass))[0]

        self._left_click(canvas, source_port)
        self._left_click(canvas, target_port)

        wire = canvas.persistent_wires()[baseline]
        endpoints = canvas._wire_endpoints(wire)
        self.assertAlmostEqual(endpoints[0].x(), source_port.x(), delta=0.01)
        self.assertAlmostEqual(endpoints[0].y(), source_port.y(), delta=0.01)
        self.assertAlmostEqual(endpoints[1].x(), target_port.x(), delta=0.01)
        self.assertAlmostEqual(endpoints[1].y(), target_port.y(), delta=0.01)

    def test_clicking_near_wire_selects_it(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("two_mass")
        baseline = len(canvas.persistent_wires())
        source_mass = canvas._components[1]
        target_mass = canvas._components[2]
        source_port = source_mass.connector_centers(canvas._dynamic_rect(source_mass))[1]
        target_port = target_mass.connector_centers(canvas._dynamic_rect(target_mass))[0]
        self._left_click(canvas, source_port)
        self._left_click(canvas, target_port)

        midpoint = QPointF((source_port.x() + target_port.x()) / 2.0, (source_port.y() + target_port.y()) / 2.0)
        self._left_click(canvas, midpoint)

        selected = canvas.selected_wire_snapshot()
        self.assertIsNotNone(selected)
        self.assertEqual(selected["index"], baseline)
        self.assertEqual(canvas.selected_component_details()["name"], "Wire")

    def test_clicking_empty_canvas_clears_wire_selection(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("two_mass")
        source_mass = canvas._components[1]
        target_mass = canvas._components[2]
        source_port = source_mass.connector_centers(canvas._dynamic_rect(source_mass))[1]
        target_port = target_mass.connector_centers(canvas._dynamic_rect(target_mass))[0]
        self._left_click(canvas, source_port)
        self._left_click(canvas, target_port)
        midpoint = QPointF((source_port.x() + target_port.x()) / 2.0, (source_port.y() + target_port.y()) / 2.0)
        self._left_click(canvas, midpoint)
        self.assertIsNotNone(canvas.selected_wire_snapshot())

        self._left_click(canvas, QPointF(40.0, 40.0))
        self.assertIsNone(canvas.selected_wire_snapshot())

    def test_clicking_component_clears_wire_selection(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("two_mass")
        source_mass = canvas._components[1]
        target_mass = canvas._components[2]
        source_port = source_mass.connector_centers(canvas._dynamic_rect(source_mass))[1]
        target_port = target_mass.connector_centers(canvas._dynamic_rect(target_mass))[0]
        self._left_click(canvas, source_port)
        self._left_click(canvas, target_port)
        midpoint = QPointF((source_port.x() + target_port.x()) / 2.0, (source_port.y() + target_port.y()) / 2.0)
        self._left_click(canvas, midpoint)

        component_center = canvas._dynamic_rect(source_mass).center()
        self._left_click(canvas, component_center)
        self.assertIsNone(canvas.selected_wire_snapshot())
        self.assertEqual(canvas.selected_component_details()["component_id"], "mass_1")

    def test_context_menu_shows_only_valid_io_actions_for_mass(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        canvas.select_component(1)
        menu = canvas.build_context_menu(1)
        action_texts = [action.text() for action in menu.actions()]
        self.assertIn("Mark as Output", action_texts)
        self.assertNotIn("Mark as Input", action_texts)

    def test_context_menu_shows_both_io_actions_for_wheel_when_supported(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        canvas.select_component(4)
        menu = canvas.build_context_menu(4)
        action_texts = [action.text() for action in menu.actions()]
        self.assertIn("Mark as Input", action_texts)
        self.assertIn("Mark as Output", action_texts)
        self.assertNotIn("Clear Input Role", action_texts)
        self.assertNotIn("Clear Output Role", action_texts)

    def test_context_menu_shows_output_for_quarter_car_spring_via_derived_signal_binding(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        canvas.select_component(3)
        menu = canvas.build_context_menu(3)
        action_texts = [action.text() for action in menu.actions()]
        self.assertIn("Mark as Output", action_texts)
        self.assertNotIn("Mark as Input", action_texts)

    def test_context_menu_hides_output_for_quarter_car_damper_when_no_supported_derived_signal_exists(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        canvas.select_component(2)
        menu = canvas.build_context_menu(2)
        action_texts = [action.text() for action in menu.actions()]
        self.assertNotIn("Mark as Output", action_texts)

    def test_context_menu_switches_to_clear_actions_for_assigned_roles(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        canvas.select_component(4)
        self.assertTrue(canvas.assign_selected_component_io_role(ComponentIoRole.INPUT))
        self.assertTrue(canvas.assign_selected_component_io_role(ComponentIoRole.OUTPUT))
        menu = canvas.build_context_menu(4)
        action_texts = [action.text() for action in menu.actions()]
        self.assertIn("Clear Input Role", action_texts)
        self.assertIn("Clear Output Role", action_texts)
        self.assertNotIn("Mark as Input", action_texts)
        self.assertNotIn("Mark as Output", action_texts)

    def test_context_menu_shows_only_valid_io_actions_for_mechanical_random_reference(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        canvas.select_component(0)
        menu = canvas.build_context_menu(0)
        action_texts = [action.text() for action in menu.actions()]
        self.assertIn("Mark as Input", action_texts)
        self.assertNotIn("Mark as Output", action_texts)

    def test_context_menu_hides_input_action_when_template_has_no_input_binding_for_component(self):
        canvas = ModelCanvas()
        canvas.clear_workspace()
        canvas._components = [
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Mechanical Random Reference"),
                component_id="road_1",
                position=QPointF(120.0, 120.0),
                size=(130.0, 80.0),
                deletable=True,
            )
        ]
        canvas.select_component(0)
        menu = canvas.build_context_menu(0)
        action_texts = [action.text() for action in menu.actions()]
        self.assertNotIn("Mark as Input", action_texts)

    def test_context_menu_shows_no_io_actions_for_mechanical_reference(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("single_mass")
        canvas.select_component(4)
        menu = canvas.build_context_menu(4)
        action_texts = [action.text() for action in menu.actions()]
        self.assertNotIn("Mark as Input", action_texts)
        self.assertNotIn("Mark as Output", action_texts)

    def test_mark_as_input_assigns_role(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        canvas.select_component(0)
        self.assertTrue(canvas.assign_selected_component_io_role(ComponentIoRole.INPUT))
        self.assertTrue(canvas._components[0].has_io_role(ComponentIoRole.INPUT))
        self.assertEqual(canvas._io_marker_label(canvas._components[0], ComponentIoRole.INPUT), "u1")
        self.assertEqual(canvas.scene_signal_roles_snapshot()["inputs"][0]["signal_id"], "road")
        layout = canvas.io_marker_layout_snapshot()
        self.assertEqual(layout[0]["role"], "input")
        self.assertEqual(layout[0]["color"], "#0b84f3")

    def test_multiple_inputs_may_coexist(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        force_source = CanvasVisualComponent(
            spec=component_spec_for_display_name("Ideal Force Source"),
            component_id="force_source_1",
            position=QPointF(780.0, 140.0),
            size=(110.0, 150.0),
            deletable=True,
        )
        canvas._components.append(force_source)
        canvas.select_component(0)
        self.assertTrue(canvas.assign_selected_component_io_role(ComponentIoRole.INPUT))
        canvas.select_component(len(canvas._components) - 1)
        self.assertTrue(canvas.assign_selected_component_io_role(ComponentIoRole.INPUT))
        self.assertTrue(canvas._components[0].has_io_role(ComponentIoRole.INPUT))
        self.assertTrue(canvas._components[-1].has_io_role(ComponentIoRole.INPUT))
        self.assertEqual([item["signal_id"] for item in canvas.scene_signal_roles_snapshot()["inputs"]], ["road", "body_force"])

    def test_mark_as_output_assigns_role(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        canvas.select_component(1)
        self.assertTrue(canvas.assign_selected_component_io_role(ComponentIoRole.OUTPUT))
        self.assertTrue(canvas._components[1].has_io_role(ComponentIoRole.OUTPUT))
        self.assertEqual(canvas._io_marker_label(canvas._components[1], ComponentIoRole.OUTPUT), "z1")
        self.assertEqual(canvas.scene_signal_roles_snapshot()["outputs"][0]["signal_id"], "body_displacement")
        layout = canvas.io_marker_layout_snapshot()
        self.assertEqual(layout[0]["role"], "output")
        self.assertEqual(layout[0]["color"], "#d94841")

    def test_marking_quarter_car_spring_as_output_maps_to_suspension_deflection(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        canvas.select_component(3)
        self.assertTrue(canvas.assign_selected_component_io_role(ComponentIoRole.OUTPUT))
        outputs = canvas.scene_signal_roles_snapshot()["outputs"]
        self.assertEqual(outputs[0]["component_id"], "suspension_spring")
        self.assertEqual(outputs[0]["signal_id"], "suspension_deflection")

    def test_component_can_hold_both_input_and_output_roles_when_supported(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        canvas.select_component(4)
        self.assertTrue(canvas.assign_selected_component_io_role(ComponentIoRole.INPUT))
        self.assertTrue(canvas.assign_selected_component_io_role(ComponentIoRole.OUTPUT))
        self.assertTrue(canvas._components[4].has_io_role(ComponentIoRole.INPUT))
        self.assertTrue(canvas._components[4].has_io_role(ComponentIoRole.OUTPUT))
        layout = canvas.io_marker_layout_snapshot()
        wheel_markers = [item for item in layout if item["component_id"] == "wheel_mass"]
        self.assertEqual({item["role"] for item in wheel_markers}, {"input", "output"})

    def test_two_mass_output_mapping_resolves_both_mass_signals(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("two_mass")
        canvas.select_component(1)
        self.assertTrue(canvas.assign_selected_component_io_role(ComponentIoRole.OUTPUT))
        canvas.select_component(2)
        self.assertTrue(canvas.assign_selected_component_io_role(ComponentIoRole.OUTPUT))
        outputs = canvas.scene_signal_roles_snapshot()["outputs"]
        self.assertEqual([item["signal_id"] for item in outputs], ["mass_1_displacement", "mass_2_displacement"])

    def test_clear_io_role_removes_marker_assignment(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        canvas.select_component(1)
        canvas.assign_selected_component_io_role(ComponentIoRole.OUTPUT)
        self.assertTrue(canvas.clear_selected_component_io_role(ComponentIoRole.OUTPUT))
        self.assertFalse(canvas._components[1].assigned_io_roles)
        self.assertEqual(canvas._io_marker_label(canvas._components[1], ComponentIoRole.OUTPUT), "")

    def test_clearing_output_role_updates_scene_snapshot(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        canvas.select_component(1)
        self.assertTrue(canvas.assign_selected_component_io_role(ComponentIoRole.OUTPUT))
        self.assertEqual(len(canvas.scene_signal_roles_snapshot()["outputs"]), 1)
        self.assertTrue(canvas.clear_selected_component_io_role(ComponentIoRole.OUTPUT))
        self.assertEqual(canvas.scene_signal_roles_snapshot()["outputs"], [])

    def test_io_numbering_updates_dynamically(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("two_mass")
        canvas.select_component(1)
        canvas.assign_selected_component_io_role(ComponentIoRole.OUTPUT)
        canvas.select_component(2)
        canvas.assign_selected_component_io_role(ComponentIoRole.OUTPUT)
        self.assertEqual(canvas._io_marker_label(canvas._components[1], ComponentIoRole.OUTPUT), "z1")
        self.assertEqual(canvas._io_marker_label(canvas._components[2], ComponentIoRole.OUTPUT), "z2")
        canvas.select_component(1)
        canvas.assign_selected_component_io_role(None)
        self.assertEqual(canvas._io_marker_label(canvas._components[2], ComponentIoRole.OUTPUT), "z1")

    def test_invalid_role_assignment_is_rejected(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("single_mass")
        canvas.select_component(2)
        self.assertFalse(canvas.assign_selected_component_io_role(ComponentIoRole.INPUT))
        self.assertFalse(canvas._components[2].assigned_io_roles)

    def test_assigned_output_marker_is_not_forced_to_single_fixed_side(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("two_mass")
        canvas.select_component(1)
        canvas.assign_selected_component_io_role(ComponentIoRole.OUTPUT)
        layout = canvas.io_marker_layout_snapshot()
        self.assertEqual(len(layout), 1)
        self.assertIn(layout[0]["side"], {"top", "bottom"})

    def test_vertical_axis_output_prefers_top_or_bottom_when_clear(self):
        canvas = ModelCanvas()
        canvas._components = [
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Mass"),
                component_id="mass_a",
                position=QPointF(220.0, 180.0),
                size=(240.0, 90.0),
                deletable=True,
                assigned_io_roles=(ComponentIoRole.OUTPUT,),
            )
        ]
        layout = canvas.io_marker_layout_snapshot()
        self.assertEqual(len(layout), 1)
        self.assertIn(layout[0]["side"], {"top", "bottom"})

    def test_axis_aware_marker_falls_back_when_preferred_sides_are_blocked(self):
        canvas = ModelCanvas()
        canvas._components = [
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Mass"),
                component_id="mass_a",
                position=QPointF(240.0, 220.0),
                size=(240.0, 90.0),
                deletable=True,
                assigned_io_roles=(ComponentIoRole.OUTPUT,),
            ),
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Mass"),
                component_id="blocker_top",
                position=QPointF(240.0, 80.0),
                size=(240.0, 110.0),
                deletable=True,
            ),
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Mass"),
                component_id="blocker_bottom",
                position=QPointF(240.0, 335.0),
                size=(240.0, 110.0),
                deletable=True,
            ),
        ]
        layout = canvas.io_marker_layout_snapshot()
        self.assertEqual(len(layout), 1)
        self.assertIn(layout[0]["side"], {"left", "right"})

    def test_axis_aware_marker_layout_is_deterministic(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("two_mass")
        canvas.select_component(1)
        canvas.assign_selected_component_io_role(ComponentIoRole.OUTPUT)
        first = canvas.io_marker_layout_snapshot()
        second = canvas.io_marker_layout_snapshot()
        self.assertEqual(first[0]["side"], second[0]["side"])
        self.assertEqual(first[0]["bounds"], second[0]["bounds"])

    def test_io_marker_chooses_alternative_side_when_preferred_side_is_blocked(self):
        canvas = ModelCanvas()
        canvas._components = [
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Mass"),
                component_id="mass_a",
                position=QPointF(120.0, 120.0),
                size=(240.0, 90.0),
                deletable=True,
                assigned_io_roles=(ComponentIoRole.OUTPUT,),
            ),
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Mass"),
                component_id="blocker",
                position=QPointF(370.0, 120.0),
                size=(240.0, 90.0),
                deletable=True,
            ),
        ]
        layout = canvas.io_marker_layout_snapshot()
        self.assertEqual(layout[0]["component_id"], "mass_a")
        self.assertNotEqual(layout[0]["side"], "right")

    def test_io_markers_do_not_overlap_their_own_components(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("two_mass")
        canvas.select_component(1)
        canvas.assign_selected_component_io_role(ComponentIoRole.OUTPUT)
        canvas.select_component(2)
        canvas.assign_selected_component_io_role(ComponentIoRole.OUTPUT)
        layout = canvas.io_marker_layout_snapshot()
        component_rects = {component.component_id: canvas._dynamic_rect(component) for component in canvas._components}
        for marker in layout:
            self.assertFalse(marker["bounds"].intersects(component_rects[marker["component_id"]]))

    def test_multiple_nearby_markers_do_not_collapse_into_same_exact_placement(self):
        canvas = ModelCanvas()
        canvas._components = [
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Mass"),
                component_id="mass_1",
                position=QPointF(180.0, 140.0),
                size=(220.0, 90.0),
                deletable=True,
                assigned_io_roles=(ComponentIoRole.OUTPUT,),
            ),
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Mass"),
                component_id="mass_2",
                position=QPointF(410.0, 140.0),
                size=(220.0, 90.0),
                deletable=True,
                assigned_io_roles=(ComponentIoRole.OUTPUT,),
            ),
        ]
        layout = canvas.io_marker_layout_snapshot()
        self.assertEqual(len(layout), 2)
        self.assertNotEqual(layout[0]["bounds"], layout[1]["bounds"])

    def test_selected_component_exposes_four_resize_handles(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("single_mass")
        canvas.select_component(1)
        handles = canvas.selected_resize_handles_snapshot()
        self.assertEqual(len(handles), 4)
        self.assertEqual({handle["corner"] for handle in handles}, {"top_left", "top_right", "bottom_left", "bottom_right"})

    def test_dragging_resize_handle_changes_component_bounds(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("single_mass")
        canvas.select_component(1)
        before = canvas._component_rect(canvas._components[1])
        bottom_right = next(handle for handle in canvas.selected_resize_handles_snapshot() if handle["corner"] == "bottom_right")
        start = bottom_right["rect"].center()
        end = QPointF(start.x() + 60.0, start.y() + 40.0)
        self._left_click(canvas, start)
        self._drag_mouse(canvas, end)
        self._release_left(canvas, end)
        after = canvas._component_rect(canvas._components[1])
        self.assertGreater(after.width(), before.width())
        self.assertGreater(after.height(), before.height())

    def test_resize_updates_connector_geometry(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("single_mass")
        canvas.select_component(1)
        before_ports = canvas._components[1].connector_centers(canvas._dynamic_rect(canvas._components[1]))
        bottom_right = next(handle for handle in canvas.selected_resize_handles_snapshot() if handle["corner"] == "bottom_right")
        start = bottom_right["rect"].center()
        end = QPointF(start.x() + 80.0, start.y() + 50.0)
        self._left_click(canvas, start)
        self._drag_mouse(canvas, end)
        self._release_left(canvas, end)
        after_ports = canvas._components[1].connector_centers(canvas._dynamic_rect(canvas._components[1]))
        self.assertNotEqual((before_ports[0].x(), before_ports[0].y()), (after_ports[0].x(), after_ports[0].y()))
        self.assertNotEqual((before_ports[1].x(), before_ports[1].y()), (after_ports[1].x(), after_ports[1].y()))

    def test_resize_updates_mass_symbol_render_rect_from_current_bounds(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("single_mass")
        canvas.select_component(1)
        component = canvas._components[1]
        before_rect = canvas._dynamic_rect(component)
        before_symbol = canvas._renderer.symbol_render_rect(component, before_rect)
        bottom_right = next(handle for handle in canvas.selected_resize_handles_snapshot() if handle["corner"] == "bottom_right")
        start = bottom_right["rect"].center()
        end = QPointF(start.x() + 120.0, start.y() + 60.0)
        self._left_click(canvas, start)
        self._drag_mouse(canvas, end)
        self._release_left(canvas, end)
        after_rect = canvas._dynamic_rect(component)
        after_symbol = canvas._renderer.symbol_render_rect(component, after_rect)
        self.assertGreater(after_symbol.width(), before_symbol.width())
        self.assertGreater(after_symbol.height(), before_symbol.height())
        self.assertAlmostEqual(after_symbol.center().x(), after_rect.center().x(), delta=0.01)
        self.assertAlmostEqual(after_symbol.center().y(), after_rect.center().y(), delta=0.01)
        self.assertAlmostEqual(
            after_symbol.width() / after_symbol.height(),
            component.spec.preferred_symbol_aspect_ratio,
            delta=0.05,
        )
        self.assertGreater(after_symbol.height(), after_rect.height() * 0.55)

    def test_resize_keeps_mass_svg_centered_and_aspect_fit(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("single_mass")
        canvas.select_component(1)
        component = canvas._components[1]
        component.size = (380.0, 150.0)
        rect = canvas._dynamic_rect(component)
        symbol_rect = canvas._renderer.symbol_render_rect(component, rect)
        symbol_ratio = symbol_rect.width() / symbol_rect.height()
        expected_ratio = component.spec.preferred_symbol_aspect_ratio
        self.assertAlmostEqual(symbol_rect.center().x(), rect.center().x(), delta=0.01)
        self.assertAlmostEqual(symbol_rect.center().y(), rect.center().y(), delta=0.01)
        self.assertAlmostEqual(symbol_ratio, expected_ratio, delta=0.05)

    def test_selection_label_rect_remains_clear_of_resized_mass_symbol(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("single_mass")
        canvas.select_component(1)
        component = canvas._components[1]
        component.size = (360.0, 150.0)
        rect = canvas._dynamic_rect(component)
        symbol_rect = canvas._renderer.symbol_render_rect(component, rect)
        label_rect, _ = canvas._renderer.selection_label_rect(component, rect, "Mass")
        self.assertFalse(label_rect.intersects(symbol_rect))

    def test_resize_keeps_wire_endpoints_snapped_to_connector_centers(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("two_mass")
        baseline = len(canvas.persistent_wires())
        source_mass = canvas._components[1]
        target_mass = canvas._components[2]
        source_port = source_mass.connector_centers(canvas._dynamic_rect(source_mass))[1]
        target_port = target_mass.connector_centers(canvas._dynamic_rect(target_mass))[0]
        self._left_click(canvas, source_port)
        self._left_click(canvas, target_port)
        canvas.select_component(1)
        bottom_right = next(handle for handle in canvas.selected_resize_handles_snapshot() if handle["corner"] == "bottom_right")
        start = bottom_right["rect"].center()
        end = QPointF(start.x() + 70.0, start.y() + 35.0)
        self._left_click(canvas, start)
        self._drag_mouse(canvas, end)
        self._release_left(canvas, end)
        wire = canvas.persistent_wires()[baseline]
        endpoints = canvas._wire_endpoints(wire)
        moved_source = source_mass.connector_centers(canvas._dynamic_rect(source_mass))[1]
        moved_target = target_mass.connector_centers(canvas._dynamic_rect(target_mass))[0]
        self.assertAlmostEqual(endpoints[0].x(), moved_source.x(), delta=0.01)
        self.assertAlmostEqual(endpoints[0].y(), moved_source.y(), delta=0.01)
        self.assertAlmostEqual(endpoints[1].x(), moved_target.x(), delta=0.01)
        self.assertAlmostEqual(endpoints[1].y(), moved_target.y(), delta=0.01)

    def test_io_marker_layout_uses_updated_resized_geometry(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("single_mass")
        canvas.select_component(1)
        canvas.assign_selected_component_io_role(ComponentIoRole.OUTPUT)
        component = canvas._components[1]
        before_layout = canvas.io_marker_layout_snapshot()[0]
        bottom_right = next(handle for handle in canvas.selected_resize_handles_snapshot() if handle["corner"] == "bottom_right")
        start = bottom_right["rect"].center()
        end = QPointF(start.x() + 110.0, start.y() + 50.0)
        self._left_click(canvas, start)
        self._drag_mouse(canvas, end)
        self._release_left(canvas, end)
        after_layout = canvas.io_marker_layout_snapshot()[0]
        self.assertNotEqual(before_layout["bounds"], after_layout["bounds"])
        self.assertFalse(after_layout["bounds"].intersects(canvas._dynamic_rect(component)))

    def test_minimum_resize_constraints_are_enforced(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("single_mass")
        canvas.select_component(1)
        component = canvas._components[1]
        min_width, min_height = canvas._minimum_component_size(component)
        self.assertEqual((min_width, min_height), component.preferred_size())
        top_left = next(handle for handle in canvas.selected_resize_handles_snapshot() if handle["corner"] == "top_left")
        start = top_left["rect"].center()
        end = QPointF(start.x() + 500.0, start.y() + 300.0)
        self._left_click(canvas, start)
        self._drag_mouse(canvas, end)
        self._release_left(canvas, end)
        rect = canvas._component_rect(component)
        self.assertGreaterEqual(rect.width(), min_width)
        self.assertGreaterEqual(rect.height(), min_height)

    def test_svg_component_cannot_shrink_below_base_size_during_resize(self):
        canvas = ModelCanvas()
        canvas._components = [
            CanvasVisualComponent(
                spec=component_spec_for_display_name("Resistor"),
                component_id="resistor_1",
                position=QPointF(220.0, 180.0),
                size=(160.0, 72.0),
                deletable=True,
            )
        ]
        canvas.select_component(0)
        component = canvas._components[0]
        self.assertTrue(component.has_svg_symbol())
        top_left = next(handle for handle in canvas.selected_resize_handles_snapshot() if handle["corner"] == "top_left")
        start = top_left["rect"].center()
        end = QPointF(start.x() + 300.0, start.y() + 200.0)
        self._left_click(canvas, start)
        self._drag_mouse(canvas, end)
        self._release_left(canvas, end)
        rect = canvas._component_rect(component)
        self.assertEqual((rect.width(), rect.height()), component.preferred_size())

    def test_svg_minimum_resize_keeps_connector_and_label_geometry_valid(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("single_mass")
        canvas.select_component(1)
        component = canvas._components[1]
        top_left = next(handle for handle in canvas.selected_resize_handles_snapshot() if handle["corner"] == "top_left")
        start = top_left["rect"].center()
        end = QPointF(start.x() + 600.0, start.y() + 300.0)
        self._left_click(canvas, start)
        self._drag_mouse(canvas, end)
        self._release_left(canvas, end)
        rect = canvas._dynamic_rect(component)
        ports = component.connector_centers(rect)
        symbol_rect = canvas._renderer.symbol_render_rect(component, rect)
        label_rect, _ = canvas._renderer.selection_label_rect(component, rect, "Mass")
        self.assertEqual((rect.width(), rect.height()), component.preferred_size())
        self.assertEqual(len(ports), 2)
        self.assertFalse(label_rect.intersects(symbol_rect))
        self.assertAlmostEqual(symbol_rect.width() / symbol_rect.height(), component.spec.preferred_symbol_aspect_ratio, delta=0.05)

    def test_pilot_set_drop_uses_presentation_preferred_sizes(self):
        canvas = ModelCanvas()
        for display_name in ("Mass", "Translational Spring", "Translational Damper", "Resistor"):
            dropped = canvas._instantiate_drop_component(display_name, 2, QPointF(320.0, 240.0))
            self.assertEqual(dropped.size, dropped.preferred_size())

    def test_repeated_components_receive_sequential_instance_names(self):
        canvas = ModelCanvas()
        mass_1 = canvas._instantiate_drop_component("Mass", 2, QPointF(220.0, 220.0))
        canvas._components.append(mass_1)
        mass_2 = canvas._instantiate_drop_component("Mass", 2, QPointF(420.0, 220.0))
        canvas._components.append(mass_2)
        spring_1 = canvas._instantiate_drop_component("Translational Spring", 2, QPointF(620.0, 220.0))
        self.assertEqual(mass_1.instance_name, "Mass1")
        self.assertEqual(mass_2.instance_name, "Mass2")
        self.assertEqual(spring_1.instance_name, "Spring1")

    def test_duplicate_component_receives_next_instance_name(self):
        canvas = ModelCanvas()
        component = canvas._instantiate_drop_component("Mass", 2, QPointF(260.0, 220.0))
        canvas._components.append(component)
        canvas.select_component(0)
        self.assertTrue(canvas.duplicate_selected_component())
        self.assertEqual([item.instance_name for item in canvas._components], ["Mass1", "Mass2"])

    def test_resize_handles_follow_authored_bounds_after_mapper_override(self):
        canvas = ModelCanvas()
        canvas._components = [
            CanvasVisualComponent(component_spec_for_display_name("Mechanical Random Reference"), "road_1", QPointF(120.0, 610.0), (130.0, 80.0), True),
            CanvasVisualComponent(component_spec_for_display_name("Mass"), "mass_1", QPointF(470.0, 110.0), (228.0, 108.0), True),
            CanvasVisualComponent(component_spec_for_display_name("Translational Spring"), "spring_1", QPointF(630.0, 260.0), (78.0, 148.0), True),
            CanvasVisualComponent(component_spec_for_display_name("Wheel"), "wheel_1", QPointF(470.0, 470.0), (230.0, 230.0), True),
            CanvasVisualComponent(component_spec_for_display_name("Tire Stiffness"), "tire_1", QPointF(515.0, 705.0), (130.0, 90.0), True),
        ]
        canvas._wires = [
            CanvasWireConnection("mass_1", "bottom", "spring_1", "R"),
            CanvasWireConnection("spring_1", "C", "wheel_1", "top"),
            CanvasWireConnection("wheel_1", "bottom", "tire_1", "R"),
            CanvasWireConnection("road_1", "output", "tire_1", "C"),
        ]
        spring = canvas._components[2]
        base_authored_rect = canvas._component_rect(spring)
        canvas.update_visualization(
            {
                "template_id": "blank",
                "runtime_outputs": {
                    "body_displacement": 0.01,
                    "wheel_displacement": 0.026,
                },
            }
        )
        dynamic_rect = canvas._dynamic_rect(spring)
        self.assertNotEqual(base_authored_rect, dynamic_rect)
        canvas.select_component(2)
        handle = next(item for item in canvas.selected_resize_handles_snapshot() if item["corner"] == "bottom_right")
        self.assertAlmostEqual(handle["rect"].center().x(), base_authored_rect.right(), delta=20.0)
        self.assertAlmostEqual(handle["rect"].center().y(), base_authored_rect.bottom(), delta=20.0)
        start = handle["rect"].center()
        end = QPointF(start.x() + 30.0, start.y() + 40.0)
        self._left_click(canvas, start)
        self._drag_mouse(canvas, end)
        self._release_left(canvas, end)
        resized_authored_rect = canvas._component_rect(spring)
        self.assertGreater(resized_authored_rect.height(), base_authored_rect.height())

    def test_global_io_numbering_uses_assignment_order_and_compacts_after_clear(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        canvas.select_component(4)
        self.assertTrue(canvas.assign_selected_component_io_role(ComponentIoRole.OUTPUT))
        canvas.select_component(1)
        self.assertTrue(canvas.assign_selected_component_io_role(ComponentIoRole.OUTPUT))
        canvas.select_component(3)
        self.assertTrue(canvas.assign_selected_component_io_role(ComponentIoRole.OUTPUT))
        self.assertEqual(canvas._io_marker_label(canvas._components[4], ComponentIoRole.OUTPUT), "z1")
        self.assertEqual(canvas._io_marker_label(canvas._components[1], ComponentIoRole.OUTPUT), "z2")
        self.assertEqual(canvas._io_marker_label(canvas._components[3], ComponentIoRole.OUTPUT), "z3")
        canvas.select_component(1)
        self.assertTrue(canvas.clear_selected_component_io_role(ComponentIoRole.OUTPUT))
        self.assertEqual(canvas._io_marker_label(canvas._components[4], ComponentIoRole.OUTPUT), "z1")
        self.assertEqual(canvas._io_marker_label(canvas._components[3], ComponentIoRole.OUTPUT), "z2")

    def test_global_input_numbering_is_assignment_order_based(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        canvas.select_component(4)
        self.assertTrue(canvas.assign_selected_component_io_role(ComponentIoRole.INPUT))
        canvas.select_component(0)
        self.assertTrue(canvas.assign_selected_component_io_role(ComponentIoRole.INPUT))
        self.assertEqual(canvas._io_marker_label(canvas._components[4], ComponentIoRole.INPUT), "u1")
        self.assertEqual(canvas._io_marker_label(canvas._components[0], ComponentIoRole.INPUT), "u2")

    def test_mechanical_pilot_set_uses_no_background_emphasis_policy(self):
        for display_name in ("Mass", "Translational Spring", "Translational Damper"):
            component = ModelCanvas()._instantiate_drop_component(display_name, 2, QPointF(320.0, 240.0))
            self.assertEqual(component.spec.presentation.emphasis_fill_opacity, 0.0)

    def test_mass_overlay_and_ports_use_tighter_presentation_geometry(self):
        canvas = ModelCanvas()
        component = canvas._instantiate_drop_component("Mass", 2, QPointF(260.0, 220.0))
        rect = canvas._dynamic_rect(component)
        visual_rect = component.visual_bounds(rect)
        overlay_rect = component.selection_overlay_rect(rect)
        ports = component.connector_centers(rect)
        self.assertLess(overlay_rect.width() - visual_rect.width(), 20.0)
        self.assertLess(overlay_rect.height() - visual_rect.height(), 20.0)
        self.assertAlmostEqual(ports[0].y(), visual_rect.top() - 6.0, delta=0.01)
        self.assertAlmostEqual(ports[1].y(), visual_rect.bottom() + 6.0, delta=0.01)

    def test_resistor_terminal_anchors_snap_to_visual_terminals_after_resize(self):
        canvas = ModelCanvas()
        component = canvas._instantiate_drop_component("Resistor", 2, QPointF(280.0, 180.0))
        component.size = (180.0, 70.0)
        rect = canvas._dynamic_rect(component)
        visual_rect = component.visual_bounds(rect)
        ports = component.connector_centers(rect)
        self.assertAlmostEqual(ports[0].x(), visual_rect.left() + 8.0, delta=0.01)
        self.assertAlmostEqual(ports[1].x(), visual_rect.right() - 8.0, delta=0.01)

    def test_mass_drop_symbol_area_exceeds_spring_and_damper(self):
        canvas = ModelCanvas()
        mass = canvas._instantiate_drop_component("Mass", 2, QPointF(220.0, 220.0))
        spring = canvas._instantiate_drop_component("Translational Spring", 2, QPointF(420.0, 220.0))
        damper = canvas._instantiate_drop_component("Translational Damper", 2, QPointF(620.0, 220.0))
        mass_area = canvas._renderer.symbol_render_rect(mass, canvas._dynamic_rect(mass)).width() * canvas._renderer.symbol_render_rect(mass, canvas._dynamic_rect(mass)).height()
        spring_area = canvas._renderer.symbol_render_rect(spring, canvas._dynamic_rect(spring)).width() * canvas._renderer.symbol_render_rect(spring, canvas._dynamic_rect(spring)).height()
        damper_area = canvas._renderer.symbol_render_rect(damper, canvas._dynamic_rect(damper)).width() * canvas._renderer.symbol_render_rect(damper, canvas._dynamic_rect(damper)).height()
        self.assertGreater(mass_area, spring_area)
        self.assertGreater(mass_area, damper_area)

    def test_spring_and_damper_connector_hit_regions_are_centered_on_terminal_endpoints(self):
        canvas = ModelCanvas()
        for display_name in ("Translational Spring", "Translational Damper"):
            component = canvas._instantiate_drop_component(display_name, 2, QPointF(320.0, 240.0))
            rect = canvas._dynamic_rect(component)
            visual_rect = component.visual_bounds(rect)
            centers = component.connector_centers(rect)
            hit_rects = component.connector_hit_rects(rect)
            self.assertAlmostEqual(centers[0].x(), visual_rect.center().x(), delta=0.01)
            self.assertAlmostEqual(centers[1].x(), visual_rect.center().x(), delta=0.01)
            self.assertAlmostEqual(centers[0].y(), visual_rect.top(), delta=0.01)
            self.assertAlmostEqual(centers[1].y(), visual_rect.bottom(), delta=0.01)
            self.assertAlmostEqual(hit_rects[0][1].center().x(), centers[0].x(), delta=0.01)
            self.assertAlmostEqual(hit_rects[0][1].center().y(), centers[0].y(), delta=0.01)
            self.assertAlmostEqual(hit_rects[1][1].center().x(), centers[1].x(), delta=0.01)
            self.assertAlmostEqual(hit_rects[1][1].center().y(), centers[1].y(), delta=0.01)

    def test_rotation_plus_resize_keeps_connector_geometry_valid(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("single_mass")
        canvas.select_component(1)
        component = canvas._components[1]
        component.rotate_clockwise()
        top_right = next(handle for handle in canvas.selected_resize_handles_snapshot() if handle["corner"] == "top_right")
        start = top_right["rect"].center()
        end = QPointF(start.x() + 50.0, start.y() - 40.0)
        self._left_click(canvas, start)
        self._drag_mouse(canvas, end)
        self._release_left(canvas, end)
        ports = component.connector_centers(canvas._dynamic_rect(component))
        self.assertEqual(len(ports), 2)
        self.assertNotEqual((ports[0].x(), ports[0].y()), (ports[1].x(), ports[1].y()))

    def test_selected_wire_exposes_distinct_render_style(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("two_mass")
        source_mass = canvas._components[1]
        target_mass = canvas._components[2]
        source_port = source_mass.connector_centers(canvas._dynamic_rect(source_mass))[1]
        target_port = target_mass.connector_centers(canvas._dynamic_rect(target_mass))[0]
        self._left_click(canvas, source_port)
        self._left_click(canvas, target_port)
        midpoint = QPointF((source_port.x() + target_port.x()) / 2.0, (source_port.y() + target_port.y()) / 2.0)
        self._left_click(canvas, midpoint)

        style = canvas.selected_wire_style()
        self.assertTrue(style["selected"])
        self.assertEqual(style["line_width"], 5.0)
        self.assertEqual(style["color"], "#0f3d91")

    def test_delete_removes_selected_wire(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("two_mass")
        baseline = len(canvas.persistent_wires())
        source_mass = canvas._components[1]
        target_mass = canvas._components[2]
        source_port = source_mass.connector_centers(canvas._dynamic_rect(source_mass))[1]
        target_port = target_mass.connector_centers(canvas._dynamic_rect(target_mass))[0]
        self._left_click(canvas, source_port)
        self._left_click(canvas, target_port)
        midpoint = QPointF((source_port.x() + target_port.x()) / 2.0, (source_port.y() + target_port.y()) / 2.0)
        self._left_click(canvas, midpoint)

        event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier)
        canvas.keyPressEvent(event)
        self.assertEqual(len(canvas.persistent_wires()), baseline)
        self.assertIsNone(canvas.selected_wire_snapshot())

    def test_backspace_removes_selected_wire(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("two_mass")
        baseline = len(canvas.persistent_wires())
        source_mass = canvas._components[1]
        target_mass = canvas._components[2]
        source_port = source_mass.connector_centers(canvas._dynamic_rect(source_mass))[1]
        target_port = target_mass.connector_centers(canvas._dynamic_rect(target_mass))[0]
        self._left_click(canvas, source_port)
        self._left_click(canvas, target_port)
        midpoint = QPointF((source_port.x() + target_port.x()) / 2.0, (source_port.y() + target_port.y()) / 2.0)
        self._left_click(canvas, midpoint)

        event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Backspace, Qt.NoModifier)
        canvas.keyPressEvent(event)
        self.assertEqual(len(canvas.persistent_wires()), baseline)
        self.assertIsNone(canvas.selected_wire_snapshot())

    def test_delete_with_no_selected_wire_does_nothing(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("two_mass")
        baseline = list(canvas.persistent_wires())
        event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier)
        canvas.keyPressEvent(event)
        self.assertEqual(canvas.persistent_wires(), baseline)
        self.assertIsNone(canvas.selected_wire_snapshot())

    def test_wire_selection_still_works_after_rotated_components(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("two_mass")
        canvas._components[1].rotate_clockwise()
        canvas._components[2].rotate_counterclockwise()
        source_port = canvas._components[1].connector_centers(canvas._dynamic_rect(canvas._components[1]))[1]
        target_port = canvas._components[2].connector_centers(canvas._dynamic_rect(canvas._components[2]))[0]
        self._left_click(canvas, source_port)
        self._left_click(canvas, target_port)
        midpoint = QPointF((source_port.x() + target_port.x()) / 2.0, (source_port.y() + target_port.y()) / 2.0)
        self._left_click(canvas, midpoint)
        self.assertIsNotNone(canvas.selected_wire_snapshot())

    def test_wire_selection_still_works_after_component_translation(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("two_mass")
        source_mass = canvas._components[1]
        target_mass = canvas._components[2]
        source_port = source_mass.connector_centers(canvas._dynamic_rect(source_mass))[1]
        target_port = target_mass.connector_centers(canvas._dynamic_rect(target_mass))[0]
        self._left_click(canvas, source_port)
        self._left_click(canvas, target_port)
        source_mass.position = QPointF(source_mass.position.x() + 30.0, source_mass.position.y() + 20.0)
        target_mass.position = QPointF(target_mass.position.x() - 20.0, target_mass.position.y() + 25.0)
        moved_source = source_mass.connector_centers(canvas._dynamic_rect(source_mass))[1]
        moved_target = target_mass.connector_centers(canvas._dynamic_rect(target_mass))[0]
        midpoint = QPointF((moved_source.x() + moved_target.x()) / 2.0, (moved_source.y() + moved_target.y()) / 2.0)
        self._left_click(canvas, midpoint)
        self.assertIsNotNone(canvas.selected_wire_snapshot())

    def test_escape_cancels_in_progress_wire(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        baseline = list(canvas.persistent_wires())
        mass = canvas._components[1]
        start = mass.connector_centers(canvas._dynamic_rect(mass))[0]
        self._left_click(canvas, start)
        self.assertTrue(canvas.wire_preview_active())

        event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
        canvas.keyPressEvent(event)

        self.assertFalse(canvas.wire_preview_active())
        self.assertIsNone(canvas.hovered_target_connector_snapshot())
        self.assertEqual(canvas.persistent_wires(), baseline)

    def test_right_click_cancels_in_progress_wire(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        baseline = list(canvas.persistent_wires())
        mass = canvas._components[1]
        start = mass.connector_centers(canvas._dynamic_rect(mass))[0]
        self._left_click(canvas, start)
        self.assertTrue(canvas.wire_preview_active())

        self._right_click(canvas, QPointF(start.x() + 80.0, start.y() + 40.0))

        self.assertFalse(canvas.wire_preview_active())
        self.assertIsNone(canvas.hovered_target_connector_snapshot())
        self.assertEqual(canvas.persistent_wires(), baseline)

    def test_clicking_empty_canvas_while_wiring_does_not_create_persistent_wire(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        baseline = list(canvas.persistent_wires())
        mass = canvas._components[1]
        start = mass.connector_centers(canvas._dynamic_rect(mass))[0]
        self._left_click(canvas, start)
        self._left_click(canvas, QPointF(50.0, 50.0))

        self.assertTrue(canvas.wire_preview_active())
        self.assertEqual(canvas.persistent_wires(), baseline)

    def test_clicking_same_connector_again_cancels_wire_without_artifacts(self):
        canvas = ModelCanvas()
        canvas.load_default_quarter_car_layout()
        baseline = list(canvas.persistent_wires())
        mass = canvas._components[1]
        start = mass.connector_centers(canvas._dynamic_rect(mass))[0]
        self._left_click(canvas, start)
        self._left_click(canvas, start)

        self.assertFalse(canvas.wire_preview_active())
        self.assertIsNone(canvas.hovered_target_connector_snapshot())
        self.assertEqual(canvas.persistent_wires(), baseline)

    def test_connector_debug_overlay_renders_without_breaking_mass_svg_component(self):
        canvas = ModelCanvas()
        canvas.resize(900, 700)
        canvas.load_default_quarter_car_layout()
        canvas.set_connector_debug_visible(True)

        image = QImage(canvas.size(), QImage.Format_ARGB32_Premultiplied)
        image.fill(0)
        canvas.render(image)

        self.assertTrue(canvas._components[1].has_svg_symbol())
        self.assertTrue(canvas.connector_debug_visible())

    def test_context_menu_rotate_counterclockwise_updates_selection_details(self):
        canvas = ModelCanvas()
        canvas.load_template_layout("single_mass")
        canvas.select_component(2)
        menu = canvas.build_context_menu(2)
        rotate_ccw_action = next(action for action in menu.actions() if action.text() == "Rotate Counterclockwise")
        rotate_ccw_action.trigger()
        self.assertEqual(canvas.selected_component_details()["rotation_degrees"], 270)


if __name__ == "__main__":
    unittest.main()
