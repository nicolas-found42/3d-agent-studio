"""Pendulum wave: fifteen brass bobs on fine wires from a walnut frame, under a museum spot.

Teaches:
- loop-exact physics: pendulum i swings a whole number of cycles (BASE_CYCLES + i) in the shot,
  so the bobs drift into travelling waves, split into groups, and realign exactly at the loop
  point. Neighbours differ by one cycle, which is what makes the pattern;
- bifilar (V-shaped) suspension: two wires per bob meet at a hook, keeping every bob in one
  swing plane. Wires and bob hang from a pivot empty on the hinge axis, so one keyed rotation
  per pendulum moves the whole assembly;
- a hand-built walnut material (straight grain from stretched wave bands plus pore noise) with
  the grain running along each part's length, bevelled joinery, brass hardware and a plaque:
  detail at the frame, hardware and surface scales;
- museum lighting: one warm, tight spot on a black plinth in a dark gallery, a cool back spot
  for glints on the wires, faint haze so the beam reads, and a dim wash on the far wall;
- a loop-safe camera tilt: the camera rides a vertical arc from a low end-on view up to almost
  overhead and back with a cosine, so the end frame matches the first.

Time is compressed: a real machine takes about a minute to realign. We keep the integer-cycle
structure and choose believable wire lengths (longest at the front) rather than the exact
g-derived lengths, which would make the short pendulums only a few centimetres long.
"""
import math

# ----------------------------------------------------------------------------- dimensions (metres)
PLINTH_TOP = 0.92      # museum plinth height; the machine stands on it
COUNT = 15             # pendulums
SPACING = 0.052        # between pendulums along the row (world Y)
PIVOT_Z = 0.60         # hinge line under the top beam, above the base board
LONGEST = 0.47         # wire length of the front pendulum (to the bob centre)
SHORTEST = 0.25        # wire length of the back pendulum
BOB_R = 0.0175         # 35 mm brass bobs
V_SPREAD = 0.021       # half-spread of each wire pair on the beam
DISPLACE = 0.085       # every bob starts pulled this far sideways (released together by a board)
BASE_CYCLES = 7        # pendulum 0 swings 7 times per loop, pendulum 14 swings 21 times

# ----------------------------------------------------------------------------- camera arc
ELEV_LOW, ELEV_HIGH = 24.0, 80.0   # degrees above the row's end; the tilt goes up and back
CAM_RADIUS = 1.75

# ----------------------------------------------------------------------------- palette
WALNUT = ['#2A170D', '#4A2B18', '#6B4128']
BRASS = '#C9A253'
PLINTH = '#141416'
WALL = '#2A2826'


