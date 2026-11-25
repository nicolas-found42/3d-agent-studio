"""Bamboo grove in rain: a rack focus from wet near stalks to a mossy stone lantern.

Teaches:
- bmesh-built segmented stalks with a per-vertex 'node' attribute that the shader reads to paint
  node ridges and the waxy band under each node (geometry and material agree by construction);
- a few unique stalk meshes shared by hundreds of linked instances, each coloured differently via
  Object Info > Random;
- moss grown onto scanned stone by mixing on the up-facing normal;
- rain as two stacked tiles of streak geometry falling on a sawtooth, with motion blur disabled on
  the rain so the wrap frame never smears;
- overcast light from a soft world gradient plus haze for depth, and kit.rack_focus at f/1.4.
"""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

# ---------------------------------------------------------------- shot constants
CAM_POS = Vector((0.05, -0.6, 1.32))
LANTERN_POS = Vector((0.75, 5.7, 0.0))
NEAR_STALKS = [(-0.02, 0.48, 0.06), (0.86, 1.75, 0.07)]   # x, y, radius: the stalks we focus on first
GROVE_AREA = (-7.0, 7.0, -1.5, 30.0)                       # x0, x1, y0, y1 of the scattered grove
STALK_COUNT = 300
RAIN_TILE_HEIGHT = 4.5                                     # metres; falls one tile per 15 frames = 9 m/s
RAIN_PER_TILE = 2400
FOCUS_NEAR, FOCUS_FAR = 1.15, 6.35

GROUND_TEX = 'polyhaven:forest_leaves_02@1k'
STONE_TEX = 'polyhaven:rock_pitted_mossy@1k'


def sock(sockets, identifier):
    """Pick a node socket by identifier (Mix nodes have several sockets named 'A')."""
    return next(s for s in sockets if s.identifier == identifier)


def ground_height(kit, x, y):
    """Gentle undulation shared by the terrain mesh and everything placed on it."""
    return 0.22 * kit.noise(x * 0.11 + 3.1, y * 0.11 + 7.7, octaves=2) + 0.05 * kit.noise(x * .6, y * .6, 2.0, octaves=1)


def path_point(s):
    """Centre line of the stepping-stone path, s in metres along y."""
    return Vector((0.12 + 0.55 * math.sin(s * 0.33) - 0.02 * s, s, 0.0))


# ---------------------------------------------------------------- materials
def bamboo_material(kit):
    """Wet culm: per-object hue from Object Info > Random, fine vertical streaks, node bands read
    from the 'node' mesh attribute written by the stalk builder."""
    mat = kit.material('Bamboo culm', '#5E7A2C', roughness=0.32, coat=0.45)
    mat.node_tree.nodes['Principled BSDF'].inputs['Coat Roughness'].default_value = 0.08
    nt, bs = mat.node_tree, kit.bsdf(mat)
    info = nt.nodes.new('ShaderNodeObjectInfo')
    hue = kit._ramp(nt, ['#3F5E22', '#5C7A2A', '#7C8A34', '#8E8C44', '#4D6A2A'])
    nt.links.new(info.outputs['Random'], hue.inputs['Fac'])
    # Long vertical streaks: object coords squashed in Z.
    coord = nt.nodes.new('ShaderNodeTexCoord')
    mapping = nt.nodes.new('ShaderNodeMapping')
    mapping.inputs['Scale'].default_value = (60, 60, 1.2)
    nt.links.new(coord.outputs['Object'], mapping.inputs['Vector'])
    streak = nt.nodes.new('ShaderNodeTexNoise')
    streak.inputs['Detail'].default_value = 6
    nt.links.new(mapping.outputs['Vector'], streak.inputs['Vector'])
    vary = nt.nodes.new('ShaderNodeMix')
    vary.data_type, vary.blend_type = 'RGBA', 'OVERLAY'
    sock(vary.inputs, 'Factor_Float').default_value = 0.55
    nt.links.new(hue.outputs['Color'], sock(vary.inputs, 'A_Color'))
    nt.links.new(streak.outputs['Color'], sock(vary.inputs, 'B_Color'))
    # Node bands: 0 = plain culm, 0.5 = pale waxy ring below the node, 1 = darker node ridge.
    attr = nt.nodes.new('ShaderNodeAttribute')
    attr.attribute_name = 'node'
    band = kit._ramp(nt, [(0.0, '#000000'), (0.35, '#000000'), (0.5, '#8E9672'), (0.75, '#9CA27E'), (1.0, '#34401C')])
    nt.links.new(attr.outputs['Fac'], band.inputs['Fac'])
    weight = nt.nodes.new('ShaderNodeMapRange')
    weight.inputs['From Min'].default_value, weight.inputs['From Max'].default_value = 0.3, 0.9
    weight.inputs['To Max'].default_value = 0.7
    nt.links.new(attr.outputs['Fac'], weight.inputs['Value'])
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    nt.links.new(weight.outputs['Result'], sock(mix.inputs, 'Factor_Float'))
    nt.links.new(sock(vary.outputs, 'Result_Color'), sock(mix.inputs, 'A_Color'))
    nt.links.new(band.outputs['Color'], sock(mix.inputs, 'B_Color'))
    nt.links.new(sock(mix.outputs, 'Result_Color'), bs.inputs['Base Color'])
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.15
    nt.links.new(streak.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bs.inputs['Normal'])
    return mat


