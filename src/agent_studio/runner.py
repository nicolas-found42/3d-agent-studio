"""Trusted Blender entry point: runs a checked scene script, saves the scene, renders stages.

Invoked only by the worker:
  blender -b --factory-startup --disable-autoexec --python runner.py -- probe JOB
  blender -b JOB/scene.blend --disable-autoexec --python runner.py -- render JOB STAGE SAMPLES
"""
from itertools import product
import json
import math
from pathlib import Path
import random
import sys
from statistics import median
from tempfile import TemporaryDirectory
import time
import traceback

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_studio.formats import stage_size  # noqa: E402
from agent_studio.kit import Kit  # noqa: E402

PROBE_LOW_SAMPLES = 4


def log(*parts):
    print('RUNNER', *parts, flush=True)


def job_info(job):
    return json.loads((job / 'job.json').read_text())


def gpu(scene):
    """Use the Metal (or other) GPU when Cycles can see one; otherwise CPU."""
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        for kind in ('METAL', 'OPTIX', 'CUDA', 'HIP', 'ONEAPI'):
            try:
                prefs.compute_device_type = kind
            except TypeError:
                continue
            prefs.get_devices()
            devices = [d for d in prefs.devices if d.type == kind]
            if devices:
                for d in prefs.devices:
                    d.use = d.type == kind
                scene.cycles.device = 'GPU'
                return kind
    except (KeyError, AttributeError):
        pass
    scene.cycles.device = 'CPU'
    return 'CPU'


def defaults(scene, brief):
    """Render defaults applied before the script runs; scripts may change any of them."""
    scene.render.engine = 'CYCLES'
    scene.cycles.use_denoising = True
    scene.cycles.seed = brief['seed']
    scene.cycles.max_bounces = 8
    scene.render.use_motion_blur = True
    scene.render.motion_blur_shutter = 0.5
    scene.view_settings.view_transform = 'AgX'
    scene.render.fps = brief['fps']
    scene.render.fps_base = 1
    scene.frame_start = 1
    scene.frame_end = brief['fps'] * brief['seconds']
    world = bpy.data.worlds.new('World')
    world.use_nodes = True
    bg = world.node_tree.nodes.get('Background')
    if bg:
        bg.inputs['Color'].default_value = (0.02, 0.022, 0.026, 1)
    scene.world = world


def configure(scene, brief, stage, samples):
    w, h = stage_size(brief['orientation'], stage)
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.color_depth = '8'
    scene.render.use_file_extension = True
    scene.render.use_overwrite = True
    scene.render.use_placeholder = False
    scene.render.film_transparent = False
    scene.render.use_persistent_data = True
    scene.cycles.use_denoising = True
    set_samples(scene, samples)
    return gpu(scene)


def set_samples(scene, samples):
    scene.cycles.samples = samples
    if hasattr(scene, 'eevee'):
        scene.eevee.taa_render_samples = max(16, samples * 2)


def clean_factory_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.cameras, bpy.data.lights, bpy.data.materials):
        for item in list(coll):
            coll.remove(item)


def title_overlay(kit):
    brief = kit.brief
    if not brief['show_title']:
        return
    cam = kit.scene.camera
    mat = kit.emissive('Title overlay', '#F4F1EA', 1.6)
    distance = 3.0
    if cam.data.type == 'ORTHO':
        height = cam.data.ortho_scale
    else:
        height = 2 * distance * math.tan(cam.data.angle / 2) / max(1.0, kit.aspect) if kit.aspect >= 1 else \
            2 * distance * math.tan(cam.data.angle / 2)
    size = height * (0.07 if kit.aspect >= 1 else 0.05)
    txt = kit.text(brief['title'], size=size, location=(0, -height * 0.36, -distance), rotation=(0, 0, 0),
                   material=mat, name='Title overlay')
    txt.parent = cam
    txt.visible_shadow = False
    log('title overlay added')


def bake_caches(scene):
    needs = scene.rigidbody_world is not None or any(
        m.type == 'PARTICLE_SYSTEM' for o in scene.objects for m in o.modifiers)
    if not needs:
        return
    with bpy.context.temp_override(scene=scene):
        bpy.ops.ptcache.bake_all(bake=True)
    log('baked simulation caches')


