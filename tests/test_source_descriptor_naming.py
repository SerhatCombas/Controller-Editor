"""Regression guard: source descriptor input_variable_name must use u_<id> convention.

Canonical convention (from app/core/base/source_descriptor.py docstring):
    input_variable_name: The symbolic name that will appear in the
        input vector u. Conventionally f"u_{component_id}".

These tests guard against future regressions where a new source type is added
with a non-canonical prefix (e.g. "r_", "f_<id>_out") that would break
SymbolicStateSpaceBackend._input_index() and related consumers.
"""
import unittest

from app.core.models.sources.random_road import RandomRoad
from app.core.models.sources.step_force import StepForce


class TestSourceDescriptorNaming(unittest.TestCase):

    # ------------------------------------------------------------------
    # a. RandomRoad
    # ------------------------------------------------------------------

    def test_random_road_input_variable_uses_u_prefix(self):
        """RandomRoad.get_source_descriptor().input_variable_name == 'u_<id>'."""
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
            "u_foo",
            f"Expected 'u_foo', got '{descriptor.input_variable_name}'. "
            "RandomRoad must follow the u_<id> convention.",
        )

    # ------------------------------------------------------------------
    # b. StepForce
    # ------------------------------------------------------------------

    def test_step_force_input_variable_uses_u_prefix(self):
        """StepForce.get_source_descriptor().input_variable_name == 'u_<id>'."""
        source = StepForce("bar", amplitude=1.0)
        descriptor = source.get_source_descriptor()
        self.assertEqual(
            descriptor.input_variable_name,
            "u_bar",
            f"Expected 'u_bar', got '{descriptor.input_variable_name}'. "
            "StepForce must follow the u_<id> convention.",
        )

    # ------------------------------------------------------------------
    # c. Format guard — catches any future non-canonical prefix
    # ------------------------------------------------------------------

    def test_input_variable_names_match_doc_convention(self):
        """Both sources must produce input_variable_name == f'u_{{component_id}}'."""
        sources = [
            RandomRoad(
                "road_source",
                amplitude=0.03,
                roughness=0.35,
                seed=7,
                vehicle_speed=6.0,
                dt=0.01,
                duration=15.0,
            ),
            StepForce("body_force", amplitude=1.0),
        ]
        for source in sources:
            descriptor = source.get_source_descriptor()
            expected = f"u_{source.id}"
            self.assertEqual(
                descriptor.input_variable_name,
                expected,
                f"{type(source).__name__}(id={source.id!r}): "
                f"expected '{expected}', got '{descriptor.input_variable_name}'. "
                "Convention: input_variable_name must be f'u_{{component_id}}'.",
            )
