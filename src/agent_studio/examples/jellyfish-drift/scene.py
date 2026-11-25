"""A bioluminescent jellyfish rising through the deep sea, as a seamless loop.

Teaches:
- a loop that travels: the jellyfish, camera and light rig all rise by exactly RISE metres per
  loop, and everything they move past (plankton, marine snow) is built periodic in Z with that
  same period, so frame frames+1 is frame 1 seen one tile higher;
- a pulsing bell from one shape key ("Contract") keyed with an asymmetric pulse curve, and a
  rise that surges on each contraction (integer-cycle waves keep it loop-safe);
- tentacles as NURBS curves whose control points are keyframed with a travelling wave that lags
  behind the bell, so motion flows from the rim to the tips;
- an emissive translucent look without refraction noise: Transparent + Emission mixed by
  Layer Weight facing (edges glow, centres stay see-through) plus radial canals from a radial
  gradient;
- vertex-instanced point clouds (instance_type='VERTS') for thousands of specks at the cost of one
  object, and shallow depth of field turning near specks into bokeh;
- a volume box with a narrow cold spot from above for blue shafts, plus a point light inside the
  bell so the jellyfish lights the water around it.
"""
import math

import bpy
from mathutils import Vector

# ---------------------------------------------------------------- constants (metres)
BELL_R = 0.18            # bell radius: an 36 cm deep-sea jellyfish
BELL_H = 0.15            # dome height above the rim
RISE = 0.6               # metres risen per loop (10 cm/s over 6 s)
PULSES = 3               # contractions per loop (whole number: loop-safe)
TENTACLES = 16           # marginal tentacles around the rim
ARMS = 4                 # frilled oral arms from the centre
CAM_DIST = 1.75          # camera distance from the jellyfish axis
GLOW = '#58E6FF'         # cyan bioluminescence
GLOW_WARM = '#FF6FD8'    # magenta gonads and arm frills
WATER = '#020A1C'


def pulse(kit, t, lag=0.0):
    """0 (relaxed) .. 1 (contracted). Quick contraction, slow relaxation: a real swimming stroke."""
    phase = (PULSES * (t - lag)) % 1.0
    if phase < 0.3:
        return math.sin(0.5 * math.pi * phase / 0.3) ** 2      # snap shut in 30% of the cycle
    return math.cos(0.5 * math.pi * (phase - 0.3) / 0.7) ** 2  # ease open over the rest


