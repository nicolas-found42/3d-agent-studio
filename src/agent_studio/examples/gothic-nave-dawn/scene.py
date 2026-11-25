"""Gothic nave at dawn: a slow dolly down a High Gothic nave toward the crossing.

Teaches: building real architecture from a few measured functions instead of primitives.
One pointed-arch height function drives the arcade cutters, the window tracery, the groin
vault surfaces and the rib paths, so every curve in the building agrees with every other.
Light is layered like a photograph of a real interior: a low physical sun through the
clerestory, a dim physical sky through every opening, and a thin volume of dust so the sun
draws shafts. Proportions follow a French High Gothic elevation (about 31 m to the vault crown,
three storeys: arcade, triforium, clerestory).
"""
import math

import bmesh
import bpy
from mathutils import Vector

# ----------------------------------------------------------------------------- dimensions (m)
BAY = 6.0                 # pier spacing along the nave (Y is east, toward the crossing)
NAVE_HALF = 5.0           # inner face of the nave wall
WALL = 0.8                # wall thickness
PIER_X = NAVE_HALF + WALL / 2
AISLE_OUT = 12.0          # inner face of the aisle wall
NAVE_BAYS = 8             # y 0..48
CROSSING = (48.0, 60.0)   # crossing square, open to the transepts
EAST = 72.0               # east wall with lancets and a rose
TRANSEPT_OUT = 24.0

ARCADE_SPRING = 9.2       # capital tops of the main piers
ARCADE_SPAN = 4.8
TRIFORIUM = (14.3, 16.7)  # sill and springing of the triforium arcade
CLERESTORY = (19.2, 25.4) # sill and springing of the clerestory lancets
VAULT_SPRING = 24.0
VAULT_RISE = 7.0          # crown at 31 m
AISLE_SPRING, AISLE_RISE = 9.2, 4.5

# ----------------------------------------------------------------------------- light and look
SUN_ELEVATION = 13.0      # very low dawn sun: beams through the south aisle lancets cross the
SUN_AZIMUTH = 62.0        # arcade and land on the nave floor ahead and to the right, slanting
                          # toward the lens (forward scattering makes them glow). Much further
                          # ahead and the 0.8 m deep window jambs swallow the beam.
SUN_COLOR = '#FFB26E'
SUN_STRENGTH = 20.0
HAZE_DENSITY = 0.012      # air in the whole church: dense enough that the low beams read as shafts
DUST_DENSITY = 0.004      # a little extra up high so the clerestory beams glow under the vault
EXPOSURE = 1.8

# ----------------------------------------------------------------------------- camera
CAM_START = (0.0, 2.5, 1.65)
CAM_END = (0.0, 13.5, 1.65)
LENS = 20.0
SHIFT_Y = 0.22            # lens shift keeps verticals upright while showing the vault

STONE = 'polyhaven:large_sandstone_blocks@1k'
FLOOR = 'polyhaven:monastery_stone_floor@1k'


# ============================================================================= arch geometry
def pointed(u, half, rise):
    """Height above springing of a two-centred pointed arch, at offset u from its centre line."""
    u = min(abs(u), half)
    cx = (rise * rise - half * half) / (2 * half)
    r = half + cx
    return math.sqrt(max(0.0, r * r - (u + cx) ** 2))


def pointed_offset(z, half, rise):
    """Inverse of `pointed`: the offset at which the arch reaches height z."""
    cx = (rise * rise - half * half) / (2 * half)
    r = half + cx
    return max(0.0, math.sqrt(max(0.0, r * r - z * z)) - cx)


def lancet(width, sill, spring, rise=None, steps=18):
    """Outline (u, z) of a pointed opening, clockwise from the bottom left."""
    h = width / 2
    rise = rise or width * 0.95
    pts = [(-h, sill)]
    pts += [(-h + width * i / steps, spring + pointed(-h + width * i / steps, h, rise)) for i in range(steps + 1)]
    pts.append((h, sill))
    return pts


def circle(cu, cz, r, n=28):
    return [(cu + r * math.cos(2 * math.pi * i / n), cz + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def add_prism(bm, outline, place):
    """Extrude a (u, z) outline between two caps; place(u, z, w) maps it into the world, w in {0, 1}."""
    a = [bm.verts.new(place(u, z, 0)) for u, z in outline]
    b = [bm.verts.new(place(u, z, 1)) for u, z in outline]
    bm.faces.new(a)
    bm.faces.new(list(reversed(b)))
    n = len(a)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], a[j], b[j], b[i]))


