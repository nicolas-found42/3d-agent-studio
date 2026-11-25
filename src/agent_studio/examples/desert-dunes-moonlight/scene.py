"""Desert dunes under a full moon: a warm campfire and glowing tent in a cold blue night.

Teaches:
- a sculpted heightfield (asymmetric dune profile with a sharp crest and a steep slip face,
  domain-warped so the crests curve) on a non-uniform grid: dense near the camera, coarse far away;
- a procedural night sky in the world shader: gradient, moon glow, a Milky Way band and two
  Voronoi star layers, so the starfield lights nothing but reads as dense;
- moonlight as a weak, cool sun plus a visible emissive moon disc placed on the same direction;
- a warm practical (campfire) whose flames and light flicker from kit.loop_noise;
- painterly Freestyle ink: relative thickness, tapered strokes, Perlin wobble, distance fade,
  and an exclusion collection so flames, sand veils and grains are not outlined;
- drifting sand as both baked particles (grains) and scrolling alpha "streamer" cards.
"""
import math

import bpy
from mathutils import Matrix, Vector

# ---------------------------------------------------------------- constants (metres, degrees)
CAMP = Vector((0.0, 0.0, 0.0))          # campfire centre
TENT_AT = Vector((-1.8, 2.8, 0.0))      # tent centre, behind and left of the fire
CAM_AT = Vector((-3.5, -8.5, 1.4))      # eye height ~9 m from the fire: the camp fills the lower third
# Aim: yaw 15 deg (from +Y toward +X), pitch +5.7 deg, so the fire sits on the lower-third line
# right of centre, the tent left of it, and the moon high on the upper left.
CAM_LOOK = CAM_AT + 200.0 * Vector((math.sin(math.radians(15)), math.cos(math.radians(15)), math.tan(math.radians(5.7))))
CAM_LENS = 30.0
MOON_ELEVATION, MOON_AZIMUTH = 27.0, 6.0  # azimuth from +Y toward +X: in frame, upper left; backlights the crests
DUNE_PERIOD = 70.0                       # crest-to-crest spacing of the big dunes
WIND = Vector((1.0, 0.25, 0.0)).normalized()  # wind blows sand toward +X
INK = '#17182A'                          # deep indigo ink, never pure black


