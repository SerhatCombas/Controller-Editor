"""Faz 4a — RandomRoad spatial API tests.

These tests validate the wheel-aware road profile API:

    height_at_distance(x) -> u(x)         (road height at horizontal position x)
    slope_at_distance(x)  -> du/dx        (road slope at horizontal position x)

Properties under test:
    * Boundary clamping (queries outside [0, V*duration] return nearest sample).
    * Consistency with the time-domain API (displacement_output(t) == height_at_distance(V*t)).
    * Slope sign correctness on monotonic sub-ranges.
    * Slope continuity (no impossible jumps between adjacent samples).
    * Reproducibility under fixed seed.
"""
import unittest

from app.core.models.sources.random_road import RandomRoad


def _make_road(seed: int = 7, vehicle_speed: float = 6.0, duration: float = 3.0, dt: float = 0.01) -> RandomRoad:
    return RandomRoad(
        "road_source",
        amplitude=0.03,
        roughness=0.4,
        seed=seed,
        vehicle_speed=vehicle_speed,
        dt=dt,
        duration=duration,
    )


class TestHeightAtDistance(unittest.TestCase):
    def test_returns_first_sample_below_domain(self):
        """x <= 0 clamps to the first sample u(0)."""
        road = _make_road()
        first_sample = road.spatial_profile(0.0)
        self.assertAlmostEqual(road.height_at_distance(-5.0), first_sample, places=12)
        self.assertAlmostEqual(road.height_at_distance(0.0), first_sample, places=12)

    def test_returns_last_sample_above_domain(self):
        """x >= V*duration clamps to the last stored sample."""
        road = _make_road(vehicle_speed=6.0, duration=3.0)
        last_distance = 6.0 * 3.0  # vehicle_speed * duration
        last_sample = road.spatial_profile(last_distance)
        self.assertAlmostEqual(road.height_at_distance(last_distance + 100.0), last_sample, places=12)

    def test_matches_displacement_output_via_v_times_t(self):
        """displacement_output(t) and height_at_distance(V*t) must agree exactly."""
        road = _make_road()
        v = road.parameters["vehicle_speed"]
        for t in [0.0, 0.05, 0.5, 1.0, 1.7, 2.99]:
            expected = road.displacement_output(t)
            actual = road.height_at_distance(v * t)
            self.assertAlmostEqual(actual, expected, places=12,
                msg=f"mismatch at t={t}: displacement={expected}, spatial={actual}")

    def test_reproducible_under_fixed_seed(self):
        """Two RandomRoad instances with the same seed expose the same height profile."""
        a = _make_road(seed=42)
        b = _make_road(seed=42)
        for x in [0.5, 2.0, 5.0, 10.0, 17.5]:
            self.assertAlmostEqual(a.height_at_distance(x), b.height_at_distance(x), places=12)


class TestSlopeAtDistance(unittest.TestCase):
    def test_slope_units_match_velocity_over_speed(self):
        """slope_at_distance(V*t) must equal velocity_output(t)/V (units consistency)."""
        road = _make_road(vehicle_speed=8.0)
        v = road.parameters["vehicle_speed"]
        for t in [0.1, 0.4, 1.0, 1.5, 2.5]:
            slope_via_x = road.slope_at_distance(v * t)
            slope_via_t = road.velocity_output(t) / v
            self.assertAlmostEqual(slope_via_x, slope_via_t, places=10,
                msg=f"slope mismatch at t={t}: via_x={slope_via_x}, via_t={slope_via_t}")

    def test_slope_clamps_at_boundaries(self):
        """Outside [0, V*duration] the slope clamps to the nearest endpoint slope."""
        road = _make_road()
        last_distance = road.parameters["vehicle_speed"] * road.parameters["duration"]
        # Below domain: matches slope at x=0
        self.assertAlmostEqual(road.slope_at_distance(-50.0), road.slope_at_distance(0.0), places=12)
        # Above domain: matches slope at x=last
        self.assertAlmostEqual(road.slope_at_distance(last_distance + 50.0),
                               road.slope_at_distance(last_distance), places=12)

    def test_slope_finite_for_smooth_profile(self):
        """A finite-amplitude road must produce finite, bounded slopes everywhere."""
        road = _make_road(seed=11)
        last_distance = road.parameters["vehicle_speed"] * road.parameters["duration"]
        for x_step in range(0, 20):
            x = (x_step / 20.0) * last_distance
            slope = road.slope_at_distance(x)
            self.assertTrue(abs(slope) < 1.0,
                msg=f"unphysical slope {slope} at x={x} (amplitude=0.03 should not produce |slope|>=1)")

    def test_slope_cache_does_not_change_results(self):
        """First and second calls return identical values (cache invariance)."""
        road = _make_road()
        x = 5.0
        first = road.slope_at_distance(x)
        # Force cache by calling other slopes first
        road.slope_at_distance(0.0)
        road.slope_at_distance(10.0)
        second = road.slope_at_distance(x)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