def add_face(bm, outline, place):
    bm.faces.new([bm.verts.new(place(u, z, 0)) for u, z in outline])


def bm_object(kit, name, bm, material, collection, smooth_angle=None):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    if material:
        me.materials.append(material)
    if smooth_angle is not None:
        for p in me.polygons:
            p.use_smooth = True
        me.set_sharp_from_angle(angle=math.radians(smooth_angle))
    kit.collection(collection).objects.link(obj)
    return obj


# ============================================================================= materials
def stone_material(kit, name, tint, scale=0.45):
    """Scanned ashlar, lifted to a pale limestone and tinted per part, with a large-scale noise that
    varies tone like real weathering so long walls do not show texture repetition."""
    mat = kit.textured(name, STONE, scale=scale, bump=0.6, tint=tint)
    nt = mat.node_tree
    bs = kit.bsdf(mat)
    mult = bs.inputs['Base Color'].links[0].from_node
    scan = mult.inputs['A'].links[0].from_socket
    lift = nt.nodes.new('ShaderNodeHueSaturation')          # grey scan -> brighter, less saturated
    lift.inputs['Saturation'].default_value = 0.35
    lift.inputs['Value'].default_value = 1.7
    nt.links.new(scan, lift.inputs['Color'])
    nt.links.new(lift.outputs['Color'], mult.inputs['A'])
    base = mult.outputs['Result']
    coord = nt.nodes.new('ShaderNodeTexCoord')
    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 0.18
    noise.inputs['Detail'].default_value = 4
    nt.links.new(coord.outputs['Object'], noise.inputs['Vector'])
    ramp = kit._ramp(nt, ['#B9AE9C', '#FFFFFF'])
    nt.links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type, mix.blend_type = 'RGBA', 'MULTIPLY'
    mix.inputs['Factor'].default_value = 1.0
    nt.links.new(base, mix.inputs['A'])
    nt.links.new(ramp.outputs['Color'], mix.inputs['B'])
    nt.links.new(mix.outputs['Result'], bs.inputs['Base Color'])
    return mat


