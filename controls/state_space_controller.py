#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np


class StateSpaceController:
    """Simple state-space feedback controller with u = -Kx.

    State order:
        x = [s, s_dot, phi, phi_dot]
    """

    def __init__(self, gains=None):
        default_gains = [1.6, 2.4, 34.0, 7.5]
        self.set_gains(gains or default_gains)

    def set_gains(self, gains):
        if len(gains) != 4:
            raise ValueError("State-space gain vector K must contain 4 values.")
        self.gains = np.array(gains, dtype=float)

    def compute_control(self, state):
        state_vector = np.array(state, dtype=float)
        return float(-np.dot(self.gains, state_vector))
