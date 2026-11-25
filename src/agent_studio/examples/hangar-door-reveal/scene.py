"""Hangar door reveal: giant doors slide open, daylight floods through haze, a mech steps forward.

Teaches:
- staging a silhouette: expose for the bright exterior, keep the interior near black, and put
  the subject between the camera and a low sun so it reads only as shape and rim;
- telescoping sliding doors: three leaves per side on separate tracks, each travelling a
  different distance with one shared easing curve, stacking into pockets behind the wall piers;
- volumetric light: a noise-modulated interior haze (density from a 3D noise texture) turns the
  sun beam into drifting dusty shafts, plus a few hundred lit dust motes keyed on slow paths;
- building at real scale (a 48 m door, a 24 m mech, 1.8 m people) and adding secondary detail
  at three scales: roof trusses and columns, door girts and floor markings, corrugation and
  roughness variation;
- a locked wide camera with a slight push, eased so it starts and settles gently.
"""
import math

# ----------------------------------------------------------------------------- dimensions (metres)
DOOR_W = 48.0          # clear opening
DOOR_H = 26.0
HALL_W = 72.0          # interior width (x)
HALL_D = 64.0          # interior depth (y, from the door wall at y=0 back to y=-HALL_D)
EAVES = 33.0           # underside of the roof
LEAVES = 3             # door leaves per side
LEAF_W = DOOR_W / 2 / LEAVES + 0.3   # a little overlap between neighbouring leaves
MECH_Y = 15.0          # the mech starts just outside the door
MECH_SCALE = 1.0       # the mech is ~24 m to the antenna tips at 1.0

# ----------------------------------------------------------------------------- timing (shot progress)
OPEN_START, OPEN_END = 0.06, 0.78
EYES_ON = (0.66, 0.76)

# ----------------------------------------------------------------------------- palette
STEEL = '#2B2F2E'
DOOR_PAINT = '#3A403B'
MECH_ARMOR = '#25272A'
SAFETY = '#C9A227'


