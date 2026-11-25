"""Headphones, exploded view: over-ear headphones separate along their axes, hold, and reassemble.

Teaches:
- modelling a product at real size (metres: the cups are 11 cm tall) and lighting it to match;
- building a part library from a few shape recipes: lathe profiles (cup shell, driver), an
  oval torus (cushions), a swept rounded-rectangle band (headband) and a tube fork (yoke);
- an exploded view as data: every part has an assembled place and an explode offset, and one
  staggered easing curve drives them all, so the loop closes because the curve starts and ends
  at zero;
- a high-key white cyclorama: a curved floor-to-wall sweep lit by its own backdrop light (not
  self-lit), big soft area lights, black flags for negative fill, and AgX pulled slightly under
  so the background sits near white while the dark shells keep their shape;
- a two-tone palette (dark slate shells, camel leather) so every part reads against white;
- thin technical axis lines that grow with the explosion, the cue that reads as "exploded view".
"""
import math

# ----------------------------------------------------------------------------- dimensions (metres)
CUP_X = 0.080          # x of the open rim of the right ear-cup shell (left side mirrors)
CUP_DEPTH = 0.042      # shell depth along x
CUP_R = 0.046          # shell rim radius before the oval stretch
OVAL = 1.2             # cups and cushions are 20% taller than wide
BAND_A = 0.100         # headband half-span (x) where it meets the sliders
BAND_B = 0.105         # headband rise above its ends
BAND_Z = 0.095         # height of the headband ends
FLOOR_Z = -0.0548     # the cups rest on the floor (subdivision pulls the shell in slightly)

# ----------------------------------------------------------------------------- motion (shot progress)
HOLD_IN = 0.10         # assembled at the start
APART = 0.40           # fully exploded by here
HOLD_OUT = 0.62        # starts closing here
CLOSED = 0.92          # assembled again; holds to the loop point
STAGGER = 0.025        # outer parts lead, inner parts follow

# ----------------------------------------------------------------------------- palette
SHELL = '#222B38'      # deep slate-blue matte plastic: dark enough to hold against white
LEATHER = '#A88F6E'    # camel protein leather: the light second tone of a two-tone product
ACCENT = '#E2682C'     # one warm accent ties the two tones together
WHITE = '#F3F3F1'


