"""Fireworks over a quiet harbor at night, reflected in rippling water past moored boats.

Teaches:
- firework bursts as baked particle systems: a hidden ico-sphere emitter fires every particle in
  one frame along its normals (a spherical shell), then gravity and drag pull the shell down;
- per-particle fading in Cycles with the Particle Info node (age / lifetime drives emission
  strength and a hue shift toward ember orange), and motion blur turning sparks into streaks;
- rockets as keyframed emissive heads that carry their own spark-trail particle systems;
- fireworks as the only light: one keyed point light per burst flashes and decays with it, so the
  boats, the quay and the haze are lit only when something explodes;
- a dark glossy water shader with anisotropic, animated ripples (4D noise W) that stretch the
  reflections into vertical streaks, the way real night water does;
- silhouetted props with real proportions: lofted sailboat hulls, masts, stays and furled sails.
"""
import math

import bmesh
import bpy
from mathutils import Vector

# ---------------------------------------------------------------- constants (metres, seconds)
SHOW_Y = 260.0                     # the launch barge is 260 m out across the harbor
CAM_AT = Vector((6.0, -4.0, 2.6))  # standing on the quay, eye height above the water
SPARK_R = 0.45                     # spark size: ~1 px at preview, streaked by motion blur
# Each shell: launch time, burst time (shot progress 0..1), burst point, colour, sparks, speed.
SHELLS = [
    (0.00, 0.14, (-38.0, SHOW_Y, 118.0), '#FFC24A', 420, 34.0),   # gold chrysanthemum
    (0.12, 0.30, (42.0, SHOW_Y + 20, 150.0), '#FF3FA4', 380, 38.0),  # magenta peony
    (0.30, 0.47, (-6.0, SHOW_Y - 10, 136.0), '#3FE0FF', 420, 36.0),  # cyan
    (0.44, 0.62, (58.0, SHOW_Y + 10, 104.0), '#FF4A3A', 340, 30.0),  # red
    (0.58, 0.78, (-50.0, SHOW_Y + 30, 166.0), '#B8FF7A', 460, 40.0),  # lime willow
]
SPARK_LIFE = 1.9                   # seconds a spark burns


def water_material(kit):
    """Dark glossy water; ripples are noise squashed along Y so reflections smear vertically."""
    mat = kit.material('Harbor water', '#02050A', roughness=0.035, specular=0.6)
    nt, bs = mat.node_tree, kit.bsdf(mat)
    coord = nt.nodes.new('ShaderNodeTexCoord')
    mapping = nt.nodes.new('ShaderNodeMapping')
    mapping.inputs['Scale'].default_value = (0.35, 2.4, 1.0)   # long crests across the view
    nt.links.new(coord.outputs['Object'], mapping.inputs['Vector'])
    ripple = nt.nodes.new('ShaderNodeTexNoise')
    ripple.noise_dimensions = '4D'
    ripple.inputs['Scale'].default_value = 1.2
    ripple.inputs['Detail'].default_value = 6.0
    ripple.inputs['Roughness'].default_value = 0.55
    nt.links.new(mapping.outputs['Vector'], ripple.inputs['Vector'])
    # Animating W moves the ripples through time without sliding the pattern sideways.
    kit.animate(ripple.inputs['W'], 'default_value', lambda t: 2.2 * t, step=2)
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.22
    bump.inputs['Distance'].default_value = 0.1
    nt.links.new(ripple.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bs.inputs['Normal'])
    return mat


