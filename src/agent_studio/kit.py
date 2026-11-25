"""Scene kit handed to agent-written scripts as `build(kit)`.

Runs inside Blender. Everything here is a convenience over `bpy`: scripts may mix kit calls with
raw `bpy`, `bmesh` and `mathutils`. Units are metres, angles are degrees unless a name says
radians, colors are '#RRGGBB' strings or sRGB tuples, and time `t` runs 0..1 over the shot.

Conventions the studio relies on:
- `kit.camera(...)` (or setting `kit.scene.camera`) chooses the shot camera.
- Animate with keyframes (`kit.animate`, `kit.key`, the camera rigs); handlers and Python drivers
  do not survive into the saved scene.
- For loops (`kit.loop`), frame `kit.frames + 1` must look like frame 1. Use `kit.wave`,
  `kit.loop_noise`, whole turns, or `kit.orbit(..., sweep=360)`.
- Mark big floors with `ground=True` (or use `kit.ground`) and volumes with `kit.haze`, so the
  review overview frames the subject rather than the horizon.
"""
import colorsys
import csv
import json
import math
from pathlib import Path
import random

import bpy
import bmesh
from mathutils import Euler, Matrix, Vector, noise
from mathutils.bvhtree import BVHTree

TAU = math.tau
EASES = ('linear', 'in', 'out', 'in_out', 'smooth', 'smoother', 'sine', 'expo_out', 'expo_in_out', 'back_out',
         'bounce_out')


def srgb_to_linear(c):
    return c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4


def rgba(value, alpha=1.0):
    """'#RRGGBB', '#RRGGBBAA', an sRGB (r, g, b[, a]) tuple in 0..1, or a gray float -> linear RGBA."""
    if isinstance(value, str):
        h = value.lstrip('#')
        if len(h) not in (6, 8):
            raise ValueError(f'Bad color {value!r}')
        parts = [int(h[i:i + 2], 16) / 255 for i in range(0, len(h), 2)]
        rgb, alpha = parts[:3], (parts[3] if len(parts) == 4 else alpha)
    elif isinstance(value, (int, float)):
        rgb = [float(value)] * 3
    else:
        rgb = list(value[:3])
        alpha = value[3] if len(value) > 3 else alpha
    return (*[srgb_to_linear(c) for c in rgb], alpha)


def hsv(h, s, v):
    """Hue 0..1, saturation, value -> '#RRGGBB'."""
    r, g, b = colorsys.hsv_to_rgb(h % 1, s, v)
    return '#{:02X}{:02X}{:02X}'.format(*(round(255 * c) for c in (r, g, b)))


def ease(t, kind='in_out', power=3.0):
    """Easing of 0..1 progress. kind: linear, in, out, in_out (power sets steepness), smooth,
    smoother, sine, expo_out, expo_in_out, back_out (overshoot), bounce_out."""
    t = min(1.0, max(0.0, t))
    if kind == 'linear':
        return t
    if kind == 'in':
        return t ** power
    if kind == 'out':
        return 1 - (1 - t) ** power
    if kind == 'in_out':
        return 0.5 * (2 * t) ** power if t < .5 else 1 - 0.5 * (2 - 2 * t) ** power
    if kind == 'smooth':
        return t * t * (3 - 2 * t)
    if kind == 'smoother':
        return t * t * t * (t * (6 * t - 15) + 10)
    if kind == 'sine':
        return 0.5 - 0.5 * math.cos(math.pi * t)
    if kind == 'expo_out':
        return 1 if t == 1 else 1 - 2 ** (-10 * t)
    if kind == 'expo_in_out':
        if t in (0, 1):
            return t
        return 0.5 * 2 ** (20 * t - 10) if t < .5 else 1 - 0.5 * 2 ** (-20 * t + 10)
    if kind == 'back_out':
        c = 1.70158
        return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2
    if kind == 'bounce_out':
        n, d = 7.5625, 2.75
        if t < 1 / d:
            return n * t * t
        if t < 2 / d:
            t -= 1.5 / d
            return n * t * t + .75
        if t < 2.5 / d:
            t -= 2.25 / d
            return n * t * t + .9375
        t -= 2.625 / d
        return n * t * t + .984375
    raise ValueError(f'Unknown ease {kind!r}; choose from {EASES}')


def lerp(a, b, t):
    """Linear blend of numbers or vectors."""
    if isinstance(a, (int, float)):
        return a + (b - a) * t
    return Vector(a).lerp(Vector(b), t)


def segment(t, start, end):
    """Local 0..1 progress of `t` within [start, end], clamped."""
    return min(1.0, max(0.0, (t - start) / (end - start))) if end > start else float(t >= end)


def catmull_rom(points, t, closed=False):
    """Point on a centripetal-ish uniform Catmull-Rom spline through `points` at 0..1."""
    pts = [Vector(p) for p in points]
    n = len(pts)
    if n == 1:
        return pts[0].copy()
    segs = n if closed else n - 1
    x = (t % 1 if closed else min(max(t, 0), 1)) * segs
    i = min(int(x), segs - 1)
    u = x - i

    def at(k):
        return pts[k % n] if closed else pts[min(max(k, 0), n - 1)]
    p0, p1, p2, p3 = at(i - 1), at(i), at(i + 1), at(i + 2)
    return 0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u + (-p0 + 3 * p1 - 3 * p2 + p3) * u ** 3)


class ArcSpline:
    """Catmull-Rom spline re-parameterized by arc length, so eased t gives even speed."""

    def __init__(self, points, closed=False, samples=400):
        self.points, self.closed = points, closed
        self.ts = [i / samples for i in range(samples + 1)]
        pos = [catmull_rom(points, t, closed) for t in self.ts]
        self.lengths = [0.0]
        for a, b in zip(pos, pos[1:]):
            self.lengths.append(self.lengths[-1] + (b - a).length)
        self.total = self.lengths[-1] or 1.0

    def __call__(self, s):
        s = (s % 1 if self.closed else min(max(s, 0), 1)) * self.total
        lo, hi = 0, len(self.lengths) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if self.lengths[mid] < s:
                lo = mid
            else:
                hi = mid
        span = self.lengths[hi] - self.lengths[lo] or 1
        t = self.ts[lo] + (self.ts[hi] - self.ts[lo]) * (s - self.lengths[lo]) / span
        return catmull_rom(self.points, t, self.closed)


class Reference:
    """An ingested reference: images, video frames, a model, data, SVG, font or text."""

    def __init__(self, root, info):
        self.id, self.kind, self.role = info['id'], info['kind'], info['role']
        self.name, self.note = info['name'], info.get('note', '')
        self.dir = root / info['id']
        self.info = info
        if self.kind == 'video':
            self.paths = [self.dir / f['file'] for f in info['frames']]
            self.times = [f['time_seconds'] for f in info['frames']]
            self.video = info['video']
        else:
            self.paths = [self.dir / info['file']] if info.get('file') else []

    @property
    def path(self):
        return self.paths[0] if self.paths else None

    def __repr__(self):
        return f'<Reference {self.id} {self.kind}/{self.role} {self.name!r}>'


