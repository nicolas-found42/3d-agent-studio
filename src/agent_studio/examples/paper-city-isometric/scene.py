"""Paper city, isometric: a pastel cut-paper city block on an orthographic turntable.

Teaches:
- an orthographic camera orbiting at the true isometric elevation (35.26 degrees) as a seamless loop;
- cel shading in EEVEE with kit.toon, where every material gets its own tinted shadow colour
  (pastel toon looks die when shadows are plain grey);
- paper-model construction: layered card base, soft rounded bevels, printed-on windows built as
  one mesh per building, thin ink outlines;
- cars driven along closed rounded-rectangle lanes by arc length, with headings unwrapped so a
  whole lap returns exactly to frame 1.
"""
import colorsys
import math

# ----------------------------------------------------------------------------- layout (metres)
BLOCK = 9.0             # each city block (raised pavement slab) is 9 m square
PITCH = 12.0            # block centre to block centre: 3 m streets between blocks
TILE = 40.0             # the whole diorama tile, edge to edge
STREET_RING = 18.0      # centreline of the street that runs around the tile edge
CURB = 0.25             # pavement slab height
FLOOR = 1.2             # storey height (a toy scale: chunky, readable floors)

# ----------------------------------------------------------------------------- palette
BACKDROP = '#F6E3D8'    # warm peach paper behind the model
ROAD = '#B8BCD9'        # soft periwinkle asphalt
PAVEMENT = '#FBF3E6'
CARD_EDGE = ['#F3B9B2', '#FFF6EA', '#C9B8E8']   # visible card layers in the base, top to bottom
BUILDINGS = ['#F7B7A3', '#A8D8EA', '#FFD7A8', '#C8B6E2', '#B5EAD7', '#F9E79F', '#F6C6D9', '#CFE8B4']
WINDOW = '#7E88BE'
GREENS = ['#9FD8A2', '#7FC7A6', '#BFE4A0']
CARS = ['#FF8C8C', '#7FB7F0', '#FFCF6B', '#9BDBA9', '#C9A2F0', '#FF9FCB', '#7ED1D6']
INK = '#6E5C7E'         # outline colour: a dark plum reads softer than black on pastels

SUN_ELEVATION = 58
SUN_AZIMUTH = 35


def shade_of(color, darken=0.62, hue_shift=0.04, sat_boost=0.10):
    """Shadow tone for a pastel: darker, slightly bluer and a little more saturated."""
    r, g, b = (int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    h = (h + hue_shift) % 1.0 if h > 0.5 or h < 0.12 else h + hue_shift
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, min(1, s + sat_boost), v * darken)
    return '#%02X%02X%02X' % (round(r * 255), round(g * 255), round(b * 255))


