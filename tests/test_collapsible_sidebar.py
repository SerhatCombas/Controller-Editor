"""Tests for CollapsibleSidebar widget — Faz UI-1.

Non-PySide6 tests cover the logical API (state transitions, signals, dimensions).
Actual rendering is tested by the PySide6 marker.
"""
from __future__ import annotations

import unittest

import pytest

pyside6 = pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel, QWidget

from app.ui.widgets.collapsible_sidebar import CollapsedSidebarRail, CollapsibleSidebar

# Ensure a QApplication exists for widget tests
_app = QApplication.instance() or QApplication([])


class TestCollapsibleSidebarInit(unittest.TestCase):
    """Test construction and default state."""

    def test_default_expanded_left(self):
        content = QLabel("test content")
        sidebar = CollapsibleSidebar("Library", content, side="left", expanded=True)
        self.assertTrue(sidebar.is_expanded)
        self.assertEqual(sidebar.side, "left")
        self.assertEqual(sidebar.title, "Library")
        self.assertTrue(sidebar.expanded_page.isVisible())
        self.assertFalse(sidebar.collapsed_page.isVisible())
        self.assertEqual(sidebar.width(), 300)

    def test_default_collapsed_right(self):
        content = QLabel("equations")
        sidebar = CollapsibleSidebar("Equations", content, side="right", expanded=False)
        self.assertFalse(sidebar.is_expanded)
        self.assertEqual(sidebar.side, "right")
        self.assertFalse(sidebar.expanded_page.isVisible())
        self.assertTrue(sidebar.collapsed_page.isVisible())
        self.assertEqual(sidebar.width(), 44)

    def test_custom_widths(self):
        content = QLabel("wide")
        sidebar = CollapsibleSidebar(
            "Config", content,
            side="left", expanded=True,
            expanded_width=400, collapsed_width=50,
        )
        self.assertEqual(sidebar.width(), 400)
        sidebar.collapse()
        self.assertEqual(sidebar.width(), 50)


class TestCollapsibleSidebarToggle(unittest.TestCase):
    """Test expand/collapse/toggle state transitions."""

    def setUp(self):
        self.content = QLabel("panel")
        self.sidebar = CollapsibleSidebar("Test", self.content, side="left", expanded=True)
        self.signal_log: list[bool] = []
        self.sidebar.toggled.connect(self.signal_log.append)

    def test_toggle_from_expanded(self):
        self.sidebar.toggle()
        self.assertFalse(self.sidebar.is_expanded)
        self.assertFalse(self.sidebar.expanded_page.isVisible())
        self.assertTrue(self.sidebar.collapsed_page.isVisible())
        self.assertEqual(self.sidebar.width(), 44)
        self.assertEqual(self.signal_log, [False])

    def test_toggle_back(self):
        self.sidebar.toggle()
        self.sidebar.toggle()
        self.assertTrue(self.sidebar.is_expanded)
        self.assertEqual(self.sidebar.width(), 300)
        self.assertEqual(self.signal_log, [False, True])

    def test_expand_when_already_expanded_no_signal(self):
        self.sidebar.expand()
        self.assertEqual(self.signal_log, [])

    def test_collapse_when_already_collapsed_no_signal(self):
        self.sidebar.collapse()  # expanded → collapsed
        self.signal_log.clear()
        self.sidebar.collapse()  # already collapsed → no-op
        self.assertEqual(self.signal_log, [])

    def test_explicit_expand(self):
        self.sidebar.collapse()
        self.signal_log.clear()
        self.sidebar.expand()
        self.assertTrue(self.sidebar.is_expanded)
        self.assertEqual(self.signal_log, [True])

    def test_explicit_collapse(self):
        self.sidebar.collapse()
        self.assertFalse(self.sidebar.is_expanded)
        self.assertEqual(self.signal_log, [False])


class TestCollapsibleSidebarArrowDirection(unittest.TestCase):
    """Toggle button arrow should point inward when expanded."""

    def test_left_sidebar_expanded_arrow(self):
        sidebar = CollapsibleSidebar("L", QLabel(""), side="left", expanded=True)
        self.assertEqual(sidebar.toggle_button.text(), "‹")

    def test_left_sidebar_collapsed_arrow(self):
        sidebar = CollapsibleSidebar("L", QLabel(""), side="left", expanded=False)
        self.assertEqual(sidebar.toggle_button.text(), "›")

    def test_right_sidebar_expanded_arrow(self):
        sidebar = CollapsibleSidebar("R", QLabel(""), side="right", expanded=True)
        self.assertEqual(sidebar.toggle_button.text(), "›")

    def test_right_sidebar_collapsed_arrow(self):
        sidebar = CollapsibleSidebar("R", QLabel(""), side="right", expanded=False)
        self.assertEqual(sidebar.toggle_button.text(), "‹")


class TestCollapsedSidebarRail(unittest.TestCase):
    """Test the collapsed rail sub-widget."""

    def test_rail_has_title(self):
        rail = CollapsedSidebarRail("Library", "left")
        self.assertEqual(rail.title, "Library")
        self.assertEqual(rail.side, "left")
        self.assertEqual(rail.objectName(), "CollapsedSidebarRail")

    def test_rail_tooltip(self):
        rail = CollapsedSidebarRail("Config", "right")
        self.assertEqual(rail.toolTip(), "Open Config")


class TestCollapsibleSidebarContentAccess(unittest.TestCase):
    """Content widget should remain accessible."""

    def test_content_is_child(self):
        content = QLabel("my content")
        sidebar = CollapsibleSidebar("Test", content, side="left")
        # Content should be a descendant
        self.assertIs(sidebar.content, content)

    def test_content_visible_when_expanded(self):
        content = QLabel("visible")
        sidebar = CollapsibleSidebar("Test", content, side="left", expanded=True)
        # Content's parent (expanded_page) is visible
        self.assertTrue(sidebar.expanded_page.isVisible())

    def test_content_hidden_when_collapsed(self):
        content = QLabel("hidden")
        sidebar = CollapsibleSidebar("Test", content, side="left", expanded=False)
        self.assertFalse(sidebar.expanded_page.isVisible())


if __name__ == "__main__":
    unittest.main()