def glow_material(kit, name, color, strength, edge_power=2.0, base_alpha=0.08, canals=0):
    """Emissive translucent: see-through where we look straight in, glowing where the surface turns away."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    lw = nt.nodes.new('ShaderNodeLayerWeight')
    lw.inputs['Blend'].default_value = 0.35
    edge = nt.nodes.new('ShaderNodeMath')
    edge.operation = 'POWER'
    nt.links.new(lw.outputs['Facing'], edge.inputs[0])
    edge.inputs[1].default_value = edge_power
    fac = nt.nodes.new('ShaderNodeMath')
    fac.operation = 'MULTIPLY_ADD'                 # alpha = base + edge * (1 - base)
    fac.use_clamp = True
    nt.links.new(edge.outputs[0], fac.inputs[0])
    fac.inputs[1].default_value = 1.0 - base_alpha
    fac.inputs[2].default_value = base_alpha
    if canals:
        # Radial canals: the radial gradient gives the angle around Z (0..1); a sharpened cosine of
        # angle*canals draws thin bright spokes that add to the alpha.
        coord = nt.nodes.new('ShaderNodeTexCoord')
        grad = nt.nodes.new('ShaderNodeTexGradient')
        grad.gradient_type = 'RADIAL'
        nt.links.new(coord.outputs['Object'], grad.inputs['Vector'])
        ang = nt.nodes.new('ShaderNodeMath')
        ang.operation = 'MULTIPLY'
        nt.links.new(grad.outputs['Fac'], ang.inputs[0])
        ang.inputs[1].default_value = math.tau * canals
        cos = nt.nodes.new('ShaderNodeMath')
        cos.operation = 'COSINE'
        nt.links.new(ang.outputs[0], cos.inputs[0])
        sharp = nt.nodes.new('ShaderNodeMath')
        sharp.operation = 'POWER'
        sharp.use_clamp = True
        nt.links.new(cos.outputs[0], sharp.inputs[0])
        sharp.inputs[1].default_value = 40.0
        add = nt.nodes.new('ShaderNodeMath')
        add.operation = 'MULTIPLY_ADD'
        add.use_clamp = True
        nt.links.new(sharp.outputs[0], add.inputs[0])
        add.inputs[1].default_value = 0.45
        nt.links.new(fac.outputs[0], add.inputs[2])
        fac = add
    # Mottling: a faint cellular texture in the emission so the bell is not a uniform plastic glow.
    mottle = nt.nodes.new('ShaderNodeTexNoise')
    mottle.inputs['Scale'].default_value = 60.0
    mottle.inputs['Detail'].default_value = 3.0
    tint = nt.nodes.new('ShaderNodeMix')
    tint.data_type = 'RGBA'
    nt.links.new(mottle.outputs['Fac'], tint.inputs['Factor'])
    tint.inputs['A'].default_value = kit.color(color)
    tint.inputs['B'].default_value = kit.color('#E8FBFF')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Strength'].default_value = strength
    nt.links.new(tint.outputs['Result'], em.inputs['Color'])
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    gloss = nt.nodes.new('ShaderNodeBsdfGlossy')     # a wet specular sheen on top
    gloss.inputs['Roughness'].default_value = 0.08
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(fac.outputs[0], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    gl_mix = nt.nodes.new('ShaderNodeMixShader')
    gl_mix.inputs[0].default_value = 0.06
    nt.links.new(mix.outputs[0], gl_mix.inputs[1])
    nt.links.new(gloss.outputs[0], gl_mix.inputs[2])
    nt.links.new(gl_mix.outputs[0], out.inputs['Surface'])
    mat.diffuse_color = kit.color(color)
    return mat


def build_bell(kit, root, bell_mat, inner_mat):
    """Lathed dome with a curled lip and an inner subumbrella; a 'Contract' shape key pulses it."""
    outer = [(BELL_R * math.sin(math.radians(a)), BELL_H * math.cos(math.radians(a)))
             for a in range(0, 101, 5)]                      # apex to rim, curling slightly under
    lip = [(BELL_R * 0.95, -0.022)]
    inner = [(0.86 * BELL_R * math.sin(math.radians(a)), 0.72 * BELL_H * math.cos(math.radians(a)) - 0.012)
             for a in range(95, -1, -5)]                     # subumbrella back up to the centre
    bell = kit.lathe('Jellyfish bell', outer + lip + inner, segments=64, material=bell_mat)
    bell.parent = root
    kit.subdivide(bell, 1)
    # Shape key: the rim pulls in hard, the dome barely moves and grows a little taller.
    bell.shape_key_add(name='Basis')
    key = bell.shape_key_add(name='Contract', from_mix=False)
    for v in key.data:
        h = max(0.0, min(1.0, (v.co.z + 0.03) / (BELL_H + 0.03)))   # 0 at the rim, 1 at the apex
        squeeze = 1.0 - 0.30 * (1.0 - h) ** 1.4
        v.co.x *= squeeze
        v.co.y *= squeeze
        v.co.z = v.co.z * 1.12 - 0.02 * (1.0 - h)
    kit.animate(key, 'value', lambda t: pulse(kit, t))
    # Gonads: four glowing horseshoes seen through the dome (mid-scale detail).
    for i in range(4):
        a = math.tau * i / 4 + math.pi / 4
        g = kit.torus(f'Gonad {i + 1}', radius=0.032, thickness=0.009, segments=40, sides=10,
                      location=(0.055 * math.cos(a), 0.055 * math.sin(a), 0.075), material=inner_mat)
        g.scale = (1.0, 0.75, 0.6)
        g.parent = root
    # Manubrium: the short central stalk the oral arms hang from.
    stalk = kit.lathe('Manubrium', [(0.0, 0.06), (0.03, 0.05), (0.022, 0.0), (0.016, -0.06), (0.0, -0.07)],
                      segments=24, material=inner_mat)
    stalk.parent = root
    # Marginal bulbs: tiny bright beads where each tentacle leaves the rim (fine detail).
    bulb = kit.emissive('Marginal bulb', GLOW, 30.0)
    for i in range(TENTACLES):
        a = math.tau * (i + 0.5) / TENTACLES
        b = kit.sphere(f'Marginal bulb {i + 1}', 0.006, (0.93 * BELL_R * math.cos(a), 0.93 * BELL_R * math.sin(a), -0.016),
                       bulb, segments=8, rings=6)
        b.parent = root
    return bell


def animated_curve(kit, root, name, n_points, radius, taper, material, shape):
    """NURBS tube whose control points are keyframed from shape(t, s) -> local position."""
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = radius
    cu.bevel_resolution = 2
    cu.resolution_u = 6
    cu.use_fill_caps = True
    sp = cu.splines.new('NURBS')
    sp.points.add(n_points - 1)
    sp.order_u = 4
    sp.use_endpoint_u = True
    for k, p in enumerate(sp.points):
        s = k / (n_points - 1)
        p.co = (*shape(0.0, s), 1.0)
        p.radius = taper(s)
    obj = bpy.data.objects.new(name, cu)
    cu.materials.append(material)
    kit.scene.collection.objects.link(obj)
    obj.parent = root
    for k, p in enumerate(sp.points):
        s = k / (n_points - 1)
        # Keys every 2 frames are plenty for a smooth wave and keep the build fast.
        kit.animate(p, 'co', lambda t, s=s: (*shape(t, s), 1.0), step=2, interpolation='BEZIER')
    return obj


def tentacles(kit, root, tent_mat, arm_mat):
    rng = kit.rng
    for i in range(TENTACLES):
        a = math.tau * (i + 0.5) / TENTACLES
        length = rng.uniform(0.9, 1.5)
        ph = rng.uniform(0, math.tau)
        radial = Vector((math.cos(a), math.sin(a), 0.0))
        tangent = Vector((-math.sin(a), math.cos(a), 0.0))

        def shape(t, s, radial=radial, tangent=tangent, length=length, ph=ph):
            # The rim anchor follows the bell's contraction; further down the tentacle the same
            # pulse arrives later (lag grows with s), so a wave runs from rim to tip.
            rim = 0.93 * BELL_R * (1.0 - 0.27 * pulse(kit, t))
            late = pulse(kit, t, lag=0.12 * s)
            sway = 0.05 * s ** 1.2 * math.sin(math.tau * (PULSES * t - 1.4 * s) + ph)
            drift = 0.03 * s * kit.loop_noise(t, seed=i, cycles=1)
            out = rim + 0.06 * s - 0.05 * s * late          # spread out at rest, drawn in after a stroke
            z = -0.016 - s * length * (1.0 - 0.06 * late)
            return tuple(radial * out + tangent * (sway + drift) + Vector((0, 0, z)))
        animated_curve(kit, root, f'Tentacle {i + 1}', 9, 0.0024, lambda s: 1.0 - 0.75 * s, tent_mat, shape)
    for i in range(ARMS):
        a = math.tau * i / ARMS + 0.3
        length = rng.uniform(0.45, 0.6)
        radial = Vector((math.cos(a), math.sin(a), 0.0))
        tangent = Vector((-math.sin(a), math.cos(a), 0.0))

        def arm(t, s, radial=radial, tangent=tangent, length=length, k=i):
            curl = 0.035 * math.sin(math.tau * (PULSES * t - 0.8 * s) + k)
            return tuple(radial * (0.012 + 0.05 * s) + tangent * curl * s + Vector((0, 0, -0.06 - s * length)))
        # Frills: the radius ripples along the arm, so the tube reads as a ruffled ribbon.
        animated_curve(kit, root, f'Oral arm {i + 1}', 14, 0.014,
                       lambda s: (1.0 - 0.7 * s) * (0.75 + 0.35 * abs(math.sin(s * 34.0))), arm_mat, arm)


def point_cloud(kit, name, count, speck, area, z0, rng):
    """`count` specks per RISE-tall tile, repeated in three tiles so the field is periodic in Z."""
    xmin, xmax, ymin, ymax = area
    base = [(rng.uniform(xmin, xmax), rng.uniform(ymin, ymax), rng.uniform(0.0, RISE)) for _ in range(count)]
    verts = [(x, y, z0 + z + tile * RISE) for tile in range(-1, 6) for x, y, z in base]
    holder = kit.mesh(name, verts, [])
    holder.instance_type = 'VERTS'           # one copy of `speck` on every vertex
    speck.parent = holder
    speck.location = (0, 0, 0)
    return holder


def build(kit):
    rng = kit.rng
    # ---------------------------------------------------------------- the water
    kit.world(WATER, strength=1.0, top='#0A2448')
    # One rig rises RISE per loop; the jellyfish bobs on top of that with each stroke.
    rig = kit.empty('Rising rig', (0, 0, 0))
    kit.animate(rig, 'location', lambda t: (0.0, 0.0, RISE * t))
    root = kit.empty('Jellyfish', (0, 0, 0))
    root.parent = rig
    # Surge: after each contraction the body jumps ahead of the steady rise, then falls back.
    kit.animate(root, 'location', lambda t: (0.02 * kit.loop_noise(t, 3, cycles=1), 0.0,
                                             0.045 * math.sin(math.tau * PULSES * (t - 0.05))))
    kit.animate(root, 'rotation_euler', lambda t: (math.radians(7) * kit.loop_noise(t, 5, cycles=1),
                                                   math.radians(5) * kit.loop_noise(t, 6, cycles=1),
                                                   math.radians(6) * kit.wave(t)))

    # ---------------------------------------------------------------- the jellyfish
    bell_mat = glow_material(kit, 'Bell glow', GLOW, 6.0, edge_power=2.2, base_alpha=0.06, canals=8)
    inner_mat = glow_material(kit, 'Gonad glow', GLOW_WARM, 9.0, edge_power=1.2, base_alpha=0.35)
    tent_mat = glow_material(kit, 'Tentacle glow', GLOW, 14.0, edge_power=0.8, base_alpha=0.5)
    arm_mat = glow_material(kit, 'Oral arm glow', '#B58CFF', 7.0, edge_power=1.2, base_alpha=0.22)
    build_bell(kit, root, bell_mat, inner_mat)
    tentacles(kit, root, tent_mat, arm_mat)
    # The jellyfish lights the water around it: a soft cyan point light inside the bell.
    inner_light = kit.point('Bell light', (0, 0, 0.04), power=3.0, color=GLOW, radius=0.12)
    inner_light.parent = root
    kit.animate(inner_light.data, 'energy', lambda t: 2.2 + 2.0 * pulse(kit, t, lag=0.05))
    kit.animate(bell_mat.node_tree.nodes['Emission'].inputs['Strength'], 'default_value',
                lambda t: 4.5 + 3.5 * pulse(kit, t, lag=0.05))

    # ---------------------------------------------------------------- plankton and marine snow
    plankton_mat = kit.emissive('Plankton glow', '#7FF3FF', 12.0)
    snow_mat = kit.material('Marine snow', '#C9D8E8', roughness=0.8, emission='#9FC4FF', emission_strength=0.4)
    tiny = kit.ico('Plankton speck', 0.0018, material=plankton_mat, subdivisions=1)
    small = kit.ico('Plankton speck large', 0.0035, material=plankton_mat, subdivisions=1)
    flake = kit.ico('Marine snow flake', 0.0025, material=snow_mat, subdivisions=1)
    point_cloud(kit, 'Plankton field', 260, tiny, (-1.2, 1.2, -1.0, 2.5), -1.5, rng)
    point_cloud(kit, 'Plankton field bright', 40, small, (-1.0, 1.0, -1.2, 2.0), -1.5, rng)
    point_cloud(kit, 'Marine snow field', 220, flake, (-1.5, 1.5, -1.3, 3.5), -1.5, rng)

    # ---------------------------------------------------------------- volumetric blue light
    # Static haze: uniform water is invariant to the rig's rise, so it is loop-safe as is.
    kit.haze(density=0.22, color='#3A7FD0', anisotropy=0.55, size=(8, 8, 9), location=(0, 0.8, 2.0),
             name='Deep water')
    # Faint shafts from far above travel with the rig, so the light pattern repeats every loop.
    for k, (x, y, power) in enumerate(((-0.9, 1.6, 260.0), (0.7, 2.4, 180.0))):
        shaft = kit.spot(f'Surface shaft {k + 1}', (x, y, 4.5), (x * 0.6, y * 0.9, -2), power=power,
                         color='#5B9BFF', angle=9.0, blend=0.6, radius=0.3)
        shaft.parent = rig

    # ---------------------------------------------------------------- the camera
    cam = kit.camera(location=(0.0, -CAM_DIST, -0.36), target=(0.0, 0.0, -0.34), lens=42.0,
                     dof=CAM_DIST, fstop=2.2, active=True)
    cam.parent = rig
    kit.target_of(cam).parent = rig
    kit.handheld(cam, amount=0.35, cycles=1, seed=12)   # a gentle float, loop-safe
    kit.render(exposure=0.4, look='AgX - Medium High Contrast', volume_step=2.0, bounces=4)
