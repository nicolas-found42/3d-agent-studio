"""Fit a macro rig around three meshing gears with pitch-matched involute teeth."""
import math

from mathutils import Vector

MODULE = 0.042
TOOTH_COUNTS = (24, 16, 32)
PRESSURE = math.radians(20)


def involute(a):
    return math.tan(a) - a


def wheel_outline(teeth):
    pitch = MODULE * teeth / 2
    base = pitch * math.cos(PRESSURE)
    root, tip = pitch - 1.25 * MODULE, pitch + MODULE
    half = math.pi / (2 * teeth)
    step = math.tau / teeth

    def flank(radius):
        a = math.acos(min(1.0, base / radius))
        return half + involute(PRESSURE) - involute(a)

    radii = [max(base, root) + (tip - max(base, root)) * i / 4 for i in range(5)]
    one_tooth = [(root, -step / 2), (root, -flank(radii[0]))]
    one_tooth += [(r, -flank(r)) for r in radii if r > root + 1e-5]
    one_tooth += [(r, flank(r)) for r in reversed(radii) if r > root + 1e-5]
    one_tooth += [(root, flank(radii[0]))]
    return [(r * math.cos(i * step + a), r * math.sin(i * step + a))
            for i in range(teeth) for r, a in one_tooth]


def build(kit):
    brass = kit.procedural('Brushed yellow brass', 'brushed_metal', ('#9B5623', '#ECB66A'), scale=0.6, bump=0.1)
    steel = kit.material('Blued steel', '#718B98', 0.27, metallic=0.92)
    ruby = kit.material('Bearing jewel', '#A32242', 0.19, transmission=0.34, coat=0.4)
    case = kit.material('Black oxide base plate', '#212226', 0.42, metallic=0.68, bump=(55, 0.09))
    inset = kit.material('Recessed brass lettering', '#BA8654', 0.44, metallic=0.62)
    kit.world('#15171D', 0.18)
    kit.ground(case, size=9, z=-0.37)
    kit.box('Chamfered clockwork plate', (4.85, 2.65, 0.27), (0, 0, -0.24), case, bevel=0.14)
    for y in (-1.18, 1.18):
        kit.tube(f'Engraved plate border {y}', [(-2.22, y, -0.096), (2.22, y, -0.096)], 0.009, inset)

    positions = (-1.05, -0.21, 0.798)
    # Tooth counts are all divisible by four; a half-tooth shift on the idler puts a gap at both meshes.
    # Four input turns give integer whole turns on all three shafts.
    turns = (4, -6, 3)
    for index, (n, x, cycles) in enumerate(zip(TOOTH_COUNTS, positions, turns)):
        centre = kit.empty(f'Gear {n} teeth pivot', (x, 0, 0.25))
        outline = wheel_outline(n)
        pitch = MODULE * n / 2
        bore = pitch * 0.77
        angles = [math.atan2(y, x) for x, y in outline]
        inner = [(bore * math.cos(a), bore * math.sin(a)) for a in angles]
        m = len(outline)
        vertices = [(x, y, z) for z in (-0.055, 0.055) for ring in (outline, inner) for x, y in ring]
        faces = []
        for i in range(m):
            j = (i + 1) % m
            faces.extend((
                (i, i + m, j + m, j),
                (i + 2*m, j + 2*m, j + 3*m, i + 3*m),
                (i, j, j + 2*m, i + 2*m),
                (i + m, i + 3*m, j + 3*m, j + m)))
        wheel = kit.mesh(f'Involute perimeter {n}', vertices, faces, brass)
        kit.bevel(wheel, 0.009)
        wheel.parent = centre
        for a in range(6):
            angle = a * math.tau / 6
            spoke = kit.box(f'Gear {n} tapered spokes {a}', (bore * 1.01, pitch * 0.15, 0.09),
                            (bore * 0.52 * math.cos(angle), bore * 0.52 * math.sin(angle), 0),
                            brass, rotation=(0, 0, math.degrees(angle)), bevel=0.025)
            spoke.parent = centre
        hub = kit.cylinder(f'Gear {n} turned brass hub', pitch * 0.29, 0.15, (0, 0, 0), brass, bevel=0.018)
        hub.parent = centre
        kit.cylinder(f'Gear {n} steel arbor', 0.045, 0.45, (x, 0, 0.12), steel, bevel=0.009)
        kit.torus(f'Gear {n} ruby bearing', 0.072, 0.033, (x, 0, 0.337), ruby, segments=36, sides=12)
        kit.cylinder(f'Gear {n} slotted steel screw', 0.045, 0.035, (x, 0, 0.371), steel, bevel=0.004)
        kit.box(f'Gear {n} recessed screw slot', (0.066, 0.012, 0.005), (x, 0, 0.39), case, bevel=0.002)
        kit.spin(centre, 'Z', turns=cycles, offset_deg=180 / n if index == 1 else 0)

    # An oscillator hints at an escapement beside the train without obscuring the tooth contacts.
    lever = kit.box('Bifurcated escapement lever', (0.47, 0.055, 0.045), (1.18, 0.81, 0.07),
                    steel, bevel=0.014)
    kit.animate(lever, 'rotation_euler', lambda t: math.radians(7) * math.sin(math.tau * 8 * t), step=2, index=2)

    kit.area('Amber bench practical', (-1.85, -0.9, 2.1), (0, 0, 0.2), 160, '#FFD398', 0.7, shape='DISK')
    kit.area('Cool narrow reflection card', (0.4, 2.0, 1.05), (0, 0, 0.2), 90, '#9DBBFC', 2, size_y=0.28)
    kit.area('Plate fill', (2.7, -1.1, 0.8), (0, 0, 0.2), 30, '#FFE8D0', 1.15)
    focus = kit.empty('Mesh-contact focus', (-0.51, 0, 0.26))
    camera = kit.camera((-1.1, -2.0, 1.24), tuple(focus.location), lens=42, dof=focus, fstop=1.6)

    def slide(t):
        return 0.5 - 0.5 * math.cos(math.tau * t)

    kit.animate(camera, 'location', lambda t: Vector((-1.30 + 1.83 * slide(t), -2.75, 1.65)), step=3)
    kit.animate(focus, 'location', lambda t: Vector((-0.44 + 0.97 * slide(t), 0.03, 0.26)), step=3)
    aim = kit.target_of(camera)
    kit.animate(aim, 'location', lambda t: Vector((-0.38 + 0.82 * slide(t), 0.10, 0.22)), step=3)
    kit.render(motion_blur=True, shutter=0.28, exposure=0.4, bounces=6)