def build(kit):
    import bmesh
    import bpy
    from mathutils import Vector

    rng = kit.rng
    kit.render(engine='EEVEE', view_transform='Standard', motion_blur=False)

    mats = {}

    ink = kit.emissive('Ink outline', INK, 1.0)
    ink.use_backface_culling = True   # the inverted hull only shows behind the silhouette

    def outline(obj, thickness):
        """Inverted-hull ink line for EEVEE: a flipped, outward solidify shell whose material culls
        back faces, so only the rim peeking out past the silhouette is drawn."""
        obj.data.materials.append(ink)
        m = obj.modifiers.new('Ink outline', 'SOLIDIFY')
        m.thickness, m.offset, m.use_flip_normals = thickness, 1.0, True
        m.material_offset = len(obj.data.materials) - 1
        return m

    def paper(color, shades=3):
        """Cached toon material whose shadow is a tinted version of its own colour."""
        if color not in mats:
            mats[color] = kit.toon(f'Paper {color}', color, shades=shades, shadow=shade_of(color))
        return mats[color]

    # ------------------------------------------------------------------ light: soft flat studio
    # A broad sun (8 degree disc = soft shadow edges) does the shaping; the pastel world adds an
    # even fill so the shadow side lands on the middle toon band, not on black.
    kit.world(BACKDROP, strength=0.34)
    kit.sun(elevation=SUN_ELEVATION, azimuth=SUN_AZIMUTH, strength=2.8, color="#FFF8EE", angle=6)

    # ------------------------------------------------------------------ the paper base
    # Three stacked card layers with slightly different footprints, like a mounted paper model.
    kit.box('Base card (pink)', (TILE + 0.8, TILE + 0.8, 1.4), (0, 0, -0.95), paper(CARD_EDGE[0]), bevel=0.25)
    kit.box('Base card (cream)', (TILE + 0.4, TILE + 0.4, 0.22), (0, 0, -0.18), paper(CARD_EDGE[1]), bevel=0.06)
    kit.box('Road surface', (TILE, TILE, 0.12), (0, 0, -0.06), paper(ROAD), bevel=0.04)
    # A large backdrop floor in the background colour catches the model's soft shadow.
    kit.plane('Backdrop floor', 400, (0, 0, -1.65), paper(BACKDROP, shades=2), ground=True)

    # ------------------------------------------------------------------ road markings
    marking = paper('#FFFFFF', shades=2)
    lines = []   # (x0, y0, x1, y1) dashed centrelines, skipping intersections
    for c in (-PITCH / 2, PITCH / 2):
        lines += [(c, -16.5, c, 16.5), (-16.5, c, 16.5, c)]
    for c in (-STREET_RING, STREET_RING):
        lines += [(c, -16.5, c, 16.5), (-16.5, c, 16.5, c)]
    dash_verts, dash_faces = [], []
    for x0, y0, x1, y1 in lines:
        length = math.hypot(x1 - x0, y1 - y0)
        ux, uy = (x1 - x0) / length, (y1 - y0) / length
        s = 0.4
        while s + 0.9 < length:
            mid = s + 0.45
            mx, my = x0 + ux * mid, y0 + uy * mid
            near_crossing = any(abs(mx - k) < 2.0 and abs(my - j) < 2.0
                                for k in (-18, -6, 6, 18) for j in (-18, -6, 6, 18))
            if not near_crossing:
                hx, hy = ux * 0.45, uy * 0.45
                px, py = -uy * 0.07, ux * 0.07
                i = len(dash_verts)
                dash_verts += [(mx - hx - px, my - hy - py, 0.012), (mx + hx - px, my + hy - py, 0.012),
                               (mx + hx + px, my + hy + py, 0.012), (mx - hx + px, my - hy + py, 0.012)]
                dash_faces.append((i, i + 1, i + 2, i + 3))
            s += 1.5
    # Zebra crossings on all four approaches of the four central intersections.
    for cx in (-6, 6):
        for cy in (-6, 6):
            for ax in ('x', 'y'):
                for side in (-1, 1):
                    for k in range(5):
                        off = (k - 2) * 0.55
                        if ax == 'x':
                            x, y = cx + side * 1.9, cy + off
                            w, d = 0.7, 0.28
                        else:
                            x, y = cx + off, cy + side * 1.9
                            w, d = 0.28, 0.7
                        i = len(dash_verts)
                        dash_verts += [(x - w / 2, y - d / 2, 0.012), (x + w / 2, y - d / 2, 0.012),
                                       (x + w / 2, y + d / 2, 0.012), (x - w / 2, y + d / 2, 0.012)]
                        dash_faces.append((i, i + 1, i + 2, i + 3))
    kit.mesh('Road markings', dash_verts, dash_faces, marking)

    # ------------------------------------------------------------------ helpers for buildings
    def windows_on_box(name, cx, cy, w, d, z0, h, radius, color=WINDOW):
        """One mesh holding every 'printed' window of a rounded box building.

        Windows sit 2 cm proud of each wall, only on the flat part between the bevelled corners,
        one row per storey. One object per building keeps the scene light."""
        verts, faces = [], []
        ww, wh = 0.5, 0.62
        floors = int((h - radius - 0.6) // FLOOR)
        for face in range(4):
            span = (w if face in (0, 2) else d) - 2 * radius - 0.5
            depth = (d if face in (0, 2) else w) / 2 + 0.02
            cols = max(1, int(span // 0.95))
            for f in range(floors):
                z = z0 + 0.95 + f * FLOOR
                for c in range(cols):
                    u = (c - (cols - 1) / 2) * (span / cols)
                    if face == 0:
                        p = [(cx + u - ww / 2, cy - depth, z), (cx + u + ww / 2, cy - depth, z),
                             (cx + u + ww / 2, cy - depth, z + wh), (cx + u - ww / 2, cy - depth, z + wh)]
                    elif face == 2:
                        p = [(cx - u + ww / 2, cy + depth, z), (cx - u - ww / 2, cy + depth, z),
                             (cx - u - ww / 2, cy + depth, z + wh), (cx - u + ww / 2, cy + depth, z + wh)]
                    elif face == 1:
                        p = [(cx + depth, cy + u - ww / 2, z), (cx + depth, cy + u + ww / 2, z),
                             (cx + depth, cy + u + ww / 2, z + wh), (cx + depth, cy + u - ww / 2, z + wh)]
                    else:
                        p = [(cx - depth, cy - u + ww / 2, z), (cx - depth, cy - u - ww / 2, z),
                             (cx - depth, cy - u - ww / 2, z + wh), (cx - depth, cy - u + ww / 2, z + wh)]
                    i = len(verts)
                    verts += p
                    faces.append((i, i + 1, i + 2, i + 3))
        if faces:
            kit.mesh(f'{name} windows', verts, faces, paper(color, shades=2))

    def windows_on_tower(name, cx, cy, r, z0, h):
        verts, faces = [], []
        floors = int((h - 0.8) // FLOOR)
        n = max(6, int(2 * math.pi * r // 1.0))
        for f in range(floors):
            z = z0 + 0.95 + f * FLOOR
            for k in range(n):
                a = 2 * math.pi * (k + 0.5 * (f % 2)) / n
                half = 0.22 / (r + 0.02)
                p = []
                for da, dz in ((-half, 0), (half, 0), (half, 0.62), (-half, 0.62)):
                    p.append((cx + (r + 0.02) * math.cos(a + da), cy + (r + 0.02) * math.sin(a + da), z + dz))
                i = len(verts)
                verts += p
                faces.append((i, i + 1, i + 2, i + 3))
        kit.mesh(f'{name} windows', verts, faces, paper(WINDOW, shades=2))

    def roof_props(name, cx, cy, w, d, top):
        """Secondary detail at roof scale: AC boxes, a water tank or a roof garden."""
        kind = rng.choice(['ac', 'tank', 'garden', 'ac'])
        if kind == 'tank' and min(w, d) > 2.4:
            leg = paper('#9C8AA8')
            for sx in (-1, 1):
                for sy in (-1, 1):
                    kit.cylinder(f'{name} tank leg', 0.06, 0.8, (cx + sx * 0.45, cy + sy * 0.45, top + 0.4), leg, segments=8)
            kit.cylinder(f'{name} water tank', 0.7, 1.1, (cx, cy, top + 1.35), paper('#E8C9A8'), segments=24, bevel=0.05)
            kit.cone(f'{name} tank roof', 0.78, 0.5, (cx, cy, top + 2.15), paper('#C9A1C2'), segments=24)
        elif kind == 'garden' and min(w, d) > 2.4:
            kit.box(f'{name} planter', (w * 0.55, d * 0.55, 0.3), (cx, cy, top + 0.15), paper('#D9B99B'), bevel=0.08)
            for k in range(3):
                kit.sphere(f'{name} shrub', 0.35, (cx + (k - 1) * w * 0.17, cy, top + 0.5),
                           paper(GREENS[k % 3]), segments=16, rings=8)
        else:
            for k in range(rng.randint(1, 2)):
                kit.box(f'{name} AC unit', (0.9, 0.7, 0.5),
                        (cx + rng.uniform(-w, w) * 0.22, cy + rng.uniform(-d, d) * 0.22, top + 0.25),
                        paper('#DCD8E8'), bevel=0.08)

    def awning(name, cx, cy, w, d, z0):
        """A door and striped awning on one random wall: the ground-floor scale of detail."""
        side = rng.randrange(4)
        accent = rng.choice(['#FF9F9F', '#7FB7F0', '#FFCF6B', '#9BDBA9'])
        if side in (0, 2):
            sgn = -1 if side == 0 else 1
            y = cy + sgn * (d / 2 + 0.25)
            kit.box(f'{name} awning', (1.6, 0.6, 0.14), (cx, y, z0 + 1.25), paper(accent), bevel=0.05)
            kit.box(f'{name} door', (0.7, 0.06, 0.95), (cx, cy + sgn * (d / 2 + 0.01), z0 + 0.48), paper('#8A6E9E'))
        else:
            sgn = -1 if side == 3 else 1
            x = cx + sgn * (w / 2 + 0.25)
            kit.box(f'{name} awning', (0.6, 1.6, 0.14), (x, cy, z0 + 1.25), paper(accent), bevel=0.05)
            kit.box(f'{name} door', (0.06, 0.7, 0.95), (cx + sgn * (w / 2 + 0.01), cy, z0 + 0.48), paper('#8A6E9E'))

    def building_box(name, cx, cy, w, d, h, color, z0=CURB):
        radius = min(0.55, min(w, d) * 0.18)
        body = kit.box(name, (w, d, h), (cx, cy, z0 + h / 2), paper(color), bevel=radius)
        body.modifiers['Bevel'].segments = 5      # rounded paper corners, not chamfers
        outline(body, 0.06)
        # A lighter roof slab inset on top: the second card of a folded roof.
        roof = kit.box(f'{name} roof', (w - 0.5, d - 0.5, 0.18), (cx, cy, z0 + h + 0.05),
                       paper(BUILDINGS[(BUILDINGS.index(color) + 3) % len(BUILDINGS)]), bevel=0.06)
        windows_on_box(name, cx, cy, w, d, z0, h, radius)
        roof_props(name, cx, cy, w, d, z0 + h + 0.12)
        awning(name, cx, cy, w, d, z0)
        return body

    def building_tower(name, cx, cy, r, h, color, z0=CURB):
        body = kit.cylinder(name, r, h, (cx, cy, z0 + h / 2), paper(color), segments=40, bevel=0.3)
        body.modifiers['Bevel'].segments = 4
        outline(body, 0.06)
        kit.cylinder(f'{name} cap', r * 0.75, 0.5, (cx, cy, z0 + h + 0.25), paper('#FFF1E0'), segments=32, bevel=0.08)
        kit.cone(f'{name} spire', r * 0.35, 1.2, (cx, cy, z0 + h + 1.1), paper('#F3B9B2'), segments=24)
        windows_on_tower(name, cx, cy, r, z0, h)

    # ------------------------------------------------------------------ trees and street furniture
    trunk_mat = paper('#B58F7A')
    crowns = [paper(g) for g in GREENS]

    def tree(name, x, y, z, s=1.0, kind=None):
        kind = kind or rng.choice(['round', 'round', 'cone'])
        kit.cylinder(f'{name} trunk', 0.12 * s, 0.9 * s, (x, y, z + 0.45 * s), trunk_mat, segments=10)
        if kind == 'round':
            crown = kit.sphere(f'{name} crown', 0.75 * s, (x, y, z + 1.45 * s), rng.choice(crowns), segments=20, rings=10)
            crown.scale = (1, 1, 0.92)
        else:
            crown = kit.cone(f'{name} crown', 0.65 * s, 1.9 * s, (x, y, z + 1.75 * s), rng.choice(crowns), segments=16)
        outline(crown, 0.04)

    def lamp(name, x, y):
        kit.cylinder(f'{name} post', 0.05, 1.5, (x, y, CURB + 0.75), paper('#8A7AA0'), segments=8)
        kit.sphere(f'{name} globe', 0.16, (x, y, CURB + 1.55), paper('#FFF4C2', shades=2), segments=12, rings=6)

    # ------------------------------------------------------------------ the eight building blocks
    # Each block: a raised pavement slab, then 1-4 buildings chosen from a few footprints so the
    # skyline varies (tall towers near the middle, low shops at the corners).
    layouts = {
        'quad': [(-2.0, -2.0, 3.4, 3.4), (2.0, -2.0, 3.4, 3.4), (-2.0, 2.0, 3.4, 3.4), (2.0, 2.0, 3.4, 3.4)],
        'pair': [(-1.9, 0.0, 3.6, 7.4), (1.9, 0.0, 3.6, 7.4)],
        'l': [(-1.9, -1.9, 3.6, 3.6), (1.9, 0.0, 3.6, 7.4), (-1.9, 1.9, 3.6, 3.6)],
        'tower': [(0.0, 0.0, 0.0, 0.0)],
        'slab': [(0.0, -1.9, 7.4, 3.6), (-1.9, 1.9, 3.6, 3.6), (1.9, 1.9, 3.6, 3.6)],
    }
    blocks = [(-PITCH, -PITCH, 'quad'), (0, -PITCH, 'slab'), (PITCH, -PITCH, 'pair'),
              (-PITCH, 0, 'pair'), (PITCH, 0, 'tower'),
              (-PITCH, PITCH, 'l'), (0, PITCH, 'tower'), (PITCH, PITCH, 'quad')]
    color_i = 0
    for bi, (bx, by, layout) in enumerate(blocks):
        kit.box(f'Block {bi} pavement', (BLOCK, BLOCK, CURB), (bx, by, CURB / 2), paper(PAVEMENT), bevel=0.08)
        centre_bias = 1.0 - (abs(bx) + abs(by)) / 48       # taller towards the park
        if layout == 'tower':
            building_tower(f'Block {bi} round tower', bx, by, 2.4, 5.6 + 3.0 * centre_bias + rng.uniform(0, 1.2),
                           BUILDINGS[color_i % len(BUILDINGS)])
            color_i += 1
            for k, (tx, ty) in enumerate([(-3.4, -3.4), (3.4, -3.4), (-3.4, 3.4), (3.4, 3.4)]):
                tree(f'Block {bi} tree {k}', bx + tx, by + ty, CURB, 0.8)
        else:
            for k, (ox, oy, w, d) in enumerate(layouts[layout]):
                h = FLOOR * rng.randint(3, 5) + 0.8 + 4.0 * centre_bias * rng.random()
                building_box(f'Block {bi} building {k}', bx + ox, by + oy, w, d, h, BUILDINGS[color_i % len(BUILDINGS)])
                color_i += 1
        lamp(f'Block {bi} lamp', bx + 4.1 * (1 if bx <= 0 else -1), by + 4.1 * (1 if by <= 0 else -1))

    # ------------------------------------------------------------------ the park (centre block)
    kit.box('Park lawn', (BLOCK, BLOCK, CURB), (0, 0, CURB / 2), paper('#BFE6B0'), bevel=0.08)
    path = paper('#F5E6C8')
    for ang in (45, -45):
        kit.box(f'Park path {ang}', (11.6, 0.9, 0.04), (0, 0, CURB + 0.02), path, rotation=(0, 0, ang))
    kit.cylinder('Park plaza', 2.3, 0.06, (0, 0, CURB + 0.03), path, segments=48)
    kit.cylinder('Pond rim', 1.65, 0.28, (0, 0, CURB + 0.14), paper('#E9DCEB'), segments=48, bevel=0.06)
    kit.cylinder('Pond water', 1.45, 0.05, (0, 0, CURB + 0.26), paper('#94CFE6'), segments=48)
    kit.cylinder('Fountain stem', 0.18, 0.9, (0, 0, CURB + 0.7), paper('#E9DCEB'), segments=16)
    kit.cylinder('Fountain bowl', 0.6, 0.15, (0, 0, CURB + 1.15), paper('#E9DCEB'), segments=32, radius_top=0.7)
    spray = kit.sphere('Fountain spray', 0.32, (0, 0, CURB + 1.55), paper('#CDEBF5', shades=2), segments=16, rings=8)
    kit.bob(spray, amplitude=0.08, cycles=6)   # integer cycles: loop-safe
    for k, (tx, ty) in enumerate([(-3.2, 0), (3.2, 0), (0, -3.2), (0, 3.2), (-3.1, -3.3), (3.3, 3.1),
                                  (-3.3, 3.2), (3.2, -3.2)]):
        tree(f'Park tree {k}', tx, ty, CURB, rng.uniform(0.9, 1.15))
    bench = paper('#C99D7F')
    for k, ang in enumerate((0, 90, 180, 270)):
        a = math.radians(ang + 45)
        kit.box(f'Park bench {k}', (1.0, 0.35, 0.3), (2.7 * math.cos(a) + 0.8 * math.sin(a),
                2.7 * math.sin(a) - 0.8 * math.cos(a), CURB + 0.15), bench, rotation=(0, 0, ang + 45), bevel=0.05)
    # Flower dots: small scattered spheres kept off the paths and pond.
    flower_protos = [kit.sphere(f'Flower {c}', 0.09, (0, 0, -50), paper(c, shades=2), segments=8, rings=4)
                     for c in ('#FF9FCB', '#FFE08A', '#FFFFFF')]
    kit.scatter(flower_protos, 60, area=(-4.2, 4.2, -4.2, 4.2), z=CURB + 0.08, scale=(0.8, 1.3),
                avoid=[(0, 0, 2.4)], min_distance=0.25)
    for p in flower_protos:
        p.hide_render = True

    # ------------------------------------------------------------------ cars on closed lanes
    def lane(half, radius, clockwise):
        """Dense polyline of a rounded-rectangle lane, and its cumulative arc length."""
        pts = []
        for corner in range(4):
            cx = (half - radius) * (1 if corner in (0, 1) else -1)
            cy = (half - radius) * (1 if corner in (1, 2) else -1)
            start = -90 + 90 * corner
            for k in range(13):
                a = math.radians(start + 90 * k / 12)
                pts.append(Vector((cx + radius * math.cos(a), cy + radius * math.sin(a), 0)))
        if clockwise:
            pts.reverse()
        pts.append(pts[0].copy())
        acc = [0.0]
        for a, b in zip(pts, pts[1:]):
            acc.append(acc[-1] + (b - a).length)
        return pts, acc

    def along(pts, acc, s):
        """Position and tangent at fraction s (any real) of the closed lane."""
        s = (s % 1.0) * acc[-1]
        for i in range(1, len(acc)):
            if acc[i] >= s:
                seg = acc[i] - acc[i - 1]
                f = (s - acc[i - 1]) / seg if seg else 0
                return pts[i - 1].lerp(pts[i], f), (pts[i] - pts[i - 1]).normalized()
        return pts[-1], (pts[-1] - pts[-2]).normalized()

    tyre = paper('#5B5470', shades=2)
    glass = paper('#D8ECF7', shades=2)

    def car(name, color):
        """A rounded toy car under an empty: body, cabin, four wheels, two headlights."""
        root = kit.empty(name, (0, 0, 0), size=0.6)
        parts = [kit.box(f'{name} body', (2.0, 0.95, 0.5), (0, 0, 0.42), paper(color), bevel=0.18),
                 kit.box(f'{name} cabin', (1.05, 0.82, 0.42), (-0.12, 0, 0.84), glass, bevel=0.14),
                 kit.box(f'{name} roof', (0.95, 0.86, 0.08), (-0.12, 0, 1.06), paper(color), bevel=0.04)]
        for sx in (-0.62, 0.62):
            for sy in (-0.47, 0.47):
                parts.append(kit.cylinder(f'{name} wheel', 0.2, 0.16, (sx, sy, 0.2), tyre,
                                          rotation=(90, 0, 0), segments=16))
        for sy in (-0.28, 0.28):
            parts.append(kit.sphere(f'{name} headlight', 0.07, (1.0, sy, 0.5), paper('#FFF6C9', shades=2),
                                    segments=8, rings=4))
        parts[0].modifiers['Bevel'].segments = 4
        outline(parts[0], 0.04)
        for p in parts:
            p.parent = root
        return root

    def drive(root, pts, acc, phase, laps=1):
        """Key location and heading every frame. Heading is unwrapped (it keeps increasing through
        corners) so the last key is exactly one full turn after the first: a seamless loop."""
        state = {'prev': None, 'yaw': 0.0}

        def at_loc(t):
            p, _ = along(pts, acc, phase + laps * t)
            return (p.x, p.y, 0.0)

        def at_rot(t):
            _, tan = along(pts, acc, phase + laps * t)
            yaw = math.atan2(tan.y, tan.x)
            if state['prev'] is not None:
                d = (yaw - state['prev'] + math.pi) % (2 * math.pi) - math.pi
                state['yaw'] += d
            else:
                state['yaw'] = yaw
            state['prev'] = yaw
            return (0.0, 0.0, state['yaw'])
        kit.animate(root, 'location', at_loc)
        kit.animate(root, 'rotation_euler', at_rot)

    lanes = [
        (lane(6.7, 1.6, clockwise=False), 2),     # around the park, inner lane
        (lane(5.35, 1.0, clockwise=True), 1),     # around the park, the other direction
        (lane(18.7, 1.8, clockwise=True), 3),     # ring road, outer lane
        (lane(17.3, 1.6, clockwise=False), 2),    # ring road, inner lane
    ]
    ci = 0
    for li, ((pts, acc), count) in enumerate(lanes):
        for k in range(count):
            root = car(f'Car {li}-{k}', CARS[ci % len(CARS)])
            ci += 1
            drive(root, pts, acc, phase=k / count + 0.13 * li)

    # ------------------------------------------------------------------ orthographic turntable
    # True isometric: elevation atan(1/sqrt(2)) = 35.26 degrees. Starting at 45 degrees gives the
    # classic diamond on frame 1; sweep=360 with linear ease makes frame frames+1 equal frame 1.
    radius = 90.0
    height = radius * math.tan(math.radians(35.264))
    cam = kit.camera((0, -radius, height), target=(0, 0, 1.5), ortho_scale=50.0, clip=(1.0, 400.0))
    kit.orbit(cam, center=(0, 0, 0), radius=radius, height=height, start=45.0, sweep=360.0,
              target_height=2.2)
