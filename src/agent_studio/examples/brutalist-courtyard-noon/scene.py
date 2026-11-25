"""Brutalist courtyard at noon: a crane shot rising up a deep-recessed concrete facade.

Teaching points
- Architecture at real scale: 3.6 m floors, 4 m bays, 1.5 m deep window recesses, a 4.5 m
  pilotis ground floor. Believable proportions do more for realism than any shader.
- Batch hundreds of boxes into one bmesh per material (fast to build, fast to render) and
  store a per-face random 'tone' attribute so every pour of concrete reads slightly different.
- Hard noon light = a small-angle sun lamp (crisp shadows) + the physical sky with its sun disc
  switched off (blue skylight fill only). The geometry, not the shader, makes the drama.
- Board-formed concrete: a CC0 scan, box-projected, then layered with tone variation, vertical
  rain streaks and damp at the base, the same layering the Laon cathedral stone uses.
"""
import math
import random

import bmesh
import bpy
from mathutils import Vector

# ----------------------------------------------------------------------------- constants
FLOOR_H = 3.6          # storey height (m)
GROUND_H = 4.5         # pilotis ground floor
FLOORS = 5             # upper storeys
RECESS = 1.5           # depth from fin face back to the glass line
FIN_W = 0.45
SLAB_T = 0.55
ATTIC_H = 2.4
COURT_X = 14.0         # half width of the courtyard (east/west facades at +-14 m)
NORTH_Y = 12.0         # north facade front plane
POOL = (0.0, -1.0, 4.6, 18.0)  # centre x, centre y, extent x, extent y: a long pool aimed at the facade
TREE_AT = (4.6, -3.5)

CONCRETE = 'polyhaven:wood_textured_concrete@1k'   # board-formed concrete scan
PAVERS = 'polyhaven:square_concrete_pavers@1k'


# ----------------------------------------------------------------------------- batching
class Boxes:
    """Accumulate axis-aligned boxes into one mesh with a per-face 'tone' attribute."""

    def __init__(self, rng):
        self.verts, self.faces, self.tones, self.rng = [], [], [], rng

    def add(self, x0, x1, y0, y1, z0, z1, tone=None):
        base = len(self.verts)
        for k in range(8):
            self.verts.append(((x0, x1)[k & 1], (y0, y1)[(k >> 1) & 1], (z0, z1)[(k >> 2) & 1]))
        for f in ((0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)):
            self.faces.append(tuple(base + i for i in f))
        t = self.rng.random() if tone is None else tone
        self.tones += [t] * 6

    def build(self, kit, name, material, bevel=0.0, location=(0, 0, 0), rotation=(0, 0, 0)):
        obj = kit.mesh(name, self.verts, self.faces, material, location=location, rotation=rotation)
        attr = obj.data.attributes.new('tone', 'FLOAT', 'FACE')
        attr.data.foreach_set('value', self.tones)
        if bevel:
            kit.bevel(obj, width=bevel, segments=2)
        return obj


