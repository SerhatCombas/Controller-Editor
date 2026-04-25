from __future__ import annotations

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.base.source_descriptor import SourceDescriptor

try:
    import numpy as np
except ModuleNotFoundError:
    np = None

try:
    from scipy import signal
except ModuleNotFoundError:
    signal = None

from app.core.models.sources.base_signal import SignalSource


class RandomRoad(SignalSource):
    def __init__(
        self,
        component_id: str,
        *,
        amplitude: float,
        roughness: float,
        seed: int,
        vehicle_speed: float,
        dt: float,
        duration: float,
        max_height: float | None = None,
        max_slope: float | None = None,
        min_feature_width: float = 0.0,
        wheel_radius_reference: float = 0.0,
        generation_mode: str = "filtered_noise",
        name: str = "Random Road",
    ) -> None:
        super().__init__(component_id, name=name)
        if generation_mode not in {"filtered_noise", "control_points"}:
            raise ValueError(
                f"Unknown generation_mode {generation_mode!r}; "
                "expected 'filtered_noise' or 'control_points'."
            )
        # Coordinate min_feature_width with wheel_radius_reference: a road
        # populated with features narrower than the contacting wheel diameter
        # produces non-physical excitation (the wheel cannot resolve sub-2R
        # detail). When the user supplies a wheel reference, take the larger
        # of the two limits — user agency preserved, but feature width never
        # falls below 2R.
        effective_feature_width = max(
            float(min_feature_width),
            2.0 * float(wheel_radius_reference),
        )
        self.parameters.update(
            {
                "amplitude": amplitude,
                "roughness": roughness,
                "seed": float(seed),
                "vehicle_speed": vehicle_speed,
                "dt": dt,
                "duration": duration,
                "max_height": max_height,
                "max_slope": max_slope,
                "min_feature_width": float(min_feature_width),
                "wheel_radius_reference": float(wheel_radius_reference),
                "effective_feature_width": effective_feature_width,
                "generation_mode": generation_mode,
            }
        )
        step_count = max(int(duration / dt) + 1, 2)
        self._time = [index * dt for index in range(step_count)]
        self._distance = [time * self.parameters["vehicle_speed"] for time in self._time]
        self._road = self._generate_profile()

    def _generate_profile(self):
        # Faz 4c — Generation algorithm switch.
        # 'filtered_noise' (default): legacy IIR-filtered Gaussian noise.
        # 'control_points':           PCHIP-interpolated random control points.
        # Both algorithms feed the same Faz 4b post-processing pipeline
        # (feature-width smoothing → slope limiting → height clamp), so
        # max_height/max_slope/min_feature_width work identically in both modes.
        if self.parameters["generation_mode"] == "control_points":
            road = self._generate_control_points_profile()
        else:
            road = self._generate_filtered_noise_profile()
        # Post-processing (Faz 4b) — no-op when bound parameters are at defaults.
        road = self._apply_feature_width_smoothing(road)
        road = self._apply_slope_limit(road)
        road = self._apply_height_clamp(road)
        return road

    def _generate_filtered_noise_profile(self) -> list[float]:
        """Legacy generation: IIR-filtered Gaussian noise scaled by amplitude.

        Behavior is bit-for-bit identical to the pre-Faz-4c implementation when
        the bound parameters (max_height/max_slope/min_feature_width) are also
        at their defaults.
        """
        sample_count = len(self._distance)
        alpha = pow(2.718281828, -self.parameters["roughness"] * self.parameters["dt"])
        if np is not None and signal is not None:
            rng = np.random.default_rng(int(self.parameters["seed"]))
            noise = rng.standard_normal(sample_count)
            road = signal.lfilter([1.0 - alpha], [1.0, -alpha], noise)
            road *= self.parameters["amplitude"]
            return road.tolist()
        rng = random.Random(int(self.parameters["seed"]))
        road: list[float] = []
        filtered = 0.0
        for _ in range(sample_count):
            white = rng.gauss(0.0, 1.0)
            filtered = alpha * filtered + (1.0 - alpha) * white
            road.append(filtered * self.parameters["amplitude"])
        return road

    def _generate_control_points_profile(self) -> list[float]:
        """Control-points generation: PCHIP-interpolate random control samples.

        Why PCHIP: a piecewise cubic Hermite interpolant is monotonic between
        knots — it does not overshoot or oscillate as a generic cubic spline
        would.  That matches what a real road profile looks like (smooth, no
        ringing) and keeps slope_at_distance well-behaved.

        Number of control points is chosen automatically from the road length
        and roughness (see _control_point_count). The control points themselves
        are independent Gaussian samples scaled by amplitude — the seed and
        amplitude semantics match filtered_noise so users can switch modes
        without re-tuning amplitude.
        """
        sample_count = len(self._distance)
        if sample_count < 2:
            return [0.0] * sample_count

        n_control = self._control_point_count()
        last_distance = self._distance[-1]
        if last_distance <= 0.0 or n_control < 2:
            return [0.0] * sample_count

        if np is not None:
            rng = np.random.default_rng(int(self.parameters["seed"]))
            control_heights = rng.standard_normal(n_control) * self.parameters["amplitude"]
            control_heights = control_heights.tolist()
        else:
            rng = random.Random(int(self.parameters["seed"]))
            control_heights = [
                rng.gauss(0.0, 1.0) * self.parameters["amplitude"]
                for _ in range(n_control)
            ]

        control_x = [
            (i / float(n_control - 1)) * last_distance for i in range(n_control)
        ]

        try:
            from scipy.interpolate import PchipInterpolator
            interpolator = PchipInterpolator(control_x, control_heights)
            road = [float(interpolator(x)) for x in self._distance]
        except ImportError:
            # Fallback: linear interpolation. Slope discontinuities at knots
            # are then smoothed out by _apply_slope_limit if max_slope is set.
            road = [self._linear_interpolate(x, control_x, control_heights)
                    for x in self._distance]
        return road

    def _control_point_count(self) -> int:
        """Auto-pick number of control points from duration and roughness.

        Heuristic: smoother road -> fewer, longer features; rougher road ->
        more, shorter features.

            typical_feature_length = 2.0 / max(roughness, 0.01)   [meters]
            n = ceil(road_length_meters / typical_feature_length)

        Bounded:
          * lower bound 8 (need enough knots for PCHIP to be meaningful)
          * upper bound (sample_count // 2) so each control point is backed
            by at least 2 raw samples
          * coordinated with effective_feature_width: spacing >= that width
            (we never place control points closer together than the wheel
            can resolve, otherwise post-pipeline smoothing wipes them out
            anyway).
        """
        road_length = self._distance[-1]
        roughness = max(float(self.parameters["roughness"]), 0.01)
        typical_feature_length = 2.0 / roughness
        raw = int(road_length / typical_feature_length) + 1

        n = max(raw, 8)
        sample_count = len(self._distance)
        n = min(n, max(sample_count // 2, 2))

        feature_width = self.parameters["effective_feature_width"]
        if feature_width > 0.0 and road_length > 0.0:
            max_n_for_feature_width = int(road_length / feature_width) + 1
            n = min(n, max(max_n_for_feature_width, 2))

        return max(n, 2)

    @staticmethod
    def _linear_interpolate(x: float, xs: list[float], ys: list[float]) -> float:
        """Plain linear interpolation between sorted (xs, ys) knots."""
        if x <= xs[0]:
            return ys[0]
        if x >= xs[-1]:
            return ys[-1]
        for i in range(1, len(xs)):
            if x <= xs[i]:
                ratio = (x - xs[i - 1]) / max(xs[i] - xs[i - 1], 1e-12)
                return ys[i - 1] * (1.0 - ratio) + ys[i] * ratio
        return ys[-1]

    def _apply_feature_width_smoothing(self, road: list[float]) -> list[float]:
        """Suppress features narrower than `effective_feature_width` via a
        moving-average low-pass (window sized in samples)."""
        feature_width = self.parameters["effective_feature_width"]
        if feature_width <= 0.0 or len(road) < 3:
            return road
        # Sample spacing in distance: dx = V * dt
        dx = max(self.parameters["vehicle_speed"] * self.parameters["dt"], 1e-12)
        window_samples = int(round(feature_width / dx))
        if window_samples < 2:
            return road
        # Symmetric moving average; clamp window to profile length.
        window_samples = min(window_samples, len(road))
        half = window_samples // 2
        smoothed: list[float] = []
        n = len(road)
        for i in range(n):
            lo = max(0, i - half)
            hi = min(n, i + half + 1)
            window = road[lo:hi]
            smoothed.append(sum(window) / len(window))
        return smoothed

    def _apply_slope_limit(self, road: list[float]) -> list[float]:
        """Iteratively soften any segment whose slope exceeds max_slope.

        On each pass we walk the profile, locate any |du/dx| > max_slope and
        relax the offending sample toward the average of its neighbors. The
        process repeats until no segment violates the limit (capped at a
        fixed iteration budget so a pathological input cannot loop forever)."""
        max_slope = self.parameters["max_slope"]
        if max_slope is None or len(road) < 3:
            return road
        max_slope = float(max_slope)
        if max_slope <= 0.0:
            return road
        dx = max(self.parameters["vehicle_speed"] * self.parameters["dt"], 1e-12)
        max_step = max_slope * dx  # max permissible |u[i] - u[i-1]|
        result = list(road)
        # Iteration budget: enough to propagate corrections across the whole
        # profile under realistic inputs; small enough to bound worst-case time.
        max_iterations = 200
        for _iteration in range(max_iterations):
            violated = False
            for i in range(1, len(result)):
                step = result[i] - result[i - 1]
                if abs(step) > max_step:
                    violated = True
                    # Pull the offending sample halfway toward its neighbor;
                    # repeated passes converge on a slope-limited profile
                    # without introducing sharp clipping artifacts.
                    correction = (abs(step) - max_step) * 0.5
                    if step > 0:
                        result[i] -= correction
                    else:
                        result[i] += correction
            if not violated:
                break
        return result

    def _apply_height_clamp(self, road: list[float]) -> list[float]:
        """Symmetric clamp: |u(x)| <= max_height."""
        max_height = self.parameters["max_height"]
        if max_height is None:
            return road
        max_height = float(max_height)
        if max_height < 0.0:
            return road  # nonsensical; treat as disabled
        return [max(-max_height, min(max_height, value)) for value in road]

    def spatial_profile(self, distance: float) -> float:
        if distance <= self._distance[0]:
            return float(self._road[0])
        if distance >= self._distance[-1]:
            return float(self._road[-1])
        for index in range(1, len(self._distance)):
            left = self._distance[index - 1]
            right = self._distance[index]
            if distance <= right:
                ratio = (distance - left) / max(right - left, 1e-12)
                return float(self._road[index - 1] * (1.0 - ratio) + self._road[index] * ratio)
        return float(self._road[-1])

    # ------------------------------------------------------------------
    # Faz 4a — Spatial API (wheel-aware road consumers)
    # ------------------------------------------------------------------
    #
    # The methods below expose the road profile in the **distance** domain,
    # which is the natural argument for any road–wheel contact computation.
    # They live alongside the time-domain API (displacement_output,
    # velocity_output) which remains the InputRouter-facing interface.
    #
    # Relation:   u_t(t) = u_x(V*t),    du/dt = V * du/dx
    # so a consumer that has a wheel at horizontal position x can call
    # height_at_distance(x) directly without going through vehicle_speed.

    def height_at_distance(self, x: float) -> float:
        """Return road profile height u(x) at horizontal distance x [m].

        Outside the sampled domain [0, V*duration] the value clamps to the
        nearest boundary sample (matches spatial_profile semantics).
        """
        return self.spatial_profile(float(x))

    def slope_at_distance(self, x: float) -> float:
        """Return road profile slope du/dx at horizontal distance x [m/m].

        Computed via central finite differences against the stored profile
        samples; uses one-sided differences at the endpoints. Outside the
        sampled domain the value clamps to the nearest boundary slope.
        """
        gradients = self._spatial_gradients()
        target_distance = float(x)
        if target_distance <= self._distance[0]:
            return float(gradients[0])
        if target_distance >= self._distance[-1]:
            return float(gradients[-1])
        for index in range(1, len(self._distance)):
            left = self._distance[index - 1]
            right = self._distance[index]
            if target_distance <= right:
                ratio = (target_distance - left) / max(right - left, 1e-12)
                return float(gradients[index - 1] * (1.0 - ratio) + gradients[index] * ratio)
        return float(gradients[-1])

    def _spatial_gradients(self) -> list[float]:
        """Compute du/dx at every stored sample (cached on first call)."""
        cached = getattr(self, "_cached_gradients", None)
        if cached is not None:
            return cached
        gradients: list[float] = []
        for index, value in enumerate(self._road):
            if index == 0:
                dv = self._road[1] - value
                dx = self._distance[1] - self._distance[0]
            elif index == len(self._road) - 1:
                dv = value - self._road[index - 1]
                dx = self._distance[index] - self._distance[index - 1]
            else:
                dv = self._road[index + 1] - self._road[index - 1]
                dx = self._distance[index + 1] - self._distance[index - 1]
            gradients.append(dv / max(dx, 1e-12))
        self._cached_gradients = gradients
        return gradients

    # ------------------------------------------------------------------

    def displacement_output(self, time: float) -> float:
        return self.spatial_profile(self.parameters["vehicle_speed"] * time)

    def velocity_output(self, time: float) -> float:
        gradients: list[float] = []
        for index, value in enumerate(self._road):
            if index == 0:
                dv = self._road[1] - value
                dx = self._distance[1] - self._distance[0]
            elif index == len(self._road) - 1:
                dv = value - self._road[index - 1]
                dx = self._distance[index] - self._distance[index - 1]
            else:
                dv = self._road[index + 1] - self._road[index - 1]
                dx = self._distance[index + 1] - self._distance[index - 1]
            gradients.append(dv / max(dx, 1e-12))
        target_distance = self.parameters["vehicle_speed"] * time
        if target_distance <= self._distance[0]:
            return gradients[0] * self.parameters["vehicle_speed"]
        if target_distance >= self._distance[-1]:
            return gradients[-1] * self.parameters["vehicle_speed"]
        for index in range(1, len(self._distance)):
            left = self._distance[index - 1]
            right = self._distance[index]
            if target_distance <= right:
                ratio = (target_distance - left) / max(right - left, 1e-12)
                value = gradients[index - 1] * (1.0 - ratio) + gradients[index] * ratio
                return value * self.parameters["vehicle_speed"]
        return gradients[-1] * self.parameters["vehicle_speed"]

    def constitutive_equations(self) -> list[str]:
        return [
            f"r_{self.id}(t) = filtered_white_noise(seed={int(self.parameters['seed'])})",
            f"dr_{self.id}/dt = road_velocity({self.id}, t)",
        ]

    # ------------------------------------------------------------------
    # Wave 1 polymorphic interface
    # ------------------------------------------------------------------

    def get_source_descriptor(self) -> SourceDescriptor:
        """RandomRoad injects a stochastic displacement profile at its output port.

        Displacement-source semantics: the InputRouter will route this into
        the constraint/input vector as a kinematic excitation rather than a
        force injection.
        """
        from app.core.base.source_descriptor import SourceDescriptor
        return SourceDescriptor(
            kind="displacement",
            driven_port_name="port",
            reference_port_name="reference_port",
            input_variable_name=f"u_{self.id}",
            amplitude_parameter="amplitude",
        )
