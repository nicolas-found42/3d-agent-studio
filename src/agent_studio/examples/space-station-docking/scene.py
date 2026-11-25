"""A ring station turns above Earth while a shuttle spin-matches and docks with its hub.

Teaching points
- Planet scale without float trouble: what the eye reads is the horizon dip and curvature, which
  depend only on radius/altitude. Earth here is 1:100 (R = 63.7 km) at a scaled altitude, so
  the horizon sits where it should while the station stays at real metres near the origin.
- A procedural Earth in one shader: normalised object position drives continent noise (land
  mask), a separate cloud shell, glossy oceans for a sun glint, and a Fresnel-weighted emissive
  shell for the thin blue limb. No textures needed.
- Space lighting is a single hard sun with no sky: shadows go to black. The only fill is
  earthshine, a broad blue area light from below standing in for sunlight bounced off the planet.
- Hard-surface detail at three scales: silhouette (ring, spokes, hub, arrays), mid forms (module
  joints, radiators, docking port, engine bells) and surface (panel seams from a Brick texture,
  crinkled gold foil, hundreds of batched greebles and lit windows).
- Docking reads as real when the shuttle matches the station's spin: its roll is keyed to the
  same angle as the station, and after contact it simply rides along.
- RCS puffs: one material reads per-object colour alpha (Object Info), so each puff object fades
  independently while it scales up; keyed in a few short bursts while braking.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

# ----------------------------------------------------------------------------- constants
EARTH_R = 63710.0          # 1:100 Earth (m)
ALTITUDE = 1300.0          # scaled altitude: puts the horizon dip at about 11 degrees
RING_R, RING_TUBE = 38.0, 3.2
HUB_R, HUB_LEN = 4.0, 44.0
SPIN_TURNS = 0.07          # station turns over the 8 s shot (slow, majestic)
PORT_X = HUB_LEN / 2 + 1.9  # face of the docking port
SHUTTLE_LEN = 12.0
DOCK_T = 0.8               # shot progress at contact
START_X = 112.0            # shuttle nose x at frame 1
SUN_ELEV, SUN_AZ = 28.0, 128.0


# ----------------------------------------------------------------------------- batching
class Batch:
    """Many small boxes in one mesh (greebles, windows): one object, fast to build and render."""

    def __init__(self):
        self.bm = bmesh.new()

    def box(self, matrix, size):
        res = bmesh.ops.create_cube(self.bm, size=1.0)
        bmesh.ops.transform(self.bm, matrix=matrix @ Matrix.Diagonal((*size, 1.0)), verts=res['verts'])

    def build(self, kit, name, material, parent=None, bevel=0.0):
        me = bpy.data.meshes.new(name)
        self.bm.to_mesh(me)
        self.bm.free()
        obj = bpy.data.objects.new(name, me)
        kit.scene.collection.objects.link(obj)
        me.materials.append(material)
        if bevel:
            kit.bevel(obj, width=bevel, segments=1)
        if parent:
            obj.parent = parent
        return obj


def frame_at(origin, normal, up_hint=Vector((1, 0, 0))):
    """A matrix at `origin` whose local Z is `normal` (for placing greebles on a surface)."""
    z = normal.normalized()
    x = up_hint.cross(z)
    if x.length < 1e-4:
        x = Vector((0, 1, 0)).cross(z)
    x.normalize()
    y = z.cross(x)
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = origin
    return m


# ----------------------------------------------------------------------------- materials
def panel_white(kit, name='Station panels', color='#D9DBDD', scale=0.45):
    """White hull panels: per-panel tone and recessed seams from a Brick texture."""
    mat = kit.material(name, color, roughness=0.5)
    nt = mat.node_tree
    bs = kit.bsdf(mat)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    brick = nt.nodes.new('ShaderNodeTexBrick')
    brick.offset = 0.5
    brick.inputs['Scale'].default_value = scale
    brick.inputs['Mortar Size'].default_value = 0.012
    brick.inputs['Color1'].default_value = kit_rgba(color, 1.0)
    brick.inputs['Color2'].default_value = kit_rgba(color, 0.86)
    brick.inputs['Mortar'].default_value = (0.25, 0.26, 0.27, 1)
    brick.inputs['Brick Width'].default_value = 1.6
    brick.inputs['Row Height'].default_value = 0.8
    nt.links.new(tc.outputs['Object'], brick.inputs['Vector'])
    nt.links.new(brick.outputs['Color'], bs.inputs['Base Color'])
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.35
    bump.invert = True
    nt.links.new(brick.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bs.inputs['Normal'])
    return mat


def kit_rgba(hexcolor, mul):
    h = hexcolor.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return (lin[0] * mul, lin[1] * mul, lin[2] * mul, 1.0)


def gold_foil(kit):
    """Crinkled Kapton/MLI foil: metallic gold with a strong Voronoi crinkle bump."""
    mat = kit.material('Gold foil', '#D6A246', roughness=0.28, metallic=1.0)
    nt = mat.node_tree
    vor = nt.nodes.new('ShaderNodeTexVoronoi')
    vor.inputs['Scale'].default_value = 3.0
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.55
    nt.links.new(vor.outputs['Distance'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], kit.bsdf(mat).inputs['Normal'])
    return mat


def solar_cells(kit):
    """Dark blue cells in a silver grid: Brick texture again, glossy so the sun skims across."""
    mat = kit.material('Solar cells', '#0B1A3A', roughness=0.22, metallic=0.3, coat=0.6)
    nt = mat.node_tree
    tc = nt.nodes.new('ShaderNodeTexCoord')
    brick = nt.nodes.new('ShaderNodeTexBrick')
    brick.offset = 0.0
    brick.inputs['Scale'].default_value = 1.6
    brick.inputs['Mortar Size'].default_value = 0.03
    brick.inputs['Color1'].default_value = (0.008, 0.02, 0.07, 1)
    brick.inputs['Color2'].default_value = (0.012, 0.03, 0.09, 1)
    brick.inputs['Mortar'].default_value = (0.4, 0.42, 0.45, 1)
    brick.inputs['Brick Width'].default_value = 1.0
    brick.inputs['Row Height'].default_value = 0.5
    nt.links.new(tc.outputs['Object'], brick.inputs['Vector'])
    nt.links.new(brick.outputs['Color'], kit.bsdf(mat).inputs['Base Color'])
    return mat


def earth_material(kit):
    """Oceans, continents and a terminator-friendly glossy/rough split from one noise land mask."""
    mat = bpy.data.materials.new('Earth surface')
    mat.use_nodes = True
    nt = mat.node_tree
    bs = kit.bsdf(mat)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    norm = nt.nodes.new('ShaderNodeVectorMath')
    norm.operation = 'NORMALIZE'
    nt.links.new(tc.outputs['Object'], norm.inputs[0])
    land = nt.nodes.new('ShaderNodeTexNoise')
    land.inputs['Scale'].default_value = 2.2
    land.inputs['Detail'].default_value = 15
    land.inputs['Roughness'].default_value = 0.62
    nt.links.new(norm.outputs[0], land.inputs['Vector'])
    mask = nt.nodes.new('ShaderNodeMapRange')
    mask.inputs['From Min'].default_value, mask.inputs['From Max'].default_value = 0.52, 0.545
    nt.links.new(land.outputs['Fac'], mask.inputs['Value'])
    # Land colour: arid tan to forest green, varied by a second noise.
    veg = nt.nodes.new('ShaderNodeTexNoise')
    veg.inputs['Scale'].default_value = 9.0
    veg.inputs['Detail'].default_value = 10
    nt.links.new(norm.outputs[0], veg.inputs['Vector'])
    land_ramp = nt.nodes.new('ShaderNodeValToRGB')
    els = land_ramp.color_ramp.elements
    els[0].position, els[0].color = 0.35, (0.05, 0.09, 0.03, 1)
    els[1].position, els[1].color = 0.65, (0.30, 0.22, 0.12, 1)
    nt.links.new(veg.outputs['Fac'], land_ramp.inputs['Fac'])
    # Ocean: deep blue, a touch lighter in the shallows near coasts.
    sea = nt.nodes.new('ShaderNodeValToRGB')
    els = sea.color_ramp.elements
    els[0].position, els[0].color = 0.40, (0.004, 0.014, 0.05, 1)
    els[1].position, els[1].color = 0.53, (0.02, 0.09, 0.16, 1)
    nt.links.new(land.outputs['Fac'], sea.inputs['Fac'])
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    nt.links.new(mask.outputs['Result'], mix.inputs['Factor'])
    nt.links.new(sea.outputs['Color'], mix.inputs['A'])
    nt.links.new(land_ramp.outputs['Color'], mix.inputs['B'])
    nt.links.new(mix.outputs['Result'], bs.inputs['Base Color'])
    rough = nt.nodes.new('ShaderNodeMapRange')
    rough.inputs['To Min'].default_value, rough.inputs['To Max'].default_value = 0.18, 0.95
    nt.links.new(mask.outputs['Result'], rough.inputs['Value'])
    nt.links.new(rough.outputs['Result'], bs.inputs['Roughness'])
    return mat


def cloud_material(kit):
    """Cloud shell: white where a cloud noise exceeds a threshold, transparent elsewhere."""
    mat = bpy.data.materials.new('Cloud layer')
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    norm = nt.nodes.new('ShaderNodeVectorMath')
    norm.operation = 'NORMALIZE'
    nt.links.new(tc.outputs['Object'], norm.inputs[0])
    n = nt.nodes.new('ShaderNodeTexNoise')
    n.inputs['Scale'].default_value = 7.0
    n.inputs['Detail'].default_value = 14
    n.inputs['Roughness'].default_value = 0.6
    n.inputs['Distortion'].default_value = 0.4
    nt.links.new(norm.outputs[0], n.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeMapRange')
    ramp.inputs['From Min'].default_value, ramp.inputs['From Max'].default_value = 0.53, 0.66
    nt.links.new(n.outputs['Fac'], ramp.inputs['Value'])
    diff = nt.nodes.new('ShaderNodeBsdfDiffuse')
    diff.inputs['Color'].default_value = (0.85, 0.87, 0.9, 1)
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(ramp.outputs['Result'], mix.inputs['Fac'])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(diff.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    return mat


def limb_material(kit):
    """Atmosphere limb: emission that rises steeply toward grazing angles (Layer Weight facing)."""
    mat = bpy.data.materials.new('Atmosphere limb')
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    lw = nt.nodes.new('ShaderNodeLayerWeight')
    lw.inputs['Blend'].default_value = 0.5
    pw = nt.nodes.new('ShaderNodeMath')
    pw.operation = 'POWER'
    pw.inputs[1].default_value = 6.0
    nt.links.new(lw.outputs['Facing'], pw.inputs[0])
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (0.25, 0.5, 1.0, 1)
    em.inputs['Strength'].default_value = 2.2
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    add = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(pw.outputs[0], add.inputs['Fac'])
    nt.links.new(tr.outputs[0], add.inputs[1])
    nt.links.new(em.outputs[0], add.inputs[2])
    nt.links.new(add.outputs[0], out.inputs['Surface'])
    return mat


def starfield_world(kit):
    """Black space with sparse stars: a thresholded Voronoi on the view direction."""
    world = kit.world('#000000', strength=1.0)
    nt = world.node_tree
    bg = next(n for n in nt.nodes if n.type == 'BACKGROUND')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    vor = nt.nodes.new('ShaderNodeTexVoronoi')
    vor.inputs['Scale'].default_value = 140.0
    nt.links.new(tc.outputs['Generated'], vor.inputs['Vector'])
    star = nt.nodes.new('ShaderNodeMapRange')
    star.inputs['From Min'].default_value, star.inputs['From Max'].default_value = 0.075, 0.0
    nt.links.new(vor.outputs['Distance'], star.inputs['Value'])
    bright = nt.nodes.new('ShaderNodeMath')
    bright.operation = 'MULTIPLY'
    nt.links.new(star.outputs['Result'], bright.inputs[0])
    nt.links.new(vor.outputs['Color'], bright.inputs[1])   # random per-star brightness
    gain = nt.nodes.new('ShaderNodeMath')
    gain.operation = 'POWER'
    gain.inputs[1].default_value = 3.0
    nt.links.new(bright.outputs[0], gain.inputs[0])
    nt.links.new(gain.outputs[0], bg.inputs['Strength'])
    bg.inputs['Color'].default_value = (1.0, 0.97, 0.92, 1)
    # Stars should not light the set: only camera rays see them.
    try:
        world.cycles_visibility.diffuse = False
        world.cycles_visibility.glossy = False
    except AttributeError:
        kit.note('world ray visibility unavailable; stars may add a negligible fill')
    return world


def puff_material(kit):
    """RCS puff: emissive-scattering white that fades with the object's own colour alpha."""
    mat = bpy.data.materials.new('RCS puff')
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    info = nt.nodes.new('ShaderNodeObjectInfo')
    lw = nt.nodes.new('ShaderNodeLayerWeight')
    lw.inputs['Blend'].default_value = 0.6
    inv = nt.nodes.new('ShaderNodeMath')
    inv.operation = 'SUBTRACT'
    inv.inputs[0].default_value = 1.0
    nt.links.new(lw.outputs['Facing'], inv.inputs[1])        # dense in the middle, soft edges
    fac = nt.nodes.new('ShaderNodeMath')
    fac.operation = 'MULTIPLY'
    nt.links.new(inv.outputs[0], fac.inputs[0])
    nt.links.new(info.outputs['Alpha'], fac.inputs[1])
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (0.9, 0.93, 1.0, 1)
    em.inputs['Strength'].default_value = 3.0
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(fac.outputs[0], mix.inputs['Fac'])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    return mat


