"""Market town agents: an agent-based simulation shown as a living tilt-shift miniature.

Teaches:
- turning an abstract simulation into a physical metaphor: every agent has a home, a goal (a stall,
  the well, another home) and a route along the town's paths, and moves at walking speed along it
  by arc length, so the crowd reads as purposeful rather than random;
- cheap crowds: a handful of shared figure meshes (one per clothing colour) instanced dozens of
  times, a head parented to each body, and walking read from a bob and a sway, not a full rig;
- the tilt-shift miniature look: a crane from high and wide down to the plaza, a focus distance
  keyed to follow the plaza, and an f-stop far below any real lens (0.06), because depth of field
  scales with the scene and a real-sized town needs a toy-sized aperture to look like a model;
- warm late-afternoon light from kit.sky at a low sun angle, long raking shadows, light warm haze;
- a cobblestone shader from Voronoi distance-to-edge (stones, mortar and per-stone colour from one
  texture) and striped awnings from a Wave texture.
"""
import math

import bpy
from mathutils import Vector

# ----------------------------------------------------------------------------- town layout (metres)
PLAZA_R = 13.0                 # cobbled plaza radius
STALL_RING = 8.6               # market stalls stand on this ring, facing the well
STALL_COUNT = 7
HOUSE_RING = 19.5              # first ring of homes around the plaza
OUTER_RING = 31.0              # second ring, further out (fills the ultrawide frame)
PATH_ANGLES = [-90, -20, 45, 115, 180]   # radial lanes out of the plaza (0 = +X, CCW, degrees)
LANE_HALF_WIDTH = 2.2

# ----------------------------------------------------------------------------- crowd
WALKERS = 46
TRADERS = 14                   # stand at stalls, bargaining (idle sway, facing the stall)
GATHERERS = 9                  # chat in a ring at the well
WALK_SPEED = (1.0, 1.45)       # m/s

# ----------------------------------------------------------------------------- palette
PLASTER = ['#EAD9BC', '#E8C69A', '#DDB4A0', '#CFD7C3', '#E9DFCB', '#D9C2A3', '#C9D3D8']
ROOF = ['#A4482E', '#B65A34', '#8E3F2A', '#9A5A3C', '#7D4A3A']
AWNING = [('#C8362F', '#F3E8D2'), ('#2F6FA8', '#F3E8D2'), ('#E2A030', '#F6EEDC'), ('#3F8A55', '#F1E9D6'),
          ('#8A3D7A', '#F3E8D2'), ('#D86A2B', '#F6EEDC'), ('#2D7F86', '#F3E8D2')]
CLOTHES = ['#B23A3A', '#2F5E9E', '#E0B13A', '#3E7D4E', '#7A4B8C', '#D9773A', '#EDE6D6', '#4A4A52', '#2C8C8C']
SKIN = ['#E2B896', '#C68E68', '#8D5A3F', '#F0CBA8']

# ----------------------------------------------------------------------------- shot
CAM_START = Vector((-12.0, -65.0, 54.0))
CAM_END = Vector((-1.5, -24.5, 15.0))
LOOK_START = Vector((0.0, 4.0, 0.0))
LOOK_END = Vector((0.0, 0.1, 1.1))
FSTOP = 0.06                   # toy aperture: see the module note


def sock(sockets, identifier):
    return next(s for s in sockets if s.identifier == identifier)


def polar(r, deg, z=0.0):
    a = math.radians(deg)
    return Vector((r * math.cos(a), r * math.sin(a), z))


def angle_gap(a, b):
    return abs((a - b + 180) % 360 - 180)


