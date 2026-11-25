"""The society sim as a living miniature, driven by its own journal.

Seven places stand in a ring around the parish commons, in the same clockwise order as the
observer window (granary at the top, then market, well, hut, shrine, woods, field). Twelve
villagers walk the ring path between them, following the moves recorded in the sim's journal
(one recorded turn per second). A small gem over each head shows the motive behind the current
action. The light runs from late afternoon into a lantern-lit dusk, and the camera cranes down
from a high oblique view with a tilt-shift focus, like looking down on a model village.
"""
import math
import random

import bpy
from mathutils import Vector

PLACES = ['granary', 'market', 'well', 'hut', 'shrine', 'woods', 'field']
RING = 8.0            # radius of the ring path (m)
BUILD_R = 11.2        # buildings sit just outside the path
SLOT_R = 9.3          # villagers gather between the path and the building
MOTIVE_COLORS = {'fear': '#E0524A', 'duty': '#4F86E8', 'hunger': '#F2A23A', 'thirst': '#3CC7D8',
                 'kinship': '#9C6BE0', 'promise': '#F2D45C'}
VILLAGER_COLORS = ['#8FD17F', '#F1E8D2', '#8FB2F0', '#E9875F', '#B9AE96', '#F0C76E',
                   '#7FCF8A', '#A7D49B', '#9CC7F2', '#D9A6E8', '#F2B8A2', '#C8D88A']


def angle_of(place):
    # Granary at the top (+Y); the ring runs clockwise as in the observer window.
    return math.radians(90 - 360 / 7 * PLACES.index(place))


def on_ring(angle, radius):
    return Vector((radius * math.cos(angle), radius * math.sin(angle), 0))


