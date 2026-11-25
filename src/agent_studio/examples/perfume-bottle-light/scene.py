"""Perfume bottle under a sweeping hard light: glass, amber liquid and a gold cap on magenta.

Teaching points
- Product scale is real scale: the bottle is 13 cm tall, so the camera sits 40-60 cm away on an
  85 mm lens with shallow depth of field. Small sets need small bevels (0.5-1 mm) or edges go soft.
- Glass that reads as glass is a *shell*: one lathe profile that runs up the outside, over the lip
  and back down the inside, with a thick base. The liquid is a separate closed volume that overlaps
  the inner wall by a fraction of a millimetre (no air gap, no z-fighting).
- Facets come for free from a low-segment lathe with flat shading: 10 sides catch the moving
  light one face at a time, which is exactly what makes cut glass sparkle.
- Path-traced caustics from a small spot are hopelessly noisy at preview samples. Two cheap fakes:
  (1) shadow rays pass through the glass and liquid as tinted transparency, so the bottle throws
  an amber 'light shadow'; (2) a second, narrow spot with a Voronoi gobo projects a rippled amber
  caustic pattern exactly where that shadow lands, and follows it as the key sweeps.
- One hard key light only: a 2 mm-radius spot sweeps in an arc from left to right. Its pool of
  light travels across the saturated backdrop, giving the shot its motion.
"""
import math

import bpy
from mathutils import Vector

# ----------------------------------------------------------------------------- constants
FACETS = 10                 # sides of the cut-glass bottle and cap
FILL_Z = 0.064              # liquid level (m above the plinth top)
PLINTH_R, PLINTH_H = 0.085, 0.05
BACKDROP = '#C8107A'        # saturated magenta sweep
AMBER = '#E07A12'
KEY_RADIUS = 0.75           # distance of the sweeping key from the bottle
KEY_HEIGHT = 0.42
SWEEP = (-58.0, 52.0)       # key azimuth start/end, degrees from the camera axis
BOTTLE_C = Vector((0, 0, 0.06))

# Outer surface up, over the lip, then the inner wall back down to a thick 12 mm base.
GLASS_PROFILE = [
    (0.0, 0.0), (0.029, 0.0), (0.0315, 0.0025), (0.0315, 0.074), (0.0255, 0.0865),
    (0.0105, 0.0925), (0.0088, 0.095), (0.0088, 0.1045),
    (0.0058, 0.1045), (0.0058, 0.093), (0.0215, 0.0835), (0.0272, 0.0725), (0.0272, 0.0145),
    (0.0248, 0.012), (0.0, 0.012),
]
# Liquid fills the cavity up to FILL_Z, 0.2 mm wider than the inner wall.
LIQUID_PROFILE = [(0.0, 0.0119), (0.0250, 0.0119), (0.0274, 0.0143), (0.0274, FILL_Z), (0.0, FILL_Z)]
CAP_PROFILE = [(0.0, 0.1035), (0.0165, 0.1035), (0.0185, 0.1060), (0.0185, 0.1290), (0.0150, 0.1325),
               (0.0, 0.1325)]


# ----------------------------------------------------------------------------- materials
def shadow_transparent(kit, mat, tint, amount):
    """Let shadow rays pass through `mat` as a tinted transparent surface (fake caustic light)."""
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    surface = out.inputs['Surface'].links[0].from_socket
    lp = nt.nodes.new('ShaderNodeLightPath')
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    tr.inputs['Color'].default_value = tint
    mix = nt.nodes.new('ShaderNodeMixShader')
    mul = nt.nodes.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY'
    mul.inputs[1].default_value = amount
    nt.links.new(lp.outputs['Is Shadow Ray'], mul.inputs[0])
    nt.links.new(mul.outputs[0], mix.inputs['Fac'])
    nt.links.new(surface, mix.inputs[1])
    nt.links.new(tr.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    return mat


def amber_liquid(kit):
    """Clear liquid surface plus volume absorption: thick parts glow deeper amber than thin ones."""
    mat = kit.material('Amber liquid', '#FFE4B0', roughness=0.0, transmission=1.0, ior=1.36)
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    vol = nt.nodes.new('ShaderNodeVolumeAbsorption')
    vol.inputs['Color'].default_value = (1.0, 0.72, 0.22, 1)
    vol.inputs['Density'].default_value = 10.0      # per metre: ~5 cm of liquid absorbs noticeably
    nt.links.new(vol.outputs[0], out.inputs['Volume'])
    return mat


def gold(kit):
    """Polished gold with fine concentric brushing: anisotropic look from a stretched noise bump."""
    mat = kit.material('Polished gold', '#E9B65C', roughness=0.16, metallic=1.0)
    nt = mat.node_tree
    tc = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (900.0, 900.0, 6.0)   # streaks run vertically
    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Detail'].default_value = 4
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.08
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
    nt.links.new(mp.outputs['Vector'], noise.inputs['Vector'])
    nt.links.new(noise.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], kit.bsdf(mat).inputs['Normal'])
    return mat


