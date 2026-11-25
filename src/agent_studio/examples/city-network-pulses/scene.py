"""City transit network as glowing data: stations, routes and travelling light pulses.

Teaches
- Turning a small hand-authored dataset (stations, lines, ridership weights) into geometry:
  every visual variable is driven by data. Busier routes get thicker tubes, brighter emission,
  more and faster pulses; busier stations get bigger discs.
- Metro-map styling: octilinear polylines with filleted corners, built as POLY curves so the
  route passes exactly through every station (Bezier AUTO handles would overshoot).
- Arc-length parametrisation: pulses are placed by distance along the route, so they travel at
  a constant speed in metres per second regardless of how the stations are spaced.
- A dark 'map' that the data lights: low bevelled city blocks in one merged bmesh, a river cut
  out of the grid, and faint street lines from a shader. The emissive routes are the main lights,
  so the blocks catch coloured glow from the lines that pass them.
- Camera tilt from an oblique view to an exact top-down plan on a spherical arc, with the
  look target fixed on the network's centre.
"""
import math

import bmesh
import bpy
from mathutils import Vector

# ---------------------------------------------------------------- data (map units ~ 10 m)
STATIONS = {
    'Central': (0, 0), 'Harbour': (-18, -2), 'Mill': (-36, -6), 'West End': (-56, -6),
    'Market': (16, 4), 'Arsenal': (32, 10), 'East Gate': (52, 14),
    'South Park': (-10, -34), 'Foundry': (-8, -20), 'Old Town': (-4, -10),
    'Museum': (2, 12), 'University': (6, 24), 'North Hill': (14, 34),
    'Lakeside': (-46, 22), 'Chapel': (-30, 18), 'Theatre': (-14, 14), 'Gardens': (20, 20),
    'Dock': (-16, -16), 'Brewery': (12, -14), 'Stadium': (26, -6),
    'Airport Rd': (42, -30), 'Hospital': (-4, 30),
    'Quarry': (-54, -28), 'Tannery': (-32, -22),
}
# (name, colour, ridership 0..1, station sequence)
LINES = [
    ('Red', '#FF3B6B', 1.00, ['West End', 'Mill', 'Harbour', 'Central', 'Market', 'Arsenal', 'East Gate']),
    ('Cyan', '#2FD8FF', 0.80, ['South Park', 'Foundry', 'Old Town', 'Central', 'Museum', 'University', 'North Hill']),
    ('Amber', '#FFB13B', 0.55, ['Lakeside', 'Chapel', 'Theatre', 'Museum', 'Gardens']),
    ('Lime', '#9BFF4A', 0.35, ['Harbour', 'Dock', 'Old Town', 'Brewery', 'Stadium', 'Arsenal']),
    ('Violet', '#B07BFF', 0.22, ['Airport Rd', 'Stadium', 'Market', 'University', 'Hospital']),
    ('Teal', '#3BFFC4', 0.45, ['Quarry', 'Tannery', 'Dock', 'Foundry']),
]
LINE_Z = 2.6                   # routes hover just above the tallest blocks
BLOCK = 5.0                    # street grid pitch
MAP_HALF = (110, 75)           # extent of the city blocks
PULSE_SPEED = 16.0             # map units per second for the busiest line
CORNER = 4.0                   # fillet radius at route corners


# ---------------------------------------------------------------- geometry helpers
def smoother(t):
    t = min(1.0, max(0.0, t))
    return t * t * t * (t * (6 * t - 15) + 10)


def tint(hex_color, amount):
    """Blend a '#RRGGBB' colour toward white by `amount` (sRGB, for emissive cores)."""
    rgb = [int(hex_color[i:i + 2], 16) for i in (1, 3, 5)]
    return '#' + ''.join(f'{round(c + (255 - c) * amount):02X}' for c in rgb)


