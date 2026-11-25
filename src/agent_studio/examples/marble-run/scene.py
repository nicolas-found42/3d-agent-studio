"""A lift returns a glass marble to a descending spiral for an exact repeated shot."""
import math

from mathutils import Vector

TOP = 4.55
BOTTOM = 1.26
ROLL_END = 0.59
LIFT_START, LIFT_END = 0.74, 0.92
HANDOFF = 0.965
LIFT_TOP_Z = TOP + 0.14
RADIUS = 0.225
TRAY_DEPTH = 0.071


def spiral(u):
    angle = math.tau * 1.83 * u
    radius = 1.58 - 0.40 * u
    return Vector((radius * math.cos(angle), radius * math.sin(angle), TOP + (BOTTOM - TOP) * u))


LIFT_BASE = Vector((2.18, 0, 0.54))
LIFT_TOP = Vector((LIFT_BASE.x, 0, LIFT_TOP_Z))
LIP = spiral(1)
FLOOR_FUNNEL = LIP + (LIP - spiral(0.99)).normalized() * 0.49
FLOOR_FUNNEL.z = LIFT_BASE.z


def smooth(u):
    return u * u * (3 - 2 * u)


def build(kit):
    maple = kit.procedural('Maple rail stock', 'wood', ('#88502D', '#D98847'), scale=0.7, bump=0.11)
    birch = kit.material('Birch end grain', '#B37443', 0.43, bump=(50, 0.12))
    enamel = kit.material('Teal lift and fittings', '#0C6A74', 0.36, coat=0.32)
    steel = kit.material('Nickel fasteners', '#A5B8BD', 0.25, metallic=0.88)
    floor = kit.material('Warm linoleum', '#D9A395', 0.67, bump=(4, 0.08))
    glass = kit.glass('Clear marble glass', '#E1FFFA', roughness=0.045)
    ribbon = kit.material('Cobalt ribbon inside marble', '#1D4BC2', 0.29, metallic=0.05)
    amber = kit.material('Amber ribbon inside marble', '#E98B2F', 0.3)

    kit.world('#E0F0FA', 0.20)
    kit.ground(floor, size=90)
    kit.cylinder('Rounded maple playroom base', 2.53, 0.23, (0, 0, 0.12), maple, bevel=0.085)
    kit.cylinder('Central wooden mast', 0.13, 4.35, (0, 0, 2.27), birch, bevel=0.025)

    def route(t):
        if t < ROLL_END:
            return spiral(t / ROLL_END)
        if t < LIFT_START:
            u = (t - ROLL_END) / (LIFT_START - ROLL_END)
            if u < 0.43:
                drop = u / 0.43
                centre = LIP.lerp(FLOOR_FUNNEL, kit.ease(min(1, 1.45 * drop), 'out', power=1.65))
                centre.z = LIP.z + (FLOOR_FUNNEL.z - LIP.z) * drop ** 2
                return centre
            return FLOOR_FUNNEL.lerp(LIFT_BASE, smooth((u - 0.43) / 0.57))
        if t < LIFT_END:
            return LIFT_BASE.lerp(LIFT_TOP, smooth((t - LIFT_START) / (LIFT_END - LIFT_START)))
        # A short handoff clears the upper rail edge before the marble settles onto it.
        receiving = spiral(0)
        if t < HANDOFF:
            u = (t - LIFT_END) / (HANDOFF - LIFT_END)
            cross = LIFT_TOP.lerp(receiving, smooth(u))
            cross.z = LIFT_TOP_Z + 0.06 * math.sin(math.pi * u)
            return cross
        u = (t - HANDOFF) / (1 - HANDOFF)
        return receiving + Vector((0, 0, (LIFT_TOP_Z - TOP) * (1 - smooth(u))))

    # Two swept rails are the visible contact surfaces; small radial sleepers fix their spacing.
    rail_drop = math.sqrt((RADIUS + 0.048) ** 2 - 0.137 ** 2)
    for side in (-1, 1):
        rail = []
        for i in range(145):
            u = i / 144
            p = spiral(u)
            normal = Vector((p.x, p.y, 0)).normalized()
            rail.append(p + normal * side * 0.137 - Vector((0, 0, rail_drop)))
        kit.tube(f'Spiral maple rail {side}', rail, 0.048, maple, resolution=8)
    for i in range(42):
        u = i / 41
        p = spiral(u)
        angle = math.degrees(math.atan2(p.y, p.x))
        kit.box(f'Radial rail sleeper {i:02}', (0.44, 0.070, 0.045),
                (p.x, p.y, p.z - 0.28), birch, rotation=(0, 0, angle), bevel=0.012)
        if i % 5 == 0:
            stem = Vector((p.x * 0.13, p.y * 0.13, p.z - 0.35))
            toe = Vector((p.x, p.y, p.z - 0.32))
            kit.tube(f'Canted maple bracket {i:02}', (stem, toe), 0.046, maple, resolution=8)
            kit.sphere(f'Bracket rivet {i:02}', 0.031, toe, steel, segments=12, rings=8)

    # The opening stays larger than the marble. The return rails catch it below the throat.
    profile = [(0.245, 0), (0.255, 0.045), (0.32, 0.090), (0.47, 0.167), (0.57, 0.228),
               (0.585, 0.212), (0.55, 0.190), (0.342, 0.04), (0.27, -0.03), (0.245, 0)]
    mouth_at = (FLOOR_FUNNEL.x, FLOOR_FUNNEL.y, 0.808)
    kit.lathe('Turned maple receiving funnel', profile, material=maple, location=mouth_at)
    kit.torus('Receiving rim', 0.555, 0.026, (FLOOR_FUNNEL.x, FLOOR_FUNNEL.y, 1.007), birch)
    exit_axis = LIFT_BASE - FLOOR_FUNNEL
    side = Vector((-exit_axis.y, exit_axis.x, 0)).normalized()
    for i, sign in enumerate((-1, 1)):
        offset = side * (sign * 0.15) - Vector((0, 0, 0.227))
        kit.tube(f'Funnel return rail {i}', [FLOOR_FUNNEL + offset, FLOOR_FUNNEL.lerp(LIFT_BASE, 0.79) + offset],
                 radius=0.047, material=maple, resolution=8)
        leg = FLOOR_FUNNEL + side * (sign * 0.345)
        kit.cylinder(f'Funnel support {i}', 0.05, 0.61, (leg.x, leg.y, 0.54), birch, bevel=0.009)
    across = math.degrees(math.atan2(side.y, side.x))
    for i, u in enumerate((0.12, 0.36, 0.60)):
        mount = FLOOR_FUNNEL.lerp(LIFT_BASE, u)
        kit.box(f'Return rail sleeper {i}', (0.40, 0.10, 0.042), (mount.x, mount.y, 0.253),
                birch, rotation=(0, 0, across), bevel=0.009)
    for side in (-1, 1):
        y = side * 0.36
        kit.cylinder(f'Lift guide {side}', 0.031, 4.57, (2.28, y, 2.52), steel, bevel=0.012)
        kit.box(f'Lift guide top lock {side}', (0.23, 0.13, 0.12), (2.27, y, 4.80), enamel, bevel=0.025)
    kit.box('Lift teal base motor', (0.45, 0.26, 0.31), (2.22, -0.69, 0.365), enamel, bevel=0.07)
    kit.torus('Lift drive pulley', 0.16, 0.039, (2.22, -0.46, 0.41), steel, rotation=(90, 0, 0))
    kit.tube('Lift drive belt', [(2.27, -0.365, 0.39), (2.27, -0.365, 4.64),
                                (2.27, -0.33, 4.70), (2.27, -0.295, 4.64), (2.27, -0.295, 0.39)],
             0.021, enamel, closed=True)

    carriage = kit.box('Moving lift carriage', (0.48, 0.52, TRAY_DEPTH), (LIFT_BASE.x, 0, 0.34), enamel, bevel=0.04)
    def carriage_pose(t):
        if t < LIFT_START:
            height = LIFT_TOP_Z - (LIFT_TOP_Z - LIFT_BASE.z) * smooth(min(1, t / 0.52))
        else:
            height = LIFT_BASE.lerp(LIFT_TOP, smooth(min(1, (t - LIFT_START) / (LIFT_END - LIFT_START)))).z
        return (LIFT_BASE.x, 0, height - RADIUS - TRAY_DEPTH / 2)

    kit.animate(carriage, 'location', carriage_pose, step=1)
    ball = kit.sphere('Glass marble', RADIUS, material=glass, segments=40, rings=20)
    for i, colour in enumerate((ribbon, amber)):
        vane = kit.sphere(f'Embedded colour ribbon {i}', RADIUS * 0.88,
                          (0.022 * (-1) ** i, 0, 0), colour, segments=24, rings=12)
        vane.scale = (0.23, 0.82, 0.95)
        vane.rotation_euler = (0.2 + i * 0.36, 0.63, 0.2)
        vane.parent = ball
    kit.animate(ball, 'location', route, step=1)
    kit.animate(ball, 'rotation_euler',
                lambda t: (math.tau * 11 * min(1.0, t / ROLL_END), math.tau * 4 * t, math.tau * 6 * t),
                step=2)

    kit.area('Playroom picture window', (-4, -3, 7), (0, 0, 2), 1250, '#FFF0D9', 4.8, size_y=3.1)
    kit.area('Glass rim from the window', (3.5, 3.7, 5), (0, 0, 2.3), 790, '#C4E9FF', 3.5)
    kit.area('Peach wall bounce', (0, -3.5, 2), (0, 0, 2), 240, '#FFDFC9', 3.2)
    kit.box('Soft pastel timber wall', (72, 0.25, 13), (0, 8.5, 6.5),
            kit.material('Muted blue wall paint', '#70979E', 0.76), bevel=0.14, ground=True)
    camera = kit.camera((5.6, -7.5, 4.0), (0, 0, 2.35), lens=45)
    target = kit.target_of(camera)
    kit.animate(camera, 'location',
                lambda t: (5.6 - 1.6 * math.sin(math.tau * t), -7.5, 3.7 + route(t).z * 0.28),
                step=2)
    kit.animate(target, 'location',
                lambda t: (0.18 * route(t).x, 0.16 * route(t).y, 1.14 + 0.39 * route(t).z), step=2)
    kit.render(motion_blur=False, bounces=6, exposure=-0.12)
