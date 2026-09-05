import math
import random
from collections import deque

import pygame as pg

pg.init()
W, H = 1000, 680
screen = pg.display.set_mode((W, H))
pg.display.set_caption("ECHO HEIST")
clock = pg.time.Clock()
font = pg.font.Font(None, 27)
large = pg.font.Font(None, 62)
V = pg.Vector2
BG, INK, GOLD = (12, 17, 29), (225, 235, 250), (255, 209, 92)
COLORS = [(65, 225, 235), (255, 105, 170)]
KEYS = [
    (pg.K_w, pg.K_s, pg.K_a, pg.K_d, pg.K_f),
    (pg.K_UP, pg.K_DOWN, pg.K_LEFT, pg.K_RIGHT, pg.K_RSHIFT),
]
ARENA = pg.Rect(18, 78, 964, 542)
RADIUS, FUSE, COOLDOWN = 96, 0.35, 1.8

def text(message, x, y, color=INK, big=False, centered=False):
    image = (large if big else font).render(message, True, color)
    rect = image.get_rect(center=(x, y)) if centered else (x, y)
    screen.blit(image, rect)

def confetti(pos, color, count):
    for _ in range(count):
        velocity = V(random.uniform(-1, 1), random.uniform(-1, 1))
        particles.append([V(pos), velocity * 210, 0.5, color])

def reset():
    global players, coins, bombs, particles, t, spawn, started
    t, spawn, started = 0.0, 0.0, False
    bombs, particles, coins, players = [], [], [], []
    for i in range(2):
        pos = V(240 + i * 520, 350)
        players.append(dict(
            pos=pos, past=deque([(0.0, pos.copy())]),
            score=0, ready=1.0, stun=0.0, safe=0.0,
        ))
    for _ in range(4):
        x, y = random.randint(70, 450), random.randint(120, 575)
        coins.extend([V(x, y), V(W - x, y)])

