"""Regression guard: source descriptor input_variable_name uses physical names.

Canonical convention (from app/core/base/source_descriptor.py docstring):
    input_variable_name: The symbolic name that will appear in the
        input vector. Prefer physical channel names when a stable port
        variable exists.

These tests guard against future regressions where a new source type is added
with a generic-only prefix that would break the transfer-function API.
"""
import unittest

from app.core.models.sources.random_road import RandomRoad
from app.core.models.sources.step_force import StepForce


class TestSourceDescriptorNaming(unittest.TestCase):

    # ------------------------------------------------------------------
    # a. RandomRoad
    # ------------------------------------------------------------------

    def test_random_road_input_variable_uses_road_prefix(self):
        """RandomRoad.get_source_descriptor().input_variable_name == 'r_<id>'."""
        source = RandomRoad(
            "foo",
            amplitude=0.03,
            roughness=0.35,
            seed=7,
            vehicle_speed=6.0,
            dt=0.01,
            duration=15.0,
        )
        descriptor = source.get_source_descriptor()
        self.assertEqual(
            descriptor.input_variable_name,
            "r_foo",
            f"Expected 'r_foo', got '{descriptor.input_variable_name}'. "
            "RandomRoad must follow the r_<id> convention.",
        )

    # ------------------------------------------------------------------
    # b. StepForce
    # ------------------------------------------------------------------

    def test_step_force_input_variable_uses_force_port_name(self):
        """StepForce.get_source_descriptor().input_variable_name == 'f_<id>_out'."""
        source = StepForce("bar", amplitude=1.0)
        descriptor = source.get_source_descriptor()
        self.assertEqual(
            descriptor.input_variable_name,
            "f_bar_out",
            f"Expected 'f_bar_out', got '{descriptor.input_variable_name}'. "
            "StepForce must follow the f_<id>_out convention.",
        )

    # ------------------------------------------------------------------
    # c. Format guard — catches any future non-canonical prefix
    # ------------------------------------------------------------------

    def test_input_variable_names_match_doc_convention(self):
        """Sources must produce stable physical input names."""
        cases = [
            (
                RandomRoad(
                    "road_source",
                    amplitude=0.03,
                    roughness=0.35,
                    seed=7,
                    vehicle_speed=6.0,
                    dt=0.01,
                    duration=15.0,
                ),
                "road_source",
                "r_road_source",
            ),
            (StepForce("body_force", amplitude=1.0), "body_force", "f_body_force_out"),
        ]
        for source, source_id, expected in cases:
            descriptor = source.get_source_descriptor()
            self.assertEqual(
                descriptor.input_variable_name,
                expected,
                f"{type(source).__name__}(id={source_id!r}): "
                f"expected '{expected}', got '{descriptor.input_variable_name}'. "
                "Convention: input_variable_name must be physically named.",
            )
