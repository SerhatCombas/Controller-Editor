"""Faz 4b — RandomRoad bound parameters tests.

These tests validate the post-generation processing pipeline:

    max_height                 -> symmetric height clamp |u(x)| <= max_height
    max_slope                  -> iterative slope-limit |du/dx| <= max_slope
    min_feature_width          -> low-pass smoothing of sub-window features
    wheel_radius_reference     -> coordinates min_feature_width with wheel size

The defaults must reproduce the legacy filtered-noise profile exactly so that
existing simulations are unaffected.
"""
import unittest

from app.core.models.sources.random_road import RandomRoad


def _make_road(
    *,
    seed: int = 7,
    vehicle_speed: float = 6.0,
    duration: float = 3.0,
    dt: float = 0.01,
    amplitude: float = 0.03,
    roughness: float = 0.4,
    **extra,
) -> RandomRoad:
    return RandomRoad(
        "road_source",
        amplitude=amplitude,
        roughness=roughness,
        seed=seed,
        vehicle_speed=vehicle_speed,
        dt=dt,
        duration=duration,
        **extra,
    )


def _sampled_distances(road: RandomRoad, count: int = 40) -> list[float]:
    last = road.parameters["vehicle_speed"] * road.parameters["duration"]
    return [(i / float(count - 1)) * last for i in range(count)]


class TestDefaultsPreserveLegacyBehavior(unittest.TestCase):
    """Without any of the new parameters, the profile must match the legacy
    filtered-noise output bit-for-bit."""

    def test_no_new_params_matches_baseline(self):
        legacy = _make_road(seed=99)
        # Same args, default new parameters explicitly stated to make the
        # contract obvious.
        with_defaults = _make_road(
            seed=99,
            max_height=None,
            max_slope=None,
            min_feature_width=0.0,
            wheel_radius_reference=0.0,
        )
        for x in _sampled_distances(legacy):
            self.assertAlmostEqual(legacy.height_at_distance(x),
                                    with_defaults.height_at_distance(x),
                                    places=12)


class TestMaxHeight(unittest.TestCase):
    def test_clamp_caps_extremes(self):
        """A tight max_height must bound |u(x)| everywhere."""
        road = _make_road(seed=3, amplitude=0.1, max_height=0.02)
        for x in _sampled_distances(road):
            self.assertLessEqual(abs(road.height_at_distance(x)), 0.02 + 1e-12,
                                  msg=f"height {road.height_at_distance(x)} exceeds 0.02 at x={x}")

    def test_loose_clamp_is_no_op(self):
        """max_height larger than amplitude leaves the profile untouched."""
        baseline = _make_road(seed=5, amplitude=0.03)
        clamped = _make_road(seed=5, amplitude=0.03, max_height=10.0)
        for x in _sampled_distances(baseline):
            self.assertAlmostEqual(baseline.height_at_distance(x),
                                    clamped.height_at_distance(x), places=12)

    def test_negative_max_height_treated_as_disabled(self):
        """Nonsense negative value must not crash; profile equals baseline."""
        baseline = _make_road(seed=11)
        weird = _make_road(seed=11, max_height=-0.05)
        for x in _sampled_distances(baseline):
            self.assertAlmostEqual(baseline.height_at_distance(x),
                                    weird.height_at_distance(x), places=12)


class TestMaxSlope(unittest.TestCase):
    def test_slope_limit_bounds_derivative(self):
        """After slope limiting, |du/dx| must not exceed max_slope anywhere."""
        # roughness=0.05 produces visible cliffs; max_slope=0.5 enforces gentle
        # gradients (|du/dx| <= 0.5 m/m means at most 50cm rise per meter).
        road = _make_road(seed=2, amplitude=0.08, roughness=0.05, max_slope=0.5)
        for x in _sampled_distances(road, count=80):
            slope = road.slope_at_distance(x)
            # Allow a small tolerance (1e-6) for floating-point + interpolation.
            self.assertLessEqual(abs(slope), 0.5 + 1e-6,
                                  msg=f"slope {slope} at x={x} violates max_slope=0.5")

    def test_max_slope_none_is_no_op(self):
        """max_slope=None preserves the legacy profile."""
        baseline = _make_road(seed=21)
        explicit = _make_road(seed=21, max_slope=None)
        for x in _sampled_distances(baseline):
            self.assertAlmostEqual(baseline.height_at_distance(x),
                                    explicit.height_at_distance(x), places=12)


