"""Alpine lake at sunrise: a low, fast skim over still water toward pink-lit snow peaks.

Teaches
- One analytic heightfield for the whole valley (lake basin, forested shores, ridged massif),
  sampled on a non-uniform grid so metres of detail sit near the lens and kilometres far away.
- A slope- and altitude-driven terrain shader (forest floor, rock, snow) with fake aerial
  perspective from the camera distance, so 8 km of mountains read as depth without a huge volume.
- Physical sky at 3 degrees sun elevation plus a matching warm sun lamp: the sun sits behind the
  camera, so the peaks catch alpenglow and the sky ahead shows the pink anti-twilight band.
- Instanced pines with per-instance colour variation (Object Info > Random), placed from the
  same height function instead of ray casts.
- A thin volumetric mist slab whose noise density drifts over time (keyed mapping offset).
"""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector, noise

# ---------------------------------------------------------------- constants (metres, degrees)
LAKE_HALF_WIDTH = 520.0        # shore to shore at the camera end is ~1 km
WALL_HEIGHT = 650.0            # valley walls saturate around this height
LAKE_NEAR_END = -680.0         # rear shoreline, behind the drone at the start
LAKE_FAR_END = 2600.0          # far shore, where the valley climbs into the massif
MASSIF_Y = 7200.0              # centre line of the big snow peaks
MASSIF_HEIGHT = 1100.0         # ridge height above the lake surface
SUMMITS = [(-700, 7600, 880, 900), (1500, 8300, 700, 800)]   # (x, y, extra height, radius)
SPIT = (-150, 330)              # forested spit reaching into the lake
SPIT_HEIGHT = 13.0
SNOW_LINE = 640.0              # snow starts here (noisy, slope dependent)
TREE_LINE = 520.0              # no pines above this
SUN_ELEVATION = 3.0            # sunrise: long shadows, pink light
SUN_AZIMUTH = 128.0            # behind the camera's right shoulder: side light carves the ridges
CAM_X = -380.0                 # ~150 m off the left shore
CAM_HEIGHT = 1.7               # skimming height above the water
CAM_TRAVEL = 150.0             # metres covered in the shot (~25 m/s, a fast drone skim)
MIST_TOP = 8.0                 # top of the mist layer


