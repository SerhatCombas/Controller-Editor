#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from abc import ABC, abstractmethod


class BaseModel(ABC):
    name = "Base Model"
    signal_labels = {
        "primary_signal": "Primary Signal",
        "secondary_signal": "Secondary Signal",
        "u_control": "u_control(t)",
        "u_total": "u_total(t)",
    }
    info_labels = {
        "s": "State 1",
        "phi": "State 2",
        "disturbance": "Disturbance",
    }
    control_limit = 10.0
    viewport_padding_ratio = 0.08

    @abstractmethod
    def reset(self, excitation):
        raise NotImplementedError

    @abstractmethod
    def get_state_vector(self):
        raise NotImplementedError

    @abstractmethod
    def step(self, dt, control_input, excitation):
        raise NotImplementedError

    @abstractmethod
    def linear_state_space(self):
        raise NotImplementedError

    @abstractmethod
    def world_bounds(self):
        raise NotImplementedError

    @abstractmethod
    def render(self, surface, viewport):
        raise NotImplementedError

    @abstractmethod
    def compute_pid_control(self, components, gains, integral_error, dt):
        raise NotImplementedError

    @abstractmethod
    def display_values(self):
        raise NotImplementedError

    @abstractmethod
    def signal_values(self):
        raise NotImplementedError
