"""A sphere of ceramic shards breathes open around a glowing core, as a seamless loop.

Teaching points
- True spherical Voronoi shards without any add-on: start from a thick spherical shell and, for
  each seed point, bisect it by the plane halfway to every nearby seed (planes through the
  centre). What is left is exactly that seed's Voronoi cell, with flat fracture walls, a curved
  glazed outside and a curved inside. Offsetting each plane by half a gap leaves clean cracks.
- Two materials per shard from face normals: glazed ceramic outside, rough unglazed bisque on the
  fracture walls. That contrast is what sells 'broken ceramic' rather than 'segmented ball'.
- The core is an emissive sphere that is invisible to shadow rays, with an orange point light
  inside it: the light leaks through the cracks while closed, then floods the fracture walls.
- Loop safety: every motion is a function of |sin(pi * (t - delay))|, which repeats exactly every
  shot, so frame frames+1 equals frame 1 even with per-shard delays.
- Soft studio look: a vertical gradient world (dark floor, bright 'ceiling') does what a studio
  HDRI does, and two cool rim strips outline the silhouette against the dark background.
"""
import math

import bmesh
import bpy
from mathutils import Vector
from mathutils.kdtree import KDTree

# ----------------------------------------------------------------------------- constants
CENTRE = Vector((0.0, 0.0, 1.65))
R_OUT, R_IN = 1.0, 0.70          # shell radii (m)
SHARDS = 64
GAP = 0.010                      # crack width between closed shards
BREATH = 0.42                    # how far a shard drifts out at full breath (m)
CORE_R = 0.52
CERAMIC = '#E9E3D9'
BISQUE = '#C7B39C'
EMBER = '#FF6A12'


def fibonacci_sphere(n, rng, jitter=0.18):
    """Evenly spread seeds, jittered so the cells are irregular like a real fracture."""
    pts = []
    golden = math.pi * (3 - math.sqrt(5))
    for i in range(n):
        y = 1 - 2 * (i + 0.5) / n
        r = math.sqrt(1 - y * y)
        a = golden * i
        p = Vector((r * math.cos(a), y, r * math.sin(a)))
        p += Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1))) * jitter / math.sqrt(n / 12)
        pts.append(p.normalized())
    return pts