def octilinear(points):
    """Insert a bend between consecutive stations so every segment runs at a multiple of 45
    degrees, like a schematic metro map: a diagonal leg, then a straight leg."""
    out = [Vector(points[0])]
    for a, b in zip(points, points[1:]):
        a, b = Vector(a), Vector(b)
        d = b - a
        diag = min(abs(d.x), abs(d.y))
        corner = a + Vector((math.copysign(diag, d.x), math.copysign(diag, d.y)))
        if 0.5 < (corner - a).length and 0.5 < (b - corner).length:
            out.append(corner)
        out.append(b)
    return out


def fillet(points, radius, steps=8):
    """Round each interior corner with a circular arc (radius clamped to the shorter leg)."""
    out = [points[0]]
    for i in range(1, len(points) - 1):
        p0, p1, p2 = points[i - 1], points[i], points[i + 1]
        d0, d1 = (p0 - p1), (p2 - p1)
        if d0.length < 1e-6 or d1.length < 1e-6:
            continue
        ang = d0.angle(d1)
        if abs(ang - math.pi) < 1e-3:          # straight through
            out.append(p1)
            continue
        r = min(radius, d0.length * 0.45 * math.tan(ang / 2), d1.length * 0.45 * math.tan(ang / 2))
        t = r / math.tan(ang / 2)
        a, b = p1 + d0.normalized() * t, p1 + d1.normalized() * t
        for k in range(steps + 1):             # quadratic Bezier through the corner ~ arc
            u = k / steps
            out.append((1 - u) ** 2 * a + 2 * u * (1 - u) * p1 + u * u * b)
    out.append(points[-1])
    return out


class Polyline:
    """Arc-length lookup along a 2D polyline: at(s) -> (point, unit tangent)."""

    def __init__(self, pts):
        self.pts = pts
        self.cum = [0.0]
        for a, b in zip(pts, pts[1:]):
            self.cum.append(self.cum[-1] + (b - a).length)
        self.length = self.cum[-1]

    def at(self, s):
        s = min(max(s, 0.0), self.length)
        lo, hi = 0, len(self.cum) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            lo, hi = (mid, hi) if self.cum[mid] <= s else (lo, mid)
        a, b = self.pts[lo], self.pts[hi]
        seg = max(self.cum[hi] - self.cum[lo], 1e-9)
        return a.lerp(b, (s - self.cum[lo]) / seg), (b - a).normalized()


# ---------------------------------------------------------------- materials
def map_material(kit):
    """Ink-blue ground with faint street lines (fract of object XY) and a soft vignette so the
    map dissolves into the night at its edges."""
    mat = kit.material('Map ground', '#060A16', roughness=0.7)
    nt, bs = mat.node_tree, kit.bsdf(mat)
    N, L = nt.nodes, nt.links
    coord = N.new('ShaderNodeTexCoord')
    sep = N.new('ShaderNodeSeparateXYZ'); L.new(coord.outputs['Object'], sep.inputs[0])

    def grid(axis):
        m = N.new('ShaderNodeMath'); m.operation = 'PINGPONG'; m.inputs[1].default_value = BLOCK / 2
        L.new(sep.outputs[axis], m.inputs[0])
        r = N.new('ShaderNodeMapRange'); r.interpolation_type = 'SMOOTHSTEP'
        r.inputs['From Min'].default_value, r.inputs['From Max'].default_value = 0.12, 0.0
        L.new(m.outputs[0], r.inputs['Value'])
        return r.outputs['Result']
    both = N.new('ShaderNodeMath'); both.operation = 'MAXIMUM'
    L.new(grid('X'), both.inputs[0]); L.new(grid('Y'), both.inputs[1])
    em = N.new('ShaderNodeMath'); em.operation = 'MULTIPLY'; em.inputs[1].default_value = 0.35
    L.new(both.outputs[0], em.inputs[0])
    L.new(em.outputs[0], bs.inputs['Emission Strength'])
    bs.inputs['Emission Color'].default_value = kit.color('#1C3A6E')
    return mat


def emissive_line(kit, name, color, strength):
    """Route tube: coloured emission over a glossy core so it also reflects the other lines."""
    mat = kit.material(name, color, roughness=0.25, emission=color, emission_strength=strength, coat=0.6)
    return mat


