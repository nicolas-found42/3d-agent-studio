"""Watch hero turntable: a 40 mm steel dress watch on a suede pillow, orbited in a seamless loop.

Teaches: product work at true scale (metres, so a 40 mm case is 0.040) and the material tricks
that sell luxury metal and glass in Cycles:
- circular-brushed steel from an anisotropic BSDF with a RADIAL tangent (highlights wrap around
  the case like real turned finishing), polished bezel and indices with a near-zero roughness;
- a sunburst dial: the same tangent rotated 90 degrees, so the highlight is a radial bar that
  sweeps as the camera moves;
- a sapphire crystal (IOR 1.77) with a reduced Fresnel reflection to model an anti-reflective coating,
  plus clear shadow rays so the dial is not darkened by missing caustics;
- a studio rig of large soft area lights and a strip softbox whose reflections slide across the
  polished surfaces as the camera orbits (static lights + moving camera = living reflections).
Motion: one 360 degree linear orbit (loop-safe) and a second hand that ticks 48 times per turn
with CONSTANT keys, so frame 145 equals frame 1 exactly.
"""
import math

import bmesh
import bpy
from mathutils import Vector

# ----------------------------------------------------------------------------- dimensions (m)
CASE_R = 0.0200           # 40 mm case
DIAL_R = 0.0166
PILLOW_R = 0.0320         # suede pillow: a horizontal cylinder the strap wraps around
PILLOW_Z = 0.0200 + 0.0320
CASE_Z = PILLOW_Z + PILLOW_R - 0.0040   # the case sinks 4 mm into the soft pillow (contact, no float)
PILLOW_LEN = 0.054
PLINTH_R, PLINTH_H = 0.075, 0.020
STRAP_W = 0.020           # lug width
HOUR, MINUTE = 10, 10     # the classic 10:10 product pose frames the logo area and looks "smiling"

# ----------------------------------------------------------------------------- camera
ORBIT_RADIUS = 0.165
ORBIT_HEIGHT = 0.150      # above the dial: looks down ~42 degrees so the dial reads all the way round
LENS = 70.0
FSTOP = 11.0              # macro depth of field is thin: f/11 keeps the case sharp, the plinth falls off
TICKS_PER_TURN = 48       # 144 frames / 48 = one tick every 3 frames


# ============================================================================= helpers
def prism(kit, name, outline, place, material, collection='Watch', bevel=0.0):
    """Extrude a 2D outline between two caps; place(u, v, w) maps it into the world, w in {0, 1}."""
    bm = bmesh.new()
    a = [bm.verts.new(place(u, v, 0)) for u, v in outline]
    b = [bm.verts.new(place(u, v, 1)) for u, v in outline]
    bm.faces.new(a)
    bm.faces.new(list(reversed(b)))
    for i in range(len(a)):
        j = (i + 1) % len(a)
        bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    me.materials.append(material)
    kit.collection(collection).objects.link(obj)
    if bevel:
        kit.bevel(obj, bevel, segments=2)
    return obj