class Kit:
    def __init__(self, ctx):
        self.ctx = ctx
        self.job = Path(ctx['job'])
        self.brief = ctx['brief']
        self.prompt = self.brief['prompt']
        self.seed = self.brief['seed']
        self.rng = random.Random(self.seed)
        self.fps = self.brief['fps']
        self.seconds = self.brief['seconds']
        self.frames = self.fps * self.seconds
        self.loop = self.brief['loop']
        self.orientation = self.brief['orientation']
        self.width, self.height = ctx['size']
        self.aspect = self.width / self.height
        self.scene = bpy.context.scene
        self._mats = {}
        inputs = self.job / 'inputs'
        manifest = json.loads((inputs / 'manifest.json').read_text()) if (inputs / 'manifest.json').is_file() else []
        self.references = [Reference(inputs, info) for info in manifest]
        assets = self.job / 'assets' / 'assets.json'
        self.assets = json.loads(assets.read_text()) if assets.is_file() else {}

    # ------------------------------------------------------------------ time
    def t(self, frame):
        """Shot progress of a frame: 0 at frame 1, 1 at the last frame (or frames+1 for loops)."""
        span = self.frames if self.loop else max(1, self.frames - 1)
        return (frame - 1) / span

    def frame(self, t):
        span = self.frames if self.loop else max(1, self.frames - 1)
        return 1 + t * span

    def key_frames(self, step=1):
        end = self.frames + 1 if self.loop else self.frames
        frames = list(range(1, end + 1, max(1, step)))
        if frames[-1] != end:
            frames.append(end)
        return frames

    ease = staticmethod(ease)
    lerp = staticmethod(lerp)
    segment = staticmethod(segment)
    color = staticmethod(rgba)
    hsv = staticmethod(hsv)

    def wave(self, t, cycles=1, phase=0.0):
        """sin over whole cycles: loop-safe when cycles is an integer."""
        return math.sin(TAU * (cycles * t + phase))

    def loop_noise(self, t, seed=0, cycles=1, octaves=2, scale=1.0):
        """Smooth noise in -1..1 that repeats exactly every 1/cycles of t (sampled on a circle)."""
        a = TAU * cycles * t
        p = Vector((math.cos(a) * scale, math.sin(a) * scale, seed * 17.31 + .5))
        return noise.fractal(p, 1.0, 2.0, octaves, noise_basis='PERLIN_NEW') * 1.2

    def noise(self, x, y=0.0, z=0.0, octaves=3, basis='PERLIN_NEW'):
        return noise.fractal(Vector((x, y, z)), 1.0, 2.0, octaves, noise_basis=basis)

    # ------------------------------------------------------------- animation
    def animate(self, target, path, fn, step=1, index=-1, interpolation='LINEAR'):
        """Key `target.path` from fn(t) at every `step` frames (t is shot progress 0..1).

        `target` is any animatable struct (object, light data, material node input, ...).
        """
        prefs = bpy.context.preferences.edit
        old = prefs.keyframe_new_interpolation_type
        prefs.keyframe_new_interpolation_type = interpolation
        try:
            for f in self.key_frames(step):
                value = fn(self.t(f))
                if isinstance(value, Vector):
                    value = tuple(value)
                setattr(target, path, value) if index < 0 else getattr(target, path).__setitem__(index, value)
                target.keyframe_insert(path, index=index, frame=f)
        finally:
            prefs.keyframe_new_interpolation_type = old
        return target

    def key(self, target, path, keys, interpolation='BEZIER', index=-1):
        """Explicit keys: [(t or frame, value), ...]. Floats <= 1 are shot progress; ints are frames."""
        prefs = bpy.context.preferences.edit
        old = prefs.keyframe_new_interpolation_type
        prefs.keyframe_new_interpolation_type = interpolation
        try:
            for when, value in keys:
                f = when if isinstance(when, int) else self.frame(when)
                setattr(target, path, tuple(value) if isinstance(value, Vector) else value) if index < 0 \
                    else getattr(target, path).__setitem__(index, value)
                target.keyframe_insert(path, index=index, frame=f)
        finally:
            prefs.keyframe_new_interpolation_type = old
        return target

    def spin(self, obj, axis='Z', turns=1.0, ease_kind='linear', offset_deg=0.0):
        """Rotate about a local axis by `turns` over the shot (whole turns are loop-safe)."""
        i = 'XYZ'.index(axis.upper())
        base = Euler(obj.rotation_euler)

        def at(t):
            r = list(base)
            r[i] += math.radians(offset_deg) + TAU * turns * ease(t, ease_kind)
            return r
        return self.animate(obj, 'rotation_euler', at)

    def bob(self, obj, amplitude=0.1, cycles=1, axis='Z', phase=0.0):
        i = 'XYZ'.index(axis.upper())
        base = Vector(obj.location)

        def at(t):
            v = base.copy()
            v[i] += amplitude * self.wave(t, cycles, phase)
            return v
        return self.animate(obj, 'location', at)

    def pulse(self, material, low=0.0, high=5.0, cycles=1, phase=0.0):
        """Animate a material's emission strength between low and high."""
        nodes = material.node_tree.nodes
        emission = next((n for n in nodes if n.type == 'EMISSION'), None)
        socket = emission.inputs['Strength'] if emission else self.bsdf(material).inputs['Emission Strength']
        return self.animate(socket, 'default_value', lambda t: low + (high - low) * (0.5 + 0.5 * self.wave(t, cycles, phase)))

    def grow(self, obj, start=0.0, end=0.3, ease_kind='back_out', from_scale=0.0):
        """Scale an object up from `from_scale` during the [start, end] part of the shot."""
        final = Vector(obj.scale)
        return self.animate(obj, 'scale', lambda t: final * lerp(from_scale, 1.0, ease(segment(t, start, end), ease_kind)))

    def move(self, obj, points, start=0.0, end=1.0, ease_kind='in_out', closed=False):
        """Move an object along a smooth path through `points` during [start, end]."""
        spline = ArcSpline(points, closed)
        return self.animate(obj, 'location', lambda t: spline(ease(segment(t, start, end), ease_kind)))

    def visible(self, obj, start=0.0, end=1.0):
        """Show an object only while shot progress is within [start, end] (hard cuts)."""
        keys = [(1, start > 0)]
        if start > 0:
            keys.append((max(1, round(self.frame(start))), False))
        if end < 1:
            keys.append((round(self.frame(end)) + 1, True))
        for prop in ('hide_render', 'hide_viewport'):
            self.key(obj, prop, keys, interpolation='CONSTANT')
        return obj

    # ---------------------------------------------------------- collections
    def collection(self, name):
        coll = bpy.data.collections.get(name)
        if not coll:
            coll = bpy.data.collections.new(name)
            self.scene.collection.children.link(coll)
        return coll

    def _link(self, obj, collection=None):
        (self.collection(collection) if isinstance(collection, str) else collection or self.scene.collection).objects.link(obj)
        return obj

    def empty(self, name='Empty', location=(0, 0, 0), display='PLAIN_AXES', size=0.5, collection=None):
        obj = bpy.data.objects.new(name, None)
        obj.empty_display_type, obj.empty_display_size = display, size
        obj.location = location
        return self._link(obj, collection)

    def parent(self, child, parent, keep_transform=True):
        matrix = child.matrix_world.copy()
        child.parent = parent
        if keep_transform:
            child.matrix_world = matrix
        return child

    def look_at(self, obj, target, up='Y'):
        direction = Vector(target) - Vector(obj.location)
        obj.rotation_euler = direction.to_track_quat('-Z', up).to_euler()
        return obj

    # ----------------------------------------------------------- materials
    def material(self, name, color='#BBBBBB', roughness=0.5, metallic=0.0, emission=None, emission_strength=0.0,
                 transmission=0.0, ior=1.45, alpha=1.0, subsurface=0.0, subsurface_radius=(1, .2, .1), coat=0.0,
                 sheen=0.0, specular=0.5, bump=None, thin_wall=False):
        """Principled BSDF material. bump=(scale, strength) adds procedural surface noise."""
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        bs = self.bsdf(mat)
        c = rgba(color)
        bs.inputs['Base Color'].default_value = c
        bs.inputs['Roughness'].default_value = roughness
        bs.inputs['Metallic'].default_value = metallic
        bs.inputs['IOR'].default_value = ior
        bs.inputs['Alpha'].default_value = alpha
        bs.inputs['Transmission Weight'].default_value = transmission
        bs.inputs['Subsurface Weight'].default_value = subsurface
        bs.inputs['Subsurface Radius'].default_value = subsurface_radius
        bs.inputs['Coat Weight'].default_value = coat
        bs.inputs['Sheen Weight'].default_value = sheen
        bs.inputs['Specular IOR Level'].default_value = specular
        if 'Thin Wall' in bs.inputs:
            bs.inputs['Thin Wall'].default_value = thin_wall
        if emission is not None or emission_strength:
            bs.inputs['Emission Color'].default_value = rgba(emission if emission is not None else color)
            bs.inputs['Emission Strength'].default_value = emission_strength
        mat.diffuse_color = c
        if alpha < 1:
            mat.surface_render_method = 'BLENDED' if hasattr(mat, 'surface_render_method') else mat.blend_method
        if bump:
            self._noise_bump(mat, *bump)
        return mat

    def bsdf(self, mat):
        node = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if node is None:
            raise ValueError(f'Material {mat.name} has no Principled BSDF (kit.emissive, kit.flat and kit.toon '
                             'materials have none); use kit.material for this helper')
        return node

    def _noise_bump(self, mat, scale, strength, detail=6.0):
        nt = mat.node_tree
        tex = nt.nodes.new('ShaderNodeTexNoise')
        tex.inputs['Scale'].default_value = scale
        tex.inputs['Detail'].default_value = detail
        bump = nt.nodes.new('ShaderNodeBump')
        bump.inputs['Strength'].default_value = strength
        nt.links.new(tex.outputs['Fac'], bump.inputs['Height'])
        nt.links.new(bump.outputs['Normal'], self.bsdf(mat).inputs['Normal'])
        return bump

    def glass(self, name='Glass', color='#FFFFFF', roughness=0.0, ior=1.45):
        return self.material(name, color, roughness=roughness, transmission=1.0, ior=ior, specular=0.5)

    def emissive(self, name='Emission', color='#FFFFFF', strength=5.0):
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        em = nt.nodes.new('ShaderNodeEmission')
        em.inputs['Color'].default_value = rgba(color)
        em.inputs['Strength'].default_value = strength
        nt.links.new(em.outputs[0], out.inputs['Surface'])
        mat.diffuse_color = rgba(color)
        return mat

    def flat(self, name='Flat', color='#FFFFFF'):
        """Unlit flat color (holdout of lighting): graphic, poster and data-viz looks."""
        return self.emissive(name, color, 1.0)

    def gradient_material(self, name, colors, axis='Z', low=0.0, high=1.0, roughness=0.5, emission_strength=0.0):
        """Color ramp along an object-space axis between `low` and `high`."""
        mat = self.material(name, colors[0], roughness=roughness)
        nt = mat.node_tree
        coord = nt.nodes.new('ShaderNodeTexCoord')
        sep = nt.nodes.new('ShaderNodeSeparateXYZ')
        nt.links.new(coord.outputs['Object'], sep.inputs[0])
        rng = nt.nodes.new('ShaderNodeMapRange')
        rng.inputs['From Min'].default_value, rng.inputs['From Max'].default_value = low, high
        nt.links.new(sep.outputs['XYZ'.index(axis)], rng.inputs['Value'])
        ramp = self._ramp(nt, colors)
        nt.links.new(rng.outputs['Result'], ramp.inputs['Fac'])
        bs = self.bsdf(mat)
        nt.links.new(ramp.outputs['Color'], bs.inputs['Base Color'])
        if emission_strength:
            nt.links.new(ramp.outputs['Color'], bs.inputs['Emission Color'])
            bs.inputs['Emission Strength'].default_value = emission_strength
        return mat

    def _ramp(self, nt, colors, interpolation='LINEAR'):
        ramp = nt.nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.interpolation = interpolation
        els = ramp.color_ramp.elements
        stops = [(i / max(1, len(colors) - 1), c) for i, c in enumerate(colors)] if not isinstance(colors[0], tuple) \
            or len(colors[0]) != 2 else colors
        while len(els) < len(stops):
            els.new(0.5)
        for el, (pos, col) in zip(els, stops):
            el.position, el.color = pos, rgba(col)
        return ramp

    def procedural(self, name, kind='stone', colors=None, scale=1.0, roughness=None, bump=0.3):
        """Procedural surfaces: stone, marble, wood, concrete, brushed_metal, rust, fabric, ground,
        sand, plastic, ceramic, terrazzo, bark, leaf, snow, lava, water."""
        presets = {
            'stone': (['#6E6A62', '#A39C8E', '#C8C0AE'], .85, 'voronoi_noise', 4.0),
            'marble': (['#E8E4DC', '#C9C2B8', '#8D867C'], .25, 'wave', 2.0),
            'wood': (['#5A3920', '#8A5A33', '#B07A48'], .55, 'wood', 3.0),
            'concrete': (['#7C7C78', '#9A9993', '#B4B2AA'], .9, 'noise', 6.0),
            'brushed_metal': (['#8E9196', '#B7BAC0', '#D9DBDF'], .3, 'brushed', 40.0),
            'rust': (['#4A2A18', '#8C4A22', '#B8703A'], .9, 'voronoi_noise', 6.0),
            'fabric': (['#5B6170', '#6D7484', '#808899'], .95, 'weave', 120.0),
            'ground': (['#3E3428', '#5C4E3A', '#776650'], .95, 'noise', 3.0),
            'sand': (['#C2A878', '#D6BE8E', '#E6D3A8'], .9, 'noise', 30.0),
            'plastic': (['#D0D2D6', '#D8DADE', '#E0E2E6'], .35, 'noise', 2.0),
            'ceramic': (['#EEE9E0', '#F4F0E8', '#FAF7F1'], .15, 'noise', 3.0),
            'terrazzo': (['#D9D2C5', '#A64B2A', '#3E5F6B', '#E8C547'], .4, 'terrazzo', 12.0),
            'bark': (['#3B2A1E', '#5A4330', '#6E5640'], .95, 'bark', 6.0),
            'leaf': (['#2E5A1C', '#4C7A2A', '#6E9A3A'], .6, 'noise', 8.0),
            'snow': (['#E9EEF5', '#F4F7FB', '#FFFFFF'], .6, 'noise', 10.0),
            'lava': (['#1A0E0A', '#FF4A00', '#FFB000'], .8, 'voronoi_noise', 3.0),
            'water': (['#0B3A4A', '#14596E', '#2A7F95'], .05, 'noise', 4.0),
        }
        if kind not in presets:
            raise ValueError(f'Unknown procedural kind {kind!r}; choose from {sorted(presets)}')
        base_colors, rough, pattern, base_scale = presets[kind]
        colors = colors or base_colors
        mat = self.material(name, colors[0], roughness=roughness if roughness is not None else rough,
                            metallic=1.0 if kind == 'brushed_metal' else 0.0)
        nt = mat.node_tree
        bs = self.bsdf(mat)
        coord = nt.nodes.new('ShaderNodeTexCoord')
        mapping = nt.nodes.new('ShaderNodeMapping')
        mapping.inputs['Scale'].default_value = (scale * base_scale,) * 3
        nt.links.new(coord.outputs['Object'], mapping.inputs['Vector'])
        vec = mapping.outputs['Vector']
        if pattern == 'wave':
            tex = nt.nodes.new('ShaderNodeTexWave')
            tex.inputs['Distortion'].default_value = 12
            tex.inputs['Detail'].default_value = 8
            fac = tex.outputs['Fac']
        elif pattern == 'wood':
            tex = nt.nodes.new('ShaderNodeTexWave')
            tex.wave_type = 'RINGS'
            tex.inputs['Distortion'].default_value = 4
            tex.inputs['Detail Scale'].default_value = 2
            fac = tex.outputs['Fac']
        elif pattern == 'brushed':
            mapping.inputs['Scale'].default_value = (scale * base_scale, scale * .5, scale * .5)
            tex = nt.nodes.new('ShaderNodeTexNoise')
            tex.inputs['Detail'].default_value = 2
            fac = tex.outputs['Fac']
        elif pattern in ('voronoi_noise', 'terrazzo'):
            tex = nt.nodes.new('ShaderNodeTexVoronoi')
            if pattern == 'terrazzo':
                tex.feature = 'F1'
                fac = tex.outputs['Color']
            else:
                fac = tex.outputs['Distance']
        elif pattern == 'weave':
            tex = nt.nodes.new('ShaderNodeTexChecker')
            fac = tex.outputs['Fac']
        elif pattern == 'bark':
            mapping.inputs['Scale'].default_value = (scale * base_scale, scale * base_scale, scale * .6)
            tex = nt.nodes.new('ShaderNodeTexVoronoi')
            tex.distance = 'CHEBYCHEV'
            fac = tex.outputs['Distance']
        else:
            tex = nt.nodes.new('ShaderNodeTexNoise')
            tex.inputs['Detail'].default_value = 10
            tex.inputs['Roughness'].default_value = .6
            fac = tex.outputs['Fac']
        nt.links.new(vec, tex.inputs['Vector'])
        if pattern == 'terrazzo':
            sep = nt.nodes.new('ShaderNodeSeparateColor')
            nt.links.new(fac, sep.inputs[0])
            ramp = self._ramp(nt, colors, 'CONSTANT')
            nt.links.new(sep.outputs[0], ramp.inputs['Fac'])
        else:
            ramp = self._ramp(nt, colors)
            nt.links.new(fac, ramp.inputs['Fac'])
        nt.links.new(ramp.outputs['Color'], bs.inputs['Base Color'])
        if kind == 'lava':
            nt.links.new(ramp.outputs['Color'], bs.inputs['Emission Color'])
            bs.inputs['Emission Strength'].default_value = 3.0
        if kind == 'water':
            bs.inputs['Transmission Weight'].default_value = .6
            bs.inputs['IOR'].default_value = 1.33
        if bump:
            b = nt.nodes.new('ShaderNodeBump')
            b.inputs['Strength'].default_value = bump
            nt.links.new(fac if pattern != 'terrazzo' else ramp.outputs['Color'], b.inputs['Height'])
            nt.links.new(b.outputs['Normal'], bs.inputs['Normal'])
        return mat

    def image(self, source, index=0, non_color=False):
        """Load an image from a reference ID (index picks a video frame) or an asset ID."""
        path = self.file(source, index=index, kinds=('image', 'video', 'hdri', 'texture'))
        img = bpy.data.images.load(str(path), check_existing=True)
        if non_color:
            img.colorspace_settings.name = 'Non-Color'
        return img

    def file(self, source, index=0, filename=None, kinds=None):
        """Filesystem path for a reference ID or declared asset ID (optionally a file inside it)."""
        ref = next((r for r in self.references if r.id == source), None)
        if ref:
            if kinds and ref.kind not in kinds:
                raise ValueError(f'{source} is a {ref.kind}, not one of {kinds}')
            return ref.paths[index]
        if source in self.assets:
            info = self.assets[source]
            folder = self.job / 'assets' / info['folder']
            files = sorted(info['files'])
            if filename:
                match = [f for f in files if f == filename or f.endswith('/' + filename)]
                if not match:
                    raise ValueError(f'{source} has no file {filename}; files: {files}')
                return folder / match[0]
            return folder / files[index]
        raise ValueError(f'{source!r} is neither an ingested reference of this job nor a declared asset. '
                         'Add reference IDs to brief.references and asset IDs to brief.assets.')

    def textured(self, name, source, scale=1.0, projection='BOX', bump=1.0, displacement=0.0, roughness=None,
                 tint=None, metallic=None):
        """PBR material from a texture asset (color/normal_gl/roughness/... maps), box-projected
        in object space so it needs no UVs. `scale` is texture repeats per metre."""
        info = self.assets.get(source)
        if not info:
            raise ValueError(f'{source} is not a declared asset of this job')
        folder = self.job / 'assets' / info['folder']
        maps = {Path(f).stem: folder / f for f in info['files']}
        mat = self.material(name, '#FFFFFF', roughness=.6)
        nt = mat.node_tree
        bs = self.bsdf(mat)
        coord = nt.nodes.new('ShaderNodeTexCoord')
        mapping = nt.nodes.new('ShaderNodeMapping')
        mapping.inputs['Scale'].default_value = (scale,) * 3
        nt.links.new(coord.outputs['Object' if projection == 'BOX' else 'UV'], mapping.inputs['Vector'])

        def tex(key, data):
            if key not in maps:
                return None
            node = nt.nodes.new('ShaderNodeTexImage')
            node.image = bpy.data.images.load(str(maps[key]), check_existing=True)
            if data:
                node.image.colorspace_settings.name = 'Non-Color'
            if projection == 'BOX':
                node.projection, node.projection_blend = 'BOX', .25
            nt.links.new(mapping.outputs['Vector'], node.inputs['Vector'])
            return node
        color = tex('color', False)
        if color:
            if tint:
                mix = nt.nodes.new('ShaderNodeMix')
                mix.data_type, mix.blend_type = 'RGBA', 'MULTIPLY'
                mix.inputs['Factor'].default_value = 1.0
                nt.links.new(color.outputs['Color'], mix.inputs['A'])
                mix.inputs['B'].default_value = rgba(tint)
                nt.links.new(mix.outputs['Result'], bs.inputs['Base Color'])
            else:
                nt.links.new(color.outputs['Color'], bs.inputs['Base Color'])
        rough = tex('roughness', True)
        if rough and roughness is None:
            nt.links.new(rough.outputs['Color'], bs.inputs['Roughness'])
        elif roughness is not None:
            bs.inputs['Roughness'].default_value = roughness
        metal = tex('metalness', True)
        if metal and metallic is None:
            nt.links.new(metal.outputs['Color'], bs.inputs['Metallic'])
        elif metallic is not None:
            bs.inputs['Metallic'].default_value = metallic
        normal = tex('normal_gl', True)
        if normal:
            nm = nt.nodes.new('ShaderNodeNormalMap')
            nm.inputs['Strength'].default_value = bump
            nt.links.new(normal.outputs['Color'], nm.inputs['Color'])
            nt.links.new(nm.outputs['Normal'], bs.inputs['Normal'])
        disp = tex('displacement', True)
        if disp and displacement:
            d = nt.nodes.new('ShaderNodeDisplacement')
            d.inputs['Scale'].default_value = displacement
            nt.links.new(disp.outputs['Color'], d.inputs['Height'])
            out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
            nt.links.new(d.outputs['Displacement'], out.inputs['Displacement'])
            if hasattr(mat, 'displacement_method'):
                mat.displacement_method = 'BOTH'
        return mat

    def image_material(self, name, source, index=0, emission=0.0, roughness=0.5, alpha=True):
        """Material showing a reference/asset image via the object's UVs (e.g. on kit.image_plane)."""
        mat = self.material(name, '#FFFFFF', roughness=roughness)
        nt = mat.node_tree
        bs = self.bsdf(mat)
        node = nt.nodes.new('ShaderNodeTexImage')
        node.image = self.image(source, index)
        nt.links.new(node.outputs['Color'], bs.inputs['Base Color'])
        if alpha:
            nt.links.new(node.outputs['Alpha'], bs.inputs['Alpha'])
        if emission:
            nt.links.new(node.outputs['Color'], bs.inputs['Emission Color'])
            bs.inputs['Emission Strength'].default_value = emission
        return mat

    def toon(self, name, color='#E0E0E0', shades=3, shadow='#303040'):
        """Cel-shaded material (EEVEE only: call kit.render(engine='EEVEE')). In Cycles it falls back
        to its diffuse base."""
        mat = self.material(name, color, roughness=1.0)
        nt = mat.node_tree
        out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
        diffuse = nt.nodes.new('ShaderNodeBsdfDiffuse')
        diffuse.inputs['Color'].default_value = (1, 1, 1, 1)
        to_rgb = nt.nodes.new('ShaderNodeShaderToRGB')
        nt.links.new(diffuse.outputs[0], to_rgb.inputs[0])
        a, b = Vector(rgba(shadow)[:3]), Vector(rgba(color)[:3])
        ramp = nt.nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.interpolation = 'CONSTANT'
        els = ramp.color_ramp.elements
        while len(els) < shades:
            els.new(0.5)
        for i, el in enumerate(els):
            el.position = i / shades
            el.color = (*a.lerp(b, i / max(1, shades - 1)), 1)
        nt.links.new(to_rgb.outputs['Color'], ramp.inputs['Fac'])
        em = nt.nodes.new('ShaderNodeEmission')
        nt.links.new(ramp.outputs['Color'], em.inputs['Color'])
        nt.links.new(em.outputs[0], out.inputs['Surface'])
        return mat

    def assign(self, obj, mat, slot=None):
        data = obj.data
        if slot is None:
            data.materials.clear()
            data.materials.append(mat)
        else:
            while len(data.materials) <= slot:
                data.materials.append(None)
            data.materials[slot] = mat
        return obj

    # ------------------------------------------------------------- geometry
    def mesh(self, name, verts, faces, material=None, location=(0, 0, 0), rotation=(0, 0, 0), smooth=False,
             collection=None, ground=False, edges=()):
        me = bpy.data.meshes.new(name)
        me.from_pydata([tuple(v) for v in verts], list(edges), [tuple(f) for f in faces])
        me.validate(clean_customdata=False)
        me.update()
        obj = bpy.data.objects.new(name, me)
        obj.location = location
        obj.rotation_euler = [math.radians(a) for a in rotation]
        if material:
            me.materials.append(material)
        if smooth:
            me.shade_smooth() if hasattr(me, 'shade_smooth') else [setattr(p, 'use_smooth', True) for p in me.polygons]
        if ground:
            obj['studio_ground'] = True
        return self._link(obj, collection)

    def _bm_object(self, name, bm, material, location, rotation, smooth, collection, ground=False):
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        obj = bpy.data.objects.new(name, me)
        obj.location = location
        obj.rotation_euler = [math.radians(a) for a in rotation]
        if material:
            me.materials.append(material)
        if smooth:
            for p in me.polygons:
                p.use_smooth = True
        if ground:
            obj['studio_ground'] = True
        return self._link(obj, collection)

    def box(self, name='Box', size=(1, 1, 1), location=(0, 0, 0), material=None, rotation=(0, 0, 0), bevel=0.0,
            collection=None, ground=False):
        """Axis-aligned box centred on `location` (size is full extents)."""
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=Vector(size if not isinstance(size, (int, float)) else (size,) * 3), verts=bm.verts)
        obj = self._bm_object(name, bm, material, location, rotation, False, collection, ground)
        if bevel:
            self.bevel(obj, bevel)
        return obj

    def cylinder(self, name='Cylinder', radius=0.5, depth=1.0, location=(0, 0, 0), material=None, rotation=(0, 0, 0),
                 segments=48, bevel=0.0, smooth=True, cap=True, collection=None, radius_top=None):
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=segments, radius1=radius,
                              radius2=radius if radius_top is None else radius_top, depth=depth)
        obj = self._bm_object(name, bm, material, location, rotation, smooth, collection)
        if smooth:
            self._auto_smooth(obj)
        if bevel:
            self.bevel(obj, bevel)
        return obj

    def cone(self, name='Cone', radius=0.5, depth=1.0, location=(0, 0, 0), material=None, rotation=(0, 0, 0),
             segments=48, radius_top=0.0, smooth=True, collection=None):
        return self.cylinder(name, radius, depth, location, material, rotation, segments, smooth=smooth,
                             collection=collection, radius_top=radius_top)

    def sphere(self, name='Sphere', radius=0.5, location=(0, 0, 0), material=None, segments=48, rings=24,
               smooth=True, collection=None, scale=(1, 1, 1)):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=rings, radius=radius)
        obj = self._bm_object(name, bm, material, location, (0, 0, 0), smooth, collection)
        obj.scale = scale
        return obj

    def ico(self, name='Ico', radius=0.5, location=(0, 0, 0), material=None, subdivisions=3, smooth=False, collection=None):
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=subdivisions, radius=radius)
        return self._bm_object(name, bm, material, location, (0, 0, 0), smooth, collection)

    def torus(self, name='Torus', radius=1.0, thickness=0.25, location=(0, 0, 0), material=None, rotation=(0, 0, 0),
              segments=64, sides=24, collection=None):
        verts, faces = [], []
        for i in range(segments):
            a = TAU * i / segments
            for j in range(sides):
                b = TAU * j / sides
                r = radius + thickness * math.cos(b)
                verts.append((r * math.cos(a), r * math.sin(a), thickness * math.sin(b)))
        for i in range(segments):
            for j in range(sides):
                faces.append((i * sides + j, i * sides + (j + 1) % sides,
                              ((i + 1) % segments) * sides + (j + 1) % sides, ((i + 1) % segments) * sides + j))
        return self.mesh(name, verts, faces, material, location, rotation, smooth=True, collection=collection)

    def plane(self, name='Plane', size=(2, 2), location=(0, 0, 0), material=None, rotation=(0, 0, 0),
              subdivisions=0, collection=None, ground=False):
        sx, sy = (size, size) if isinstance(size, (int, float)) else size
        n = subdivisions + 1
        verts = [((i / n - .5) * sx, (j / n - .5) * sy, 0) for j in range(n + 1) for i in range(n + 1)]
        faces = [(j * (n + 1) + i, j * (n + 1) + i + 1, (j + 1) * (n + 1) + i + 1, (j + 1) * (n + 1) + i)
                 for j in range(n) for i in range(n)]
        obj = self.mesh(name, verts, faces, material, location, rotation, collection=collection, ground=ground)
        uv = obj.data.uv_layers.new(name='UVMap')
        for loop in obj.data.loops:
            x, y, _ = obj.data.vertices[loop.vertex_index].co
            uv.data[loop.index].uv = (x / sx + .5, y / sy + .5)
        return obj

    def ground(self, material=None, size=400, z=0.0, name='Ground'):
        """Large floor marked as ground so the review overview ignores its extent."""
        return self.plane(name, size, (0, 0, z), material or self.material('Ground', '#6B6B66', .8), ground=True)

    def lathe(self, name, profile, segments=64, material=None, location=(0, 0, 0), rotation=(0, 0, 0),
              smooth=True, collection=None):
        """Revolve a (radius, z) profile around Z. Close the ends by starting/ending at radius 0."""
        verts, faces = [], []
        n = len(profile)
        for i in range(segments):
            a = TAU * i / segments
            for r, z in profile:
                verts.append((r * math.cos(a), r * math.sin(a), z))
        for i in range(segments):
            for k in range(n - 1):
                a0, a1 = i * n + k, ((i + 1) % segments) * n + k
                faces.append((a0, a1, a1 + 1, a0 + 1))
        obj = self.mesh(name, verts, faces, material, location, rotation, smooth=smooth, collection=collection)
        self._merge(obj)
        return obj

    def extrude(self, name, polygon, height=1.0, material=None, location=(0, 0, 0), rotation=(0, 0, 0),
                bevel=0.0, collection=None):
        """Prism from a 2D (x, y) outline (counter-clockwise) extruded up by `height`."""
        n = len(polygon)
        verts = [(x, y, 0) for x, y in polygon] + [(x, y, height) for x, y in polygon]
        faces = [tuple(reversed(range(n))), tuple(range(n, 2 * n))]
        faces += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
        obj = self.mesh(name, verts, faces, material, location, rotation, collection=collection)
        if bevel:
            self.bevel(obj, bevel)
        return obj

    def arch_profile(self, span, rise=None, kind='gothic', steps=24):
        """Intrados of an arch as [(x, z, cx, cz)]: points from left to right springing, each with
        the centre of the arc it lies on. kind: gothic (two-centred, pointed), round, segmental."""
        h = span / 2
        if kind == 'round':
            return [(-h * math.cos(math.pi * i / steps), h * math.sin(math.pi * i / steps), 0.0, 0.0)
                    for i in range(steps + 1)]
        if kind == 'segmental':
            rise = rise or span / 4
            r = (h * h + rise * rise) / (2 * rise)
            cz = rise - r
            a = math.asin(h / r)
            return [(r * math.sin(-a + 2 * a * i / steps), cz + r * math.cos(-a + 2 * a * i / steps), 0.0, cz)
                    for i in range(steps + 1)]
        rise = rise or span * 0.87
        if rise <= h * 1.02:
            # A pointed arch needs rise > span/2; fall back to an equilateral arch rather than fail.
            print(f'KIT_NOTE gothic arch rise {rise:.2f} <= half span {h:.2f}; using equilateral rise', flush=True)
            rise = span * math.sqrt(3) / 2
        cx = (rise * rise - h * h) / (2 * h)
        r = h + cx
        apex = math.atan2(rise, -cx)
        half = steps // 2
        left = [(cx + r * math.cos(th), r * math.sin(th), cx, 0.0)
                for th in (math.pi + (apex - math.pi) * i / half for i in range(half + 1))]
        right = [(-x, z, -c, cz) for x, z, c, cz in reversed(left[:-1])]
        return left + right

    def arch(self, name='Arch', span=2.0, rise=None, kind='gothic', depth=0.5, thickness=0.3, location=(0, 0, 0),
             rotation=(0, 0, 0), material=None, pier_height=0.0, pier_width=None, collection=None, steps=24):
        """An arch ring in the XZ plane (depth along Y), springing at z=pier_height, with optional
        square piers below. Returns the ring object (piers are parented to it)."""
        inner = self.arch_profile(span, rise, kind, steps)
        outer = []
        for x, z, cx, cz in inner:
            d = Vector((x - cx, z - cz))
            d = d.normalized() if d.length else Vector((0, 1))
            outer.append((x + d.x * thickness, z + d.y * thickness))
        n = len(inner)
        y0, y1 = -depth / 2, depth / 2
        verts = []
        for x, z, *_ in inner:
            verts += [(x, y0, z + pier_height), (x, y1, z + pier_height)]
        for x, z in outer:
            verts += [(x, y0, z + pier_height), (x, y1, z + pier_height)]
        I = lambda i, side: 2 * i + side
        O = lambda i, side: 2 * n + 2 * i + side
        faces = []
        for i in range(n - 1):
            faces.append((I(i, 0), I(i + 1, 0), O(i + 1, 0), O(i, 0)))   # front
            faces.append((O(i, 1), O(i + 1, 1), I(i + 1, 1), I(i, 1)))   # back
            faces.append((I(i, 1), I(i + 1, 1), I(i + 1, 0), I(i, 0)))   # intrados
            faces.append((O(i, 0), O(i + 1, 0), O(i + 1, 1), O(i, 1)))   # extrados
        faces.append((I(0, 0), O(0, 0), O(0, 1), I(0, 1)))
        faces.append((I(n - 1, 1), O(n - 1, 1), O(n - 1, 0), I(n - 1, 0)))
        obj = self.mesh(name, verts, faces, material, location, rotation, collection=collection)
        self._merge(obj)
        if pier_height:
            pw = pier_width or thickness
            for sx in (-1, 1):
                pier = self.box(f'{name} pier', (pw, depth, pier_height),
                                (sx * (span / 2 + pw / 2), 0, pier_height / 2), material, collection=collection)
                pier.parent = obj
        return obj

    def tube(self, name, points, radius=0.05, material=None, closed=False, resolution=12, collection=None,
             taper=None, smooth=True):
        """Swept circular tube along points (a curve object with bevel). Good for cables, ribs, paths."""
        cu = bpy.data.curves.new(name, 'CURVE')
        cu.dimensions = '3D'
        cu.bevel_depth = radius
        cu.bevel_resolution = max(1, resolution // 4)
        cu.use_fill_caps = True
        sp = cu.splines.new('POLY' if len(points) > 64 else 'BEZIER')
        if sp.type == 'BEZIER':
            sp.bezier_points.add(len(points) - 1)
            for bp, pt in zip(sp.bezier_points, points):
                bp.co = pt
                bp.handle_left_type = bp.handle_right_type = 'AUTO'
        else:
            sp.points.add(len(points) - 1)
            for bp, pt in zip(sp.points, points):
                bp.co = (*pt, 1)
        sp.use_cyclic_u = closed
        if taper:
            for bp, r in zip(sp.bezier_points if sp.type == 'BEZIER' else sp.points, taper):
                bp.radius = r
        obj = bpy.data.objects.new(name, cu)
        if material:
            cu.materials.append(material)
        return self._link(obj, collection)

    def text(self, body, size=1.0, location=(0, 0, 0), rotation=(90, 0, 0), material=None, extrude=0.0,
             bevel=0.0, align='CENTER', font=None, name=None, collection=None, spacing=1.0):
        """3D text. font is a reference ID, a fontsource:/asset ID, or None for Blender's default."""
        cu = bpy.data.curves.new(name or f'Text {body[:16]}', 'FONT')
        cu.body = body
        cu.size = size
        cu.extrude = extrude
        cu.bevel_depth = bevel
        cu.align_x = align
        cu.align_y = 'CENTER'
        cu.space_character = spacing
        if font:
            cu.font = self.font(font)
        obj = bpy.data.objects.new(cu.name, cu)
        obj.location = location
        obj.rotation_euler = [math.radians(a) for a in rotation]
        if material:
            cu.materials.append(material)
        return self._link(obj, collection)

    def font(self, source):
        return bpy.data.fonts.load(str(self.file(source, kinds=('font',))), check_existing=True)

    def instance(self, obj, location=(0, 0, 0), rotation=(0, 0, 0), scale=1.0, name=None, collection=None):
        """Linked duplicate sharing mesh data: cheap repetition."""
        dup = bpy.data.objects.new(name or obj.name, obj.data)
        dup.location = location
        dup.rotation_euler = [math.radians(a) for a in rotation]
        dup.scale = (scale,) * 3 if isinstance(scale, (int, float)) else scale
        return self._link(dup, collection or (obj.users_collection[0] if obj.users_collection else None))

    def array(self, obj, count, offset=(1, 0, 0), rotation_step=(0, 0, 0), name=None):
        """`count` linked copies stepped by `offset` (and rotation_step degrees). Returns them all."""
        out = [obj]
        for i in range(1, count):
            loc = Vector(obj.location) + Vector(offset) * i
            rot = [math.degrees(a) + s * i for a, s in zip(obj.rotation_euler, rotation_step)]
            out.append(self.instance(obj, loc, rot, tuple(obj.scale), name=f'{name or obj.name} {i + 1}'))
        return out

    def scatter(self, prototypes, count, area=(-10, 10, -10, 10), surface=None, scale=(0.8, 1.2), rotate=True,
                min_distance=0.0, seed=None, z=0.0, align_to_normal=False, collection=None, avoid=()):
        """Scatter linked copies of prototype object(s). With `surface`, drop each onto it by raycast.
        `avoid` is a list of (x, y, radius) circles to keep clear. Returns the instances."""
        rng = random.Random(self.seed if seed is None else seed)
        protos = prototypes if isinstance(prototypes, (list, tuple)) else [prototypes]
        bvh = None
        if surface is not None:
            deps = bpy.context.evaluated_depsgraph_get()
            bvh = BVHTree.FromObject(surface.evaluated_get(deps), deps)
            mw = surface.matrix_world
            mwi = mw.inverted()
        placed, out = [], []
        tries = 0
        while len(out) < count and tries < count * 30:
            tries += 1
            x, y = rng.uniform(area[0], area[1]), rng.uniform(area[2], area[3])
            if any((x - ax) ** 2 + (y - ay) ** 2 < ar ** 2 for ax, ay, ar in avoid):
                continue
            if min_distance and any((x - px) ** 2 + (y - py) ** 2 < min_distance ** 2 for px, py in placed):
                continue
            loc, normal = Vector((x, y, z)), Vector((0, 0, 1))
            if bvh:
                origin = mwi @ Vector((x, y, 10000))
                hit = bvh.ray_cast(origin, mwi.to_3x3() @ Vector((0, 0, -1)))
                if hit[0] is None:
                    continue
                loc = mw @ hit[0]
                normal = (mw.to_3x3() @ hit[1]).normalized()
            proto = rng.choice(protos)
            s = rng.uniform(*scale)
            dup = self.instance(proto, loc, (0, 0, rng.uniform(0, 360) if rotate else 0), s * Vector(proto.scale),
                                collection=collection)
            if align_to_normal:
                dup.rotation_euler = (normal.to_track_quat('Z', 'Y') @ Euler((0, 0, dup.rotation_euler.z)).to_quaternion()).to_euler()
            placed.append((x, y))
            out.append(dup)
        return out

    def terrain(self, name='Terrain', size=40.0, resolution=160, height=4.0, roughness=0.5, scale=0.08,
                seed=None, material=None, flatten_center=0.0, ridged=False, ground=True, location=(0, 0, 0)):
        """Heightfield landscape from fractal noise. flatten_center (metres) keeps a level area."""
        seed = self.seed if seed is None else seed
        off = Vector((seed * 13.17, seed * 7.31, 0))
        n = resolution
        verts, faces = [], []
        for j in range(n + 1):
            for i in range(n + 1):
                x, y = (i / n - .5) * size, (j / n - .5) * size
                p = Vector((x * scale, y * scale, 0)) + off
                if ridged:
                    h = noise.ridged_multi_fractal(p, 1.0 - roughness * .5, 2.0, 6, 1.0, 2.0, noise_basis='PERLIN_NEW') * .5
                else:
                    h = noise.fractal(p, 1.0 - roughness * .5, 2.0, 6, noise_basis='PERLIN_NEW')
                if flatten_center:
                    d = math.hypot(x, y)
                    h *= min(1, max(0, (d - flatten_center) / flatten_center)) ** 2
                verts.append((x, y, h * height))
        for j in range(n):
            for i in range(n):
                a = j * (n + 1) + i
                faces.append((a, a + 1, a + n + 2, a + n + 1))
        return self.mesh(name, verts, faces, material, location, smooth=True, ground=ground)

    def height_at(self, obj, x, y):
        deps = bpy.context.evaluated_depsgraph_get()
        bvh = BVHTree.FromObject(obj.evaluated_get(deps), deps)
        mw = obj.matrix_world
        hit = bvh.ray_cast(mw.inverted() @ Vector((x, y, 10000)), Vector((0, 0, -1)))
        return (mw @ hit[0]).z if hit[0] else 0.0

    def rock(self, name='Rock', radius=1.0, location=(0, 0, 0), material=None, seed=None, roughness=0.35,
             squash=0.7, detail=3, collection=None):
        seed = self.rng.random() * 100 if seed is None else seed
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=detail, radius=radius)
        for v in bm.verts:
            d = v.co.normalized()
            v.co = d * radius * (1 + roughness * noise.fractal(d * 1.6 + Vector((seed, seed * .7, 0)), 1.0, 2.0, 4))
            v.co.z *= squash
        obj = self._bm_object(name, bm, material, location, (0, 0, self.rng.uniform(0, 360)), False, collection)
        return obj

    def tree(self, name='Tree', height=6.0, location=(0, 0, 0), style='broadleaf', bark=None, leaves=None,
             seed=None, collection=None):
        """Stylized procedural tree: broadleaf, conifer, palm or bare. Returns the root empty."""
        rng = random.Random(self.seed if seed is None else seed)
        root = self.empty(name, location, collection=collection)
        bark = bark or self.procedural(f'{name} bark', 'bark')
        leaves = leaves or self.procedural(f'{name} leaves', 'leaf')
        trunk_h = height * (0.45 if style == 'broadleaf' else 0.9 if style == 'conifer' else 0.85)
        lean = Vector((rng.uniform(-.3, .3), rng.uniform(-.3, .3), 0)) * (height / 10 if style == 'palm' else .1)
        pts = [Vector((0, 0, 0)), lean * .3 + Vector((0, 0, trunk_h * .5)), lean + Vector((0, 0, trunk_h))]
        trunk = self.tube(f'{name} trunk', pts, radius=height * .035, material=bark, taper=[1.4, 1.0, .6], collection=collection)
        self.parent(trunk, root, keep_transform=False)
        top = pts[-1]
        if style == 'conifer':
            for k in range(5):
                z = trunk_h * (.25 + .17 * k)
                r = height * (.32 - .055 * k)
                c = self.cone(f'{name} tier {k}', r, height * .3, (0, 0, z), leaves, segments=12, collection=collection)
                self.parent(c, root, keep_transform=False)
        elif style == 'palm':
            for k in range(9):
                a = TAU * k / 9 + rng.uniform(-.2, .2)
                d = Vector((math.cos(a), math.sin(a), 0))
                frond = [top, top + d * height * .25 + Vector((0, 0, height * .06)), top + d * height * .45 - Vector((0, 0, height * .12))]
                f = self.tube(f'{name} frond {k}', frond, radius=height * .03, material=leaves, taper=[.4, 1.2, .1], collection=collection)
                f.data.bevel_resolution = 1
                f.scale.z = .3
                self.parent(f, root, keep_transform=False)
        elif style != 'bare':
            for k in range(rng.randint(5, 8)):
                a = rng.uniform(0, TAU)
                off = Vector((math.cos(a), math.sin(a), 0)) * rng.uniform(.1, .35) * height + Vector((0, 0, rng.uniform(-.1, .35) * height))
                blob = self.rock(f'{name} canopy {k}', height * rng.uniform(.18, .27), top + off, leaves,
                                 seed=rng.random() * 50, roughness=.3, squash=.8, detail=3, collection=collection)
                for p in blob.data.polygons:
                    p.use_smooth = True
                self.parent(blob, root, keep_transform=False)
        for i in range(rng.randint(2, 4)) if style in ('broadleaf', 'bare') else ():
            a = rng.uniform(0, TAU)
            start = pts[1] + (pts[2] - pts[1]) * rng.uniform(.3, .9)
            end = start + Vector((math.cos(a), math.sin(a), rng.uniform(.4, .9))) * height * .3
            br = self.tube(f'{name} branch {i}', [start, (start + end) / 2 + Vector((0, 0, .2)), end],
                           radius=height * .016, material=bark, taper=[1, .7, .3], collection=collection)
            self.parent(br, root, keep_transform=False)
        return root

    # ------------------------------------------------------------ modifiers
    def bevel(self, obj, width=0.02, segments=3, harden=True):
        m = obj.modifiers.new('Bevel', 'BEVEL')
        m.width, m.segments, m.limit_method = width, segments, 'ANGLE'
        m.harden_normals = harden
        return m

    def subdivide(self, obj, levels=2, render_levels=None):
        m = obj.modifiers.new('Subdivision', 'SUBSURF')
        m.levels, m.render_levels = levels, render_levels or levels
        return m

    def displace(self, obj, strength=0.2, scale=1.0, kind='CLOUDS', seed=None, detail=2):
        tex = bpy.data.textures.new(f'{obj.name} displace', kind)
        if hasattr(tex, 'noise_scale'):
            tex.noise_scale = scale
        if hasattr(tex, 'noise_depth'):
            tex.noise_depth = detail
        m = obj.modifiers.new('Displace', 'DISPLACE')
        m.texture, m.strength = tex, strength
        m.texture_coords = 'LOCAL'
        return m

    def solidify(self, obj, thickness=0.05, offset=-1.0):
        m = obj.modifiers.new('Solidify', 'SOLIDIFY')
        m.thickness, m.offset = thickness, offset
        return m

    def boolean(self, obj, cutter, operation='DIFFERENCE', hide_cutter=True):
        m = obj.modifiers.new('Boolean', 'BOOLEAN')
        m.object, m.operation, m.solver = cutter, operation, 'EXACT'
        if hide_cutter:
            cutter.hide_render = cutter.hide_viewport = True
        return m

    def _auto_smooth(self, obj, angle=40):
        try:
            mod = obj.modifiers.new('Smooth by Angle', 'NODES')
            obj.modifiers.remove(mod)
        except Exception:
            pass
        for p in obj.data.polygons:
            p.use_smooth = True
        if hasattr(obj.data, 'set_sharp_from_angle'):
            obj.data.set_sharp_from_angle(angle=math.radians(angle))

    def _merge(self, obj, distance=1e-5):
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=distance)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(obj.data)
        bm.free()

    def outline(self, obj, thickness=0.02, color='#111111'):
        """Inverted-hull ink outline (works in Cycles and EEVEE)."""
        mat = bpy.data.materials.new(f'{obj.name} outline')
        mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        geo = nt.nodes.new('ShaderNodeNewGeometry')
        em = nt.nodes.new('ShaderNodeEmission')
        em.inputs['Color'].default_value = rgba(color)
        tr = nt.nodes.new('ShaderNodeBsdfTransparent')
        mix = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(geo.outputs['Backfacing'], mix.inputs[0])
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs['Surface'])
        obj.data.materials.append(mat)
        m = obj.modifiers.new('Outline', 'SOLIDIFY')
        m.thickness, m.offset = thickness, 1.0
        m.use_flip_normals = True
        m.material_offset = len(obj.data.materials) - 1
        return m

    # ------------------------------------------------------- lights & world
    def _world(self):
        world = self.scene.world or bpy.data.worlds.new('World')
        self.scene.world = world
        world.use_nodes = True
        nt = world.node_tree
        nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputWorld')
        bg = nt.nodes.new('ShaderNodeBackground')
        nt.links.new(bg.outputs[0], out.inputs['Surface'])
        return world, nt, bg

    def world(self, color='#1A1D22', strength=1.0, top=None):
        """Flat (or two-tone gradient if top is given) world light and background."""
        world, nt, bg = self._world()
        bg.inputs['Strength'].default_value = strength
        if top is None:
            bg.inputs['Color'].default_value = rgba(color)
        else:
            coord = nt.nodes.new('ShaderNodeTexCoord')
            sep = nt.nodes.new('ShaderNodeSeparateXYZ')
            nt.links.new(coord.outputs['Generated'], sep.inputs[0])
            ramp = self._ramp(nt, [color, top])
            nt.links.new(sep.outputs['Z'], ramp.inputs['Fac'])
            nt.links.new(ramp.outputs['Color'], bg.inputs['Color'])
        return world

    def sky(self, sun_elevation=35.0, sun_rotation=0.0, strength=0.12, altitude=0.0, air=1.0, aerosol=1.0,
            ozone=1.0, sun_disc=True, sun_intensity=1.0):
        """Physical multiple-scattering daylight sky that lights the scene with its own sun.
        Its physical intensity is high: strength 0.08-0.2 suits exteriors at exposure 0; an interior
        lit through windows wants about 0.08 with kit.render(exposure=1)."""
        world, nt, bg = self._world()
        sky = nt.nodes.new('ShaderNodeTexSky')
        sky.sky_type = 'MULTIPLE_SCATTERING' if 'MULTIPLE_SCATTERING' in [i.identifier for i in sky.bl_rna.properties['sky_type'].enum_items] else 'NISHITA'
        sky.sun_elevation = math.radians(sun_elevation)
        sky.sun_rotation = math.radians(sun_rotation)
        sky.altitude = altitude
        sky.air_density, sky.aerosol_density, sky.ozone_density = air, aerosol, ozone
        sky.sun_disc = sun_disc
        sky.sun_intensity = sun_intensity
        nt.links.new(sky.outputs['Color'], bg.inputs['Color'])
        bg.inputs['Strength'].default_value = strength
        return sky

    def hdri(self, source, strength=1.0, rotation=0.0, background=None, background_strength=1.0):
        """Image-based lighting from an HDRI asset. background='#RRGGBB' hides the image behind a color."""
        world, nt, bg = self._world()
        coord = nt.nodes.new('ShaderNodeTexCoord')
        mapping = nt.nodes.new('ShaderNodeMapping')
        mapping.inputs['Rotation'].default_value = (0, 0, math.radians(rotation))
        env = nt.nodes.new('ShaderNodeTexEnvironment')
        info = self.assets.get(source)
        path = self.file(source, filename=next((f for f in info['files'] if f.endswith(('.hdr', '.exr'))), None)) if info else self.file(source)
        env.image = bpy.data.images.load(str(path), check_existing=True)
        nt.links.new(coord.outputs['Generated'], mapping.inputs['Vector'])
        nt.links.new(mapping.outputs['Vector'], env.inputs['Vector'])
        nt.links.new(env.outputs['Color'], bg.inputs['Color'])
        bg.inputs['Strength'].default_value = strength
        if background:
            out = next(n for n in nt.nodes if n.type == 'OUTPUT_WORLD')
            path_node = nt.nodes.new('ShaderNodeLightPath')
            bg2 = nt.nodes.new('ShaderNodeBackground')
            bg2.inputs['Color'].default_value = rgba(background)
            bg2.inputs['Strength'].default_value = background_strength
            mix = nt.nodes.new('ShaderNodeMixShader')
            nt.links.new(path_node.outputs['Is Camera Ray'], mix.inputs[0])
            nt.links.new(bg.outputs[0], mix.inputs[1])
            nt.links.new(bg2.outputs[0], mix.inputs[2])
            nt.links.new(mix.outputs[0], out.inputs['Surface'])
        return env

    def _light(self, kind, name, location, power, color, target=None):
        data = bpy.data.lights.new(name, kind)
        data.energy = power
        data.color = rgba(color)[:3]
        obj = bpy.data.objects.new(name, data)
        obj.location = location
        self._link(obj)
        if target is not None:
            self.look_at(obj, target)
        return obj

    def sun(self, elevation=45.0, azimuth=30.0, strength=3.0, color='#FFF4E5', angle=1.0, name='Sun'):
        """Directional sunlight; azimuth is degrees from +Y toward +X; strength in W/m^2."""
        obj = self._light('SUN', name, (0, 0, 20), strength, color)
        obj.data.angle = math.radians(angle)
        el, az = math.radians(elevation), math.radians(azimuth)
        direction = -Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))
        obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
        return obj

    def area(self, name='Area', location=(0, -4, 4), target=(0, 0, 0), power=500.0, color='#FFFFFF', size=2.0,
             shape='RECTANGLE', size_y=None, spread=180.0):
        obj = self._light('AREA', name, location, power, color, target)
        obj.data.shape = shape
        obj.data.size = size
        obj.data.size_y = size_y or size
        obj.data.spread = math.radians(spread)
        return obj

    def point(self, name='Point', location=(0, 0, 3), power=200.0, color='#FFFFFF', radius=0.1):
        obj = self._light('POINT', name, location, power, color)
        obj.data.shadow_soft_size = radius
        return obj

    def spot(self, name='Spot', location=(0, -4, 4), target=(0, 0, 0), power=800.0, color='#FFFFFF', angle=35.0,
             blend=0.3, radius=0.1):
        obj = self._light('SPOT', name, location, power, color, target)
        obj.data.spot_size, obj.data.spot_blend = math.radians(angle), blend
        obj.data.shadow_soft_size = radius
        return obj

    def three_point(self, target=(0, 0, 1), distance=6.0, power=800.0, warm='#FFE2C2', cool='#C9DCFF', azimuth=0.0):
        """Studio key, fill and rim lights around `target`, rotated by azimuth degrees."""
        t = Vector(target)
        rot = Matrix.Rotation(math.radians(azimuth), 3, 'Z')
        key = self.area('Key light', t + rot @ Vector((-distance * .7, -distance * .7, distance * .6)), t, power, warm, distance * .4)
        fill = self.area('Fill light', t + rot @ Vector((distance * .8, -distance * .5, distance * .25)), t, power * .35, cool, distance * .6)
        rim = self.area('Rim light', t + rot @ Vector((distance * .2, distance * .9, distance * .7)), t, power * .9, '#FFFFFF', distance * .25)
        return key, fill, rim

    def haze(self, density=0.02, color='#FFFFFF', anisotropy=0.3, size=(60, 60, 30), location=(0, 0, 15),
             name='Atmospheric haze'):
        """Low-density volume box for light shafts and depth. Keep it around, not just behind, the shot."""
        obj = self.box(name, size, location)
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        vol = nt.nodes.new('ShaderNodeVolumePrincipled')
        vol.inputs['Color'].default_value = rgba(color)
        vol.inputs['Density'].default_value = density
        vol.inputs['Anisotropy'].default_value = anisotropy
        nt.links.new(vol.outputs[0], out.inputs['Volume'])
        obj.data.materials.append(mat)
        obj['studio_volume'] = True
        obj.visible_shadow = False
        return obj

    # --------------------------------------------------------------- camera
    def camera(self, location=(0, -10, 2), target=(0, 0, 1), lens=35.0, name='Camera', sensor=36.0, shift=(0, 0),
               clip=(0.05, 2000.0), ortho_scale=None, dof=None, fstop=4.0, active=True):
        """Create the shot camera. `target` adds a 'Camera target' empty with a Track To constraint;
        animate that empty to change where the camera looks. dof=distance or object focuses."""
        data = bpy.data.cameras.new(name)
        data.lens, data.sensor_width = lens, sensor
        data.shift_x, data.shift_y = shift
        data.clip_start, data.clip_end = clip
        if ortho_scale:
            data.type, data.ortho_scale = 'ORTHO', ortho_scale
        cam = bpy.data.objects.new(name, data)
        cam.location = location
        self._link(cam)
        if target is not None:
            tgt = self.empty(f'{name} target', target, size=.3)
            con = cam.constraints.new('TRACK_TO')
            con.target, con.track_axis, con.up_axis = tgt, 'TRACK_NEGATIVE_Z', 'UP_Y'
            cam['studio_target'] = tgt.name
        if dof is not None:
            data.dof.use_dof = True
            if isinstance(dof, (int, float)):
                data.dof.focus_distance = dof
            else:
                data.dof.focus_object = dof
            data.dof.aperture_fstop = fstop
        if active:
            self.scene.camera = cam
        return cam

    def target_of(self, cam):
        name = cam.get('studio_target')
        return bpy.data.objects.get(name) if name else None

    def dolly(self, cam, start, end, target_start=None, target_end=None, ease_kind='in_out', power=2.5,
              t0=0.0, t1=1.0):
        """Straight move from start to end (and optionally move the look target)."""
        self.animate(cam, 'location', lambda t: lerp(start, end, ease(segment(t, t0, t1), ease_kind, power)))
        tgt = self.target_of(cam)
        if tgt and target_start is not None:
            te = target_end if target_end is not None else target_start
            self.animate(tgt, 'location', lambda t: lerp(target_start, te, ease(segment(t, t0, t1), ease_kind, power)))
        return cam

    def orbit(self, cam, center=(0, 0, 0), radius=8.0, height=2.0, start=0.0, sweep=360.0, ease_kind='linear',
              target_height=None, height_wave=0.0):
        """Circle around center. sweep=360 with linear ease is seamless for loops."""
        c = Vector(center)

        def at(t):
            a = math.radians(start + sweep * ease(t, ease_kind))
            return c + Vector((radius * math.sin(a), -radius * math.cos(a), height + height_wave * self.wave(t)))
        self.animate(cam, 'location', at)
        tgt = self.target_of(cam)
        if tgt:
            tgt.location = c + Vector((0, 0, height if target_height is None else target_height))
        return cam

    def crane(self, cam, base, rise=4.0, push=2.0, ease_kind='in_out', look=None):
        """Rise up while pushing toward the look target."""
        b = Vector(base)
        tgt = self.target_of(cam)
        aim = Vector(look) if look is not None else (Vector(tgt.location) if tgt else b + Vector((0, 10, 0)))
        flat = (aim - b)
        flat.z = 0
        flat = flat.normalized() if flat.length else Vector((0, 1, 0))
        return self.animate(cam, 'location', lambda t: b + Vector((0, 0, rise * ease(t, ease_kind))) + flat * push * ease(t, ease_kind))

    def path(self, cam, points, targets=None, ease_kind='in_out', power=2.0, closed=False, look_ahead=0.0):
        """Smooth constant-speed camera path through `points`. `targets` moves the look target along
        its own spline; look_ahead (0..0.2) aims down the path instead."""
        spline = ArcSpline(points, closed)
        self.animate(cam, 'location', lambda t: spline(ease(t, ease_kind, power) if not closed else t))
        tgt = self.target_of(cam)
        if tgt and targets:
            tspline = ArcSpline(targets, closed)
            self.animate(tgt, 'location', lambda t: tspline(ease(t, ease_kind, power) if not closed else t))
        elif tgt and look_ahead:
            self.animate(tgt, 'location', lambda t: spline(min(1, ease(t, ease_kind, power) + look_ahead) if not closed else t + look_ahead))
        return cam

    def handheld(self, cam, amount=0.6, cycles=2, seed=3):
        """Loop-safe subtle rotational shake in degrees (applied as delta rotation)."""
        k = math.radians(amount)
        return self.animate(cam, 'delta_rotation_euler', lambda t: (
            k * self.loop_noise(t, seed, cycles), k * .5 * self.loop_noise(t, seed + 9, cycles),
            k * .7 * self.loop_noise(t, seed + 21, cycles)), step=1)

    def rack_focus(self, cam, distances, fstop=2.0):
        """Animate focus distance: distances=[(t, metres), ...]."""
        cam.data.dof.use_dof = True
        cam.data.dof.aperture_fstop = fstop
        return self.key(cam.data.dof, 'focus_distance', distances)

    def zoom(self, cam, lens_start, lens_end, ease_kind='in_out'):
        return self.animate(cam.data, 'lens', lambda t: lerp(lens_start, lens_end, ease(t, ease_kind)))

    # -------------------------------------------------------------- imports
    def import_model(self, source, location=(0, 0, 0), rotation=(0, 0, 0), size=None, scale=1.0, on_ground=True,
                     name=None):
        """Import a model reference or asset (glb/gltf/obj/fbx/usd/stl/ply/blend). Returns a parent
        empty. size=metres fits the largest dimension; on_ground puts its lowest point at z=location.z."""
        path = self._model_path(source)
        before = set(bpy.data.objects)
        ext = path.suffix.lower()
        if ext in ('.glb', '.gltf'):
            bpy.ops.import_scene.gltf(filepath=str(path))
        elif ext == '.obj':
            bpy.ops.wm.obj_import(filepath=str(path))
        elif ext == '.fbx':
            bpy.ops.import_scene.fbx(filepath=str(path))
        elif ext in ('.usd', '.usda', '.usdc', '.usdz'):
            bpy.ops.wm.usd_import(filepath=str(path))
        elif ext == '.stl':
            bpy.ops.wm.stl_import(filepath=str(path))
        elif ext == '.ply':
            bpy.ops.wm.ply_import(filepath=str(path))
        elif ext == '.blend':
            with bpy.data.libraries.load(str(path), link=False) as (src, dst):
                dst.objects = list(src.objects)
            for obj in dst.objects:
                if obj and obj.type != 'CAMERA' and obj.type != 'LIGHT':
                    self.scene.collection.objects.link(obj)
        else:
            raise ValueError(f'Cannot import {ext} models')
        new = [o for o in bpy.data.objects if o not in before and o.name in self.scene.objects]
        if not new:
            raise ValueError(f'{source} contained no objects')
        root = self.empty(name or f'Model {path.stem}', (0, 0, 0))
        for obj in new:
            if obj.parent is None:
                obj.parent = root
            if obj.type == 'CAMERA' or obj.type == 'LIGHT':
                obj.hide_render = obj.hide_viewport = True
        bpy.context.view_layer.update()
        lo, hi = self.bounds([o for o in new if o.type == 'MESH'] or new)
        dims = hi - lo
        fit = (size / max(dims)) if size and max(dims) > 0 else 1.0
        root.scale = (fit * scale,) * 3
        centre = (lo + hi) / 2
        offset = Vector((-centre.x, -centre.y, -lo.z if on_ground else -centre.z)) * fit * scale
        root.location = Vector(location) + offset
        root.rotation_euler = [math.radians(a) for a in rotation]
        return root

    def play_animation(self, root, speed=1.0, action=None, start=0.0):
        """Loop an imported model's embedded animation (e.g. a rigged glTF walk) over the whole shot.
        root is what kit.import_model returned; speed scales playback; action picks one by name
        substring. Returns the animated objects. Whole repeats keep loops seamless only if the
        clip length divides the shot; otherwise prefer non-looping shots."""
        animated = []
        for obj in [root, *root.children_recursive]:
            ad = obj.animation_data
            acts = [a for a in bpy.data.actions if action and action.lower() in a.name.lower()] if action else []
            act = acts[0] if acts else (ad.action if ad and ad.action else None)
            if act is None:
                continue
            ad = ad or obj.animation_data_create()
            first, last = act.frame_range
            length = max(1.0, last - first)
            ad.action = None
            track = ad.nla_tracks.new()
            strip = track.strips.new(act.name, int(self.frame(start)), act)
            strip.scale = 1.0 / speed
            strip.repeat = max(1.0, (self.frames + 2) / (length / speed))
            if hasattr(ad, 'action_slot') and hasattr(strip, 'action_slot') and act.slots:
                strip.action_slot = act.slots[0]
            animated.append(obj)
        if not animated:
            raise ValueError('No embedded animation found under this model')
        return animated

    def _model_path(self, source):
        ref = next((r for r in self.references if r.id == source), None)
        if ref:
            return ref.path
        info = self.assets.get(source)
        if not info:
            raise ValueError(f'{source} is neither a model reference nor a declared asset')
        folder = self.job / 'assets' / info['folder']
        for ext in ('.glb', '.gltf', '.blend', '.fbx', '.obj', '.usdz', '.usd', '.usdc', '.stl', '.ply'):
            for f in sorted(info['files']):
                if f.lower().endswith(ext):
                    return folder / f
        raise ValueError(f'{source} has no importable model file: {sorted(info["files"])}')

    def blend_material(self, source):
        """Append the first material from a .blend asset (e.g. a BlenderKit material)."""
        path = self._model_path(source)
        with bpy.data.libraries.load(str(path), link=False) as (src, dst):
            dst.materials = src.materials[:1]
        if not dst.materials:
            raise ValueError(f'{source} contains no materials')
        return dst.materials[0]

    def image_plane(self, source, height=2.0, location=(0, 0, 1), rotation=(90, 0, 0), index=0, emission=0.0,
                    name=None):
        """A plane sized to the image's aspect, showing a reference or asset image."""
        img = self.image(source, index)
        w, h = img.size
        aspect = w / h if h else 1
        obj = self.plane(name or f'Image {source}', (height * aspect, height), location, rotation=rotation)
        obj.data.materials.append(self.image_material(f'{obj.name} material', source, index, emission))
        return obj

    def data(self, source):
        """Parsed data reference: JSON value, or a list of row dicts for CSV/TSV (numbers converted)."""
        path = self.file(source, kinds=('data',))
        text = path.read_text(encoding='utf-8')
        if path.suffix.lower() == '.json':
            return json.loads(text)
        rows = list(csv.DictReader(text.splitlines(), delimiter='\t' if path.suffix.lower() == '.tsv' else ','))

        def conv(v):
            try:
                return int(v)
            except (TypeError, ValueError):
                try:
                    return float(v)
                except (TypeError, ValueError):
                    return v
        return [{k: conv(v) for k, v in row.items()} for row in rows]

    def read_text(self, source):
        """Text of a shot list or notes reference."""
        return self.file(source, kinds=('text',)).read_text(encoding='utf-8')

    def svg(self, source, size=2.0, extrude=0.02, material=None, location=(0, 0, 0), rotation=(90, 0, 0)):
        """Import an SVG logo as curves under a parent empty, fitted to `size` metres wide."""
        path = self.file(source, kinds=('vector',))
        before = set(bpy.data.objects)
        bpy.ops.import_curve.svg(filepath=str(path))
        new = [o for o in bpy.data.objects if o not in before]
        root = self.empty(f'Logo {path.stem}', (0, 0, 0))
        for o in new:
            o.parent = root
            if o.type == 'CURVE':
                o.data.extrude = extrude / max(1e-6, size)
                if material:
                    o.data.materials.clear()
                    o.data.materials.append(material)
        bpy.context.view_layer.update()
        lo, hi = self.bounds(new)
        width = max(1e-6, hi.x - lo.x)
        s = size / width
        root.scale = (s, s, s)
        centre = (lo + hi) / 2
        root.rotation_euler = [math.radians(a) for a in rotation]
        bpy.context.view_layer.update()
        root.location = Vector(location) - (root.matrix_world.to_3x3() @ centre)
        return root

    def references_by_role(self, role):
        return [r for r in self.references if r.role == role]

    # ---------------------------------------------------------- figures
    def figure(self, name='Figure', height=1.75, location=(0, 0, 0), material=None, head_material=None,
               build=1.0, facing=0.0):
        """Stylized jointed mannequin. Returns a dict of joint empties (root, hips, chest, neck, head,
        shoulder_l/r, elbow_l/r, hip_l/r, knee_l/r). Rotate joints (kit.walk, kit.idle, kit.wave_hand)."""
        s = height / 1.75
        mat = material or self.material(f'{name} body', '#C9B8A6', .55, subsurface=.05)
        head_mat = head_material or mat
        J = {}
        J['root'] = self.empty(name, location, display='ARROWS', size=.3 * s)
        J['root'].rotation_euler.z = math.radians(facing)

        def joint(key, parent, offset):
            e = self.empty(f'{name} {key}', (0, 0, 0), size=.08 * s)
            e.parent = J[parent]
            e.location = Vector(offset) * s
            J[key] = e
            return e

        def limb(key, length, radius, along=-1):
            seg = self.cylinder(f'{name} {key} limb', radius * s * build, length * s, (0, 0, along * length * s / 2),
                                mat, segments=20)
            end = self.sphere(f'{name} {key} cap', radius * s * build * 1.05, (0, 0, along * length * s), mat, segments=16, rings=8)
            for o in (seg, end):
                o.parent = J[key]
            return seg
        joint('hips', 'root', (0, 0, .95))
        joint('chest', 'hips', (0, 0, .12))
        torso = self.sphere(f'{name} torso', .2 * s, (0, 0, .2 * s), mat, scale=(1.05 * build, .65 * build, 1.5))
        torso.parent = J['chest']
        pelvis = self.sphere(f'{name} pelvis', .17 * s, (0, 0, 0), mat, scale=(1.05 * build, .7 * build, .7))
        pelvis.parent = J['hips']
        joint('neck', 'chest', (0, 0, .46))
        joint('head', 'neck', (0, 0, .06))
        head = self.sphere(f'{name} head', .115 * s, (0, 0, .11 * s), head_mat, scale=(.9, 1.0, 1.15))
        head.parent = J['head']
        for side, x in (('l', 1), ('r', -1)):
            joint(f'shoulder_{side}', 'chest', (x * .2, 0, .4))
            limb(f'shoulder_{side}', .3, .045)
            joint(f'elbow_{side}', f'shoulder_{side}', (0, 0, -.3))
            limb(f'elbow_{side}', .28, .038)
            joint(f'hip_{side}', 'hips', (x * .1, 0, -.04))
            limb(f'hip_{side}', .43, .065)
            joint(f'knee_{side}', f'hip_{side}', (0, 0, -.43))
            limb(f'knee_{side}', .43, .05)
            foot = self.box(f'{name} foot {side}', (.09 * s, .22 * s, .06 * s), (0, -.05 * s, -.45 * s), mat)
            foot.parent = J[f'knee_{side}']
        for e in J.values():
            e.hide_render = True
        return J

    def walk(self, J, cycles=2, stride=30.0, arm_swing=25.0, bounce=0.03, travel=None):
        """Loop-safe walk cycle on a kit.figure. travel=(start, end) also moves the root (not loop-safe)."""
        def rot(key, fn):
            self.animate(J[key], 'rotation_euler', lambda t: (math.radians(fn(t)), 0, 0))
        for side, ph in (('l', 0.0), ('r', 0.5)):
            rot(f'hip_{side}', lambda t, ph=ph: stride * self.wave(t, cycles, ph))
            rot(f'knee_{side}', lambda t, ph=ph: -stride * 1.1 * max(0, self.wave(t, cycles, ph + .25)))
            rot(f'shoulder_{side}', lambda t, ph=ph: -arm_swing * self.wave(t, cycles, ph))
            rot(f'elbow_{side}', lambda t, ph=ph: 15 + 10 * max(0, self.wave(t, cycles, ph)))
        base = Vector(J['hips'].location)
        self.animate(J['hips'], 'location', lambda t: base + Vector((0, 0, bounce * abs(self.wave(t, cycles)))))
        if travel:
            self.animate(J['root'], 'location', lambda t: lerp(travel[0], travel[1], t))
        return J

    def idle(self, J, cycles=1, breathe=0.015, sway=2.0):
        """Loop-safe breathing and weight shift."""
        self.animate(J['chest'], 'scale', lambda t: (1, 1 + breathe * self.wave(t, cycles * 2), 1 + breathe * self.wave(t, cycles * 2)))
        self.animate(J['hips'], 'rotation_euler', lambda t: (0, math.radians(sway * self.wave(t, cycles)), 0))
        self.animate(J['head'], 'rotation_euler', lambda t: (math.radians(3 * self.loop_noise(t, 4, cycles)), 0,
                                                              math.radians(6 * self.loop_noise(t, 7, cycles))))
        return J

    def wave_hand(self, J, side='r', cycles=3, start=0.0, end=1.0):
        x = 1 if side == 'l' else -1
        self.animate(J[f'shoulder_{side}'], 'rotation_euler', lambda t: (0, math.radians(-x * 150 * ease(min(1, segment(t, start, end) * 4), 'out')), 0))
        self.animate(J[f'elbow_{side}'], 'rotation_euler', lambda t: (0, math.radians(-x * 25 * self.wave(t, cycles)), 0))
        return J

    # ------------------------------------------------------------- physics
    def particles(self, emitter, count=500, lifetime=None, velocity=2.0, random_velocity=0.5, gravity=1.0,
                  instance=None, size=0.05, size_random=0.3, start=0.0, end=0.7, seed=None, physics='NEWTON',
                  render_emitter=False):
        """Particle system on `emitter`; the studio bakes it into the saved scene.
        instance= an object to use as each particle (hidden at origin by default)."""
        psys_mod = emitter.modifiers.new('Particles', 'PARTICLE_SYSTEM')
        ps = psys_mod.particle_system
        st = ps.settings
        st.count = count
        st.frame_start, st.frame_end = self.frame(start), self.frame(end)
        st.lifetime = lifetime or self.frames
        if isinstance(velocity, (int, float)):
            st.normal_factor = velocity  # along the emitter's normals
        else:
            st.normal_factor = 0
            st.object_align_factor = velocity
        st.factor_random = random_velocity
        st.effector_weights.gravity = gravity
        st.physics_type = physics
        st.particle_size = size
        st.size_random = size_random
        ps.seed = self.seed if seed is None else seed
        st.render_type = 'OBJECT' if instance else 'HALO'
        if instance:
            st.instance_object = instance
            instance.hide_render = True
            instance.location = (0, 0, -1000)
        emitter.show_instancer_for_render = render_emitter
        return ps

    def rigid_body(self, obj, kind='ACTIVE', mass=1.0, shape='CONVEX_HULL', friction=0.5, bounce=0.2):
        """Rigid body simulation (baked by the studio). Passive bodies are static colliders."""
        scene = self.scene
        if scene.rigidbody_world is None:
            with bpy.context.temp_override(scene=scene):
                bpy.ops.rigidbody.world_add()
            scene.rigidbody_world.point_cache.frame_start = 1
            scene.rigidbody_world.point_cache.frame_end = self.frames + 1
            scene.rigidbody_world.collection = bpy.data.collections.new('RigidBodyWorld')
        scene.rigidbody_world.collection.objects.link(obj)
        rb = obj.rigid_body
        rb.type, rb.mass, rb.collision_shape = kind, mass, shape
        rb.friction, rb.restitution = friction, bounce
        return rb

    # --------------------------------------------------------------- render
    def render(self, engine=None, motion_blur=None, shutter=None, exposure=None, look=None, bounces=None,
               transparent=None, film_filter=None, view_transform=None, gamma=None, freestyle=None,
               line_thickness=1.5, line_color='#111111', volume_step=None):
        """Override render defaults. engine='EEVEE' for toon/stylized looks; look is an AgX look such
        as 'AgX - Punchy' or 'AgX - Base Contrast'. Samples are controlled by the studio stage."""
        sc = self.scene
        if engine:
            sc.render.engine = {'EEVEE': 'BLENDER_EEVEE', 'CYCLES': 'CYCLES', 'WORKBENCH': 'BLENDER_WORKBENCH'}.get(engine.upper(), engine)
        if motion_blur is not None:
            sc.render.use_motion_blur = motion_blur
        if shutter is not None:
            sc.render.motion_blur_shutter = shutter
        if exposure is not None:
            sc.view_settings.exposure = exposure
        if gamma is not None:
            sc.view_settings.gamma = gamma
        if view_transform:
            sc.view_settings.view_transform = view_transform
        if look:
            sc.view_settings.look = look
        if bounces is not None:
            sc.cycles.max_bounces = bounces
        if transparent is not None:
            sc.render.film_transparent = transparent
        if film_filter is not None:
            sc.cycles.filter_width = film_filter
        if volume_step is not None:
            sc.cycles.volume_step_rate = volume_step
        if freestyle is not None:
            sc.render.use_freestyle = freestyle
            if freestyle:
                sc.render.line_thickness = line_thickness
                ls = sc.view_layers[0].freestyle_settings.linesets
                lineset = ls[0] if len(ls) else ls.new('Lines')
                lineset.linestyle.color = rgba(line_color)[:3]
        return sc

    # ----------------------------------------------------------- utilities
    def bounds(self, objects):
        lo = Vector((math.inf,) * 3)
        hi = Vector((-math.inf,) * 3)
        deps = bpy.context.evaluated_depsgraph_get()
        found = False
        for obj in objects:
            if obj.type not in ('MESH', 'CURVE', 'FONT', 'SURFACE', 'META'):
                continue
            ev = obj.evaluated_get(deps)
            for corner in ev.bound_box:
                w = obj.matrix_world @ Vector(corner)
                lo = Vector(map(min, lo, w))
                hi = Vector(map(max, hi, w))
                found = True
        if not found:
            return Vector((0, 0, 0)), Vector((0, 0, 0))
        return lo, hi

    def note(self, text):
        """Log a line to the stage run.log (e.g. how a reference was interpreted)."""
        print('KIT_NOTE', text, flush=True)