def smoothstep(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def dune_height(kit, x, y):
    """Asymmetric dune field: long windward slopes, sharp crests, short steep slip faces."""
    # Domain warp bends the straight ridges into crescents.
    warp = 26.0 * kit.noise(x * 0.008, y * 0.008, 1.7, octaves=2)
    # Crests run diagonally across the view, so the moon (front-left) lights the slip faces and
    # leaves the windward slopes in shadow: the light/shadow split is what models a dune.
    u = x * 0.72 + y * 0.69 + warp
    phase = (u / DUNE_PERIOD) % 1.0
    crest = 0.78
    # Cosine halves have zero slope at the crest and the trough, so crests are rounded rather than
    # razor edges (a razor crest on a coarse far grid zigzags and reads as a row of trees).
    if phase < crest:
        profile = 0.5 - 0.5 * math.cos(math.pi * phase / crest)              # long windward slope
    else:
        profile = 0.5 + 0.5 * math.cos(math.pi * (phase - crest) / (1 - crest))  # short slip face
    d = math.hypot(x - CAMP.x, y - CAMP.y)
    # Dunes grow with distance, so from a low camera each ridge peeks over the one before it:
    # layered silhouettes instead of one near slope hiding everything.
    amplitude = min(42.0, 3.0 + 0.0012 * d * d) * (1 + 0.3 * kit.noise(x * 0.004, y * 0.004, 4.2, octaves=2))
    swell = 2.5 * kit.noise(x * 0.012, y * 0.012, 9.1, octaves=3)
    ripple = 0.08 * math.sin(u * 2.4 + 3 * kit.noise(x * 0.2, y * 0.2, 2.0, octaves=1))
    h = amplitude * profile + swell + ripple
    # Keep a gentle hollow around the camp: dunes rise only beyond ~15 m.
    keep = smoothstep(14.0, 40.0, d)
    # The camp itself (within ~3 m) is level at z=0 so props sit on the sand.
    near = smoothstep(3.0, 14.0, d) * (0.25 * kit.noise(x * 0.15, y * 0.15, 5.0, octaves=2) + 0.03 * d)
    return keep * h + (1 - keep) * near


def build_dunes(kit, sand):
    # Non-uniform grid: s in -1..1 mapped with a power curve gives ~10 cm cells at the camp
    # and ~7 m cells at the horizon, for ~90k vertices instead of millions.
    n = 300
    def axis(s, lo, hi, centre):
        span = hi - centre if s >= 0 else centre - lo
        return centre + math.copysign(abs(s) ** 1.6 * span, s)
    verts = []
    for j in range(n + 1):
        y = axis(j / n * 2 - 1, -60.0, 720.0, 0.0)
        for i in range(n + 1):
            x = axis(i / n * 2 - 1, -380.0, 380.0, 0.0)
            verts.append((x, y, dune_height(kit, x, y)))
    faces = []
    for j in range(n):
        for i in range(n):
            a = j * (n + 1) + i
            faces.append((a, a + 1, a + n + 2, a + n + 1))
    return kit.mesh('Dune field', verts, faces, sand, smooth=True, ground=True)


def sand_material(kit):
    """Warm sand that turns blue under the moon: wind ripples as bump, slope-darkened slip faces."""
    mat = kit.material('Moonlit sand', '#C8A27A', roughness=0.92, specular=0.3)
    nt, bs = mat.node_tree, kit.bsdf(mat)
    coord = nt.nodes.new('ShaderNodeTexCoord')
    # Ripples: a band wave perpendicular to the wind, distorted so lines wander like real ripples.
    ripples = nt.nodes.new('ShaderNodeTexWave')
    ripples.wave_type, ripples.bands_direction = 'BANDS', 'X'
    ripples.inputs['Scale'].default_value = 1.6
    ripples.inputs['Distortion'].default_value = 6.0
    ripples.inputs['Detail'].default_value = 3.0
    ripples.inputs['Detail Scale'].default_value = 0.6
    nt.links.new(coord.outputs['Object'], ripples.inputs['Vector'])
    grain = nt.nodes.new('ShaderNodeTexNoise')
    grain.inputs['Scale'].default_value = 140.0
    grain.inputs['Detail'].default_value = 4.0
    nt.links.new(coord.outputs['Object'], grain.inputs['Vector'])
    mix_h = nt.nodes.new('ShaderNodeMath')
    mix_h.operation = 'MULTIPLY_ADD'
    nt.links.new(grain.outputs['Fac'], mix_h.inputs[0])
    mix_h.inputs[1].default_value = 0.25
    nt.links.new(ripples.outputs['Fac'], mix_h.inputs[2])
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.35
    bump.inputs['Distance'].default_value = 0.02
    nt.links.new(mix_h.outputs[0], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bs.inputs['Normal'])
    # Colour: large-scale tonal variation plus slightly darker, redder steep faces.
    tone = nt.nodes.new('ShaderNodeTexNoise')
    tone.inputs['Scale'].default_value = 0.05
    nt.links.new(coord.outputs['Object'], tone.inputs['Vector'])
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(geo.outputs['Normal'], sep.inputs[0])
    steep = nt.nodes.new('ShaderNodeMath')
    steep.operation = 'MULTIPLY_ADD'
    nt.links.new(sep.outputs['Z'], steep.inputs[0])
    steep.inputs[1].default_value = 0.6
    nt.links.new(tone.outputs['Fac'], steep.inputs[2])
    ramp = kit._ramp(nt, [(0.0, '#6E5C4E'), (0.75, '#9C8670'), (1.3, '#B5A086')])  # muted: the moon and fire tint it
    nt.links.new(steep.outputs[0], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], bs.inputs['Base Color'])
    return mat