def spark_material(kit, name, colour, strength=60.0):
    """Emission that fades over each particle's life and cools from white-hot to ember."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    info = nt.nodes.new('ShaderNodeParticleInfo')
    life = nt.nodes.new('ShaderNodeMath')
    life.operation = 'DIVIDE'
    life.use_clamp = True
    nt.links.new(info.outputs['Age'], life.inputs[0])
    nt.links.new(info.outputs['Lifetime'], life.inputs[1])
    # Colour: white flash -> the shell colour -> a dim ember orange.
    ramp = kit._ramp(nt, [(0.0, '#FFFFFF'), (0.12, colour), (0.7, colour), (1.0, '#FF5A12')])
    nt.links.new(life.outputs[0], ramp.inputs['Fac'])
    # Strength: bright, then a long fall to zero (1 - x)^2.
    inv = nt.nodes.new('ShaderNodeMath')
    inv.operation = 'SUBTRACT'
    inv.inputs[0].default_value = 1.0
    nt.links.new(life.outputs[0], inv.inputs[1])
    sq = nt.nodes.new('ShaderNodeMath')
    sq.operation = 'POWER'
    nt.links.new(inv.outputs[0], sq.inputs[0])
    sq.inputs[1].default_value = 2.0
    k = nt.nodes.new('ShaderNodeMath')
    k.operation = 'MULTIPLY'
    nt.links.new(sq.outputs[0], k.inputs[0])
    k.inputs[1].default_value = strength
    em = nt.nodes.new('ShaderNodeEmission')
    nt.links.new(ramp.outputs['Color'], em.inputs['Color'])
    nt.links.new(k.outputs[0], em.inputs['Strength'])
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    mat.diffuse_color = kit.color(colour)
    return mat


def shell(kit, n, launch, burst, at, colour, count, speed):
    at = Vector(at)
    pad = Vector((at.x * 0.6, SHOW_Y, 1.5))          # launch tube on the barge, rockets lean outward
    life = round(SPARK_LIFE * kit.fps)
    # --- the rocket: an emissive head on a slightly bowed climb, hidden after it bursts
    head = kit.sphere(f'Rocket {n}', 0.5, pad, kit.emissive(f'Rocket {n} flare', '#FFE2A8', 80.0), segments=12, rings=8)
    mid = pad.lerp(at, 0.5) + Vector((2.0, 0, 0))
    kit.move(head, [pad, mid, at], start=launch, end=burst, ease_kind='out')
    kit.visible(head, launch, burst)
    trail = spark_material(kit, f'Rocket {n} trail', '#FFB050', 25.0)
    trail_spark = kit.ico(f'Rocket {n} trail spark', 0.2, material=trail, subdivisions=1)
    ps = kit.particles(head, count=120, lifetime=round(0.45 * kit.fps), velocity=0.0, random_velocity=3.0,
                       gravity=0.6, instance=trail_spark, size=1.0, size_random=0.5, start=launch,
                       end=burst, seed=10 + n, render_emitter=True)
    # --- the burst: every spark leaves one hidden ico sphere in a single frame
    emitter = kit.ico(f'Burst {n} emitter', 1.0, at, subdivisions=3)
    mat = spark_material(kit, f'Burst {n} sparks', colour)
    spark = kit.ico(f'Burst {n} spark', SPARK_R, material=mat, subdivisions=1)
    ps = kit.particles(emitter, count=count, lifetime=life, velocity=speed, random_velocity=0.12 * speed,
                       gravity=1.0, instance=spark, size=1.0, size_random=0.4, start=burst,
                       end=burst + 1.0 / kit.frames, seed=20 + n)
    ps.settings.emit_from = 'VERT' if count <= len(emitter.data.vertices) else 'FACE'
    ps.settings.drag_factor = 0.08               # air drag: the shell slows and then droops
    ps.settings.lifetime_random = 0.35           # sparks die at different times: ragged edges
    # --- the light it casts on the harbor: a flash, then decay with the sparks
    light = kit.point(f'Burst {n} light', at, power=0.0, color=colour, radius=8.0)
    b = burst
    kit.animate(light.data, 'energy', lambda t, b=b: 0.0 if t < b else
                2.6e6 * math.exp(-(t - b) * kit.seconds / 0.55), step=1)


def hull_mesh(kit, name, length, beam, depth, material, location, heading):
    """Lofted sailboat hull: half-width follows a pointed bow and a rounded stern."""
    bm = bmesh.new()
    sections = 16
    rings = []
    for i in range(sections + 1):
        s = i / sections                                     # 0 stern .. 1 bow
        x = (s - 0.5) * length
        half = beam / 2 * (math.sin(math.pi * (0.18 + 0.82 * s)) ** 0.7) * (1 - 0.15 * s)
        sheer = 0.12 * (2 * s - 1) ** 2 + 0.25 * s           # deck rises toward the bow
        keel = -depth * (0.65 + 0.35 * math.sin(math.pi * s))
        ring = []
        for k in range(9):                                   # cross-section from port deck to starboard deck
            a = math.pi * k / 8
            y = -half * math.cos(a)
            z = sheer + (keel - sheer) * math.sin(a) ** 1.3
            ring.append(bm.verts.new((x, y, z)))
        rings.append(ring)
    for i in range(sections):
        for k in range(8):
            bm.faces.new((rings[i][k], rings[i][k + 1], rings[i + 1][k + 1], rings[i + 1][k]))
    bm.faces.new([rings[0][k] for k in range(9)])            # transom
    deck = [rings[i][0] for i in range(sections + 1)] + [rings[i][8] for i in reversed(range(sections + 1))]
    bm.faces.new(deck)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = kit._bm_object(name, bm, material, location, (0, 0, heading), True, None)
    kit.subdivide(obj, 1)
    return obj


def sailboat(kit, n, at, length, heading, mats, mast_h):
    paint, wood, rope, canvas = mats
    root = kit.empty(f'Sailboat {n}', at)
    hull = hull_mesh(kit, f'Sailboat {n} hull', length, length * 0.33, length * 0.13, paint, (0, 0, 0), 0)
    hull.parent = root
    cabin = kit.box(f'Sailboat {n} cabin', (length * 0.28, length * 0.2, 0.45), (-0.04 * length, 0, 0.42),
                    wood, bevel=0.06)
    cabin.parent = root
    mast_x = 0.08 * length
    mast = kit.cylinder(f'Sailboat {n} mast', 0.06, mast_h, (mast_x, 0, mast_h / 2 + 0.3), wood, segments=10)
    mast.parent = root
    boom = kit.cylinder(f'Sailboat {n} boom', 0.045, length * 0.42, (mast_x - length * 0.21, 0, 1.25), wood,
                        rotation=(0, 90, 0), segments=10)
    boom.parent = root
    sail = kit.cylinder(f'Sailboat {n} furled sail', 0.12, length * 0.38, (mast_x - length * 0.2, 0, 1.37), canvas,
                        rotation=(0, 90, 0), segments=12, radius_top=0.07)
    sail.parent = root
    top = (mast_x, 0, mast_h + 0.3)
    for name, end in (('forestay', (length * 0.5, 0, 0.6)), ('backstay', (-length * 0.5, 0, 0.45)),
                      ('port shroud', (mast_x - 0.2, -length * 0.16, 0.5)),
                      ('starboard shroud', (mast_x - 0.2, length * 0.16, 0.5))):
        stay = kit.tube(f'Sailboat {n} {name}', [top, end], 0.012, rope)
        stay.parent = root
    root.rotation_euler = (0, 0, math.radians(heading))
    # Moored boats rock a little; each on its own phase.
    kit.animate(root, 'rotation_euler', lambda t, h=heading, p=n: (
        math.radians(1.6) * math.sin(math.tau * (0.55 * t * kit.seconds / 3) + p),
        math.radians(0.8) * math.sin(math.tau * (0.4 * t * kit.seconds / 3) + 2 * p), math.radians(h)), step=2)
    return root


def build(kit):
    # ---------------------------------------------------------------- night sky: a dim gradient
    kit.world('#010205', strength=1.0, top='#060B1A')

    # ---------------------------------------------------------------- water
    water = kit.plane('Harbor water', (1600, 1600), (0, 400, 0), material=water_material(kit), ground=True)

    # ---------------------------------------------------------------- far shore and breakwater
    land = kit.material('Shore rock', '#07080A', roughness=0.9)
    kit.terrain('Far hills', size=900, resolution=120, height=55, roughness=0.55, scale=0.006, seed=4,
                material=land, location=(0, 700, -8), ground=False)
    wall = kit.procedural('Breakwater stone', 'stone', colors=['#16171A', '#202226', '#2A2C30'], scale=0.4)
    kit.box('Breakwater', (420, 9, 4.5), (-40, 330, 1.2), wall, bevel=0.6)
    tower = kit.material('Lighthouse paint', '#2B2D33', roughness=0.6)
    kit.cylinder('Lighthouse', 2.2, 16, (-150, 330, 11), tower, radius_top=1.6, segments=24)
    kit.cylinder('Lighthouse lantern room', 1.9, 2.5, (-150, 330, 20.3), tower, segments=16)
    kit.box('Launch barge', (34, 12, 2.0), (0, SHOW_Y, 0.4), kit.material('Barge', '#101114', roughness=0.7),
            bevel=0.3)

    # ---------------------------------------------------------------- moored boats (silhouettes)
    mats = (kit.material('Hull paint', '#1B1E24', roughness=0.25, coat=0.6),
            kit.procedural('Boat timber', 'wood', colors=['#2A1E16', '#3A2A1E', '#4A3626'], scale=3.0),
            kit.material('Rigging', '#151515', roughness=0.6),
            kit.procedural('Sail cover', 'fabric', colors=['#2C3138', '#363C44', '#3E444C'], scale=1.0))
    for n, (x, y, length, heading, mast_h) in enumerate(((-9.0, 26.0, 9.0, 18, 12.0), (7.0, 44.0, 11.0, -10, 14.5),
                                                        (-24.0, 62.0, 8.0, 30, 10.5), (22.0, 78.0, 10.0, 5, 13.0),
                                                        (-2.0, 105.0, 12.0, -20, 15.0)), start=1):
        sailboat(kit, n, (x, y, 0.25), length, heading, mats, mast_h)

    # ---------------------------------------------------------------- the quay we stand on
    planks = kit.procedural('Quay planks', 'wood', colors=['#1D1712', '#2A2019', '#352A20'], scale=1.5)
    for i in range(14):
        kit.box(f'Quay plank {i + 1}', (0.28, 7.0, 0.09), (CAM_AT.x - 3.8 + i * 0.3, -1.6, 0.95), planks,
                rotation=(0, 0, kit.rng.uniform(-0.6, 0.6)), bevel=0.012)
    pile = kit.procedural('Pile timber', 'bark', colors=['#16110D', '#211A14', '#2B221A'], scale=1.5)
    for i, x in enumerate((CAM_AT.x - 3.6, CAM_AT.x + 0.6)):
        kit.cylinder(f'Quay pile {i + 1}', 0.16, 3.2, (x, 1.8, 0.0), pile, segments=16, bevel=0.02)
    iron = kit.material('Bollard iron', '#1A1C1F', roughness=0.45, metallic=0.8)
    kit.lathe('Bollard', [(0, 0), (0.17, 0), (0.15, 0.08), (0.11, 0.35), (0.16, 0.45), (0.13, 0.5), (0, 0.5)],
              material=iron, location=(CAM_AT.x - 2.2, 1.2, 1.0))
    kit.tube('Mooring line', [(CAM_AT.x - 2.2, 1.2, 1.35), (CAM_AT.x - 4.5, 8.0, 0.4), (-9.0, 22.0, 1.2)], 0.025,
             kit.material('Mooring rope', '#3A3128', roughness=0.9))

    # ---------------------------------------------------------------- the show
    for n, (launch, burst, at, colour, count, speed) in enumerate(SHELLS, start=1):
        shell(kit, n, launch, burst, at, colour, count, speed)
    # A thin layer of smoke and haze over the water catches each flash.
    kit.haze(density=0.0009, color='#AFB6C8', anisotropy=0.5, size=(900, 900, 260), location=(0, 300, 120))

    # ---------------------------------------------------------------- camera: static, slow tilt up
    cam = kit.camera(location=CAM_AT, target=(0.0, SHOW_Y, 18.0), lens=22.0)
    kit.dolly(cam, CAM_AT, CAM_AT, target_start=(0.0, SHOW_Y, 18.0), target_end=(0.0, SHOW_Y, 62.0),
              ease_kind='in_out', power=2.0)
    kit.render(exposure=0.6, look='AgX - Medium High Contrast', shutter=0.9, volume_step=4.0)