def leaf_material(kit, name, colors, translucency=0.35):
    """Thin leaf: principled front mixed with a translucent back so backlit leaves glow."""
    mat = kit.material(name, colors[0], roughness=0.38, coat=0.2)
    nt, bs = mat.node_tree, kit.bsdf(mat)
    info = nt.nodes.new('ShaderNodeObjectInfo')
    ramp = kit._ramp(nt, colors)
    nt.links.new(info.outputs['Random'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], bs.inputs['Base Color'])
    trans = nt.nodes.new('ShaderNodeBsdfTranslucent')
    nt.links.new(ramp.outputs['Color'], trans.inputs['Color'])
    mix = nt.nodes.new('ShaderNodeMixShader')
    mix.inputs[0].default_value = translucency
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    nt.links.new(bs.outputs[0], mix.inputs[1])
    nt.links.new(trans.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    return mat


def add_moss(kit, mat, amount=0.55, scale=5.0):
    """Grow moss on up-facing surfaces of an existing principled material (e.g. a scanned stone):
    factor = smoothstep(normal.z) * clumpy noise, mixed into colour and roughness."""
    nt, bs = mat.node_tree, kit.bsdf(mat)
    base_link = bs.inputs['Base Color'].links
    base = base_link[0].from_socket if base_link else None
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(geo.outputs['Normal'], sep.inputs[0])
    up = nt.nodes.new('ShaderNodeMapRange')
    up.interpolation_type = 'SMOOTHSTEP'
    up.inputs['From Min'].default_value, up.inputs['From Max'].default_value = 1 - amount - 0.25, 1 - amount + 0.25
    nt.links.new(sep.outputs['Z'], up.inputs['Value'])
    coord = nt.nodes.new('ShaderNodeTexCoord')
    clump = nt.nodes.new('ShaderNodeTexNoise')
    clump.inputs['Scale'].default_value = scale
    clump.inputs['Detail'].default_value = 8
    nt.links.new(coord.outputs['Object'], clump.inputs['Vector'])
    edge = nt.nodes.new('ShaderNodeMapRange')
    edge.inputs['From Min'].default_value, edge.inputs['From Max'].default_value = 0.42, 0.58
    nt.links.new(clump.outputs['Fac'], edge.inputs['Value'])
    fac = nt.nodes.new('ShaderNodeMath')
    fac.operation = 'MULTIPLY'
    nt.links.new(up.outputs['Result'], fac.inputs[0])
    nt.links.new(edge.outputs['Result'], fac.inputs[1])
    moss_col = kit._ramp(nt, ['#2F4A18', '#4E6E22', '#6F8A2E'])
    nt.links.new(clump.outputs['Fac'], moss_col.inputs['Fac'])
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    nt.links.new(fac.outputs[0], sock(mix.inputs, 'Factor_Float'))
    if base:
        nt.links.new(base, sock(mix.inputs, 'A_Color'))
    else:
        sock(mix.inputs, 'A_Color').default_value = bs.inputs['Base Color'].default_value
    nt.links.new(moss_col.outputs['Color'], sock(mix.inputs, 'B_Color'))
    nt.links.new(sock(mix.outputs, 'Result_Color'), bs.inputs['Base Color'])
    rough = nt.nodes.new('ShaderNodeMix')
    rough.data_type = 'FLOAT'
    nt.links.new(fac.outputs[0], sock(rough.inputs, 'Factor_Float'))
    r_link = bs.inputs['Roughness'].links
    if r_link:
        nt.links.new(r_link[0].from_socket, sock(rough.inputs, 'A_Float'))
    else:
        sock(rough.inputs, 'A_Float').default_value = bs.inputs['Roughness'].default_value
    sock(rough.inputs, 'B_Float').default_value = 0.85
    nt.links.new(sock(rough.outputs, 'Result_Float'), bs.inputs['Roughness'])
    return mat


# ---------------------------------------------------------------- geometry builders
def stalk_mesh(kit, name, height, radius, rng, segments=10, bow=None):
    """A bamboo culm as stacked rings: a ridge at each node, a waxy band just below it, slight
    taper and bow. Writes a float 'node' attribute per vertex for the shader."""
    bm = bmesh.new()
    layer = bm.verts.layers.float.new('node')
    bow = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), 0)).normalized() * (rng.uniform(0.05, 0.25) if bow is None else bow)
    rings, z = [], 0.0
    while z < height:
        spacing = min(0.42, 0.14 + 0.09 * z) * rng.uniform(0.92, 1.08)
        if z > height * 0.8:
            spacing *= 0.8
        z1 = min(height, z + spacing)
        # (fraction of internode, radius factor, node value)
        for f, rf, nv in ((0.0, 1.07, 1.0), (0.03, 1.0, 0.85), (0.06, 0.99, 0.0), (0.5, 0.985, 0.0),
                          (0.88, 0.99, 0.0), (0.92, 1.0, 0.5), (0.97, 1.01, 0.62)):
            rings.append((z + f * (z1 - z), rf, nv))
        z = z1
    loops = []
    for zz, rf, nv in rings:
        u = zz / height
        r = radius * (1 - 0.45 * u) * rf
        c = bow * u * u
        loop = []
        for i in range(segments):
            a = math.tau * i / segments
            v = bm.verts.new((c.x + r * math.cos(a), c.y + r * math.sin(a), zz))
            v[layer] = nv
            loop.append(v)
        loops.append(loop)
    for a, b in zip(loops, loops[1:]):
        for i in range(segments):
            bm.faces.new((a[i], a[(i + 1) % segments], b[(i + 1) % segments], b[i]))
    bm.faces.new(list(reversed(loops[0])))
    bm.faces.new(loops[-1])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me