# ----------------------------------------------------------------------------- station
def build_station(kit, rng, mats):
    root = kit.empty('Station', location=(0, 0, 0))
    parts = []

    # Hub along X, with ribs every 4 m.
    hub = kit.cylinder('Hub', radius=HUB_R, depth=HUB_LEN, rotation=(0, 90, 0), material=mats['white'],
                       segments=64, bevel=0.15)
    parts.append(hub)
    for k in range(-5, 6):
        parts.append(kit.torus(f'Hub rib {k + 5}', radius=HUB_R + 0.05, thickness=0.16, location=(k * 4.0, 0, 0),
                               rotation=(0, 90, 0), material=mats['grey'], segments=64, sides=8))
    # Gold-foiled service module at the aft end and the docking port at the front.
    parts.append(kit.cylinder('Service module', radius=HUB_R * 1.1, depth=6.0, location=(-HUB_LEN / 2 - 3, 0, 0),
                              rotation=(0, 90, 0), material=mats['foil'], segments=48, bevel=0.2))
    parts.append(kit.cylinder('Port collar', radius=1.9, depth=1.9, location=(HUB_LEN / 2 + 0.95, 0, 0),
                              rotation=(0, 90, 0), material=mats['grey'], segments=48, bevel=0.08))
    parts.append(kit.torus('Port seal ring', radius=1.75, thickness=0.22, location=(PORT_X, 0, 0),
                           rotation=(0, 90, 0), material=mats['dark'], segments=64, sides=12))
    parts.append(kit.box('Docking target', size=(0.08, 0.5, 2.0), location=(HUB_LEN / 2 + 0.2, 0, 2.6),
                         material=mats['dark']))

    # Ring, its module joints, spokes and window strip.
    parts.append(kit.torus('Habitat ring', radius=RING_R, thickness=RING_TUBE, rotation=(0, 90, 0),
                           material=mats['white'], segments=220, sides=32))
    win = Batch()
    for j in range(16):
        a = 2 * math.pi * j / 16
        centre = Vector((0, RING_R * math.cos(a), RING_R * math.sin(a)))
        tangent = Vector((0, -math.sin(a), math.cos(a)))
        joint = kit.torus(f'Ring joint {j:02d}', radius=RING_TUBE + 0.12, thickness=0.28, location=centre,
                          material=mats['grey'], segments=48, sides=10)
        joint.rotation_euler = tangent.to_track_quat('Z', 'X').to_euler()
        parts.append(joint)
    for j in range(160):
        a = 2 * math.pi * (j + 0.5) / 160
        if j % 10 in (0, 9):
            continue                          # leave the joints clear
        radial = Vector((0, math.cos(a), math.sin(a)))
        for side in (-1, 1):
            n = (radial * 0.82 + Vector((side * 0.57, 0, 0))).normalized()
            p = radial * RING_R + n * (RING_TUBE + 0.01)
            win.box(frame_at(p, n), (0.5, 0.9, 0.06))
    parts.append(win.build(kit, 'Ring windows', mats['window']))
    for s in range(6):
        a = 2 * math.pi * s / 6 + math.pi / 12
        radial = Vector((0, math.cos(a), math.sin(a)))
        a_mid = radial * (HUB_R + RING_R - RING_TUBE) / 2
        spoke = kit.cylinder(f'Spoke {s}', radius=0.9, depth=RING_R - RING_TUBE - HUB_R + 0.6, location=a_mid,
                             material=mats['white'], segments=24, bevel=0.05)
        spoke.rotation_euler = radial.to_track_quat('Z', 'X').to_euler()
        parts.append(spoke)
        # A thin cable tray along each spoke: mid-scale detail.
        tray = kit.box(f'Spoke tray {s}', size=(0.35, 0.35, RING_R - RING_TUBE - HUB_R), location=a_mid,
                       material=mats['dark'])
        tray.rotation_euler = radial.to_track_quat('Z', 'X').to_euler()
        tray.location += tangent_of(a) * 0.95
        parts.append(tray)

    # Solar wings and radiators on a truss behind the service module.
    truss = kit.box('Aft truss', size=(10, 1.2, 1.2), location=(-HUB_LEN / 2 - 11, 0, 0), material=mats['grey'],
                    bevel=0.05)
    parts.append(truss)
    for k, a in enumerate((0, 90, 180, 270)):
        d = Vector((0, math.cos(math.radians(a)), math.sin(math.radians(a))))
        for w, x in enumerate((-HUB_LEN / 2 - 8.5, -HUB_LEN / 2 - 13.5)):
            wing = kit.box(f'Solar wing {k}{w}', size=(4.2, 0.08, 20.0), location=Vector((x, 0, 0)) + d * 12.0,
                           material=mats['solar'])
            wing.rotation_euler = (math.radians(a + 90), 0, 0)
            parts.append(wing)
        parts.append(kit.cylinder(f'Wing mast {k}', radius=0.18, depth=22.5, location=Vector((-HUB_LEN / 2 - 11, 0, 0)) + d * 11.6,
                                  rotation=(math.radians(a + 90), 0, 0), material=mats['grey'], segments=12))
    for k in (-1, 1):
        rad = kit.box(f'Radiator {k}', size=(9.0, 0.12, 5.0), location=(-HUB_LEN / 2 + 6, k * (HUB_R + 3.2), 0),
                      material=mats['radiator'], bevel=0.03)
        parts.append(rad)

    # Greebles: batched boxes on the hub and ring skin (tanks, antennas, handrail stand-offs).
    greeb = Batch()
    for _ in range(140):
        x = rng.uniform(-HUB_LEN / 2 + 1, HUB_LEN / 2 - 1)
        a = rng.uniform(0, 2 * math.pi)
        n = Vector((0, math.cos(a), math.sin(a)))
        s = (rng.uniform(0.3, 1.4), rng.uniform(0.3, 1.0), rng.uniform(0.1, 0.5))
        greeb.box(frame_at(Vector((x, 0, 0)) + n * (HUB_R + s[2] / 2), n), s)
    for _ in range(420):
        a = rng.uniform(0, 2 * math.pi)
        radial = Vector((0, math.cos(a), math.sin(a)))
        b = rng.uniform(-2.2, 2.2)
        n = (radial * math.cos(b) + Vector((math.sin(b), 0, 0))).normalized()
        s = (rng.uniform(0.2, 1.1), rng.uniform(0.2, 0.8), rng.uniform(0.08, 0.35))
        greeb.box(frame_at(radial * RING_R + n * (RING_TUBE + s[2] / 2 - 0.02), n), s)
    parts.append(greeb.build(kit, 'Station greebles', mats['grey'], bevel=0.02))

    for p in parts:
        kit.parent(p, root)
    # Nav lights: red/green blinkers at the ring's extremes.
    for k, (col, a) in enumerate((('#FF2A1A', 0.0), ('#21FF5A', math.pi))):
        lamp = kit.sphere(f'Nav light {k}', radius=0.25, location=(0, (RING_R + RING_TUBE + 0.2) * math.cos(a), 0),
                          material=kit.emissive(f'Nav {k}', col, 40.0), segments=12, rings=6)
        kit.parent(lamp, root)
    return root


