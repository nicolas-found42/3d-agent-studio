"""A spiral of lacquered dominoes toppling on an oak floor, tracked by a low camera.

Teaches
- Real rigid-body dominoes at true scale (48 x 24 x 7.5 mm): Bullet needs small collision
  margins and more substeps per frame for objects this small, or the chain jitters and stalls.
- Laying objects out by arc length on an Archimedean spiral, so the spacing between dominoes
  is constant even as the radius shrinks; the turn pitch exceeds a domino's height so a falling
  turn never knocks into the next one inward.
- Driving the camera from the simulation itself: the script steps the solver once (frame_set),
  measures where the toppling front is on every frame, smooths it, and keys a low tracking
  camera to it. The studio's bake reproduces the same deterministic result.
- Practical interior light: a large cool window (area light behind a mullion gobo that throws
  window-bar shadows across the floor) against a warm table lamp, with the room built just
  enough to give the defocused background real shapes.
- A plank floor shader: a brick texture lays out staggered boards, its per-brick colour drives
  tone and grain offset per plank, stretched noise plus a wave texture make the oak grain.
"""
import math

import bmesh
import bpy
from mathutils import Vector

# ---------------------------------------------------------------- constants (metres)
DOMINO = (0.0075, 0.024, 0.048)     # thickness (along travel), width, height
SPACING = 0.030                     # centre-to-centre along the chain (0.62 x height)
R_OUTER, R_INNER = 0.56, 0.15       # spiral radii
PITCH = 0.10                        # distance between turns (> domino height)
FIRST_TILT = 22.0                   # degrees: the first domino is already leaning, it starts the chain
CAM_HEIGHT = 0.075                  # lens height above the floor
CAM_OFFSET = 0.30                   # how far outside the chain the camera rides
ROOM = 2.6                          # half-size of the room


def spiral_points():
    """Positions and travel tangents every SPACING metres along r = R_OUTER - PITCH * theta / tau."""
    k = PITCH / math.tau
    out, theta, s_next, s = [], 0.0, 0.0, 0.0
    prev = Vector((R_OUTER, 0, 0))
    while True:
        r = R_OUTER - k * theta
        if r < R_INNER:
            break
        p = Vector((r * math.cos(theta), r * math.sin(theta), 0))
        s += (p - prev).length
        prev = p
        if s >= s_next:
            tangent = Vector((-r * math.sin(theta) - k * math.cos(theta), r * math.cos(theta) - k * math.sin(theta), 0)).normalized()
            out.append((p, tangent, s))
            s_next += SPACING
        theta += 0.0004
    return out