class TestFeatureWidthSmoothing(unittest.TestCase):
    def test_zero_feature_width_is_no_op(self):
        """min_feature_width=0 and wheel_radius_reference=0 leave profile alone."""
        baseline = _make_road(seed=4)
        explicit = _make_road(seed=4, min_feature_width=0.0, wheel_radius_reference=0.0)
        for x in _sampled_distances(baseline):
            self.assertAlmostEqual(baseline.height_at_distance(x),
                                    explicit.height_at_distance(x), places=12)

    def test_smoothing_reduces_variance(self):
        """A meaningful smoothing window must reduce sample-to-sample roughness."""
        # Same seed — fair comparison: smoother variant has lower local variance.
        rough = _make_road(seed=8, amplitude=0.05, roughness=0.05)
        smoothed = _make_road(seed=8, amplitude=0.05, roughness=0.05,
                              min_feature_width=2.0)  # 2 m window at V=6 m/s
        # Sum of squared first-differences as a proxy for roughness.
        def roughness_metric(road):
            xs = _sampled_distances(road, count=80)
            heights = [road.height_at_distance(x) for x in xs]
            return sum((heights[i] - heights[i - 1]) ** 2 for i in range(1, len(heights)))
        self.assertLess(roughness_metric(smoothed), roughness_metric(rough))


class TestWheelRadiusCoordination(unittest.TestCase):
    def test_wheel_radius_overrides_smaller_user_width(self):
        """If the user requests a width below 2R, the effective width is 2R."""
        # User asked for 0.1 m, but R=0.3 m -> effective_feature_width must be 0.6 m.
        road = _make_road(seed=12, min_feature_width=0.1, wheel_radius_reference=0.3)
        self.assertAlmostEqual(road.parameters["effective_feature_width"], 0.6, places=12)

    def test_user_width_wins_when_larger_than_2r(self):
        """If user requests a wider width than 2R, the user's value sticks."""
        road = _make_road(seed=13, min_feature_width=2.0, wheel_radius_reference=0.3)
        # max(2.0, 2*0.3) = 2.0
        self.assertAlmostEqual(road.parameters["effective_feature_width"], 2.0, places=12)

    def test_wheel_radius_only_sets_2r_default(self):
        """If user leaves min_feature_width=0, wheel reference alone sets 2R."""
        road = _make_road(seed=14, wheel_radius_reference=0.25)
        self.assertAlmostEqual(road.parameters["effective_feature_width"], 0.5, places=12)


class TestPipelineComposition(unittest.TestCase):
    def test_all_bounds_together(self):
        """All three bound parameters can coexist; final profile satisfies all
        of them simultaneously."""
        road = _make_road(
            seed=17, amplitude=0.12, roughness=0.05,
            max_height=0.05,
            max_slope=0.4,
            min_feature_width=1.0,
            wheel_radius_reference=0.2,
        )
        for x in _sampled_distances(road, count=80):
            height = road.height_at_distance(x)
            slope = road.slope_at_distance(x)
            self.assertLessEqual(abs(height), 0.05 + 1e-12, msg=f"height {height} at x={x}")
            self.assertLessEqual(abs(slope), 0.4 + 1e-6, msg=f"slope {slope} at x={x}")
        # And the effective_feature_width is the larger of the two requirements.
        self.assertAlmostEqual(road.parameters["effective_feature_width"], 1.0, places=12)


if __name__ == "__main__":
    unittest.main()
