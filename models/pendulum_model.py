#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import math

import numpy as np
import pygame

from models.base_model import BaseModel
from models.rendering import WorldBounds


def build_pendulum_state_space_matrices(
    cart_mass=1.2,
    pendulum_mass=0.25,
    pendulum_length=0.6,
    gravity=9.81,
):
    A = np.array([
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, -(pendulum_mass * gravity) / cart_mass, 0.0],
        [0.0, 0.0, 0.0, 1.0],
        [0.0, 0.0, ((cart_mass + pendulum_mass) * gravity) / (cart_mass * pendulum_length), 0.0],
    ])
    B = np.array([
        [0.0],
        [1.0 / cart_mass],
        [0.0],
        [-1.0 / (cart_mass * pendulum_length)],
    ])
    C = np.array([
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
    ])
    D = np.zeros((2, 1))
    return A, B, C, D


class PendulumModel(BaseModel):
    name = "Motor-Belt-Pendulum"
    signal_labels = {
        "primary_signal": "phi(t) [deg]",
        "secondary_signal": "s(t) [m]",
        "u_control": "u_control(t) [N]",
        "u_total": "u_total(t) [N]",
    }
    info_labels = {
        "s": "Cart Position",
        "phi": "Pendulum Angle",
        "disturbance": "Disturbance",
    }
    control_limit = 14.0

    def __init__(self):
        self.gravity = 9.81
        self.cart_mass = 1.2
        self.pendulum_mass = 0.25
        self.pendulum_length_m = 0.6
        self.track_half_span_m = 1.65
        self.motor_center_x_m = 1.78
        self.motor_body_width_m = 0.30
        self.motor_body_height_m = 0.24
        self.motor_head_width_m = 0.12
        self.motor_head_height_m = 0.14
        self.pulley_radius_m = 0.11
        self.cart_width_m = 0.42
        self.cart_height_m = 0.20
        self.cart_base_y_m = 0.12
        self.rail_margin_m = 0.08
        self.belt_y_m = 0.0
        self.cart_damping = 0.12
        self.pendulum_damping = 0.04
        self.reset({})

    def reset(self, excitation):
        self.s = 0.0
        self.s_dot = 0.0
        self.phi = 0.0
        self.phi_dot = 0.0
        self.last_disturbance = 0.0
        self.elapsed_time = 0.0

        mode = excitation.get("mode", "Baslangic Acisi")
        if mode == "Baslangic Acisi":
            self.phi = math.radians(excitation.get("angle_deg", 8.0))
        elif mode == "Baslangic Acisal Hiz":
            self.phi_dot = excitation.get("angular_velocity", 0.0)

    def get_state_vector(self):
        return [self.s, self.s_dot, self.phi, self.phi_dot]

    def compute_pid_control(self, components, gains, integral_error, dt):
        theta_error = -self.phi
        theta_dot_error = -self.phi_dot
        new_integral = integral_error + theta_error * dt
        new_integral = max(min(new_integral, 2.5), -2.5)

        force = 0.0
        if components.get("P", False):
            force += gains.get("P", 0.0) * theta_error
        if components.get("I", False):
            force += gains.get("I", 0.0) * new_integral
        if components.get("D", False):
            force += gains.get("D", 0.0) * theta_dot_error

        force += -0.35 * self.s - 0.9 * self.s_dot
        return force, new_integral

    def step(self, dt, control_input, excitation):
        self.elapsed_time += dt
        disturbance_force = self._disturbance_force(excitation, dt)
        total_force = control_input + disturbance_force
        s_ddot, phi_ddot = self._dynamics(total_force)

        self.s_dot += s_ddot * dt
        self.s += self.s_dot * dt
        self.phi_dot += phi_ddot * dt
        self.phi += self.phi_dot * dt
        while self.phi > math.pi:
            self.phi -= 2 * math.pi
        while self.phi < -math.pi:
            self.phi += 2 * math.pi
        return total_force, disturbance_force

    def linear_state_space(self):
        return build_pendulum_state_space_matrices(
            cart_mass=self.cart_mass,
            pendulum_mass=self.pendulum_mass,
            pendulum_length=self.pendulum_length_m,
            gravity=self.gravity,
        )

    def display_values(self):
        return {
            "s": f"{self.s:.3f} m",
            "phi": f"{math.degrees(self.phi):.2f} deg",
            "disturbance": f"{self.last_disturbance:.2f} N",
        }

    def signal_values(self):
        return {
            "primary_signal": math.degrees(self.phi),
            "secondary_signal": self.s,
            "disturbance": self.last_disturbance,
        }

    def world_bounds(self):
        return WorldBounds(min_x=-2.35, max_x=2.35, min_y=-0.55, max_y=2.15)

    def render(self, surface, viewport):
        white = (245, 245, 245)
        black = (20, 20, 20)
        gray = (130, 130, 130)
        dark_gray = (80, 80, 80)
        green = (0, 170, 0)
        light_gray = (210, 210, 210)
        motor = (120, 120, 120)
        red = (180, 50, 50)

        surface.fill(white)
        line_width = viewport.line_width(0.035, minimum=2)
        outline_width = viewport.line_width(0.02, minimum=1)
        pulley_r = viewport.length_to_screen(self.pulley_radius_m, minimum=6)

        left_pulley = (-self.track_half_span_m, self.belt_y_m)
        right_pulley = (self.track_half_span_m, self.belt_y_m)
        cart_center = (self.s, self.cart_base_y_m)
        pivot = cart_center
        tip = (
            pivot[0] + self.pendulum_length_m * math.sin(self.phi),
            pivot[1] + self.pendulum_length_m * math.cos(self.phi),
        )

        pygame.draw.line(surface, dark_gray, viewport.world_to_screen(left_pulley), viewport.world_to_screen(right_pulley), line_width)
        for pulley in (left_pulley, right_pulley):
            pygame.draw.circle(surface, light_gray, viewport.world_to_screen(pulley), pulley_r)
            pygame.draw.circle(surface, black, viewport.world_to_screen(pulley), pulley_r, outline_width)
            pygame.draw.circle(surface, green, viewport.world_to_screen(pulley), max(3, pulley_r // 4))

        cart_rect = viewport.rect_from_center(cart_center, self.cart_width_m, self.cart_height_m)
        pygame.draw.rect(surface, light_gray, cart_rect)
        pygame.draw.rect(surface, black, cart_rect, outline_width)

        pygame.draw.circle(surface, green, viewport.world_to_screen(pivot), max(3, viewport.length_to_screen(0.03)))

        pivot_x, pivot_y = viewport.world_to_screen(pivot)
        tip_x, tip_y = viewport.world_to_screen(tip)
        rod_color = red if abs(self.phi) > math.radians(60) else black
        pygame.draw.line(surface, rod_color, (pivot_x, pivot_y), (tip_x, tip_y), viewport.line_width(0.025, minimum=2))
        pygame.draw.circle(surface, rod_color, (tip_x, tip_y), max(4, viewport.length_to_screen(0.04)))

        arc_radius = viewport.length_to_screen(0.20, minimum=18)
        arc_rect = pygame.Rect(pivot_x - arc_radius, pivot_y - arc_radius, arc_radius * 2, arc_radius * 2)
        pygame.draw.arc(surface, gray, arc_rect, -math.pi / 2 - self.phi, -math.pi / 2, 2)

        motor_center = (self.motor_center_x_m, self.belt_y_m + 0.01)
        motor_rect = viewport.rect_from_center(motor_center, self.motor_body_width_m, self.motor_body_height_m)
        motor_head_rect = viewport.rect_from_center(
            (self.motor_center_x_m - 0.18, self.belt_y_m + 0.01),
            self.motor_head_width_m,
            self.motor_head_height_m,
        )
        pygame.draw.rect(surface, motor, motor_rect, border_radius=max(4, outline_width * 2))
        pygame.draw.rect(surface, light_gray, motor_head_rect, border_radius=max(3, outline_width * 2))
        pygame.draw.line(
            surface,
            black,
            viewport.world_to_screen((self.motor_center_x_m - 0.30, self.belt_y_m + 0.01)),
            viewport.world_to_screen((self.motor_center_x_m - 0.24, self.belt_y_m + 0.01)),
            line_width,
        )

        font = pygame.font.SysFont("Arial", viewport.font_size(0.16, minimum=14, maximum=30))
        small_font = pygame.font.SysFont("Arial", viewport.font_size(0.12, minimum=11, maximum=24))
        surface.blit(font.render("Motor - Belt - Pendulum Simulation", True, black), viewport.world_to_screen((-1.85, 1.72)))
        surface.blit(small_font.render("s(t)", True, black), viewport.world_to_screen((cart_center[0] - 0.22, -0.34)))
        surface.blit(small_font.render("phi(t)", True, black), viewport.world_to_screen((pivot[0] + 0.34, pivot[1] + 0.56)))
        surface.blit(small_font.render("U_M(t)", True, black), viewport.world_to_screen((self.motor_center_x_m - 0.05, -0.28)))

    def max_travel_m(self):
        return self.track_half_span_m - self.pulley_radius_m - self.cart_width_m / 2.0 - self.rail_margin_m

    def _dynamics(self, force):
        sin_phi = math.sin(self.phi)
        cos_phi = math.cos(self.phi)
        total_mass = self.cart_mass + self.pendulum_mass
        polemass_length = self.pendulum_mass * self.pendulum_length_m

        temp = (force + polemass_length * self.phi_dot * self.phi_dot * sin_phi) / total_mass
        phi_ddot = (
            self.gravity * sin_phi - cos_phi * temp
        ) / (
            self.pendulum_length_m * (4.0 / 3.0 - (self.pendulum_mass * cos_phi * cos_phi) / total_mass)
        )
        s_ddot = temp - (polemass_length * phi_ddot * cos_phi) / total_mass
        s_ddot -= self.cart_damping * self.s_dot
        phi_ddot -= self.pendulum_damping * self.phi_dot
        return s_ddot, phi_ddot

    def _disturbance_force(self, excitation, _dt):
        mode = excitation.get("mode", "Baslangic Acisi")
        if mode == "Dis Girdi (Step)" and self.elapsed_time >= excitation.get("step_time", 1.0):
            return excitation.get("step_force", 2.0)
        return 0.0