# ---------------------------------------------------------------- materials
def oak_floor(kit):
    mat = kit.material('Oak floor', '#8A5A33', roughness=0.4, coat=0.25)
    nt, bs = mat.node_tree, kit.bsdf(mat)
    N, L = nt.nodes, nt.links
    coord = N.new('ShaderNodeTexCoord')
    brick = N.new('ShaderNodeTexBrick')
    brick.offset, brick.offset_frequency = 0.37, 1
    brick.inputs['Scale'].default_value = 1.0
    brick.inputs['Brick Width'].default_value = 1.25
    brick.inputs['Row Height'].default_value = 0.14
    brick.inputs['Mortar Size'].default_value = 0.0012
    brick.inputs['Mortar Smooth'].default_value = 0.3
    brick.inputs['Color1'].default_value = (0, 0, 0, 1)
    brick.inputs['Color2'].default_value = (1, 1, 1, 1)
    L.new(coord.outputs['Object'], brick.inputs['Vector'])
    # Per-plank random value offsets the grain so neighbouring boards never match.
    rnd = N.new('ShaderNodeSeparateColor'); L.new(brick.outputs['Color'], rnd.inputs[0])
    sz = N.new('ShaderNodeMath'); sz.operation = 'MULTIPLY'; sz.inputs[1].default_value = 13.0
    L.new(rnd.outputs[0], sz.inputs[0])
    plank_shift = N.new('ShaderNodeCombineXYZ')
    L.new(sz.outputs[0], plank_shift.inputs['Z'])
    offset = N.new('ShaderNodeVectorMath'); offset.operation = 'ADD'
    L.new(coord.outputs['Object'], offset.inputs[0])
    L.new(plank_shift.outputs[0], offset.inputs[1])
    grain_map = N.new('ShaderNodeMapping'); grain_map.inputs['Scale'].default_value = (1.5, 60.0, 4.0)
    L.new(offset.outputs[0], grain_map.inputs['Vector'])
    grain = N.new('ShaderNodeTexNoise'); grain.inputs['Scale'].default_value = 3.0
    grain.inputs['Detail'].default_value = 8; grain.inputs['Distortion'].default_value = 0.6
    L.new(grain_map.outputs['Vector'], grain.inputs['Vector'])
    rings = N.new('ShaderNodeTexWave'); rings.wave_type = 'BANDS'; rings.bands_direction = 'Y'
    rings.inputs['Scale'].default_value = 2.5; rings.inputs['Distortion'].default_value = 6
    rings.inputs['Detail'].default_value = 3
    L.new(grain_map.outputs['Vector'], rings.inputs['Vector'])
    mixg = N.new('ShaderNodeMix'); mixg.data_type = 'FLOAT'; mixg.inputs['Factor'].default_value = 0.45
    L.new(grain.outputs['Fac'], mixg.inputs['A']); L.new(rings.outputs['Fac'], mixg.inputs['B'])
    ramp = N.new('ShaderNodeValToRGB')
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.3, kit.color('#5E3A1E')
    els[1].position, els[1].color = 0.75, kit.color('#B98552')
    mid = els.new(0.55); mid.color = kit.color('#8E6036')
    L.new(mixg.outputs['Result'], ramp.inputs['Fac'])
    # Plank tone: some boards lighter, some darker.
    tone = N.new('ShaderNodeMix'); tone.data_type = 'RGBA'; tone.blend_type = 'MULTIPLY'
    L.new(ramp.outputs['Color'], tone.inputs['A'])
    tr = N.new('ShaderNodeValToRGB')
    tr.color_ramp.elements[0].color = kit.color('#B9AFA4'); tr.color_ramp.elements[1].color = (1, 1, 1, 1)
    L.new(rnd.outputs[1], tr.inputs['Fac'])
    L.new(tr.outputs['Color'], tone.inputs['B'])
    tone.inputs['Factor'].default_value = 1.0
    gap = N.new('ShaderNodeMix'); gap.data_type = 'RGBA'
    L.new(brick.outputs['Fac'], gap.inputs['Factor'])
    L.new(tone.outputs['Result'], gap.inputs['A'])
    gap.inputs['B'].default_value = kit.color('#1E130B')
    L.new(gap.outputs['Result'], bs.inputs['Base Color'])
    bump = N.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.25
    bump.inputs['Distance'].default_value = 0.002
    h = N.new('ShaderNodeMath'); h.operation = 'MULTIPLY_ADD'; h.inputs[1].default_value = -1.0
    L.new(brick.outputs['Fac'], h.inputs[0]); L.new(mixg.outputs['Result'], h.inputs[2])
    L.new(h.outputs[0], bump.inputs['Height'])
    L.new(bump.outputs['Normal'], bs.inputs['Normal'])
    return mat


def lacquer(kit, name, color):
    """Glossy lacquered wood: coloured base under a hard, clear coat."""
    mat = kit.material(name, color, roughness=0.32, coat=1.0, bump=(900.0, 0.02))
    bs = kit.bsdf(mat)
    bs.inputs['Coat Roughness'].default_value = 0.04
    return mat