# ----------------------------------------------------------------------------- materials
def weathered(kit, mat, streaks=True, saturation=1.0):
    """Multiply a material's base colour by tone variation, rain streaks and damp at the base."""
    nt = mat.node_tree
    bs = kit.bsdf(mat)
    link = next(l for l in nt.links if l.to_socket == bs.inputs['Base Color'])
    src = link.from_socket
    nt.links.remove(link)
    if saturation != 1.0:
        # Scans carry their own colour cast; pull it toward grey so the tint decides.
        hs = nt.nodes.new('ShaderNodeHueSaturation')
        hs.inputs['Saturation'].default_value = saturation
        nt.links.new(src, hs.inputs['Color'])
        src = hs.outputs['Color']

    def mul(a, b_socket, fac=1.0):
        m = nt.nodes.new('ShaderNodeMix')
        m.data_type, m.blend_type = 'RGBA', 'MULTIPLY'
        m.inputs['Factor'].default_value = fac
        nt.links.new(a, m.inputs['A'])
        nt.links.new(b_socket, m.inputs['B'])
        return m.outputs['Result']

    def remap(sock, a, b, c, d):
        r = nt.nodes.new('ShaderNodeMapRange')
        r.inputs['From Min'].default_value, r.inputs['From Max'].default_value = a, b
        r.inputs['To Min'].default_value, r.inputs['To Max'].default_value = c, d
        nt.links.new(sock, r.inputs['Value'])
        return r.outputs['Result']

    # Pour-to-pour tone: each box carries a random 'tone'.
    tone = nt.nodes.new('ShaderNodeAttribute')
    tone.attribute_name = 'tone'
    col = mul(src, remap(tone.outputs['Fac'], 0, 1, 0.82, 1.08))
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    if streaks:
        # Rain streaks: noise stretched 25x along Z in world space.
        mp = nt.nodes.new('ShaderNodeMapping')
        mp.inputs['Scale'].default_value = (1.6, 1.6, 0.06)
        nt.links.new(geo.outputs['Position'], mp.inputs['Vector'])
        n = nt.nodes.new('ShaderNodeTexNoise')
        n.inputs['Scale'].default_value = 3.0
        n.inputs['Detail'].default_value = 6
        nt.links.new(mp.outputs['Vector'], n.inputs['Vector'])
        col = mul(col, remap(n.outputs['Fac'], 0.35, 0.75, 1.05, 0.72))
    # Damp darkening in the first metre above the paving.
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(geo.outputs['Position'], sep.inputs[0])
    col = mul(col, remap(sep.outputs['Z'], 0.0, 1.1, 0.62, 1.0))
    nt.links.new(col, bs.inputs['Base Color'])
    return mat