def night_sky(kit, moon_dir):
    """World: dark gradient, moon glow, Milky Way band, two star layers (only camera rays see stars)."""
    world, nt, bg = kit._world()
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_WORLD')
    coord = nt.nodes.new('ShaderNodeTexCoord')
    dirv = coord.outputs['Generated']          # in a world shader this is the view direction
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(dirv, sep.inputs[0])
    grad = kit._ramp(nt, [(0.0, '#2A3A5C'), (0.12, '#14213D'), (0.5, '#070C1C'), (1.0, '#03050D')])
    nt.links.new(sep.outputs['Z'], grad.inputs['Fac'])
    # Moon glow: dot(view, moon) sharpened with a power.
    dot = nt.nodes.new('ShaderNodeVectorMath')
    dot.operation = 'DOT_PRODUCT'
    nt.links.new(dirv, dot.inputs[0])
    dot.inputs[1].default_value = moon_dir
    glow = nt.nodes.new('ShaderNodeMath')
    glow.operation = 'POWER'
    nt.links.new(dot.outputs['Value'], glow.inputs[0])
    glow.inputs[1].default_value = 60.0
    glow_col = nt.nodes.new('ShaderNodeMix')
    glow_col.data_type, glow_col.blend_type = 'RGBA', 'ADD'
    nt.links.new(glow.outputs[0], glow_col.inputs['Factor'])
    nt.links.new(grad.outputs['Color'], glow_col.inputs['A'])
    glow_col.inputs['B'].default_value = kit.color('#3D5688')

    def stars(scale, size, gate):
        vor = nt.nodes.new('ShaderNodeTexVoronoi')
        vor.inputs['Scale'].default_value = scale
        vor.inputs['Randomness'].default_value = 1.0
        nt.links.new(dirv, vor.inputs['Vector'])
        core = nt.nodes.new('ShaderNodeMapRange')
        core.inputs['From Min'].default_value, core.inputs['From Max'].default_value = size, 0.0
        nt.links.new(vor.outputs['Distance'], core.inputs['Value'])
        # Each cell's random colour gates whether it holds a star and how bright it is.
        rnd = nt.nodes.new('ShaderNodeSeparateColor')
        nt.links.new(vor.outputs['Color'], rnd.inputs[0])
        keep = nt.nodes.new('ShaderNodeMath')
        keep.operation = 'GREATER_THAN'
        nt.links.new(rnd.outputs[0], keep.inputs[0])
        keep.inputs[1].default_value = gate
        m1 = nt.nodes.new('ShaderNodeMath')
        m1.operation = 'MULTIPLY'
        nt.links.new(core.outputs['Result'], m1.inputs[0])
        nt.links.new(keep.outputs[0], m1.inputs[1])
        m2 = nt.nodes.new('ShaderNodeMath')
        m2.operation = 'MULTIPLY'
        nt.links.new(m1.outputs[0], m2.inputs[0])
        nt.links.new(rnd.outputs[1], m2.inputs[1])
        return m2
    fine = stars(160.0, 0.2, 0.5)
    bright = stars(48.0, 0.09, 0.8)
    # Milky Way: a soft band of cloudy noise across the sky.
    band_dot = nt.nodes.new('ShaderNodeVectorMath')
    band_dot.operation = 'DOT_PRODUCT'
    nt.links.new(dirv, band_dot.inputs[0])
    band_dot.inputs[1].default_value = Vector((0.75, -0.25, 0.6)).normalized()
    band_abs = nt.nodes.new('ShaderNodeMath')
    band_abs.operation = 'ABSOLUTE'
    nt.links.new(band_dot.outputs['Value'], band_abs.inputs[0])
    band = nt.nodes.new('ShaderNodeMapRange')
    band.inputs['From Min'].default_value, band.inputs['From Max'].default_value = 0.16, 0.0
    nt.links.new(band_abs.outputs[0], band.inputs['Value'])
    clouds = nt.nodes.new('ShaderNodeTexNoise')
    clouds.inputs['Scale'].default_value = 7.0
    clouds.inputs['Detail'].default_value = 8.0
    nt.links.new(dirv, clouds.inputs['Vector'])
    band_m = nt.nodes.new('ShaderNodeMath')
    band_m.operation = 'MULTIPLY'
    nt.links.new(band.outputs['Result'], band_m.inputs[0])
    nt.links.new(clouds.outputs['Fac'], band_m.inputs[1])
    # Sum the layers, mask below the horizon and fade near it (extinction).
    total = nt.nodes.new('ShaderNodeMath')
    total.operation = 'ADD'
    nt.links.new(fine.outputs[0], total.inputs[0])
    nt.links.new(bright.outputs[0], total.inputs[1])
    total2 = nt.nodes.new('ShaderNodeMath')
    total2.operation = 'MULTIPLY_ADD'
    nt.links.new(band_m.outputs[0], total2.inputs[0])
    total2.inputs[1].default_value = 0.16
    nt.links.new(total.outputs[0], total2.inputs[2])
    horizon = nt.nodes.new('ShaderNodeMapRange')
    horizon.inputs['From Min'].default_value, horizon.inputs['From Max'].default_value = 0.02, 0.25
    nt.links.new(sep.outputs['Z'], horizon.inputs['Value'])
    masked = nt.nodes.new('ShaderNodeMath')
    masked.operation = 'MULTIPLY'
    nt.links.new(total2.outputs[0], masked.inputs[0])
    nt.links.new(horizon.outputs['Result'], masked.inputs[1])
    # Stars are sub-pixel at preview size: boost them above 1 so they survive pixel filtering.
    boosted = nt.nodes.new('ShaderNodeMath')
    boosted.operation = 'MULTIPLY'
    nt.links.new(masked.outputs[0], boosted.inputs[0])
    boosted.inputs[1].default_value = 3.0
    masked = boosted
    star_col = nt.nodes.new('ShaderNodeMix')
    star_col.data_type, star_col.blend_type = 'RGBA', 'ADD'
    star_col.clamp_factor = False
    nt.links.new(masked.outputs[0], star_col.inputs['Factor'])
    nt.links.new(glow_col.outputs['Result'], star_col.inputs['A'])
    star_col.inputs['B'].default_value = kit.color('#DCE6FF')
    # Camera rays see the full sky; lighting rays see only the dim gradient (stars light nothing).
    sky_bg = nt.nodes.new('ShaderNodeBackground')
    sky_bg.inputs['Strength'].default_value = 1.0
    nt.links.new(star_col.outputs['Result'], sky_bg.inputs['Color'])
    nt.links.new(grad.outputs['Color'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = 1.6   # blue skylight fills the moon shadows
    lp = nt.nodes.new('ShaderNodeLightPath')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs[0])
    nt.links.new(bg.outputs[0], mix.inputs[1])
    nt.links.new(sky_bg.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])