def leaded_glass(kit, name, color, glow=0.0):
    """Window glass that lets shadow rays through (Transparent BSDF) so the sun still casts shafts,
    plus a faint diffuse layer so the panes read as glass when seen against the sky."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    clear = nt.nodes.new('ShaderNodeBsdfTransparent')
    clear.inputs['Color'].default_value = kit.color(color)
    tint = nt.nodes.new('ShaderNodeEmission')
    tint.inputs['Color'].default_value = kit.color(color)
    tint.inputs['Strength'].default_value = glow
    add = nt.nodes.new('ShaderNodeAddShader')
    nt.links.new(clear.outputs[0], add.inputs[0])
    nt.links.new(tint.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs['Surface'])
    return mat


# ============================================================================= parts
def clustered_pier(kit, name, x, y, scale, mat, cap_mat, col):
    """A pier of a core plus eight attached shafts: the outline is the union of circles,
    sampled by angle, so the shafts meet the core in crisp re-entrant angles."""
    core = 0.65 * scale
    shafts = [(core, a * 90, 0.24 * scale) for a in range(4)] + [(core * 1.1, 45 + a * 90, 0.13 * scale) for a in range(4)]
    outline = []
    for i in range(160):
        th = 2 * math.pi * i / 160
        d = Vector((math.cos(th), math.sin(th)))
        best = core
        for dist, ang, r in shafts:
            c = Vector((math.cos(math.radians(ang)), math.sin(math.radians(ang)))) * dist
            dc = d.dot(c)
            disc = r * r - c.length_squared + dc * dc
            if disc >= 0:
                best = max(best, dc + math.sqrt(disc))
        outline.append((best * d.x, best * d.y))
    shaft = kit.extrude(name, outline, ARCADE_SPRING - 1.35, mat, location=(x, y, 0.75), collection=col)
    for p in shaft.data.polygons:
        p.use_smooth = True
    shaft.data.set_sharp_from_angle(angle=math.radians(50))
    # Base: octagonal plinth, a hollow-and-torus moulding (attic base), then the shaft.
    plinth = kit.cylinder(f'{name} plinth', 1.2 * scale, 0.5, (x, y, 0.25), mat, segments=8, bevel=0.03,
                          smooth=False, collection=col)
    base = kit.lathe(f'{name} base', [(0, 0), (1.05 * scale, 0), (1.05 * scale, .08), (.98 * scale, .16),
                                      (.92 * scale, .2), (.95 * scale, .27), (0, .27)],
                     material=mat, location=(x, y, 0.5), collection=col, segments=40)
    # Capital: a crocket-less bell flaring to an octagonal abacus at the arcade springing.
    bell = kit.lathe(f'{name} capital', [(0, 0), (.95 * scale, 0), (.98 * scale, .08), (1.08 * scale, .35),
                                         (1.22 * scale, .52), (1.25 * scale, .58), (0, .58)],
                     material=cap_mat, location=(x, y, ARCADE_SPRING - 0.6), collection=col, segments=48)
    abacus = kit.cylinder(f'{name} abacus', 1.34 * scale, 0.14, (x, y, ARCADE_SPRING - 0.05), cap_mat,
                          segments=8, bevel=0.025, smooth=False, collection=col)
    abacus.rotation_euler.z = math.radians(22.5)
    return shaft


def groin_vault(kit, name, cx, cy, hx, hy, spring, rise, web_mat, rib_mat, col, edges='xy', boss=None):
    """Quadripartite vault: the web is max() of two pointed barrels, so the groins fall exactly where
    the barrels meet. Diagonal ribs follow those groins (found with pointed_offset); edge ribs follow
    the barrels' own arches. Ribs hang a little below the web so they read as structure."""
    nx, ny = 44, 28
    verts, faces = [], []
    for j in range(ny + 1):
        for i in range(nx + 1):
            x, y = -hx + 2 * hx * i / nx, -hy + 2 * hy * j / ny
            verts.append((cx + x, cy + y, spring + max(pointed(x, hx, rise), pointed(y, hy, rise))))
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append((a, a + nx + 1, a + nx + 2, a + 1))   # normals face down into the room
    web = kit.mesh(name, verts, faces, web_mat, collection=col)
    for p in web.data.polygons:
        p.use_smooth = True
    web.data.set_sharp_from_angle(angle=math.radians(25))
    kit.solidify(web, 0.35, offset=-1.0)
    ribs = []
    n = 26
    for s in (1, -1):    # two diagonals
        pts = []
        for k in range(n + 1):
            x = -hx + 2 * hx * k / n
            z = pointed(x, hx, rise)
            u = pointed_offset(z, hy, rise)
            pts.append((cx + x, cy + s * math.copysign(u, x), spring + z - 0.12))
        ribs.append(kit.tube(f'{name} diagonal rib', pts, 0.16, rib_mat, collection=col, resolution=8))
    if 'y' in edges:     # arches across x at the y edges (transverse arches in the nave)
        for ey in (-hy, hy):
            pts = [(cx - hx + 2 * hx * k / n, cy + ey, spring + pointed(-hx + 2 * hx * k / n, hx, rise) - 0.1)
                   for k in range(n + 1)]
            ribs.append(kit.tube(f'{name} transverse rib', pts, 0.21, rib_mat, collection=col, resolution=8))
    if 'x' in edges:     # wall ribs (formerets) along the lunettes
        for ex in (-hx, hx):
            pts = [(cx + ex * 0.985, cy - hy + 2 * hy * k / n, spring + pointed(-hy + 2 * hy * k / n, hy, rise) - 0.05)
                   for k in range(n + 1)]
            ribs.append(kit.tube(f'{name} wall rib', pts, 0.11, rib_mat, collection=col, resolution=8))
    if boss:
        b = kit.ico(f'{name} boss', 0.34, (cx, cy, spring + rise - 0.2), boss, subdivisions=2, collection=col)
        b.scale = (1, 1, 0.7)
        kit.displace(b, 0.06, 0.15)
    return web, ribs