def glass_material(kit):
    """Dark glazing; some panes show pale curtains behind (picked by the per-face tone)."""
    mat = kit.material('Window glass', '#0E1418', roughness=0.04, coat=1.0)
    nt = mat.node_tree
    tone = nt.nodes.new('ShaderNodeAttribute')
    tone.attribute_name = 'tone'
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.interpolation = 'CONSTANT'
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.0, (0.008, 0.011, 0.014, 1)
    els[1].position, els[1].color = 0.62, (0.30, 0.27, 0.22, 1)
    e = els.new(0.84)
    e.color = (0.05, 0.06, 0.07, 1)
    nt.links.new(tone.outputs['Fac'], ramp.inputs['Fac'])
    bs = kit.bsdf(mat)
    nt.links.new(ramp.outputs['Color'], bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = 0.35   # curtain is matte; the coat gives the glass sheen
    bs.inputs['Coat Roughness'].default_value = 0.02
    return mat


# ----------------------------------------------------------------------------- planting
def trailing_plants(verts, faces, rng, x0, x1, y, z, count=260, drop=1.6):
    """Leaf cards for ivy spilling over a parapet edge at (y, z) between x0 and x1.

    Density falls off with depth below the edge, so the planting reads as hanging strands."""
    for _ in range(count):
        hang = drop * rng.random() ** 1.8
        c = Vector((rng.uniform(x0, x1), y - rng.uniform(0.0, 0.18) + rng.gauss(0, 0.05),
                    z + 0.25 - hang + rng.gauss(0, 0.06)))
        n = Vector((rng.uniform(-0.6, 0.6), -1.0, rng.uniform(-0.3, 0.8))).normalized()
        u = n.cross(Vector((0, 0, 1))).normalized()
        v = n.cross(u)
        s = rng.uniform(0.05, 0.09)
        b = len(verts)
        verts += [c + u * s * 1.5, c + v * s, c - u * s * 1.5, c - v * s]
        faces.append((b, b + 1, b + 2, b + 3))


# ----------------------------------------------------------------------------- facade
def facade(kit, rng, name, width, bays, mats, location, rotation_z):
    # rotation_z is in degrees: kit.mesh takes degrees, like every kit rotation.
    """One facade in local space: front face at y=0, building mass behind (+y).

    Layout: pilotis ground floor, FLOORS storeys of deep cells framed by slabs and fins,
    then a slotted attic band. Returns nothing; builds three batched meshes."""
    conc, glass, frame = Boxes(rng), Boxes(rng), Boxes(rng)
    leaf_v, leaf_f = [], []
    hw = width / 2
    bay = width / bays
    top = GROUND_H + FLOORS * FLOOR_H
    # Mass behind the glass line and the arcade back wall.
    conc.add(-hw, hw, RECESS, RECESS + 12, GROUND_H, top + ATTIC_H)
    conc.add(-hw, hw, 5.0, 17, 0, GROUND_H)
    # Ground floor: square pilotis with a deep, dark arcade behind.
    for i in range(bays + 1):
        x = -hw + i * bay
        conc.add(x - 0.45, x + 0.45, -0.1, 0.8, 0, GROUND_H)
    for i in range(bays):
        x0 = -hw + i * bay + 0.6
        x1 = x0 + bay - 1.2
        glass.add(x0, x1, 4.95, 5.0, 0.1, GROUND_H - 0.6)
        frame.add(x0, x1, 4.9, 4.98, GROUND_H - 0.7, GROUND_H - 0.6)          # transom
        frame.add((x0 + x1) / 2 - 0.04, (x0 + x1) / 2 + 0.04, 4.9, 4.98, 0.1, GROUND_H - 0.6)
    # Soffit over the arcade with a coffer ridge per bay (reads in the reflected light).
    conc.add(-hw, hw, -0.25, 5.0, GROUND_H - 0.1, GROUND_H + SLAB_T)
    for i in range(bays + 1):
        x = -hw + i * bay
        conc.add(x - 0.2, x + 0.2, 0.0, 5.0, GROUND_H - 0.55, GROUND_H)
    # Upper storeys: slabs (with an eyebrow lip on alternate floors), fins, cells.
    for f in range(FLOORS):
        z0 = GROUND_H + f * FLOOR_H
        z1 = z0 + FLOOR_H
        lip = 0.35 if f % 2 == 0 else 0.0
        conc.add(-hw, hw, -0.25, RECESS, z1 - SLAB_T * 0.5, z1 + SLAB_T * 0.5)
        if lip:
            conc.add(-hw, hw, -0.25, 0.0, z1 - SLAB_T * 0.5 - lip, z1)
        for i in range(bays + 1):
            x = -hw + i * bay
            # Fins step forward on the top floor to vary the silhouette.
            front = -0.6 if f == FLOORS - 1 else 0.0
            conc.add(x - FIN_W / 2, x + FIN_W / 2, front, RECESS, z0, z1)
        # Projecting balcony boxes on two floors break the grid (classic brutalist move).
        if f in (1, 3):
            for i in range(bays):
                if (i + f) % 3 == 0:
                    x0 = -hw + i * bay + FIN_W / 2
                    x1 = x0 + bay - FIN_W
                    conc.add(x0 - 0.1, x1 + 0.1, -1.3, 0.0, z0 + 0.0, z0 + 0.35)       # floor
                    conc.add(x0 - 0.1, x1 + 0.1, -1.3, -1.05, z0 + 0.35, z0 + 1.45)    # parapet
                    conc.add(x0 - 0.1, x0 + 0.15, -1.3, 0.0, z0 + 0.35, z0 + 1.45)
                    conc.add(x1 - 0.15, x1 + 0.1, -1.3, 0.0, z0 + 0.35, z0 + 1.45)
                    # Residents' planting: ivy trailing over the parapet adds life and colour.
                    trailing_plants(leaf_v, leaf_f, rng, x0 + 0.1, x1 - 0.1, -1.3, z0 + 1.45,
                                    count=rng.randint(160, 320), drop=rng.uniform(0.8, 2.2))
        for i in range(bays):
            x0 = -hw + i * bay + FIN_W / 2
            x1 = x0 + bay - FIN_W
            sill = z0 + SLAB_T * 0.5
            head = z1 - SLAB_T * 0.5
            conc.add(x0, x1, RECESS - 0.35, RECESS, sill, sill + 0.95)        # upstand
            tone = rng.random()
            glass.add(x0, x1, RECESS - 0.02, RECESS, sill + 0.95, head, tone=tone)
            # Bronze frames: perimeter, a mullion and a transom.
            for (a, b, c, d) in ((x0, x1, head - 0.07, head), (x0, x1, sill + 0.95, sill + 1.02),
                                 (x0, x0 + 0.07, sill + 0.95, head), (x1 - 0.07, x1, sill + 0.95, head)):
                frame.add(a, b, RECESS - 0.1, RECESS - 0.02, c, d)
            mid = (x0 + x1) / 2 + rng.choice((-0.6, 0.0, 0.0, 0.6))
            frame.add(mid - 0.035, mid + 0.035, RECESS - 0.1, RECESS - 0.02, sill + 0.95, head)
            tz = head - 0.75
            frame.add(x0, x1, RECESS - 0.1, RECESS - 0.02, tz - 0.035, tz + 0.035)
    # Attic: a slotted band of narrow blades under a heavy cap.
    z0 = top + SLAB_T * 0.5
    blade, gap = 0.55, 0.28
    x = -hw
    while x < hw - 0.01:
        conc.add(x, min(hw, x + blade), -0.25, 0.4, z0, top + ATTIC_H - 0.5)
        x += blade + gap
    conc.add(-hw, hw, -0.45, 1.2, top + ATTIC_H - 0.5, top + ATTIC_H)
    # Rooftop plant room set back, so the crane end frame has a stepped skyline.
    conc.add(-hw * 0.4, hw * 0.1, 5.0, 10.0, top + ATTIC_H, top + ATTIC_H + 3.0)
    # Roof: rear parapet and a few vent stacks, so the set reads as a whole building.
    back = RECESS + 12
    conc.add(-hw, hw, back - 0.4, back, top + ATTIC_H, top + ATTIC_H + 1.1)
    for k in range(4):
        vx = rng.uniform(-hw + 2, hw - 2)
        conc.add(vx - 0.6, vx + 0.6, back - 4.0, back - 2.8, top + ATTIC_H, top + ATTIC_H + 1.6)
    # Outer (street) face: a quieter grid of narrow slot windows.
    for f in range(FLOORS):
        z = GROUND_H + f * FLOOR_H + 1.0
        x = -hw + 1.2
        while x < hw - 1.6:
            glass.add(x, x + 0.9, back, back + 0.03, z, z + 2.1, tone=0.1)
            x += 2.2
    rot = (0, 0, rotation_z)
    conc.build(kit, f'{name} concrete', mats['concrete'], bevel=0.03, location=location, rotation=rot)
    glass.build(kit, f'{name} glazing', mats['glass'], location=location, rotation=rot)
    frame.build(kit, f'{name} bronze frames', mats['bronze'], bevel=0.008, location=location, rotation=rot)
    if leaf_f:
        kit.mesh(f'{name} balcony ivy', leaf_v, leaf_f, mats['leaf'], location=location, rotation=rot)


# ----------------------------------------------------------------------------- tree
def lone_tree(kit, rng, location, bark, leaf):
    """Recursive branching trunk as tapered frusta in one bmesh, plus ~3000 leaf cards.

    A real canopy is mostly holes: thousands of small leaves give dappled shadow on the
    paving, which no blob canopy can."""
    bm = bmesh.new()
    tips = []

    def limb(p0, p1, r0, r1, sides=7):
        axis = (p1 - p0).normalized()
        ref = Vector((0, 0, 1)) if abs(axis.z) < 0.9 else Vector((1, 0, 0))
        u = axis.cross(ref).normalized()
        v = axis.cross(u)
        rings = []
        for p, r in ((p0, r0), (p1, r1)):
            rings.append([bm.verts.new(p + (u * math.cos(a) + v * math.sin(a)) * r)
                          for a in (2 * math.pi * k / sides for k in range(sides))])
        for k in range(sides):
            bm.faces.new((rings[0][k], rings[0][(k + 1) % sides], rings[1][(k + 1) % sides], rings[1][k]))

    def grow(p, d, length, r, depth):
        end = p + d * length
        limb(p, end, r, r * 0.72)
        if depth == 0:
            tips.append(end)
            return
        for k in range(2 if depth > 2 else 3):
            yaw = rng.uniform(0, 2 * math.pi)
            nd = (d + Vector((math.cos(yaw), math.sin(yaw), 0)) * rng.uniform(0.5, 0.9)
                  + Vector((0, 0, 0.35))).normalized()
            grow(end, nd, length * rng.uniform(0.66, 0.8), r * 0.62, depth - 1)

    base = Vector((0, 0, 0))
    trunk_top = Vector((0.15, -0.1, 2.6))
    limb(base, trunk_top, 0.2, 0.16, sides=10)
    grow(trunk_top, Vector((0.05, 0, 1)).normalized(), 1.8, 0.15, 5)
    me = bpy.data.meshes.new('Tree branches')
    bm.to_mesh(me)
    bm.free()
    branches = bpy.data.objects.new('Tree branches', me)
    branches.location = location
    branches.data.materials.append(bark)
    kit.scene.collection.objects.link(branches)
    for p in branches.data.polygons:
        p.use_smooth = True

    # Leaf cards: small diamonds clustered around every branch tip.
    verts, faces = [], []
    for tip in tips:
        for _ in range(38):
            c = tip + Vector((rng.gauss(0, 0.55), rng.gauss(0, 0.55), rng.gauss(0, 0.4)))
            n = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(0.2, 1))).normalized()
            u = n.cross(Vector((0.3, 0.2, 1)).normalized()).normalized()
            v = n.cross(u)
            s = rng.uniform(0.07, 0.12)
            b = len(verts)
            verts += [c + u * s * 1.6, c + v * s, c - u * s * 1.6, c - v * s]
            faces.append((b, b + 1, b + 2, b + 3))
    leaves = kit.mesh('Tree leaves', verts, faces, leaf, location=location)
    return branches, leaves


