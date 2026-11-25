"""A translucent cross-section with batched lipids and editable membrane proteins."""
import math

STEP = .24
OFFSETS = (-.075, .075)


def build(kit):
    heads = [
        kit.material('Extracellular blue phosphates', '#579FC0', .28, subsurface=.14, coat=.3),
        kit.material('Cytosolic teal phosphates', '#5DC7BA', .28, subsurface=.14, coat=.3),
    ]
    tails = kit.material('Fatty-acid tails', '#3C818E', .31, subsurface=.12)
    proteins = [
        kit.material('Rose channel protein', '#FE9C94', .35, subsurface=.17, coat=.24),
        kit.material('Periwinkle receptor', '#AAA1F7', .36, subsurface=.18, coat=.18),
        kit.material('Apricot sugar residues', '#FFC492', .33, subsurface=.24),
    ]
    channels = [(-2.9, -.1, .47), (.8, -.58, .68), (4, .65, .53), (2.45, 2.1, .47)]
    molecules = [[] for _ in range(2)]
    for row in range(18):
        for col in range(51):
            x = (col - 25 + .5 * (row % 2)) * STEP
            y = (row - 8.5) * STEP
            if any(math.hypot(x - a, y - b) < r + .07 for a, b, r in channels):
                continue
            for i, side in enumerate((1, -1)):
                z = side * .43 + kit.rng.uniform(-.036, .036) + .05 * math.sin(x * .8 + y)
                molecules[i].append((x + kit.rng.uniform(-.023, .023), y, z))

    # Mesh batching keeps the individual lipids editable without a thousand object datablocks.
    head_verts = [(0, 0, 1), (0, 0, -1)] + [
        (math.cos(k * math.pi / 3), math.sin(k * math.pi / 3), 0) for k in range(6)]
    head_faces = [(0, 2+k, 2+((k+1) % 6)) for k in range(6)] + [
        (1, 2+((k+1) % 6), 2+k) for k in range(6)]
    for i, side in enumerate((1, -1)):
        verts, faces, tail_verts, tail_faces = [], [], [], []
        for x, y, z in molecules[i]:
            base = len(verts)
            verts.extend((x + a * .098, y + b * .098, z + c * .092) for a, b, c in head_verts)
            faces.extend(tuple(base + n for n in face) for face in head_faces)
            for tail in OFFSETS:
                base = len(tail_verts)
                for ring in range(4):
                    for k in range(5):
                        a = math.tau * k / 5
                        tail_verts.append((x + tail * (ring/3) + .018 * math.cos(a),
                                           y + .018 * math.sin(a) + .025 * math.sin(ring * 1.4 + x),
                                           z - side * ring * .108))
                for ring in range(3):
                    for k in range(5):
                        a = base + 5 * ring + k
                        b = base + 5 * ring + (k + 1) % 5
                        face = (a, b, b + 5, a + 5)
                        tail_faces.append(face if side == -1 else face[::-1])
        for name, points, faces_, mat in (
                ('Phosphate beads', verts, faces, heads[i]), ('Paired fatty chains', tail_verts, tail_faces, tails)):
            obj = kit.mesh(f'{name}, leaflet {i+1}', points, faces_, mat, smooth=True)
            obj.shape_key_add(name='Rest')
            posed = obj.shape_key_add(name='Thermal displacement')
            for vertex, (x, y, z) in zip(posed.data, points):
                vertex.co.z += .045 * math.sin(3.3 * x + 4.2 * y) + .03 * math.cos(9.3 * (y + z))
            kit.animate(posed, 'value', lambda t: .5 + .5 * math.sin(math.tau * 2 * t), step=6)

    for index, (x, y, r) in enumerate(channels):
        root = kit.empty(f'Channel {index+1}', (x, y, 0))
        for n in range(6):
            a = math.tau * n / 6
            parts = []
            for step in range(24):
                z = -1 + step * .087
                angle = a + .27 * math.sin(step * .22 + n)
                span = r * (.64 + .46 * abs(z))
                parts.append((span * math.cos(angle), span * math.sin(angle), z))
            kit.tube('Channel subunit', parts, .225, proteins[index % 2], resolution=5).parent = root
        if index in (1, 3):
            for n in range(3):
                a = -.9 + n * .7
                for segment in range(5):
                    z = .9 + .18 * segment
                    kit.sphere('Glycan sugar', .105, (.25 + math.sin(a) * .12 * segment,
                                                     .15 + math.cos(a) * .1 * segment, z), proteins[2],
                               segments=12, rings=8).parent = root
        kit.animate(root, 'location', lambda t, x=x, y=y, n=index: (
            x + .08 * math.sin(math.tau*t+n), y + .07 * math.cos(math.tau*t+n), 0), step=6)

    kit.world('#173647', .34, top='#327C91')
    kit.area('Diffused membrane backlight', (-2, 3, 2.8), (0, 0, 0), 780, '#DBFEFC', 5)
    kit.area('Pink secondary light', (5, -3, 1), (1, 0, .1), 330, '#FFB5CF', 3)
    kit.area('Underleaf blue bounce', (-4, -2, -2.5), (0, 0, 0), 160, '#91DAFF', 5)
    cam = kit.camera((-3.25, -6.35, 2.6), (-.9, -.1, .05), lens=37)
    kit.dolly(cam, (-3.25, -6.35, 2.6), (2.6, -5.8, 2.25), (-.9, -.1, .05), (1.3, .1, .05))
    kit.render(bounces=4)
