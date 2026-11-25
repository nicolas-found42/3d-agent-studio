"""Clay walker on an old-town street at golden hour, followed by a side tracking shot.

Teaches
- A hand-built character rig: joint empties with clay body parts parented to them, posed per
  frame by a procedural gait instead of kit.walk, so the feet are planted (no skating).
- Two-bone analytic IK for the legs: the gait defines where each ankle must be (stance foot
  fixed on the pavement, swing foot on an arc), and the law of cosines turns that into hip and
  knee angles. Heel strike and toe-off pitch the feet; pelvis bob, sway and counter-twisting
  shoulders come from the same phase.
- A facade generator: walls assembled from blocks around window openings (real recesses without
  booleans), shopfronts with glazing, lit interiors, painted signs, striped awnings, shutters,
  string courses and cornices, all in a warm clay palette.
- Golden-hour light down the street: a low raking sun along the street axis, a physical sky for
  fill, warm practical lanterns just switched on, and thin haze for depth down the street.
- A tracking camera that dollies slightly slower than the walker, so the figure crosses the frame
  while staying framed, with shallow depth of field on the walker.
"""
import math

import bmesh
import bpy
from mathutils import Vector

# ---------------------------------------------------------------- constants (metres, seconds)
SIDEWALK_TOP = 0.15            # kerb height
SIDEWALK_DEPTH = 3.2           # facade line is at y = SIDEWALK_DEPTH
WALK_Y = 1.35                  # walker's line on the pavement
WALK_SPEED = 1.3               # m/s, an unhurried stroll
CYCLE = 1.05                   # seconds per gait cycle (two steps)
STRIDE = WALK_SPEED * CYCLE    # metres per cycle
DUTY = 0.6                     # fraction of the cycle each foot is on the ground
THIGH, SHIN = 0.44, 0.44       # bone lengths
ANKLE_H = 0.08                 # ankle height above the sole
HIP_Z = 0.84                   # mean hip-joint height
WALKER_X0 = -4.2               # where the walker starts
CAM_Y, CAM_Z = -7.0, 1.45      # camera dolly line in the road
CAM_LAG = 0.72                 # camera speed as a fraction of the walker's: the figure drifts across
SUN_ELEVATION = 7.0            # golden hour
SUN_AZIMUTH = -124.0           # from down the street (-X) and the camera side: rakes the facades
PALETTE = ['#D9A15B', '#C8684A', '#E6D2AC', '#E29778', '#E8C477', '#9FB08A', '#C98F6B', '#D7B98E']
SHOPS = ['BAKERY', 'BOOKS', 'CAFE', 'FLORIST', 'TAILOR', 'WINE', 'GROCER', 'HATS', 'CHEESE', 'TOYS']


# ---------------------------------------------------------------- materials
def clay(kit, name, color, rough=0.6, grain=0.12, sss=0.06):
    """Matte clay: soft subsurface, a little sheen, and a fine thumb-pressed bump at two scales."""
    mat = kit.material(name, color, roughness=rough, subsurface=sss, subsurface_radius=(0.6, 0.25, 0.12),
                       sheen=0.15)
    nt, bs = mat.node_tree, kit.bsdf(mat)
    coord = nt.nodes.new('ShaderNodeTexCoord')
    big = nt.nodes.new('ShaderNodeTexNoise'); big.inputs['Scale'].default_value = 9; big.inputs['Detail'].default_value = 3
    fine = nt.nodes.new('ShaderNodeTexNoise'); fine.inputs['Scale'].default_value = 70; fine.inputs['Detail'].default_value = 2
    for n in (big, fine):
        nt.links.new(coord.outputs['Object'], n.inputs['Vector'])
    add = nt.nodes.new('ShaderNodeMath'); add.operation = 'MULTIPLY_ADD'
    add.inputs[1].default_value = 0.35
    nt.links.new(fine.outputs['Fac'], add.inputs[0]); nt.links.new(big.outputs['Fac'], add.inputs[2])
    bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = grain
    bump.inputs['Distance'].default_value = 0.02
    nt.links.new(add.outputs[0], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bs.inputs['Normal'])
    # Low-frequency tone variation so large surfaces never read as one flat colour.
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
    mix.inputs['Factor'].default_value = 0.18
    mix.inputs['A'].default_value = kit.color(color)
    nt.links.new(big.outputs['Color'], mix.inputs['B'])
    nt.links.new(mix.outputs['Result'], bs.inputs['Base Color'])
    return mat


def stucco(kit, name, color):
    """Facade plaster: clay base plus darker weathering toward the ground (object-space Z)."""
    mat = clay(kit, name, color, rough=0.85, grain=0.25, sss=0.0)
    nt, bs = mat.node_tree, kit.bsdf(mat)
    base_link = bs.inputs['Base Color'].links[0].from_socket
    coord = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(coord.outputs['Object'], sep.inputs[0])
    grime = nt.nodes.new('ShaderNodeMapRange'); grime.interpolation_type = 'SMOOTHSTEP'
    grime.inputs['From Min'].default_value, grime.inputs['From Max'].default_value = 0.0, 1.4
    grime.inputs['To Min'].default_value, grime.inputs['To Max'].default_value = 0.35, 0.0
    nt.links.new(sep.outputs['Z'], grime.inputs['Value'])
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'
    nt.links.new(grime.outputs['Result'], mix.inputs['Factor'])
    nt.links.new(base_link, mix.inputs['A'])
    mix.inputs['B'].default_value = kit.color('#5A4434')
    nt.links.new(mix.outputs['Result'], bs.inputs['Base Color'])
    return mat