# ---------------------------------------------------------------- build
def build(kit):
    rng = kit.rng

    # --- the dark map: ground, river, blocks ----------------------------------------------
    kit.ground(map_material(kit), size=600, z=0.0, name='Map')
    river = [Vector((-140, -48)), Vector((-70, -40)), Vector((-40, -48)), Vector((-6, -28)), Vector((20, -22)),
             Vector((48, -40)), Vector((90, -36)), Vector((150, -50))]
    river_line = Polyline(fillet(river, 14, 12))
    water = kit.material('River', '#04122A', roughness=0.08, specular=0.8, coat=1.0)
    ribbon = []
    for k in range(161):
        p, tng = river_line.at(river_line.length * k / 160)
        nrm = Vector((-tng.y, tng.x))
        ribbon.append((p + nrm * 4.2, p - nrm * 4.2))
    verts = [(v.x, v.y, 0.05) for a, b in ribbon for v in (a, b)]
    faces = [(2 * k, 2 * k + 1, 2 * k + 3, 2 * k + 2) for k in range(len(ribbon) - 1)]
    kit.mesh('River', verts, faces, water, collection='Map')

    def near_river(x, y, clearance):
        for k in range(0, 161, 2):
            p, _ = river_line.at(river_line.length * k / 160)
            if (p.x - x) ** 2 + (p.y - y) ** 2 < clearance ** 2:
                return True
        return False

    # City blocks: one merged mesh (hundreds of boxes stay cheap), heights taller near Central,
    # every block inset from the street lines and bevelled by one modifier.
    bm = bmesh.new()
    nx, ny = int(MAP_HALF[0] / BLOCK), int(MAP_HALF[1] / BLOCK)
    for i in range(-nx, nx):
        for j in range(-ny, ny):
            cx, cy = (i + 0.5) * BLOCK, (j + 0.5) * BLOCK
            if near_river(cx, cy, 7.5) or rng.random() < 0.08:       # river and the odd plaza
                continue
            core = math.exp(-(cx * cx + cy * cy) / (2 * 38 ** 2))
            for sub in range(rng.choice((1, 1, 2, 4))):                # split some blocks into lots
                w = BLOCK * (0.72 if sub == 0 else 0.34)
                ox = 0 if sub == 0 else rng.uniform(-1, 1) * BLOCK * 0.2
                oy = 0 if sub == 0 else rng.uniform(-1, 1) * BLOCK * 0.2
                h = 0.25 + (2.1 * core + 0.4) * rng.random() ** 1.6
                res = bmesh.ops.create_cube(bm, size=1.0)
                for v in res['verts']:
                    v.co = Vector((cx + ox + v.co.x * w, cy + oy + v.co.y * w, h / 2 + v.co.z * h))
    me = bpy.data.meshes.new('City blocks')
    bm.to_mesh(me); bm.free()
    blocks = bpy.data.objects.new('City blocks', me)
    blocks_mat = kit.material('City blocks', '#121A2E', roughness=0.55, bump=(3.0, 0.15))
    me.materials.append(blocks_mat)
    kit._link(blocks, 'Map')
    kit.bevel(blocks, 0.08, 2)

    # --- routes, stations and pulses -------------------------------------------------------
    used = {}
    for name, color, load, stops in LINES:
        pts = fillet(octilinear([STATIONS[s] for s in stops]), CORNER)
        line = Polyline(pts)
        radius = 0.22 + 0.33 * load
        route_material = emissive_line(kit, f'Route {name}', color, 0.65 + 2.8 * load)
        kit.tube(f'Route {name}', [(p.x, p.y, LINE_Z) for p in pts], radius, route_material,
                 collection='Network', spline='POLY')
        # Pulses: count and speed scale with ridership. Spacing is even with a seeded jitter.
        # White-hot core tinted toward the line colour, much brighter than the tube it rides.
        pulse_mat = kit.emissive(f'Pulse {name}', tint(color, 0.6), 7.0 + 24.0 * load)
        count = max(2, round(line.length / 22 * (0.5 + 1.5 * load)))
        speed = PULSE_SPEED * (0.6 + 0.4 * load)
        for k in range(count):
            for direction in (1, -1):                      # both directions of travel
                if direction == -1 and load < 0.3:
                    continue
                s0 = (k + rng.uniform(-0.25, 0.25)) / count * line.length
                bead = kit.sphere(f'Pulse {name} {k} {direction}', 1.0, (0, 0, 0), pulse_mat, segments=16, rings=8,
                                  collection='Pulses')
                size = 0.45 + 0.4 * load
                bead.scale = (size * 2.6, size, size)          # elongated along travel; motion blur adds the streak
                bead.rotation_mode = 'QUATERNION'
                for f in range(1, kit.frames + 1):
                    s = (s0 + direction * speed * (f - 1) / kit.fps) % line.length
                    p, tng = line.at(s)
                    bead.location = (p.x, p.y, LINE_Z)
                    bead.rotation_quaternion = Vector((tng.x * direction, tng.y * direction, 0)).to_track_quat('X', 'Z')
                    bead.keyframe_insert('location', frame=f)
                    bead.keyframe_insert('rotation_quaternion', frame=f)
                # Wrapping from the end of the line back to its start would streak across the
                # map under motion blur, so hide the bead on the frame it wraps.
                fc = bead.animation_data.action
                for f in range(2, kit.frames + 1):
                    a = (s0 + direction * speed * (f - 2) / kit.fps) % line.length
                    b = (s0 + direction * speed * (f - 1) / kit.fps) % line.length
                    if abs(b - a) > line.length / 2:
                        kit.key(bead, 'hide_render', [(f - 1, False), (f, True), (f + 1, False)], interpolation='CONSTANT')
        for s in stops:
            used.setdefault(s, []).append((color, load))

    ring_mat = kit.material('Station ring', '#E8F0FF', roughness=0.3, emission='#CFE2FF', emission_strength=2.0)
    for s, lines in used.items():
        x, y = STATIONS[s]
        weight = sum(load for _, load in lines)
        r = 0.9 + 0.7 * weight
        kit.cylinder(f'Station {s}', r, 0.5, (x, y, LINE_Z), kit.material(f'Station {s} core', '#FFFFFF', roughness=0.2,
                     emission='#FFFFFF', emission_strength=3.0 + 3.0 * weight), segments=40, bevel=0.12, collection='Network')
        kit.torus(f'Station {s} ring', r + 0.45, 0.14, (x, y, LINE_Z + 0.05), ring_mat if len(lines) > 1 else
                  emissive_line(kit, f'Station {s} ring', lines[0][0], 3.0), collection='Network')
        # A faint light pillar down to the map anchors each station to its place in the city.
        kit.cylinder(f'Station {s} stem', 0.12, LINE_Z, (x, y, LINE_Z / 2), ring_mat, segments=12, collection='Network')

    # --- light: night world plus a dim blue moon so the blocks keep their form --------------
    kit.world('#03060F', strength=0.5, top='#08122A')
    kit.sun(elevation=35, azimuth=-140, strength=0.24, color='#9DB6FF', angle=3)

    # --- camera: tilt from oblique to top-down on a sphere around the network centre -------
    centre = Vector((-2, 0, 0))
    cam = kit.camera((0, -90, 50), tuple(centre), lens=35, clip=(0.5, 1500))

    def orbit_point(t):
        u = smoother(t)
        el = math.radians(30 + 60 * u)          # 30 degrees oblique -> exactly overhead
        az = math.radians(-28 * (1 - u))        # unwinds a slight yaw on the way up
        dist = 124 + 20 * u
        return centre + dist * Vector((math.cos(el) * math.sin(az), -math.cos(el) * math.cos(az), math.sin(el)))
    kit.animate(cam, 'location', orbit_point)

    kit.render(exposure=0.0, look='AgX - Medium High Contrast', motion_blur=True, shutter=0.6)