def smoothstep(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def height(x, y):
    """Valley height in metres; the lake surface is z = 0."""
    # Wobbly shoreline: the lake half-width varies with y and with low-frequency noise.
    half = shore_half_width(x, y)
    side = abs(x) - half                         # metres beyond the side shore
    end = max(y - LAKE_FAR_END, LAKE_NEAR_END - y) * .3
    beyond = max(side, end, -60.0)
    if beyond < 0:
        # Lake bed shelving down from the shore, plus one forested spit that gives the
        # camera a midground to pass (a Gaussian mound that breaks the water line).
        spit = SPIT_HEIGHT * math.exp(-(((x - SPIT[0]) / 85) ** 2 + ((y - SPIT[1]) / 300) ** 2)) - 3
        return max(beyond * .31, spit)
    # Shore apron, then valley walls that steepen and saturate around WALL_HEIGHT.
    base = beyond * .09 + max(0.0, beyond - 50) ** 1.35 * .055
    walls = WALL_HEIGHT * (1 - math.exp(-base / WALL_HEIGHT))
    p = Vector((x * .0011, y * .0011, 3.1))
    ridges = noise.ridged_multi_fractal(p, 1.0, 2.0, 7, 1.0, 2.0, noise_basis='PERLIN_NEW') * .5
    walls *= .55 + .8 * ridges
    # The massif: a band of ridged peaks across the valley head.
    band = math.exp(-((y - MASSIF_Y) / 1900) ** 2) * smoothstep(LAKE_FAR_END + 1000, LAKE_FAR_END + 3600, y)
    q = Vector((x * .00045, y * .00045, 8.4))
    peaks = noise.ridged_multi_fractal(q, .85, 2.1, 8, 1.0, 2.2, noise_basis='PERLIN_NEW') * .5
    # Squaring the ridged value sharpens crests into aretes and deepens the cols between them.
    massif = MASSIF_HEIGHT * band * (.2 + 1.1 * peaks * peaks) * (1 - .35 * smoothstep(1500, 4500, abs(x)))
    # Two named summits anchor the composition (left of centre, and a lower one right).
    for px, py, ph, pr in SUMMITS:
        d2 = ((x - px) ** 2 + (y - py) ** 2) / (pr * pr)
        massif += ph * math.exp(-d2) * (.7 + .5 * peaks)
    # Gullies and spurs at ~150 m, fading in away from the shore so beaches stay smooth.
    gully = 45 * noise.fractal(Vector((x * .007, y * .007, 5.0)), .7, 2.0, 5) * smoothstep(20, 300, beyond)
    return walls + massif + gully


def shore_half_width(x, y):
    wobble = 90 * noise.noise(Vector((x * .0025, y * .0025, 1.7))) + 50 * math.sin(y * .0021)
    width = LAKE_HALF_WIDTH + wobble + 220 * smoothstep(0, 1600, y)
    rear_curve = smoothstep(LAKE_NEAR_END, LAKE_NEAR_END + 440, y)
    far_inlet = 1.0 - smoothstep(LAKE_FAR_END - 880, LAKE_FAR_END, y)
    return 42 + (width - 42) * rear_curve * far_inlet


def terrain_mesh(kit, mat):
    """Non-uniform grid: columns crowd toward x = 0, rows toward the camera."""
    cols, rows = 520, 460
    xs = [math.copysign(6500 * abs(u) ** 2.1, u) for u in (2 * i / cols - 1 for i in range(cols + 1))]
    ys = [-900 + 11500 * (j / rows) ** 2.0 for j in range(rows + 1)]
    verts = [(x, y, height(x, y)) for y in ys for x in xs]
    faces = []
    for j in range(rows):
        for i in range(cols):
            a = j * (cols + 1) + i
            faces.append((a, a + 1, a + cols + 2, a + cols + 1))
    return kit.mesh('Valley terrain', verts, faces, mat, smooth=True, ground=True)


def terrain_material(kit):
    """Forest floor / rock / snow from slope and altitude, faded toward the sky with distance."""
    mat = kit.material('Valley terrain', '#3A3A36', roughness=.9)
    nt, bs = mat.node_tree, kit.bsdf(mat)
    N, L = nt.nodes, nt.links
    geo = N.new('ShaderNodeNewGeometry')
    sep_p = N.new('ShaderNodeSeparateXYZ'); L.new(geo.outputs['Position'], sep_p.inputs[0])
    sep_n = N.new('ShaderNodeSeparateXYZ'); L.new(geo.outputs['Normal'], sep_n.inputs[0])

    def node_noise(scale, detail=8.0, rough=.6):
        n = N.new('ShaderNodeTexNoise')
        n.inputs['Scale'].default_value, n.inputs['Detail'].default_value = scale, detail
        n.inputs['Roughness'].default_value = rough
        L.new(geo.outputs['Position'], n.inputs['Vector'])
        return n.outputs['Fac']

    def math_node(op, a, b=None):
        m = N.new('ShaderNodeMath'); m.operation = op
        for k, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                m.inputs[k].default_value = v
            else:
                L.new(v, m.inputs[k])
        return m.outputs[0]

    def mix(fac, a, b):
        m = N.new('ShaderNodeMix'); m.data_type = 'RGBA'
        L.new(fac, m.inputs['Factor'])
        for sock, v in ((m.inputs['A'], a), (m.inputs['B'], b)):
            if isinstance(v, str):
                sock.default_value = kit.color(v)
            else:
                L.new(v, sock)
        return m.outputs['Result']

    def ramp(value, lo, hi):
        m = N.new('ShaderNodeMapRange'); m.interpolation_type = 'SMOOTHSTEP'
        L.new(value, m.inputs['Value'])
        m.inputs['From Min'].default_value, m.inputs['From Max'].default_value = lo, hi
        return m.outputs['Result']

    big = node_noise(.004, 6)          # 250 m patches: geology and forest density
    mid = node_noise(.05, 8)           # 20 m: scree, clearings
    fine = node_noise(1.5, 10)         # surface grain
    # Rock: three tones driven by noise at two scales.
    rock = mix(math_node('MULTIPLY', big, 1.6), '#4B4743', '#7C756C')
    rock = mix(math_node('MULTIPLY', fine, .8), rock, '#2E2B28')
    # Forest floor seen from afar: dark conifer green with mossy patches.
    forest = mix(mid, '#16231A', '#2F3B22')
    # Altitude/slope masks with noise so edges break up.
    slope = sep_n.outputs['Z']
    jitter = math_node('ADD', math_node('MULTIPLY', math_node('SUBTRACT', big, .5), 260),
                       math_node('MULTIPLY', math_node('SUBTRACT', mid, .5), 60))
    alt = math_node('ADD', sep_p.outputs['Z'], jitter)
    # Soft masks (smoothstep ranges, never hard thresholds) avoid a camouflage pattern.
    forest_mask = math_node('MULTIPLY', ramp(alt, TREE_LINE + 160, TREE_LINE + 40), ramp(slope, .66, .8))
    snow_mask = math_node('MULTIPLY', ramp(alt, SNOW_LINE - 80, SNOW_LINE + 80),
                          ramp(math_node('ADD', slope, math_node('MULTIPLY', fine, .2)), .62, .78))
    col = mix(forest_mask, rock, forest)
    col = mix(snow_mask, col, '#E9EDF4')
    rough = math_node('ADD', .55, math_node('MULTIPLY', math_node('SUBTRACT', 1.0, snow_mask), .37))
    L.new(rough, bs.inputs['Roughness'])
    # Aerial perspective: blend toward a cool sky tone with view distance (km scale).
    cam = N.new('ShaderNodeCameraData')
    fog = math_node('MULTIPLY', math_node('SUBTRACT', 1.0, math_node('EXPONENT', math_node('MULTIPLY', cam.outputs['View Distance'], -1 / 9000))), .55)
    col = mix(fog, col, '#8C93A8')
    L.new(col, bs.inputs['Base Color'])
    # Snow scatters light a little; rock gets a coarse bump.
    bs.inputs['Subsurface Weight'].default_value = .0
    bump = N.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = .35
    L.new(math_node('ADD', mid, math_node('MULTIPLY', fine, .3)), bump.inputs['Height'])
    L.new(bump.outputs['Normal'], bs.inputs['Normal'])
    return mat


def water_material(kit):
    """Dark, glassy lake: almost all you see is Fresnel reflection. A faint, slowly moving
    ripple bump keeps the reflection alive without breaking the mirror."""
    mat = kit.material('Lake water', '#050A0C', roughness=.015, ior=1.333, specular=.5)
    nt, bs = mat.node_tree, kit.bsdf(mat)
    coord = nt.nodes.new('ShaderNodeTexCoord')
    mapping = nt.nodes.new('ShaderNodeMapping')
    mapping.inputs['Scale'].default_value = (.35, 1.4, 1)          # ripples elongated across view
    nt.links.new(coord.outputs['Object'], mapping.inputs['Vector'])
    ripple = nt.nodes.new('ShaderNodeTexNoise')
    ripple.noise_dimensions = '4D'
    ripple.inputs['Scale'].default_value = .9
    ripple.inputs['Detail'].default_value = 6
    nt.links.new(mapping.outputs['Vector'], ripple.inputs['Vector'])
    kit.animate(ripple.inputs['W'], 'default_value', lambda t: t * 1.2)
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = .035
    nt.links.new(ripple.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bs.inputs['Normal'])
    return mat


def pine_mesh(kit, name, h, seed):
    """A conifer: tapered trunk plus stacked, drooping star-shaped tiers of needles."""
    rng = random.Random(seed)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=7, radius1=h * .016, radius2=h * .004, depth=h,
                          matrix=Matrix.Translation((0, 0, h / 2)))
    tiers = 11
    for k in range(tiers):
        f = k / (tiers - 1)
        z0 = h * (.16 + .8 * f)                   # tier top
        r = h * (.24 * (1 - f) ** 1.1 + .03)      # wide at the bottom, narrow at the crown
        droop = r * .55
        spikes = 9 - k // 3
        apex = bm.verts.new((0, 0, z0 + r * .15))
        ring = []
        for s in range(spikes * 2):
            a = math.tau * s / (spikes * 2) + rng.uniform(-.12, .12)
            rr = r * (1.0 if s % 2 == 0 else .55) * rng.uniform(.85, 1.1)
            ring.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), z0 - droop * (rr / r))))
        for s in range(len(ring)):
            bm.faces.new((apex, ring[s], ring[(s + 1) % len(ring)]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    obj = bpy.data.objects.new(name, me)
    kit.collection('Pine prototypes').objects.link(obj)
    return obj


def pine_material(kit):
    """Needle green with per-instance hue/value jitter: Object Info > Random drives a ramp."""
    mat = kit.material('Pine needles', '#13221A', roughness=.8)
    nt, bs = mat.node_tree, kit.bsdf(mat)
    info = nt.nodes.new('ShaderNodeObjectInfo')
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    for el, (pos, col) in zip(ramp.color_ramp.elements, ((0, '#0C1A12'), (1, '#22351E'))):
        el.position, el.color = pos, kit.color(col)
    mid = ramp.color_ramp.elements.new(.5); mid.color = kit.color('#16281A')
    nt.links.new(info.outputs['Random'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], bs.inputs['Base Color'])
    return mat


def build(kit):
    # --- terrain and lake -------------------------------------------------------------------
    terrain_mesh(kit, terrain_material(kit))
    # The ground intersects the water everywhere around the tapered, closed basin.
    length = LAKE_FAR_END - LAKE_NEAR_END + 300
    kit.plane('Lake surface', (2200, length), (0, (LAKE_NEAR_END + LAKE_FAR_END) / 2, 0),
              water_material(kit), ground=True)

    # --- forest: pines on gentle shore slopes, denser near the water ------------------------
    needles = pine_material(kit)
    protos = [pine_mesh(kit, f'Pine prototype {i}', 24.0, 40 + i) for i in range(4)]
    for p in protos:
        p.data.materials.append(needles)
        p.hide_render = True
        p.location = (0, 0, -5000)
    rng = kit.rng
    placed = 0
    forest = kit.collection('Forest')
    for _ in range(30000):
        if placed >= 4200:
            break
        # Sample a band hugging the shoreline so the forest reads as a dense dark fringe.
        y = rng.uniform(-500, 3000)
        side = rng.choice((-1, 1))
        x = side * (shore_half_width(side * LAKE_HALF_WIDTH, y) + 900 * rng.random() ** 1.6 - 20)
        z = height(x, y)
        if not (1.0 < z < TREE_LINE):
            continue
        # slope from finite differences: skip cliffs
        dzx = (height(x + 4, y) - z) / 4
        dzy = (height(x, y + 4) - z) / 4
        if dzx * dzx + dzy * dzy > .55:
            continue
        # density falls off away from the shoreline, so the lake edge reads as a dark band
        if rng.random() > 1.25 - z / 300:
            continue
        s = rng.uniform(.55, 1.35)
        kit.instance(rng.choice(protos), (x, y, z - .5), (rng.uniform(-3, 3), rng.uniform(-3, 3), rng.uniform(0, 360)),
                     (s, s, s * rng.uniform(.9, 1.2)), name=f'Pine {placed:04d}', collection=forest)
        placed += 1
    # A tight stand on the spit: the nearest trees in the shot.
    for i in range(150):
        x, y = SPIT[0] + rng.gauss(0, 38), SPIT[1] + rng.gauss(0, 140)
        z = height(x, y)
        if z < 1.5:
            continue
        s = rng.uniform(.8, 1.5)
        kit.instance(rng.choice(protos), (x, y, z - .4), (0, 0, rng.uniform(0, 360)), (s, s, s),
                     name=f'Spit pine {i:02d}', collection=forest)
        placed += 1
    kit.note(f'placed {placed} pines')

    # --- shoreline boulders: mid-scale detail where the camera passes closest ---------------
    boulder_mat = kit.procedural('Shore granite', 'stone', colors=['#3F3D3A', '#6B665E', '#8E877B'], scale=.6, bump=.5)
    for i in range(40):
        side = -1 if i % 2 else 1
        y = rng.uniform(-250, 900)
        x = side * (shore_half_width(side * LAKE_HALF_WIDTH, y) + rng.uniform(-14, 6))
        kit.rock(f'Shore boulder {i}', rng.uniform(1.2, 4.5), (x, y, rng.uniform(-.8, .3)), boulder_mat,
                 seed=rng.random() * 90, squash=.55)

    # --- light: physical sunrise sky plus a matching sun lamp ------------------------------
    kit.sky(sun_elevation=SUN_ELEVATION, sun_rotation=SUN_AZIMUTH, strength=.22, sun_disc=False,
            air=1.2, aerosol=2.6, ozone=2.0)   # extra ozone/aerosol: violet-pink twilight
    kit.sun(elevation=SUN_ELEVATION, azimuth=SUN_AZIMUTH, strength=5.0, color='#FF9A86', angle=.6)

    # --- mist: thin drifting volume over the water ------------------------------------------
    mist = kit.box('Lake mist', (1100, 3000, MIST_TOP), (0, 1100, MIST_TOP / 2))
    mist['studio_volume'] = True
    mist.visible_shadow = False
    mm = bpy.data.materials.new('Lake mist'); mm.use_nodes = True
    nt = mm.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    vol = nt.nodes.new('ShaderNodeVolumePrincipled')
    vol.inputs['Color'].default_value = kit.color('#F4E6E8')
    vol.inputs['Anisotropy'].default_value = .5
    coord = nt.nodes.new('ShaderNodeTexCoord')
    mapping = nt.nodes.new('ShaderNodeMapping')
    mapping.inputs['Scale'].default_value = (.012, .006, .12)   # long, low banks of mist
    nt.links.new(coord.outputs['Object'], mapping.inputs['Vector'])
    # drift: slide the noise sideways and a little forward over the shot
    kit.animate(mapping.inputs['Location'], 'default_value', lambda t: (t * .5, t * .15, 0))
    tex = nt.nodes.new('ShaderNodeTexNoise')
    tex.inputs['Detail'].default_value = 5
    tex.inputs['Scale'].default_value = 3.0
    nt.links.new(mapping.outputs['Vector'], tex.inputs['Vector'])
    banks = nt.nodes.new('ShaderNodeMapRange')            # carve gaps between mist banks
    banks.inputs['From Min'].default_value, banks.inputs['From Max'].default_value = .5, .78
    nt.links.new(tex.outputs['Fac'], banks.inputs['Value'])
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(coord.outputs['Object'], sep.inputs[0])
    fall = nt.nodes.new('ShaderNodeMapRange')             # densest at the water, gone by MIST_TOP
    fall.inputs['From Min'].default_value, fall.inputs['From Max'].default_value = -MIST_TOP / 2, MIST_TOP / 2
    fall.inputs['To Min'].default_value, fall.inputs['To Max'].default_value = 1.0, 0.0
    fall.interpolation_type = 'SMOOTHSTEP'
    nt.links.new(sep.outputs['Z'], fall.inputs['Value'])
    dens = nt.nodes.new('ShaderNodeMath'); dens.operation = 'MULTIPLY'
    nt.links.new(banks.outputs['Result'], dens.inputs[0]); nt.links.new(fall.outputs['Result'], dens.inputs[1])
    scale = nt.nodes.new('ShaderNodeMath'); scale.operation = 'MULTIPLY'; scale.inputs[1].default_value = .028
    nt.links.new(dens.outputs[0], scale.inputs[0])
    nt.links.new(scale.outputs[0], vol.inputs['Density'])
    nt.links.new(vol.outputs[0], out.inputs['Volume'])
    mist.data.materials.append(mm)

    # --- camera: low skim toward the massif, gently rising, slight drift right --------------
    # Hug the left (shaded) shore so its pines read as silhouettes; aim between the summits.
    # The ultrawide frame needs vertical breathing room for both the summit and its reflection.
    cam = kit.camera((CAM_X, -160, CAM_HEIGHT), (100, MASSIF_Y, 5), lens=22, clip=(.1, 20000))
    kit.path(cam, [(CAM_X, -160, CAM_HEIGHT), (CAM_X + 12, -160 + CAM_TRAVEL * .5, CAM_HEIGHT + .3),
                   (CAM_X + 30, -160 + CAM_TRAVEL, CAM_HEIGHT + .9)],
             targets=[(60, MASSIF_Y, 5), (200, MASSIF_Y, 25)], ease_kind='in_out', power=1.6)
    kit.handheld(cam, amount=.25, cycles=1, seed=5)   # a whisper of drone wobble

    kit.render(exposure=1.1, look='AgX - Medium High Contrast', volume_step=4, motion_blur=True, shutter=.35)
