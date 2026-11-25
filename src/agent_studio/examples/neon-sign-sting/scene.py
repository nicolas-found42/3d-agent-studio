"""Bend neon tubes by hand and cue both glow and practical light in letter order."""

LETTER_PATHS = {
    'O': [[(.2, 0), (.03, .2), (.03, .84), (.2, 1), (.58, 1), (.75, .84), (.75, .2), (.58, 0), (.2, 0)]],
    'P': [[(.05, 0), (.05, 1), (.59, 1), (.76, .84), (.76, .68), (.59, .51), (.05, .51)]],
    'E': [[(.74, 0), (.06, 0), (.06, 1), (.74, 1)], [[.06, .51], [.6, .51]]],
    'N': [[(.04, 0), (.04, 1), (.73, 0), (.73, 1)]],
    'L': [[(.06, 1), (.06, 0), (.73, 0)]],
    'A': [[(.02, 0), (.35, 1), (.43, 1), (.77, 0)], [[.16, .43], [.62, .43]]],
    'T': [[(.01, 1), (.78, 1)], [[.395, 1], [.395, 0]]],
}


def build(kit):
    mortar = kit.material('Charcoal mortar', '#252227', .83, bump=(42, .27))
    glaze = kit.material('Wet asphalt', '#211F2A', .16, coat=.7, bump=(86, .12))
    cast = kit.material('Blackened mounting brackets', '#232531', .32, metallic=.8)
    bricks = [kit.procedural(f'Pressed brick tone {i}', 'stone', [shade, '#30262E', '#543B3C'],
                             scale=8, roughness=.56, bump=.24)
              for i, shade in enumerate(('#502C28', '#754132', '#613532', '#966753'))]
    kit.box('Mortar backing wall', (18, .45, 7), (0, .22, 3.3), mortar)
    for row in range(26):
        for col in range(-16, 17):
            x = (col + .5 * (row % 2)) * .52
            kit.box(f'Brick {row}.{col}', (.5, .12, .218), (x, -.035, row * .235 + .11),
                    kit.rng.choice(bricks), bevel=.012)
    kit.ground(glaze, 50)
    pool = kit.material('Puddled rainwater', '#33283A', .075, coat=1, ior=1.33, bump=(19, .07))
    kit.sphere('Main street puddle',1,(0,-4.27,.001),pool,segments=34,rings=10,
               scale=(3.65,1.69,.005))
    for i in range(21):
        x, y = kit.rng.uniform(-6, 6), kit.rng.uniform(-5.2, -1)
        kit.sphere(f'Rain puddle {i}', 1, (x, y, .002), pool, segments=18, rings=8,
                   scale=(kit.rng.uniform(.3, 1.9), kit.rng.uniform(.16, .55), .003))
    def draw_tube(name, path, bulb):
        # Straight runs preserve the letter skeleton. Short bevels soften glass bends.
        rounded = [path[0]]
        for left, point, right in zip(path, path[1:], path[2:]):
            for neighbor in (left, right):
                rounded.append(tuple(p + .10 * (n - p) for p, n in zip(point, neighbor)))
        rounded.append(path[-1])
        kit.tube(name, rounded, .024, bulb, resolution=12, spline='POLY')

    for row, (word, color) in enumerate((('OPEN', '#FF4C96'), ('LATE', '#4AF0FF'))):
        z = 2.37 - row * 1.19
        kit.box('Painted support rail', (4.55, .145, .09), (0, -.145, z + .48), cast, bevel=.025)
        for index, char in enumerate(word):
            x = -1.94 + index * 1.065
            start = .018 + (index + row * 4) * .032
            bulb = kit.emissive(f'{row}.{char} neon phosphor', color, .035)
            for route in LETTER_PATHS[char]:
                pts = [(x + p, -.32, z + q) for p, q in route]
                draw_tube(f'{char} gas tube', pts, bulb)
                for px, _, pz in (pts[0], pts[-1]):
                    kit.cylinder('Stand-off insulator', .041, .24, (px, -.23, pz), cast,
                                 rotation=(90, 0, 0), segments=10)
            socket = next(node for node in bulb.node_tree.nodes if node.type == 'EMISSION').inputs['Strength']
            light = kit.point(f'{char} wall spill', (x + .36, -.54, z + .5), 0, color, .21)
            times = [(0., .0), (start, .0), (start + .015, .85), (start + .035, .09),
                     (start + .053, .64), (start + .066, 1.), (1., 1.)]
            kit.key(socket, 'default_value', [(t, .035 + v * 5) for t, v in times], interpolation='LINEAR')
            kit.key(light.data, 'energy', [(t, v * 32) for t, v in times], interpolation='LINEAR')
    kit.world('#22182F', .12)
    kit.area('Street bounce', (0, -4.6, 4.2), (0, 0, 2), 65, '#8373D4', 5)
    cam = kit.camera((.72, -10.8, 4.12), (0, -.66, 1.46), lens=39)
    kit.dolly(cam, (.72, -10.8, 4.12), (.05, -9.2, 3.65), ease_kind='in_out')
    kit.render(bounces=5)