def backdrop_material(kit):
    """Saturated paper sweep with a faint fibre noise so the light pool has texture."""
    return kit.material('Magenta sweep', BACKDROP, roughness=0.62, sheen=0.2, bump=(400, 0.04))


# ----------------------------------------------------------------------------- geometry
def cove(kit, mat, width=1.6, floor_front=-0.9, floor_back=0.22, radius=0.32, top=1.3, z=-PLINTH_H):
    """Infinity cove: a floor that curves up into the back wall, so there is no visible corner."""
    prof = [(floor_front, z), (floor_back, z)]
    for k in range(1, 17):
        a = math.radians(90 * k / 16)
        prof.append((floor_back + radius * math.sin(a), z + radius * (1 - math.cos(a))))
    prof.append((floor_back + radius, top))
    verts, faces = [], []
    for x in (-width / 2, width / 2):
        verts += [(x, y, zz) for y, zz in prof]
    n = len(prof)
    for k in range(n - 1):
        faces.append((k, k + 1, n + k + 1, n + k))
    obj = kit.mesh('Backdrop cove', verts, faces, mat, smooth=True, ground=True)
    return obj


def key_position(t):
    """Arc of the sweeping key around the bottle, in front of it, eased in and out."""
    a = math.radians(SWEEP[0] + (SWEEP[1] - SWEEP[0]) * (0.5 - 0.5 * math.cos(math.pi * t)))
    return Vector((KEY_RADIUS * math.sin(a), -KEY_RADIUS * math.cos(a), KEY_HEIGHT))


def shadow_point(t):
    """Where the bottle's shadow lands on the cove, for the fake caustic gobo to aim at."""
    p = key_position(t)
    d = (BOTTLE_C - p).normalized()
    hit = BOTTLE_C + d * 0.09
    hit.z = max(hit.z, -PLINTH_H + 0.002)
    return hit


def track(obj, target):
    con = obj.constraints.new('TRACK_TO')
    con.target = target
    con.track_axis, con.up_axis = 'TRACK_NEGATIVE_Z', 'UP_Y'