reset()
alive = True
while alive:
    dt = min(clock.tick(60) / 1000, 0.04)
    for event in pg.event.get():
        if event.type == pg.QUIT:
            alive = False
        if event.type != pg.KEYDOWN:
            continue
        if event.key == pg.K_ESCAPE:
            alive = False
        elif event.key == pg.K_r:
            reset()
        elif event.key == pg.K_SPACE:
            started = True
        elif started and t < 60:
            for i, p in enumerate(players):
                if (event.key == KEYS[i][4]
                        and t >= max(p["ready"], p["stun"])):
                    bombs.append([p["pos"].copy(), t + FUSE, i, False])
                    p["pos"] = p["past"][0][1].copy()
                    p["past"].clear()
                    p["past"].append((t, p["pos"].copy()))
                    p["ready"] = t + COOLDOWN
                    confetti(p["pos"], COLORS[i], 12)

    if started and t < 60:
        t = min(60, t + dt)
        held = pg.key.get_pressed()
        for i, p in enumerate(players):
            up, down, left, right, _ = KEYS[i]
            direction = V(int(held[right]) - int(held[left]),
                          int(held[down]) - int(held[up]))
            if direction.length_squared() and t >= p["stun"]:
                p["pos"] += direction.normalize() * 265 * dt
            p["pos"].x = max(34, min(W - 34, p["pos"].x))
            p["pos"].y = max(94, min(604, p["pos"].y))
            p["past"].append((t, p["pos"].copy()))
            while len(p["past"]) > 1 and p["past"][1][0] <= t - 1:
                p["past"].popleft()

        for bomb in bombs:
            pos, deadline, owner, exploded = bomb
            if t >= deadline and not exploded:
                bomb[3] = True
                confetti(pos, COLORS[owner], 28)
                victim = players[1 - owner]
                if (pos.distance_to(victim["pos"]) < RADIUS + 14
                        and t >= victim["safe"]):
                    amount = min(2, victim["score"])
                    victim["score"] -= amount
                    players[owner]["score"] += amount
                    victim["stun"], victim["safe"] = t + 0.55, t + 0.9
        bombs[:] = [b for b in bombs if t < b[1] + 0.3]

        for coin in coins[:]:
            distances = [
                p["pos"].distance_to(coin) if t >= p["stun"]
                else float("inf") for p in players
            ]
            nearest = min(distances)
            if nearest < 24:
                # An exact tie leaves the coin available.
                if distances[0] == distances[1]:
                    continue
                winner = distances.index(nearest)
                players[winner]["score"] += 1
                coins.remove(coin)
                confetti(coin, GOLD, 8)

        spawn -= dt
        if spawn <= 0:
            spawn = 0.65
            if len(coins) < 10:
                coins.append(V(random.randint(55, 945),
                               random.randint(115, 585)))

    screen.fill(BG)
    pg.draw.rect(screen, (21, 29, 45), ARENA, border_radius=18)
    for x in range(40, W, 40):
        for y in range(100, 620, 40):
            pg.draw.circle(screen, (35, 44, 61), (x, y), 1)

    for coin in coins:
        r = 7 + int(2 * math.sin(t * 6 + coin.x))
        pg.draw.circle(screen, (75, 62, 37), coin, r + 5)
        pg.draw.circle(screen, GOLD, coin, r)

    glow = pg.Surface((W, H), pg.SRCALPHA)
    for pos, deadline, owner, exploded in bombs:
        color = COLORS[owner]
        if not exploded:
            pg.draw.circle(screen, color, pos, RADIUS, 1)
            progress = max(0, min(1, 1 - (deadline - t) / FUSE))
            pg.draw.circle(screen, color, pos, 5 + int(progress * 17), 3)
        else:
            alpha = int(130 * max(0, 1 - (t - deadline) / 0.3))
            pg.draw.circle(glow, (*color, alpha), pos, RADIUS)
    screen.blit(glow, (0, 0))

    for i, p in enumerate(players):
        color, pos = COLORS[i], p["pos"]
        ghost = p["past"][0][1]
        dim = tuple(c // 3 for c in color)
        pg.draw.line(screen, dim, ghost, pos, 2)
        pg.draw.circle(screen, dim, ghost, 14, 2)
        pg.draw.circle(screen, INK if t < p["stun"] else color, pos, 14)
        pg.draw.circle(screen, BG, pos + V(4, -3), 4)
        charge = max(0, min(1, 1 - (p["ready"] - t) / COOLDOWN))
        if charge:
            rect = pg.Rect(0, 0, 44, 44)
            rect.center = pos
            pg.draw.arc(screen, color, rect, -math.pi / 2,
                        -math.pi / 2 + charge * math.tau, 3)

    for particle in particles[:]:
        pos, velocity, life, color = particle
        particle[2] -= dt
        pos += velocity * dt
        velocity *= 0.94
        if particle[2] <= 0:
            particles.remove(particle)
        else:
            pg.draw.circle(screen, color, pos, max(1, int(life * 7)))

    text(f"CYAN  {players[0]['score']}", 30, 26, COLORS[0])
    text(f"PINK  {players[1]['score']}", 830, 26, COLORS[1])
    text(f"{math.ceil(60 - t):02d}", W // 2, 37, centered=True)
    text("WASD + F", 30, 641, COLORS[0])
    text("R: restart   /   Esc: quit", W // 2, 653, centered=True)
    text("Arrows + Right Shift", 775, 641, COLORS[1])

    if not started or t >= 60:
        veil = pg.Surface((W, H), pg.SRCALPHA)
        veil.fill((7, 11, 20, 225))
        screen.blit(veil, (0, 0))
        a, b = (p["score"] for p in players)
        title = "ECHO HEIST" if not started else (
            "A PERFECT TIE" if a == b else
            "CYAN WINS" if a > b else "PINK WINS")
        text(title, 500, 240, big=True, centered=True)
        lines = [
            "Collect gold. Rewind one second. Leave an explosion.",
            "Tag your rival: steal 2 points. Keep your own loot.",
            "Cyan: WASD / F       Pink: Arrows / Right Shift",
            "SPACE to begin",
        ] if not started else [
            f"Cyan {a}   :   {b} Pink",
            "Press R for a rematch, then SPACE.",
        ]
        for j, line in enumerate(lines):
            text(line, 500, 320 + j * 43, centered=True)

    pg.display.flip()

pg.quit()
