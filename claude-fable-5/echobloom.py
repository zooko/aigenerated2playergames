import pygame, random, math, sys

W, H = 1280, 800
pygame.init()
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("ECHOBLOOM")
clock = pygame.time.Clock()
F_S = pygame.font.SysFont("menlo", 18)
F_M = pygame.font.SysFont("menlo", 26, bold=True)
F_B = pygame.font.SysFont("menlo", 64, bold=True)

CYAN = (90, 220, 255); MAG = (255, 90, 200); GOLD = (255, 215, 110)
GRN = (120, 255, 170); RED = (255, 90, 90); PUR = (160, 110, 255)
WHT = (235, 240, 255)

def scale_col(c, f): return tuple(max(0, min(255, int(x * f))) for x in c)
def clamp(v, a, b): return a if v < a else b if v > b else v

_glow = {}
def add_glow(surf, pos, radius, color):
    r = max(4, int(radius) // 4 * 4)
    key = (r, color)
    g = _glow.get(key)
    if g is None:
        g = pygame.Surface((r * 2, r * 2))
        steps = max(3, r // 3)
        for i in range(steps, 0, -1):
            a = (1 - i / steps) ** 2.2
            pygame.draw.circle(g, scale_col(color, a), (r, r), int(r * i / steps))
        _glow[key] = g
    surf.blit(g, (int(pos[0]) - r, int(pos[1]) - r), special_flags=pygame.BLEND_RGB_ADD)

def rect_dist(rect, x, y):
    cx = clamp(x, rect.left, rect.right); cy = clamp(y, rect.top, rect.bottom)
    return math.hypot(x - cx, y - cy)

STARS = [(random.randint(0, W), random.randint(0, H),
          random.uniform(0.3, 1.0), random.uniform(1, 4)) for _ in range(150)]

class Wall:
    def __init__(self, rect): self.rect = rect; self.bright = 0.0

class Seed:
    def __init__(self, x, y): self.x = x; self.y = y; self.phase = random.uniform(0, 6.28)

class Wraith:
    def __init__(self, x, y):
        self.x = x; self.y = y; self.vx = 0.0; self.vy = 0.0
        self.stun = 0.0; self.reveal = 0.0; self.phase = random.uniform(0, 6.28)

class Pulse:
    def __init__(self, x, y, maxr):
        self.x = x; self.y = y; self.r = 8.0; self.maxr = maxr; self.hit = set()

class Player:
    def __init__(self, x, y, color, keymap, r=13):
        self.x = x; self.y = y; self.color = color; self.keys = keymap
        self.r = r; self.invuln = 0.0; self.trail = []

    def move(self, pressed, walls, speed, dt):
        dx = (pressed[self.keys['r']] - pressed[self.keys['l']])
        dy = (pressed[self.keys['d']] - pressed[self.keys['u']])
        if dx and dy: dx *= 0.7071; dy *= 0.7071
        self._step(dx * speed * dt, 0, walls)
        self._step(0, dy * speed * dt, walls)
        self.x = clamp(self.x, self.r, W - self.r)
        self.y = clamp(self.y, self.r, H - self.r)
        self.trail.append((self.x, self.y))
        if len(self.trail) > 10: self.trail.pop(0)

    def _step(self, dx, dy, walls):
        if not dx and not dy: return
        self.x += dx; self.y += dy
        rect = pygame.Rect(int(self.x - self.r), int(self.y - self.r),
                           int(self.r * 2), int(self.r * 2))
        for w in walls:
            if rect.colliderect(w.rect):
                if dx > 0: self.x = w.rect.left - self.r
                elif dx < 0: self.x = w.rect.right + self.r
                if dy > 0: self.y = w.rect.top - self.r
                elif dy < 0: self.y = w.rect.bottom + self.r
                rect = pygame.Rect(int(self.x - self.r), int(self.y - self.r),
                                   int(self.r * 2), int(self.r * 2))

def new_stats():
    return {"hearts": 3, "max_hearts": 3, "energy": 70.0, "max_energy": 100,
            "pulse_r": 260, "pulse_cost": 24, "stun": 2.2, "magnet": 0,
            "lumen_speed": 230, "sprout_speed": 250, "ambient": 120,
            "seeds_total": 0}

UPGRADES = [
    ("PULSE BLOOM", "Sonar radius +50",
     lambda s: s.update(pulse_r=s["pulse_r"] + 50)),
    ("SWIFT SPROUT", "Sprout moves 15% faster",
     lambda s: s.update(sprout_speed=int(s["sprout_speed"] * 1.15))),
    ("BRIGHT LUMEN", "Lumen light +40, speed +10%",
     lambda s: s.update(ambient=s["ambient"] + 40,
                        lumen_speed=int(s["lumen_speed"] * 1.10))),
    ("DEEP CELL", "Max energy +40",
     lambda s: s.update(max_energy=s["max_energy"] + 40)),
    ("SEED CALL", "Seeds drift toward Sprout (+70 range)",
     lambda s: s.update(magnet=s["magnet"] + 70)),
    ("LONG HUSH", "Wraith stun lasts +1.0s",
     lambda s: s.update(stun=s["stun"] + 1.0)),
    ("HEARTBLOOM", "+1 heart (and heal it)",
     lambda s: s.update(max_hearts=min(6, s["max_hearts"] + 1),
                        hearts=min(6, s["hearts"] + 1))),
    ("CHEAP ECHO", "Pulse energy cost -6",
     lambda s: s.update(pulse_cost=max(6, s["pulse_cost"] - 6))),
]

def gen_level(level):
    walls = [Wall(pygame.Rect(0, 0, W, 16)), Wall(pygame.Rect(0, H - 16, W, 16)),
             Wall(pygame.Rect(0, 0, 16, H)), Wall(pygame.Rect(W - 16, 0, 16, H))]
    spawn = pygame.Rect(30, 30, 300, 240)
    target = 10 + level * 2
    tries = 0
    while len(walls) < target + 4 and tries < 900:
        tries += 1
        if random.random() < 0.5:
            w, h = random.randint(34, 58), random.randint(120, 280)
        else:
            w, h = random.randint(120, 280), random.randint(34, 58)
        r = pygame.Rect(random.randint(30, W - 30 - w), random.randint(30, H - 30 - h), w, h)
        if r.inflate(80, 80).colliderect(spawn): continue
        if any(r.inflate(56, 56).colliderect(o.rect) for o in walls[4:]): continue
        walls.append(Wall(r))
    seeds = []
    while len(seeds) < 6 + level:
        x, y = random.randint(60, W - 60), random.randint(60, H - 60)
        if any(rect_dist(w.rect, x, y) < 34 for w in walls): continue
        if math.hypot(x - 170, y - 150) < 230: continue
        seeds.append(Seed(x, y))
    wraiths = []
    while len(wraiths) < min(2 + level, 10):
        x, y = random.randint(80, W - 80), random.randint(80, H - 80)
        if math.hypot(x - 170, y - 150) < 420: continue
        wraiths.append(Wraith(x, y))
    portal = None
    while portal is None:
        x, y = random.randint(90, W - 90), random.randint(90, H - 90)
        if math.hypot(x - 170, y - 150) > 620 and \
           all(rect_dist(w.rect, x, y) > 60 for w in walls):
            portal = (x, y)
    return walls, seeds, wraiths, portal

def burst(parts, x, y, color, n, spd=190):
    for _ in range(n):
        a = random.uniform(0, 6.283); s = random.uniform(0.25, 1.0) * spd
        parts.append([x, y, math.cos(a) * s, math.sin(a) * s,
                      random.uniform(0.4, 0.9), color])

def draw_heart(surf, x, y, filled):
    c = RED if filled else (70, 40, 50)
    pygame.draw.circle(surf, c, (x - 5, y), 6)
    pygame.draw.circle(surf, c, (x + 5, y), 6)
    pygame.draw.polygon(surf, c, [(x - 10, y + 2), (x + 10, y + 2), (x, y + 14)])

def main():
    world = pygame.Surface((W, H))
    state = "MENU"
    stats = new_stats(); level = 1
    walls, seeds, wraiths, portal = gen_level(level)
    lumen = Player(130, 130, CYAN, {'u': pygame.K_w, 'd': pygame.K_s,
                                    'l': pygame.K_a, 'r': pygame.K_d})
    sprout = Player(210, 170, MAG, {'u': pygame.K_UP, 'd': pygame.K_DOWN,
                                    'l': pygame.K_LEFT, 'r': pygame.K_RIGHT})
    pulses, parts = [], []
    shake = 0.0; portal_charge = 0.0; t = 0.0
    choices = []

    def reset_level():
        nonlocal walls, seeds, wraiths, portal, pulses, portal_charge
        walls, seeds, wraiths, portal = gen_level(level)
        lumen.x, lumen.y = 130, 130; sprout.x, sprout.y = 210, 170
        lumen.trail.clear(); sprout.trail.clear()
        pulses = []; portal_charge = 0.0

    def full_restart():
        nonlocal stats, level, state
        stats = new_stats(); level = 1
        reset_level(); state = "PLAY"

    while True:
        dt = min(clock.tick(60) / 1000.0, 0.033); t += dt
        for e in pygame.event.get():
            if e.type == pygame.QUIT: pygame.quit(); sys.exit()
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE: pygame.quit(); sys.exit()
                if state == "MENU" and e.key == pygame.K_SPACE:
                    full_restart()
                elif state == "PLAY" and e.key == pygame.K_SPACE:
                    if stats["energy"] >= stats["pulse_cost"]:
                        stats["energy"] -= stats["pulse_cost"]
                        pulses.append(Pulse(lumen.x, lumen.y, stats["pulse_r"]))
                elif state == "GAMEOVER" and e.key == pygame.K_r:
                    full_restart()
                elif state == "UPGRADE" and e.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                    idx = e.key - pygame.K_1
                    if idx < len(choices):
                        choices[idx][2](stats)
                        reset_level(); state = "PLAY"

        pressed = pygame.key.get_pressed()

        if state == "PLAY":
            lumen.move(pressed, walls, stats["lumen_speed"], dt)
            sprout.move(pressed, walls, stats["sprout_speed"], dt)
            lumen.invuln = max(0, lumen.invuln - dt)
            sprout.invuln = max(0, sprout.invuln - dt)
            stats["energy"] = min(stats["max_energy"], stats["energy"] + 3 * dt)

            for p in pulses[:]:
                p.r += 430 * dt
                if p.r > p.maxr: pulses.remove(p); continue
                band = 30
                for w in walls:
                    if abs(rect_dist(w.rect, p.x, p.y) - p.r) < band:
                        w.bright = min(1.0, w.bright + 4 * dt)
                for i, wr in enumerate(wraiths):
                    d = math.hypot(wr.x - p.x, wr.y - p.y)
                    if abs(d - p.r) < band and i not in p.hit:
                        p.hit.add(i)
                        wr.stun = stats["stun"]; wr.reveal = stats["stun"] + 1.5
                        if d > 1:
                            wr.vx = (wr.x - p.x) / d * 320
                            wr.vy = (wr.y - p.y) / d * 320
                        burst(parts, wr.x, wr.y, PUR, 10, 120)

            for w in walls:
                base = 0.0
                for pl, rad in ((lumen, stats["ambient"]), (sprout, 65)):
                    d = rect_dist(w.rect, pl.x, pl.y)
                    if d < rad: base = max(base, (1 - d / rad) * 0.5)
                w.bright = max(base, w.bright - 0.6 * dt)

            for s in seeds[:]:
                d = math.hypot(s.x - sprout.x, s.y - sprout.y)
                if stats["magnet"] and d < stats["magnet"] and d > 1:
                    s.x += (sprout.x - s.x) / d * 170 * dt
                    s.y += (sprout.y - s.y) / d * 170 * dt
                    d = math.hypot(s.x - sprout.x, s.y - sprout.y)
                if d < 22:
                    seeds.remove(s)
                    stats["energy"] = min(stats["max_energy"], stats["energy"] + 18)
                    stats["seeds_total"] += 1
                    burst(parts, s.x, s.y, GOLD, 14)

            for wr in wraiths:
                wr.reveal = max(0, wr.reveal - dt)
                if wr.stun > 0:
                    wr.stun -= dt; wr.vx *= 0.9; wr.vy *= 0.9
                else:
                    dx, dy = sprout.x - wr.x, sprout.y - wr.y
                    d = math.hypot(dx, dy) or 1
                    wr.vx += dx / d * 150 * dt; wr.vy += dy / d * 150 * dt
                    dl = math.hypot(lumen.x - wr.x, lumen.y - wr.y)
                    if dl < stats["ambient"] and dl > 1:
                        f = (1 - dl / stats["ambient"]) * 700 * dt
                        wr.vx += (wr.x - lumen.x) / dl * f
                        wr.vy += (wr.y - lumen.y) / dl * f
                    sp = math.hypot(wr.vx, wr.vy)
                    cap = 62 + level * 7
                    if sp > cap: wr.vx *= cap / sp; wr.vy *= cap / sp
                wr.x = clamp(wr.x + wr.vx * dt, 20, W - 20)
                wr.y = clamp(wr.y + wr.vy * dt, 20, H - 20)
                if wr.stun <= 0:
                    for pl in (lumen, sprout):
                        if pl.invuln <= 0 and math.hypot(wr.x - pl.x, wr.y - pl.y) < pl.r + 12:
                            stats["hearts"] -= 1; pl.invuln = 1.6; shake = 14
                            d = math.hypot(pl.x - wr.x, pl.y - wr.y) or 1
                            pl.x += (pl.x - wr.x) / d * 46
                            pl.y += (pl.y - wr.y) / d * 46
                            burst(parts, pl.x, pl.y, RED, 20)
                            if stats["hearts"] <= 0: state = "GAMEOVER"

            if not seeds:
                d1 = math.hypot(lumen.x - portal[0], lumen.y - portal[1])
                d2 = math.hypot(sprout.x - portal[0], sprout.y - portal[1])
                if d1 < 54 and d2 < 54:
                    portal_charge += dt
                    if portal_charge > 0.9:
                        burst(parts, portal[0], portal[1], GRN, 40, 260)
                        level += 1
                        choices = random.sample(UPGRADES, 3)
                        state = "UPGRADE"
                else:
                    portal_charge = max(0, portal_charge - dt * 2)

        for p in parts[:]:
            p[0] += p[2] * dt; p[1] += p[3] * dt; p[4] -= dt
            p[2] *= 0.96; p[3] *= 0.96
            if p[4] <= 0: parts.remove(p)
        shake = max(0, shake - 40 * dt)

        # ---------- RENDER ----------
        world.fill((7, 8, 16))
        for sx, sy, b, ph in STARS:
            f = b * (0.5 + 0.5 * math.sin(t * ph + sx))
            world.set_at((sx, sy), scale_col(WHT, 0.35 * f))

        if state in ("PLAY", "GAMEOVER"):
            for w in walls:
                if w.bright > 0.03:
                    col = scale_col((80, 150, 235), w.bright)
                    pygame.draw.rect(world, scale_col(col, 0.25), w.rect)
                    pygame.draw.rect(world, col, w.rect, 2)
            if not seeds:
                pr = 40 + 8 * math.sin(t * 3)
                add_glow(world, portal, 90 + portal_charge * 80, GRN)
                pygame.draw.circle(world, GRN, portal, int(pr), 3)
                pygame.draw.circle(world, scale_col(GRN, 0.5), portal,
                                   int(pr + 14 + 6 * math.sin(t * 2)), 2)
                if portal_charge > 0:
                    pygame.draw.arc(world, WHT,
                                    (portal[0] - 60, portal[1] - 60, 120, 120),
                                    0, portal_charge / 0.9 * 6.283, 4)
            for s in seeds:
                pul = 0.7 + 0.3 * math.sin(t * 4 + s.phase)
                add_glow(world, (s.x, s.y), 26 * pul, GOLD)
                pygame.draw.circle(world, GOLD, (int(s.x), int(s.y)), 4)
            for p in pulses:
                f = 1 - p.r / p.maxr
                for w_, fac in ((6, 0.35), (3, 0.7), (1, 1.0)):
                    pygame.draw.circle(world, scale_col(CYAN, f * fac),
                                       (int(p.x), int(p.y)), int(p.r), w_)
            for wr in wraiths:
                if wr.reveal > 0:
                    f = min(1, wr.reveal)
                    col = PUR if wr.stun > 0 else RED
                    add_glow(world, (wr.x, wr.y), 34, scale_col(col, f))
                    pygame.draw.circle(world, scale_col(col, f),
                                       (int(wr.x), int(wr.y)), 10, 2)
                else:
                    f = 0.10 + 0.08 * math.sin(t * 11 + wr.phase)
                    add_glow(world, (wr.x, wr.y), 22, scale_col(RED, max(0, f)))
            for pl, ambient in ((lumen, stats["ambient"]), (sprout, 60)):
                for i, (tx, ty) in enumerate(pl.trail):
                    add_glow(world, (tx, ty), 6 + i, scale_col(pl.color, i / 22))
                add_glow(world, (pl.x, pl.y), ambient, scale_col(pl.color, 0.45))
                if pl.invuln <= 0 or int(t * 14) % 2 == 0:
                    add_glow(world, (pl.x, pl.y), 26, pl.color)
                    pygame.draw.circle(world, WHT, (int(pl.x), int(pl.y)), 6)
                    pygame.draw.circle(world, pl.color, (int(pl.x), int(pl.y)),
                                       pl.r, 2)
            for p in parts:
                add_glow(world, (p[0], p[1]), 10 * p[4] + 3, p[5])
            # HUD
            for i in range(stats["max_hearts"]):
                draw_heart(world, 40 + i * 30, 36, i < stats["hearts"])
            eb = pygame.Rect(W // 2 - 160, H - 34, 320, 14)
            pygame.draw.rect(world, (40, 50, 70), eb, border_radius=6)
            fw = int(316 * stats["energy"] / stats["max_energy"])
            pygame.draw.rect(world, CYAN, (eb.x + 2, eb.y + 2, fw, 10), border_radius=6)
            world.blit(F_S.render("PULSE ENERGY", True, scale_col(CYAN, 0.8)),
                       (eb.x + 100, eb.y - 22))
            world.blit(F_M.render(f"DEPTH {level}", True, WHT), (W - 190, 22))
            msg = f"seeds left: {len(seeds)}" if seeds else "PORTAL OPEN — go together!"
            world.blit(F_S.render(msg, True, GOLD if seeds else GRN), (W - 280, 56))

        if state == "MENU":
            world.blit(F_B.render("E C H O B L O O M", True, CYAN),
                       (W // 2 - 330, 150))
            add_glow(world, (W // 2, 190), 260, scale_col(CYAN, 0.35))
            lines = [
                ("A garden grows in total darkness. Two of you must tend it.", WHT),
                ("", WHT),
                ("LUMEN (P1)   WASD to move, SPACE for sonar pulse", CYAN),
                ("   reveals the maze, stuns wraiths, radiates safety", CYAN),
                ("SPROUT (P2)  Arrow keys to move", MAG),
                ("   gathers seeds — seeds refuel Lumen's pulses", MAG),
                ("", WHT),
                ("Wraiths drift through walls hunting Sprout. Shared hearts.", RED),
                ("Collect every seed, then reach the portal TOGETHER.", GRN),
                ("", WHT),
                ("Press SPACE to descend", GOLD)]
            for i, (txt, col) in enumerate(lines):
                world.blit(F_S.render(txt, True, col), (W // 2 - 310, 300 + i * 32))
        elif state == "UPGRADE":
            world.blit(F_B.render(f"DEPTH {level - 1} CLEARED", True, GRN),
                       (W // 2 - 330, 130))
            world.blit(F_M.render("Choose one bloom (press 1, 2 or 3):", True, WHT),
                       (W // 2 - 250, 260))
            for i, (name, desc, _) in enumerate(choices):
                y = 330 + i * 100
                pygame.draw.rect(world, scale_col(GOLD, 0.4),
                                 (W // 2 - 300, y, 600, 78), 2, border_radius=10)
                world.blit(F_M.render(f"{i + 1}.  {name}", True, GOLD),
                           (W // 2 - 270, y + 12))
                world.blit(F_S.render(desc, True, WHT), (W // 2 - 270, y + 46))
        elif state == "GAMEOVER":
            world.blit(F_B.render("THE GARDEN FADES", True, RED), (W // 2 - 310, 260))
            world.blit(F_M.render(f"You reached depth {level} and grew "
                                  f"{stats['seeds_total']} seeds.", True, WHT),
                       (W // 2 - 290, 360))
            world.blit(F_M.render("Press R to replant", True, GOLD),
                       (W // 2 - 130, 420))

        off = (random.uniform(-shake, shake), random.uniform(-shake, shake))
        screen.fill((0, 0, 0))
        screen.blit(world, off)
        pygame.display.flip()

main()
