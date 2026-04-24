#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Mar 18 23:19:52 2026

@author: serhatcombas
"""

import math
import pygame

pygame.init()

# --------------------------------------------------
# Ayarlar
# --------------------------------------------------
WIDTH, HEIGHT = 1000, 500
FPS = 60

WHITE = (245, 245, 245)
BLACK = (20, 20, 20)
GRAY = (150, 150, 150)
DARK_GRAY = (90, 90, 90)
GREEN = (0, 180, 0)
RED = (220, 50, 50)
BLUE = (30, 80, 200)

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Motor-Belt-Pendulum Simulation")
clock = pygame.time.Clock()

font = pygame.font.SysFont("Arial", 24)

# --------------------------------------------------
# Fiziksel parametreler
# --------------------------------------------------
g = 9.81
M = 1.0      # blok/arabacık kütlesi
m = 0.25     # pendulum kütlesi
L = 120.0    # çizim için piksel uzunluğu
l = 0.6      # fiziksel model için metre cinsinden pendulum uzunluğu
dt = 1 / FPS

# durumlar
s = 0.0          # m
s_dot = 0.0      # m/s
phi = math.radians(8)   # rad, başlangıç açısı
phi_dot = 0.0    # rad/s

# çizim ölçeği
PIXELS_PER_METER = 250
rail_y = 330
rail_x1 = 100
rail_x2 = 900

# --------------------------------------------------
# Dinamik model: klasik cart-pole yaklaşımı
# phi = 0 --> dik yukarı
# --------------------------------------------------
def dynamics(state, force):
    s, s_dot, phi, phi_dot = state

    sin_phi = math.sin(phi)
    cos_phi = math.cos(phi)

    total_mass = M + m
    polemass_length = m * l

    # Cart-pole denklemi
    temp = (force + polemass_length * phi_dot * phi_dot * sin_phi) / total_mass

    phi_ddot = (
        g * sin_phi - cos_phi * temp
    ) / (l * (4.0 / 3.0 - (m * cos_phi * cos_phi) / total_mass))

    s_ddot = temp - (polemass_length * phi_ddot * cos_phi) / total_mass

    return s_dot, s_ddot, phi_dot, phi_ddot

# --------------------------------------------------
# Basit Euler integrasyonu
# --------------------------------------------------
def step(state, force, dt):
    s, s_dot, phi, phi_dot = state
    ds, ds_dot, dphi, dphi_dot = dynamics(state, force)

    s += ds * dt
    s_dot += ds_dot * dt
    phi += dphi * dt
    phi_dot += dphi_dot * dt

    return [s, s_dot, phi, phi_dot]

# --------------------------------------------------
# Çizim fonksiyonları
# --------------------------------------------------
def draw_motor(x, y):
    # motor gövdesi
    pygame.draw.rect(screen, DARK_GRAY, (x, y - 25, 70, 50), border_radius=8)
    # motor burnu
    pygame.draw.rect(screen, GRAY, (x - 20, y - 15, 20, 30), border_radius=6)
    # eksen
    pygame.draw.line(screen, BLACK, (x - 35, y), (x - 20, y), 4)

    txt = font.render("Motor", True, BLACK)
    screen.blit(txt, (x + 5, y - 60))

def draw_arrow(start, end, color=BLACK, width=3):
    pygame.draw.line(screen, color, start, end, width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    head_len = 12
    a1 = angle + math.pi / 7
    a2 = angle - math.pi / 7
    p1 = (end[0] - head_len * math.cos(a1), end[1] - head_len * math.sin(a1))
    p2 = (end[0] - head_len * math.cos(a2), end[1] - head_len * math.sin(a2))
    pygame.draw.polygon(screen, color, [end, p1, p2])

def draw_system(s, phi, force):
    # ray / kayış
    pygame.draw.line(screen, DARK_GRAY, (rail_x1, rail_y), (rail_x2, rail_y), 8)

    # makaralar
    pygame.draw.circle(screen, GRAY, (rail_x1, rail_y), 18)
    pygame.draw.circle(screen, GRAY, (rail_x2, rail_y), 18)
    pygame.draw.circle(screen, GREEN, (rail_x1, rail_y), 6)
    pygame.draw.circle(screen, GREEN, (rail_x2, rail_y), 6)

    # blok konumu
    cart_x = WIDTH // 2 + int(s * PIXELS_PER_METER)
    cart_y = rail_y - 18
    cart_w, cart_h = 90, 36

    pygame.draw.rect(
        screen,
        (200, 200, 200),
        (cart_x - cart_w // 2, cart_y - cart_h // 2, cart_w, cart_h),
        border_radius=4,
    )
    pygame.draw.rect(
        screen,
        BLACK,
        (cart_x - cart_w // 2, cart_y - cart_h // 2, cart_w, cart_h),
        2,
        border_radius=4,
    )

    # mafsal noktası
    pivot_x = cart_x
    pivot_y = cart_y
    pygame.draw.circle(screen, GREEN, (pivot_x, pivot_y), 7)

    # çubuk
    rod_len_px = int(L)
    tip_x = pivot_x + int(rod_len_px * math.sin(phi))
    tip_y = pivot_y - int(rod_len_px * math.cos(phi))

    pygame.draw.line(screen, BLACK, (pivot_x, pivot_y), (tip_x, tip_y), 5)
    pygame.draw.circle(screen, BLACK, (tip_x, tip_y), 8)

    # açı yayı
    arc_rect = pygame.Rect(pivot_x - 50, pivot_y - 50, 100, 100)
    pygame.draw.arc(screen, DARK_GRAY, arc_rect, -math.pi / 2 - phi, -math.pi / 2, 2)

    # s(t) oku
    draw_arrow((cart_x - 90, cart_y + 45), (cart_x - 20, cart_y + 45))
    txt_s = font.render("s(t)", True, BLACK)
    screen.blit(txt_s, (cart_x - 80, cart_y + 10))

    # phi(t) yazısı
    txt_phi = font.render("φ(t)", True, BLACK)
    screen.blit(txt_phi, (pivot_x + 30, pivot_y - 100))

    # motor
    motor_x = rail_x2 + 40
    motor_y = rail_y - 10
    draw_motor(motor_x, motor_y)

    # motor kuvvet oku
    if force >= 0:
        draw_arrow((motor_x + 120, motor_y), (motor_x + 70, motor_y), RED)
    else:
        draw_arrow((motor_x + 70, motor_y), (motor_x + 120, motor_y), RED)

    txt_u = font.render("U_M(t)", True, BLACK)
    screen.blit(txt_u, (motor_x + 55, motor_y + 20))

    # bilgi metni
    info1 = font.render(f"s = {s:.3f} m", True, BLUE)
    info2 = font.render(f"phi = {math.degrees(phi):.2f} deg", True, BLUE)
    screen.blit(info1, (40, 30))
    screen.blit(info2, (40, 65))

# --------------------------------------------------
# Ana döngü
# --------------------------------------------------
running = True

while running:
    clock.tick(FPS)

    force = 0.0
    keys = pygame.key.get_pressed()
    if keys[pygame.K_LEFT]:
        force = -8.0
    if keys[pygame.K_RIGHT]:
        force = 8.0

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # durum güncelle
    s, s_dot, phi, phi_dot = step([s, s_dot, phi, phi_dot], force, dt)

    # ray sınırı
    max_s = (rail_x2 - rail_x1 - 100) / (2 * PIXELS_PER_METER)
    if s > max_s:
        s = max_s
        s_dot = 0
    elif s < -max_s:
        s = -max_s
        s_dot = 0

    screen.fill(WHITE)
    draw_system(s, phi, force)
    pygame.display.flip()

pygame.quit()