def caustic_gobo(kit, light):
    """Light node tree: a Voronoi ripple projected through the spot (planar projection x/z, y/z)."""
    data = light.data
    try:
        data.use_nodes = True
        nt = data.node_tree
    except AttributeError:
        kit.note('light nodes unavailable: caustic gobo left as a plain amber spot')
        return
    em = next(n for n in nt.nodes if n.type == 'EMISSION')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Normal'], sep.inputs[0])
    dx, dy = nt.nodes.new('ShaderNodeMath'), nt.nodes.new('ShaderNodeMath')
    for node, sock in ((dx, 'X'), (dy, 'Y')):
        node.operation = 'DIVIDE'
        nt.links.new(sep.outputs[sock], node.inputs[0])
        nt.links.new(sep.outputs['Z'], node.inputs[1])
    comb = nt.nodes.new('ShaderNodeCombineXYZ')
    nt.links.new(dx.outputs[0], comb.inputs['X'])
    nt.links.new(dy.outputs[0], comb.inputs['Y'])
    vor = nt.nodes.new('ShaderNodeTexVoronoi')
    vor.feature = 'DISTANCE_TO_EDGE'
    vor.inputs['Scale'].default_value = 9.0
    vor.inputs['Randomness'].default_value = 0.85
    nt.links.new(comb.outputs[0], vor.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.0, (1.0, 0.75, 0.35, 1)     # bright caustic filaments
    els[1].position, els[1].color = 0.09, (0.05, 0.02, 0.0, 1)    # dark cells between them
    nt.links.new(vor.outputs['Distance'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], em.inputs['Color'])


# ----------------------------------------------------------------------------- build
def build(kit):
    # --- materials ------------------------------------------------------------------------
    glass = kit.material('Cut glass', '#FFFFFF', roughness=0.0, transmission=1.0, ior=1.52, coat=0.0)
    shadow_transparent(kit, glass, (1.0, 0.97, 0.93, 1), 0.85)
    liquid = shadow_transparent(kit, amber_liquid(kit), (1.0, 0.55, 0.12, 1), 0.9)
    gold_mat = gold(kit)
    lacquer = kit.material('Black lacquer', '#0B0B0D', roughness=0.08, coat=1.0)
    kit.bsdf(lacquer).inputs['Coat Roughness'].default_value = 0.03
    sweep = backdrop_material(kit)
    tube_mat = kit.material('Dip tube', '#F2F2F2', roughness=0.25, transmission=0.9, ior=1.45)

    # --- the bottle -------------------------------------------------------------------------
    bottle = kit.lathe('Bottle glass', GLASS_PROFILE, segments=FACETS, material=glass, smooth=False)
    bottle.rotation_euler.z = math.radians(180 / FACETS)    # a facet edge faces the camera
    kit.bevel(bottle, width=0.0004, segments=2)              # glints along every facet edge
    kit.lathe('Amber liquid', LIQUID_PROFILE, segments=FACETS * 4, material=liquid)
    kit.tube('Dip tube', [(0.003, 0, 0.014), (0.0005, 0, 0.06), (0, 0, 0.104)], radius=0.0011,
             material=tube_mat, resolution=8)
    kit.cylinder('Neck collar', radius=0.0108, depth=0.0085, location=(0, 0, 0.0995),
                          material=gold_mat, segments=48, bevel=0.0006)
    cap = kit.lathe('Faceted cap', CAP_PROFILE, segments=FACETS, material=gold_mat, smooth=False)
    cap.rotation_euler.z = bottle.rotation_euler.z
    kit.bevel(cap, width=0.0005, segments=2)

    # --- set: glossy plinth on a magenta cove -------------------------------------------------
    kit.cylinder('Lacquer plinth', radius=PLINTH_R, depth=PLINTH_H, location=(0, 0, -PLINTH_H / 2),
                          material=lacquer, segments=96, bevel=0.0025)
    # A thin gold inlay ring on the plinth top: a small accent that ties cap and plinth together.
    kit.torus('Plinth inlay', radius=PLINTH_R - 0.008, thickness=0.0012, location=(0, 0, 0.0),
              material=gold_mat, segments=128, sides=8)
    cove(kit, sweep)

    # --- light: one hard sweeping key + its fake caustic --------------------------------------
    aim = kit.empty('Key aim', location=BOTTLE_C)
    key = kit.spot('Hard key', location=key_position(0), target=BOTTLE_C, power=55.0, color='#FFF1DE',
                   angle=40, blend=0.15, radius=0.002)
    track(key, aim)
    kit.animate(key, 'location', key_position)

    gobo_aim = kit.empty('Caustic aim', location=shadow_point(0))
    kit.animate(gobo_aim, 'location', shadow_point)
    gobo = kit.spot('Caustic gobo', location=key_position(0), target=shadow_point(0), power=22.0,
                    color='#FFB347', angle=6.5, blend=0.6, radius=0.001)
    track(gobo, gobo_aim)
    kit.animate(gobo, 'location', key_position)
    caustic_gobo(kit, gobo)
    gobo.data.use_shadow = False    # the gobo stands in for light that already went through the glass

    # Reflection-only strip boxes: product photographers flank glass with tall strips so its
    # edges draw as clean white lines. These emit, but are invisible to the camera and to diffuse
    # rays, so they add no light to the set: the hard spot stays the only key.
    for side in (-1, 1):
        strip = kit.plane(f'Reflection strip {"L" if side < 0 else "R"}', size=(0.06, 0.5),
                          location=(side * 0.28, 0.12, 0.12), rotation=(90, 0, side * -70),
                          material=kit.emissive('Strip glow', '#FFF6EE', 6.0))
        strip.visible_camera = False
        strip.visible_diffuse = False
        strip.visible_shadow = False
        strip.visible_volume_scatter = False

    # A dim magenta world keeps the unlit sweep saturated instead of black.
    kit.world('#3A0822', strength=0.35)
    kit.render(look='AgX - Medium High Contrast', exposure=0.2, bounces=16)
    sc = kit.scene
    sc.cycles.transmission_bounces = 16
    sc.cycles.glossy_bounces = 8
    sc.cycles.volume_bounces = 2
    sc.cycles.caustics_refractive = False   # real caustics would only add noise; the gobo fakes them
    sc.cycles.caustics_reflective = False

    # --- camera: slow push-in on an 85 mm lens ---------------------------------------------------
    cam = kit.camera(location=(0.05, -0.62, 0.11), target=(0, 0, 0.058), lens=85, dof=0.62, fstop=3.2)
    kit.dolly(cam, (0.05, -0.62, 0.11), (0.02, -0.45, 0.09), target_start=(0, 0, 0.058),
              target_end=(0, 0, 0.068), ease_kind='in_out', power=2.0)
    # Keep focus on the bottle as the camera moves.
    kit.rack_focus(cam, [(0.0, 0.625), (1.0, 0.452)], fstop=3.2)