def build(kit):
    import bpy
    from mathutils import Vector

    rng = kit.rng

    # ------------------------------------------------------------------ helpers
    def strut(name, a, b, w, h, mat):
        """A box beam between two points: the workhorse of trusses, braces and frames."""
        a, b = Vector(a), Vector(b)
        d = b - a
        obj = kit.box(name, (w, h, d.length), tuple((a + b) / 2), mat)
        obj.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
        return obj

    def i_beam(name, x, y, height, mat, depth=0.9, flange=0.5):
        """A wide-flange column: two flanges and a web read as structural steel, not a box."""
        web = kit.box(name, (0.08, depth, height), (x, y, height / 2), mat)
        for s in (-1, 1):
            kit.box(f'{name} flange', (flange, 0.06, height), (x, y + s * depth / 2, height / 2), mat)
        kit.box(f'{name} base plate', (1.2, 1.4, 0.06), (x, y, 0.03), mat)
        return web

    # ------------------------------------------------------------------ materials
    steel = kit.material('Painted structural steel', STEEL, roughness=0.55, metallic=0.3, bump=(40, 0.15))
    door_paint = kit.material('Door paint', DOOR_PAINT, roughness=0.5, metallic=0.4, bump=(25, 0.2))
    wall = kit.procedural('Hangar wall cladding', 'concrete', colors=['#262826', '#2E302E', '#373936'],
                          scale=0.4, roughness=0.8, bump=0.1)

    # Concrete floor with a sealed sheen that varies in patches: the bright doorway smears into
    # long reflections where it is smooth, which sells the floor's scale.
    floor = kit.procedural('Hangar floor', 'concrete', colors=['#3A3B39', '#4A4B48', '#5A5A56'], scale=0.25,
                           bump=0.05)
    nt = floor.node_tree
    bs = kit.bsdf(floor)
    patch = nt.nodes.new('ShaderNodeTexNoise')
    patch.inputs['Scale'].default_value = 0.08
    patch.inputs['Detail'].default_value = 6.0
    coord = nt.nodes.new('ShaderNodeTexCoord')
    nt.links.new(coord.outputs['Object'], patch.inputs['Vector'])
    sheen = nt.nodes.new('ShaderNodeMapRange')
    sheen.inputs['From Min'].default_value = 0.4
    sheen.inputs['From Max'].default_value = 0.65
    sheen.inputs['To Min'].default_value = 0.12
    sheen.inputs['To Max'].default_value = 0.62
    nt.links.new(patch.outputs['Fac'], sheen.inputs['Value'])
    nt.links.new(sheen.outputs['Result'], bs.inputs['Roughness'])
    paint_line = kit.material('Floor safety paint', SAFETY, roughness=0.45)
    mech_armor = kit.material('Mech armour', MECH_ARMOR, roughness=0.42, metallic=0.6, bump=(6, 0.2))
    mech_joint = kit.material('Mech joints', '#141516', roughness=0.35, metallic=0.9)
    eye = kit.emissive('Mech eye glow', '#FF6A2A', strength=0.0)
    lamp_glow = kit.emissive('High-bay lamp', '#FFE3B5', strength=6.0)
    apron = kit.procedural('Apron concrete', 'concrete', colors=['#6D6C67', '#7E7C76', '#8E8C85'], scale=0.12,
                           bump=0.05)

    # ------------------------------------------------------------------ hangar shell
    kit.plane('Hangar floor', (HALL_W, HALL_D), (0, -HALL_D / 2, 0), floor)
    kit.ground(apron, size=600, z=-0.02, name='Apron')
    for s in (-1, 1):
        kit.box('Side wall', (0.6, HALL_D, EAVES + 2), (s * HALL_W / 2, -HALL_D / 2, (EAVES + 2) / 2), wall)
        # Door-wall piers either side of the opening: the leaves stack behind these.
        pier_w = (HALL_W - DOOR_W) / 2
        kit.box('Door pier', (pier_w, 0.8, EAVES + 2), (s * (DOOR_W / 2 + pier_w / 2), 0.4, (EAVES + 2) / 2), wall)
    kit.box('Back wall', (HALL_W, 0.6, EAVES + 2), (0, -HALL_D, (EAVES + 2) / 2), wall)
    kit.box('Door header', (DOOR_W + 1, 0.8, EAVES + 2 - DOOR_H), (0, 0.4, DOOR_H + (EAVES + 2 - DOOR_H) / 2), wall)
    kit.box('Roof deck', (HALL_W + 1, HALL_D + 1, 0.5), (0, -HALL_D / 2, EAVES + 2.25), wall)
    # Header girder across the opening: a deep truss that the door leaves hang from.
    kit.box('Door head girder', (DOOR_W + 6, 1.2, 2.2), (0, -0.3, DOOR_H + 1.1), steel, bevel=0.05)

    # Columns along the side walls every bay.
    bay = 8.0
    ys = [-4.0 - bay * k for k in range(int(HALL_D / bay))]
    for y in ys:
        for s in (-1, 1):
            i_beam('Wall column', s * (HALL_W / 2 - 0.8), y, EAVES, steel)

    # Roof trusses: a pitched top chord, a flat bottom chord and alternating diagonals. Seen from
    # below against the lit haze they make the strongest interior silhouette.
    for y in ys:
        n = 12
        span = HALL_W - 2
        bottom = [(-span / 2 + span * k / n, y, EAVES - 4.0) for k in range(n + 1)]
        top = [(x, y, EAVES - 0.4 + 1.2 * (1 - abs(x) / (span / 2))) for x, _, _ in bottom]
        strut('Truss bottom chord', bottom[0], bottom[-1], 0.35, 0.35, steel)
        strut('Truss top chord L', top[0], top[n // 2], 0.4, 0.4, steel)
        strut('Truss top chord R', top[n // 2], top[-1], 0.4, 0.4, steel)
        for k in range(n + 1):
            strut('Truss post', bottom[k], top[k], 0.18, 0.18, steel)
            if k < n:
                a, b = (bottom[k], top[k + 1]) if k < n // 2 else (top[k], bottom[k + 1])
                strut('Truss diagonal', a, b, 0.16, 0.16, steel)
    # Purlins tie the trusses together along the length.
    for x in (-24, -12, 0, 12, 24):
        strut('Purlin', (x, ys[0], EAVES + 0.4), (x, ys[-1], EAVES + 0.4), 0.25, 0.3, steel)

    # High-bay lamps: dim warm pools that show the interior exists before the doors open.
    for y in ys[1::2]:
        for x in (-16, 16):
            kit.cylinder('High-bay housing', 0.45, 0.5, (x, y, EAVES - 5.0), steel, segments=24)
            kit.cylinder('High-bay lens', 0.4, 0.04, (x, y, EAVES - 5.27), lamp_glow, segments=24)
            kit.spot('High-bay light', (x, y, EAVES - 5.4), (x, y, 0), power=2200, color='#FFD8A0', angle=70,
                     blend=0.6, radius=0.3)

    # Floor markings: taxi centre line and bay boxes, a mid-scale rhythm leading to the door.
    for k in range(14):
        kit.box('Centre line dash', (0.25, 2.2, 0.01), (0, -2.5 - k * 4.4, 0.005), paint_line)
    for s in (-1, 1):
        kit.box('Bay edge line', (0.2, HALL_D - 4, 0.01), (s * 22, -HALL_D / 2 - 1, 0.005), paint_line)
        kit.box('Door threshold stripe', (DOOR_W / 2 - 0.5, 0.35, 0.01), (s * DOOR_W / 4, -1.2, 0.005), paint_line)

    # Clutter at human scale: crates, drums, a scaffold tower and two technicians.
    crate = kit.material('Crate plywood', '#6B5A40', roughness=0.8, bump=(8, 0.2))
    drum = kit.material('Drum paint', '#5B2A22', roughness=0.5, metallic=0.5)
    for k in range(9):
        x = -30 + rng.uniform(-2.5, 2.5)
        y = -10 - k * 3.6 + rng.uniform(-0.8, 0.8)
        h = rng.choice((1.2, 1.6, 2.0))
        kit.box(f'Crate {k}', (rng.uniform(1.6, 2.6), rng.uniform(1.4, 2.2), h), (x, y, h / 2), crate, bevel=0.04,
                rotation=(0, 0, rng.uniform(-8, 8)))
    for k in range(12):
        x = 27 + rng.uniform(-3, 3)
        y = -9 - rng.uniform(0, 20)
        kit.cylinder(f'Drum {k}', 0.3, 0.9, (x, y, 0.45), drum, segments=24, bevel=0.02)
    for lx in (25.0, 29.0):
        for ly in (-26.0, -30.0):
            strut('Scaffold leg', (lx, ly, 0), (lx, ly, 12), 0.08, 0.08, steel)
    for z in (3, 6, 9, 12):
        kit.box('Scaffold deck', (4.6, 4.6, 0.08), (27, -28, z), steel)
    tech = kit.material('Coverall', '#1E2226', roughness=0.8)
    for k, (x, y) in enumerate(((-4.0, -9.0), (-2.6, -10.5))):
        J = kit.figure(f'Technician {k}', height=1.78, location=(x, y, 0), material=tech, facing=180)
        kit.idle(J, cycles=1, breathe=0.01, sway=1.5)

    # ------------------------------------------------------------------ sliding door leaves
    def corrugated_leaf(name):
        """A door leaf: corrugated skin (a sine-profile mesh) with girts and stiles on the inner face."""
        pitch, amp = 0.25, 0.05
        steps = int(LEAF_W / pitch * 4)
        verts, faces = [], []
        for i in range(steps + 1):
            x = -LEAF_W / 2 + LEAF_W * i / steps
            yy = amp * math.sin(2 * math.pi * x / pitch)
            verts += [(x, yy, 0.0), (x, yy, DOOR_H + 0.6)]
        for i in range(steps):
            faces.append((2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1))
        skin = kit.mesh(name, verts, faces, door_paint)
        kit.solidify(skin, 0.02)
        for z in (0.4, 6.5, 13.0, 19.5, DOOR_H + 0.2):
            g = kit.box(f'{name} girt', (LEAF_W, 0.3, 0.35), (0, -0.25, z), door_paint)
            g.parent = skin
        for sx in (-1, 1):
            st = kit.box(f'{name} stile', (0.35, 0.4, DOOR_H + 0.6), (sx * (LEAF_W / 2 - 0.18), -0.25,
                                                                       (DOOR_H + 0.6) / 2), door_paint)
            st.parent = skin
        for sx in (-1, 1):
            w = kit.cylinder(f'{name} bottom wheel', 0.35, 0.3, (sx * (LEAF_W / 2 - 1.2), 0, 0.35), steel,
                             rotation=(0, 90, 0), segments=20)
            w.parent = skin
        return skin

    pocket_x = DOOR_W / 2 + (HALL_W - DOOR_W) / 4    # where the leaves stack when open
    for s in (-1, 1):
        for k in range(LEAVES):
            # k = 0 is the leaf at the centre of the opening; it travels furthest and runs on the
            # outermost track so it can pass the others.
            closed_x = s * (LEAF_W / 2 + 0.08 + k * (LEAF_W - 0.3))
            open_x = s * (pocket_x + 0.2 * k)
            track_y = 1.2 + 0.8 * (LEAVES - 1 - k)
            leaf = corrugated_leaf(f'Door leaf {"L" if s < 0 else "R"}{k}')
            leaf.location = (closed_x, track_y, 0.0)
            kit.animate(leaf, 'location', lambda t, a=closed_x, b=open_x, y=track_y: Vector((
                kit.lerp(a, b, kit.ease(kit.segment(t, OPEN_START, OPEN_END), 'in_out', 2.2)), y, 0.0)), step=2,
                interpolation='BEZIER')
        kit.box('Door track', (HALL_W / 2 + 2, 3.0, 0.15), (s * HALL_W / 4, 2.2, 0.075), steel)
    # A tiny gap between the two centre leaves lets one blade of daylight in at frame 1.

    # ------------------------------------------------------------------ the mech
    def build_mech():
        s = MECH_SCALE
        root = kit.empty('Mech', (0, 0, 0), size=2)
        body = kit.empty('Mech moving body', size=1)
        body.parent = root
        parts = []

        def add(obj):
            parts.append(obj)
            return obj

        def box(name, size, loc, mat=mech_armor, rot=(0, 0, 0), bevel=0.08):
            return add(kit.box(name, tuple(v * s for v in size), tuple(v * s for v in loc), mat, rotation=rot,
                               bevel=bevel))

        def limb(name, a, b, r, mat=mech_armor):
            a = Vector(a) * s
            b = Vector(b) * s
            return add(strut(name, a, b, r * 2 * s, r * 1.6 * s, mat))

        def bind_leg_group(name, anchor, start):
            pivot = kit.empty(name, anchor, size=0.6)
            pivot.parent = root
            for child in parts[start:]:
                child.parent = pivot
                child.location -= anchor
            del parts[start:]
            return pivot

        def body_pose(t):
            progress = kit.ease(kit.segment(t, 0.48, 0.96), 'smooth')
            return Vector((0, -2.95 * s * progress, 0.16 * s * math.sin(math.tau * progress) ** 2))

        for side, swing, reach in ((-1, (0.48, 0.73), 3.8), (1, (0.72, 0.96), 3.3)):
            x = side * 3.4
            ankle, heel, hip = (Vector(p) * s for p in ((x, 0, 1.6), (x * 1.08, 3.4, 8), (x * 0.85, -0.2, 13)))
            start = len(parts)
            box('Mech foot', (2.6, 4.2, 1.0), (x, -0.6, 0.5))
            box('Mech toe', (2.2, 1.6, 0.7), (x, -3.0, 0.35), rot=(-12, 0, 0))
            box('Mech heel spur', (1.2, 1.8, 0.8), (x, 1.9, 0.6), rot=(20, 0, 0))
            add(kit.sphere('Mech ankle hinge', 1.15 * s, ankle, mech_joint, segments=24, rings=12))
            foot = bind_leg_group(f'Mech foot pivot {side}', ankle, start)

            limb('Mech shin', ankle / s, heel / s, 0.9)
            limb('Mech shin ram', ankle / s + Vector((side * 0.9, 0.4, 1)),
                 heel / s + Vector((side * 0.9, -0.6, -0.8)), 0.22, mech_joint)
            add(kit.sphere('Mech heel hinge', 1.15 * s, heel, mech_joint, segments=24, rings=12))
            shin = bind_leg_group(f'Mech shin pivot {side}', heel, start)

            limb('Mech thigh', heel / s, hip / s, 1.25)
            limb('Mech thigh ram', heel / s + Vector((side * 0.8, -0.8, 0.8)),
                 hip / s + Vector((side * 1.1, 0.8, -1.2)), 0.3, mech_joint)
            add(kit.sphere('Mech hip hinge', 1.15 * s, hip, mech_joint, segments=24, rings=12))
            thigh = bind_leg_group(f'Mech thigh pivot {side}', hip, start)
            shin.rotation_mode = thigh.rotation_mode = 'QUATERNION'

            rest_upper, rest_lower = heel - hip, ankle - heel
            upper, lower = rest_upper.length, rest_lower.length

            def pose(t):
                progress = kit.ease(kit.segment(t, *swing), 'smooth')
                toe = ankle + Vector((0, -reach * s * progress, 1.45 * s * math.sin(math.pi * progress)))
                pivot = hip + body_pose(t)
                axis = toe - pivot
                span = min(axis.length, upper + lower)
                direction = axis.normalized()
                # Place the backward joint at the intersection of both fixed-length leg segments.
                projection = (upper ** 2 - lower ** 2 + span ** 2) / (2 * span)
                bend = (rest_upper - direction * rest_upper.dot(direction)).normalized()
                middle = pivot + direction * projection + bend * math.sqrt(max(0, upper ** 2 - projection ** 2))
                return pivot, middle, toe

            kit.animate(foot, 'location', lambda t: pose(t)[2], step=2)
            kit.animate(shin, 'location', lambda t: pose(t)[1], step=2)
            kit.animate(thigh, 'location', lambda t: pose(t)[0], step=2)

            def shin_rotation(t):
                _, middle, toe = pose(t)
                return rest_lower.rotation_difference(toe - middle)

            def thigh_rotation(t):
                pivot, middle, _ = pose(t)
                return rest_upper.rotation_difference(middle - pivot)

            kit.animate(shin, 'rotation_quaternion', shin_rotation, step=2)
            kit.animate(thigh, 'rotation_quaternion', thigh_rotation, step=2)
            # Shoulder, arm, forearm cannon.
            box('Mech shoulder', (3.2, 4.0, 2.8), (side * 6.3, 0.4, 18.6), rot=(0, side * -8, 0))
            box('Mech shoulder plate', (3.6, 3.0, 0.4), (side * 6.6, 0.2, 20.2), rot=(0, side * -14, 0))
            elbow = (side * 6.9, 0.8, 13.4)
            wrist = (side * 7.0, -3.6, 12.4)
            limb('Mech upper arm', (side * 6.4, 0.4, 17.4), elbow, 0.8)
            limb('Mech forearm', elbow, wrist, 1.05)
            add(kit.sphere('Mech elbow', 0.95 * s, tuple(Vector(elbow) * s), mech_joint, segments=24, rings=12))
            barrel = add(kit.cylinder('Mech cannon', 0.42 * s, 6.0 * s, tuple(Vector((side * 7.0, -6.0, 12.3)) * s),
                                      mech_joint, rotation=(90, 0, 0), segments=24, bevel=0.03))
            add(kit.cylinder('Mech muzzle', 0.55 * s, 0.6 * s, tuple(Vector((side * 7.0, -8.8, 12.3)) * s),
                             mech_armor, rotation=(90, 0, 0), segments=24, bevel=0.03))
        # Hip block and the main hull: an extruded prow so the front reads as a wedge.
        box('Mech pelvis', (5.6, 4.0, 2.4), (0, 0.0, 13.2))
        hull = add(kit.extrude('Mech hull', [(-4.6, 2.8), (4.6, 2.8), (5.0, -0.6), (2.6, -3.6), (-2.6, -3.6),
                                             (-5.0, -0.6)], height=5.4 * s, material=mech_armor,
                               location=(0, 0, 14.4 * s), bevel=0.1))
        hull.scale = (s, s, 1)
        box('Mech dorsal plate', (7.2, 5.2, 0.6), (0, 0.5, 20.0), rot=(6, 0, 0))
        # Cockpit head low on the prow, with a narrow visor slit that lights up later.
        box('Mech head', (3.2, 2.8, 2.0), (0, -3.9, 18.4), rot=(-8, 0, 0))
        box('Mech brow', (3.6, 1.2, 0.5), (0, -5.0, 19.4), rot=(-20, 0, 0))
        visor = box('Mech visor', (2.4, 0.2, 0.22), (0, -5.32, 18.55), mat=eye, bevel=0.0)
        for side in (-1, 1):
            add(kit.cylinder('Mech eye lamp', 0.22 * s, 0.2 * s, tuple(Vector((side * 1.9, -5.0, 17.6)) * s), eye,
                             rotation=(90, 0, 0), segments=16))
        # Missile pod on the left shoulder, exhaust stacks and antennae on the back.
        pod = box('Mech missile pod', (2.8, 3.2, 2.2), (-6.2, 0.8, 21.4))
        for i in range(3):
            for j in range(2):
                add(kit.cylinder('Mech pod tube', 0.28 * s, 0.3 * s,
                                 tuple(Vector((-7.1 + i * 0.9, -0.85, 21.0 + j * 0.9)) * s), mech_joint,
                                 rotation=(90, 0, 0), segments=12))
        for side in (-1, 1):
            add(kit.cylinder('Mech exhaust stack', 0.5 * s, 3.2 * s, tuple(Vector((side * 2.2, 3.0, 21.2)) * s),
                             mech_joint, segments=20, rotation=(-12, 0, 0)))
        add(kit.tube('Mech antenna', [tuple(Vector(p) * s) for p in ((3.6, 2.0, 20.2), (3.9, 2.4, 25.0))],
                     radius=0.07 * s, material=mech_joint))
        add(kit.tube('Mech antenna', [tuple(Vector(p) * s) for p in ((4.3, 1.6, 20.2), (4.8, 2.2, 23.4))],
                     radius=0.05 * s, material=mech_joint))
        for part in parts:
            part.parent = body
        kit.animate(body, 'location', body_pose, step=2)
        root.location = (2.5, MECH_Y, 0)
        root.rotation_euler.z = math.radians(-8)

    build_mech()
    kit.key(eye.node_tree.nodes['Emission'].inputs['Strength'], 'default_value',
            [(EYES_ON[0], 0.0), (EYES_ON[1], 60.0), (1.0, 45.0)])

    # Floodlight masts on the apron outside: silhouettes that layer the depth behind the mech.
    for x, y in ((-34, 60), (40, 85), (-70, 130)):
        strut('Floodlight mast', (x, y, 0), (x, y, 30), 0.6, 0.6, steel)
        kit.box('Floodlight head', (4.0, 1.0, 2.0), (x, y - 0.6, 30.5), steel)

    # ------------------------------------------------------------------ light and atmosphere
    # Physical sky for the bright exterior, with a low sun almost behind the mech so its long
    # shadow reaches into the hangar along the beam.
    kit.sky(sun_elevation=9.0, sun_rotation=180.0, strength=0.1, sun_disc=False, aerosol=2.5)
    kit.sun(elevation=9.0, azimuth=14.0, strength=4.0, color='#FFE2BE', angle=0.6, name='Low sun')
    kit.area('Dim service lights', (-16, -42, 16), (-5, -8, 5), 21500, '#C6D4EB', 8, size_y=4)
    # Interior haze with a noise-driven density: shafts break into drifting dusty layers.
    haze = kit.haze(density=0.012, color='#E8E2D8', anisotropy=0.38, size=(HALL_W - 1.5, HALL_D - 1, EAVES),
                    location=(0, -HALL_D / 2, EAVES / 2), name='Hangar dust haze')
    hn = haze.data.materials[0].node_tree
    vol = next(n for n in hn.nodes if n.type == 'PRINCIPLED_VOLUME')
    dust = hn.nodes.new('ShaderNodeTexNoise')
    dust.inputs['Scale'].default_value = 0.09
    dust.inputs['Detail'].default_value = 4.0
    dust_map = hn.nodes.new('ShaderNodeMapRange')
    dust_map.inputs['To Min'].default_value = 0.003
    dust_map.inputs['To Max'].default_value = 0.020
    hn.links.new(dust.outputs['Fac'], dust_map.inputs['Value'])
    hn.links.new(dust_map.outputs['Result'], vol.inputs['Density'])
    # Drift the noise slowly through the hall so the dust visibly moves in the beams.
    dust_coord = hn.nodes.new('ShaderNodeTexCoord')
    drift = hn.nodes.new('ShaderNodeMapping')
    hn.links.new(dust_coord.outputs['Object'], drift.inputs['Vector'])
    hn.links.new(drift.outputs['Vector'], dust.inputs['Vector'])
    kit.animate(drift.inputs['Location'], 'default_value', lambda t: (1.2 * t, -0.6 * t, 0.4 * t), step=6,
                interpolation='BEZIER')
    kit.haze(density=0.0008, color='#F2E6D6', anisotropy=0.40, size=(500, 400, 80), location=(0, 202, 40),
             name='Exterior haze')

    # Dust motes: small bright specks that only show where the beam lights them.
    mote_mat = kit.material('Dust mote', '#FFF4E2', roughness=0.9)
    motes = []
    for k in range(260):
        p = Vector((rng.uniform(-14, 14), rng.uniform(-30, -3), rng.uniform(0.3, 9.0)))
        m = kit.ico(f'Dust mote {k}', rng.uniform(0.012, 0.03), tuple(p), mote_mat, subdivisions=1)
        drift_v = Vector((rng.uniform(-0.6, 0.6), rng.uniform(-0.4, 0.4), rng.uniform(-0.25, 0.35)))
        kit.animate(m, 'location', lambda t, p=p, d=drift_v, ph=rng.random(): p + d * t + Vector((0, 0, 0.15 * math.sin(
            2 * math.pi * (t + ph)))), step=12, interpolation='BEZIER')
        motes.append(m)

    kit.render(exposure=-0.4, look='AgX - Medium High Contrast', motion_blur=True, volume_step=1.5)

    # ------------------------------------------------------------------ camera: locked wide, slight push
    cam = kit.camera((0, -HALL_D + 10, 2.2), target=(0.0, 0.0, 11.0), lens=21)
    kit.dolly(cam, (0, -HALL_D + 10, 2.2), (0, -HALL_D + 14, 2.5), ease_kind='in_out', power=2.0)
