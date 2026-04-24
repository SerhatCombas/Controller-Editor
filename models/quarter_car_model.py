#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import math
import random

import numpy as np
import pygame

from models.base_model import BaseModel
from models.rendering import WorldBounds


def build_quarter_car_state_space_matrices(
    body_mass=320.0,
    wheel_mass=45.0,
    suspension_stiffness=18000.0,
    suspension_damping=1400.0,
    tire_stiffness=160000.0,
    tire_damping=1200.0,
):
    A = np.array([
        [0.0, 1.0, 0.0, 0.0],
        [-suspension_stiffness / body_mass, -suspension_damping / body_mass, suspension_stiffness / body_mass, suspension_damping / body_mass],
        [0.0, 0.0, 0.0, 1.0],
        [suspension_stiffness / wheel_mass, suspension_damping / wheel_mass, -(suspension_stiffness + tire_stiffness) / wheel_mass, -(suspension_damping + tire_damping) / wheel_mass],
    ])
    B = np.array([
        [0.0],
        [1.0 / body_mass],
        [0.0],
        [-1.0 / wheel_mass],
    ])
    C = np.array([
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
    ])
    D = np.zeros((2, 1))
    return A, B, C, D


class QuarterCarRoadProfile:
    def __init__(self, seed=42):
        rng = random.Random(seed)
        self.terms = []
        for _ in range(7):
            amplitude = rng.uniform(0.003, 0.018)
            frequency = rng.uniform(0.08, 0.45)
            phase = rng.uniform(0.0, 2.0 * math.pi)
            self.terms.append((amplitude, frequency, phase))

    def sample(self, x):
        return sum(amplitude * math.sin(2.0 * math.pi * frequency * x + phase) for amplitude, frequency, phase in self.terms)

    def derivative(self, x):
        return sum(
            amplitude * 2.0 * math.pi * frequency * math.cos(2.0 * math.pi * frequency * x + phase)
            for amplitude, frequency, phase in self.terms
        )