# ---------------------------------------------------------------- room
def build_room(kit):
    plaster = kit.material('Wall plaster', '#D8CFC2', roughness=0.9, bump=(40.0, 0.05))
    trim = kit.material('Painted trim', '#EFEAE2', roughness=0.35, coat=0.2)
    fabric = kit.procedural('Armchair fabric', 'fabric', colors=['#5C3A2E', '#6E4536', '#7F5241'], scale=1.0)
    for name, loc, size in (('Wall north', (0, ROOM, 1.3), (2 * ROOM, 0.1, 2.6)), ('Wall east', (ROOM, 0, 1.3), (0.1, 2 * ROOM, 2.6)),
                            ('Wall south', (0, -ROOM, 1.3), (2 * ROOM, 0.1, 2.6))):
        kit.box(name, size, loc, plaster, collection='Room')
    # West wall with a window opening: wall pieces around it, a frame, glazing bars and sky.
    for name, loc, size in (('Wall west low', (-ROOM, 0, 0.35), (0.1, 2 * ROOM, 0.7)),
                            ('Wall west high', (-ROOM, 0, 2.35), (0.1, 2 * ROOM, 0.5)),
                            ('Wall west left', (-ROOM, -1.55, 1.4), (0.1, 2.1, 1.4)),
                            ('Wall west right', (-ROOM, 1.55, 1.4), (0.1, 2.1, 1.4))):
        kit.box(name, size, loc, plaster, collection='Room')
    sky = kit.emissive('Window daylight', '#DCE8FF', 4.0)
    kit.box('Window sky', (0.02, 1.0, 1.4), (-ROOM - 0.6, 0, 1.4), sky, collection='Room')
    for z in (0.7, 1.4, 2.1):
        kit.box('Window bar', (0.06, 1.0, 0.05), (-ROOM, 0, z), trim, collection='Room')
    for y in (-0.5, 0, 0.5):
        kit.box('Window bar', (0.06, 0.05, 1.4), (-ROOM, y, 1.4), trim, collection='Room')
    kit.box('Window sill', (0.25, 1.15, 0.04), (-ROOM + 0.08, 0, 0.69), trim, bevel=0.008, collection='Room')
    for name, loc, size in (('Skirting north', (0, ROOM - 0.06, 0.06), (2 * ROOM, 0.02, 0.12)),
                            ('Skirting east', (ROOM - 0.06, 0, 0.06), (0.02, 2 * ROOM, 0.12)),
                            ('Skirting south', (0, -ROOM + 0.06, 0.06), (2 * ROOM, 0.02, 0.12)),
                            ('Skirting west', (-ROOM + 0.06, 0, 0.06), (0.02, 2 * ROOM, 0.12))):
        kit.box(name, size, loc, trim, bevel=0.004, collection='Room')
    # Side table with a warm lamp in the north-east corner.
    walnut = kit.procedural('Walnut', 'wood', colors=['#3B2416', '#5A3923', '#704A2E'], scale=4.0)
    tx, ty = 1.7, 1.75
    kit.cylinder('Side table top', 0.3, 0.035, (tx, ty, 0.55), walnut, bevel=0.008, collection='Room')
    for a in range(3):
        ang = math.tau * a / 3
        kit.cylinder('Side table leg', 0.018, 0.55, (tx + 0.2 * math.cos(ang), ty + 0.2 * math.sin(ang), 0.27), walnut,
                     segments=12, collection='Room')
    brass = kit.material('Lamp brass', '#B8903F', roughness=0.25, metallic=1.0)
    kit.lathe('Lamp base', [(0, 0), (0.08, 0), (0.08, 0.02), (0.03, 0.05), (0.015, 0.06), (0.012, 0.35), (0, 0.35)], 32, brass,
              location=(tx, ty, 0.568), collection='Room')
    shade = kit.material('Lamp shade', '#F3DDB4', roughness=0.8, emission='#FFB866', emission_strength=1.5,
                         transmission=0.0, subsurface=0.4)
    kit.lathe('Lamp shade', [(0.17, 0), (0.12, 0.2)], 48, shade, location=(tx, ty, 0.82), collection='Room')
    kit.point('Table lamp bulb', (tx, ty, 0.9), power=55, color='#FFAA55', radius=0.04)
    # Armchair in the south-east corner: cushions as bevelled boxes.
    ax, ay = 1.75, -1.6
    for name, loc, size in (('Armchair seat', (ax, ay, 0.3), (0.8, 0.8, 0.22)), ('Armchair back', (ax + 0.32, ay, 0.62), (0.18, 0.8, 0.6)),
                            ('Armchair arm L', (ax, ay - 0.42, 0.45), (0.8, 0.16, 0.42)), ('Armchair arm R', (ax, ay + 0.42, 0.45), (0.8, 0.16, 0.42))):
        kit.subdivide(kit.box(name, size, loc, fabric, bevel=0.05, collection='Room'), 1)
    for dx in (-0.32, 0.32):
        for dy in (-0.38, 0.38):
            kit.cylinder('Armchair foot', 0.025, 0.19, (ax + dx, ay + dy, 0.095), walnut, segments=12, collection='Room')