# ----------------------------------------------------------------------------- materials
def cobble_material(kit):
    """Voronoi cobbles: distance-to-edge gives mortar joints and bump; the cell colour varies
    each stone between three warm greys."""
    mat = kit.material('Cobblestones', '#9C8F7E', roughness=0.82)
    nt, bs = mat.node_tree, kit.bsdf(mat)
    coord = nt.nodes.new('ShaderNodeTexCoord')
    vor = nt.nodes.new('ShaderNodeTexVoronoi')
    vor.feature = 'DISTANCE_TO_EDGE'
    vor.inputs['Scale'].default_value = 2.6            # about 40 cm stones
    nt.links.new(coord.outputs['Object'], vor.inputs['Vector'])
    cells = nt.nodes.new('ShaderNodeTexVoronoi')
    cells.inputs['Scale'].default_value = 2.6
    nt.links.new(coord.outputs['Object'], cells.inputs['Vector'])
    tone = kit._ramp(nt, ['#7E7468', '#A49784', '#B9AC97', '#8C8579'])
    nt.links.new(cells.outputs['Color'], tone.inputs['Fac'])
    joint = nt.nodes.new('ShaderNodeMapRange')
    joint.inputs['From Min'].default_value, joint.inputs['From Max'].default_value = 0.02, 0.09
    nt.links.new(vor.outputs['Distance'], joint.inputs['Value'])
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    nt.links.new(joint.outputs['Result'], sock(mix.inputs, 'Factor_Float'))
    sock(mix.inputs, 'A_Color').default_value = kit.color('#4E463E')
    nt.links.new(tone.outputs['Color'], sock(mix.inputs, 'B_Color'))
    nt.links.new(sock(mix.outputs, 'Result_Color'), bs.inputs['Base Color'])
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.6
    nt.links.new(joint.outputs['Result'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bs.inputs['Normal'])
    return mat


def awning_material(kit, name, a, b):
    """Canvas stripes from a Wave texture in bands mode, sharpened by a constant ramp."""
    mat = kit.material(name, a, roughness=0.9, sheen=0.3)
    nt, bs = mat.node_tree, kit.bsdf(mat)
    coord = nt.nodes.new('ShaderNodeTexCoord')
    wave = nt.nodes.new('ShaderNodeTexWave')
    wave.inputs['Scale'].default_value = 2.2
    wave.inputs['Distortion'].default_value = 0.0
    wave.bands_direction = 'X'
    nt.links.new(coord.outputs['Object'], wave.inputs['Vector'])
    ramp = kit._ramp(nt, [(0.0, a), (0.5, b)], 'CONSTANT')
    nt.links.new(wave.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], bs.inputs['Base Color'])
    return mat


def clay_roof(kit, name, color):
    mat = kit.material(name, color, roughness=0.63)
    tree, bsdf = mat.node_tree, kit.bsdf(mat)
    coord = tree.nodes.new('ShaderNodeTexCoord')
    tiles = tree.nodes.new('ShaderNodeTexBrick')
    tiles.offset, tiles.offset_frequency = 0.5, 2
    tiles.inputs['Scale'].default_value = 1.25
    tiles.inputs['Brick Width'].default_value = 0.51
    tiles.inputs['Row Height'].default_value = 0.24
    tiles.inputs['Mortar Size'].default_value = 0.018
    rgb = kit.color(color)
    tiles.inputs['Color1'].default_value = rgb
    tiles.inputs['Color2'].default_value = (*[c * 0.56 for c in rgb[:3]], 1)
    tiles.inputs['Mortar'].default_value = kit.color('#533123')
    bump = tree.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.37
    bump.inputs['Distance'].default_value = 0.046
    bump.invert = True
    tree.links.new(coord.outputs['Object'], tiles.inputs['Vector'])
    tree.links.new(tiles.outputs['Color'], bsdf.inputs['Base Color'])
    tree.links.new(tiles.outputs['Fac'], bump.inputs['Height'])
    tree.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return mat