# ----------------------------------------------------------------------------- build
def build(kit):
    rng = random.Random(kit.seed)

    # --- materials --------------------------------------------------------------------
    concrete = weathered(kit, kit.textured('Board-formed concrete', CONCRETE, scale=0.45, bump=0.8,
                                           tint='#E4E6E8'), saturation=0.55)
    pavers = weathered(kit, kit.textured('Courtyard pavers', PAVERS, scale=0.33, bump=0.6, tint='#D0D0CC'),
                       streaks=False, saturation=0.3)
    mats = {
        'concrete': concrete,
        'glass': glass_material(kit),
        'bronze': kit.material('Bronze', '#3A2A1C', roughness=0.38, metallic=1.0),
    }
    coping = weathered(kit, kit.procedural('Pool coping', 'concrete', colors=['#9C978D', '#B3AEA3', '#C6C1B6'],
                                           scale=1.5, bump=0.15), streaks=False)
    slate = kit.material('Basin slate', '#141618', roughness=0.6, bump=(18, 0.2))
    water = kit.material('Pool water', '#0A1A1C', roughness=0.015, transmission=1.0, ior=1.333,
                         bump=(0.9, 0.04))
    gravel = kit.procedural('Planter gravel', 'sand', colors=['#5F5A52', '#8B857A', '#A9A295'], scale=2.5,
                            bump=0.5)
    bark = kit.procedural('Tree bark', 'bark', colors=['#2B241E', '#4A4036', '#5E5446'], scale=2.0)
    leaf = kit.material('Leaves', '#3F6B25', roughness=0.55, sheen=0.3)
    # Leaves glow when backlit: mix in a translucent BSDF.
    nt = leaf.node_tree
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    tr = nt.nodes.new('ShaderNodeBsdfTranslucent')
    tr.inputs['Color'].default_value = (0.25, 0.42, 0.05, 1)
    mix = nt.nodes.new('ShaderNodeMixShader')
    mix.inputs['Fac'].default_value = 0.35
    nt.links.new(kit.bsdf(leaf).outputs[0], mix.inputs[1])
    nt.links.new(tr.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    mats['leaf'] = leaf

    # --- architecture -----------------------------------------------------------------
    facade(kit, rng, 'North facade', 2 * COURT_X, 7, mats, (0, NORTH_Y, 0), 0.0)
    span = NORTH_Y + 24.0
    centre_y = NORTH_Y - span / 2
    facade(kit, rng, 'West facade', span, 9, mats, (-COURT_X, centre_y, 0), 90)
    facade(kit, rng, 'East facade', span, 9, mats, (COURT_X, centre_y, 0), -90)

    # --- courtyard floor --------------------------------------------------------------
    kit.box('Courtyard paving', (2 * COURT_X + 12, 60, 0.3), (0, -10, -0.15), pavers, ground=True)

    # Reflecting pool: coping ring, slate basin floor, water 4 cm below the coping.
    px, py, pl, pw = POOL
    c = 0.4
    cop = Boxes(rng)
    cop.add(px - pl / 2 - c, px + pl / 2 + c, py - pw / 2 - c, py - pw / 2, 0, 0.14)
    cop.add(px - pl / 2 - c, px + pl / 2 + c, py + pw / 2, py + pw / 2 + c, 0, 0.14)
    cop.add(px - pl / 2 - c, px - pl / 2, py - pw / 2, py + pw / 2, 0, 0.14)
    cop.add(px + pl / 2, px + pl / 2 + c, py - pw / 2, py + pw / 2, 0, 0.14)
    cop.build(kit, 'Pool coping', coping, bevel=0.015)
    kit.box('Pool basin', (pl, pw, 0.05), (px, py, -0.25), slate)
    kit.box('Pool water', (pl, pw, 0.3), (px, py, -0.07), water)
    # Monolithic benches parallel to the pool on the west side.
    bench = Boxes(rng)
    bench.add(px - 5.8, px - 5.2, py - 7.0, py - 1.5, 0.0, 0.46)
    bench.add(px - 5.8, px - 5.2, py + 1.5, py + 7.0, 0.0, 0.46)
    bench.build(kit, 'Concrete benches', concrete, bevel=0.02)
    # Linear drain grate between pool and facade.
    kit.box('Drain grate', (2 * COURT_X - 2, 0.25, 0.02), (0, NORTH_Y - 1.8, 0.005),
            kit.material('Grate steel', '#2A2B2C', roughness=0.5, metallic=1.0, bump=(60, 0.6)))

    # Planter and lone tree.
    tx, ty = TREE_AT
    planter = Boxes(rng)
    planter.add(tx - 1.8, tx + 1.8, ty - 1.8, ty - 1.5, 0, 0.5)
    planter.add(tx - 1.8, tx + 1.8, ty + 1.5, ty + 1.8, 0, 0.5)
    planter.add(tx - 1.8, tx - 1.5, ty - 1.5, ty + 1.5, 0, 0.5)
    planter.add(tx + 1.5, tx + 1.8, ty - 1.5, ty + 1.5, 0, 0.5)
    planter.build(kit, 'Tree planter', concrete, bevel=0.025)
    kit.box('Planter gravel', (3.0, 3.0, 0.4), (tx, ty, 0.2), gravel)
    lone_tree(kit, rng, (tx, ty, 0.38), bark, leaf)

    # --- light: hard noon sun + blue skylight -----------------------------------------
    # The physical sky is very bright per unit strength; with its disc off it is only fill,
    # so keep its strength tiny or the shadows wash out.
    kit.sky(sun_elevation=60, sun_rotation=235, strength=0.045, sun_disc=False)
    # The sun rakes in 55 degrees off the facade normal so every fin throws a diagonal
    # shadow across its neighbouring cell: the shadows draw the grid.
    kit.sun(elevation=60, azimuth=235, strength=8.0, color='#FFF3E2', angle=0.55)
    # Faint haze so the far facades sit back a touch.
    kit.haze(density=0.0025, color='#DCE6F2', size=(90, 90, 40), location=(0, -5, 18))
    kit.render(look='AgX - Medium High Contrast', exposure=0.55)

    # --- camera: crane from pool level up the north facade ----------------------------
    # Start low at the end of the long pool so the water is a leading line carrying the
    # facade's reflection, the tree on the right; end high, level with the attic.
    cam = kit.camera(location=(-0.8, -12.0, 1.2), target=(0.6, NORTH_Y, 6.5), lens=22)
    kit.dolly(cam, (-0.8, -12.0, 1.2), (-0.6, -7.0, 15.5),
              target_start=(0.6, NORTH_Y, 6.5), target_end=(0.4, NORTH_Y, 18.5), ease_kind='in_out', power=2.2)