# ---------------------------------------------------------------- build
def build(kit):
    scene = kit.scene
    floor = kit.box('Oak floor', (2 * ROOM, 2 * ROOM, 0.04), (0, 0, -0.02), oak_floor(kit), ground=True)
    kit.rigid_body(floor, 'PASSIVE', shape='BOX', friction=0.6, bounce=0.0)
    rbw = scene.rigidbody_world
    rbw.substeps_per_frame = 12          # ~360 Hz at 30 fps: small dominoes need short steps
    rbw.solver_iterations = 20
    floor.rigid_body.use_margin, floor.rigid_body.collision_margin = True, 0.0005

    # Prototype domino with bevelled edges baked into the mesh (instances share it).
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(DOMINO), verts=bm.verts)
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.0012, segments=3, affect='EDGES', profile=0.5)
    me = bpy.data.meshes.new('Domino')
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(None)

    # A rainbow of lacquers cycling along the chain in bands of eight.
    palette = ['#C8202F', '#E5562A', '#F2A428', '#E9D24A', '#4FA84A', '#1E8C7E', '#2A6FC2', '#3B3FA0', '#7A3E9D', '#C23A7A']
    mats = [lacquer(kit, f'Lacquer {i}', c) for i, c in enumerate(palette)]
    chain = spiral_points()
    dominoes = []
    for i, (p, tng, s) in enumerate(chain):
        d = bpy.data.objects.new(f'Domino {i:03d}', me)
        kit._link(d, 'Dominoes')
        d.material_slots[0].link = 'OBJECT'
        d.material_slots[0].material = mats[(i // 8) % len(mats)]
        heading = math.atan2(tng.y, tng.x)
        tilt = math.radians(FIRST_TILT) if i == 0 else 0.0
        # When tilted, rest on the leading bottom edge: raise and shift the centre accordingly.
        lift = DOMINO[2] / 2 * math.cos(tilt) + DOMINO[0] / 2 * math.sin(tilt)
        shift = DOMINO[2] / 2 * math.sin(tilt) - DOMINO[0] / 2 * (1 - math.cos(tilt))
        d.location = p + tng * shift + Vector((0, 0, lift + 0.0002))
        d.rotation_euler = (0, tilt, heading)
        kit.rigid_body(d, 'ACTIVE', mass=0.012, shape='BOX', friction=0.45, bounce=0.05)
        d.rigid_body.use_margin, d.rigid_body.collision_margin = True, 0.0003
        d.rigid_body.linear_damping, d.rigid_body.angular_damping = 0.04, 0.1
        dominoes.append(d)
    kit.note(f'{len(dominoes)} dominoes over {chain[-1][2]:.2f} m of spiral')

    build_room(kit)

    # --- light: cool window key through glazing bars, warm lamp, soft room fill ------------
    kit.area('Window light', (-ROOM - 0.4, 0, 1.4), (0.2, 0, 0), power=1400, color='#DCE8FF', size=1.0, size_y=1.4)
    kit.world('#2B2622', strength=0.25)

    # --- measure the toppling front by stepping the solver once ---------------------------
    fronts = []
    i_front = 0
    for f in range(1, kit.frames + 1):
        scene.frame_set(f)
        while i_front + 1 < len(dominoes) and dominoes[i_front + 1].matrix_world.col[2].z < math.cos(math.radians(35)):
            i_front += 1
        fronts.append(chain[i_front][2])
    scene.frame_set(1)
    rbw.solver_iterations = rbw.solver_iterations      # touch the world so the studio re-bakes from frame 1
    kit.note(f'front reached domino {i_front} of {len(dominoes)}')
    # Smooth the front (it advances in steps of one domino) with a wide moving average.
    smooth = []
    for k in range(len(fronts)):
        win = fronts[max(0, k - 8): k + 9]
        smooth.append(sum(win) / len(win))
    total = chain[-1][2]

    def at(s):
        idx = min(len(chain) - 1, max(0, int(s / SPACING)))
        return chain[idx][0], chain[idx][1]

    cam = kit.camera((0, -1, CAM_HEIGHT), (0, 0, 0.02), lens=40, clip=(0.01, 50), dof=0.3, fstop=3.2)
    tgt = kit.target_of(cam)
    for f in range(1, kit.frames + 1):
        s = min(total, smooth[f - 1])
        p, tng = at(max(0.0, s - 0.10))
        outward = Vector((p.x, p.y, 0)).normalized()
        cam.location = p + outward * CAM_OFFSET + Vector((0, 0, CAM_HEIGHT))
        q, _ = at(min(total, s + 0.03))
        tgt.location = q + Vector((0, 0, 0.018))
        cam.data.dof.focus_distance = (cam.location - tgt.location).length
        cam.keyframe_insert('location', frame=f)
        tgt.keyframe_insert('location', frame=f)
        cam.data.dof.keyframe_insert('focus_distance', frame=f)
    kit.render(exposure=0.3, look='AgX - Medium High Contrast', motion_blur=True, shutter=0.5)