def build(kit):
    rows = kit.data(next(r.id for r in kit.references if r.kind == 'data'))
    turns = sorted({r['turn'] for r in rows})[:kit.seconds]          # one recorded turn per second
    names = sorted({r['agent'] for r in rows})[:12]
    plan = {(r['turn'], r['agent']): r for r in rows}
    kit.note(f'turns {turns[0]}-{turns[-1]}, villagers {names}')

    # ---------------------------------------------------------------- ground and commons
    rng = random.Random(kit.brief['seed'])
    grass = kit.procedural('Meadow', 'leaf', colors=['#2E4A30', '#4F673C', '#78854E'], scale=1.5, roughness=.91)
    soil = kit.procedural('Cut soil', 'ground', colors=['#362824', '#584137', '#7D5946'], scale=1.8, roughness=.85)
    base = kit.material('Fumed edge under the model', '#302923', .42, bump=(25, .12))
    kit.ground(kit.material('Blue-grey display surface', '#2C404A', .69), z=-1.55, size=180, name='Studio table')
    kit.cylinder('Machined plinth', 16.98, .42, (0, 0, -1.34), base, segments=144, bevel=.13)
    kit.cylinder('Earth section of the model', 16.71, 1.17, (0, 0, -.62), soil, segments=144, bevel=.12)
    kit.cylinder('Meadow cap', 16.71, .11, (0, 0, -.049), grass, segments=144, bevel=.046)
    path_mat = kit.procedural('Packed earth path', 'ground', colors=['#6B5338', '#866846', '#9C7F58'], scale=0.8)
    kit.torus('Ring path', RING, 0.93, (0, 0, -.20), path_mat, segments=128, sides=16).scale.z = .24
    stone = kit.procedural('Commons flagstones', 'stone', colors=['#8A8478', '#A49C8C', '#BDB4A2'], scale=0.7)
    kit.cylinder('Commons plaza', 4.2, 0.16, (0, 0, 0.05), stone, segments=64, bevel=0.03)
    kit.cylinder('Commons ring kerb', 4.35, 0.2, (0, 0, 0.04), kit.procedural('Kerb', 'stone', scale=1.4), segments=64)
    gravel = kit.material('Sun-bleached path stones', '#9F9272', .89, bump=(37, .16))
    for side in (-1, 1):
        for i in range(71):
            a = math.tau * i / 71 + rng.uniform(-.016, .016)
            x, y, _ = on_ring(a, RING + side * (0.70 + rng.uniform(-.045, .045)))
            kit.ico(f'Ring stone {side}.{i}', rng.uniform(.065, .16), (x, y, .027), gravel, subdivisions=1)
    for i in range(60):
        a = rng.uniform(0, math.tau)
        x, y, _ = on_ring(a, rng.uniform(13.2, 16.05))
        kit.rock(f'Meadow border stone {i}', rng.uniform(.06, .28), (x, y, .02), gravel, detail=1)
    kit.tree('Commons oak', 4.6, (0, 0.6, 0.1), 'broadleaf', seed=3)
    for i in range(6):
        a = math.radians(i * 60 + 15)
        kit.box(f'Commons bench {i}', (1.3, 0.35, 0.42), tuple(on_ring(a, 3.2) + Vector((0, 0, 0.21))),
                kit.procedural('Bench oak', 'wood', scale=2), rotation=(0, 0, math.degrees(a) + 90), bevel=0.02)
    # Spokes: the faint lines from the commons to each place in the observer window.
    for p in PLACES:
        a = angle_of(p)
        kit.box(f'Spoke {p}', (RING - 4.4, 0.7, 0.06), tuple(on_ring(a, (RING + 4.4) / 2) + Vector((0, 0, 0.02))),
                path_mat, rotation=(0, 0, math.degrees(a)))

    # ---------------------------------------------------------------- the seven places
    timber = kit.procedural('Timber', 'wood', colors=['#5A3B22', '#7A5232', '#93683F'], scale=1.5)
    plaster = kit.material('Lime plaster', '#E4D9C3', 0.85, bump=(18, 0.08))
    thatch = kit.procedural('Thatch', 'sand', colors=['#8E6E3A', '#A8864A', '#C2A060'], scale=3, bump=0.6)
    roof_tile = kit.material('Red clay tiles', '#9E4B32', 0.7, bump=(30, 0.15))
    ridge_clay = kit.material('Red clay ridge details', '#A35237', .70, bump=(36, .16))
    sign_paint = kit.emissive('Painted location lettering', '#F2DEAE', 0.94)
    lanterns = []

    def lantern(name, pos):
        glow = kit.emissive(f'{name} lantern flame', '#FFB65C', 0.0)
        kit.cylinder(f'{name} lantern post', 0.05, 1.6, tuple(pos + Vector((0, 0, 0.8))), timber, segments=12)
        kit.sphere(f'{name} lantern', 0.16, tuple(pos + Vector((0, 0, 1.7))), glow, segments=16, rings=8)
        light = kit.point(f'{name} lantern light', tuple(pos + Vector((0, 0, 1.75))), 0.0, '#FFB060', 0.15)
        lanterns.append((glow, light))

    def house(name, center, facing, w, d, h, roof, roof_h):
        """A plastered building with a gabled roof; width runs along the ring, door faces the commons."""
        out = Vector((math.cos(facing), math.sin(facing), 0))       # away from the commons
        along = Vector((-math.sin(facing), math.cos(facing), 0))    # along the ring
        rot = math.degrees(facing) + 90                             # box X axis -> along
        kit.box(f'{name} walls', (w, d, h), tuple(center + Vector((0, 0, h / 2))), plaster, rotation=(0, 0, rot), bevel=0.03)
        kit.box(f'{name} sill beam', (w + 0.1, d + 0.1, 0.18), tuple(center + Vector((0, 0, 0.09))), timber, rotation=(0, 0, rot))
        for s in (-1, 1):
            kit.box(f'{name} corner post {s}', (0.18, d + 0.12, h), tuple(center + along * s * w / 2 + Vector((0, 0, h / 2))),
                    timber, rotation=(0, 0, rot))
        ew, ed, z = w / 2 + 0.3, d / 2 + 0.4, h
        verts = [center + along * sx * ew + out * sy * ed + Vector((0, 0, z)) for sx in (-1, 1) for sy in (-1, 1)]
        verts += [center + along * sx * ew + Vector((0, 0, z + roof_h)) for sx in (-1, 1)]
        # 0:(-,-) 1:(-,+) 2:(+,-) 3:(+,+) 4: ridge(-) 5: ridge(+)
        faces = [(0, 2, 5, 4), (3, 1, 4, 5), (0, 4, 1), (2, 3, 5), (0, 1, 3, 2)]
        kit.solidify(kit.mesh(f'{name} roof', verts, faces, roof), 0.12, 0)
        for side in (-1, 1):
            for tile in range(round(w / .18) + 2):
                along_roof = -.96 * ew + 1.92 * ew * tile / (round(w / .18) + 1)
                ridge = center + along * along_roof + Vector((0, 0, z + roof_h + .025))
                eave = center + along * along_roof + out * side * ed + Vector((0, 0, z + .035))
                kit.tube(f'{name} roof course {side}.{tile}', [tuple(ridge), tuple(eave)], .028,
                         ridge_clay if roof == roof_tile else roof, resolution=3)
        door = center - out * (d / 2 + 0.03)
        kit.box(f'{name} door', (0.9, 0.08, 1.7), tuple(door + Vector((0, 0, 0.85))), timber, rotation=(0, 0, rot))
        for sx in (-1, 1):
            win = center - out * (d / 2 + 0.03) + along * sx * w * 0.3 + Vector((0, 0, h * 0.6))
            kit.box(f'{name} window {sx}', (0.6, 0.06, 0.5), tuple(win), kit.emissive(f'{name} window glow {sx}', '#FFC37A', 0.0),
                    rotation=(0, 0, rot))

    for p in PLACES:
        a = angle_of(p)
        c = on_ring(a, BUILD_R)
        inward = a  # buildings face the commons: their door side points to -radial
        if p == 'granary':
            house('Granary', c, inward, 4.2, 3.2, 3.2, roof_tile, 1.9)
            for k in range(5):
                kit.sphere(f'Grain sack {k}', 0.32, tuple(on_ring(a + 0.09 * (k - 2), BUILD_R - 2.2) + Vector((0, 0, 0.25))),
                           kit.material('Burlap', '#B59A6A', 0.95, bump=(60, 0.2)), scale=(1, 0.8, 0.75))
        elif p == 'market':
            for k, col in enumerate(['#C2443A', '#2F6FA8', '#D9A43B']):
                s = on_ring(a + 0.22 * (k - 1), BUILD_R - 0.5)
                for dx in (-0.8, 0.8):
                    for dy in (-0.6, 0.6):
                        off = Vector((dx, dy, 0))
                        kit.cylinder(f'Stall {k} pole', 0.05, 2.2, tuple(s + off + Vector((0, 0, 1.1))), timber, segments=10)
                awning = kit.box(f'Stall {k} awning', (2.0, 1.6, 0.06), tuple(s + Vector((0, 0, 2.25))),
                                 kit.material(f'Awning {k}', col, 0.8, sheen=0.4), rotation=(8, 0, math.degrees(a)))
                kit.box(f'Stall {k} counter', (1.8, 0.7, 0.9), tuple(s + Vector((0, 0, 0.45))), timber, rotation=(0, 0, math.degrees(a)), bevel=0.02)
                for f in range(4):
                    kit.sphere(f'Stall {k} produce {f}', 0.12, tuple(s + Vector((-0.6 + f * 0.4, 0, 0.98))),
                               kit.material(f'Produce {k}{f}', ['#D8452E', '#E9A23B', '#6FA23C', '#8E3B63'][f], 0.5))
        elif p == 'well':
            well_stone = kit.procedural('Well stone', 'stone', scale=2.2)
            kit.lathe('Open well wall', [(.87, 0), (.87, .79), (.92, .85), (.91, .93), (.72, .93),
                                       (.70, .87), (.70, .26)], 48, well_stone, location=tuple(c))
            kit.cylinder('Well water', 0.72, 0.07, tuple(c + Vector((0, 0, 0.52))), kit.procedural('Well water', 'water'))
            for dx in (-0.8, 0.8):
                kit.box(f'Well post {dx}', (0.15, 0.15, 2.0), tuple(c + Vector((dx, 0, 1.0))), timber)
            kit.extrude('Well roof', [(-1.2, 0), (1.2, 0), (0, 0.8)], 1.4, roof_tile, location=tuple(c + Vector((0, -0.7, 2.0))),
                        rotation=(90, 0, 0))
        elif p == 'hut':
            house('Hut', c, inward, 3.0, 2.6, 2.2, thatch, 1.6)
        elif p == 'shrine':
            shrine_stone = kit.procedural('Shrine stone', 'marble', scale=0.6)
            kit.box('Shrine plinth', (2.2, 2.2, 0.4), tuple(c + Vector((0, 0, 0.2))), shrine_stone, rotation=(0, 0, math.degrees(a)), bevel=0.04)
            kit.arch('Shrine arch', 1.4, kind='gothic', depth=0.6, thickness=0.22, location=tuple(c + Vector((0, 0, 0.4))),
                     rotation=(0, 0, math.degrees(a) + 90), material=shrine_stone, pier_height=1.2, pier_width=0.3)
            for k in range(5):
                kit.cylinder(f'Shrine candle {k}', 0.05, 0.25, tuple(c + Vector((-0.5 + k * 0.25, 0, 0.52))),
                             kit.material('Wax', '#F2E8D0', 0.4, subsurface=0.3), segments=12)
        elif p == 'woods':
            for k in range(7):
                t = on_ring(a + 0.28 * (k - 3) / 3, BUILD_R + 1.5 * ((k * 37) % 3) - 1)
                kit.tree(f'Woods tree {k}', 4.5 + (k % 3), tuple(t), 'conifer' if k % 2 else 'broadleaf', seed=11 + k)
            for k in range(3):
                kit.cylinder(f'Log {k}', 0.22, 1.6, tuple(on_ring(a, BUILD_R - 2.4) + Vector((0, 0, 0.22 + 0.38 * (k == 2))) +
                             Vector((0, (k - 0.5) * 0.45 if k < 2 else 0, 0))), kit.procedural('Log bark', 'bark'),
                             rotation=(0, 90, math.degrees(a)), segments=20)
        elif p == 'field':
            wheat = kit.procedural('Wheat', 'sand', colors=['#B8902F', '#D4AE4C', '#E8CB72'], scale=6, bump=0.8)
            for k in range(6):
                row = on_ring(a + 0.08 * (k - 2.5), BUILD_R + 0.5)
                kit.box(f'Wheat row {k}', (0.45, 4.2, 0.75), tuple(row + Vector((0, 0, 0.37))), wheat,
                        rotation=(0, 0, math.degrees(a + 0.08 * (k - 2.5)) + 90), bevel=0.15)
            fence = on_ring(a, BUILD_R - 1.9)
            kit.box('Field fence rail', (0.08, 4.4, 0.08), tuple(fence + Vector((0, 0, 0.75))), timber, rotation=(0, 0, math.degrees(a)))
        # The small flat signs can also be read from the overhead observer view.
        sign = on_ring(a, RING - 1.6)
        kit.box(f'{p} sign post', (.16, .16, .56), tuple(sign + Vector((0, 0, .28))), timber, bevel=.027)
        kit.box(f'{p} signboard', (2.28, .74, .13), tuple(sign + Vector((0, 0, .61))), timber, bevel=.038)
        kit.text(p.upper(), .32, tuple(sign + Vector((0, 0, .684))), rotation=(0, 0, 0),
                 material=sign_paint, extrude=.008, font='fontsource:cinzel@700', name=f'{p} sign text')
        lantern(p, on_ring(a + 0.12, RING + 1.3))

    # ---------------------------------------------------------------- villagers from the journal
    def place_of(turn, name, last):
        r = plan.get((turn, name))
        return (r['place'], r['why']) if r else last

    frames_per_turn = kit.fps
    for v, name in enumerate(names):
        body = kit.material(f'{name} tunic', VILLAGER_COLORS[v % len(VILLAGER_COLORS)], 0.8, sheen=0.3)
        skin = kit.material(f'{name} skin', '#D9B08C', 0.6, subsurface=0.08)
        J = kit.figure(name, 1.9, (0, 0, 0), material=body, head_material=skin, build=1.25)
        gem_mat = kit.emissive(f'{name} motive', '#FFFFFF', 3.0)
        gem = kit.ico(f'{name} motive gem', 0.2, (0, 0, 0), gem_mat, subdivisions=1)
        gem.parent = J['root']
        gem.location = (0, 0, 2.35)
        # Per-turn place and motive, then a slot so villagers at one place stand apart.
        seq, last = [], ('well', 'duty')
        for turn in turns:
            last = place_of(turn, name, last)
            seq.append(last)
        slot = (v * 0.61) % 1.0 - 0.5

        def pos(t, seq=seq, slot=slot):
            x = t * len(seq)
            i = min(int(x), len(seq) - 1)
            u = kit.ease(min(1.0, (x - i) / 0.75), 'in_out', 2.2)      # walk during the first 3/4 of a turn
            a0 = angle_of(seq[i - 1][0] if i else seq[0][0])
            a1 = angle_of(seq[i][0])
            da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi          # shortest way round the ring
            a = a0 + da * u
            radius = kit.lerp(SLOT_R, RING, math.sin(math.pi * u)) if abs(da) > 1e-3 else SLOT_R
            return on_ring(a + slot * 0.16, radius), a, da

        def location(t):
            p, _, _ = pos(t)
            return p + Vector((0, 0, 0.02))

        unwrap = {'last': None}

        def heading(t):
            # The figure's front is -Y, so facing direction phi needs a Z rotation of phi + 90 degrees.
            p0, _, _ = pos(max(0.0, t - 0.004))
            p1, a, _ = pos(min(1.0, t + 0.004))
            d = p1 - p0
            z = (a + math.pi * 1.5) if d.length < 1e-4 else math.atan2(d.y, d.x) + math.pi / 2
            if unwrap['last'] is not None:                              # no spins across the +-pi seam
                z = unwrap['last'] + (z - unwrap['last'] + math.pi) % (2 * math.pi) - math.pi
            unwrap['last'] = z
            return (0, 0, z)

        kit.animate(J['root'], 'location', location)
        kit.animate(J['root'], 'rotation_euler', heading)

        def stride(t, side):
            p0, _, _ = pos(max(0.0, t - 0.004))
            p1, _, _ = pos(min(1.0, t + 0.004))
            speed = min(1.0, (p1 - p0).length / 0.06)
            return math.radians(32 * speed * math.sin(t * kit.seconds * 2 * math.pi * 1.8 + (math.pi if side == 'r' else 0)))
        for side in ('l', 'r'):
            kit.animate(J[f'hip_{side}'], 'rotation_euler', lambda t, s=side: (stride(t, s), 0, 0))
            kit.animate(J[f'shoulder_{side}'], 'rotation_euler', lambda t, s=side: (-0.8 * stride(t, s), 0, 0))
        # Motive gem color follows the recorded reason for each turn's action.
        node = gem_mat.node_tree.nodes['Emission']
        keys = []
        for i, (_, why) in enumerate(seq):
            keys.append((1 + i * frames_per_turn, (*kit.color(MOTIVE_COLORS.get(why, '#FFFFFF'))[:3], 1)))
        kit.key(node.inputs['Color'], 'default_value', keys, interpolation='CONSTANT')

    # ---------------------------------------------------------------- light: afternoon into dusk
    sky = kit.sky(sun_elevation=18, sun_rotation=210, strength=0.12)
    kit.animate(sky, 'sun_elevation', lambda t: math.radians(kit.lerp(20, 1.5, kit.ease(t, 'in', 1.6))))
    world_bg = kit.scene.world.node_tree.nodes['Background']
    kit.animate(world_bg.inputs['Strength'], 'default_value', lambda t: kit.lerp(0.12, 0.094, kit.ease(t, 'in', 1.4)))
    kit.area('Cool dusk bounce', (8, -12, 16), (0, 0, 0), 1350, '#B7CDF8', 12)
    for mat in [m for m in bpy.data.materials if 'window glow' in m.name]:
        socket = mat.node_tree.nodes['Emission'].inputs['Strength']
        kit.animate(socket, 'default_value', lambda t: 12 * kit.ease(kit.segment(t, 0.4, 0.85), 'smooth'))
    for glow, light in lanterns:
        socket = glow.node_tree.nodes['Emission'].inputs['Strength']
        kit.animate(socket, 'default_value', lambda t: 30 * kit.ease(kit.segment(t, 0.3, 0.75), 'smooth'))
        kit.animate(light.data, 'energy', lambda t: 180 * kit.ease(kit.segment(t, 0.3, 0.75), 'smooth'))
    kit.haze(0.002, '#FFD9B0', size=(42, 42, 12), location=(0, 0, 6))

    # ---------------------------------------------------------------- camera: crane down, tilt-shift
    start, end = Vector((6, -43, 49)), Vector((0, -10, 44))
    cam = kit.camera(tuple(start), (0, 1.5, 0), lens=51, dof=60, fstop=1.4)
    kit.path(cam, [tuple(start), (3, -29, 47), tuple(end)], targets=[(0, 2.5, 0), (0, 0.5, 0)], ease_kind='in_out')
    kit.animate(cam.data, 'lens', lambda t: kit.lerp(51, 35, kit.ease(t, 'in_out')))
    kit.animate(cam.data.dof, 'focus_distance', lambda t: (kit.lerp(start, end, kit.ease(t)) - Vector((0, 0, 0.5))).length)
    kit.render(look='AgX - Base Contrast')