def tangent_of(a):
    return Vector((0, -math.sin(a), math.cos(a)))


# ----------------------------------------------------------------------------- shuttle
def build_shuttle(kit, mats):
    """A 12 m crew shuttle built along local +Z (nose at +Z), under a frame empty."""
    frame = kit.empty('Shuttle frame')
    parts = []
    hull = kit.lathe('Shuttle hull', [(0, 0), (1.15, 0), (1.5, 0.35), (1.62, 1.6), (1.62, 7.6), (1.45, 9.4),
                                      (1.05, 10.9), (0.62, 11.6), (0.0, 11.75)],
                     segments=48, material=mats['white2'])
    kit.bevel(hull, width=0.02, segments=1)
    parts.append(hull)
    # Heat-tile band and cockpit glazing near the nose.
    parts.append(kit.cylinder('Tile band', radius=1.64, depth=1.2, location=(0, 0, 2.2), material=mats['tiles'],
                              segments=48))
    glass = kit.material('Cockpit glass', '#05070A', roughness=0.05, coat=1.0)
    for k in range(5):
        a = math.radians(-40 + 20 * k)
        w = kit.box(f'Cockpit window {k}', size=(0.42, 0.05, 0.55), location=(1.28 * math.sin(a), -1.28 * math.cos(a), 9.9),
                    material=glass, bevel=0.03)
        w.rotation_euler = (math.radians(-20), 0, a)
        parts.append(w)
    parts.append(kit.cylinder('Docking adapter', radius=0.7, depth=0.9, location=(0, 0, 11.9), material=mats['grey'],
                              segments=32, bevel=0.05))
    parts.append(kit.torus('Adapter seal', radius=0.66, thickness=0.12, location=(0, 0, 12.35), material=mats['dark'],
                           segments=32, sides=8))
    for k, x in enumerate((-0.6, 0.6)):
        parts.append(kit.lathe(f'Engine bell {k}', [(0.18, 0.4), (0.25, 0.1), (0.55, -0.9), (0.5, -0.9), (0.2, 0.05)],
                               segments=32, material=mats['bell'], location=(x, 0, 0)))
    # Swept fins and RCS quads.
    fin = [(0, 0), (2.6, 0.4), (2.8, 1.4), (0, 4.5)]
    for k, s in enumerate((-1, 1)):
        f = kit.extrude(f'Fin {k}', [(s * x, y) for x, y in (fin if s > 0 else list(reversed(fin)))], height=0.14,
                        material=mats['white2'], bevel=0.03)
        f.rotation_euler = (math.radians(90), 0, 0)
        f.location = (s * 1.35, 0.07, 0.8)
        parts.append(f)
    puffs = []
    puff_mat = puff_material(kit)
    for ring_z, forward in ((10.2, True), (1.2, False)):
        for k in range(4):
            a = math.pi / 4 + k * math.pi / 2
            n = Vector((math.cos(a), math.sin(a), 0))
            q = kit.box(f'RCS quad {ring_z:.0f}-{k}', size=(0.36, 0.36, 0.36), location=n * 1.55 + Vector((0, 0, ring_z)),
                        material=mats['dark'], bevel=0.03)
            parts.append(q)
            if forward:
                # The braking puff points forward and outward from the nose quad.
                d = (n * 0.45 + Vector((0, 0, 1))).normalized()
                p = kit.sphere(f'RCS puff {k}', radius=0.5, location=n * 1.75 + Vector((0, 0, ring_z)) + d * 1.0,
                               material=puff_mat, segments=16, rings=8, scale=(0.55, 0.55, 1.9))
                p.rotation_euler = d.to_track_quat('Z', 'X').to_euler()
                p.visible_shadow = False
                puffs.append(p)
    for p in parts + puffs:
        kit.parent(p, frame)
    return frame, puffs