def validate(scene):
    cam = scene.camera
    if cam is None or cam.type != 'CAMERA':
        raise RuntimeError('The script must create a camera (kit.camera) or set kit.scene.camera')
    renderable = [o for o in scene.objects if o.type in ('MESH', 'CURVE', 'FONT', 'SURFACE', 'META', 'VOLUME',
                                                         'POINTCLOUD', 'CURVES', 'GPENCIL', 'GREASEPENCIL')
                  and not o.hide_render]
    if not renderable:
        raise RuntimeError('The script built no renderable geometry')


def scene_stats(scene):
    deps = bpy.context.evaluated_depsgraph_get()
    polys = 0
    for inst in deps.object_instances:
        obj = inst.object
        if obj.type == 'MESH':
            polys += len(obj.data.polygons)
    def has_animation(data):
        ad = getattr(data, 'animation_data', None)
        return ad and (ad.action or any(not track.mute and track.strips for track in ad.nla_tracks))

    animated = [o.name for o in scene.objects if has_animation(o)]
    data_blocks = {o.data for o in scene.objects if o.data}
    data_blocks.update(bpy.data.materials)
    if scene.world:
        data_blocks.add(scene.world)
    if scene.compositing_node_group:
        data_blocks.add(scene.compositing_node_group)
    for data in data_blocks:
        if has_animation(data):
            animated.append(data.name)
        if has_animation(getattr(data, 'node_tree', None)):
            animated.append(data.name + ' (nodes)')
        if has_animation(getattr(data, 'shape_keys', None)):
            animated.append(data.name + ' (shape keys)')
    lights = [o for o in scene.objects if o.type == 'LIGHT' and not o.hide_render]
    emissive = any(n.type == 'EMISSION' or (n.type == 'BSDF_PRINCIPLED' and n.inputs['Emission Strength'].default_value > 0)
                   for m in bpy.data.materials if m.node_tree for n in m.node_tree.nodes)
    toon = any(n.type == 'SHADERTORGB' for m in bpy.data.materials if m.node_tree for n in m.node_tree.nodes)
    sky = scene.world and scene.world.node_tree and any(n.type in ('TEX_SKY', 'TEX_ENVIRONMENT') for n in scene.world.node_tree.nodes)
    return {'objects': len(scene.objects), 'evaluated_polygons': polys, 'lights': len(lights),
            'emissive_materials': emissive, 'sky_or_hdri': bool(sky), 'engine': scene.render.engine,
            'camera': scene.camera.name, 'camera_type': scene.camera.data.type, 'lens_mm': round(scene.camera.data.lens, 2),
            'animated': sorted(set(animated)), 'view_transform': scene.view_settings.view_transform,
            'look': scene.view_settings.look, 'motion_blur': scene.render.use_motion_blur, 'toon_materials': toon}


def render_still(scene, frame, path):
    scene.frame_set(frame)
    scene.render.filepath = str(path)
    start = time.perf_counter()
    bpy.ops.render.render(write_still=True)
    return time.perf_counter() - start


def pixels(path, size=48):
    """Downscaled linear RGB array (size x size x 3) of a PNG/JPG, via Blender's image API."""
    import numpy as np
    img = bpy.data.images.load(str(path))
    try:
        img.scale(size, size)
        arr = np.empty(size * size * 4, dtype=np.float32)
        img.pixels.foreach_get(arr)
        return arr.reshape(size, size, 4)[..., :3]
    finally:
        bpy.data.images.remove(img)


def frame_stats(paths):
    """Luminance, clipping and inter-frame change for sampled frames."""
    import numpy as np
    out, prev = [], None
    for path in paths:
        px = pixels(path, 64)
        lum = (0.2126 * px[..., 0] + 0.7152 * px[..., 1] + 0.0722 * px[..., 2])
        entry = {'file': Path(path).name, 'mean_luminance': round(float(lum.mean()), 4),
                 'dark_fraction': round(float((lum < 0.01).mean()), 4),
                 'clipped_fraction': round(float((px.max(axis=2) > 0.99).mean()), 4)}
        if prev is not None:
            entry['change_from_previous'] = round(float(np.abs(px - prev).mean()), 5)
        out.append(entry)
        prev = px
    return out


