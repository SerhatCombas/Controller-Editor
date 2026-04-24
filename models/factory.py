#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from models.pendulum_model import PendulumModel
from models.quarter_car_model import QuarterCarModel

MODEL_PENDULUM = "Motor-Belt-Pendulum"
MODEL_QUARTER_CAR = "Mass-Spring-Damper with Wheel"


def create_model(model_name):
    if model_name == MODEL_QUARTER_CAR:
        return QuarterCarModel()
    return PendulumModel()


def get_model_names():
    return [MODEL_PENDULUM, MODEL_QUARTER_CAR]


def get_default_state_feedback_gains(model_name):
    if model_name == MODEL_QUARTER_CAR:
        return [1800.0, 260.0, -900.0, -90.0]
    return [1.6, 2.4, 34.0, 7.5]


def get_default_lqr_weights(model_name):
    if model_name == MODEL_QUARTER_CAR:
        return [1800.0, 40.0, 900.0, 25.0], 0.35
    return [1.0, 1.0, 100.0, 10.0], 0.01


def get_linear_state_space(model_name):
    model = create_model(model_name)
    return model.linear_state_space()