def ribbon(kit, name, path, width, thickness, material, centre, collection='Strap'):
    """A flat band swept along a path in the YZ plane (a strap): each path point becomes a
    rectangle (width along X, thickness along the path normal), stitched into a closed solid."""
    bm = bmesh.new()
    rings = []
    for i, p in enumerate(path):
        p = Vector(p)
        q0 = Vector(path[max(0, i - 1)])
        q1 = Vector(path[min(len(path) - 1, i + 1)])
        tan = (q1 - q0).normalized()
        nrm = Vector((0, -tan.z, tan.y))          # in-plane normal, flipped to point away from `centre`
        if nrm.dot(p - Vector(centre)) < 0:
            nrm = -nrm
        ring = [bm.verts.new(p + Vector((sx * width / 2, 0, 0)) + nrm * (sz * thickness))
                for sx, sz in ((-1, 0), (1, 0), (1, 1), (-1, 1))]
        rings.append(ring)
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(4):
            bm.faces.new((r0[k], r0[(k + 1) % 4], r1[(k + 1) % 4], r1[k]))
    bm.faces.new(rings[0])
    bm.faces.new(list(reversed(rings[-1])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = True
    obj = bpy.data.objects.new(name, me)
    me.materials.append(material)
    kit.collection(collection).objects.link(obj)
    kit.bevel(obj, thickness * 0.3, segments=2, harden=False)   # rounded leather edges
    return obj


# ============================================================================= materials
def brushed_steel(kit, name, rotate=0.0, roughness=0.22, color='#C9CCD1'):
    """Anisotropic steel brushed around the object's Z axis (RADIAL tangent). rotate=0.25 turns
    the brushing 90 degrees (sunburst). A stretched noise adds the fine brushing lines."""
    mat = kit.material(name, color, roughness=roughness, metallic=1.0)
    nt = mat.node_tree
    bs = kit.bsdf(mat)
    tangent = nt.nodes.new('ShaderNodeTangent')
    tangent.direction_type, tangent.axis = 'RADIAL', 'Z'
    nt.links.new(tangent.outputs['Tangent'], bs.inputs['Tangent'])
    bs.inputs['Anisotropic'].default_value = 0.85
    bs.inputs['Anisotropic Rotation'].default_value = rotate
    # Brushing lines: noise squashed along the circumference, driving roughness a little.
    coord = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(coord.outputs['Object'], sep.inputs[0])
    length = nt.nodes.new('ShaderNodeVectorMath')
    length.operation = 'LENGTH'
    nt.links.new(coord.outputs['Object'], length.inputs[0])
    lines = nt.nodes.new('ShaderNodeTexNoise')
    lines.noise_dimensions = '1D'
    lines.inputs['Scale'].default_value = 9000.0          # ~0.1 mm streaks at watch scale
    lines.inputs['Detail'].default_value = 3
    nt.links.new(length.outputs['Value'], lines.inputs['W'])
    rng = nt.nodes.new('ShaderNodeMapRange')
    rng.inputs['To Min'].default_value = roughness * 0.75
    rng.inputs['To Max'].default_value = roughness * 1.3
    nt.links.new(lines.outputs['Fac'], rng.inputs['Value'])
    nt.links.new(rng.outputs['Result'], bs.inputs['Roughness'])
    return mat


def sapphire(kit, name='Sapphire crystal'):
    """Refract through the crystal, retain a light Fresnel sheen, and pass shadow rays."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    refraction = nt.nodes.new('ShaderNodeBsdfRefraction')
    refraction.inputs['Color'].default_value = kit.color('#F4F8FF')
    refraction.inputs['Roughness'].default_value = 0.006
    refraction.inputs['IOR'].default_value = 1.77
    reflection = nt.nodes.new('ShaderNodeBsdfGlossy')
    reflection.inputs['Roughness'].default_value = 0.035
    fresnel = nt.nodes.new('ShaderNodeFresnel')
    fresnel.inputs['IOR'].default_value = 1.77
    coating = nt.nodes.new('ShaderNodeMath')
    coating.operation = 'MULTIPLY'
    coating.inputs[1].default_value = 0.23
    nt.links.new(fresnel.outputs['Fac'], coating.inputs[0])
    glass = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(coating.outputs[0], glass.inputs[0])
    nt.links.new(refraction.outputs[0], glass.inputs[1])
    nt.links.new(reflection.outputs[0], glass.inputs[2])
    clear = nt.nodes.new('ShaderNodeBsdfTransparent')
    path = nt.nodes.new('ShaderNodeLightPath')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(path.outputs['Is Shadow Ray'], mix.inputs[0])
    nt.links.new(glass.outputs[0], mix.inputs[1])
    nt.links.new(clear.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    return mat


# ============================================================================= watch parts
def hand(kit, name, length, tail, width, z, mat, kind='dauphine'):
    """A hand as an extruded outline pointing along +Y from the dial centre (rotated later)."""
    if kind == 'dauphine':        # faceted lozenge: widest a quarter of the way out
        outline = [(0, -tail), (width / 2, length * 0.22), (0, length), (-width / 2, length * 0.22)]
    else:                         # seconds: needle with a round counterweight tail
        outline = [(-width / 2, -tail), (width / 2, -tail), (width * 0.3, length), (-width * 0.3, length)]
    return prism(kit, name, outline, lambda u, v, w: (u, v, z + w * 0.00025), mat)


def build(kit):
    kit.note('40 mm steel watch on a suede pillow; 360 degree orbit; second hand ticks 48 times per loop')

    steel = brushed_steel(kit, 'Circular-brushed steel', 0.0, 0.2)
    polished = kit.material('Polished steel', '#D4D7DC', roughness=0.05, metallic=1.0)
    dial_mat = brushed_steel(kit, 'Sunburst blue dial', 0.25, 0.32, '#28466D')
    dial_bs = kit.bsdf(dial_mat)
    dial_bs.inputs['Metallic'].default_value = 0.45           # lacquered, so the dial also catches diffuse light
    dial_bs.inputs['Coat Weight'].default_value = 0.18
    dial_bs.inputs['Coat Roughness'].default_value = 0.14
    print_white = kit.material('Printed white', '#E8E6E0', roughness=0.5)
    lume = kit.material('Lume', '#EDEBD8', roughness=0.4, emission='#B8F0C8', emission_strength=0.05)
    red = kit.material('Red lacquer', '#B3241B', roughness=0.25, coat=0.6)
    crystal = sapphire(kit)
    leather = kit.material('Black calf leather', '#100D0B', roughness=0.5, bump=(4000.0, 0.12), coat=0.15)
    thread = kit.material('Stitching', '#9A8F7E', roughness=0.8)
    suede = kit.material('Charcoal suede', '#1A1B1E', roughness=0.95, sheen=0.25, bump=(9000.0, 0.08))
    kit.bsdf(suede).inputs['Sheen Tint'].default_value = kit.color('#55575C')   # soft grazing fuzz, not white
    anodised = kit.material('Black anodised plinth', '#0C0C0E', roughness=0.32, metallic=0.6, bump=(1800.0, 0.03))
    floor = kit.material('Studio floor', '#0A0A0B', roughness=0.4)

    # --- set: a dark glossy floor (gradient comes from light falloff), plinth, suede pillow
    kit.ground(floor, size=12)
    kit.lathe('Plinth', [(0, 0), (PLINTH_R, 0), (PLINTH_R, PLINTH_H - 0.003), (PLINTH_R - 0.0008, PLINTH_H - 0.0008),
                         (PLINTH_R - 0.003, PLINTH_H), (0, PLINTH_H)], segments=128, material=anodised,
              collection='Set')
    # Pillow: a lathed capsule with soft rounded ends, turned to lie along X.
    prof = [(0, -PILLOW_LEN / 2)]
    for k in range(9):
        a = math.radians(90 * k / 8)
        prof.append((PILLOW_R - 0.006 + 0.006 * math.sin(a), -PILLOW_LEN / 2 + 0.006 - 0.006 * math.cos(a)))
    prof += [(r, -z) for r, z in reversed(prof[1:])] + [(0, PILLOW_LEN / 2)]
    kit.lathe('Suede pillow', prof, segments=96, material=suede, location=(0, 0, PILLOW_Z), rotation=(0, 90, 0),
              collection='Set')

    # --- case: caseback, brushed middle, polished bezel (separate lathes = separate finishes)
    kit.lathe('Caseback', [(0, 0), (0.0160, 0), (0.0168, 0.0008), (0.0170, 0.0018), (0, 0.0018)],
              material=polished, location=(0, 0, CASE_Z), segments=96)
    kit.lathe('Case middle', [(0, 0.0016), (0.0182, 0.0016), (0.0196, 0.0034), (0.0201, 0.0060),
                              (0.0199, 0.0084), (0.0193, 0.0094), (0, 0.0094)],
              material=steel, location=(0, 0, CASE_Z), segments=128)
    kit.lathe('Bezel', [(0.0168, 0.0094), (0.0194, 0.0094), (0.0197, 0.0104), (0.0191, 0.0120),
                        (0.0180, 0.0126), (0.0171, 0.0125), (0.0169, 0.0118)],
              material=polished, location=(0, 0, CASE_Z), segments=128)
    # Lugs: a side profile that curves down toward the strap, extruded across X, bevelled.
    lug = [(0.0150, 0.0016), (0.0262, 0.0030), (0.0266, 0.0048), (0.0240, 0.0078), (0.0170, 0.0090)]
    for sx in (-1, 1):
        for sy in (-1, 1):
            x0 = sx * (STRAP_W / 2 + 0.0002)
            prism(kit, f'Lug {sx:+d}{sy:+d}', lug,
                  lambda u, v, w, sx=sx, sy=sy, x0=x0: (x0 + sx * w * 0.0024, sy * u, CASE_Z + v), steel, bevel=0.0004)
    # Crown at 3 o'clock with 24 knurls.
    kit.cylinder('Crown tube', 0.0014, 0.0016, (CASE_R + 0.0006, 0, CASE_Z + 0.0055), polished, rotation=(0, 90, 0),
                 segments=24)
    kit.cylinder('Crown', 0.0030, 0.0024, (CASE_R + 0.0024, 0, CASE_Z + 0.0055), polished, rotation=(0, 90, 0),
                 segments=48, bevel=0.0003)
    knurl = kit.box('Crown knurl', (0.0020, 0.0004, 0.0004), (0, 0, 0), polished)
    for k in range(1, 24):                     # the prototype itself is knurl 0
        a = 2 * math.pi * k / 24
        kit.instance(knurl, (CASE_R + 0.0024, 0.0030 * math.cos(a), CASE_Z + 0.0055 + 0.0030 * math.sin(a)),
                     (math.degrees(a), 0, 0), name=f'Crown knurl {k}', collection='Watch')
    knurl.location = (CASE_R + 0.0024, 0.0030, CASE_Z + 0.0055)

    # --- dial: sunburst disc, minute track, applied indices with lume, hands, crystal
    dz = CASE_Z + 0.0094
    kit.cylinder('Dial', DIAL_R, 0.0004, (0, 0, dz + 0.0002), dial_mat, segments=128)
    kit.lathe('Rehaut', [(DIAL_R - 0.0010, dz + 0.0004), (DIAL_R, dz + 0.0016), (DIAL_R, dz + 0.0004)],
              material=dial_mat, segments=128)
    tick = kit.box('Minute tick', (0.00012, 0.0009, 0.00004), (0, 0, 0), print_white)
    for m in range(60):
        if m % 5 == 0:
            continue
        a = math.radians(90 - 6 * m)
        r = DIAL_R - 0.0019
        kit.instance(tick, (r * math.cos(a), r * math.sin(a), dz + 0.00042), (0, 0, math.degrees(a) - 90),
                     name=f'Minute tick {m}', collection='Dial')
    tick.location = (0, 0, -1)   # prototype parked under the plinth, out of every view
    for h in range(12):
        a = math.radians(90 - 30 * h)
        r = DIAL_R - 0.0042
        offsets = (-0.0007, 0.0007) if h == 0 else (0.0,)    # doubled baton at 12
        for o in offsets:
            c = Vector((r * math.cos(a), r * math.sin(a), dz + 0.0007))
            side = Vector((-math.sin(a), math.cos(a), 0)) * o
            idx = kit.box(f'Index {h} {o:+.4f}', (0.0009, 0.0034, 0.0005), c + side, polished,
                          rotation=(0, 0, math.degrees(a) - 90), bevel=0.00012, collection='Dial')
            kit.box(f'Index lume {h} {o:+.4f}', (0.0004, 0.0022, 0.0002), c + side + Vector((0, 0, 0.00026)), lume,
                    rotation=(0, 0, math.degrees(a) - 90), collection='Dial')
            idx.name = f'Applied index {h}'

    hz = dz + 0.0012
    hour = hand(kit, 'Hour hand', 0.0092, 0.0015, 0.0019, hz, polished)
    minute = hand(kit, 'Minute hand', 0.0140, 0.0017, 0.0015, hz + 0.0004, polished)
    seconds = hand(kit, 'Seconds hand', 0.0152, 0.0040, 0.00028, hz + 0.0008, red, kind='needle')
    weight = kit.cylinder('Seconds counterweight', 0.0007, 0.00025, (0, -0.0034, hz + 0.0009), red, segments=24)
    weight.parent = seconds
    hour.rotation_euler.z = -math.radians(30 * (HOUR + MINUTE / 60))
    minute.rotation_euler.z = -math.radians(6 * MINUTE)
    kit.cylinder('Centre cap', 0.0006, 0.0003, (0, 0, hz + 0.0011), polished, segments=24)
    kit.lathe('Crystal', [(0, 0.0131), (0.0080, 0.01305), (0.0150, 0.01285), (0.0172, 0.0125), (0.0172, 0.0118),
                          (0, 0.0122)], material=crystal, location=(0, 0, CASE_Z), segments=128)

    # The tick: CONSTANT keys every 3 frames, a whole turn over the loop (frame 145 == frame 1).
    kit.animate(seconds, 'rotation_euler',
                lambda t: (0, 0, -2 * math.pi * math.floor(t * TICKS_PER_TURN + 1e-6) / TICKS_PER_TURN),
                step=1, interpolation='CONSTANT')

    # --- strap: two leather halves leave the lugs and wrap around the pillow, with edge stitching
    for sy in (1, -1):
        # Leave the spring bar heading down and out, then blend (cubic Bezier) into an arc that
        # hugs the pillow; the arc runs round and under, where the two halves would buckle.
        r = PILLOW_R + 0.0003
        a0 = math.radians(56)
        p0 = Vector((0, sy * 0.0240, CASE_Z + 0.0028))
        p3 = Vector((0, sy * r * math.sin(a0), PILLOW_Z + r * math.cos(a0)))
        tan3 = Vector((0, sy * math.cos(a0), -math.sin(a0)))
        p1, p2 = p0 + Vector((0, sy * 0.0020, -0.0015)), p3 - tan3 * 0.004
        path = [tuple(((1 - u) ** 3) * p0 + 3 * ((1 - u) ** 2) * u * p1 + 3 * (1 - u) * u * u * p2 + (u ** 3) * p3)
                for u in (0, 0.2, 0.4, 0.6, 0.8)]
        for k in range(15):
            a = a0 + math.radians(100 * k / 14)
            path.append((0, sy * r * math.sin(a), PILLOW_Z + r * math.cos(a)))
        ribbon(kit, f'Strap {"12" if sy > 0 else "6"} o\'clock', path, STRAP_W, 0.0032, leather, (0, 0, PILLOW_Z))
        for sx in (-1, 1):
            stitch = []
            for i in range(1, len(path)):        # same in-plane normal as ribbon(): sits on the top face
                v = Vector(path[i])
                tan = (Vector(path[min(i + 1, len(path) - 1)]) - Vector(path[i - 1])).normalized()
                out = Vector((0, -tan.z, tan.y))
                out = out if out.dot(v - Vector((0, 0, PILLOW_Z))) > 0 else -out
                stitch.append(v + out * 0.0033 + Vector((sx * (STRAP_W / 2 - 0.0014), 0, 0)))
            kit.tube(f'Stitch {sy:+d}{sx:+d}', stitch, 0.00022, thread, collection='Strap', resolution=4)

    # --- light: dark studio. Big soft key, cool fill, hard rim, and a strip softbox overhead whose
    # reflection is the long bright line on the bezel and crystal.
    target = (0, 0, CASE_Z + 0.008)
    key = kit.area('Key softbox', (-0.30, -0.22, 0.32), target, 2.5, '#FFF1E0', 0.28)
    fill = kit.area('Fill card', (0.32, -0.10, 0.14), target, 0.5, '#D8E4FF', 0.35)
    rim = kit.area('Rim strip', (0.10, 0.34, 0.20), target, 4.0, '#FFFFFF', 0.04, size_y=0.40)
    strip = kit.area('Overhead strip', (0, 0, 0.42), target, 1.5, '#FFFFFF', 0.06, size_y=0.6)
    for light in (key, fill, rim, strip):
        light.visible_camera = False
    kit.world('#050506', 1.0, top='#15171B')
    kit.render(exposure=0.4, look='AgX - Punchy')

    # --- camera: whole-turn linear orbit (seamless) with a one-cycle height breathe (also seamless)
    dial_focus = kit.empty('Focus on dial', (0, 0, CASE_Z + 0.011), size=0.01)
    cam = kit.camera((0, -ORBIT_RADIUS, CASE_Z + ORBIT_HEIGHT), target, lens=LENS, clip=(0.005, 20),
                     dof=dial_focus, fstop=FSTOP)
    kit.orbit(cam, center=(0, 0, CASE_Z), radius=ORBIT_RADIUS, height=ORBIT_HEIGHT, start=-25, sweep=360,
              target_height=0.006, height_wave=0.012)