def build(kit):
    import bpy
    from mathutils import Vector

    base_z = PLINTH_TOP

    # ------------------------------------------------------------------ materials
    def walnut(name, axis):
        """Straight-grained walnut. Wave BANDS stretched along `axis` give long grain lines; a
        fine noise adds pores; both feed roughness and a little bump so the spot rakes the grain."""
        mat = kit.material(name, WALNUT[1], roughness=0.38, coat=0.25)
        nt = mat.node_tree
        bs = kit.bsdf(mat)
        coord = nt.nodes.new('ShaderNodeTexCoord')
        mapping = nt.nodes.new('ShaderNodeMapping')
        # Squash the coordinate along the grain axis so bands run lengthwise.
        stretch = {'X': (0.6, 9.0, 9.0), 'Y': (9.0, 0.6, 9.0), 'Z': (9.0, 9.0, 0.6)}[axis]
        mapping.inputs['Scale'].default_value = stretch
        nt.links.new(coord.outputs['Object'], mapping.inputs['Vector'])
        wave = nt.nodes.new('ShaderNodeTexWave')
        wave.wave_type = 'BANDS'
        wave.bands_direction = {'X': 'Y', 'Y': 'X', 'Z': 'X'}[axis]
        wave.inputs['Scale'].default_value = 6.0
        wave.inputs['Distortion'].default_value = 7.0
        wave.inputs['Detail'].default_value = 4.0
        wave.inputs['Detail Scale'].default_value = 1.6
        nt.links.new(mapping.outputs['Vector'], wave.inputs['Vector'])
        pores = nt.nodes.new('ShaderNodeTexNoise')
        pores.inputs['Scale'].default_value = 420.0
        pores.inputs['Detail'].default_value = 2.0
        nt.links.new(coord.outputs['Object'], pores.inputs['Vector'])
        mix = nt.nodes.new('ShaderNodeMix')
        mix.data_type = 'FLOAT'
        mix.inputs['Factor'].default_value = 0.25
        nt.links.new(wave.outputs['Fac'], mix.inputs['A'])
        nt.links.new(pores.outputs['Fac'], mix.inputs['B'])
        ramp = nt.nodes.new('ShaderNodeValToRGB')
        for i, c in enumerate(WALNUT):
            el = ramp.color_ramp.elements[i] if i < 2 else ramp.color_ramp.elements.new(0.5)
            el.position = (0.15, 0.85, 0.5)[i]
            el.color = kit.color(c)
        nt.links.new(mix.outputs['Result'], ramp.inputs['Fac'])
        nt.links.new(ramp.outputs['Color'], bs.inputs['Base Color'])
        rough = nt.nodes.new('ShaderNodeMapRange')
        rough.inputs['To Min'].default_value = 0.30
        rough.inputs['To Max'].default_value = 0.52
        nt.links.new(mix.outputs['Result'], rough.inputs['Value'])
        nt.links.new(rough.outputs['Result'], bs.inputs['Roughness'])
        bump = nt.nodes.new('ShaderNodeBump')
        bump.inputs['Strength'].default_value = 0.08
        bump.inputs['Distance'].default_value = 0.0005
        nt.links.new(mix.outputs['Result'], bump.inputs['Height'])
        nt.links.new(bump.outputs['Normal'], bs.inputs['Normal'])
        return mat

    walnut_x = walnut('Walnut (grain X)', 'X')
    walnut_y = walnut('Walnut (grain Y)', 'Y')
    walnut_z = walnut('Walnut (grain Z)', 'Z')
    # Polished but handled brass: low roughness with a faint bump so highlights are not CG-perfect.
    brass = kit.material('Polished brass', BRASS, roughness=0.16, metallic=1.0, bump=(1800, 0.015))
    brass_dull = kit.material('Aged brass', '#A8854A', roughness=0.32, metallic=1.0, bump=(900, 0.03))
    wire = kit.material('Steel wire', '#D8DADC', roughness=0.2, metallic=1.0)
    felt = kit.material('Plinth paint', PLINTH, roughness=0.75, bump=(300, 0.03))
    engraving = kit.material('Engraving fill', '#1A140C', roughness=0.6)

    # ------------------------------------------------------------------ the museum room
    kit.box('Museum plinth', (0.62, 1.25, PLINTH_TOP), (0, 0.02, PLINTH_TOP / 2), felt, bevel=0.004)
    kit.ground(kit.procedural('Gallery floor', 'concrete', colors=['#1C1C1E', '#232325', '#2B2B2D'],
                              scale=0.5, roughness=0.55, bump=0.05))
    kit.box('Gallery wall', (8.0, 0.2, 4.0), (0, 3.4, 2.0), kit.material('Gallery wall', WALL, roughness=0.9))
    kit.box('Skirting', (8.0, 0.02, 0.12), (0, 3.29, 0.06), kit.material('Skirting', '#111111', roughness=0.6))

    # ------------------------------------------------------------------ the walnut frame
    half_len = (COUNT - 1) * SPACING / 2
    post_y = half_len + 0.075
    board = kit.box('Base board', (0.27, 2 * post_y + 0.11, 0.032), (0, 0, base_z + 0.006 + 0.016),
                    walnut_y, bevel=0.004)
    plinth_edge = kit.box('Base moulding', (0.29, 2 * post_y + 0.13, 0.006), (0, 0, base_z + 0.003),
                          walnut_y, bevel=0.0015)
    board_top = base_z + 0.038
    for sx in (-1, 1):
        for sy in (-1, 1):
            # Brass feet raise the board off the plinth: small, but they ground the object.
            kit.cylinder('Brass foot', 0.009, 0.006, (sx * 0.12, sy * (post_y + 0.035), base_z + 0.003), brass_dull,
                         segments=24, bevel=0.001)
    beam_z = base_z + PIVOT_Z
    for sy in (-1, 1):
        kit.box('Frame post', (0.036, 0.036, beam_z - board_top + 0.004),
                (0, sy * post_y, (board_top + beam_z) / 2), walnut_z, bevel=0.003)
        # Turned brass collar where each post meets the board.
        kit.lathe('Post collar', [(0.0, 0.0), (0.031, 0.0), (0.031, 0.004), (0.027, 0.008), (0.027, 0.012),
                                  (0.0, 0.012)], segments=40, material=brass_dull,
                  location=(0, sy * post_y, board_top))
        # A foot block and two raked braces across the row stiffen each post. They sit outside
        # the wire pairs, so nothing swinging can touch them.
        kit.box('Post foot', (0.15, 0.05, 0.018), (0, sy * post_y, board_top + 0.009), walnut_x, bevel=0.003)
        for sx in (-1, 1):
            kit.box('Post brace', (0.012, 0.014, 0.12), (sx * 0.042, sy * post_y, board_top + 0.05), walnut_z,
                    rotation=(0, sx * -35, 0), bevel=0.002)
    beam = kit.box('Top beam', (0.05, 2 * post_y + 0.08, 0.04), (0, 0, beam_z + 0.02), walnut_y, bevel=0.005)
    kit.box('Beam cap', (0.058, 2 * post_y + 0.09, 0.008), (0, 0, beam_z + 0.044), walnut_y, bevel=0.003)

    # Plaque on the base board: engraved title on a brass plate, a small museum-object cue.
    front = -(post_y + 0.055)
    kit.box('Brass plaque', (0.12, 0.002, 0.02), (0, front - 0.001, base_z + 0.022), brass, bevel=0.0006)
    kit.text('PENDULUM WAVE', size=0.0085, location=(0, front - 0.0021, base_z + 0.0192),
             rotation=(90, 0, 0), material=engraving, extrude=0.0002, name='Plaque engraving')
    # A walnut release board rests on the base: the paddle used to pull all bobs aside together.
    kit.box('Release board', (0.05, 0.86, 0.012), (0.098, 0.0, board_top + 0.006), walnut_y, bevel=0.003,
            rotation=(0, 0, 0))
    # Scale ticks along the board edge, one per pendulum: a mid-scale rhythm under the bobs.
    for i in range(COUNT):
        y = -half_len + i * SPACING
        kit.box(f'Index pin {i}', (0.004, 0.004, 0.003), (-0.105, y, board_top + 0.0015), brass_dull, bevel=0.0008)

    # ------------------------------------------------------------------ the pendulums
    for i in range(COUNT):
        y = -half_len + i * SPACING            # i = 0 is the front (nearest the low camera)
        length = LONGEST + (SHORTEST - LONGEST) * i / (COUNT - 1)
        cycles = BASE_CYCLES + i
        amplitude = math.asin(DISPLACE / length)

        # Pivot empty on the hinge axis (world Y). Everything that swings is parented to it.
        pivot = kit.empty(f'Pendulum {i:02d} pivot', (0, y, beam_z), size=0.02)
        # Screw eyes in the beam underside, where each wire is tied off (fixed, not swinging).
        for s in (-1, 1):
            kit.torus(f'Screw eye {i:02d}', 0.0028, 0.0007, (0, y + s * V_SPREAD, beam_z - 0.0028), brass_dull,
                      rotation=(0, 90, 0), segments=16, sides=6)
        hook_z = beam_z - length + BOB_R + 0.004
        parts = []
        for s in (-1, 1):
            parts.append(kit.tube(f'Wire {i:02d}', [(0, y + s * V_SPREAD, beam_z - 0.005), (0, y, hook_z)],
                                  radius=0.0005, material=wire, resolution=4, smooth=False))
        bob_z = beam_z - length
        parts.append(kit.sphere(f'Brass bob {i:02d}', BOB_R, (0, y, bob_z), brass, segments=40, rings=20))
        parts.append(kit.torus(f'Bob eyelet {i:02d}', 0.0032, 0.0009, (0, y, hook_z), brass, rotation=(0, 90, 0),
                               segments=16, sides=6))
        parts.append(kit.cylinder(f'Bob stem {i:02d}', 0.0024, 0.006, (0, y, bob_z + BOB_R + 0.0005), brass,
                                  segments=16))
        bpy.context.view_layer.update()
        for p in parts:
            kit.parent(p, pivot)

        # theta(t) = A cos(2 pi c t): every bob starts at full displacement (all in a line) and,
        # because c is an integer, returns there at t = 1. Keyed every frame for a smooth swing.
        kit.animate(pivot, 'rotation_euler', lambda t, a=amplitude, c=cycles: a * math.cos(2 * math.pi * c * t),
                    index=1)

    # ------------------------------------------------------------------ lighting
    kit.world('#07080A', strength=1.0)
    # The museum key: a warm, tight spot almost straight above, slightly in front.
    kit.spot('Museum key spot', (0.35, -0.55, base_z + 2.4), (0, 0.0, base_z + 0.25), power=520,
             color='#FFD9AE', angle=30, blend=0.45, radius=0.04)
    # A cool spot from behind and above rims the wires and the far side of the bobs.
    kit.spot('Back glint spot', (-0.25, 1.9, base_z + 1.6), (0, 0, base_z + 0.35), power=160,
             color='#CFE0FF', angle=24, blend=0.5, radius=0.03)
    # A low-power wash on the far wall separates the gallery from black.
    kit.area('Wall wash', (0, 2.2, 3.4), (0, 3.3, 1.2), power=90, color='#FFE6C8', size=3.0, size_y=0.6)
    # A large, dim soft source over the plinth: something for the brass to reflect besides black.
    kit.area('Ceiling bounce', (0, 0, base_z + 2.0), (0, 0, base_z), power=14, color='#FFF1E0', size=2.0)
    kit.haze(density=0.006, color='#FFFFFF', anisotropy=0.55, size=(6, 8, 4), location=(0, 0.8, 2.0))
    kit.render(exposure=0.0, look='AgX - Medium High Contrast', motion_blur=True, shutter=0.5)

    # ------------------------------------------------------------------ camera: overhead tilt
    center = Vector((0, 0.02, base_z + 0.33))
    cam = kit.camera(tuple(center + Vector((0, -CAM_RADIUS, 0.3))), target=tuple(center), lens=48,
                     dof=CAM_RADIUS, fstop=8)

    def on_arc(t):
        # (1 - cos)/2 eases out of and back into the low view; equal at t = 0 and t = 1.
        k = (1 - math.cos(2 * math.pi * t)) / 2
        e = math.radians(ELEV_LOW + (ELEV_HIGH - ELEV_LOW) * k)
        radius_horizontal = CAM_RADIUS * math.cos(e)
        bearing = math.radians(24)
        return center + Vector((0.22 + radius_horizontal * math.sin(bearing),
                                -radius_horizontal * math.cos(bearing), CAM_RADIUS * math.sin(e)))

    kit.animate(cam, 'location', on_arc)
    kit.note('Pendulum i swings BASE_CYCLES + i times per loop; all bobs realign at the loop point.')
