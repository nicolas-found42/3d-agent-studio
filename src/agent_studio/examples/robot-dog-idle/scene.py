"""Robot dog idle: a cel-shaded cartoon robot dog sitting on a checkered floor, as a seamless loop.

Teaches:
- a hand-built EEVEE cel shader with colored shadow bands, a thresholded specular lobe, and a
  lower-weight physically lit layer that reveals bevels and cast shadows;
- the same cel shader driven by a procedural checker that fades into the backdrop colour with
  distance, so a curved cyclorama floor has no horizon line;
- inverted-hull ink outlines with a back-face-culled emission material (EEVEE-safe);
- a character rig made only of empties and parenting: root -> torso (breathing) and head pivot
  (tilt), tail pivot (wag), ear pivots (lagging wobble);
- loop-safe secondary motion: kit.wave with whole cycles, a blink keyed mid-shot, and a camera
  arc that swings out and back on one sine so frame kit.frames + 1 equals frame 1.
"""
import math

import bmesh
import bpy
from mathutils import Vector

# ----------------------------------------------------------------------------- palette
BODY = '#F3EEE4'        # warm off-white plastic shell
ACCENT = '#FF7A3D'      # tangerine: ear tips, collar, paw pads, chin
JOINT = '#59606E'       # graphite joints and neck
SCREEN = '#1B2140'      # dark navy face screen
EYE = '#62F3FF'         # glowing cyan eyes
BLUSH = '#FF8FB0'
CHECK_A, CHECK_B = '#516893', '#BBC4DF'   # powder-blue tiles on a dark studio floor
BACKDROP = '#35435F'    # a muted indigo sweep makes the warm plastic and cyan face stand out
INK = '#0C1025'         # deep blue ink

# Shadow tints: the base colour is multiplied by these, darkest band first. A violet-blue cast in
# the shadows is what makes cel shading look illustrated instead of simply darker.
SHADOW_TINT = '#59689F'
MID_TINT = '#B7C8EA'

# ----------------------------------------------------------------------------- dimensions (metres)
# A small dog-sized robot: about 0.75 m to the ear tips when sitting.
TORSO = (0.30, 0.42, 0.24)          # width, length, height of the boxy body
TORSO_PITCH = -36.0                 # sitting: chest raised, rump down
HEAD = (0.32, 0.25, 0.25)
HEAD_PIVOT = Vector((0.0, -0.12, 0.50))
FACING = -35.0                      # three-quarter pose: face, flank and tail all read
BALL_XY, BOWL_XY = (0.41, -0.33), (-0.40, 0.06)

# ----------------------------------------------------------------------------- motion
BREATHS = 2          # breaths per loop
WAGS = 6             # tail wags per loop (1.2 Hz at 5 s)
TILT_DEG = 16.0      # head tilt at its peak
ARC_CENTER = 3.0     # camera azimuth around the dog, degrees (0 = straight in front)
ARC_SWING = 21.0     # +/- swing of the slow arc


def sock(sockets, identifier):
    """Pick a node socket by identifier (Mix nodes have several sockets named 'A')."""
    return next(s for s in sockets if s.identifier == identifier)