# ----------------------------------------------------------------------------- build
def build(kit):
    rng = kit.rng
    mats = {
        'white': panel_white(kit),
        'white2': panel_white(kit, 'Shuttle panels', '#E6E6E3', scale=0.9),
        'grey': kit.material('Truss grey', '#6E7174', roughness=0.42, metallic=0.6),
        'dark': kit.material('Dark composite', '#1A1B1D', roughness=0.5),
        'foil': gold_foil(kit),
        'solar': solar_cells(kit),
        'radiator': kit.material('Radiator white', '#F1F1EE', roughness=0.3, coat=0.4, bump=(6, 0.1)),
        'window': kit.emissive('Lit windows', '#FFC98A', 6.0),
        'tiles': kit.material('Heat tiles', '#141414', roughness=0.8, bump=(40, 0.2)),
        'bell': kit.material('Niobium bell', '#3B3631', roughness=0.35, metallic=1.0),
    }

    # --- Earth below ---------------------------------------------------------------------
    earth_c = (0, 0, -(EARTH_R + ALTITUDE))
    earth = kit.sphere('Earth', radius=EARTH_R, location=earth_c, material=earth_material(kit), segments=512, rings=256)
    clouds = kit.sphere('Cloud layer', radius=EARTH_R * 1.0012, location=earth_c, material=cloud_material(kit),
                        segments=512, rings=256)
    limb = kit.sphere('Atmosphere limb', radius=EARTH_R * 1.01, location=earth_c, material=limb_material(kit),
                      segments=512, rings=256)
    limb.visible_shadow = False
    clouds.visible_shadow = False
    # Tilt the planet so a coastline sits under the station, and let it drift slowly.
    earth.rotation_euler = clouds.rotation_euler = (0.6, 0.3, 0.0)
    kit.animate(earth, 'rotation_euler', lambda t: (0.6 + 0.0004 * t, 0.3, 0.0), step=24)
    kit.animate(clouds, 'rotation_euler', lambda t: (0.6 + 0.0005 * t, 0.3, 0.0), step=24)

    # --- the station and its slow spin ---------------------------------------------------------
    station = build_station(kit, rng, mats)
    spin = lambda t: 2 * math.pi * SPIN_TURNS * t          # noqa: E731
    kit.animate(station, 'rotation_euler', lambda t: (spin(t), 0, 0), step=4)

    # --- the shuttle: approach, brake, spin-match, dock ----------------------------------------
    frame, puffs = build_shuttle(kit, mats)
    root = kit.empty('Shuttle', location=(START_X, 0, 0))
    kit.parent(frame, root, keep_transform=False)
    frame.rotation_euler = (0, math.radians(-90), 0)       # local +Z (nose) points to world -X
    dock_x = PORT_X + 12.35                                # nose adapter seal meets the port seal

    def shuttle_x(t):
        u = min(t / DOCK_T, 1.0)
        return dock_x + (START_X - dock_x) * (1 - u) ** 2.2   # decelerating approach, zero speed at contact

    # Small lateral misalignment that the pilot trims out before contact.
    def shuttle_loc(t):
        u = min(t / DOCK_T, 1.0)
        return (shuttle_x(t), 1.4 * (1 - u) ** 1.5, -0.8 * (1 - u) ** 1.8)

    kit.animate(root, 'location', shuttle_loc, step=2)
    kit.animate(root, 'rotation_euler', lambda t: (spin(t) + math.radians(8) * (1 - min(t / DOCK_T, 1)) ** 2, 0, 0),
                step=2)

    # RCS bursts while braking: short fades on the per-object colour alpha, with a scale pop.
    bursts = [(0.18, 0.05), (0.42, 0.05), (0.58, 0.04), (0.71, 0.03)]

    def puff_alpha(t):
        a = 0.0
        for t0, dur in bursts:
            if t0 <= t <= t0 + dur * 2.2:
                u = (t - t0) / (dur * 2.2)
                a = max(a, math.sin(math.pi * min(u * 2.0, 1.0)) if u < 0.5 else (1 - u) * 2)
        return a

    for k, p in enumerate(puffs):
        kit.animate(p, 'color', lambda t, k=k: (1, 1, 1, puff_alpha(t - 0.004 * k)), step=1)
        base = p.scale.copy()
        kit.animate(p, 'scale', lambda t, b=base, k=k: tuple(c * (0.4 + 0.9 * puff_alpha(t - 0.004 * k)) for c in b),
                    step=1)

    # --- light: harsh sun, earthshine fill, nothing else -----------------------------------------
    kit.sun(elevation=SUN_ELEV, azimuth=SUN_AZ, strength=5.5, color='#FFF8F0', angle=0.53)
    kit.area('Earthshine', location=(40, -20, -60), target=(10, 0, 0), power=6.0e4, color='#9DB8E8', size=80)
    starfield_world(kit)
    kit.render(look='AgX - Medium High Contrast', exposure=-0.2, motion_blur=True, shutter=0.4)

    # --- camera: track alongside the shuttle, trailing and slightly above ---------------------------
    cam = kit.camera(location=(START_X + 24, -40, 9), target=(START_X - 14, 0, -1), lens=28, clip=(0.5, 400000))

    def cam_loc(t):
        x = shuttle_x(min(t, 1.0))
        return (x + 24 - 6 * t, -40 + 6 * t, 9 + 2 * t)

    def cam_target(t):
        x = shuttle_x(min(t, 1.0))
        return (x - 15 - 6 * t, 0, -1.5)

    kit.animate(cam, 'location', cam_loc, step=2)
    kit.animate(kit.target_of(cam), 'location', cam_target, step=2)
