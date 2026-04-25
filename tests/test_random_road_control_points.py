"""Faz 4c — RandomRoad control-points generation tests.

Validates the alternate generation_mode='control_points' algorithm:
PCHIP-interpolated random control points, with auto-sized control point
count derived from duration and roughness.

Properties under test:
  * Default mode is 'filtered_noise' (legacy behavior, bit-for-bit match).
  * generation_mode='control_points' produces a different but valid profile.
  * Invalid generation_mode raises ValueError immediately.
  * Control-point count scales with roughness (rough -> more, smooth -> fewer).
  * Profile satisfies bound parameters (max_height/max_slope) in either mode.
  * Seed reproducibility holds in control_points mode too.
  * PCHIP smoothness: slopes don't jump arbitrarily between adjacent samples.
"""
import unittest

from app.core.models.sources.random_road import RandomRoad


def _make_road(
    *,
    seed: int = 7,
    vehicle_speed: float = 10.0,
    duration: float = 3.0,
    dt: float = 0.01,
    amplitude: float = 0.05,
    roughness: float = 0.4,
    generation_mode: str = "filtered_noise",
    **extra,
) -> RandomRoad:
    return RandomRoad(
        "road",
        amplitude=amplitude,
        roughness=roughness,
        seed=seed,
        vehicle_speed=vehicle_speed,
        dt=dt,
        duration=duration,
        generation_mode=generation_mode,
        **extra,
    )


def _sampled_distances(road: RandomRoad, count: int = 60) -> list[float]:
    last = road.parameters["vehicle_speed"] * road.parameters["duration"]
    return [(i / float(count - 1)) * last for i in range(count)]


class TestGenerationModeSwitch(unittest.TestCase):
    def test_default_mode_is_filtered_noise(self):
        """Without specifying generation_mode the legacy algorithm is used."""
        road = _make_road()
        self.assertEqual(road.parameters["generation_mode"], "filtered_noise")

    def test_explicit_filtered_noise_matches_default(self):
        """Explicit filtered_noise must produce identical profile to omitted default."""
        omitted = _make_road(seed=51)
        explicit = _make_road(seed=51, generation_mode="filtered_noise")
        for x in _sampled_distances(omitted):
            self.assertAlmostEqual(omitted.height_at_distance(x),
                                    explicit.height_at_distance(x), places=12)

    def test_invalid_mode_raises(self):
        """Unknown generation_mode is rejected at construction."""
        with self.assertRaises(ValueError):
            _make_road(generation_mode="foo")

    def test_two_modes_produce_different_profiles(self):
        """control_points and filtered_noise must produce visibly different profiles
        (otherwise we have no real switch)."""
        legacy = _make_road(seed=7, generation_mode="filtered_noise")
        new = _make_road(seed=7, generation_mode="control_points")
        # Sum of squared differences across many points; guard against any
        # accidental aliasing.
        diff_sum = sum(
            (legacy.height_at_distance(x) - new.height_at_distance(x)) ** 2
            for x in _sampled_distances(legacy)
        )
        self.assertGreater(diff_sum, 1e-6)