def moon(kit, moon_dir, no_ink):
    """Visible full-moon disc far away along the moonlight direction, with darker maria."""
    mat = kit.emissive('Moon surface', '#F2F0E6', 6.0)
    nt = mat.node_tree
    em = next(n for n in nt.nodes if n.type == 'EMISSION')
    maria = nt.nodes.new('ShaderNodeTexNoise')
    maria.inputs['Scale'].default_value = 2.2
    maria.inputs['Detail'].default_value = 5.0
    ramp = kit._ramp(nt, [(0.38, '#9C9A93'), (0.55, '#F4F1E6')])
    nt.links.new(maria.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], em.inputs['Color'])
    distance = 1800.0   # inside the camera's 2000 m clip range
    disc = kit.sphere('Full moon', radius=distance * math.tan(math.radians(1.4)), location=moon_dir * distance,
                      material=mat, segments=48, rings=24, collection=no_ink)
    disc.visible_shadow = False
    return disc


def campfire(kit, no_ink):
    """Stone ring, crossed logs with glowing char, flickering flame tongues and a warm point light."""
    stone = kit.procedural('Fire-ring stone', 'stone', colors=['#4A453F', '#6F6A61', '#8E877B'], scale=2.0, bump=0.4)
    for i in range(11):
        a = math.tau * i / 11 + 0.2
        r = 0.62 + 0.05 * kit.rng.uniform(-1, 1)
        kit.rock(f'Fire-ring stone {i + 1}', radius=kit.rng.uniform(0.13, 0.19),
                 location=(CAMP.x + r * math.cos(a), CAMP.y + r * math.sin(a), 0.05), material=stone,
                 seed=40 + i, squash=0.6)
    bark = kit.procedural('Firewood bark', 'bark', scale=3.0)
    char = kit.material('Glowing char', '#1A0E08', roughness=0.9, emission='#FF5A14', emission_strength=0.0)
    # Char glow follows the black-to-ember noise so only cracks glow.
    nt, bs = char.node_tree, kit.bsdf(char)
    cracks = nt.nodes.new('ShaderNodeTexVoronoi')
    cracks.feature = 'DISTANCE_TO_EDGE'
    cracks.inputs['Scale'].default_value = 18.0
    ramp = kit._ramp(nt, [(0.0, '#FF6A1A'), (0.06, '#000000')])
    nt.links.new(cracks.outputs['Distance'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], bs.inputs['Emission Color'])
    bs.inputs['Emission Strength'].default_value = 6.0
    for i, yaw in enumerate((10, 70, 130, 190, 250, 310)):
        log = kit.cylinder(f'Firewood log {i + 1}', radius=0.055 + 0.01 * (i % 2), depth=0.75,
                           location=(0, 0, 0), material=bark, rotation=(0, 62, yaw), segments=14, bevel=0.01)
        kit.assign(log, char, slot=1)
        # Cap faces (the ends) get the char material: they point along the log's local Z.
        for p in log.data.polygons:
            if abs(p.normal.z) > 0.9:
                p.material_index = 1
        d = Vector((math.cos(math.radians(yaw)), math.sin(math.radians(yaw)), 0))
        log.location = CAMP + d * 0.16 + Vector((0, 0, 0.17))
    # Flames: lathed teardrops with a vertical white-yellow-red ramp fading to transparent tips.
    flame_mat = bpy.data.materials.new('Flame')
    flame_mat.use_nodes = True
    nt = flame_mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    coord = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(coord.outputs['Generated'], sep.inputs[0])
    col = kit._ramp(nt, [(0.0, '#FFF2C4'), (0.35, '#FFB43A'), (0.75, '#FF5A10'), (1.0, '#B0200A')])
    nt.links.new(sep.outputs['Z'], col.inputs['Fac'])
    alpha = kit._ramp(nt, [(0.55, '#FFFFFF'), (1.0, '#000000')])
    nt.links.new(sep.outputs['Z'], alpha.inputs['Fac'])
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Strength'].default_value = 9.0
    nt.links.new(col.outputs['Color'], em.inputs['Color'])
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(alpha.outputs['Color'], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    profile = [(0.0, 0.0), (0.09, 0.05), (0.12, 0.16), (0.10, 0.3), (0.06, 0.46), (0.025, 0.6), (0.0, 0.7)]
    flames = []
    for i in range(7):
        a = math.tau * i / 7
        r = 0.0 if i == 0 else 0.13
        f = kit.lathe(f'Flame tongue {i + 1}', profile, segments=20, material=flame_mat,
                      location=(CAMP.x + r * math.cos(a), CAMP.y + r * math.sin(a), 0.16), collection=no_ink)
        s = 1.25 if i == 0 else kit.rng.uniform(0.6, 0.9)
        f.scale = (s, s * 0.8, s)
        f.visible_shadow = False
        base = Vector(f.scale)
        lean = math.radians(8 if i else 0)
        # Flicker: fast loop_noise on height, width and lean; each tongue gets its own seed.
        kit.animate(f, 'scale', lambda t, b=base, k=i: (
            b.x * (1 + 0.12 * kit.loop_noise(t, 50 + k, cycles=14)),
            b.y * (1 + 0.12 * kit.loop_noise(t, 60 + k, cycles=14)),
            b.z * (1 + 0.32 * kit.loop_noise(t, 70 + k, cycles=17, octaves=3))))
        kit.animate(f, 'rotation_euler', lambda t, k=i, a0=a, l=lean: (
            l * math.cos(a0) + 0.12 * kit.loop_noise(t, 80 + k, cycles=11),
            -l * math.sin(a0) + 0.12 * kit.loop_noise(t, 90 + k, cycles=11) + 0.06, 0.0))
        flames.append(f)
    fire_light = kit.point('Campfire light', location=CAMP + Vector((0, 0, 0.45)), power=180.0,
                           color='#FF8A3A', radius=0.25)
    kit.animate(fire_light.data, 'energy', lambda t: 180.0 * (1 + 0.28 * kit.loop_noise(t, 7, cycles=19, octaves=3)))
    return flames


def tent(kit, no_ink):
    """Ridge tent of sagging canvas, lit from inside so it glows; poles, guy ropes, pegs, ground sheet."""
    L, W, H = 2.3, 1.7, 1.3        # length along the ridge, base width, ridge height
    canvas = kit.material('Tent canvas', '#A8865A', roughness=0.85, sheen=0.4)
    # Mix in translucency so the interior lamp shows through the fabric.
    nt, bs = canvas.node_tree, kit.bsdf(canvas)
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    trans = nt.nodes.new('ShaderNodeBsdfTranslucent')
    trans.inputs['Color'].default_value = kit.color('#FFB25A')
    weave = nt.nodes.new('ShaderNodeTexNoise')
    weave.inputs['Scale'].default_value = 60.0
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.15
    nt.links.new(weave.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bs.inputs['Normal'])
    mix = nt.nodes.new('ShaderNodeMixShader')
    mix.inputs[0].default_value = 0.35
    nt.links.new(bs.outputs[0], mix.inputs[1])
    nt.links.new(trans.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    root = kit.empty('Tent', TENT_AT)
    root.rotation_euler = (0, 0, math.radians(-70))   # door end turned toward the fire and camera
    # Two side panels: a grid from ridge to hem, sagging between poles (catenary-like sine).
    nu, nv = 18, 8
    for side in (-1, 1):
        verts, faces = [], []
        for j in range(nv + 1):
            v = j / nv
            for i in range(nu + 1):
                u = i / nu
                x = (u - 0.5) * L
                sag = 0.07 * math.sin(math.pi * u) * math.sin(math.pi * v)
                y = side * (v * W / 2 - sag * 0.7)
                z = H * (1 - v) - sag * 0.7
                verts.append((x, y, z + 0.02))
        for j in range(nv):
            for i in range(nu):
                a = j * (nu + 1) + i
                faces.append((a, a + 1, a + nu + 2, a + nu + 1) if side > 0 else (a, a + nu + 1, a + nu + 2, a + 1))
        panel = kit.mesh(f'Tent side panel {"right" if side > 0 else "left"}', verts, faces, canvas, smooth=True)
        kit.solidify(panel, 0.006)
        panel.parent = root
    # Back wall closed; front wall split into two flaps tied open to reveal the glowing inside.
    for end, name in ((-1, 'back'), (1, 'front')):
        x = end * L / 2
        if end < 0:
            wall = kit.mesh('Tent back wall', [(x, -W / 2, 0.02), (x, W / 2, 0.02), (x, 0, H + 0.02)], [(0, 1, 2)], canvas)
            kit.solidify(wall, 0.006)
            wall.parent = root
        else:
            for s in (-1, 1):
                flap = kit.mesh(f'Tent door flap {"right" if s > 0 else "left"}',
                                [(x, s * W / 2, 0.02), (x + 0.28, s * W * 0.33, 0.05), (x, 0, H + 0.02)],
                                [(0, 1, 2)], canvas)
                kit.solidify(flap, 0.006)
                flap.parent = root
    pole_mat = kit.procedural('Tent pole wood', 'wood', scale=4.0)
    rope = kit.material('Guy rope', '#C9B48E', roughness=0.9)
    peg = kit.material('Steel peg', '#6C6F73', roughness=0.4, metallic=1.0)
    for end in (-1, 1):
        x = end * (L / 2 + 0.02)
        p = kit.cylinder(f'Tent pole {"front" if end > 0 else "back"}', 0.018, H + 0.1, (x, 0, (H + 0.1) / 2),
                         pole_mat, segments=10)
        p.parent = root
        anchor = (x + end * 1.1, 0, 0.0)
        r = kit.tube(f'Guy rope {"front" if end > 0 else "back"}', [(x, 0, H + 0.05), anchor], 0.005, rope)
        r.parent = root
        pg = kit.cylinder('Tent peg', 0.01, 0.2, (anchor[0], 0, 0.05), peg, rotation=(0, end * 20, 0), segments=8)
        pg.parent = root
    for x in (-L / 2 + 0.2, 0.0, L / 2 - 0.2):
        for s in (-1, 1):
            pg = kit.cylinder('Tent hem peg', 0.008, 0.14, (x, s * (W / 2 + 0.06), 0.04), peg, segments=8)
            pg.parent = root
    sheet = kit.box('Ground sheet', (L + 0.1, W + 0.1, 0.01), (0, 0, 0.005),
                    kit.material('Ground sheet', '#3E4A3A', roughness=0.7), bevel=0.003)
    sheet.parent = root
    # Interior: a bedroll and a lantern that is the tent's light source.
    bedroll = kit.cylinder('Bedroll', 0.16, 0.8, (-0.3, 0.25, 0.17), kit.procedural('Wool bedroll', 'fabric',
                           colors=['#6B2E25', '#7E3A2E', '#8C4535'], scale=0.4), rotation=(90, 0, 10), segments=24, bevel=0.03)
    bedroll.parent = root
    lantern_glass = kit.emissive('Lantern glow', '#FFC472', 12.0)
    lantern = kit.cylinder('Lantern', 0.06, 0.16, (0.55, -0.2, 0.1), lantern_glass, segments=16, collection=no_ink)
    lantern.parent = root
    lamp = kit.point('Tent lantern light', location=(0.5, -0.1, 0.45), power=28.0, color='#FFB060', radius=0.15)
    lamp.parent = root
    return root


def camp_props(kit):
    """Mid-scale storytelling props: a log seat, a blackened kettle on a stone, a pack, dry scrub."""
    bark = kit.procedural('Seat log bark', 'bark', colors=['#3A2C22', '#5C4636', '#715842'], scale=2.0)
    seat = kit.cylinder('Log seat', 0.17, 1.4, (-1.35, 0.7, 0.16), bark, rotation=(90, 0, 70), segments=20, bevel=0.02)
    kit.displace(seat, strength=0.015, scale=0.2, seed=3)
    kettle_mat = kit.material('Sooty enamel', '#1E1F22', roughness=0.55, metallic=0.4, bump=(80.0, 0.2))
    kettle = kit.lathe('Kettle', [(0, 0), (0.09, 0.0), (0.11, 0.05), (0.1, 0.12), (0.06, 0.16), (0.03, 0.18),
                                  (0.0, 0.185)], segments=28, material=kettle_mat, location=(0.95, -0.55, 0.0))
    kit.tube('Kettle handle', [(0.86, -0.55, 0.17), (0.95, -0.55, 0.26), (1.04, -0.55, 0.17)], 0.006, kettle_mat)
    pack_mat = kit.procedural('Canvas pack', 'fabric', colors=['#3F4A2E', '#4E5A38', '#5E6A44'], scale=0.5)
    pack = kit.box('Backpack', (0.36, 0.24, 0.52), (1.1, 1.0, 0.25), pack_mat, rotation=(-12, 0, 35), bevel=0.06)
    kit.subdivide(pack, 2)
    kit.box('Pack flap', (0.37, 0.26, 0.04), (1.1, 0.98, 0.52), pack_mat, rotation=(-12, 0, 35), bevel=0.015)
    # Dry grass tufts: fans of thin leaning cones. Low and wide, so they never read as figures.
    straw = kit.material('Dry grass', '#8A7652', roughness=0.85)
    for i, (x, y) in enumerate(((-5.0, 4.5), (5.5, 6.5), (-6.5, -1.5), (6.8, 0.5), (3.5, 11.0), (-8.5, 9.0),
                                (1.2, -4.5), (-1.0, -6.2))):
        z = dune_height(kit, x, y)
        tuft = kit.empty(f'Grass tuft {i + 1}', (x, y, z))
        for k in range(14):
            a = kit.rng.uniform(0, math.tau)
            lean = kit.rng.uniform(15, 55)
            length = kit.rng.uniform(0.25, 0.5)
            blade = kit.cone(f'Grass blade {i + 1}.{k + 1}', radius=0.012, depth=length,
                             location=(0, 0, 0), material=straw, segments=5, smooth=False)
            blade.data.transform(Matrix.Translation((0, 0, length / 2)))   # pivot at the root
            blade.rotation_euler = (math.radians(lean) * math.cos(a), math.radians(lean) * math.sin(a), 0)
            blade.parent = tuft


def drifting_sand(kit, sand_mat, no_ink):
    """Wind-blown sand: baked grain particles plus low scrolling streamer cards."""
    grain = kit.ico('Sand grain', 0.012, material=sand_mat, subdivisions=1, collection=no_ink)
    emitter = kit.plane('Sand drift emitter', (26, 24), (-9, 4, 0.4), collection=no_ink)
    kit.particles(emitter, count=3000, lifetime=kit.frames, velocity=(3.2, 0.6, 0.35), random_velocity=0.8,
                  gravity=0.08, instance=grain, size=1.0, size_random=0.6, start=-0.6, end=0.9, seed=5)
    # Streamers: alpha noise stretched along the wind, scrolled downwind by animating the mapping.
    veil = kit.material('Sand veil', '#D6B48C', roughness=1.0)
    nt, bs = veil.node_tree, kit.bsdf(veil)
    coord = nt.nodes.new('ShaderNodeTexCoord')
    mapping = nt.nodes.new('ShaderNodeMapping')
    mapping.inputs['Scale'].default_value = (0.12, 1.4, 1.0)
    nt.links.new(coord.outputs['Object'], mapping.inputs['Vector'])
    streak = nt.nodes.new('ShaderNodeTexNoise')
    streak.inputs['Scale'].default_value = 2.0
    streak.inputs['Detail'].default_value = 6.0
    nt.links.new(mapping.outputs['Vector'], streak.inputs['Vector'])
    ramp = kit._ramp(nt, [(0.52, '#000000'), (0.75, '#2A2A2A')])
    nt.links.new(streak.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], bs.inputs['Alpha'])
    sh = kit.animate(mapping.inputs['Location'], 'default_value', lambda t: (-t * 1.4, 0.0, t * 0.6))
    # Each card is draped over the sand: its vertices follow dune_height plus a small lift.
    for i, (lift, y0) in enumerate(((0.06, -5.0), (0.15, 0.5), (0.08, 6.0), (0.12, 13.0))):
        nx, ny, w, h = 40, 6, 46.0, 5.0
        verts = []
        for j in range(ny + 1):
            for k in range(nx + 1):
                x = (k / nx - 0.5) * w
                y = y0 + (j / ny - 0.5) * h + 0.25 * x   # angled slightly with the wind
                verts.append((x, y, dune_height(kit, x, y) + lift))
        faces = [(j * (nx + 1) + k, j * (nx + 1) + k + 1, (j + 1) * (nx + 1) + k + 1, (j + 1) * (nx + 1) + k)
                 for j in range(ny) for k in range(nx)]
        card = kit.mesh(f'Sand streamer {i + 1}', verts, faces, veil, collection=no_ink)
        card.visible_shadow = False


def painterly_ink(kit, no_ink):
    """Freestyle tuned for an ink-wash look rather than CAD outlines."""
    kit.render(freestyle=True, line_thickness=1.1, line_color=INK)
    sc = kit.scene
    sc.render.line_thickness_mode = 'RELATIVE'      # same visual weight at preview and master sizes
    fs = sc.view_layers[0].freestyle_settings
    fs.crease_angle = math.radians(140)            # dune crests and log edges, not every facet
    ls = fs.linesets[0]
    ls.select_silhouette, ls.select_border, ls.select_crease = True, False, True
    ls.select_by_collection, ls.collection, ls.collection_negation = True, no_ink, 'EXCLUSIVE'
    style = ls.linestyle
    style.caps = 'ROUND'
    style.chaining = 'PLAIN'
    style.thickness = 3.0
    style.alpha = 0.85
    taper = style.thickness_modifiers.new('Brush taper', 'ALONG_STROKE')
    taper.mapping = 'CURVE'
    curve = taper.curve
    curve.curves[0].points[0].location = (0.0, 0.25)
    curve.curves[0].points[-1].location = (1.0, 0.3)
    curve.curves[0].points.new(0.4, 1.0)
    curve.update()
    far = style.thickness_modifiers.new('Thinner with distance', 'DISTANCE_FROM_CAMERA')
    far.range_min, far.range_max = 20.0, 500.0
    far.value_min, far.value_max = 1.4, 0.35
    fade = style.alpha_modifiers.new('Fade with distance', 'DISTANCE_FROM_CAMERA')
    fade.range_min, fade.range_max = 30.0, 700.0
    fade.invert = True                              # near lines opaque, far lines fade into haze
    wobble = style.geometry_modifiers.new('Hand wobble', 'PERLIN_NOISE_1D')
    wobble.frequency, wobble.amplitude, wobble.seed = 6.0, 0.6, 4


def build(kit):
    no_ink = kit.collection('No ink')               # objects Freestyle must skip
    el, az = math.radians(MOON_ELEVATION), math.radians(MOON_AZIMUTH)
    moon_dir = Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))

    sand = sand_material(kit)
    build_dunes(kit, sand)
    night_sky(kit, moon_dir)
    moon(kit, moon_dir, no_ink)
    # Moonlight: a weak, slightly soft, cool sun from the moon's direction.
    kit.sun(elevation=MOON_ELEVATION, azimuth=MOON_AZIMUTH, strength=1.1, color='#7C98E6', angle=0.6,
            name='Moonlight')
    campfire(kit, no_ink)
    tent(kit, no_ink)
    camp_props(kit)
    drifting_sand(kit, sand, no_ink)
    # Thin cold haze separates the dune ranges; it is wide so it surrounds the camera too.
    haze = kit.haze(density=0.003, color='#9FB2D6', anisotropy=0.2, size=(900, 1000, 200), location=(0, 420, 90))
    for c in haze.users_collection:
        c.objects.unlink(haze)
    no_ink.objects.link(haze)

    # Stand the camera on the sand wherever the dune field puts it.
    eye = CAM_AT + Vector((0, 0, dune_height(kit, CAM_AT.x, CAM_AT.y)))
    cam = kit.camera(location=eye, target=CAM_LOOK, lens=CAM_LENS, dof=10.5, fstop=8.0)
    # Locked-off tripod that someone is holding: a tiny drift plus loop-noise shake.
    kit.dolly(cam, eye, eye + Vector((0.2, 0.25, 0.03)), ease_kind='sine')
    kit.handheld(cam, amount=0.25, cycles=2, seed=8)   # breathing operator, not a shaky one
    painterly_ink(kit, no_ink)
    kit.render(exposure=1.0, look='AgX - Medium High Contrast', volume_step=4.0)