def gable_roof(kit, name, axis, centre, half, a0, a1, eave, rise, mat):
    """Steep pitched roof: a triangular prism along `axis` ('y' or 'x') from a0 to a1."""
    prof = [(-half, eave), (half, eave), (0.0, eave + rise)]

    def at(u, z, a):
        return (centre + u, a, z) if axis == 'y' else (a, centre + u, z)
    verts = [at(u, z, a0) for u, z in prof] + [at(u, z, a1) for u, z in prof]
    faces = [(0, 2, 1), (3, 4, 5), (0, 1, 4, 3), (1, 2, 5, 4), (2, 0, 3, 5)]
    roof = kit.mesh(name, verts, faces, mat, collection='Exterior')
    bm = bmesh.new()                       # recalc normals so the prism is closed and outward
    bm.from_mesh(roof.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(roof.data)
    bm.free()
    return roof


def chair(kit, name, wood, rush):
    """Rush-seated church chair (the rows give the nave human scale)."""
    bm = bmesh.new()

    def part(size, loc):
        r = bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=size, verts=r['verts'])
        bmesh.ops.translate(bm, vec=loc, verts=r['verts'])
    for sx in (-1, 1):
        part((0.035, 0.035, 0.46), (sx * 0.19, 0.18, 0.23))          # front legs
        part((0.035, 0.035, 0.92), (sx * 0.19, -0.19, 0.46))         # back legs run up as posts
        part((0.02, 0.36, 0.02), (sx * 0.19, 0.0, 0.14))             # side stretchers
    part((0.36, 0.02, 0.02), (0, 0.18, 0.16))
    for z in (0.62, 0.8):
        part((0.38, 0.025, 0.06), (0, -0.19, z))                     # back slats
    part((0.38, 0.02, 0.02), (0, -0.05, 0.86))                       # kneeler rail on the back
    frame = bm_object(kit, name, bm, wood, 'Furniture')
    seat = kit.box(f'{name} seat', (0.4, 0.4, 0.035), (0, 0, 0.465), rush, bevel=0.01, collection='Furniture')
    return frame, seat