def striped(kit, name, a, b, stripes_per_m=4.0):
    """Awning canvas: hard stripes from a wave texture along object X."""
    mat = clay(kit, name, a, rough=0.8, grain=0.08, sss=0.0)
    nt, bs = mat.node_tree, kit.bsdf(mat)
    coord = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(coord.outputs['Object'], sep.inputs[0])
    m = nt.nodes.new('ShaderNodeMath'); m.operation = 'MULTIPLY'; m.inputs[1].default_value = stripes_per_m
    nt.links.new(sep.outputs['X'], m.inputs[0])
    fr = nt.nodes.new('ShaderNodeMath'); fr.operation = 'FRACT'; nt.links.new(m.outputs[0], fr.inputs[0])
    st = nt.nodes.new('ShaderNodeMath'); st.operation = 'GREATER_THAN'; st.inputs[1].default_value = 0.5
    nt.links.new(fr.outputs[0], st.inputs[0])
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'
    nt.links.new(st.outputs[0], mix.inputs['Factor'])
    mix.inputs['A'].default_value, mix.inputs['B'].default_value = kit.color(a), kit.color(b)
    nt.links.new(mix.outputs['Result'], bs.inputs['Base Color'])
    return mat


def cobbles(kit):
    """Road setts: Voronoi distance-to-edge gives the joints, cell colour gives per-stone tone."""
    mat = kit.material('Cobbles', '#6E625A', roughness=0.8)
    nt, bs = mat.node_tree, kit.bsdf(mat)
    coord = nt.nodes.new('ShaderNodeTexCoord')
    mapping = nt.nodes.new('ShaderNodeMapping'); mapping.inputs['Scale'].default_value = (1.0, 1.6, 1.0)
    nt.links.new(coord.outputs['Object'], mapping.inputs['Vector'])
    cells = nt.nodes.new('ShaderNodeTexVoronoi'); cells.inputs['Scale'].default_value = 5.5
    nt.links.new(mapping.outputs['Vector'], cells.inputs['Vector'])
    edges = nt.nodes.new('ShaderNodeTexVoronoi'); edges.feature = 'DISTANCE_TO_EDGE'
    edges.inputs['Scale'].default_value = 5.5
    nt.links.new(mapping.outputs['Vector'], edges.inputs['Vector'])
    joint = nt.nodes.new('ShaderNodeMapRange'); joint.interpolation_type = 'SMOOTHSTEP'
    joint.inputs['From Min'].default_value, joint.inputs['From Max'].default_value = 0.0, 0.12
    nt.links.new(edges.outputs['Distance'], joint.inputs['Value'])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    for el, (p, c) in zip(ramp.color_ramp.elements, ((0, '#574C46'), (1, '#9A8775'))):
        el.position, el.color = p, kit.color(c)
    nt.links.new(cells.outputs['Color'], ramp.inputs['Fac'])
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'
    nt.links.new(joint.outputs['Result'], mix.inputs['Factor'])
    mix.inputs['A'].default_value = kit.color('#2E2824')
    nt.links.new(ramp.outputs['Color'], mix.inputs['B'])
    nt.links.new(mix.outputs['Result'], bs.inputs['Base Color'])
    bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.6
    nt.links.new(joint.outputs['Result'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bs.inputs['Normal'])
    return mat


def paving(kit):
    """Pavement flags: a brick texture with long, wide 'bricks' and thin mortar."""
    mat = kit.material('Pavement', '#B8A58C', roughness=0.85)
    nt, bs = mat.node_tree, kit.bsdf(mat)
    coord = nt.nodes.new('ShaderNodeTexCoord')
    brick = nt.nodes.new('ShaderNodeTexBrick')
    brick.inputs['Scale'].default_value = 1.0
    brick.inputs['Brick Width'].default_value = 0.9
    brick.inputs['Row Height'].default_value = 0.6
    brick.inputs['Mortar Size'].default_value = 0.012
    brick.inputs['Color1'].default_value = kit.color('#BCA88E')
    brick.inputs['Color2'].default_value = kit.color('#A8957D')
    brick.inputs['Mortar'].default_value = kit.color('#5B5048')
    nt.links.new(coord.outputs['Object'], brick.inputs['Vector'])
    nt.links.new(brick.outputs['Color'], bs.inputs['Base Color'])
    bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.4
    inv = nt.nodes.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0
    nt.links.new(brick.outputs['Fac'], inv.inputs[1])
    nt.links.new(inv.outputs[0], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bs.inputs['Normal'])
    return mat


# ---------------------------------------------------------------- street architecture
def wall_with_openings(kit, name, x0, x1, z0, z1, openings, mat, y=SIDEWALK_DEPTH, depth=0.45):
    """Assemble a wall from blocks around rectangular openings (x0, x1, z0, z1) so windows and
    doors are genuinely recessed. Columns split at every opening edge; each column keeps the
    z-ranges no opening covers."""
    xs = sorted({x0, x1, *[o[0] for o in openings], *[o[1] for o in openings]})
    parts = []
    for a, b in zip(xs, xs[1:]):
        cut = sorted((o[2], o[3]) for o in openings if o[0] <= a and o[1] >= b)
        zc = z0
        for lo, hi in cut + [(z1, z1)]:
            if lo > zc + 1e-4:
                parts.append((a, b, zc, lo))
            zc = max(zc, hi)
    bm = bmesh.new()
    for a, b, lo, hi in parts:
        res = bmesh.ops.create_cube(bm, size=1.0)
        for v in res['verts']:
            v.co = Vector(((a + b) / 2 + v.co.x * (b - a), y + depth / 2 + v.co.y * depth, (lo + hi) / 2 + v.co.z * (hi - lo)))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    obj = bpy.data.objects.new(name, me)
    me.materials.append(mat)
    return kit._link(obj, 'Street')


def window(kit, mats, x, z, w, h, shutters, flowers, rng):
    """Upper-floor window: recessed glass, frame, sill, lintel, optional shutters and flower box."""
    y = SIDEWALK_DEPTH
    kit.box('Window glass', (w, 0.02, h), (x, y + 0.2, z + h / 2), mats['glass'], collection='Street')
    kit.box('Window dark room', (w, 0.02, h), (x, y + 0.6, z + h / 2), mats['room'], collection='Street')
    for dx in (-w / 2, 0, w / 2):           # mullion and jambs
        kit.box('Window frame', (0.05, 0.08, h), (x + dx, y + 0.17, z + h / 2), mats['frame'], bevel=0.01, collection='Street')
    kit.box('Window transom', (w, 0.08, 0.05), (x, y + 0.17, z + h * 0.68), mats['frame'], bevel=0.01, collection='Street')
    kit.box('Window sill', (w + 0.24, 0.2, 0.07), (x, y - 0.06, z - 0.035), mats['trim'], bevel=0.015, collection='Street')
    kit.box('Window lintel', (w + 0.3, 0.1, 0.18), (x, y - 0.03, z + h + 0.09), mats['trim'], bevel=0.015, collection='Street')
    if shutters:
        for side in (-1, 1):
            sx = x + side * (w / 2 + w / 4 + 0.03)
            sh = kit.box('Shutter', (w / 2, 0.04, h), (sx, y - 0.03, z + h / 2), mats['shutter'], bevel=0.008, collection='Street')
            for k in range(9):                # louvres: secondary detail that catches the raking sun
                kit.box('Shutter slat', (w / 2 - 0.06, 0.03, 0.025), (sx, y - 0.06, z + 0.12 + k * (h - 0.24) / 8),
                        mats['shutter'], rotation=(25, 0, 0), collection='Street')
    if flowers:
        kit.box('Flower box', (w + 0.1, 0.22, 0.2), (x, y - 0.2, z + 0.06), mats['planter'], bevel=0.02, collection='Street')
        for k in range(9):
            bx = x - w / 2 + 0.05 + k * w / 8
            kit.sphere('Geranium', rng.uniform(0.06, 0.09), (bx, y - 0.22 + rng.uniform(-0.04, 0.04), z + 0.2 + rng.uniform(0, .05)),
                       mats['flower'] if k % 2 else mats['leaf'], segments=12, rings=8, collection='Street')


def building(kit, mats, x0, width, palette_mat, shop, rng):
    """One narrow townhouse: shopfront at street level, two or three upper floors, cornice."""
    x1 = x0 + width
    floors = rng.choice((2, 3, 3))
    ground_h, floor_h = 4.0, 3.1
    top = ground_h + floors * floor_h
    # Ground floor openings: a wide display window and a door.
    door_w = 1.1
    shop_l, shop_r = x0 + 0.55, x1 - 0.55 - door_w - 0.4
    door_l = x1 - 0.55 - door_w
    openings = [(shop_l, shop_r, 0.55, 3.05), (door_l, door_l + door_w, 0.0, 2.55)]
    n_win = max(2, int(width // 1.9))
    pitch = (width - 0.8) / n_win
    for f in range(floors):
        z = ground_h + f * floor_h + 0.75
        for k in range(n_win):
            cx = x0 + 0.4 + pitch * (k + 0.5)
            openings.append((cx - 0.45, cx + 0.45, z, z + 1.75))
    wall_with_openings(kit, f'Facade {shop}', x0, x1, 0.0, top, openings, palette_mat)
    # Rusticated plinth and string courses (horizontal bands) at each floor line.
    kit.box('Plinth', (width, 0.08, 0.5), (x0 + width / 2, SIDEWALK_DEPTH - 0.04, 0.25), mats['trim'], bevel=0.02, collection='Street')
    for f in range(floors):
        kit.box('String course', (width, 0.14, 0.16), (x0 + width / 2, SIDEWALK_DEPTH - 0.07, ground_h + f * floor_h),
                mats['trim'], bevel=0.03, collection='Street')
    # Stepped cornice: three bands, each projecting further.
    for k, (dy, hz) in enumerate(((0.12, 0.18), (0.24, 0.12), (0.38, 0.2))):
        kit.box('Cornice', (width + 0.04, dy * 2, hz), (x0 + width / 2, SIDEWALK_DEPTH - dy + 0.05, top + 0.1 + k * 0.17),
                mats['trim'], bevel=0.02, collection='Street')
    kit.box('Roof', (width, 4.0, 0.3), (x0 + width / 2, SIDEWALK_DEPTH + 2.0, top + 0.6), mats['roof'], collection='Street')
    # Upper windows.
    for f in range(floors):
        z = ground_h + f * floor_h + 0.75
        for k in range(n_win):
            cx = x0 + 0.4 + pitch * (k + 0.5)
            window(kit, mats, cx, z, 0.9, 1.75, shutters=rng.random() < 0.6, flowers=(f == 0 and rng.random() < 0.5), rng=rng)
    # Shopfront: painted frame, glazing, a warm lit interior with shelves, sign and awning.
    sw = shop_r - shop_l
    scx = (shop_l + shop_r) / 2
    kit.box('Shop glass', (sw, 0.02, 2.5), (scx, SIDEWALK_DEPTH + 0.3, 1.8), mats['glass'], collection='Street')
    kit.box('Shop interior', (sw, 0.05, 3.0), (scx, SIDEWALK_DEPTH + 2.2, 1.6), mats['interior'], collection='Street')
    for k in range(3):
        kit.box('Shop shelf', (sw - 0.2, 0.4, 0.05), (scx, SIDEWALK_DEPTH + 1.9, 0.9 + k * 0.6), mats['shelf'], collection='Street')
        for j in range(int(sw / 0.25)):
            if rng.random() < 0.7:
                h = rng.uniform(0.12, 0.3)
                kit.box('Shop goods', (0.16, 0.16, h), (shop_l + 0.2 + j * 0.25, SIDEWALK_DEPTH + 1.85, 0.93 + k * 0.6 + h / 2),
                        rng.choice(mats['goods']), bevel=0.02, collection='Street')
    kit.box('Shop sill', (sw + 0.2, 0.3, 0.12), (scx, SIDEWALK_DEPTH - 0.02, 0.5), mats['shopframe'], bevel=0.02, collection='Street')
    for px in (shop_l - 0.12, shop_r + 0.12, door_l - 0.12, door_l + door_w + 0.12):
        kit.box('Shop pilaster', (0.24, 0.16, 3.3), (px, SIDEWALK_DEPTH - 0.05, 1.65), mats['shopframe'], bevel=0.02, collection='Street')
    kit.box('Shop fascia', (x1 - x0 - 0.5, 0.18, 0.62), (x0 + width / 2, SIDEWALK_DEPTH - 0.08, 3.45), mats['shopframe'], bevel=0.03, collection='Street')
    kit.text(shop, size=0.36, location=(x0 + width / 2, SIDEWALK_DEPTH - 0.18, 3.45), rotation=(90, 0, 0),
             material=mats['gilt'], extrude=0.012, bevel=0.003, font=mats.get('font'), name=f'Sign {shop}', collection='Street')
    kit.box('Door', (door_w, 0.06, 2.55), (door_l + door_w / 2, SIDEWALK_DEPTH + 0.25, 1.275), mats['shopframe'], bevel=0.02, collection='Street')
    kit.box('Door glass', (door_w - 0.36, 0.02, 1.2), (door_l + door_w / 2, SIDEWALK_DEPTH + 0.21, 1.65), mats['glass'], collection='Street')
    kit.sphere('Door knob', 0.035, (door_l + door_w - 0.15, SIDEWALK_DEPTH + 0.19, 1.15), mats['brass'], segments=12, rings=8, collection='Street')
    if rng.random() < 0.75:
        awning(kit, x0 + 0.3, x1 - 0.3, rng.choice(mats['awnings']), mats)
    # Interior practical: a warm glow that spills onto the pavement.
    kit.point(f'Shop light {shop}', (scx, SIDEWALK_DEPTH + 1.2, 2.6), power=120, color='#FFC27A', radius=0.4)
    # Drainpipe at the party wall.
    kit.cylinder('Drainpipe', 0.05, top, (x1 - 0.08, SIDEWALK_DEPTH - 0.08, top / 2), mats['iron'], segments=12, collection='Street')
    return top


def awning(kit, x0, x1, mat, mats):
    """A sloped striped awning with a scalloped valance and two iron arms."""
    w, reach, drop = x1 - x0, 1.3, 0.55
    top_z = 3.85
    verts = [(x0, SIDEWALK_DEPTH - 0.05, top_z), (x1, SIDEWALK_DEPTH - 0.05, top_z),
             (x1, SIDEWALK_DEPTH - reach, top_z - drop), (x0, SIDEWALK_DEPTH - reach, top_z - drop)]
    canvas = kit.mesh('Awning canvas', verts, [(0, 1, 2, 3)], mat, collection='Street')
    kit.solidify(canvas, 0.02)
    kit.subdivide(canvas, 2)
    n = int(w / 0.3)
    for k in range(n):                       # scalloped valance from half-discs
        cx = x0 + (k + 0.5) * w / n
        kit.cylinder('Awning scallop', w / n / 2, 0.02, (cx, SIDEWALK_DEPTH - reach, top_z - drop - 0.08),
                     mat, rotation=(90, 0, 0), segments=16, collection='Street')
    kit.box('Awning valance', (w, 0.02, 0.16), (x0 + w / 2, SIDEWALK_DEPTH - reach, top_z - drop - 0.01), mat, collection='Street')
    for ax in (x0 + 0.1, x1 - 0.1):
        kit.tube('Awning arm', [(ax, SIDEWALK_DEPTH, top_z - 0.9), (ax, SIDEWALK_DEPTH - reach * 0.6, top_z - drop * 0.7 - 0.2),
                                (ax, SIDEWALK_DEPTH - reach, top_z - drop - 0.02)], 0.015, mats['iron'], collection='Street')


def lamp_post(kit, x, mats):
    """Cast-iron lamp post: lathed base, fluted shaft, lantern with a warm emissive mantle."""
    y = 0.45
    kit.lathe('Lamp base', [(0, 0), (0.17, 0), (0.17, 0.1), (0.12, 0.16), (0.12, 0.42), (0.08, 0.5), (0.07, 0.6), (0, 0.6)],
              24, mats['iron'], location=(x, y, SIDEWALK_TOP), collection='Street')
    kit.cylinder('Lamp shaft', 0.06, 2.4, (x, y, SIDEWALK_TOP + 1.75), mats['iron'], segments=16, radius_top=0.045, collection='Street')
    kit.lathe('Lamp collar', [(0, 0), (0.09, 0), (0.12, 0.06), (0.06, 0.14), (0, 0.14)], 24, mats['iron'],
              location=(x, y, SIDEWALK_TOP + 2.9), collection='Street')
    kit.lathe('Lantern glass', [(0.08, 0), (0.17, 0.42), (0.14, 0.5)], 6, mats['lantern'], smooth=False,
              location=(x, y, SIDEWALK_TOP + 3.02), collection='Street')
    kit.lathe('Lantern cap', [(0.0, 0.32), (0.08, 0.3), (0.2, 0.08), (0.18, 0.0), (0.0, 0.0)], 6, mats['iron'], smooth=False,
              location=(x, y, SIDEWALK_TOP + 3.52), collection='Street')
    kit.point(f'Lantern {x:.0f}', (x, y, SIDEWALK_TOP + 3.3), power=25, color='#FFB060', radius=0.08)


# ---------------------------------------------------------------- the clay walker
def capsule(kit, name, r0, r1, length, mat, parent, offset=(0, 0, 0), scale=(1, 1, 1)):
    """A tapered capsule hanging down -Z from its joint (r0 at the joint, r1 at the far end)."""
    prof = [(0, r0)]
    for k in range(1, 7):
        a = math.pi / 2 * k / 6
        prof.append((r0 * math.sin(a), r0 * math.cos(a)))
    for k in range(0, 7):
        a = math.pi / 2 * k / 6
        prof.append((r1 * math.cos(a), -length - r1 * math.sin(a)))
    obj = kit.lathe(name, prof, 24, mat, collection='Walker')
    obj.parent = parent
    obj.location, obj.scale = offset, scale
    return obj


def blob(kit, name, r, mat, parent, offset=(0, 0, 0), scale=(1, 1, 1), rotation=(0, 0, 0)):
    obj = kit.sphere(name, r, (0, 0, 0), mat, segments=32, rings=16, scale=(1, 1, 1), collection='Walker')
    obj.parent = parent
    obj.location, obj.scale = offset, scale
    obj.rotation_euler = [math.radians(a) for a in rotation]
    return obj


def build_walker(kit):
    """Joints are empties; clay parts hang from them. The figure faces +X; its left is +Y."""
    skin = clay(kit, 'Clay skin', '#E2A887', rough=0.55, sss=0.12)
    sweater = clay(kit, 'Clay sweater', '#3E7A78', rough=0.75, grain=0.2)
    trousers = clay(kit, 'Clay trousers', '#E7D7B5', rough=0.7)
    shoes = clay(kit, 'Clay shoes', '#5A3424', rough=0.45)
    hair = clay(kit, 'Clay hair', '#3A2418', rough=0.6, grain=0.35)
    beret = clay(kit, 'Clay beret', '#B5412F', rough=0.75)
    scarf = clay(kit, 'Clay scarf', '#E8B547', rough=0.8, grain=0.25)
    eye = kit.material('Clay eye', '#16100C', roughness=0.25)

    def joint(name, parent, offset):
        e = kit.empty(f'Walker {name}', (0, 0, 0), size=0.06, collection='Walker')
        e.parent = parent
        e.location = offset
        return e

    J = {'root': kit.empty('Walker', (WALKER_X0, WALK_Y, SIDEWALK_TOP), display='ARROWS', size=0.3, collection='Walker')}
    J['pelvis'] = joint('pelvis', J['root'], (0, 0, HIP_Z + 0.03))
    blob(kit, 'Walker pelvis', 0.17, trousers, J['pelvis'], (0, 0, 0.02), (0.85, 1.15, 0.8))
    J['chest'] = joint('chest', J['pelvis'], (0, 0, 0.08))
    torso = kit.lathe('Walker torso', [(0, 0), (0.15, 0.0), (0.17, 0.12), (0.18, 0.28), (0.17, 0.4), (0.12, 0.5), (0.06, 0.55), (0, 0.56)],
                      32, sweater, collection='Walker')
    torso.parent, torso.scale = J['chest'], (0.78, 1.18, 1.0)
    kit.subdivide(torso, 1)
    J['neck'] = joint('neck', J['chest'], (0.0, 0, 0.53))
    capsule(kit, 'Walker neck', 0.05, 0.05, 0.06, skin, J['neck'], (0, 0, 0.07))
    kit.torus('Walker scarf', 0.075, 0.045, (0, 0, 0), scarf, segments=32, sides=12, collection='Walker').parent = J['neck']
    tail = kit.tube('Walker scarf tail', [(0.06, 0.05, -0.02), (0.13, 0.06, -0.12), (0.15, 0.07, -0.28)], 0.03, scarf, collection='Walker')
    tail.parent = J['neck']
    J['head'] = joint('head', J['neck'], (0, 0, 0.09))
    blob(kit, 'Walker head', 0.14, skin, J['head'], (0, 0, 0.12), (0.95, 0.9, 1.08))
    blob(kit, 'Walker nose', 0.035, skin, J['head'], (0.135, 0, 0.1), (1.2, 0.9, 1.0))
    for side in (1, -1):
        blob(kit, 'Walker eye', 0.016, eye, J['head'], (0.122, side * 0.05, 0.15))
        blob(kit, 'Walker ear', 0.035, skin, J['head'], (-0.01, side * 0.125, 0.12), (0.6, 0.4, 1.0))
    blob(kit, 'Walker hair', 0.145, hair, J['head'], (-0.03, 0, 0.15), (0.92, 0.95, 0.88))
    blob(kit, 'Walker beret', 0.15, beret, J['head'], (-0.01, 0, 0.255), (1.1, 1.05, 0.33), rotation=(0, -12, 0))
    blob(kit, 'Walker beret stalk', 0.02, beret, J['head'], (-0.02, 0, 0.305))
    for side, name in ((1, 'l'), (-1, 'r')):
        J[f'shoulder_{name}'] = joint(f'shoulder {name}', J['chest'], (0, side * 0.2, 0.43))
        capsule(kit, f'Walker upper arm {name}', 0.055, 0.045, 0.27, sweater, J[f'shoulder_{name}'])
        J[f'elbow_{name}'] = joint(f'elbow {name}', J[f'shoulder_{name}'], (0, 0, -0.28))
        capsule(kit, f'Walker forearm {name}', 0.045, 0.038, 0.24, sweater, J[f'elbow_{name}'])
        blob(kit, f'Walker hand {name}', 0.052, skin, J[f'elbow_{name}'], (0.01, 0, -0.3), (0.9, 0.7, 1.1))
        J[f'hip_{name}'] = joint(f'hip {name}', J['pelvis'], (0, side * 0.095, -0.03))
        capsule(kit, f'Walker thigh {name}', 0.075, 0.058, THIGH, trousers, J[f'hip_{name}'])
        J[f'knee_{name}'] = joint(f'knee {name}', J[f'hip_{name}'], (0, 0, -THIGH))
        capsule(kit, f'Walker shin {name}', 0.058, 0.046, SHIN, trousers, J[f'knee_{name}'])
        J[f'ankle_{name}'] = joint(f'ankle {name}', J[f'knee_{name}'], (0, 0, -SHIN))
        shoe = kit.box(f'Walker shoe {name}', (0.27, 0.11, 0.09), (0, 0, 0), shoes, bevel=0.04, collection='Walker')
        shoe.parent, shoe.location = J[f'ankle_{name}'], (0.06, 0, -ANKLE_H + 0.045)
    return J


def smooth01(u):
    u = min(1.0, max(0.0, u))
    return u * u * u * (u * (u * 6 - 15) + 10)


def leg_target(p):
    """Ankle position relative to the hip joint (dx forward, dz up from the sole) and foot pitch
    for gait phase p. Stance moves the foot back exactly as fast as the body moves forward."""
    a = STRIDE * DUTY / 2                  # reach in front of / behind the hip
    if p < DUTY:
        u = p / DUTY
        dx = a - 2 * a * u
        lift = 0.0
        # heel strike (toe up), flat, then toe-off (heel rises, pivoting on the ball)
        pitch = -12 * (1 - smooth01(u / 0.14)) + 32 * smooth01((u - 0.72) / 0.28)
        lift += 0.13 * math.sin(math.radians(max(0.0, pitch)))
    else:
        u = (p - DUTY) / (1 - DUTY)
        dx = -a + STRIDE * smooth01(u) - STRIDE * (1 - DUTY) * u
        pitch = 32 + (-12 - 32) * smooth01(u)
        lift = 0.13 * math.sin(math.radians(32)) * (1 - smooth01(u * 2)) + 0.1 * math.sin(math.pi * u) ** 1.5
    return dx, lift, pitch


def two_bone(dx, dz):
    """Hip flexion (forward, rad) and knee flexion (rad) that put the ankle at (dx, dz)."""
    r = min(math.hypot(dx, dz), THIGH + SHIN - 1e-4)
    phi = math.atan2(dx, -dz)
    alpha = math.acos(max(-1, min(1, (THIGH ** 2 + r * r - SHIN ** 2) / (2 * THIGH * r))))
    beta = math.acos(max(-1, min(1, (THIGH ** 2 + SHIN ** 2 - r * r) / (2 * THIGH * SHIN))))
    return phi + alpha, math.pi - beta


def animate_walker(kit, J):
    rad = math.radians
    for f in range(1, kit.frames + 1):
        ts = (f - 1) / kit.fps
        pl = (ts / CYCLE) % 1.0
        pr = (pl + 0.5) % 1.0
        # Pelvis: lowest in double support, highest mid-stance; sways over the stance foot.
        hip_z = HIP_Z + 0.022 * -math.cos(4 * math.pi * (pl - 0.05))
        J['root'].location = (WALKER_X0 + WALK_SPEED * ts, WALK_Y, SIDEWALK_TOP)
        J['pelvis'].location = (0, 0.02 * math.sin(2 * math.pi * (pl - 0.05)), hip_z + 0.03)
        J['pelvis'].rotation_euler = (rad(3 * math.sin(2 * math.pi * (pl - 0.05))), 0, rad(-6 * math.cos(2 * math.pi * pl)))
        J['chest'].rotation_euler = (rad(-2 * math.sin(2 * math.pi * (pl - 0.05))), rad(5), rad(13 * math.cos(2 * math.pi * pl)))
        J['neck'].rotation_euler = (0, rad(-6), rad(-6 * math.cos(2 * math.pi * pl)))
        J['head'].rotation_euler = (0, rad(2 * math.sin(4 * math.pi * pl)), rad(4))   # a glance toward the shop windows
        for side, p, other in (('l', pl, pr), ('r', pr, pl)):
            dx, lift, pitch = leg_target(p)
            dz = -(hip_z - 0.0) + ANKLE_H + lift
            flex, knee = two_bone(dx, dz)
            J[f'hip_{side}'].rotation_euler = (0, -flex, 0)
            J[f'knee_{side}'].rotation_euler = (0, knee, 0)
            # keep the shoe level (cancel parent rotations), then add the gait pitch
            J[f'ankle_{side}'].rotation_euler = (0, flex - knee + rad(pitch), 0)
            swing = math.cos(2 * math.pi * other)          # arm follows the opposite leg
            out = 1 if side == 'l' else -1
            J[f'shoulder_{side}'].rotation_euler = (rad(out * 7), rad(-24 * swing), 0)
            J[f'elbow_{side}'].rotation_euler = (0, rad(-(14 + 16 * max(0.0, swing))), 0)
        for key, e in J.items():
            e.keyframe_insert('location', frame=f)
            e.keyframe_insert('rotation_euler', frame=f)


# ---------------------------------------------------------------- build
def build(kit):
    rng = kit.rng
    mats = {
        'glass': kit.material('Window glass', '#1B2228', roughness=0.04, specular=0.9, coat=0.5),
        'room': kit.material('Dark room', '#2A1F18', roughness=0.9),
        'frame': clay(kit, 'Window frame', '#F1E7D2', rough=0.5),
        'trim': stucco(kit, 'Stone trim', '#EADCC0'),
        'shutter': clay(kit, 'Shutters', '#4F7A6A', rough=0.55),
        'planter': clay(kit, 'Planter', '#8E4A2E', rough=0.7),
        'flower': clay(kit, 'Geranium', '#D2352B', rough=0.6),
        'leaf': clay(kit, 'Geranium leaf', '#3F6B35', rough=0.7),
        'roof': clay(kit, 'Roof tiles', '#8F4A35', rough=0.8),
        'interior': kit.emissive('Shop interior glow', '#FFC890', 1.2),
        'shelf': clay(kit, 'Shelf', '#7A5134', rough=0.6),
        'goods': [clay(kit, f'Goods {i}', c, rough=0.5) for i, c in enumerate(('#E7C26B', '#B9553D', '#F2E6CF', '#6A8E7E', '#D98E4A'))],
        'shopframe': clay(kit, 'Shopfront paint', '#2F4A5A', rough=0.4),
        'gilt': kit.material('Gilt lettering', '#D9A53F', roughness=0.3, metallic=0.9),
        'brass': kit.material('Brass', '#C59A4A', roughness=0.25, metallic=1.0),
        'iron': kit.material('Cast iron', '#1E211F', roughness=0.45, metallic=0.6),
        'lantern': kit.emissive('Lantern glass', '#FFC170', 6.0),
        'awnings': [striped(kit, 'Awning red', '#B7412F', '#F0E2C6'), striped(kit, 'Awning green', '#3E6E5A', '#F0E2C6'),
                    striped(kit, 'Awning ochre', '#D69A3C', '#F4E9D2')],
    }
    try:
        kit.font('fontsource:playfair-display@700')
        mats['font'] = 'fontsource:playfair-display@700'
    except Exception as exc:                # the default font still reads as painted lettering
        kit.note(f'sign font unavailable: {exc}')
    walls = [stucco(kit, f'Stucco {i}', c) for i, c in enumerate(PALETTE)]

    # --- street surfaces -------------------------------------------------------------------
    road = kit.plane('Cobbled road', (140, 30), (10, -15, 0), cobbles(kit), ground=True, collection='Street')
    kit.box('Pavement', (140, SIDEWALK_DEPTH - 0.3, SIDEWALK_TOP), (10, 0.3 + (SIDEWALK_DEPTH - 0.3) / 2, SIDEWALK_TOP / 2),
            paving(kit), collection='Street')
    kit.box('Kerb', (140, 0.3, SIDEWALK_TOP), (10, 0.15, SIDEWALK_TOP / 2), stucco(kit, 'Granite kerb', '#8D867C'),
            bevel=0.03, collection='Street')
    kit.box('Gutter', (140, 0.35, 0.02), (10, -0.17, 0.005), kit.material('Gutter', '#4B433D', roughness=0.4), collection='Street')
    road['studio_ground'] = True

    # --- the row of townhouses ---------------------------------------------------------------
    x = -42.0
    i = 0
    while x < 48:
        w = rng.uniform(5.2, 7.6)
        building(kit, mats, x, w, walls[i % len(walls)], SHOPS[i % len(SHOPS)], rng)
        x += w
        i += 1
    for lx in range(-38, 48, 7):
        lamp_post(kit, lx + 0.3, mats)

    # --- pavement props: planters and a sandwich board, kept clear of the walker's line ------
    for px in (-8.5, 5.6, 16.0):
        kit.lathe('Pot', [(0, 0), (0.22, 0), (0.3, 0.5), (0.33, 0.55), (0, 0.55)], 32, mats['planter'],
                  location=(px, SIDEWALK_DEPTH - 0.5, SIDEWALK_TOP), collection='Street')
        for k in range(7):
            kit.sphere('Shrub', rng.uniform(0.17, 0.26), (px + rng.uniform(-0.15, 0.15), SIDEWALK_DEPTH - 0.5 + rng.uniform(-0.12, 0.12),
                       SIDEWALK_TOP + 0.65 + rng.uniform(0, 0.25)), mats['leaf'], segments=16, rings=10, collection='Street')
    # An A-frame chalkboard: two framed boards leaning on each other.
    chalk = clay(kit, 'Chalkboard', '#26302C', rough=0.9, grain=0.05)
    for side in (1, -1):
        kit.box('Sandwich board frame', (0.66, 0.035, 0.95), (1.4, SIDEWALK_DEPTH - 0.75 + side * 0.1, SIDEWALK_TOP + 0.46),
                mats['shelf'], rotation=(side * 12, 0, 0), bevel=0.012, collection='Street')
        kit.box('Sandwich board slate', (0.54, 0.04, 0.72), (1.4, SIDEWALK_DEPTH - 0.75 + side * 0.105, SIDEWALK_TOP + 0.5),
                chalk, rotation=(side * 12, 0, 0), collection='Street')

    # --- the walker ----------------------------------------------------------------------------
    J = build_walker(kit)
    animate_walker(kit, J)

    # --- light: low sun down the street, sky fill, haze --------------------------------------
    kit.sky(sun_elevation=SUN_ELEVATION, sun_rotation=SUN_AZIMUTH, strength=0.09, sun_disc=False, aerosol=2.0)
    kit.sun(elevation=SUN_ELEVATION, azimuth=SUN_AZIMUTH, strength=5.5, color='#FFB070', angle=1.2)
    kit.haze(density=0.006, color='#FFD9B0', anisotropy=0.55, size=(120, 26, 16), location=(5, 0, 8))

    # --- camera: dolly along the road, a touch slower than the walker -----------------------
    span = WALK_SPEED * kit.seconds
    c0 = WALKER_X0 + 3.2
    c1 = c0 + span * CAM_LAG
    cam = kit.camera((c0, CAM_Y, CAM_Z), (c0 - 1.8, WALK_Y, 1.7), lens=28, dof=None, fstop=2.2)
    kit.dolly(cam, (c0, CAM_Y, CAM_Z), (c1, CAM_Y, CAM_Z), (c0 - 1.8, WALK_Y, 1.7), (c1 - 1.8, WALK_Y, 1.7),
              ease_kind='in_out', power=1.4)
    cam.data.dof.use_dof = True
    cam.data.dof.focus_object = J['chest']           # focus rides with the walker
    cam.data.dof.aperture_fstop = 2.2
    kit.handheld(cam, amount=0.22, cycles=2, seed=8)
    kit.render(exposure=0.65, look='AgX - Medium High Contrast', motion_blur=True, shutter=0.5)