class TestControlPointAutoCount(unittest.TestCase):
    def test_lower_bound_is_eight(self):
        """A very smooth (low-roughness) road clamps to the minimum count."""
        road = _make_road(roughness=0.01, generation_mode="control_points",
                          duration=3.0, vehicle_speed=10.0)
        self.assertGreaterEqual(road._control_point_count(), 8)

    def test_rough_road_uses_more_points(self):
        """Rougher road yields more control points than smoother one (same length)."""
        smooth = _make_road(seed=1, roughness=0.1, generation_mode="control_points")
        rough = _make_road(seed=1, roughness=2.0, generation_mode="control_points")
        self.assertLess(smooth._control_point_count(), rough._control_point_count())

    def test_count_respects_sample_count_upper_bound(self):
        """Cannot have more control points than half the sample count."""
        # Very short profile: dt=0.1, duration=0.5 -> 6 samples; count <= 3.
        road = _make_road(roughness=10.0, dt=0.1, duration=0.5,
                          generation_mode="control_points")
        sample_count = len(road._distance)
        self.assertLessEqual(road._control_point_count(), max(sample_count // 2, 2))

    def test_count_respects_feature_width_coordination(self):
        """If effective_feature_width forces wide spacing, the control count drops."""
        # Without feature_width: rough road -> many points
        free = _make_road(seed=1, roughness=2.0, duration=3.0, vehicle_speed=10.0,
                          generation_mode="control_points")
        # With wheel_radius_reference=1.0 -> effective_feature_width = 2.0 m
        # On a 30 m road that limits spacing to 2.0 m -> at most ~16 control points.
        constrained = _make_road(seed=1, roughness=2.0, duration=3.0, vehicle_speed=10.0,
                                  wheel_radius_reference=1.0,
                                  generation_mode="control_points")
        self.assertLess(constrained._control_point_count(), free._control_point_count())


class TestControlPointsBehavior(unittest.TestCase):
    def test_seed_reproducibility(self):
        """Two control_points roads with the same seed produce identical profiles."""
        a = _make_road(seed=42, generation_mode="control_points")
        b = _make_road(seed=42, generation_mode="control_points")
        for x in _sampled_distances(a):
            self.assertAlmostEqual(a.height_at_distance(x), b.height_at_distance(x), places=12)

    def test_different_seeds_produce_different_profiles(self):
        """Different seeds -> different profiles (sanity check on RNG plumbing)."""
        a = _make_road(seed=1, generation_mode="control_points")
        b = _make_road(seed=2, generation_mode="control_points")
        diff_sum = sum(
            (a.height_at_distance(x) - b.height_at_distance(x)) ** 2
            for x in _sampled_distances(a)
        )
        self.assertGreater(diff_sum, 1e-6)

    def test_profile_magnitude_scales_with_amplitude(self):
        """Doubling amplitude doubles peak-to-peak (control points are scaled by amplitude)."""
        small = _make_road(seed=5, amplitude=0.01, generation_mode="control_points")
        big = _make_road(seed=5, amplitude=0.04, generation_mode="control_points")
        # Compare peak absolute values; ratio should be ~4 (one-sigma comparison).
        small_peak = max(abs(small.height_at_distance(x))
                         for x in _sampled_distances(small))
        big_peak = max(abs(big.height_at_distance(x))
                       for x in _sampled_distances(big))
        self.assertGreater(big_peak, 2.5 * small_peak,
            f"big_peak={big_peak} should be >2.5x small_peak={small_peak}")

    def test_pchip_does_not_overshoot_extreme_control_values(self):
        """A core property of PCHIP: profile values don't blow past the largest
        random control sample. Verify max(|profile|) is on the order of
        amplitude*reasonable_factor — not 10x amplitude (which a naive cubic
        spline could produce)."""
        road = _make_road(seed=11, amplitude=0.05, roughness=2.0,
                          generation_mode="control_points")
        peak = max(abs(road.height_at_distance(x))
                   for x in _sampled_distances(road, count=200))
        # Random-normal samples scaled by amplitude have ~99.7% within 3*sigma,
        # so peak should be at most ~4*amplitude with margin for finite samples.
        # (A truly-overshooting interpolant would push well past 5*amplitude.)
        self.assertLess(peak, 5.0 * road.parameters["amplitude"],
            f"PCHIP peak {peak} exceeds 5*amplitude={5*road.parameters['amplitude']}")


class TestControlPointsBoundsInteraction(unittest.TestCase):
    """Bounds (max_height, max_slope) work in control_points mode just like filtered_noise."""

    def test_max_height_clamps_in_control_points_mode(self):
        road = _make_road(seed=3, amplitude=0.5, max_height=0.05,
                          generation_mode="control_points")
        for x in _sampled_distances(road):
            self.assertLessEqual(abs(road.height_at_distance(x)), 0.05 + 1e-12)

    def test_max_slope_bounds_in_control_points_mode(self):
        road = _make_road(seed=4, amplitude=0.2, roughness=2.0,
                          max_slope=0.3, generation_mode="control_points")
        for x in _sampled_distances(road, count=80):
            self.assertLessEqual(abs(road.slope_at_distance(x)), 0.3 + 1e-6)


if __name__ == "__main__":
    unittest.main()