def shell_bmesh():
    """A closed thick spherical shell: outer UV sphere plus an inward-facing inner sphere."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=96, v_segments=48, radius=R_OUT)
    inner = bmesh.new()
    bmesh.ops.create_uvsphere(inner, u_segments=64, v_segments=32, radius=R_IN)
    bmesh.ops.reverse_faces(inner, faces=inner.faces[:])
    me = bpy.data.meshes.new('tmp inner')
    inner.to_mesh(me)
    inner.free()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)
    return bm


def voronoi_shard(seed, neighbours):
    """Cut the shell down to one spherical Voronoi cell (see module notes)."""
    bm = shell_bmesh()
    for other in neighbours:
        n = (other - seed).normalized()            # plane normal points toward the neighbour
        # The bisector of two unit seeds passes through the centre; shift it back by half a gap.
        co = -n * (GAP / 2)
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        res = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=n, clear_outer=True)
        cut_edges = [e for e in res['geom_cut'] if isinstance(e, bmesh.types.BMEdge)]
        if cut_edges:
            bmesh.ops.holes_fill(bm, edges=cut_edges, sides=0)
        if not bm.faces:
            break
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    return bm


# ----------------------------------------------------------------------------- materials
def ceramic_glaze(kit):
    mat = kit.material('Ceramic glaze', CERAMIC, roughness=0.42, coat=0.25, subsurface=0.08,
                       subsurface_radius=(0.02, 0.015, 0.01), bump=(60, 0.04))
    kit.bsdf(mat).inputs['Coat Roughness'].default_value = 0.3
    return mat


def bisque(kit):
    """Unglazed fracture: rougher, warmer, with a granular bump."""
    return kit.material('Bisque fracture', BISQUE, roughness=0.9, bump=(240, 0.25))


def molten_core(kit):
    """Emission driven by layered noise: deep red veins in a bright orange-yellow body."""
    mat = bpy.data.materials.new('Molten core')
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 3.5
    noise.inputs['Detail'].default_value = 8
    noise.inputs['Distortion'].default_value = 0.6
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.32, (0.55, 0.05, 0.0, 1)
    els[1].position, els[1].color = 0.62, (1.0, 0.55, 0.12, 1)
    nt.links.new(tc.outputs['Object'], noise.inputs['Vector'])
    nt.links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], em.inputs['Color'])
    em.inputs['Strength'].default_value = 6.0
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    return mat, em


# ----------------------------------------------------------------------------- motion
def breath(t, delay=0.0, power=1.6):
    """0 (closed) .. 1 (open) .. 0, periodic in t with period 1: loop-safe for any delay."""
    return abs(math.sin(math.pi * (t - delay))) ** power


# ----------------------------------------------------------------------------- build
def build(kit):
    rng = kit.rng
    glaze, frac = ceramic_glaze(kit), bisque(kit)

    seeds = fibonacci_sphere(SHARDS, rng)
    tree = KDTree(len(seeds))
    for i, s in enumerate(seeds):
        tree.insert(s, i)
    tree.balance()

    shards = kit.collection('Shards')
    for i, s in enumerate(seeds):
        near = [seeds[j] for (_, j, _) in tree.find_n(s, 14) if j != i]
        bm = voronoi_shard(s, near)
        if not bm.faces:
            bm.free()
            continue
        # Recentre the shard on its own centroid so it can move and tilt about itself.
        centroid = sum((v.co for v in bm.verts), Vector()) / len(bm.verts)
        bmesh.ops.translate(bm, verts=bm.verts[:], vec=-centroid)
        me = bpy.data.meshes.new(f'Shard {i:02d}')
        bm.to_mesh(me)
        bm.free()
        obj = bpy.data.objects.new(f'Shard {i:02d}', me)
        obj.location = CENTRE + centroid
        shards.objects.link(obj)
        me.materials.append(glaze)
        me.materials.append(frac)
        out_dir = centroid.normalized()
        for p in me.polygons:
            # Outer skin faces point along the shard's radial direction; everything else is a
            # fracture wall or the inner skin.
            world_c = p.center + centroid
            outer = p.normal.dot(world_c.normalized()) > 0.75 and world_c.length > (R_OUT + R_IN) / 2
            p.material_index = 0 if outer else 1
            p.use_smooth = outer
        kit.bevel(obj, width=0.006, segments=2, harden=True)

        # Breathing: drift out along the radial direction with a slight tumble. Shards nearer the
        # camera-facing 'equator' lead, so the opening ripples across the sphere.
        delay = 0.05 * (1 - out_dir.y) / 2 + rng.uniform(0.0, 0.02)
        amount = BREATH * rng.uniform(0.75, 1.15)
        axis = out_dir.cross(Vector((0, 0, 1))).normalized() if abs(out_dir.z) < 0.99 else Vector((1, 0, 0))
        tilt = math.radians(rng.uniform(6, 14))
        base_loc = obj.location.copy()

        def loc_fn(t, base=base_loc, d=out_dir, a=amount, dl=delay):
            return base + d * a * breath(t, dl)

        def rot_fn(t, ax=axis, tl=tilt, dl=delay):
            return (ax * tl * breath(t, dl)).to_tuple()

        kit.animate(obj, 'location', loc_fn, step=2, interpolation='BEZIER')
        kit.animate(obj, 'rotation_euler', rot_fn, step=2, interpolation='BEZIER')

    # --- the glowing core ----------------------------------------------------------------
    core_mat, core_em = molten_core(kit)
    core = kit.sphere('Molten core', radius=CORE_R, location=CENTRE, material=core_mat, segments=64, rings=32)
    core.visible_shadow = False
    kit.displace(core, strength=0.03, scale=0.4, kind='CLOUDS', detail=3)
    kit.animate(core_em.inputs['Strength'], 'default_value', lambda t: 4.0 + 6.0 * breath(t, 0.02), step=2)
    glow = kit.point('Core light', location=CENTRE, power=900.0, color=EMBER, radius=0.35)
    kit.animate(glow.data, 'energy', lambda t: 260.0 + 1500.0 * breath(t, 0.02), step=2)
    # The core turns once per loop so the molten pattern moves (a whole turn is loop-safe).
    kit.spin(core, axis='Z', turns=1.0)

    # --- studio: dark cyc floor, gradient 'HDRI' world, cool rims -------------------------
    floor = kit.material('Studio floor', '#1A1B1F', roughness=0.35, coat=0.3)
    kit.ground(floor, size=60)
    kit.world('#07080A', strength=1.0, top='#5E646E')
    kit.area('Overhead softbox', location=(0.0, -1.0, 6.0), target=CENTRE, power=900.0, color='#F3F1EC',
             size=4.0)
    kit.area('Rim left', location=(-3.2, 2.6, 2.6), target=CENTRE, power=650.0, color='#CFE0FF', size=0.5,
             size_y=3.0)
    kit.area('Rim right', location=(3.2, 2.4, 2.2), target=CENTRE, power=500.0, color='#D8E6FF', size=0.5,
             size_y=3.0)
    kit.haze(density=0.012, color='#FFFFFF', anisotropy=0.4, size=(10, 10, 6), location=(0, 0, 2.6))
    kit.render(look='AgX - Medium High Contrast', exposure=0.0, motion_blur=False)

    # --- camera: static and centred ----------------------------------------------------------
    kit.camera(location=(0.0, -9.5, 2.35), target=CENTRE + Vector((0, 0, -0.08)), lens=80, dof=9.4, fstop=5.6)