def leaf_spray_mesh(kit, name, rng, leaves=9, length=0.7, droop=0.35, leaf_len=0.2):
    """A thin twig carrying lanceolate bamboo leaves that hang and fan out."""
    bm = bmesh.new()

    def twig_at(s):
        return Vector((s * length, 0, -droop * s * s))

    # twig as a thin square tube
    steps = 6
    prev = None
    for k in range(steps + 1):
        p = twig_at(k / steps)
        w = 0.006 * (1 - 0.6 * k / steps)
        ring = [bm.verts.new(p + Vector((0, dy, dz))) for dy, dz in ((-w, -w), (w, -w), (w, w), (-w, w))]
        if prev:
            for i in range(4):
                bm.faces.new((prev[i], prev[(i + 1) % 4], ring[(i + 1) % 4], ring[i]))
        prev = ring
    for j in range(leaves):
        s = 0.25 + 0.75 * j / max(1, leaves - 1)
        base = twig_at(s)
        yaw = (1 if j % 2 else -1) * rng.uniform(35, 75) + rng.uniform(-10, 10)
        pitch = -rng.uniform(25, 60)
        L = leaf_len * rng.uniform(0.75, 1.15)
        rot = Matrix.Rotation(math.radians(yaw), 3, 'Z') @ Matrix.Rotation(math.radians(pitch), 3, 'Y')
        rows = []
        n = 7
        for i in range(n + 1):
            u = i / n
            half = 0.13 * L * math.sin(math.pi * min(1, u * 1.15)) ** 0.8 * (1 - 0.2 * u)
            sag = -0.25 * L * u * u
            row = []
            for side in (-1, 0, 1):
                fold = 0.012 * L * abs(side)  # shallow V along the midrib
                local = Vector((u * L, side * half, sag + fold))
                row.append(bm.verts.new(base + rot @ local))
            rows.append(row)
        for a, b in zip(rows, rows[1:]):
            bm.faces.new((a[0], b[0], b[1], a[1]))
            bm.faces.new((a[1], b[1], b[2], a[2]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me


def hex_prism(kit, name, r_bottom, r_top, height, z, material, sides=6, location=(0, 0, 0)):
    verts = []
    for rr, zz in ((r_bottom, 0), (r_top, height)):
        for i in range(sides):
            a = math.tau * (i + 0.5) / sides
            verts.append((rr * math.cos(a), rr * math.sin(a), zz))
    faces = [tuple(reversed(range(sides))), tuple(range(sides, 2 * sides))]
    faces += [(i, (i + 1) % sides, sides + (i + 1) % sides, sides + i) for i in range(sides)]
    obj = kit.mesh(name, verts, faces, material, (location[0], location[1], location[2] + z))
    kit.bevel(obj, 0.012, 2)
    return obj


def lantern_roof(kit, name, radius, z, material, location):
    """Hexagonal kasa with up-curled corners (warabite): concentric polygon rings whose corner
    vertices lift more toward the rim."""
    seg = 36
    profile = [(1.0, 0.0), (1.0, 0.05), (0.78, 0.12), (0.5, 0.2), (0.24, 0.27), (0.12, 0.29), (0.0, 0.3)]
    verts, faces = [], []
    for k, (rf, zf) in enumerate(profile):
        for i in range(seg):
            a = math.tau * i / seg
            # distance to a hexagon edge at angle a (corners at multiples of 60 degrees)
            local = (a % (math.tau / 6)) - math.tau / 12
            hexr = math.cos(math.tau / 12) / math.cos(local)
            corner = (abs(local) / (math.tau / 12)) ** 4
            lift = 0.07 * corner * rf ** 3 if k <= 2 else 0
            r = radius * rf * hexr * (1 + 0.06 * corner * rf)
            verts.append((r * math.cos(a), r * math.sin(a), zf * radius + lift))
    n = len(profile)
    for k in range(n - 1):
        for i in range(seg):
            a0, a1 = k * seg + i, k * seg + (i + 1) % seg
            faces.append((a0, a1, a1 + seg, a0 + seg))
    faces.append(tuple(reversed(range(seg))))  # underside
    obj = kit.mesh(name, verts, faces, material, (location[0], location[1], location[2] + z), smooth=True)
    kit._merge(obj)
    kit.bevel(obj, 0.01, 2, harden=False)
    return obj


def build_lantern(kit, stone, glow):
    """Kasuga-style stone lantern, ~2 m: base, pillar, platform, firebox with windows, roof, jewel."""
    p = LANTERN_POS.copy()
    p.z = ground_height(kit, p.x, p.y) - 0.04
    parts = [
        hex_prism(kit, 'Lantern base slab', 0.42, 0.40, 0.14, 0.0, stone, location=p),
        hex_prism(kit, 'Lantern base lotus', 0.36, 0.22, 0.1, 0.14, stone, location=p),
    ]
    pillar = kit.lathe('Lantern pillar', [(0, 0), (0.13, 0), (0.12, 0.05), (0.11, 0.33), (0.13, 0.35), (0.13, 0.39),
                                          (0.11, 0.41), (0.105, 0.72), (0.12, 0.76), (0, 0.76)],
                       segments=32, material=stone, location=(p.x, p.y, p.z + 0.24))
    parts.append(pillar)
    parts.append(hex_prism(kit, 'Lantern platform', 0.2, 0.33, 0.16, 1.0, stone, location=p))
    firebox = hex_prism(kit, 'Lantern firebox', 0.24, 0.23, 0.34, 1.16, stone, location=p)
    # Window cut-outs: two boxes through the firebox (front/back and a side pair).
    for k, ang in enumerate((90, 30)):
        cutter = kit.box(f'Lantern window cutter {k}', (0.15, 0.8, 0.2), (p.x, p.y, p.z + 1.33),
                         rotation=(0, 0, ang))
        kit.boolean(firebox, cutter)
    parts.append(firebox)
    # Paper screen inside the firebox and a small flame light: a warm focal point in the grey.
    paper = hex_prism(kit, 'Lantern paper screen', 0.16, 0.16, 0.24, 1.21, glow, location=p)
    paper.visible_shadow = False
    kit.point('Lantern candle', (p.x, p.y, p.z + 1.33), power=6, color='#FFB060', radius=0.04)
    parts.append(lantern_roof(kit, 'Lantern roof', 0.5, 1.48, stone, p))
    parts.append(kit.lathe('Lantern jewel', [(0, 0), (0.07, 0), (0.07, 0.03), (0.045, 0.05), (0.09, 0.1), (0.075, 0.16),
                                             (0.03, 0.21), (0.0, 0.24)],
                           segments=32, material=stone, location=(p.x, p.y, p.z + 1.62)))
    return parts


def build(kit):
    rng = random.Random(kit.seed)

    # ------------------------------------------------------------ render and light
    kit.render(exposure=0.5, look='AgX - Medium High Contrast', bounces=6, motion_blur=True)
    # Overcast: a soft, bright grey-green dome; no sun. The haze carries the depth.
    kit.world('#8E9A92', strength=1.1, top='#DCE3E0')
    kit.haze(density=0.032, color='#D4DCD6', anisotropy=0.15, size=(34, 64, 16), location=(0, 22, 7.5))

    # ------------------------------------------------------------ ground and path
    ground_mat = kit.textured('Wet leaf litter', GROUND_TEX, scale=0.55, roughness=0.42, tint='#B9B49E')
    n, size = 90, 46.0
    verts, faces = [], []
    for j in range(n + 1):
        for i in range(n + 1):
            x, y = (i / n - .5) * size, (j / n - .5) * size + 12
            verts.append((x, y, ground_height(kit, x, y)))
    for j in range(n):
        for i in range(n):
            a = j * (n + 1) + i
            faces.append((a, a + 1, a + n + 2, a + n + 1))
    kit.mesh('Grove floor', verts, faces, ground_mat, smooth=True, ground=True)

    stone_mat = kit.textured('Mossy lantern stone', STONE_TEX, scale=1.6, tint='#D2D5D2')
    add_moss(kit, stone_mat, amount=0.42, scale=6.0)
    path_mat = kit.textured('Wet stepping stone', STONE_TEX, scale=1.1, roughness=0.22, tint='#BDBDB6')
    add_moss(kit, path_mat, amount=0.08, scale=9.0)
    s = -1.0
    while s < 22:
        c = path_point(s)
        stone = kit.rock(f'Stepping stone {s:.1f}', radius=rng.uniform(0.3, 0.37), squash=0.24, detail=3,
                         material=path_mat, seed=rng.uniform(0, 99),
                         location=(c.x + rng.uniform(-0.06, 0.06), c.y, ground_height(kit, c.x, c.y) - 0.015))
        # Sunk below their equator: stones bedded in the soil, never shelves with dark gaps under them.
        stone.scale = (rng.uniform(1.0, 1.3), rng.uniform(0.8, 1.0), 1.0)
        s += rng.uniform(0.78, 0.9)

    # ------------------------------------------------------------ lantern
    glow = kit.material('Lantern paper', '#F3E2C0', roughness=0.8, emission='#FFB866', emission_strength=1.6)
    build_lantern(kit, stone_mat, glow)

    # ------------------------------------------------------------ bamboo
    culm = bamboo_material(kit)
    leaf = leaf_material(kit, 'Bamboo leaf', ['#3D6A1E', '#557E26', '#6E8E2C', '#4A7322'])
    dead_leaf = leaf_material(kit, 'Fallen leaf', ['#7A6A3A', '#9C8A4E', '#6B5A30', '#B0A060'], translucency=0.15)
    protos = [stalk_mesh(kit, f'Culm mesh {k}', rng.uniform(9, 13), 1.0, rng) for k in range(7)]
    sprays = [leaf_spray_mesh(kit, f'Leaf spray mesh {k}', rng) for k in range(4)]
    stalks_coll = kit.collection('Bamboo')

    for me in protos:
        me.materials.append(culm)
    for me in sprays:
        me.materials.append(leaf)

    def add_stalk(name, x, y, radius, sprays_from, mesh=None):
        """A culm and its leaf sprays share an unscaled pivot empty at the root; the pivot sways.
        (Parenting to the radius-scaled culm itself would shear the children when it rotates.)"""
        pivot = bpy.data.objects.new(f'{name} pivot', None)
        pivot.location = (x, y, ground_height(kit, x, y) - 0.05)
        stalks_coll.objects.link(pivot)
        ob = bpy.data.objects.new(name, mesh or rng.choice(protos))
        ob.parent = pivot
        ob.scale = (radius, radius, 1.0 if mesh else rng.uniform(0.9, 1.1))
        ob.rotation_euler.z = rng.uniform(0, math.tau)
        stalks_coll.objects.link(ob)
        # Leaf sprays hang off the culm above eye level.
        for _ in range(rng.randint(3, 6)):
            sp = bpy.data.objects.new(f'{name} spray', rng.choice(sprays))
            sp.parent = pivot
            sp.location = (0, 0, rng.uniform(sprays_from, 9.0))
            sp.rotation_euler = (0, math.radians(rng.uniform(-25, 10)), math.radians(rng.uniform(0, 360)))
            sp.scale = (rng.uniform(0.8, 1.3),) * 3
            stalks_coll.objects.link(sp)
        return pivot

    stalks = []
    straight = stalk_mesh(kit, 'Near culm mesh', 11.0, 1.0, rng, bow=0.0)   # beads need a known surface
    straight.materials.append(culm)
    for i, (x, y, r) in enumerate(NEAR_STALKS):
        stalks.append(add_stalk(f'Near stalk {i + 1}', x, y, r, 3.2, mesh=straight))
    placed = [(x, y) for x, y, _ in NEAR_STALKS]
    tries = 0
    while len(stalks) < STALK_COUNT and tries < STALK_COUNT * 40:
        tries += 1
        x, y = rng.uniform(*GROVE_AREA[:2]), rng.uniform(*GROVE_AREA[2:])
        c = path_point(y)
        if abs(x - c.x) < 0.75 + 0.02 * max(0, y):          # keep the path corridor open
            continue
        if (Vector((x, y)) - LANTERN_POS.xy).length < 1.3:   # clearing around the lantern
            continue
        if (x - CAM_POS.x) ** 2 + (y - CAM_POS.y) ** 2 < 0.8 ** 2:
            continue
        if any((x - px) ** 2 + (y - py) ** 2 < 0.36 ** 2 for px, py in placed):
            continue
        placed.append((x, y))
        stalks.append(add_stalk(f'Stalk {len(stalks)}', x, y, rng.uniform(0.04, 0.075),
                                1.6 if y > 4 else 2.6))

    # Sway: a shared gust plus per-stalk flutter, pivoting at the root; tall culms move at the top.
    for k, ob in enumerate(stalks):
        ph = rng.uniform(0, 10)
        amp = math.radians(rng.uniform(0.5, 1.1))
        def sway(t, ph=ph, amp=amp):
            gust = 0.6 + 0.4 * math.sin(t * 2.2 + 0.3)
            x = amp * (gust * kit.noise(t * 2.4 + ph, ph, 1.7, octaves=2) + 0.25)
            y = amp * 0.7 * gust * kit.noise(ph, t * 2.4 + ph, 3.1, octaves=2)
            return (x, y, 0.0)
        kit.animate(ob, 'rotation_euler', sway, step=3, interpolation='BEZIER')

    # Low dwarf-bamboo undergrowth (sasa) along the path edges and around the lantern.
    sasa = kit.collection('Undergrowth')
    for i in range(140):
        y = rng.uniform(-0.5, 18)
        c = path_point(y)
        side = rng.choice((-1, 1))
        x = c.x + side * rng.uniform(0.75, 2.6)
        if (Vector((x, y)) - LANTERN_POS.xy).length < 0.6:
            continue
        sp = bpy.data.objects.new(f'Sasa {i}', rng.choice(sprays))
        sp.location = (x, y, ground_height(kit, x, y) - 0.02)
        sp.rotation_euler = (0, math.radians(-rng.uniform(55, 80)), math.radians(rng.uniform(0, 360)))
        sp.scale = (rng.uniform(0.6, 1.0),) * 3
        sasa.objects.link(sp)

    # Fallen leaves for close-range detail the texture alone cannot give.
    litter = bpy.data.meshes.new('Fallen leaf mesh')
    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in ((0, 0, 0), (0.05, 0.009, 0.004), (0.1, 0.011, 0.006), (0.15, 0, 0.002),
                                    (0.1, -0.011, 0.006), (0.05, -0.009, 0.004))]
    bm.faces.new((vs[0], vs[1], vs[2], vs[3], vs[4], vs[5]))
    bm.to_mesh(litter)
    bm.free()
    litter.materials.append(dead_leaf)
    litter_coll = kit.collection('Leaf litter')
    for i in range(900):
        x, y = rng.uniform(-2.6, 3.2), rng.uniform(-0.6, 9.0)
        ob = bpy.data.objects.new(f'Fallen leaf {i}', litter)
        ob.location = (x, y, ground_height(kit, x, y) + 0.006)
        ob.rotation_euler = (rng.uniform(-.15, .15), rng.uniform(-.15, .15), rng.uniform(0, math.tau))
        ob.scale = (rng.uniform(0.7, 1.3),) * 3
        litter_coll.objects.link(ob)

    # Raindrops beaded on the near culms: they read only while the focus is near.
    drop_mat = kit.glass('Raindrop', '#F4FAFF', roughness=0.02, ior=1.33)
    for i, (x, y, r) in enumerate(NEAR_STALKS):
        pivot = stalks[i]
        to_cam = (CAM_POS.xy - Vector((x, y))).normalized()
        for k in range(60):
            a = math.atan2(to_cam.y, to_cam.x) + rng.uniform(-1.2, 1.2)
            z = rng.uniform(0.7, 2.2)
            rr = r * (1 - 0.45 * z / 11.0) * 0.985
            d = rng.uniform(0.0018, 0.0042)
            bead = kit.sphere(f'Bead {i}-{k}', d, ((rr + d * 0.4) * math.cos(a), (rr + d * 0.4) * math.sin(a), z + 0.05),
                              drop_mat, segments=10, rings=6, scale=(1, 1, 1.4))
            bead.parent = pivot   # local to the root pivot, so beads ride the sway

    # ------------------------------------------------------------ rain
    # Two identical tiles of streaks, stacked; each falls one tile height per 15 frames on a
    # sawtooth, so the pair always covers the view. Motion blur is off on the rain: the streak
    # length (shutter-like) is modelled, and the wrap frame cannot smear.
    rain_mat = bpy.data.materials.new('Rain streak')
    rain_mat.use_nodes = True
    nt = rain_mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = kit.color('#E4ECEA')
    em.inputs['Strength'].default_value = 0.7
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    mix.inputs[0].default_value = 0.28
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    bm = bmesh.new()
    fwd = (LANTERN_POS - CAM_POS).normalized()
    for i in range(RAIN_PER_TILE):
        depth = 0.9 + 11 * rng.random() ** 1.3           # thinner near the lens: close drops blur huge
        side = rng.uniform(-1, 1) * (0.5 + depth * 0.45)
        base = CAM_POS + fwd * depth + Vector((fwd.y, -fwd.x, 0)) * side
        z = rng.uniform(0, RAIN_TILE_HEIGHT)
        L = rng.uniform(0.14, 0.26)
        w = 0.0008 + 0.0006 * depth / 12
        for dx, dy in ((w, 0), (0, w)):                  # two crossed quads read from any angle
            q = [bm.verts.new((base.x - dx, base.y - dy, z)), bm.verts.new((base.x + dx, base.y + dy, z)),
                 bm.verts.new((base.x + dx, base.y + dy, z + L)), bm.verts.new((base.x - dx, base.y - dy, z + L))]
            bm.faces.new(q)
    rain_me = bpy.data.meshes.new('Rain tile')
    bm.to_mesh(rain_me)
    bm.free()
    rain_me.materials.append(rain_mat)
    period = 15
    for k in range(2):
        tile = bpy.data.objects.new(f'Rain tile {k + 1}', rain_me)
        kit.scene.collection.objects.link(tile)
        tile.visible_shadow = False
        try:
            tile.cycles.use_motion_blur = False
        except AttributeError:
            pass
        z0 = k * RAIN_TILE_HEIGHT

        def fall(t, z0=z0):
            f = kit.frame(t) - 1
            return (0, 0, z0 - RAIN_TILE_HEIGHT * ((f % period) / period))
        kit.animate(tile, 'location', fall)

    # ------------------------------------------------------------ camera: rack focus
    cam = kit.camera(CAM_POS, target=LANTERN_POS + Vector((0, 0, 1.05)), lens=40, fstop=1.4, dof=FOCUS_NEAR)
    cam.data.dof.aperture_blades = 7
    kit.dolly(cam, CAM_POS, CAM_POS + Vector((0.08, 0.32, 0.03)), ease_kind='in_out', power=2)
    kit.rack_focus(cam, [(0.0, FOCUS_NEAR), (0.28, FOCUS_NEAR), (0.68, FOCUS_FAR), (1.0, FOCUS_FAR)], fstop=1.4)
    kit.handheld(cam, amount=0.12, cycles=2, seed=5)
    kit.note('Focus racks from the near culm (1.15 m) to the lantern (6.35 m) between 28% and 68% of the shot.')