class QuarterCarModel(BaseModel):
    name = "Mass-Spring-Damper with Wheel"
    signal_labels = {
        "primary_signal": "z2(t) [mm]",
        "secondary_signal": "z1(t) [mm]",
        "u_control": "u_control(t) [N]",
        "u_total": "road force proxy",
    }
    info_labels = {
        "s": "Body Position z2",
        "phi": "Wheel Position z1",
        "disturbance": "Road Profile h",
    }
    control_limit = 4500.0

    def __init__(self):
        self.body_mass = 320.0
        self.wheel_mass = 45.0
        self.suspension_stiffness = 18000.0
        self.suspension_damping = 1400.0
        self.tire_stiffness = 160000.0
        self.tire_damping = 1200.0
        self.road_speed = 6.0
        self.visual_motion_gain = 6.0
        self.road_span_m = 5.8
        self.body_center_y_m = 1.28
        self.wheel_center_y_m = 0.22
        self.ground_y_m = -0.82
        self.wheel_radius_m = 0.34
        self.body_width_m = 1.50
        self.body_height_m = 0.34
        self.wheel_block_width_m = 0.66
        self.wheel_block_height_m = 0.28
        self.spring_offset_m = 0.46
        self.damper_offset_m = -0.46
        self.road = QuarterCarRoadProfile()
        self.reset({})

    def reset(self, excitation):
        self.z2 = 0.0
        self.z2_dot = 0.0
        self.z1 = 0.0
        self.z1_dot = 0.0
        self.road_position = 0.0
        self.last_road_height = 0.0
        self.last_road_velocity = 0.0

        mode = excitation.get("mode", "Baslangic Acisi")
        if mode == "Baslangic Acisi":
            self.z2 = math.radians(excitation.get("angle_deg", 8.0)) * 0.03
        elif mode == "Baslangic Acisal Hiz":
            self.z2_dot = excitation.get("angular_velocity", 0.0) * 0.04
        elif mode == "Dis Girdi (Step)":
            self.road_position = excitation.get("step_time", 0.0)

    def get_state_vector(self):
        return [self.z2, self.z2_dot, self.z1, self.z1_dot]

    def compute_pid_control(self, components, gains, integral_error, dt):
        error = -self.z2
        error_rate = -self.z2_dot
        new_integral = integral_error + error * dt
        new_integral = max(min(new_integral, 0.75), -0.75)

        force = 0.0
        if components.get("P", False):
            force += gains.get("P", 0.0) * 180.0 * error
        if components.get("I", False):
            force += gains.get("I", 0.0) * 260.0 * new_integral
        if components.get("D", False):
            force += gains.get("D", 0.0) * 85.0 * error_rate
        force += -120.0 * (self.z2 - self.z1) - 30.0 * (self.z2_dot - self.z1_dot)
        return force, new_integral

    def step(self, dt, control_input, excitation):
        self.road_position += self.road_speed * dt
        h = self.road.sample(self.road_position)
        h_dot = self.road.derivative(self.road_position) * self.road_speed
        self.last_road_height = h
        self.last_road_velocity = h_dot

        z2_ddot = (
            -self.suspension_stiffness * (self.z2 - self.z1)
            - self.suspension_damping * (self.z2_dot - self.z1_dot)
            + control_input
        ) / self.body_mass
        z1_ddot = (
            self.suspension_stiffness * (self.z2 - self.z1)
            + self.suspension_damping * (self.z2_dot - self.z1_dot)
            - self.tire_stiffness * (self.z1 - h)
            - self.tire_damping * (self.z1_dot - h_dot)
            - control_input
        ) / self.wheel_mass

        self.z2_dot += z2_ddot * dt
        self.z2 += self.z2_dot * dt
        self.z1_dot += z1_ddot * dt
        self.z1 += self.z1_dot * dt
        return control_input, h

    def linear_state_space(self):
        return build_quarter_car_state_space_matrices(
            body_mass=self.body_mass,
            wheel_mass=self.wheel_mass,
            suspension_stiffness=self.suspension_stiffness,
            suspension_damping=self.suspension_damping,
            tire_stiffness=self.tire_stiffness,
            tire_damping=self.tire_damping,
        )

    def display_values(self):
        return {
            "s": f"z2 = {self.z2 * 1000.0:.2f} mm",
            "phi": f"z1 = {self.z1 * 1000.0:.2f} mm",
            "disturbance": f"h = {self.last_road_height * 1000.0:.2f} mm",
        }

    def signal_values(self):
        return {
            "primary_signal": self.z2 * 1000.0,
            "secondary_signal": self.z1 * 1000.0,
            "disturbance": self.last_road_height * 1000.0,
        }

    def world_bounds(self):
        return WorldBounds(min_x=-2.9, max_x=2.9, min_y=-1.25, max_y=2.85)

    def render(self, surface, viewport):
        white = (245, 245, 245)
        black = (20, 20, 20)
        dark_gray = (80, 80, 80)
        light_gray = (220, 228, 236)
        blue = (56, 120, 196)
        green = (0, 150, 90)
        spring_color = (60, 60, 60)

        surface.fill(white)
        font = pygame.font.SysFont("Arial", viewport.font_size(0.16, minimum=14, maximum=30))
        small_font = pygame.font.SysFont("Arial", viewport.font_size(0.11, minimum=11, maximum=22))
        outline_width = viewport.line_width(0.018, minimum=1)

        body_center = (0.0, self.body_center_y_m - self.z2 * self.visual_motion_gain)
        wheel_block_center = (0.0, self.wheel_center_y_m - self.z1 * self.visual_motion_gain)
        wheel_center = (0.0, wheel_block_center[1] - 0.40)

        road_points = []
        for index in range(121):
            world_x = -self.road_span_m / 2.0 + self.road_span_m * index / 120.0
            road_y = self.ground_y_m + self.road.sample(self.road_position + world_x)
            road_points.append(viewport.world_to_screen((world_x, road_y)))
        pygame.draw.lines(surface, dark_gray, False, road_points, viewport.line_width(0.03, minimum=2))
        pygame.draw.line(
            surface,
            (170, 170, 170),
            viewport.world_to_screen((-self.road_span_m / 2.0, self.ground_y_m - 0.12)),
            viewport.world_to_screen((self.road_span_m / 2.0, self.ground_y_m - 0.12)),
            viewport.line_width(0.015, minimum=1),
        )

        body_rect = viewport.rect_from_center(body_center, self.body_width_m, self.body_height_m)
        pygame.draw.rect(surface, light_gray, body_rect, border_radius=6)
        pygame.draw.rect(surface, black, body_rect, outline_width, border_radius=6)

        wheel_rect = viewport.rect_from_center(wheel_block_center, self.wheel_block_width_m, self.wheel_block_height_m)
        pygame.draw.rect(surface, blue, wheel_rect, border_radius=8)
        pygame.draw.rect(surface, black, wheel_rect, outline_width, border_radius=8)
        wheel_center_px = viewport.world_to_screen(wheel_center)
        wheel_radius_px = viewport.length_to_screen(self.wheel_radius_m, minimum=8)
        pygame.draw.circle(surface, black, wheel_center_px, wheel_radius_px, viewport.line_width(0.03, minimum=2))
        pygame.draw.circle(surface, green, wheel_center_px, max(4, viewport.length_to_screen(0.05)))

        top_anchor_y = body_center[1] - self.body_height_m / 2.0
        bottom_anchor_y = wheel_block_center[1] + self.wheel_block_height_m / 2.0 - 0.04
        self._draw_spring(surface, viewport, self.spring_offset_m, top_anchor_y, bottom_anchor_y, spring_color)
        self._draw_damper(surface, viewport, self.damper_offset_m, top_anchor_y, bottom_anchor_y, black)
        pygame.draw.line(
            surface,
            black,
            viewport.world_to_screen((0.0, body_center[1] - self.body_height_m / 2.0)),
            viewport.world_to_screen((0.0, wheel_block_center[1] + self.wheel_block_height_m / 2.0)),
            viewport.line_width(0.025, minimum=2),
        )

        surface.blit(font.render("Quarter-Car Active Suspension", True, black), viewport.world_to_screen((-2.45, 2.38)))
        surface.blit(small_font.render("m_A", True, black), viewport.world_to_screen((body_center[0] - 0.55, body_center[1] + 0.02)))
        surface.blit(small_font.render("m_R", True, black), viewport.world_to_screen((wheel_block_center[0] - 0.56, wheel_block_center[1] - 0.02)))
        surface.blit(small_font.render("h(x-vt)", True, black), viewport.world_to_screen((1.85, self.ground_y_m + 0.10)))
        surface.blit(small_font.render("z2", True, black), viewport.world_to_screen((body_center[0] + 0.72, body_center[1] + 0.02)))
        surface.blit(small_font.render("z1", True, black), viewport.world_to_screen((wheel_block_center[0] + 0.72, wheel_block_center[1] - 0.02)))

    def _draw_spring(self, surface, viewport, x, y_top, y_bottom, color):
        segments = 8
        points = [viewport.world_to_screen((x, y_top))]
        span = max(y_top - y_bottom, 0.25)
        for index in range(1, segments):
            offset = 0.12 if index % 2 else -0.12
            y = y_top - span * index / segments
            points.append(viewport.world_to_screen((x + offset, y)))
        points.append(viewport.world_to_screen((x, y_bottom)))
        pygame.draw.lines(surface, color, False, points, viewport.line_width(0.025, minimum=2))

    def _draw_damper(self, surface, viewport, x, y_top, y_bottom, color):
        mid_y = (y_top + y_bottom) / 2.0
        pygame.draw.line(
            surface,
            color,
            viewport.world_to_screen((x, y_top)),
            viewport.world_to_screen((x, mid_y + 0.12)),
            viewport.line_width(0.025, minimum=2),
        )
        piston_rect = viewport.rect_from_center((x, mid_y + 0.04), 0.18, 0.10)
        pygame.draw.rect(surface, color, piston_rect, viewport.line_width(0.012, minimum=1))
        pygame.draw.line(
            surface,
            color,
            viewport.world_to_screen((x, mid_y - 0.02)),
            viewport.world_to_screen((x, y_bottom)),
            viewport.line_width(0.025, minimum=2),
        )