def pair_references(kit, candidates, stage):
    """For each image reference, the candidate render frame that looks most like it."""
    import numpy as np

    def features(path):
        px = pixels(path, 32)
        srgb = np.clip(px, 0, 1) ** (1 / 2.2)
        hist = np.concatenate([np.histogram(srgb[..., c], bins=8, range=(0, 1))[0] for c in range(3)]).astype(np.float32)
        hist /= hist.sum() or 1
        gray = srgb.mean(axis=2)
        gray = (gray - gray.mean()) / (gray.std() + 1e-6)
        return hist, gray
    cand = [(c, features(c)) for c in candidates]
    pairs = []
    for ref in kit.references:
        if ref.kind not in ('image', 'video'):
            continue
        for i, rpath in enumerate(ref.paths):
            if rpath.suffix.lower() in ('.exr', '.hdr'):
                # Put the display rendering in the stage. Keep the scene's original HDR input intact.
                folder = stage / 'reference-previews'
                folder.mkdir(exist_ok=True)
                img = bpy.data.images.load(str(rpath))
                try:
                    w, h = img.size
                    scale = min(1, 960 / max(w, h))
                    img.scale(max(1, round(w * scale)), max(1, round(h * scale)))
                    rpath = folder / f'{ref.id}-{i}.png'
                    img.save_render(str(rpath), scene=kit.scene)
                finally:
                    bpy.data.images.remove(img)
            rh, rg = features(rpath)
            best = None
            for path, (h, g) in cand:
                score = float(np.minimum(rh, h).sum()) * .6 + float((rg * g).mean() * .5 + .5) * .4
                if best is None or score > best[1]:
                    best = (path, score)
            pairs.append({'reference': ref.id, 'role': ref.role, 'name': ref.name, 'index': i,
                          'reference_path': str(rpath), 'frame_path': str(best[0]), 'similarity': round(best[1], 3)})
    return pairs


def run_script(kit, job):
    source = (job / 'scene.py').read_text(encoding='utf-8')
    namespace = {'__name__': 'studio_scene'}
    exec(compile(source, str(job / 'scene.py'), 'exec'), namespace)
    build = namespace.get('build')
    if not callable(build):
        raise RuntimeError('scene.py defines no build(kit)')
    build(kit)


def animation_throughput(scene, stage_dir, middle, samples, count):
    """Measure contiguous animation frames, where Blender can reuse per-render state."""
    start, end, path = scene.frame_start, scene.frame_end, scene.render.filepath
    set_samples(scene, samples)
    try:
        with TemporaryDirectory(prefix='.timing-', dir=stage_dir) as scratch:
            scene.frame_start = min(middle, end - count + 1)
            scene.frame_end = scene.frame_start + count - 1
            scene.render.filepath = str(Path(scratch) / 'frame-####')
            bpy.ops.render.render(animation=True)
            times = [path.stat().st_mtime_ns for path in sorted(Path(scratch).glob('frame-*.png'))]
    finally:
        scene.frame_start, scene.frame_end, scene.render.filepath = start, end, path
    if len(times) != count:
        raise RuntimeError(f'Animation timing needs {count} contiguous PNG frames')
    seconds = median((b - a) / 1e9 for a, b in zip(times, times[1:]))
    return {'per_frame_seconds': max(0.02, seconds), 'samples': samples}