def build(kit):
    rng = kit.rng
    # Cycles with AgX Punchy: miniature photos are saturated and contrasty.
    kit.render(exposure=0.46, look='AgX - Punchy', bounces=5, motion_blur=False)

    # -------------------------------------------------------------------- light
    # Late afternoon: a low sun from the west rakes long shadows across the
    # cobbles; kit.sky supplies the matching warm sun and blue sky fill. A thin warm haze softens
    # the far rings of houses.
    kit.sky(sun_elevation=20, sun_rotation=215, strength=0.13, sun_disc=False, aerosol=1.45)
    kit.sun(elevation=20, azimuth=-108, strength=3.2, color='#FFE0B1', angle=2.6)
    kit.haze(density=0.0013, color='#FFD9A8', anisotropy=0.4, size=(260, 260, 60), location=(0, 0, 30))

    # -------------------------------------------------------------------- ground, plaza, lanes
    grass = kit.procedural('Meadow', 'ground', colors=['#3E5930', '#5F7937', '#8E9A4F'], scale=0.6, bump=0.2)
    kit.ground(grass, size=600)
    plaza = kit.cylinder('Plaza cobbles', PLAZA_R, 0.08, (0, 0, 0.04), cobble_material(kit), segments=96, bevel=0.03)
    curb_mat = kit.procedural('Curb stone', 'stone', colors=['#857B6C', '#A59A88', '#BDB29E'], scale=2.0)
    curb = kit.torus('Plaza curb', PLAZA_R + 0.15, 0.22, (0, 0, 0.06), curb_mat, segments=128, sides=10)
    curb.scale.z = 0.5

    dirt = kit.procedural('Packed earth lane', 'ground', colors=['#8A6E4C', '#A58A62', '#B89D74'], scale=1.5, bump=0.25)
    lane_ends = {}
    for deg in PATH_ANGLES:
        # A slightly wandering ribbon from the plaza edge out past the second ring.
        pts = []
        for k in range(15):
            r = PLAZA_R - 0.5 + k * 3.4
            wob = 1.3 * kit.noise(deg * 0.1, k * 0.35)
            pts.append(polar(r, deg) + polar(wob, deg + 90))
        verts, faces = [], []
        for i, p in enumerate(pts):
            nxt = pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]
            side = Vector((-nxt.y, nxt.x, 0)).normalized() * (LANE_HALF_WIDTH * (1 + 0.15 * kit.noise(i * .7, deg)))
            verts += [p - side + Vector((0, 0, 0.03)), p + side + Vector((0, 0, 0.03))]
            if i:
                faces.append((2 * i - 2, 2 * i - 1, 2 * i + 1, 2 * i))
        kit.mesh(f'Lane {deg}', verts, faces, dirt)
        lane_ends[deg] = pts

    # -------------------------------------------------------------------- the well
    well_stone = kit.procedural('Well stone', 'stone', colors=['#7B7266', '#9E9483', '#B7AD99'], scale=3.0, bump=0.5)
    timber = kit.procedural('Timber', 'wood', colors=['#4A3020', '#6B4630', '#8A6040'], scale=4.0)
    kit.lathe('Well ring', [(1.19, 0.0), (1.47, 0.0), (1.47, 0.90), (1.52, 0.98),
                           (1.47, 1.08), (1.19, 1.08), (1.19, 0.0)],
              segments=64, material=well_stone, smooth=False)
    pool = kit.material('Well water', '#1D5660', 0.085, coat=0.5)
    kit.cylinder('Well water', 1.20, 0.05, (0, 0, 0.46), pool, segments=64)
    for x in (-1.40, 1.40):
        kit.box('Well post', (0.18, 0.20, 2.75), (x, 0, 1.43), timber, bevel=0.024)
    kit.cylinder('Well windlass', 0.11, 2.94, (0, 0, 2.00), timber, rotation=(0, 90, 0), segments=20)
    kit.torus('Well crank wheel', 0.28, 0.031, (1.57, 0, 2), timber, rotation=(0, 90, 0), segments=24, sides=8)
    kit.box('Well crossbeam', (3.2, 0.18, 0.20), (0, 0, 2.78), timber, bevel=0.035)
    kit.tube('Well rope', [(0.1, 0, 1.93), (0.1, 0, 1.18)], radius=0.019, material=kit.material('Rope', '#B49A6A', .9))
    kit.cylinder('Bucket', 0.17, 0.26, (0.1, 0, 1.08), kit.procedural('Bucket wood', 'wood', scale=8), segments=20,
                 radius_top=0.20)

    # -------------------------------------------------------------------- market stalls
    goods_mats = [kit.material(n, c, 0.45, coat=0.2) for n, c in
                  (('Apples', '#B5241C'), ('Oranges', '#E58A1F'), ('Pears', '#9DB53A'), ('Plums', '#5A2A55'),
                   ('Lemons', '#E8CF3A'))]
    cloth = kit.material('Table cloth', '#EFE6D2', 0.85, sheen=0.4)
    crate_mat = kit.procedural('Crate wood', 'wood', colors=['#8A6440', '#A87D52', '#C49A6A'], scale=6)
    fruit_protos = []
    for m in goods_mats:
        f = kit.sphere(f'{m.name} proto', 0.075, (0, 0, -50), m, segments=12, rings=8)
        fruit_protos.append(f)
    stalls = []                                     # (front position, facing angle) for traders
    for i in range(STALL_COUNT):
        deg = 90 + i * 360 / STALL_COUNT + 12
        if min(angle_gap(deg, p) for p in PATH_ANGLES) < 18:
            deg += 20                                  # keep lanes into the plaza clear
        c = polar(STALL_RING, deg)
        rot = deg - 90                                 # tangent to the ring, local -Y faces the well
        stall = kit.empty(f'Stall {i}', c)
        stall.rotation_euler.z = math.radians(rot)
        parts = []
        parts.append(kit.box('Stall table', (2.6, 1.1, 0.08), (0, 0, 0.86), crate_mat, bevel=0.015))
        parts.append(kit.box('Stall cloth', (2.66, 1.16, 0.5), (0, 0, 0.66), cloth, bevel=0.01))
        for x in (-1.25, 1.25):
            for y in (-0.5, 0.5):
                h = 2.5 if y > 0 else 2.15                  # awning slopes toward the customers
                parts.append(kit.box('Stall post', (0.08, 0.08, h), (x, y, h / 2), timber))
        aw = awning_material(kit, f'Awning {i}', *AWNING[i % len(AWNING)])
        canopy = kit.plane('Awning canvas', (2.9, 1.55), (0, 0.0, 2.36), aw, rotation=(14, 0, 0), subdivisions=6)
        kit.solidify(canopy, 0.02)
        parts.append(canopy)
        # Scalloped valance along the customer edge.
        for k in range(10):
            parts.append(kit.cylinder('Valance scallop', 0.14, 0.02, (-1.3 + k * 0.29, -0.78, 2.08), aw,
                                      rotation=(90, 0, 0), segments=12))
        # Goods: heaped fruit in two crates and loose on the cloth.
        for cx in (-0.7, 0.55):
            parts.append(kit.box('Goods crate', (0.8, 0.5, 0.18), (cx, 0.05, 0.99), crate_mat, bevel=0.01))
            proto = fruit_protos[(i + int(cx > 0)) % len(fruit_protos)]
            for _ in range(14):
                parts.append(kit.instance(proto, (cx + rng.uniform(-0.33, 0.33), 0.05 + rng.uniform(-0.18, 0.18),
                                                  1.1 + rng.uniform(0, 0.08))))
        for _ in range(3):                                      # spare crates and a barrel behind
            parts.append(kit.box('Stacked crate', (0.55, 0.45, 0.4), (rng.uniform(-1.0, 1.0), 1.0 + rng.uniform(0, .3), 0.2),
                                 crate_mat, rotation=(0, 0, rng.uniform(-15, 15)), bevel=0.01))
        parts.append(kit.cylinder('Barrel', 0.3, 0.8, (1.55, 0.6, 0.4), crate_mat, segments=20, bevel=0.02))
        bpy.context.view_layer.update()
        for p in parts:
            p.parent = stall                            # built in stall-local space
        stalls.append((c + polar(1.4, deg + 180), deg))  # trader stands on the well side

    # -------------------------------------------------------------------- homes
    door_mat = kit.procedural('Door oak', 'wood', colors=['#3E2818', '#563822', '#6E4A2C'], scale=5)
    glass_mat = kit.material('Window glass', '#2A2E33', 0.12, coat=0.6)
    frame_mat = kit.material('Window frame', '#EDE4D2', 0.6)
    beam_mat = kit.material('Timber beam', '#4A3424', 0.7)
    roof_mats = [clay_roof(kit, f'Roof tiles {i}', color) for i, color in enumerate(ROOF)]
    hedge_mat = kit.procedural('Planter foliage', 'leaf', colors=['#435B2B', '#698347', '#7D9851'], scale=3.7)
    blossom = kit.material('Scarlet window flowers', '#B94539', roughness=0.68, subsurface=0.12)
    plaster_mats = [kit.material(f'Plaster {c}', c, 0.85, bump=(8.0, 0.08)) for c in PLASTER]
    doors = []                                      # door positions: agents' homes

    def house(name, center, polar_deg, w, d, h, roof_mat, wall_mat, timbered):
        """A gabled house built around its own empty at polar angle `polar_deg`; its door (local -Y)
        faces the plaza."""
        root = kit.empty(name, center)
        root.rotation_euler.z = math.radians(polar_deg - 90)
        parts = [kit.box('Walls', (w, d, h), (0, 0, h / 2), wall_mat, bevel=0.04)]
        rise = d * 0.42
        ov = 0.35
        x0, x1 = -w / 2 - ov, w / 2 + ov
        y0, y1 = -d / 2 - ov, d / 2 + ov
        verts = [(x0, y0, h - 0.1), (x1, y0, h - 0.1), (x1, 0, h + rise), (x0, 0, h + rise),
                 (x0, y1, h - 0.1), (x1, y1, h - 0.1)]
        roof = kit.mesh('Roof', verts, [(0, 1, 2, 3), (3, 2, 5, 4)], roof_mat)
        kit.solidify(roof, 0.14, offset=1.0)
        parts.append(roof)
        gable = kit.mesh('Gable', [(-w / 2, -d / 2, h), (-w / 2, d / 2, h), (-w / 2, 0, h + rise - 0.05),
                                   (w / 2, -d / 2, h), (w / 2, d / 2, h), (w / 2, 0, h + rise - 0.05)],
                         [(0, 2, 1), (3, 4, 5)], wall_mat)
        parts.append(gable)
        parts.append(kit.box('Chimney', (0.6, 0.6, 1.6), (w * 0.28, d * 0.18, h + rise * 0.6 + 0.6),
                             kit.procedural('Chimney brick', 'stone', colors=['#7A3A2A', '#924A36', '#A85C44'], scale=5),
                             bevel=0.02))
        # Front: door with step and lintel, windows with frames and sills, on both floors.
        parts.append(kit.box('Door', (1.0, 0.1, 2.0), (0, -d / 2 - 0.02, 1.0), door_mat, bevel=0.015))
        parts.append(kit.box('Door step', (1.4, 0.5, 0.16), (0, -d / 2 - 0.25, 0.08), curb_mat, bevel=0.02))
        floors = max(1, int(h // 2.6))
        for f in range(floors):
            zc = 1.5 + f * 2.6
            for xw in (-w * 0.3, w * 0.3):
                if f == 0 and abs(xw) < 1.0:
                    continue
                parts.append(kit.box('Window frame', (0.95, 0.08, 1.15), (xw, -d / 2 - 0.02, zc), frame_mat))
                parts.append(kit.box('Window glass', (0.75, 0.1, 0.95), (xw, -d / 2 - 0.035, zc), glass_mat))
                parts.append(kit.box('Window sill', (1.1, 0.2, 0.07), (xw, -d / 2 - 0.08, zc - 0.62), frame_mat))
                parts.append(kit.box('Window mullion', (0.055, 0.035, 0.96), (xw, -d / 2 - 0.093, zc), frame_mat))
                if f == 0 and w > 5.5:
                    parts.append(kit.box('Window planter box', (0.95, 0.28, 0.17), (xw, -d / 2 - 0.15, zc - 0.57),
                                         door_mat, bevel=0.032))
                    for dx in (-0.30, 0, 0.30):
                        plant = kit.ico('Window planter leaves', 0.14,
                                        (xw + dx, -d / 2 - 0.17, zc - 0.42), hedge_mat, subdivisions=1)
                        parts.append(plant)
                        flower = kit.ico('Window blossom', 0.052, (xw + dx, -d / 2 - 0.23, zc - 0.32),
                                         blossom, subdivisions=1)
                        parts.append(flower)
                if rng.random() < 0.5:
                    parts.append(kit.box('Shutter', (0.42, 0.05, 1.1), (xw - 0.72, -d / 2 - 0.04, zc),
                                         kit.material('Shutter', rng.choice(['#3F6E5A', '#6E3A32', '#3A5A7A']), 0.7)))
        if timbered:
            # Half-timbering on the upper floor: posts and a band beam.
            for xb in [-w / 2 + 0.06, -w / 6, w / 6, w / 2 - 0.06]:
                parts.append(kit.box('Timber post', (0.16, 0.06, h - 2.7), (xb, -d / 2 - 0.04, 2.7 + (h - 2.7) / 2), beam_mat))
            parts.append(kit.box('Timber band', (w, 0.07, 0.18), (0, -d / 2 - 0.045, 2.7), beam_mat))
        for p in parts:
            p.parent = root
        bpy.context.view_layer.update()
        door_world = root.matrix_world @ Vector((0, -d / 2 - 0.7, 0))
        return root, door_world

    def place_ring(radius, count, size_scale, jitter):
        homes = []
        for i in range(count):
            deg = i * 360 / count + rng.uniform(-jitter, jitter)
            if min(angle_gap(deg, p) for p in PATH_ANGLES) < 360 / count * 0.55:
                continue                                    # leave the lanes open
            w = rng.uniform(5.0, 7.0) * size_scale
            d = rng.uniform(4.8, 6.0) * size_scale
            h = rng.choice([3.4, 5.6, 6.2]) * size_scale
            c = polar(radius + d / 2 + rng.uniform(-0.6, 0.8), deg)
            root, door = house(f'House {radius:.0f}-{i}', c, deg, w, d, h, rng.choice(roof_mats),
                               rng.choice(plaster_mats), rng.random() < 0.45)
            homes.append((door, deg))
        return homes

    inner_homes = place_ring(HOUSE_RING, 16, 1.0, 3.0)
    outer_homes = place_ring(OUTER_RING, 24, 0.9, 4.0)
    doors = [(d, a, True) for d, a in inner_homes] + [(d, a, False) for d, a in outer_homes]

    # Trees and garden clutter beyond the plaza (secondary scale), kept off the lanes and houses.
    bark = kit.procedural('Bark', 'bark', scale=3.0)
    leaves = kit.procedural('Foliage', 'leaf', colors=['#3E5A22', '#56752C', '#6E8A34'], scale=2.0)
    for k in range(30):
        deg = rng.uniform(0, 360)
        if min(angle_gap(deg, p) for p in PATH_ANGLES) < 9:
            continue
        r = rng.choice([HOUSE_RING + 9.0, OUTER_RING + 10.5, OUTER_RING + 16]) + rng.uniform(-1.0, 1.5)
        kit.tree('Tree', rng.uniform(5.5, 9.0), polar(r, deg), style=rng.choice(['broadleaf', 'broadleaf', 'conifer']),
                 bark=bark, leaves=leaves, seed=k)
    hedge = kit.procedural('Hedge', 'leaf', colors=['#2F4A1C', '#44622A', '#5A7A30'], scale=3.0)
    for k in range(40):
        deg = rng.uniform(0, 360)
        if min(angle_gap(deg, p) for p in PATH_ANGLES) < 8:
            continue
        r = rng.uniform(HOUSE_RING + 6.5, OUTER_RING - 1.0)
        kit.rock('Shrub', rng.uniform(0.5, 0.9), polar(r, deg, 0.2), hedge, seed=k, squash=0.8)

    # Bunting strung between neighbouring stalls above the awnings: triangle flags on sagging lines.
    flag_mats = [kit.material(f'Flag {c}', c, 0.8) for c in ('#C8362F', '#E2A030', '#2F6FA8', '#F3E8D2', '#3F8A55')]
    for i in range(STALL_COUNT):
        a = polar(STALL_RING, stalls[i][1], 2.62)
        b = polar(STALL_RING, stalls[(i + 1) % STALL_COUNT][1], 2.62)
        pts = [a.lerp(b, u) - Vector((0, 0, 0.45 * math.sin(math.pi * u))) for u in [k / 16 for k in range(17)]]
        kit.tube('Bunting line', pts, radius=0.012, material=beam_mat)
        for k in range(1, 16):
            p = pts[k]
            side = (pts[k + 1] - pts[k - 1]).normalized() * 0.15
            kit.mesh('Bunting flag', [p - side, p + side, p - Vector((0, 0, 0.32))], [(0, 1, 2)],
                     flag_mats[k % len(flag_mats)])

    # -------------------------------------------------------------------- crowd meshes
    body_mats = [kit.material(f'Clothes {c}', c, 0.75, sheen=0.3) for c in CLOTHES]
    skin_mats = [kit.material(f'Skin {c}', c, 0.55, subsurface=0.1) for c in SKIN]
    # A figure as a toy maker would carve it: a tapered robe/torso with shoulders, legs implied.
    body_profile = [(0.0, 0.0), (0.19, 0.0), (0.21, 0.08), (0.19, 0.6), (0.17, 1.05), (0.22, 1.32),
                    (0.2, 1.42), (0.08, 1.48), (0.0, 1.48)]
    body_protos = []
    for m in body_mats:
        o = kit.lathe('Agent body proto', body_profile, segments=16, material=m, location=(0, 0, -60))
        body_protos.append(o)
    head_protos = [kit.sphere('Agent head proto', 0.12, (0, 0, -60), m, segments=16, rings=10) for m in skin_mats]
    hat_mat = kit.material('Straw hat', '#D8B86A', 0.8)
    hat_proto = kit.cylinder('Hat proto', 0.2, 0.03, (0, 0, -60), hat_mat, segments=16)
    basket_proto = kit.cylinder('Basket proto', 0.16, 0.18, (0, 0, -60), kit.procedural('Wicker', 'wood', scale=12),
                                segments=12, radius_top=0.2)
    for o in body_protos + head_protos + [hat_proto, basket_proto]:
        o.hide_render = True

    for o in fruit_protos:
        o.hide_render = True

    def make_agent(name):
        """Body instance plus parented head (and sometimes a hat or basket). Children are placed in
        body-local space; their scale undoes the body's flattening so heads stay round."""
        body = kit.instance(rng.choice(body_protos), name=name)
        s = rng.uniform(0.9, 1.08)
        body.scale = (s, 0.72 * s, s)
        undo = (1 / s, 1 / (0.72 * s), 1 / s)
        extras = [(rng.choice(head_protos), (0, 0, 1.58))]
        if rng.random() < 0.3:
            extras.append((hat_proto, (0, 0, 1.7)))
        if rng.random() < 0.25:
            extras.append((basket_proto, (0.26, 0, 0.8)))
        for proto, loc in extras:
            child = kit.instance(proto, loc, name=f'{name} {proto.name.split()[0].lower()}')
            child.hide_render = False
            child.parent = body
            child.scale = undo
        return body

    # -------------------------------------------------------------------- simulation: routes
    def lane_route(deg, inward=True):
        pts = [p.copy() for p in lane_ends[deg][:7]]
        return pts[::-1] if inward else pts

    targets = [pos + polar(0.9, deg + 180) for pos, deg in stalls] + [polar(3.3, a) for a in range(0, 360, 45)]

    def arc(r, a0, a1, step=10.0):
        """Points on a circle from angle a0 to a1 the short way round (walking around the stalls)."""
        span = (a1 - a0 + 180) % 360 - 180
        n = max(1, int(abs(span) // step))
        return [polar(r, a0 + span * k / n) for k in range(n + 1)]

    def route_from_home(door, home_deg, inner):
        """Door -> (outer homes: along the gap to the nearest lane) -> plaza edge -> round the
        outside of the stall ring -> in along a lane axis -> a stall or the well."""
        lane = min(PATH_ANGLES, key=lambda p: angle_gap(p, home_deg))
        route = [door]
        if not inner:
            pts = [p.copy() for p in lane_ends[lane][:7]][::-1]
            k = min(range(len(pts)), key=lambda i: (pts[i] - door).length)
            route += pts[k:]
            start_deg = lane
        else:
            start_deg = home_deg
        route += arc(11.2, start_deg, lane)
        route.append(polar(5.0, lane))
        route.append(rng.choice(targets))
        return route

    def route_across():
        """Shopping rounds inside the stall ring: one stall (or the well) to another."""
        a, b = rng.sample(targets, 2)
        mid = polar(rng.uniform(3.6, 5.5), rng.uniform(0, 360))
        return [a, mid, b]

    def polyline(points):
        segs, total = [], 0.0
        for p, q in zip(points, points[1:]):
            L = (q - p).length
            segs.append((p, q, total, L))
            total += L
        return segs, total

    def along(segs, total, s):
        """Point at arc length s along a polyline (clamped at both ends)."""
        s = min(max(s, 0.0), total)
        for p, q, s0, L in segs:
            if s <= s0 + L:
                return p.lerp(q, 0 if L == 0 else (s - s0) / L)
        return segs[-1][1].copy()

    for n in range(WALKERS):
        if n % 3 == 2:
            route = route_across()
        else:
            door, hdeg, inner = rng.choice(doors)
            route = route_from_home(door, hdeg, inner)
            if rng.random() < 0.4:
                route = route[::-1]                         # heading home with shopping
        # Shift each walker sideways a little so agents sharing a lane don't walk in single file.
        off = Vector((rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6), 0))
        route = [p + off for p in route]
        segs, total = polyline(route)
        speed = rng.uniform(*WALK_SPEED)
        s0 = rng.uniform(0, max(0.0, total - speed * kit.seconds))     # start mid-journey
        body = make_agent(f'Walker {n}')
        cadence = speed / 0.7                                 # steps per second for a 0.7 m stride
        phase = rng.random()

        def loc(t, segs=segs, total=total, s0=s0, speed=speed, cadence=cadence, phase=phase):
            p = along(segs, total, s0 + speed * t * kit.seconds)
            bob = 0.035 * abs(math.sin(math.pi * (cadence * t * kit.seconds + phase)))
            return Vector((p.x, p.y, 0.06 + bob))

        last = [None]

        def rot(t, segs=segs, total=total, s0=s0, speed=speed, cadence=cadence, phase=phase, last=last):
            # Face along the route, sampling a little behind and ahead so corners turn smoothly;
            # unwrap the angle against the previous key so no agent spins across +-180 degrees.
            s = s0 + speed * t * kit.seconds
            d = along(segs, total, s + 0.7) - along(segs, total, s - 0.7)
            heading = math.atan2(d.y, d.x) + math.pi / 2 if d.length > 1e-4 else (last[0] or 0.0)
            if last[0] is not None:
                heading = last[0] + ((heading - last[0] + math.pi) % math.tau - math.pi)
            last[0] = heading
            sway = math.radians(3.5) * math.sin(math.pi * (cadence * t * kit.seconds + phase))
            return (0.0, sway, heading)
        kit.animate(body, 'location', loc, step=2)
        kit.animate(body, 'rotation_euler', rot, step=2)

    # Traders: two per stall front, facing the goods, shifting weight and gesturing (turning).
    for n in range(TRADERS):
        pos, deg = stalls[n % len(stalls)]
        side = 1 if n < len(stalls) else -1
        p = pos + polar(0.7 * side, deg + 90) + polar(rng.uniform(-0.2, 0.3), deg)
        body = make_agent(f'Trader {n}')
        face = math.radians(deg - 90 + rng.uniform(-25, 25))
        ph = rng.random()
        kit.animate(body, 'location', lambda t, p=p: Vector((p.x, p.y, 0.06)), step=24)
        kit.animate(body, 'rotation_euler', lambda t, face=face, ph=ph: (
            0.0, math.radians(3) * math.sin(math.tau * (0.4 * t * kit.seconds + ph)),
            face + math.radians(14) * math.sin(math.tau * (0.17 * t * kit.seconds + ph))), step=3)

    # Gatherers at the well: a loose chatting ring, each turning between neighbours.
    for n in range(GATHERERS):
        a = n * 360 / GATHERERS + rng.uniform(-10, 10)
        p = polar(rng.uniform(1.9, 2.4), a)
        body = make_agent(f'Gatherer {n}')
        face = math.radians(a + 90) + math.pi
        ph = rng.random()
        kit.animate(body, 'location', lambda t, p=p: Vector((p.x, p.y, 0.06)), step=24)
        kit.animate(body, 'rotation_euler', lambda t, face=face, ph=ph: (
            0.0, 0.0, face + math.radians(30) * math.sin(math.tau * (0.2 * t * kit.seconds + ph))), step=3)

    # -------------------------------------------------------------------- camera: crane down
    cam = kit.camera(CAM_START, LOOK_START, lens=32)
    kit.dolly(cam, CAM_START, CAM_END, LOOK_START, LOOK_END, ease_kind='smooth')
    # Keep the plaza in the thin plane of focus all the way down: key the focus distance to the
    # camera-to-look-target distance along the move.
    keys = []
    for k in range(9):
        t = k / 8
        e = kit.ease(t, 'smooth')
        keys.append((t, (kit.lerp(CAM_START, CAM_END, e) - kit.lerp(LOOK_START, LOOK_END, e)).length))
    kit.rack_focus(cam, keys, fstop=FSTOP)
