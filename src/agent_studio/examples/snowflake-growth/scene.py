"""Grow a six-fold ice crystal using radial hierarchies and staggered branches."""
import math

ARMS = 6
BRANCHES = ((.39, .39), (.63, .52), (.88, .47), (1.12, .45), (1.36, .37), (1.57, .28))
ICE = '#93DBFF'


def point(length, angle, z=0):
    return length * math.cos(angle), length * math.sin(angle), z


def build(kit):
    ice = kit.material('Faceted ice', ICE, .15, metallic=.31, transmission=.34, coat=.8, ior=1.31)
    frost = kit.material('Frosted growth tips', '#76B9E8', .28, metallic=.26, coat=.7)
    shadow = kit.procedural('Out of focus frozen field', 'stone', ['#020617', '#081A36', '#174163'],
                            scale=.68, roughness=.75, bump=.29)
    kit.plane('Background', (24, 24), (0, 0, -.7), shadow, ground=True)
    root = kit.empty('Crystal axis')
    core = kit.cylinder('Hexagonal seed plate', .41, .075, material=ice, segments=6, bevel=.023)
    core.parent = root
    ring = kit.cylinder('Inset hexagon', .245, .03, (0, 0, .048), frost, segments=6, bevel=.015)
    ring.parent = root
    glint = kit.emissive('Small blue ice highlights', '#82C5FF', 1.2)
    for i in range(44):
        x, y = kit.rng.uniform(-2.7, 2.7), kit.rng.uniform(-2.7, 2.7)
        if math.hypot(x, y) >= 1.55:
            kit.sphere(f'Backlit frozen speck {i}', kit.rng.uniform(.007, .024), (x, y, -.58),
                       glint, segments=8, rings=5)
    for arm in range(ARMS):
        a = math.tau * arm / ARMS
        rig = kit.empty(f'Dendrite {arm + 1}')
        rig.parent = root
        rig.rotation_euler.z = a
        # A raised ridge gives grazing light separate planes to catch.
        stem = kit.mesh('Faceted primary ice prism',
                        [(0,-.12,0), (1.74,-.068,0), (1.98,0,0), (1.74,.068,0), (0,.12,0),
                         (0,0,.16), (1.72,0,.105), (.96,0,.12)],
                        [(0,5,7),(0,7,1),(7,6,1),(1,6,2),(2,6,3),(3,6,7),(3,7,4),
                         (4,7,5),(4,5,0),(0,1,2,3,4)], ice)
        kit.bevel(stem,.004,2)
        kit.tube('Frost on raised spine', [(0,0,.16),(.96,0,.12),(1.72,0,.105),(1.98,0,0)],
                 .014,frost,resolution=3).parent = stem
        stem.parent = rig
        kit.key(stem, 'scale', [(0., (.18, .85, .85)), (.66, (1, 1, 1)),
                                 (1., (1, 1, 1))])
        for i, (distance, length) in enumerate(BRANCHES):
            t = .13 + i * .08
            for side in (-1, 1):
                angle = side * math.pi / 3
                end = point(length, angle)
                rib = kit.tube(f'Branch {i}.{side}', [(0, 0, 0), end], .038 - i * .002, ice, resolution=2)
                rib.location = (distance, 0, .019)
                rib.parent = rig
                kit.grow(rib, t, t + .28, ease_kind='out')
                for j, fraction in enumerate((.53, .8)):
                    tx, ty, _ = point(length * fraction, angle)
                    twig = kit.tube(f'Twig {i}.{side}.{j}', [(0, 0, 0), (.12 + .02 * j, 0, .006)],
                                    .016, frost, resolution=2)
                    twig.location = (distance + tx, ty, .017)
                    twig.parent = rig
                    kit.grow(twig, t + .23, t + .47, ease_kind='out')
    kit.animate(root, 'rotation_euler', lambda t: (.045 * math.sin(math.pi * t), .08 * math.sin(math.pi * t), -.2 + .92 * t),
                step=4)
    kit.world('#2E509C', .085)
    kit.area('Icy rim', (-3, 4, 2), (0, 0, 0), 380, '#A2DAFF', 3.3)
    kit.area('Clean specular sweep', (4.8, -3.5, 2.1), (0, 0, 0), 470, '#E2FDFF', 2.8)
    kit.area('Soft violet fill', (0, 0, 6), (0, 0, 0), 140, '#AAABFF', 4)
    kit.camera((0, -2.33, 7), (0, 0, 0), ortho_scale=4.85)
    kit.render(bounces=5)
