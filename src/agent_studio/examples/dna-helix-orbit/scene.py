"""A glossary-style double helix built from two continuous rails and colored paired bases."""
import math

PAIR_COUNT = 27
PITCH = 3.4
RADIUS = 1.04
BASE_COLORS = ('#F5894F', '#67CCE6', '#CC72EE', '#FFE16C')


def rail(z, phase=0):
    a = z / PITCH * math.tau + phase
    return RADIUS * math.cos(a), RADIUS * math.sin(a), z


def build(kit):
    backbone = kit.material('Ivory phosphate', '#D2E5DD', .22, metallic=.27, coat=.69)
    rail_mat = kit.material('Teal backbone links', '#5798A9', .26, metallic=.21)
    bases = [kit.material(f'Base type {letter}', hue, .24, metallic=.12, coat=.4)
             for letter, hue in zip('ATGC', BASE_COLORS)]
    root = kit.empty('Molecule axis')
    for strand in range(2):
        phase = strand * math.pi
        points = [rail(-3.7 + 7.4 * j / 168, phase) for j in range(169)]
        kit.tube(f'Phosphate chain {strand + 1}', points, .043, rail_mat, resolution=4).parent = root
        for i in range(PAIR_COUNT):
            z = -3.55 + 7.1 * i / (PAIR_COUNT - 1)
            kit.sphere(f'Phosphate bead {strand + 1}.{i}', .146, rail(z, phase), backbone,
                       segments=16, rings=10).parent = root
    for i in range(PAIR_COUNT):
        z = -3.55 + 7.1 * i / (PAIR_COUNT - 1)
        x, y, _ = rail(z)
        pair = 2 * ((i + i // 3) % 2)
        for j, side in enumerate((-1, 1)):
            kit.tube(f'Base pair {i}.{j}', [(x * side * .13, y * side * .13, z),
                                          (x * side * .88, y * side * .88, z)], .071,
                     bases[pair + (j ^ (i % 2))], resolution=3).parent = root
        kit.sphere(f'Base join {i}', .062, (0, 0, z), backbone, segments=10, rings=6).parent = root
    kit.spin(root, turns=-.40 if not kit.loop else -1)
    cam = kit.camera((4, -9, 0), (0, 0, 0), lens=44)
    kit.animate(cam, 'location', lambda t: (10.8 * math.cos(math.tau * t), 10.8 * math.sin(math.tau * t),
                                            .9 * math.sin(math.tau * t)), step=2)
    kit.animate(kit.target_of(cam), 'location', lambda t: (0, 0, .46 * math.sin(math.tau * t)), step=2)
    particle = kit.emissive('Far molecular haze', '#5BB0CD', .47)
    for i in range(35):
        angle = kit.rng.uniform(0, math.tau)
        radius = kit.rng.uniform(2, 4.1)
        z = kit.rng.uniform(-4.8,4.8)
        kit.sphere('Outlying molecule',kit.rng.uniform(.007,.022),
                   (radius*math.cos(angle),radius*math.sin(angle),z),particle,segments=8,rings=5)
    kit.world('#123155', .37, top='#4971AC')
    kit.area('Polar cyan key', (2, -4, 4), (0, 0, 0), 710, '#B3ECFF', 5)
    kit.area('Apricot strip light', (-4, -1, 1), (0, 0, 0), 650, '#FFC389', 3, size_y=6)
    kit.area('Backlight', (-1, 4, 0), (0, 0, 0), 760, '#6EC6FF', 5)
    kit.render(bounces=4)