def probe(job):
    info = job_info(job)
    brief = info['brief']
    stage = job / 'probe'
    scene = bpy.context.scene
    clean_factory_scene()
    defaults(scene, brief)
    random.seed(brief['seed'])
    bpy.context.preferences.edit.keyframe_new_interpolation_type = 'BEZIER'
    kit = Kit({'job': str(job), 'brief': brief, 'size': stage_size(brief['orientation'], 'master')})
    started = time.perf_counter()
    try:
        run_script(kit, job)
    except Exception:
        (stage / 'script-error.txt').write_text(traceback.format_exc(), encoding='utf-8')
        raise
    validate(scene)
    title_overlay(kit)
    bake_caches(scene)
    build_seconds = time.perf_counter() - started
    for img in bpy.data.images:
        if img.source == 'FILE' and img.filepath:
            img.pack()
    for font in bpy.data.fonts:
        if font.filepath and font.filepath != '<builtin>':
            font.pack()
    scene.frame_set(1)
    out = job / 'scene.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True)
    log('saved', out)
    device = configure(scene, brief, 'probe', 16)
    stills = stage / 'stills'
    stills.mkdir()
    # Warm-up: the first render on a GPU compiles kernels; keep that out of the timing fit.
    warm = stage / 'warmup.png'
    res = scene.render.resolution_percentage
    scene.render.resolution_percentage = 10
    set_samples(scene, 1)
    log('warm-up', round(render_still(scene, 1, warm), 2))
    warm.unlink()
    scene.render.resolution_percentage = res
    set_samples(scene, 16)
    n = scene.frame_end
    frames = sorted({1, max(1, (n + 1) // 2), n})
    times = []
    paths = []
    for i, f in enumerate(frames, 1):
        p = stills / f'still-{i:02d}-frame-{f:04d}.png'
        times.append(render_still(scene, f, p))
        paths.append(p)
        log('still', f, round(times[-1], 2))
    set_samples(scene, PROBE_LOW_SAMPLES)
    low = render_still(scene, frames[len(frames) // 2], stage / 'timing-low.png')
    (stage / 'timing-low.png').unlink()
    w, h = stage_size(brief['orientation'], 'probe')
    stats = frame_stats(paths)
    middle = frames[len(frames) // 2]
    throughput = animation_throughput(scene, stage, middle, brief['samples'].get('preview', 16), 4)
    log('preview animation seconds per frame', round(throughput['per_frame_seconds'], 3))

    # Measure at master resolution. Extrapolating the small-preview sample slope is very noisy.
    render = scene.render
    mw, mh = stage_size(brief['orientation'], 'master')
    render.resolution_x, render.resolution_y = mw, mh
    try:
        master_low = animation_throughput(scene, stage, middle, 16, 3)
        master_high = animation_throughput(scene, stage, middle, 64, 3)
    finally:
        render.resolution_x, render.resolution_y = w, h
    calibration = {'pixels': mw * mh, 'low': master_low, 'high': master_high}
    log('master animation seconds per frame', json.dumps(calibration))
    timing = {'device': device, 'engine': scene.render.engine, 'width': w, 'height': h,
              'samples_high': 16, 'samples_low': PROBE_LOW_SAMPLES, 'seconds_high': times,
              'seconds_low': low, 'build_seconds': round(build_seconds, 2), 'frames': frames,
              'preview_throughput': throughput, 'master_calibration': calibration}
    (stage / 'timing.json').write_text(json.dumps(timing, indent=2))
    checks = {'scene': scene_stats(scene), 'stills': stats}
    (stage / 'checks-raw.json').write_text(json.dumps(checks, indent=2))
    pairs = pair_references(kit, paths, stage)
    (stage / 'pairs.json').write_text(json.dumps(pairs, indent=2))
    log('probe done')


def bbox_subject(scene):
    """Bounds of the subject: renderable objects that are not ground, volumes or giant backdrops."""
    deps = bpy.context.evaluated_depsgraph_get()
    boxes = []
    for obj in scene.objects:
        if obj.hide_render or obj.type not in ('MESH', 'CURVE', 'FONT', 'SURFACE', 'META'):
            continue
        if obj.get('studio_ground') or obj.get('studio_volume') or obj.name == 'Title overlay':
            continue
        ev = obj.evaluated_get(deps)
        pts = [obj.matrix_world @ Vector(c) for c in ev.bound_box]
        lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        boxes.append((lo, hi, (hi - lo).length))
    if not boxes:
        return Vector((-1, -1, 0)), Vector((1, 1, 2))
    sizes = sorted(b[2] for b in boxes)
    median = sizes[len(sizes) // 2] or 1
    keep = [b for b in boxes if b[2] <= max(median * 25, 1e-3)] or boxes
    lo = Vector((min(b[0].x for b in keep), min(b[0].y for b in keep), min(b[0].z for b in keep)))
    hi = Vector((max(b[1].x for b in keep), max(b[1].y for b in keep), max(b[1].z for b in keep)))
    return lo, hi


def proof_camera(name, location, target, lens=35.0, ortho=None):
    data = bpy.data.cameras.new(name)
    data.lens = lens
    data.clip_start, data.clip_end = 0.05, 10000
    if ortho:
        data.type, data.ortho_scale = 'ORTHO', ortho
    cam = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = location
    cam.rotation_euler = (Vector(target) - Vector(location)).to_track_quat('-Z', 'Y').to_euler()
    return cam


def camera_path(scene, step):
    frames = list(range(scene.frame_start, scene.frame_end + 1, step))
    if frames[-1] != scene.frame_end:
        frames.append(scene.frame_end)
    pts = []
    for frame in frames:
        scene.frame_set(frame)
        pts.append(scene.camera.matrix_world.translation.copy())
    return pts


def frame_proof(scene, cam, lo, hi):
    """Fit the entire bounding box into the proof camera at the render's actual aspect ratio."""
    centre = (lo + hi) / 2
    basis = cam.rotation_euler.to_matrix()
    inverse = basis.transposed()
    corners = [inverse @ (Vector(corner) - centre) for corner in product(*zip(lo, hi))]
    if cam.data.type == 'ORTHO':
        cam.data.ortho_scale = 1.0
    viewport = cam.data.view_frame(scene=scene)
    half_x = max(abs(v.x) for v in viewport)
    half_y = max(abs(v.y) for v in viewport)
    margin = 0.86
    if cam.data.type == 'ORTHO':
        cam.data.ortho_scale = max(0.5, max(max(abs(v.x) / half_x, abs(v.y) / half_y) for v in corners) / margin)
        distance = max(1.0, max(v.z for v in corners) + 1.0)
    else:
        depth = abs(viewport[0].z)
        horizontal, vertical = half_x / depth, half_y / depth
        distance = max(1.0, max(v.z + max(2 * cam.data.clip_start,
                                         max(abs(v.x) / horizontal, abs(v.y) / vertical) / margin) for v in corners))
    cam.data.clip_end = max(cam.data.clip_end, distance - min(v.z for v in corners) + 1.0)
    cam.location = centre + basis @ Vector((0, 0, distance))
    return cam


def proofs(job, stage_dir, brief):
    """Three review views at the proof frame: wider lens from the shot camera, a top-down overview
    with the camera path drawn in, and a three-quarter view of the whole set."""
    scene = bpy.context.scene
    out = stage_dir / 'proofs'
    out.mkdir()
    shot = scene.camera
    n = brief['fps'] * brief['seconds']
    pose = 1 + (n - 1) // 3
    w, h = stage_size(brief['orientation'], 'preview')
    longest = 640
    scale = longest / max(w, h)
    scene.render.resolution_x, scene.render.resolution_y = int(w * scale) // 2 * 2, int(h * scale) // 2 * 2
    scene.cycles.samples = 12
    scene.render.use_motion_blur = False
    pts = camera_path(scene, max(1, n // 120))
    scene.frame_set(pose)
    lo, hi = bbox_subject(scene)
    centre = (lo + hi) / 2
    path_lo, path_hi = lo.copy(), hi.copy()
    for point in pts:
        path_lo = Vector(map(min, path_lo, point))
        path_hi = Vector(map(max, path_hi, point))
    path_centre = (path_lo + path_hi) / 2
    radius = max((path_hi - path_lo).length / 2, 0.5)

    # 1. Wide: same camera transform, half the focal length (or double ortho scale).
    wide = bpy.data.objects.new('Proof wide', shot.data.copy())
    scene.collection.objects.link(wide)
    wide.matrix_world = shot.matrix_world.copy()
    if wide.data.type == 'ORTHO':
        wide.data.ortho_scale *= 2
    else:
        wide.data.lens *= 0.5
    wide.data.dof.use_dof = False
    views = [('angle-01-wide', wide)]
    # 2. Three-quarter outside view of the set.
    oblique = proof_camera('Proof three-quarter', centre + Vector((1, -1, .9)), centre)
    views.append(('angle-02-three-quarter', frame_proof(scene, oblique, lo, hi)))
    # 3. Overview: top-down orthographic with the camera path.
    top = proof_camera('Proof overview', path_centre + Vector((0, 0, 1)), path_centre, ortho=1.0)
    views.append(('angle-03-overview', frame_proof(scene, top, path_lo, path_hi)))
    for name, cam in views:
        scene.camera = cam
        engine = scene.render.engine
        if name == 'angle-03-overview':
            # Project the camera track onto the review plane above occluding roofs and set pieces.
            path_width = max(radius * 0.01, 0.02)
            height = path_hi.z + 2 * path_width
            lift = max(0.0, height + path_width + 1.0 - top.location.z)
            top.location.z += lift
            top.data.clip_end += lift
            path_obj = draw_path(scene, [Vector((point.x, point.y, height)) for point in pts], radius)
            hidden = [o for o in scene.objects if (o.get('studio_volume') or o.type == 'VOLUME'
                                                   or o.name == 'Title overlay') and not o.hide_render]
            for o in hidden:
                o.hide_render = True
            scene.render.engine = 'BLENDER_WORKBENCH'
            scene.display.shading.light = 'STUDIO'
            scene.display.shading.color_type = 'MATERIAL'
            scene.display.shading.show_shadows = True
        render_still(scene, pose, out / f'{name}.png')
        if name == 'angle-03-overview':
            bpy.data.objects.remove(path_obj, do_unlink=True)
            for o in hidden:
                o.hide_render = False
        scene.render.engine = engine
        log('proof', name)
    scene.camera = shot


def draw_path(scene, pts, radius):
    cu = bpy.data.curves.new('Proof camera path', 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = max(radius * 0.01, 0.02)
    sp = cu.splines.new('POLY')
    sp.points.add(max(0, len(pts) - 1))
    for bp, p in zip(sp.points, pts):
        bp.co = (*p, 1)
    mat = bpy.data.materials.new('Proof path')
    mat.diffuse_color = (1.0, 0.15, 0.55, 1)
    cu.materials.append(mat)
    obj = bpy.data.objects.new('Proof camera path', cu)
    scene.collection.objects.link(obj)
    return obj


def render(job, stage_name, samples):
    info = job_info(job)
    brief = info['brief']
    stage = job / stage_name
    scene = bpy.context.scene
    device = configure(scene, brief, stage_name, samples)
    n = brief['fps'] * brief['seconds']
    scene.frame_start, scene.frame_end = 1, n + (1 if brief['loop'] else 0)
    scene.render.filepath = str(stage / 'frames' / 'frame-####')
    log('rendering', scene.frame_end, 'frames on', device, 'at', samples, 'spp')
    start = time.perf_counter()
    bpy.ops.render.render(animation=True)
    elapsed = time.perf_counter() - start
    frames = sorted((stage / 'frames').glob('frame-*.png'))
    sample = frames[::max(1, len(frames) // 48)]
    stats = frame_stats(sample)
    kit = Kit({'job': str(job), 'brief': brief, 'size': stage_size(brief['orientation'], stage_name)})
    pairs = pair_references(kit, frames[:n][::max(1, n // 36)], stage)
    seam = None
    if brief['loop']:
        import numpy as np
        a, b = pixels(frames[0], 64), pixels(frames[-1], 64)
        seam = round(float(np.abs(a - b).mean()), 5)
        typical = [s['change_from_previous'] for s in stats if 'change_from_previous' in s]
        seam = {'first_vs_extra_frame': seam, 'typical_sampled_change': round(sorted(typical)[len(typical) // 2], 5) if typical else None}
    (stage / 'render-stats.json').write_text(json.dumps({
        'device': device, 'samples': samples, 'seconds': round(elapsed, 1),
        'seconds_per_frame': round(elapsed / max(1, len(frames)), 3), 'frames': len(frames),
        'frame_stats': stats, 'loop_seam': seam}, indent=2))
    (stage / 'pairs.json').write_text(json.dumps(pairs, indent=2))
    proofs(job, stage, brief)
    log('render done')


if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:]
    mode, job = args[0], Path(args[1])
    if mode == 'probe':
        probe(job)
    elif mode == 'render':
        render(job, args[2], int(args[3]))
    else:
        raise SystemExit('unknown runner mode')
