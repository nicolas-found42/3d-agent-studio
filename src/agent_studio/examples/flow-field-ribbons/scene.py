"""Integrate a noisy corkscrew field and reveal its layered strands by arc progress."""
import math

from mathutils import Vector, noise

RIBBONS = 208
STEPS = 59
STEP = 0.265
PALETTE = ('#22EBCB', '#1BA6CC', '#486CF5', '#9355D6', '#EF54B2', '#FF789C')


def centre(y):
    return Vector((0.68 * math.sin(y * 0.24), y, 0.48 * math.sin(y * 0.34 + 0.5)))


def field(p):
    """Keep an open channel while gently varying twist, spacing and longitudinal speed."""
    line = centre(p.y)
    x, z = p.x - line.x, p.z - line.z
    speed = 1.0 + 0.14 * math.cos(x * 0.67 + z * 0.8)
    twist = 0.28 + 0.10 * math.sin(p.y * 0.41)
    dilation = 0.045 * math.sin(p.y * 0.47)
    drift_x = speed * 0.68 * 0.24 * math.cos(p.y * 0.24)
    drift_z = speed * 0.48 * 0.34 * math.cos(p.y * 0.34 + 0.5)
    turn = Vector((drift_x - twist * z + dilation * x, speed, drift_z + twist * x + dilation * z))
    return turn + 0.19 * noise.noise_vector(p * 0.37, noise_basis='PERLIN_NEW')


def gradient_emission(kit, name, color):
    material = kit.emissive(name, color, 2.3)
    tree = material.node_tree
    coordinates = tree.nodes.new('ShaderNodeTexCoord')
    axes = tree.nodes.new('ShaderNodeSeparateXYZ')
    length = tree.nodes.new('ShaderNodeMapRange')
    length.inputs['From Min'].default_value = -7
    length.inputs['From Max'].default_value = 10
    channels = tuple(int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    deep = tuple(c * 0.43 for c in channels)
    pale = tuple(0.17 + c * 0.83 for c in channels)
    bands = kit.color_ramp(tree, [(0, deep), (0.21, color), (0.49, pale), (0.71, color), (1, deep)])
    tree.links.new(coordinates.outputs['Object'], axes.inputs[0])
    tree.links.new(axes.outputs['Y'], length.inputs['Value'])
    tree.links.new(length.outputs[0], bands.inputs['Fac'])
    tree.links.new(bands.outputs['Color'], tree.nodes['Emission'].inputs['Color'])
    return material


def position_at(points, progress):
    x = progress * (len(points) - 1)
    i = min(len(points) - 2, int(x))
    return points[i].lerp(points[i + 1], x - i)


def build(kit):
    kit.render(engine='EEVEE', motion_blur=False, exposure=-0.45)
    kit.world('#010208', 0.015)
    materials = [gradient_emission(kit, f'Flow spectral band {i + 1}', c) for i, c in enumerate(PALETTE)]
    tips = [kit.emissive(f'Growing tip {i + 1}', c, 4.5) for i, c in enumerate(PALETTE)]

    outline = [(0.108 * math.cos(a * math.tau / 8), 0.014 * math.sin(a * math.tau / 8), 0)
               for a in range(8)]
    profile = kit.tube('Elliptical ribbon section', outline, radius=0, closed=True)
    profile.location.z = -1000
    profile.hide_render = True
    profile['studio_ground'] = True

    for n in range(RIBBONS):
        theta = math.tau * (n * 0.61803399 % 1)
        y = -6.0 + kit.rng.uniform(-1.2, 1.2)
        radius = 1.74 + 2.95 * math.sqrt((n + 0.5) / RIBBONS)
        p = centre(y) + Vector((math.cos(theta) * radius, 0, math.sin(theta) * radius * 0.8))
        points = [p.copy()]
        for _ in range(STEPS):
            # Midpoint integration preserves the curl without coarse Euler kinks.
            p += field(p + field(p) * (STEP * 0.5)) * STEP
            points.append(p.copy())
        width = 0.009 + 0.022 * kit.rng.random()
        taper = [0.17 + 0.83 * math.sin(math.pi * i / STEPS) ** 0.67 for i in range(STEPS + 1)]
        band = min(len(PALETTE) - 1, int(theta / math.tau * len(PALETTE)))
        strand = kit.tube(f'Field ribbon {n + 1:03}', points, width, materials[band],
                          resolution=8, taper=taper)
        if n % 13 == 0:
            strand.data.bevel_mode = 'OBJECT'
            strand.data.bevel_object = profile
            for i, point in enumerate(strand.data.splines[0].bezier_points):
                point.tilt = 0.9 * math.sin(0.18 * i + theta)

        delay = 0.06 + 0.30 * kit.rng.random()
        finish = 0.61 + 0.32 * kit.rng.random()
        initial = 0.16 + 0.28 * kit.rng.random()

        def extent(t, delay=delay, finish=finish, initial=initial):
            u = kit.ease(kit.segment(t, delay, finish), 'smooth')
            return initial + (1 - initial) * u

        kit.animate(strand.data, 'bevel_factor_end', extent, step=3)
        if n % 6 == 0:
            tip = kit.ico(f'Bright leading tip {n + 1:03}', 0.041, material=tips[band], subdivisions=2)
            kit.animate(tip, 'location', lambda t: position_at(points, extent(t)), step=2)

    start = (1.5, -12.2, 0.5)
    end = (-0.55, -3.8, 0.38)
    aim_start, aim_end = (0.3, 0.0, 0.35), (0.6, 7.1, 0.45)
    focus = kit.empty('Inner flow focus', (0.1, -2.9, 0.1))
    kit.animate(focus, 'location', lambda t: (0.1, -2.9 + 5.4 * t, 0.1), step=3)
    camera = kit.camera(start, aim_start, lens=25, dof=focus, fstop=0.50)
    kit.dolly(camera, start, end, aim_start, aim_end, ease_kind='smooth')
    kit.glow(strength=0.52, size=0.37, threshold=0.82)