def cel_shader(kit, name, color=None, spec=0.0, spec_size=0.58, physical=0.52):
    """Return the material and both base-color sockets for callers that supply a texture."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    diffuse = nt.nodes.new('ShaderNodeBsdfDiffuse')
    diffuse.inputs['Color'].default_value = (1, 1, 1, 1)
    light = nt.nodes.new('ShaderNodeShaderToRGB')
    nt.links.new(diffuse.outputs[0], light.inputs[0])
    # Separate the side planes with colored shadows and hold a thin band through each bevel.
    bands = kit.color_ramp(nt, [(0.0, SHADOW_TINT), (0.15, MID_TINT), (0.39, '#FFFFFF')], 'CONSTANT')
    nt.links.new(light.outputs['Color'], bands.inputs['Fac'])
    tint = nt.nodes.new('ShaderNodeMix')
    tint.data_type, tint.blend_type = 'RGBA', 'MULTIPLY'
    sock(tint.inputs, 'Factor_Float').default_value = 1.0
    base = sock(tint.inputs, 'A_Color')
    base.default_value = kit.color(color or '#FFFFFF')
    nt.links.new(bands.outputs['Color'], sock(tint.inputs, 'B_Color'))
    shaded = sock(tint.outputs, 'Result_Color')
    if spec:
        # Toon specular: a sharp-thresholded glossy highlight added on top.
        gloss = nt.nodes.new('ShaderNodeBsdfGlossy')
        gloss.inputs['Roughness'].default_value = 0.22
        g_rgb = nt.nodes.new('ShaderNodeShaderToRGB')
        nt.links.new(gloss.outputs[0], g_rgb.inputs[0])
        g_band = kit.color_ramp(nt, [(0.0, '#000000'), (spec_size, '#FFFFFF')], 'CONSTANT')
        nt.links.new(g_rgb.outputs['Color'], g_band.inputs['Fac'])
        add = nt.nodes.new('ShaderNodeMix')
        add.data_type, add.blend_type = 'RGBA', 'ADD'
        sock(add.inputs, 'Factor_Float').default_value = spec
        nt.links.new(shaded, sock(add.inputs, 'A_Color'))
        nt.links.new(g_band.outputs['Color'], sock(add.inputs, 'B_Color'))
        shaded = sock(add.outputs, 'Result_Color')
    em = nt.nodes.new('ShaderNodeEmission')
    nt.links.new(shaded, em.inputs['Color'])
    plastic = nt.nodes.new('ShaderNodeBsdfPrincipled')
    plastic.inputs['Base Color'].default_value = base.default_value[:]
    plastic.inputs['Roughness'].default_value = 0.31 if spec else 0.78
    plastic.inputs['Coat Weight'].default_value = spec * 0.38
    layer = nt.nodes.new('ShaderNodeMixShader')
    layer.inputs[0].default_value = physical
    nt.links.new(em.outputs[0], layer.inputs[1])
    nt.links.new(plastic.outputs[0], layer.inputs[2])
    nt.links.new(layer.outputs[0], out.inputs['Surface'])
    mat.diffuse_color = kit.color(color or '#FFFFFF')
    return mat, (base, plastic.inputs['Base Color'])


def radial_distance(tree, vector, centre, scale):
    offset = tree.nodes.new('ShaderNodeVectorMath')
    offset.operation = 'SUBTRACT'
    tree.links.new(vector, offset.inputs[0])
    offset.inputs[1].default_value = centre
    scaled = tree.nodes.new('ShaderNodeVectorMath')
    scaled.operation = 'MULTIPLY'
    tree.links.new(offset.outputs['Vector'], scaled.inputs[0])
    scaled.inputs[1].default_value = scale
    radius = tree.nodes.new('ShaderNodeVectorMath')
    radius.operation = 'LENGTH'
    tree.links.new(scaled.outputs['Vector'], radius.inputs[0])
    return radius.outputs['Value']


def build(kit):
    # EEVEE renders the Shader-to-RGB trick; 'Standard' keeps the palette exact (AgX would
    # desaturate the flat colours).
    kit.render(engine='EEVEE', view_transform='Standard', motion_blur=False)
    kit.glow(strength=0.19, size=0.2, threshold=1.12)
    rng = kit.rng

    # -------------------------------------------------------------------- materials
    cache = {}

    def cel(color, spec=0.0):
        key = (color, spec)
        if key not in cache:
            cache[key] = cel_shader(kit, f'Cel {color}', color, spec)[0]
        return cache[key]

    ink = kit.emissive('Ink', INK, 1.0)
    ink.use_backface_culling = True     # only the flipped hull's rim behind the silhouette shows

    def outline(obj, thickness=0.007):
        """Inverted hull: an outward, normal-flipped solidify shell drawn in ink."""
        obj.data.materials.append(ink)
        m = obj.modifiers.new('Ink outline', 'SOLIDIFY')
        m.thickness, m.offset, m.use_flip_normals = thickness * 1.48, 1.0, True
        m.material_offset = len(obj.data.materials) - 1
        return obj

    def smooth(obj):
        for p in obj.data.polygons:
            p.use_smooth = True
        return obj

    def rounded_box(name, size, loc, color, bevel, rot=(0, 0, 0), spec=0.35, line=0.011):
        """Bevelled box with smooth shading: the 'toy plastic' primitive of this character."""
        obj = kit.box(name, size, loc, cel(color, spec), rotation=rot)
        m = obj.modifiers.new('Round', 'BEVEL')
        m.width, m.segments, m.limit_method = bevel, 4, 'ANGLE'
        m.harden_normals = True      # flat faces stay flat under smooth shading: clean cel bands
        smooth(obj)
        return outline(obj, line) if line else obj

    # -------------------------------------------------------------------- light: graphic toon
    # Warm key for the face and legs, cool glancing light for the shell rim and a gentle fill.
    kit.world(BACKDROP, strength=0.45)
    kit.area('Warm key', (-1.35, -1.70, 2.05), (0, 0, 0.36), 285, '#FFE1BC', 0.82, size_y=1.3)
    kit.area('Cool edge', (0.9, 1.02, 1.44), (0, 0.02, 0.45), 115, '#BDD9FF', 0.55, size_y=1.1)
    kit.area('Face fill', (1.3, -1.2, 0.9), (0, -0.12, 0.58), 44, '#E4EDFF', 0.95)

    # -------------------------------------------------------------------- cyclorama floor
    # One mesh: a flat floor that bends up into a back wall (no horizon line behind a low camera).
    floor_mat, floor_inputs = cel_shader(kit, 'Checker floor', spec=0.0, physical=0.50)
    nt = floor_mat.node_tree
    coord = nt.nodes.new('ShaderNodeTexCoord')
    checker = nt.nodes.new('ShaderNodeTexChecker')
    checker.inputs['Scale'].default_value = 1 / 0.22          # 22 cm tiles (object coords are metres)
    checker.inputs['Color1'].default_value = kit.color(CHECK_A)
    checker.inputs['Color2'].default_value = kit.color(CHECK_B)
    nt.links.new(coord.outputs['Object'], checker.inputs['Vector'])
    dist = nt.nodes.new('ShaderNodeVectorMath')
    dist.operation = 'LENGTH'
    nt.links.new(coord.outputs['Object'], dist.inputs[0])
    fade = nt.nodes.new('ShaderNodeMapRange')
    fade.inputs['From Min'].default_value, fade.inputs['From Max'].default_value = 1.3, 2.8
    nt.links.new(dist.outputs['Value'], fade.inputs['Value'])
    to_back = nt.nodes.new('ShaderNodeMix')
    to_back.data_type = 'RGBA'
    nt.links.new(fade.outputs['Result'], sock(to_back.inputs, 'Factor_Float'))
    nt.links.new(checker.outputs['Color'], sock(to_back.inputs, 'A_Color'))
    backdrop_gradient = kit.color_ramp(nt, [(0.0, '#8390B7'), (0.48, BACKDROP), (1.0, '#1B233D')], 'EASE')
    backdrop_radius = radial_distance(nt, coord.outputs['Object'], (0, 5.2, 1.8), (0.22, 0, 0.34))
    nt.links.new(backdrop_radius, backdrop_gradient.inputs['Fac'])
    nt.links.new(backdrop_gradient.outputs['Color'], sock(to_back.inputs, 'B_Color'))

    # Soft ground shadows use the floor's coordinates so the inked objects stay anchored during the orbit.
    mask = None
    for x, y, scale in ((0, 0.04, (2.3, 2.0, 2)), (*BALL_XY, (9, 10, 5)), (*BOWL_XY, (5.9, 5.9, 4))):
        radius = radial_distance(nt, coord.outputs['Object'], (x, y, 0), scale)
        falloff = nt.nodes.new('ShaderNodeMapRange')
        falloff.interpolation_type = 'SMOOTHSTEP'
        falloff.inputs['From Min'].default_value, falloff.inputs['From Max'].default_value = 0.28, 1.0
        falloff.inputs['To Min'].default_value, falloff.inputs['To Max'].default_value = 0.59, 0.0
        nt.links.new(radius, falloff.inputs['Value'])
        if mask is None:
            mask = falloff.outputs['Result']
        else:
            combine = nt.nodes.new('ShaderNodeMath')
            combine.operation = 'MAXIMUM'
            nt.links.new(mask, combine.inputs[0])
            nt.links.new(falloff.outputs['Result'], combine.inputs[1])
            mask = combine.outputs[0]
    shade = nt.nodes.new('ShaderNodeMix')
    shade.data_type, shade.blend_type = 'RGBA', 'MULTIPLY'
    nt.links.new(mask, sock(shade.inputs, 'Factor_Float'))
    nt.links.new(sock(to_back.outputs, 'Result_Color'), sock(shade.inputs, 'A_Color'))
    sock(shade.inputs, 'B_Color').default_value = kit.color('#737291')
    for floor_base in floor_inputs:
        nt.links.new(sock(shade.outputs, 'Result_Color'), floor_base)

    profile = [(y, 0.0) for y in (-8.0, -3.0, 0.0, 2.0, 3.6)]
    bend_r = 1.6
    for i in range(1, 13):                                  # quarter circle up into the wall
        a = math.radians(90 * i / 12)
        profile.append((3.6 + bend_r * math.sin(a), bend_r * (1 - math.cos(a))))
    profile += [(3.6 + bend_r, 4.0), (3.6 + bend_r, 9.0)]
    verts, faces = [], []
    for x in (-9.0, 9.0):
        verts += [(x, y, z) for y, z in profile]
    n = len(profile)
    faces = [(i, n + i, n + i + 1, i + 1) for i in range(n - 1)]
    cyc = kit.mesh('Cyclorama floor', verts, faces, floor_mat, smooth=True, ground=True)
    cyc.data.polygons.foreach_set('use_smooth', [True] * len(cyc.data.polygons))

    # -------------------------------------------------------------------- rig skeleton
    root = kit.empty('Robot dog', (0, 0, 0), display='ARROWS', size=0.3)
    parts = []                                                # every mesh, parented at the end

    # -------------------------------------------------------------------- torso
    torso = rounded_box('Torso shell', TORSO, (0, 0.07, 0.29), BODY, 0.06, rot=(TORSO_PITCH, 0, 0), spec=0.2)
    torso_children = []
    # Chest plate in accent colour and a little status light (mid-scale detail).
    chest = rounded_box('Chest plate', (0.18, 0.03, 0.14), (0, -0.205, 0.0), ACCENT, 0.012, line=0.006)
    readout = rounded_box('Chest status panel', (0.093, 0.012, 0.033), (0, -0.224, 0.014),
                          SCREEN, 0.005, line=0)
    torso_children += [chest, readout]
    light_mat = kit.emissive('Status light', '#91F8CE', 1.3)
    for x in (-0.028, 0, 0.028):
        torso_children.append(kit.cylinder('Status indicator', 0.006, 0.004, (x, -0.231, 0.014),
                                          light_mat, rotation=(90, 0, 0), segments=16))
    # Trace a rounded seam on the housing so the paint follows the bevel.
    seam = []
    corner = 0.06
    for sx, sz, start in ((1, 1, 0), (-1, 1, 90), (-1, -1, 180), (1, -1, 270)):
        for step in range(7):
            a = math.radians(start + step * 15)
            seam.append((sx * (TORSO[0] / 2 - corner) + corner * math.cos(a), 0.053,
                         sz * (TORSO[2] / 2 - corner) + corner * math.sin(a)))
    torso_children.append(kit.tube('Housing gasket', seam, 0.003, cel(JOINT), closed=True))
    rivet_mat = cel('#C9C3B8', 0.6)
    for side in (-1, 1):
        for y in (-0.13, -0.0, 0.13):
            for z in (-0.07, 0.07):
                torso_children.append(kit.sphere('Rivet', 0.008, (side * (TORSO[0] / 2 + 0.002), y, z), rivet_mat,
                                                 segments=10, rings=6))
        # Side vents: three short dark slots.
        for k in range(3):
            torso_children.append(kit.box('Side vent', (0.006, 0.07, 0.012),
                                          (side * (TORSO[0] / 2 + 0.003), 0.05, -0.03 + k * 0.026), cel(SCREEN)))
    # Children are built in torso-local space, then moved by the torso transform.
    for c in torso_children:
        c.parent = torso
    # Breathing: the torso swells across its width and height, two breaths per loop.
    kit.animate(torso, 'scale', lambda t: (1 + 0.022 * kit.wave(t, BREATHS), 1.0, 1 + 0.03 * kit.wave(t, BREATHS)))
    parts.append(torso)

    # -------------------------------------------------------------------- legs
    joint_mat = cel(JOINT, 0.4)
    for side in (-1, 1):
        x = side * 0.105
        # Front legs: straight, two segments with a knee ball and a chunky paw.
        upper = kit.cylinder('Front leg upper', 0.032, 0.17, (x, -0.10, 0.27), cel(BODY, 0.3), segments=24)
        lower = kit.cylinder('Front leg lower', 0.026, 0.15, (x, -0.11, 0.12), joint_mat, segments=24)
        knee = kit.sphere('Front knee', 0.036, (x, -0.105, 0.185), joint_mat, segments=24, rings=12)
        paw = rounded_box('Front paw', (0.085, 0.11, 0.05), (x, -0.13, 0.026), BODY, 0.02)
        pad = rounded_box('Front paw pad', (0.075, 0.03, 0.034), (x, -0.18, 0.022), ACCENT, 0.012, line=0.004)
        for o in (upper, lower, knee):
            outline(o, 0.006)
        # Rear legs: a big thigh disc on the hip, and a long foot pointing forward.
        thigh = kit.cylinder('Haunch', 0.105, 0.07, (side * 0.165, 0.13, 0.125), cel(BODY, 0.35),
                             rotation=(0, 90, 0), segments=40)
        thigh_m = thigh.modifiers.new('Round', 'BEVEL')
        thigh_m.width, thigh_m.segments, thigh_m.limit_method = 0.018, 3, 'ANGLE'
        outline(thigh, 0.007)
        hub = kit.cylinder('Haunch hub', 0.045, 0.012, (side * 0.203, 0.13, 0.125), joint_mat, rotation=(0, 90, 0),
                           segments=28)
        foot = rounded_box('Rear foot', (0.08, 0.15, 0.05), (side * 0.17, 0.02, 0.026), BODY, 0.02)
        parts += [upper, lower, knee, paw, pad, thigh, hub, foot]

    # -------------------------------------------------------------------- tail: a coil spring
    tail_pivot = kit.empty('Tail pivot', (0, 0.30, 0.15), size=0.05)
    coil = []
    turns, length, coil_r = 6.0, 0.33, 0.037
    for i in range(140):
        s = i / 139
        a = s * turns * math.tau
        coil.append((coil_r * math.cos(a), coil_r * math.sin(a), s * length))
    spring = kit.tube('Tail spring', coil, radius=0.008, material=cel('#797DA1', 0.7), resolution=8)
    spring.location = (0, 0.30, 0.15)
    spring.rotation_euler = (math.radians(-28), 0, 0)       # sweeps back and up from the rump
    tip_dir = Vector((0, math.sin(math.radians(28)), math.cos(math.radians(28))))
    tail_tip = kit.sphere('Tail tip', 0.042, Vector((0, 0.30, 0.15)) + tip_dir * (length + 0.03), cel(ACCENT, 0.5),
                          segments=24, rings=12)
    outline(tail_tip, 0.005)
    for o in (spring, tail_tip):
        kit.parent(o, tail_pivot)
    # Wag: side to side about the pivot's vertical axis, with a little up-down bounce at 2x rate.
    kit.animate(tail_pivot, 'rotation_euler', lambda t: (math.radians(6 * kit.wave(t, WAGS * 2)), 0,
                                                         math.radians(32 * kit.wave(t, WAGS))))

    # -------------------------------------------------------------------- neck and head
    neck = kit.cylinder('Neck', 0.045, 0.12, (0, -0.10, 0.45), joint_mat, rotation=(-12, 0, 0), segments=24)
    outline(neck, 0.006)
    collar = kit.torus('Collar', 0.056, 0.016, (0, -0.10, 0.43), cel(ACCENT, 0.4), rotation=(-12, 0, 0),
                       segments=40, sides=12)
    outline(collar, 0.004)
    tag = kit.cylinder('Collar tag', 0.022, 0.006, (0, -0.165, 0.405), cel('#F4C542', 0.8), rotation=(90, 0, 0),
                       segments=20)
    outline(tag, 0.003)
    parts += [neck, collar, tag]

    head_pivot = kit.empty('Head pivot', HEAD_PIVOT, size=0.08)
    head_parts = []
    hx, hy, hz = HEAD
    head_c = Vector((0, -0.15, 0.64))
    head = rounded_box('Head shell', HEAD, head_c, BODY, 0.06)
    top_inlay = rounded_box('Head crown inlay', (0.17, 0.115, 0.017), (0, head_c.y + 0.016, head_c.z + hz / 2),
                            '#62769A', 0.008, spec=0.42, line=0.004)
    # Screen face: a dark glossy inset with a bezel, slightly proud of the front.
    face_y = head_c.y - hy / 2 - 0.004
    bezel = rounded_box('Screen bezel', (hx - 0.04, 0.012, hz - 0.055), (0, face_y, head_c.z + 0.005), JOINT,
                        0.02, line=0)
    screen = rounded_box('Face screen', (hx - 0.065, 0.012, hz - 0.08), (0, face_y - 0.004, head_c.z + 0.005),
                         SCREEN, 0.018, spec=0.9, line=0)
    face_outline = []
    frame_corner = 0.023
    for sx, sz, start in ((1, 1, 0), (-1, 1, 90), (-1, -1, 180), (1, -1, 270)):
        for step in range(7):
            a = math.radians(start + step * 15)
            face_outline.append((sx * ((hx - 0.035) / 2 - frame_corner) + frame_corner * math.cos(a),
                                 face_y - 0.006,
                                 head_c.z + 0.005 + sz * ((hz - 0.050) / 2 - frame_corner) +
                                 frame_corner * math.sin(a)))
    screen_stroke = kit.tube('Inked screen rim', face_outline, radius=0.0048, material=ink, closed=True)
    head_parts += [head, top_inlay, bezel, screen, screen_stroke]
    # Eyes: emissive cyan discs with a white catch-light, kept as separate objects so they blink.
    eye_mat = kit.emissive('Eye glow', EYE, 1.6)
    catch_mat = kit.emissive('Eye catch-light', '#FFFFFF', 1.0)
    eyes = []
    for side in (-1, 1):
        ex = side * 0.058
        eye = kit.cylinder('Eye', 0.036, 0.004, (ex, face_y - 0.012, head_c.z + 0.018), eye_mat,
                           rotation=(90, 0, 0), segments=40)
        catch = kit.cylinder('Eye catch-light', 0.01, 0.004, (ex + 0.012, face_y - 0.015, head_c.z + 0.03),
                             catch_mat, rotation=(90, 0, 0), segments=16)
        kit.parent(catch, eye)
        blush = kit.cylinder('Cheek blush', 0.016, 0.003, (side * 0.098, face_y - 0.011, head_c.z - 0.035),
                             kit.emissive('Blush', BLUSH, 1.0), rotation=(90, 0, 0), segments=20)
        eyes.append(eye)
        head_parts += [eye, blush]
    # A small happy mouth: a cyan arc tube on the screen.
    mouth_pts = [(0.022 * math.cos(a), face_y - 0.012, head_c.z - 0.03 - 0.012 * math.sin(a))
                 for a in [math.pi * k / 10 for k in range(11)]]
    mouth = kit.tube('Mouth', mouth_pts, radius=0.0035, material=eye_mat, resolution=6)
    head_parts.append(mouth)
    # Chin plate under the screen (the 'snout') and side vents on the cheeks.
    chin = rounded_box('Chin', (0.15, 0.06, 0.04), (0, head_c.y - hy / 2 + 0.005, head_c.z - hz / 2 + 0.01),
                       ACCENT, 0.015, line=0.004)
    head_parts.append(chin)
    for side in (-1, 1):
        for k in range(3):
            head_parts.append(kit.box('Head vent', (0.006, 0.06, 0.01),
                                      (side * (hx / 2 + 0.003), head_c.y + 0.03, head_c.z - 0.04 + k * 0.022),
                                      cel(SCREEN)))
        # Ear discs on the sides (where a dog's ears would hinge).
        ear_disc = kit.cylinder('Ear hub', 0.042, 0.02, (side * (hx / 2 + 0.01), head_c.y + 0.02, head_c.z + 0.04),
                                cel(ACCENT, 0.4), rotation=(0, 90, 0), segments=32)
        outline(ear_disc, 0.004)
        head_parts.append(ear_disc)

    # Antenna ears: pivots on the top corners, each a rod, a ring and a ball tip; they wobble with
    # a delay after the head moves (overlapping action).
    ear_pivots = []
    for side in (-1, 1):
        base = Vector((side * 0.10, head_c.y + 0.03, head_c.z + hz / 2 - 0.01))
        pivot = kit.empty('Ear pivot', base, size=0.04)
        rod = kit.cylinder('Antenna rod', 0.008, 0.15, base + Vector((0, 0, 0.075)), joint_mat, segments=12)
        collar_ring = kit.cylinder('Antenna base', 0.022, 0.02, base + Vector((0, 0, 0.01)), cel(BODY, 0.3),
                                   segments=24)
        tip = kit.sphere('Antenna tip', 0.026, base + Vector((0, 0, 0.16)), cel(ACCENT, 0.6), segments=24, rings=12)
        for o in (rod, collar_ring, tip):
            outline(o, 0.004)
            kit.parent(o, pivot)
        pivot.rotation_euler = (0, math.radians(side * 16), 0)     # splayed outward
        ear_pivots.append((pivot, side))
        head_parts.append(pivot)

    for o in head_parts:
        kit.parent(o, head_pivot)

    # Head motion: a curious tilt to one side that rises and settles once per loop, plus a slow
    # look-around and a breathing bob in sync with the torso.
    def head_rot(t):
        tilt = TILT_DEG * math.sin(math.pi * t) ** 4                    # 0 at both ends: loop-safe
        yaw = 9.0 * kit.wave(t, 1, 0.1)
        nod = 3.0 * kit.wave(t, BREATHS, 0.2)
        return (math.radians(nod), math.radians(tilt), math.radians(yaw))
    kit.animate(head_pivot, 'rotation_euler', head_rot)
    kit.animate(head_pivot, 'location', lambda t: HEAD_PIVOT + Vector((0, 0, 0.006 * kit.wave(t, BREATHS, -0.05))))

    for pivot, side in ear_pivots:
        def ear_rot(t, side=side):
            lag = 7.0 * kit.wave(t, 2, -0.12 + 0.1 * side) + 5.0 * kit.wave(t, WAGS, 0.3)
            return (math.radians(lag * 0.6), math.radians(side * 16 + lag), 0)
        kit.animate(pivot, 'rotation_euler', ear_rot)

    # Blink once, mid-loop: squash the eye discs (local Z of the rotated disc is the face's up).
    for eye in eyes:
        b = int(kit.frames * 0.62)
        kit.key(eye, 'scale', [(1, (1, 1, 1)), (b - 3, (1, 1, 1)), (b, (1.0, 0.12, 1.0)),
                               (b + 3, (1, 1, 1)), (kit.frames + 1, (1, 1, 1))])

    # -------------------------------------------------------------------- props (story + scale)
    # A red ball and a food bowl tell 'dog' and give the floor something to hold.
    ball_mat, ball_inputs = cel_shader(kit, 'Toy ball enamel', '#E8413C', spec=0.5)
    nt = ball_mat.node_tree
    coords = nt.nodes.new('ShaderNodeTexCoord')
    axis = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(coords.outputs['Generated'], axis.inputs[0])
    stripe = kit.color_ramp(nt, [(0.0, '#E8413C'), (0.39, '#F6EBDD'), (0.59, '#E8413C')], 'CONSTANT')
    nt.links.new(axis.outputs['Z'], stripe.inputs['Fac'])
    for ball_base in ball_inputs:
        nt.links.new(stripe.outputs['Color'], ball_base)
    ball = kit.sphere('Toy ball', 0.075, (*BALL_XY, 0.075), ball_mat, segments=48, rings=24)
    ball.rotation_euler = (math.radians(-23), math.radians(34), 0)
    outline(ball, 0.006)
    bowl_profile = [(0.0, 0.0), (0.09, 0.0), (0.11, 0.012), (0.125, 0.07), (0.135, 0.075), (0.128, 0.08),
                    (0.11, 0.075), (0.098, 0.03), (0.0, 0.03)]
    bowl = kit.lathe('Food bowl', bowl_profile, segments=48, material=cel(ACCENT, 0.5), location=(*BOWL_XY, 0))
    outline(bowl, 0.006)
    # Kibble: a few bolt-shaped nuggets heaped in the bowl (the robot's 'food').
    nut_mat = cel('#9AA1AE', 0.5)
    for i in range(9):
        a, r = rng.uniform(0, math.tau), rng.uniform(0, 0.07)
        kit.cylinder('Kibble nut', 0.016, 0.012, (BOWL_XY[0] + r * math.cos(a), BOWL_XY[1] + r * math.sin(a),
                                                0.038 + 0.01 * rng.random()),
                     nut_mat, rotation=(rng.uniform(-20, 20), rng.uniform(-20, 20), rng.uniform(0, 60)), segments=6,
                     smooth=False)

    # -------------------------------------------------------------------- assemble and turn the dog
    for o in parts + [tail_pivot, head_pivot]:
        kit.parent(o, root)
    root.rotation_euler.z = math.radians(FACING)

    # -------------------------------------------------------------------- camera: low hero arc
    # Lens near the floor looking slightly up; the azimuth swings out and back on one sine, so
    # the end frame meets the start frame exactly.
    focus_point = kit.empty('Focus on the face and breastplate', (0, -0.11, 0.48), size=0.03)
    cam = kit.camera((0, -1.5, 0.22), (0, -0.02, 0.42), lens=42, dof=focus_point, fstop=5.6)
    radius, focus = 1.62, Vector((0, -0.05, 0.0))

    def cam_at(t):
        a = math.radians(ARC_CENTER + ARC_SWING * kit.wave(t, 1))
        h = 0.25 + 0.052 * kit.wave(t, 1, 0.25)
        return focus + Vector((radius * math.sin(a), -radius * math.cos(a), h))
    kit.animate(cam, 'location', cam_at)
