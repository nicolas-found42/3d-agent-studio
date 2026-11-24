"""Trusted Blender entry point. Never evaluates brief text as code."""
import json
import math
from pathlib import Path
import random
import sys

import bpy
from mathutils import Vector

# Blender runs this file directly in its own Python, outside the installed CLI environment.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_studio.formats import stage_size

TAU = 2 * math.pi


def color(hexstr):
    rgb = [int(hexstr[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return tuple(c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in rgb)


def material(name, rgb, metal=0, rough=.4, glow=0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*rgb, 1)
    mat.use_nodes = True
    bs = mat.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (*rgb, 1)
    bs.inputs['Metallic'].default_value = metal
    bs.inputs['Roughness'].default_value = rough
    bs.inputs['Emission Color'].default_value = (*rgb, 1)
    bs.inputs['Emission Strength'].default_value = glow
    return mat


def mesh_part(name, mat, bevel=0, smooth=True):
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    if bevel:
        m = obj.modifiers.new('Manufactured edges', 'BEVEL')
        m.width, m.segments = bevel, 3
        obj.modifiers.new('Face normals', 'WEIGHTED_NORMAL')
    if smooth:
        for p in obj.data.polygons:
            p.use_smooth = True
    return obj


def cube(name, loc, dims, mat, bevel=.04):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = mesh_part(name, mat, bevel, False)
    obj.dimensions = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj


def tube(name, loc, r, depth, mat, bevel=.025):
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=r, depth=depth, location=loc)
    return mesh_part(name, mat, bevel)


def torus(name, loc, r, wire, mat):
    bpy.ops.mesh.primitive_torus_add(location=loc, major_radius=r, minor_radius=wire, major_segments=64, minor_segments=10)
    return mesh_part(name, mat)


def orb(name, loc, r, mat):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=r, location=loc)
    return mesh_part(name, mat, smooth=False)


def body_shell(name, z, top, mat):
    # Real shallow ceramic wall and lip, not a clipped sphere. Each profile is closed around Z.
    profile = [(0.02, .44), (.19, .43), (.36, .32), (.48, .14), (.50, .01),
               (.45, -.01), (.43, .13), (.32, .28), (.16, .38), (.02, .39)]
    n = 64
    v = [(r * math.cos(TAU * j/n), r * math.sin(TAU * j/n), (1 if top else -1) * h)
         for r, h in profile for j in range(n)]
    f = [(k*n+j, k*n+(j+1)%n, ((k+1)%len(profile))*n+(j+1)%n, ((k+1)%len(profile))*n+j)
         for k in range(len(profile)) for j in range(n)]
    if top:
        f = [tuple(reversed(face)) for face in f]
    mesh = bpy.data.meshes.new(name); mesh.from_pydata(v, [], f); mesh.update()
    obj = bpy.data.objects.new(name, mesh); bpy.context.collection.objects.link(obj)
    obj.location.z = z
    mesh.materials.append(mat)
    for poly in mesh.polygons:
        poly.use_smooth = True
    return obj


def aim(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()


def area(name, loc, hue, energy, size, target=(0,0,2.7)):
    data = bpy.data.lights.new(name, 'AREA')
    data.color, data.energy, data.shape, data.size = hue, energy, 'DISK', size
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = loc; aim(obj, target)
    return obj


def camera(name, loc, target, scale, clip=.05):
    d = bpy.data.cameras.new(name); d.type = 'ORTHO'; d.sensor_fit = 'VERTICAL'
    d.ortho_scale, d.clip_start, d.clip_end = scale, clip, 100
    obj = bpy.data.objects.new(name, d); bpy.context.collection.objects.link(obj)
    obj.location = loc; aim(obj, target)
    return obj


def text(cam, scene, name, body, u, v, height, mat, right_edge=.90):
    curve = bpy.data.curves.new(name, 'FONT'); curve.body = body; curve.size = height
    obj = bpy.data.objects.new(name, curve); bpy.context.collection.objects.link(obj)
    obj.parent = cam
    points = cam.data.view_frame(scene=scene)
    w, h = max(p.x for p in points), max(p.y for p in points)
    obj.location = ((u * 2 - 1)*w, (v * 2 - 1)*h, -3.3)
    obj.data.materials.append(mat)
    bpy.context.view_layer.update()
    max_width = 2 * w * (right_edge - u)
    if obj.dimensions.x > max_width:
        curve.size *= max_width / obj.dimensions.x
    return obj


def hero(scene, spec, hot, ink):
    is_conveyor = spec['template'] == 'gravity-conveyor'
    suffix = '01 / CERAMIC MECHANISM' if is_conveyor else '02 / RADIAL KINETIC SCULPTURE'
    loc = Vector((6.0, -14.5, 7.0))
    look = Vector((.02 if is_conveyor else .17, 0, 2.54))
    if spec['orientation'] == 'horizontal':
        # Translate the orthographic rig sideways without changing its viewing angle.
        # Keep the left column for type and the full mechanism in the right column.
        right = (look - loc).normalized().cross(Vector((0, 0, 1))).normalized()
        shift = right * 1.93
        cam = camera('Hero / native landscape', loc - shift, look - shift,
                     6.35 if is_conveyor else 6.65)
        text(cam, scene, 'Series label', suffix, .105, .635, .125, hot, right_edge=.45)
        text(cam, scene, 'Title', spec['title'].upper(), .105, .542, .48, ink, right_edge=.45)
    else:
        cam = camera('Hero / native portrait', loc, look, 7.75 if is_conveyor else 8.55)
        text(cam, scene, 'Series label', suffix, .11, .894, .083, hot)
        text(cam, scene, 'Title', spec['title'].upper(), .11, .838, .255, ink)
    scene.camera = cam


def conveyor(scene, colors, count, seed):
    pale, hot, dark, trim = colors
    parts = []
    for i, z in enumerate((1.27, 2.79, 4.31)):
        # Rings are structurally fastened to twin stationary rail supports.
        ring = torus(f'Station {i+1} - fixed collar', (0,0,z), .75, .082, trim)
        ring.scale.y = .91
        for side in (-1, 1):
            cube('Anodized collar bracket', (side*.84,.02,z), (.36,.27,.17), trim)
            cube('Status insert', (side*.94,-.13,z), (.16,.025,.043), hot, .013)
        lo = body_shell(f'Capsule {i+1} - lower ceramic', z-.05, False, pale)
        hi = body_shell(f'Capsule {i+1} - upper ceramic', z+.05, True, pale)
        core = orb(f'Capsule {i+1} - radiant core', (0,0,z), .23, hot)
        top_trim = torus(f'Capsule {i+1} - fired seam', (0,0,z+.06), .48, .022, dark)
        parts.append((z, lo, hi, core, top_trim))
    for side in (-1,1):
        cube('Structural spine', (side*.98,.14,2.67), (.15,.28,4.56), dark)
        cube('Spine inlay', (side*.985,-.013,2.76), (.028,.025,4.05), trim, .007)
    rng = random.Random(seed)
    offset = rng.uniform(-.2,.2)
    for n in range(count+1):
        phase = TAU * (n % count)/count
        for i, (z, lo, hi, core, lip) in enumerate(parts):
            p = phase - i*TAU/3 + offset
            spread = .06 + .36 * (.5+.5*math.sin(p))**3
            rise = .105 * math.sin(2*p)
            hi.location.z = z+spread+rise
            lo.location.z = z-spread+rise
            lip.location.z = hi.location.z + .012
            core.location.z = z+rise
            core.rotation_euler = (phase, 2*phase, phase)
            core.scale = (1 + .12*math.sin(p),)*3
            for obj in (lo, hi, lip, core):
                obj.keyframe_insert('location', frame=n+1)
            core.keyframe_insert('rotation_euler', frame=n+1)
            core.keyframe_insert('scale', frame=n+1)
    scene.timeline_markers.new('01 / capsule stations', frame=1)


def bloom(scene, colors, count, seed):
    pale, hot, dark, trim = colors
    rng = random.Random(seed)
    axle = bpy.data.objects.new('Bloom drive', None); bpy.context.collection.objects.link(axle)
    axle.location = (0,0,2.80)
    stand = cube('Tapered display strut', (0,.30,1.25), (.30,.34,2.32), trim)
    stand.rotation_euler.y = -.16
    cube('Hub bearing saddle', (.18,.14,2.48), (.33,.40,.46), trim, .07)
    orb('Dark faceted hub', (0,0,2.80), .43, dark)
    light_ring = torus('Machined central light ring', (0,-.23,2.80), .456,.035,hot)
    light_ring.rotation_euler.x = math.pi / 2
    for k in range(14):
        a = TAU*k/14
        # Local Z is the long axis of each bead, oriented radial in the face plane.
        petal = orb(f'Facet petal {k+1:02d}', (0,0,0), 1, pale if k%3 else trim)
        petal.parent = axle
        length = rng.uniform(.55, .68)
        petal.scale = (.23, .235, length)
        tip = orb(f'Luminous tip {k+1:02d}', (0,0,0), .074, hot)
        tip.parent = petal
        tip.location.z = 1.025
        tip.scale = (1/.23,1/.235,1/length)
        stem = tube(f'Radial stem {k+1:02d}', (0,0,0), .055, 1, trim, .007)
        stem.parent = axle
        for n in range(count+1):
            t = TAU * (n % count)/count
            r = 1.06 + .22 * math.sin(2*a-2*t)
            y = .25 * math.sin(a-2*t)
            petal.location = (math.cos(a)*r, y, math.sin(a)*r)
            bearing = Vector((math.cos(a), .22*math.sin(a+t), math.sin(a)))
            petal.rotation_euler = bearing.to_track_quat('Z','Y').to_euler()
            stem.location = petal.location * .5
            stem.rotation_euler = petal.location.to_track_quat('Z','Y').to_euler()
            stem.scale.z = petal.location.length
            petal.keyframe_insert('location', frame=n+1); petal.keyframe_insert('rotation_euler', frame=n+1)
            for prop in ('location','rotation_euler','scale'):
                stem.keyframe_insert(prop, frame=n+1)
    for n in range(count+1):
        t = TAU * (n % count)/count
        axle.rotation_euler = (.13*math.sin(t), t, .15*math.cos(t))
        axle.keyframe_insert('rotation_euler', frame=n+1)
    scene.timeline_markers.new('01 / orbital bloom', frame=1)


def scene_build(job):
    spec = json.loads((job/'job.json').read_text())['brief']
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = spec['orientation'].upper() + ' / ' + spec['template']
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x, scene.render.resolution_y = stage_size(spec['orientation'], 'master')
    scene.render.resolution_percentage = 100
    scene.render.fps, scene.render.fps_base = 30, 1
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.compression = 10
    scene.render.film_transparent = False
    scene.frame_start, scene.frame_end = 1, spec['seconds']*30
    scene.view_settings.view_transform = 'AgX'
    scene.world = bpy.data.worlds.new('Midnight studio'); scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get('Background')
    bg.inputs['Color'].default_value, bg.inputs['Strength'].default_value = ((.026,.043,.079,1), .33)
    pale = material('Primary / enamel', color(spec['primary']), .21, .25)
    hot = material('Accent / emissive', color(spec['accent']), .22, .29, 2.7)
    dark = material('Midnight steel', (.023,.035,.055), .52, .32)
    trim = material('Machined titanium', (.16,.21,.30), .54, .29)
    floor = material('Studio floor', (.016,.026,.044), .12, .37)
    ink = material('Title / frost', (.78,.87,1), rough=.45, glow=.8)
    colors = pale, hot, dark, trim
    cube('Studio ground', (0,0,-.24), (200,200,.12), floor, 0)
    tube('Display plinth', (0,0,.12), 1.27, .45, dark)
    tube('Plinth top plate', (0,0,.355), 1.23, .09, trim)
    torus('Plinth accent stripe', (0,0,.218), 1.256,.018,hot)
    area('Key / wide white', (-4,-5,7),(0.86,0.93,1),780,4.7)
    area('Fill / indigo', (4,-2,4),(.36,.52,1),360,3.1)
    area('Rim / warm', (1,4,6),(1,.72,.47),1000,3.4)
    area('Backdrop pool', (-3,4,4),(.49,.63,1),430,4.0,(0,0,.10))
    hero(scene, spec, hot, ink)
    generate = conveyor if spec['template'] == 'gravity-conveyor' else bloom
    generate(scene, colors, scene.frame_end, spec['seed'])
    scene.timeline_markers.new('Seam reference (exclude from export)', frame=scene.frame_end+1)
    scene.frame_set(1)
    out = job/'scene.blend'
    if out.exists():
        raise RuntimeError('Refusing to overwrite source scene')
    bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True)
    print('BLEND_READY', out, flush=True)


def proof(scene, stage, pose):
    scene.frame_set(pose)
    scene.render.resolution_x, scene.render.resolution_y = 540, 720
    scene.render.use_file_extension = True
    target = (0,0,2.56)
    views = [('angle-01-front', (0,-12,3.8), target, 6.65, .05),
             ('angle-02-side', (12,-3,5.7), target, 6.75, .05),
             ('angle-03-reverse', (-5,12,6.6), target, 6.85, .05),
             ('section-01-center-x', (10,0,2.56), target, 6.10, 10),
             ('section-02-center-y', (0,-10,2.56), target, 6.10, 10)]
    original = scene.camera
    for obj in original.children:
        obj.hide_render = True
    for name, loc, look, scale, clip in views:
        if name == 'section-01-center-x':
            # Inspection-only backface contrast; no cut caps or geometry in the saved scene.
            area('Proof-only fill', (0, -4, 5), (.91,.94,1), 520, 4.3)
            for mat in bpy.data.materials:
                if not mat.use_nodes or mat.name == 'Studio floor':
                    continue
                tree = mat.node_tree
                output = tree.nodes.get('Material Output')
                surface = output.inputs['Surface']
                original_socket = surface.links[0].from_socket
                g = tree.nodes.new('ShaderNodeNewGeometry')
                clay = tree.nodes.new('ShaderNodeEmission')
                clay.inputs['Color'].default_value = (.23,.31,.36,1)
                clay.inputs['Strength'].default_value = .85
                mix = tree.nodes.new('ShaderNodeMixShader')
                tree.links.new(g.outputs['Backfacing'], mix.inputs[0])
                tree.links.new(original_socket, mix.inputs[1])
                tree.links.new(clay.outputs[0], mix.inputs[2])
                tree.links.new(mix.outputs[0], surface)
        scene.camera = camera(name, loc, look, scale, clip)
        scene.render.filepath = str(stage/'proofs'/f'{name}.png')
        bpy.ops.render.render(write_still=True)
        print('PROOF_READY', name, flush=True)


def scene_render(stage, kind):
    scene = bpy.context.scene
    stage = Path(stage)
    spec = json.loads((stage.parent/'job.json').read_text())['brief']
    scene.render.resolution_x, scene.render.resolution_y = stage_size(spec['orientation'], kind)
    scene.render.use_overwrite = True  # worker insists on an empty directory; no implicit resume
    scene.render.use_placeholder = False
    scene.render.filepath = str(stage/'frames'/'frame-####')
    bpy.ops.render.render(animation=True)
    proof(scene, stage, 1 + (scene.frame_end-1)//3)


if __name__ == '__main__':
    mode, path, *args = sys.argv[sys.argv.index('--')+1:]
    if mode == 'build':
        scene_build(Path(path))
    elif mode == 'render':
        scene_render(Path(path), args[0])
    else:
        raise ValueError('unknown Blender mode')