# ============================================================================= build
def build(kit):
    kit.note('Gothic nave: 8 nave bays, crossing with transepts, 2 choir bays; sun at '
             f'{SUN_ELEVATION} deg elevation from the south-east')

    # --- materials: one scanned ashlar, tinted differently for walls, carved work and vault webs
    wall = stone_material(kit, 'Limestone ashlar', '#E9DCC6', 0.45)
    carved = stone_material(kit, 'Dressed limestone (piers, ribs)', '#E3D6C0', 0.8)
    web = stone_material(kit, 'Vault web limestone', '#EFE6D6', 0.35)
    floor = kit.textured('Worn flagstone floor', FLOOR, scale=0.32, bump=0.8, tint='#CFC6B8')
    boss = kit.material('Painted boss', '#B08A3E', roughness=0.35, metallic=0.6)
    clear = leaded_glass(kit, 'Grisaille glass', '#FFF0D8', glow=0.02)
    blue = leaded_glass(kit, 'Blue stained glass', '#2F57C8', glow=0.6)
    ruby = leaded_glass(kit, 'Ruby stained glass', '#C8302C', glow=0.6)
    wood = kit.procedural('Oak chairs', 'wood', colors=['#3A2414', '#5A3A20', '#6E4A2A'], scale=6.0)
    rush = kit.procedural('Rush seats', 'fabric', colors=['#7A6238', '#8E7444', '#A0864F'], scale=0.4)
    iron = kit.material('Wrought iron', '#1C1B1A', roughness=0.55, metallic=0.8)

    kit.plane('Nave floor', (60, 80), (0, 36, 0), floor, ground=True)

    # --- walls: long slabs with every opening cut by one boolean per wall (EXACT solver)
    for side in (-1, 1):
        tag = 'south' if side > 0 else 'north'
        nave_wall = kit.box(f'Nave wall {tag}', (WALL, EAST + 1, 33), (side * PIER_X, (EAST - 1) / 2, 16.5), wall)
        cut = bmesh.new()
        glass = bmesh.new()
        for i in range(int(EAST / BAY)):
            y0 = i * BAY
            ym = y0 + BAY / 2

            def place(u, z, w, ym=ym):
                return (side * (NAVE_HALF - 0.4 + w * (WALL + 0.8)), ym + u, z)

            def pane(u, z, w, ym=ym):
                return (side * (PIER_X + 0.1), ym + u, z)
            if CROSSING[0] <= y0 < CROSSING[1]:
                if y0 == CROSSING[0]:   # one great arch per side opens the crossing into a transept
                    def big(u, z, w):
                        return (side * (NAVE_HALF - 0.4 + w * (WALL + 0.8)), sum(CROSSING) / 2 + u, z)
                    add_prism(cut, lancet(10.2, -1, 14.0, 8.9, 28), big)
                continue
            add_prism(cut, lancet(ARCADE_SPAN, -1, ARCADE_SPRING, 4.2), place)
            for k in range(4):                          # triforium: four small lancets
                u = (k - 1.5) * 1.1
                add_prism(cut, [(a + u, b) for a, b in lancet(0.85, TRIFORIUM[0], TRIFORIUM[1], 0.75, 10)], place)
            for u in (-0.95, 0.95):                     # clerestory: paired lancets...
                outline = [(a + u, b) for a, b in lancet(1.35, CLERESTORY[0], CLERESTORY[1], 1.3)]
                add_prism(cut, outline, place)
                add_face(glass, outline, pane)
            add_prism(cut, circle(0, 28.0, 0.62), place)  # ...under an oculus (plate tracery)
            add_face(glass, circle(0, 28.0, 0.62), pane)
        cutter = bm_object(kit, f'Nave wall {tag} openings', cut, None, 'Cutters')
        kit.boolean(nave_wall, cutter)
        bm_object(kit, f'Clerestory glass {tag}', glass, clear, 'Glass')

        # Aisle outer wall with a tall lancet per bay; it stops at the transept.
        for y_a, y_b in ((-1, CROSSING[0]), (CROSSING[1], EAST)):
            aw = kit.box(f'Aisle wall {tag} {y_a:.0f}', (WALL, y_b - y_a, 15), (side * (AISLE_OUT + WALL / 2), (y_a + y_b) / 2, 7.5), wall)
            cut = bmesh.new()
            glass = bmesh.new()
            for i in range(int(y_a // BAY) + (1 if y_a < 0 else 0), int(y_b // BAY)):
                ym = i * BAY + BAY / 2
                if ym < y_a or ym > y_b:
                    continue
                outline = lancet(2.0, 2.6, 7.6, 1.9)
                add_prism(cut, outline, lambda u, z, w, ym=ym: (side * (AISLE_OUT - 0.4 + w * 1.8), ym + u, z))
                add_face(glass, outline, lambda u, z, w, ym=ym: (side * (AISLE_OUT + 0.5), ym + u, z))
            kit.boolean(aw, bm_object(kit, f'Aisle wall {tag} openings {y_a:.0f}', cut, None, 'Cutters'))
            bm_object(kit, f'Aisle glass {tag} {y_a:.0f}', glass, clear, 'Glass')
            kit.box(f'Aisle roof {tag} {y_a:.0f}', (AISLE_OUT + WALL - PIER_X - WALL / 2, y_b - y_a, 0.3),
                    (side * (PIER_X + WALL / 2 + (AISLE_OUT + WALL - PIER_X - WALL / 2) / 2), (y_a + y_b) / 2, 14.15), wall)
            # Triforium passage: a dark wall-passage behind the small lancets.
            kit.box(f'Triforium back wall {tag} {y_a:.0f}', (0.5, y_b - y_a, 4.6), (side * 8.25, (y_a + y_b) / 2, 16.5), wall)
            kit.box(f'Triforium ceiling {tag} {y_a:.0f}', (2.5, y_b - y_a, 0.3), (side * 7.25, (y_a + y_b) / 2, 18.65), wall)

        # Transept arm: end wall with three lancets and a rose, side walls, its own vault.
        tx = side * (TRANSEPT_OUT + WALL / 2)
        end = kit.box(f'Transept end wall {tag}', (WALL, 13, 33), (tx, sum(CROSSING) / 2, 16.5), wall)
        cut, glass = bmesh.new(), bmesh.new()
        tm = sum(CROSSING) / 2
        for u in (-2.6, 0, 2.6):
            o = [(a + u, b) for a, b in lancet(2.0, 3.0, 15.5 + (1.5 if u == 0 else 0), 1.9)]
            add_prism(cut, o, lambda a, b, w: (side * (TRANSEPT_OUT - 0.4 + w * 1.8), tm + a, b))
            add_face(glass, o, lambda a, b, w: (side * (TRANSEPT_OUT + 0.5), tm + a, b))
        rose = circle(0, 23.5, 3.2, 48)
        add_prism(cut, rose, lambda a, b, w: (side * (TRANSEPT_OUT - 0.4 + w * 1.8), tm + a, b))
        add_face(glass, rose, lambda a, b, w: (side * (TRANSEPT_OUT + 0.5), tm + a, b))
        kit.boolean(end, bm_object(kit, f'Transept openings {tag}', cut, None, 'Cutters'))
        bm_object(kit, f'Transept glass {tag}', glass, clear, 'Glass')
        for ey in (CROSSING[0] - 0.5, CROSSING[1] + 0.5):
            kit.box(f'Transept side wall {tag} {ey:.0f}', (TRANSEPT_OUT - AISLE_OUT, WALL, 33),
                    (side * (AISLE_OUT + TRANSEPT_OUT) / 2, ey, 16.5), wall)
            kit.box(f'Transept clerestory wall {tag} {ey:.0f}', (AISLE_OUT - PIER_X - WALL / 2, WALL, 19),
                    (side * (PIER_X + WALL / 2 + AISLE_OUT) / 2, ey, 23.8), wall)
        for k in range(3):
            cx = side * (PIER_X + WALL / 2 + 3 + 6 * k)
            groin_vault(kit, f'Transept vault {tag} {k}', cx, tm, 3.0, 6.0, 21.0, 8.0, web, carved, 'Vaults',
                        edges='x', boss=boss)
        kit.box(f'Transept roof {tag}', (TRANSEPT_OUT - PIER_X, 13, 0.4), (side * (PIER_X + TRANSEPT_OUT) / 2, tm, 33.2), wall)

    # East wall: three tall lancets and a rose in stained glass, glowing with the dawn behind it.
    east = kit.box('East wall', (2 * (AISLE_OUT + WALL), WALL, 33), (0, EAST + WALL / 2, 16.5), wall)
    cut, g_blue, g_ruby = bmesh.new(), bmesh.new(), bmesh.new()
    for u in (-2.7, 0, 2.7):
        o = [(a + u, b) for a, b in lancet(2.1, 4.0, 17.0 + (2.0 if u == 0 else 0), 2.0)]
        add_prism(cut, o, lambda a, b, w: (a, EAST - 0.4 + w * 1.8, b))
        add_face(g_blue if u else g_ruby, o, lambda a, b, w: (a, EAST + 0.5, b))
    add_prism(cut, circle(0, 25.5, 3.0, 48), lambda a, b, w: (a, EAST - 0.4 + w * 1.8, b))
    add_face(g_blue, circle(0, 25.5, 3.0, 48), lambda a, b, w: (a, EAST + 0.5, b))
    kit.boolean(east, bm_object(kit, 'East openings', cut, None, 'Cutters'))
    bm_object(kit, 'East glass blue', g_blue, blue, 'Glass')
    bm_object(kit, 'East glass ruby', g_ruby, ruby, 'Glass')
    # Rose tracery: spokes and a hub in front of the glass.
    for k in range(12):
        a = math.radians(30 * k)
        kit.tube(f'Rose spoke {k}', [(0.6 * math.cos(a), EAST + 0.2, 25.5 + 0.6 * math.sin(a)),
                                     (3.0 * math.cos(a), EAST + 0.2, 25.5 + 3.0 * math.sin(a))], 0.07, carved,
                 collection='Tracery')
    kit.torus('Rose hub', 0.6, 0.1, (0, EAST + 0.2, 25.5), carved, rotation=(90, 0, 0), collection='Tracery')
    kit.box('West wall', (2 * (AISLE_OUT + WALL), WALL, 33), (0, -1.5, 16.5), wall)
    kit.box('Nave roof', (2 * PIER_X + WALL, EAST + 2, 0.4), (0, EAST / 2, 33.2), wall)

    # --- exterior: never seen by the shot camera, but the review's three-quarter view sees the whole
    # set. Steep lead roofs, stepped buttresses, flyers and pinnacles make it read as a finished
    # building instead of a shell.
    lead = kit.material('Lead roof', '#5B6064', roughness=0.55, metallic=0.4, bump=(6.0, 0.15))
    half = PIER_X + WALL / 2 + 0.3
    gable_roof(kit, 'Nave roof gable', 'y', 0.0, half, -2.0, EAST + 1.0, 33.4, 11.0, lead)
    gable_roof(kit, 'Transept roof gable', 'x', sum(CROSSING) / 2, 6.8, -TRANSEPT_OUT - 1.0, TRANSEPT_OUT + 1.0,
               33.4, 10.0, lead)
    kit.cone('Crossing fleche', 1.4, 16.0, (0, sum(CROSSING) / 2, 52.0), lead, segments=8, smooth=False)
    for side in (-1, 1):
        for y_a, y_b in ((-1.5, CROSSING[0]), (CROSSING[1], EAST + 0.8)):
            # Aisle lean-to: a sloped slab from the aisle wall head up to under the triforium sill.
            ax0, ax1 = side * (AISLE_OUT + WALL + 0.3), side * 8.5   # meets the triforium back wall
            kit.mesh(f'Aisle lean-to roof {side:+d} {y_a:.0f}',
                     [(ax0, y_a, 15.0), (ax1, y_a, 18.6), (ax1, y_b, 18.6), (ax0, y_b, 15.0)],
                     [(0, 1, 2, 3)] if side < 0 else [(3, 2, 1, 0)], lead)
        for i in range(int(EAST / BAY) + 1):
            y = i * BAY
            if CROSSING[0] < y < CROSSING[1]:
                continue
            bx = side * (AISLE_OUT + WALL + 0.7)
            # Stepped buttress (two offsets) capped by a pinnacle.
            kit.box(f'Buttress {side:+d} {i}', (1.4, 1.3, 13.0), (bx, y, 6.5), wall, bevel=0.05)
            kit.box(f'Buttress upper {side:+d} {i}', (1.0, 1.1, 5.0), (bx - side * 0.2, y, 15.5), wall, bevel=0.05)
            kit.cone(f'Pinnacle {side:+d} {i}', 0.55, 3.2, (bx - side * 0.2, y, 19.6), carved, segments=8,
                     smooth=False)
            # Flying buttress: a quarter-arch strut from the pinnacle pier to the clerestory wall.
            pts = [(bx - side * (0.6 + 7.2 * s), y, 17.2 + 6.0 * math.sin(s * math.pi / 2)) for s in
                   (0, 0.2, 0.4, 0.6, 0.8, 1.0)]
            kit.tube(f'Flying buttress {side:+d} {i}', pts, 0.32, carved, collection='Exterior', resolution=6)

    # --- piers, mouldings, shafts and string courses
    for side in (-1, 1):
        for i in range(int(EAST / BAY) + 1):
            y = i * BAY
            big = y in CROSSING
            clustered_pier(kit, f'Pier {side:+d} {i}', side * PIER_X, y, 1.35 if big else 1.0, carved, carved, 'Piers')
            # Vaulting shaft from the capital to the vault springing, with shaft rings at the string courses.
            sx = side * (NAVE_HALF - 0.2)
            top = VAULT_SPRING if not big else VAULT_SPRING
            kit.cylinder(f'Vaulting shaft {side:+d} {i}', 0.2, top - ARCADE_SPRING, (sx, y, (top + ARCADE_SPRING) / 2),
                         carved, segments=20, collection='Piers')
            for z in (TRIFORIUM[0] - 0.3, CLERESTORY[0] - 0.55):
                kit.torus(f'Shaft ring {side:+d} {i} {z:.0f}', 0.21, 0.06, (sx, y, z), carved, collection='Piers')
            kit.lathe(f'Shaft capital {side:+d} {i}', [(0, 0), (.21, 0), (.24, .12), (.36, .32), (.38, .38), (0, .38)],
                      material=carved, location=(sx, y, VAULT_SPRING - 0.38), collection='Piers', segments=20)
        for i in range(int(EAST / BAY)):
            y0 = i * BAY
            ym = y0 + BAY / 2
            if CROSSING[0] <= y0 < CROSSING[1]:
                continue
            # Two arch orders step the arcade back into the wall; the outer one oversails the cut edge.
            kit.arch(f'Arcade outer order {side:+d} {i}', span=ARCADE_SPAN - 0.25, rise=4.0, depth=WALL + 0.25,
                     thickness=0.42, location=(side * PIER_X, ym, ARCADE_SPRING), rotation=(0, 0, 90), material=carved,
                     collection='Mouldings')
            kit.arch(f'Arcade inner order {side:+d} {i}', span=ARCADE_SPAN - 0.75, rise=3.6, depth=WALL - 0.3,
                     thickness=0.3, location=(side * PIER_X, ym, ARCADE_SPRING), rotation=(0, 0, 90), material=carved,
                     collection='Mouldings')
            for z in (TRIFORIUM[0] - 0.3, CLERESTORY[0] - 0.55):     # string courses
                kit.box(f'String course {side:+d} {i} {z:.0f}', (0.3, BAY - 0.4, 0.26),
                        (side * (NAVE_HALF - 0.1), ym, z), carved, bevel=0.06)
            for k in range(3):                                         # triforium colonnettes
                u = (k - 1) * 1.1
                kit.cylinder(f'Triforium colonnette {side:+d} {i} {k}', 0.08, TRIFORIUM[1] - TRIFORIUM[0],
                             (side * (NAVE_HALF + 0.05), ym + u, sum(TRIFORIUM) / 2), carved, segments=14,
                             collection='Mouldings')
            # Clerestory iron saddle bars (ferramenta) catch the sun and stripe the shafts.
            for u in (-0.95, 0.95):
                for z in (20.6, 22.0, 23.4, 24.8):
                    kit.box(f'Saddle bar {side:+d} {i} {u:+.0f} {z:.0f}', (0.04, 1.4, 0.04),
                            (side * (PIER_X + 0.05), ym + u, z), iron, collection='Tracery')

    # --- vaults: nave and choir bays, crossing, and aisles
    for i in range(int(EAST / BAY)):
        y0 = i * BAY
        if CROSSING[0] <= y0 < CROSSING[1]:
            continue
        groin_vault(kit, f'Nave vault {i}', 0, y0 + BAY / 2, NAVE_HALF, BAY / 2, VAULT_SPRING, VAULT_RISE, web, carved,
                    'Vaults', boss=boss)
        for side in (-1, 1):
            groin_vault(kit, f'Aisle vault {side:+d} {i}', side * (PIER_X + WALL / 2 + 3.0), y0 + BAY / 2, 3.0, 3.0,
                        AISLE_SPRING, AISLE_RISE, web, carved, 'Vaults')
    groin_vault(kit, 'Crossing vault', 0, sum(CROSSING) / 2, NAVE_HALF, 6.0, VAULT_SPRING, VAULT_RISE, web, carved,
                'Vaults', boss=boss)

    # --- furniture: rows of chairs either side of a central aisle (scale and parallax for the dolly)
    # One prototype chair; every other chair is a linked duplicate (cheap, and edits propagate).
    frame, seat = chair(kit, 'Chair', wood, rush)
    seat.parent = None
    rng = kit.rng
    y, row = 5.0, 0
    while y < CROSSING[0] - 5:
        for side in (-1, 1):
            for k in range(7):
                x = side * (1.0 + k * 0.56) + rng.uniform(-0.03, 0.03)
                yy, turn = y + rng.uniform(-0.04, 0.04), rng.uniform(-4, 4)
                if row == 0 and side < 0 and k == 0:      # the prototype itself fills this slot
                    frame.location, seat.location = (x, yy, 0), (x, yy, 0.465)
                    frame.rotation_euler.z = seat.rotation_euler.z = math.radians(turn)
                    continue
                kit.instance(frame, (x, yy, 0), (0, 0, turn), name=f'Chair {row} {side:+d} {k}', collection='Furniture')
                kit.instance(seat, (x, yy, 0.465), (0, 0, turn), name=f'Chair seat {row} {side:+d} {k}',
                             collection='Furniture')
        y += 0.95
        row += 1

    # --- light: physical sky (sun disc off) + a matching sun lamp for crisp shafts + dust
    kit.sky(sun_elevation=SUN_ELEVATION, sun_rotation=90 - SUN_AZIMUTH, strength=0.1, sun_disc=False,
            aerosol=1.6)
    kit.sun(elevation=SUN_ELEVATION, azimuth=SUN_AZIMUTH, strength=SUN_STRENGTH, color=SUN_COLOR, angle=0.6)
    # Soft bounce standing in for sunlit stone across the nave (keeps the shadow side from going black).
    fills = [kit.area('Bounce from sunlit north arcade', (-4.0, 30, 9), (2, 20, 2), 1800, '#FFD6A8', 6.0, size_y=30),
             kit.area('Cool sky bounce off the floor', (0, 20, 0.4), (0, 20, 20), 900, '#C8D6FF', 8.0, size_y=30)]
    for light in fills:
        light.visible_camera = False          # fills light the room but never show as glowing panels...
        light.visible_volume_scatter = False  # ...and never light the haze, so only the sun draws shafts
    kit.haze(HAZE_DENSITY, '#F4E6D2', anisotropy=0.6, size=(2 * TRANSEPT_OUT + 2, EAST + 3, 33),
             location=(0, EAST / 2, 16.5))
    kit.haze(DUST_DENSITY, '#F7EBDA', anisotropy=0.6, size=(2 * AISLE_OUT, EAST + 3, 21),
             location=(0, EAST / 2, 22.5), name='Upper dust')
    kit.render(exposure=EXPOSURE, look='AgX - Medium High Contrast')

    # --- camera: eye level in the central aisle, slow eased dolly toward the crossing
    cam = kit.camera(CAM_START, (0, 70, CAM_START[2]), lens=LENS, shift=(0, SHIFT_Y), clip=(0.1, 300),
                     dof=22.0, fstop=8.0)
    kit.dolly(cam, CAM_START, CAM_END, (0, 70, CAM_START[2]), (0.0, 70, CAM_END[2]), ease_kind='in_out', power=1.8)