def build(kit):
    import bmesh
    import bpy
    from mathutils import Vector

    # ------------------------------------------------------------------ materials
    # Matte plastics are about roughness, not colour: a fine bead-blast bump at millimetre scale
    # breaks up highlights the way real moulded parts do.
    plastic = kit.material('Graphite matte plastic', SHELL, roughness=0.58, specular=0.45, bump=(900, 0.04))
    plastic_light = kit.material('Light grey plastic', '#B9BCC2', roughness=0.5, bump=(900, 0.03))
    leather = kit.material('Protein leather', LEATHER, roughness=0.42, sheen=0.25, coat=0.08, bump=(260, 0.08))
    foam_fabric = kit.procedural('Acoustic fabric', 'fabric', colors=['#8E8271', '#9C907E', '#A99D8A'], scale=22)
    aluminium = kit.procedural('Anodised aluminium', 'brushed_metal', colors=['#A9ADB3', '#C3C6CB', '#D7D9DD'],
                               scale=60, roughness=0.32)
    copper = kit.material('Driver copper', '#C98250', roughness=0.28, metallic=1.0)
    cone_mat = kit.material('Diaphragm', '#1E1F22', roughness=0.3, coat=0.6)
    accent = kit.material('Accent ring', ACCENT, roughness=0.5, bump=(900, 0.03))
    axis_mat = kit.material('Axis line', '#7F8794', roughness=0.8)

    # ------------------------------------------------------------------ shape recipes
    def oval_lathe(name, profile, mat, x, side, segments=72, facing=None):
        """Revolve a (radius, depth) profile, turn its axis to +-X and stretch it into an oval.

        Lathe revolves around Z; rotating 90 degrees about Y points that axis along X. The oval
        stretch goes on local X, which becomes world Z after the rotation."""
        obj = kit.lathe(name, profile, segments=segments, material=mat)
        facing = side if facing is None else facing
        obj.rotation_euler = (0, math.radians(90 if facing > 0 else -90), 0)
        obj.scale = (OVAL, 1, 1)
        obj.location = (side * x, 0, 0)
        return obj

    def oval_torus(name, radius, thickness, mat, x, side, flat=1.0):
        obj = kit.torus(name, radius, thickness, material=mat, segments=72, sides=20)
        obj.rotation_euler = (0, math.radians(90), 0)
        obj.scale = (OVAL, 1, flat)
        obj.location = (side * x, 0, 0)
        return obj

    def sweep(name, points, width, thickness, mat, round_k=0.45):
        """Sweep a rounded-rectangle section along a curve in the XZ plane (bands, pads).

        The section's width runs along Y and its thickness along the curve's in-plane normal."""
        sec = []
        n = 6
        hw, ht = width / 2, thickness / 2
        r = min(hw, ht) * round_k * 2
        for cx, cy, a0 in ((hw - r, ht - r, 0), (-hw + r, ht - r, 90), (-hw + r, -ht + r, 180), (hw - r, -ht + r, 270)):
            for k in range(n + 1):
                a = math.radians(a0 + 90 * k / n)
                sec.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        verts, faces = [], []
        m = len(sec)
        for i, p in enumerate(points):
            p = Vector(p)
            q0 = Vector(points[max(0, i - 1)])
            q1 = Vector(points[min(len(points) - 1, i + 1)])
            tan = (q1 - q0).normalized()
            nrm = tan.cross(Vector((0, 1, 0))).normalized()
            verts += [tuple(p + Vector((0, 1, 0)) * u + nrm * v) for u, v in sec]
        for i in range(len(points) - 1):
            for k in range(m):
                faces.append((i * m + k, i * m + (k + 1) % m, (i + 1) * m + (k + 1) % m, (i + 1) * m + k))
        faces.append(tuple(reversed(range(m))))
        faces.append(tuple(range((len(points) - 1) * m, len(points) * m)))
        obj = kit.mesh(name, verts, faces, mat, smooth=True)
        # Make the normals consistent whatever the curve direction (bmesh is allowed in scripts).
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(obj.data)
        bm.free()
        return obj

    def attach(child, parent):
        """Parent keeping the child's world placement. New objects have a stale matrix_world until
        the view layer updates, so update first (kit.parent alone would snap them to the origin)."""
        bpy.context.view_layer.update()
        return kit.parent(child, parent)

    parts = []   # (object, explode offset Vector, order 0 = leads)

    def part(obj, offset, order):
        parts.append((obj, Vector(offset), order))
        return obj

    # ------------------------------------------------------------------ the two ear-cup stacks
    for side in (1, -1):
        tag = 'R' if side > 0 else 'L'
        # Cup shell: a thick moulded cup, open toward the head, with a rolled outer edge.
        shell_profile = [(0.0, 0.036), (0.030, 0.035), (0.040, 0.030), (0.0425, 0.010), (0.0425, 0.0),
                         (CUP_R, 0.0), (CUP_R + 0.0005, 0.012), (CUP_R - 0.001, 0.028),
                         (0.041, 0.038), (0.032, 0.0415), (0.0, CUP_DEPTH)]
        shell = oval_lathe(f'{tag} ear-cup shell', shell_profile, plastic, CUP_X, side)
        kit.subdivide(shell, 1)
        part(shell, (side * 0.068, 0, 0), 1)

        # Outer cap: an accent ring and a recessed light disc on the back of the shell.
        cap = oval_torus(f'{tag} accent ring', 0.030, 0.0022, accent, CUP_X + CUP_DEPTH + 0.0005, side)
        part(cap, (side * 0.106, 0, 0), 0)
        badge = oval_lathe(f'{tag} cap badge', [(0, 0.003), (0.024, 0.0028), (0.0275, 0.0012), (0.0275, 0)],
                           plastic_light, CUP_X + CUP_DEPTH - 0.001, side, segments=64)
        part(badge, (side * 0.106, 0, 0), 0)

        # Baffle: the plate that carries the driver, with a ring of vent holes (dark dots).
        baffle = oval_lathe(f'{tag} baffle plate', [(0, 0.0), (0.040, 0.0), (0.041, 0.0015), (0.040, 0.003), (0, 0.003)],
                            plastic, CUP_X - 0.002, side)
        part(baffle, (side * 0.046, 0, 0), 3)
        vents = []
        for k in range(18):
            a = 2 * math.pi * k / 18
            v = kit.cylinder(f'{tag} vent {k}', 0.0018, 0.004, (side * (CUP_X - 0.0025), 0.034 * math.cos(a),
                             0.034 * OVAL * math.sin(a)), cone_mat, rotation=(0, 90, 0), segments=12)
            attach(v, baffle)

        # Driver: copper frame, glossy cone with a dust cap, magnet pot behind.
        driver = oval_lathe(f'{tag} driver frame', [(0.020, 0.0), (0.0235, 0.0), (0.0235, 0.0025), (0.020, 0.0025)],
                            copper, CUP_X - 0.006, side, segments=64, facing=-side)
        driver.scale = (1, 1, 1)
        cone = kit.lathe(f'{tag} diaphragm', [(0.0, 0.0045), (0.007, 0.0040), (0.0085, 0.0032), (0.020, 0.0008),
                                              (0.0205, 0.0)], segments=64, material=cone_mat)
        cone.rotation_euler = (0, math.radians(-90 * side), 0)
        cone.location = (side * (CUP_X - 0.006), 0, 0)
        magnet = kit.cylinder(f'{tag} magnet pot', 0.011, 0.008, (side * (CUP_X - 0.002), 0, 0), aluminium,
                              rotation=(0, 90, 0), segments=40, bevel=0.0008)
        for child in (cone, magnet):
            attach(child, driver)
        part(driver, (side * 0.020, 0, 0), 4)

        # Acoustic scrim and the cushion: inner-most, they move toward the head when exploded.
        scrim = oval_lathe(f'{tag} acoustic scrim', [(0, 0.0), (0.033, 0.0), (0.033, 0.001), (0, 0.001)],
                           foam_fabric, CUP_X - 0.009, side, facing=-side)
        part(scrim, (side * -0.006, 0, 0), 5)
        cushion = oval_torus(f'{tag} ear cushion', 0.0335, 0.0112, leather, CUP_X - 0.020, side, flat=1.0)
        kit.subdivide(cushion, 1)
        part(cushion, (side * -0.028, 0, 0), 6)

        # Yoke: a fork that hugs the cup and pivots at its sides.
        yoke_pts = [(side * 0.101, 0.053 * math.cos(math.pi * k / 16), 0.064 * math.sin(math.pi * k / 16))
                    for k in range(17)]
        yoke = kit.tube(f'{tag} yoke', yoke_pts, radius=0.0034, material=plastic_light, resolution=16)
        for sy in (-1, 1):
            pivot = kit.cylinder(f'{tag} yoke pivot', 0.0052, 0.006, (side * 0.101, sy * 0.050, 0), aluminium,
                                 rotation=(90, 0, 0), segments=24, bevel=0.0006)
            attach(pivot, yoke)
        hinge = kit.box(f'{tag} hinge block', (0.010, 0.012, 0.010), (side * 0.101, 0, 0.068), plastic_light, bevel=0.002)
        attach(hinge, yoke)
        part(yoke, (side * 0.068, 0, 0.026), 2)

        # Slider: a brushed aluminium bar that telescopes into the headband end, with a stop.
        slider = kit.box(f'{tag} slider', (0.0032, 0.013, 0.058), (side * 0.101, 0, 0.100), aluminium, bevel=0.0012)
        stop = kit.box(f'{tag} slider stop', (0.0046, 0.0145, 0.004), (side * 0.101, 0, 0.073), accent, bevel=0.001)
        attach(stop, slider)
        part(slider, (side * 0.068, 0, 0.056), 2)

    # ------------------------------------------------------------------ headband and its pad
    arc = [(BAND_A * math.cos(math.pi * k / 48), 0, BAND_Z + BAND_B * math.sin(math.pi * k / 48)) for k in range(49)]
    band = sweep('Headband', arc, 0.034, 0.0075, plastic)
    kit.subdivide(band, 1)
    part(band, (0, 0, 0.094), 0)
    pad_arc = [((BAND_A - 0.010) * math.cos(a), 0, BAND_Z + (BAND_B - 0.010) * math.sin(a))
               for a in (math.pi * (0.22 + 0.56 * k / 32) for k in range(33))]
    pad = sweep('Headband pad', pad_arc, 0.027, 0.011, leather, round_k=0.5)
    kit.subdivide(pad, 1)
    part(pad, (0, 0, 0.046), 1)
    # Stitching seam along the pad: a fine tube just proud of the leather.
    seam = kit.tube('Pad seam', [((BAND_A - 0.0158) * math.cos(a), 0.0, BAND_Z + (BAND_B - 0.0158) * math.sin(a))
                                 for a in (math.pi * (0.24 + 0.52 * k / 24) for k in range(25))],
                    radius=0.0006, material=plastic_light)
    attach(seam, pad)

    # ------------------------------------------------------------------ the explode curve
    def amount(t, order):
        """0 assembled .. 1 exploded. Outer parts lead on the way out and trail on the way in, so
        the stack opens and closes like a sequence rather than a single pop."""
        lead = order * STAGGER
        if t < HOLD_OUT:
            return kit.ease(kit.segment(t, HOLD_IN + lead, APART + lead * 0.5), 'in_out', 3.0)
        return 1.0 - kit.ease(kit.segment(t, HOLD_OUT + (6 - order) * STAGGER * 0.5,
                                          CLOSED - order * STAGGER * 0.4), 'in_out', 3.0)

    for obj, offset, order in parts:
        home = Vector(obj.location)
        kit.animate(obj, 'location', lambda t, h=home, o=offset, r=order: h + o * amount(t, r))

    # Technical axis lines: dashed rods along each cup axis and the headband's vertical, grown
    # from the assembly with the same curve (scale 0 when assembled, so they vanish at the loop).
    def dashed(name, start, end, dash=0.006, gap=0.004, radius=0.00045):
        start, end = Vector(start), Vector(end)
        length = (end - start).length
        direction = (end - start).normalized()
        root = kit.empty(name, tuple(start), size=0.01)
        s = 0.0
        while s < length:
            seg = min(dash, length - s)
            mid = direction * (s + seg / 2)
            rod = kit.cylinder(f'{name} dash', radius, seg, tuple(start + mid), axis_mat, segments=6, smooth=False)
            rod.rotation_euler = direction.to_track_quat('Z', 'Y').to_euler()
            attach(rod, root)
            s += dash + gap
        return root

    for side in (1, -1):
        line = dashed(f'{"R" if side > 0 else "L"} cup axis', (side * 0.030, 0, 0), (side * 0.245, 0, 0))
        kit.animate(line, 'scale', lambda t: [max(1e-4, amount(t, 3))] * 3)
    vline = dashed('Headband axis', (0, 0, BAND_Z + BAND_B + 0.006), (0, 0, BAND_Z + BAND_B + 0.115))
    kit.animate(vline, 'scale', lambda t: [max(1e-4, amount(t, 0))] * 3)

    # ------------------------------------------------------------------ white cyclorama
    # Floor that bends into a back wall with a 35 cm radius: no horizon line, soft gradient.
    verts, faces = [], []
    width, depth_front, wall_y, bend_r, wall_h = 4.0, 1.6, 0.55, 0.35, 1.6
    profile = [(-depth_front, FLOOR_Z)]
    for k in range(1, 13):
        a = math.radians(90 * k / 12)
        profile.append((wall_y - bend_r + bend_r * math.sin(a), FLOOR_Z + bend_r - bend_r * math.cos(a)))
    profile.append((wall_y, FLOOR_Z + wall_h))
    for y, z in profile:
        verts += [(-width / 2, y, z), (width / 2, y, z)]
    for i in range(len(profile) - 1):
        faces.append((2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2))
    # The sweep is lit, not glowing: a self-lit backdrop bathes rough plastics in white
    # reflections and washes every dark part to grey.
    kit.mesh('White cyclorama', verts, faces, kit.material('Cyclorama white', WHITE, roughness=0.95),
             smooth=True, ground=True)

    # ------------------------------------------------------------------ high-key studio light
    # A dim world (the studio is not a white sphere), one big key softbox, a top strip for the
    # headband highlight, a rim strip to separate the dark shells from the backdrop, and a
    # dedicated backdrop light that pushes the sweep to near white behind the product.
    kit.world('#F4F4F2', strength=0.08)
    kit.area('Key softbox', (-0.55, -0.75, 0.85), (0, 0, 0.05), power=55, color='#FFF9F2', size=0.9, size_y=0.6)
    kit.area('Fill card', (0.95, -0.45, 0.25), (0, 0, 0.04), power=14, color='#F2F6FF', size=1.0)
    kit.area('Top strip', (0.0, 0.2, 1.0), (0, 0, 0.1), power=35, color='#FFFFFF', size=1.4, size_y=0.25)
    kit.area('Rim strip', (0.6, 0.55, 0.3), (0, 0, 0.08), power=45, color='#FFFFFF', size=0.25, size_y=0.9)
    kit.area('Backdrop light', (0.0, -0.2, 1.2), (0.0, 0.6, 0.35), power=35, color='#FFFFFF', size=2.4, size_y=0.8)
    # Negative fill: black flags just out of frame give the matte shells a dark edge to read
    # against the white sweep, the way a product photographer flags a set.
    flag = kit.material('Black flag', '#050505', roughness=1.0)
    # Each flag sits well outside the lens's 30-degree view cone (check the angles board).
    kit.plane('Black flag R', (0.5, 0.6), (0.75, 0.05, 0.25), flag, rotation=(90, 0, 90))
    kit.plane('Black flag L', (0.5, 0.6), (-0.95, -0.55, 0.25), flag, rotation=(90, 0, 70))
    kit.render(exposure=-0.3, look='AgX - Medium High Contrast')

    # ------------------------------------------------------------------ locked three-quarter camera
    cam = kit.camera((0.66, -1.05, 0.44), target=(0.0, 0.0, 0.116), lens=67, dof=1.25, fstop=11)
