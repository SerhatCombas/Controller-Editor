#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from dataclasses import dataclass

import pygame


@dataclass(frozen=True)
class WorldBounds:
    min_x: float
    max_x: float
    min_y: float
    max_y: float

    @property
    def width(self):
        return max(self.max_x - self.min_x, 1e-9)

    @property
    def height(self):
        return max(self.max_y - self.min_y, 1e-9)


class Viewport:
    def __init__(self, screen_rect, drawable_rect, world_bounds, scale, offset_x, offset_y):
        self.screen_rect = screen_rect
        self.drawable_rect = drawable_rect
        self.world_bounds = world_bounds
        self.scale = scale
        self.offset_x = offset_x
        self.offset_y = offset_y

    def world_to_screen(self, point):
        x, y = point
        return (
            int(round(self.offset_x + x * self.scale)),
            int(round(self.offset_y - y * self.scale)),
        )

    def length_to_screen(self, value, minimum=1):
        return max(minimum, int(round(abs(value) * self.scale)))

    def font_size(self, world_height, minimum=12, maximum=36):
        return max(minimum, min(maximum, int(round(world_height * self.scale))))

    def line_width(self, world_width, minimum=1, maximum=8):
        return max(minimum, min(maximum, int(round(world_width * self.scale))))

    def rect_from_center(self, center, width, height):
        cx, cy = self.world_to_screen(center)
        screen_width = self.length_to_screen(width, minimum=2)
        screen_height = self.length_to_screen(height, minimum=2)
        rect = pygame.Rect(0, 0, screen_width, screen_height)
        rect.center = (cx, cy)
        return rect


def fit_model_to_rect(screen_size, world_bounds, padding_ratio=0.08, min_padding_px=12):
    width = max(int(screen_size[0]), 1)
    height = max(int(screen_size[1]), 1)
    screen_rect = pygame.Rect(0, 0, width, height)
    padding = max(min_padding_px, int(round(min(width, height) * padding_ratio)))
    drawable_rect = screen_rect.inflate(-2 * padding, -2 * padding)
    if drawable_rect.width <= 0 or drawable_rect.height <= 0:
        drawable_rect = screen_rect.copy()

    scale = min(drawable_rect.width / world_bounds.width, drawable_rect.height / world_bounds.height)
    scale = max(scale, 1e-9)

    content_width = world_bounds.width * scale
    content_height = world_bounds.height * scale
    content_left = drawable_rect.left + (drawable_rect.width - content_width) / 2.0
    content_top = drawable_rect.top + (drawable_rect.height - content_height) / 2.0

    offset_x = content_left - world_bounds.min_x * scale
    offset_y = content_top + world_bounds.max_y * scale
    return Viewport(screen_rect, drawable_rect, world_bounds, scale, offset_x, offset_y)
