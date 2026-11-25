"""Noir title card: THE LONG NIGHT on an office wall striped by venetian-blind shadows.

Teaches:
- hard-light storytelling: one small, distant spot outside a window shines through real blind
  slats, so the stripes are true cast shadows that bend over the wainscot, the hat and the
  letters, instead of a painted texture;
- shadow-transparent glass: the window pane mixes Glass with Transparent on shadow rays, so the
  pane looks like glass to the camera but does not block the spot (Cycles would otherwise treat
  it as an opaque caustic caster). Rain drops stay real glass, so they throw moving specks;
- a volumetric smoke plume: noise-driven density shaped by a gradient mask into a column that
  widens and fades as it rises, with the noise drifting upward over the shot;
- a title that fades up: text with a Transparent/paint mix whose factor is keyed;
- monochrome by construction: every material and light is neutral grey, so the frame is black
  and white without post-processing.
"""
import math

# ----------------------------------------------------------------------------- set dimensions (metres)
ROOM_X0 = -2.2         # the window wall (left wall) plane
WALL_Y = 0.0           # the back wall, with the title
WINDOW_Y = (-1.55, -0.25)
WINDOW_Z = (0.85, 2.55)
SLAT_PITCH = 0.055
TITLE = 'THE LONG NIGHT'
TITLE_X, TITLE_Z = 0.06, 1.62
TITLE_SIZE = 0.293
FONT = 'fontsource:playfair-display@700'

# ----------------------------------------------------------------------------- timing (shot progress)
TITLE_IN = (0.09, 0.31)

# ----------------------------------------------------------------------------- greys
PLASTER = '#B8B6B2'
WAINSCOT = '#3A3836'
INK = '#121212'


def build(kit):
    from mathutils import Vector

    rng = kit.rng

    # ------------------------------------------------------------------ materials
    plaster = kit.procedural('Office plaster', 'concrete', colors=['#A9A7A3', PLASTER, '#C4C2BE'], scale=1.4,
                             roughness=0.85, bump=0.12)
    wainscot = kit.procedural('Wainscot wood', 'wood', colors=['#252423', WAINSCOT, '#4A4846'], scale=1.0,
                              roughness=0.45, bump=0.1)
    trim = kit.material('Painted trim', '#5A5856', roughness=0.4)
    floor = kit.procedural('Office floorboards', 'wood', colors=['#1E1D1C', '#2A2928', '#363433'], scale=0.6,
                           roughness=0.35, bump=0.1)
    metal = kit.material('Dark metal', '#2A2A2A', roughness=0.35, metallic=0.9)
    felt = kit.material('Fedora felt', '#1C1C1C', roughness=0.9, sheen=0.4)
    band = kit.material('Hat band', '#0A0A0A', roughness=0.5)
    blind = kit.material('Blind slat', '#C8C8C8', roughness=0.5)
    drop_glass = kit.glass('Rain drop', '#FFFFFF', roughness=0.02, ior=1.33)

    def shadow_clear_glass(name):
        """Glass for camera rays, Transparent for shadow rays: light passes, reflections stay."""
        mat = kit.glass(name, '#F2F2F2', roughness=0.03, ior=1.5)
        nt = mat.node_tree
        out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
        shader = out.inputs['Surface'].links[0].from_socket
        path = nt.nodes.new('ShaderNodeLightPath')
        clear = nt.nodes.new('ShaderNodeBsdfTransparent')
        mix = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(path.outputs['Is Shadow Ray'], mix.inputs[0])
        nt.links.new(shader, mix.inputs[1])
        nt.links.new(clear.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs['Surface'])
        return mat

    pane_glass = shadow_clear_glass('Window pane')

    # ------------------------------------------------------------------ room shell
    kit.box('Back wall', (6.0, 0.1, 3.0), (0.6, WALL_Y + 0.05, 1.5), plaster)
    kit.box('Floor', (6.0, 6.0, 0.05), (0.6, -2.6, -0.025), floor, ground=True)
    # Complete the room footprint outside the title framing and leave the proof view open above the return.
    kit.box('Right partition', (.13, 4.8, 1.08), (3.57, -2.38, .54), wainscot, bevel=.013)
    kit.box('Right partition rail', (.185, 4.8, .063), (3.56, -2.38, 1.095), trim, bevel=.012)
    # Wainscot panelling with a chair rail and skirting: three horizontal bands of detail.
    kit.box('Wainscot', (6.0, 0.03, 0.95), (0.6, WALL_Y - 0.015, 0.475), wainscot)
    for k in range(9):
        x = -1.9 + k * 0.62
        kit.box('Wainscot stile', (0.05, 0.02, 0.8), (x, WALL_Y - 0.035, 0.48), wainscot, bevel=0.006)
    kit.box('Chair rail', (6.0, 0.05, 0.06), (0.6, WALL_Y - 0.03, 0.97), trim, bevel=0.01)
    kit.box('Skirting board', (6.0, 0.035, 0.14), (0.6, WALL_Y - 0.03, 0.07), trim, bevel=0.006)

    # Left wall with a window opening: four wall pieces around the hole, then frame, pane, blinds.
    y0, y1 = WINDOW_Y
    z0, z1 = WINDOW_Z
    lw = kit.material('Left wall plaster', '#9C9A96', roughness=0.85, bump=(6, 0.1))
    kit.box('Left wall (near)', (0.1, 3.0 + y0, 3.0), (ROOM_X0 - 0.05, (y0 - 3.0) / 2 + 0.0, 1.5), lw)
    kit.box('Left wall (corner)', (0.1, -y1, 3.0), (ROOM_X0 - 0.05, y1 / 2, 1.5), lw)
    kit.box('Left wall (sill)', (0.1, y1 - y0, z0), (ROOM_X0 - 0.05, (y0 + y1) / 2, z0 / 2), lw)
    kit.box('Left wall (head)', (0.1, y1 - y0, 3.0 - z1), (ROOM_X0 - 0.05, (y0 + y1) / 2, (3.0 + z1) / 2), lw)
    for name, size, loc in (
            ('Window sill', (0.22, y1 - y0 + 0.16, 0.04), (ROOM_X0 + 0.02, (y0 + y1) / 2, z0 - 0.02)),
            ('Window head', (0.14, y1 - y0 + 0.12, 0.06), (ROOM_X0, (y0 + y1) / 2, z1 + 0.03)),
            ('Window jamb', (0.14, 0.06, z1 - z0), (ROOM_X0, y0 - 0.03, (z0 + z1) / 2)),
            ('Window jamb', (0.14, 0.06, z1 - z0), (ROOM_X0, y1 + 0.03, (z0 + z1) / 2)),
            ('Window mullion', (0.06, 0.04, z1 - z0), (ROOM_X0 - 0.06, (y0 + y1) / 2, (z0 + z1) / 2)),
            ('Window transom', (0.06, y1 - y0, 0.04), (ROOM_X0 - 0.06, (y0 + y1) / 2, z0 + (z1 - z0) * 0.62))):
        kit.box(name, size, loc, trim, bevel=0.006)
    kit.box('Window pane', (0.008, y1 - y0, z1 - z0), (ROOM_X0 - 0.09, (y0 + y1) / 2, (z0 + z1) / 2), pane_glass)

    # Venetian blind: tilted slats on two ladder cords, raised a little so the top is clear.
    for k in range(int((z1 - z0 - 0.25) / SLAT_PITCH)):
        z = z1 - 0.1 - k * SLAT_PITCH
        kit.box('Blind slat', (0.05, y1 - y0 - 0.06, 0.003), (ROOM_X0 + 0.06, (y0 + y1) / 2, z), blind,
                rotation=(0, -38, 0))
    for y in (y0 + 0.25, y1 - 0.25):
        kit.tube('Blind cord', [(ROOM_X0 + 0.06, y, z1 - 0.05), (ROOM_X0 + 0.06, y, z0 + 0.2)], radius=0.002,
                 material=blind, resolution=4)
    kit.box('Blind head rail', (0.07, y1 - y0 - 0.04, 0.04), (ROOM_X0 + 0.06, (y0 + y1) / 2, z1 - 0.04), blind,
            bevel=0.004)

    # Rain on the glass: static beads plus a few drops that run down the outside of the pane.
    gx = ROOM_X0 - 0.097
    for k in range(170):
        r = rng.uniform(0.002, 0.006)
        p = (gx, rng.uniform(y0 + 0.02, y1 - 0.02), rng.uniform(z0 + 0.02, z1 - 0.02))
        kit.sphere(f'Bead {k}', r, p, drop_glass, segments=10, rings=6, scale=(0.4, 1.0, 1.25))
    for k in range(14):
        y = rng.uniform(y0 + 0.05, y1 - 0.05)
        top = rng.uniform(z0 + 0.6, z1)
        fall = rng.uniform(0.4, 1.1)
        delay = rng.uniform(0.0, 0.5)
        d = kit.sphere(f'Running drop {k}', 0.007, (gx, y, top), drop_glass, segments=12, rings=8, scale=(0.4, 1.0, 1.6))
        kit.animate(d, 'location', lambda t, y=y, top=top, f=fall, dl=delay: Vector((
            gx, y + 0.01 * math.sin(9 * t + y * 30), top - f * kit.ease(kit.segment(t, dl, min(1.0, dl + 0.5)), 'in', 1.6))),
            step=2)

    # Rain outside: falling streaks lit by the street lamp, seen through the glass.
    streak = kit.material('Rain streak', '#D8D8D8', roughness=0.2)
    for k in range(160):
        x = rng.uniform(ROOM_X0 - 3.5, ROOM_X0 - 0.4)
        y = rng.uniform(y0 - 1.0, y1 + 1.0)
        z_start = rng.uniform(0.0, 4.0)
        s = kit.cylinder(f'Rain streak {k}', 0.0025, 0.12, (x, y, z_start), streak, segments=4, smooth=False)
        s['studio_ground'] = True  # Exterior weather is outside the measured room footprint.
        speed = rng.uniform(5.5, 7.5)

        def fall(t, z0_=z_start, v=speed):
            z = z0_ - v * t * kit.seconds
            return Vector((s.location.x, s.location.y, 4.0 - ((4.0 - z) % 4.4)))
        kit.animate(s, 'location', lambda t, f=fall, x=x, y=y: Vector((x, y, f(t).z)), step=1)

    # Night city beyond: a few soft rectangles of distant windows, very dim.
    city = kit.emissive('Distant windows', '#FFFFFF', strength=0.6)
    for k in range(18):
        kit.plane(f'Distant window {k}', (rng.uniform(0.3, 0.8), rng.uniform(0.4, 0.9)),
                  (ROOM_X0 - 14.0, rng.uniform(-5.0, 3.0), rng.uniform(0.5, 6.0)), city,
                  rotation=(90, 0, 90), ground=True)

    # ------------------------------------------------------------------ props
    # Coat hook with a fedora: a silhouette that says the genre before the words arrive.
    hook_x = -1.35
    kit.box('Hook plate', (0.06, 0.012, 0.14), (hook_x, WALL_Y - 0.006, 1.78), metal, bevel=0.004)
    kit.tube('Coat hook', [(hook_x, -0.01, 1.82), (hook_x, -0.09, 1.80), (hook_x, -0.12, 1.86)], radius=0.008,
             material=metal)
    hat = kit.lathe('Fedora', [(0.0, 0.135), (0.05, 0.132), (0.085, 0.11), (0.095, 0.03), (0.17, 0.012),
                               (0.19, 0.03), (0.18, 0.0), (0.09, 0.0), (0.0, 0.0)], segments=64, material=felt,
                    location=(hook_x, -0.16, 1.74), rotation=(70, 0, 0))
    hat.scale = (1.0, 1.15, 1.0)
    kit.cylinder('Hat band', 0.0965, 0.03, (hook_x, -0.147, 1.775), band, rotation=(70, 0, 0), segments=48)
    # A framed photograph on the wall right of the title and a light switch: mid-scale detail.
    kit.box('Picture frame', (0.42, 0.03, 0.52), (2.45, WALL_Y - 0.02, 1.72), metal, bevel=0.01)
    kit.box('Picture mat', (0.34, 0.01, 0.44), (2.45, WALL_Y - 0.04, 1.72),
            kit.material('Photo', '#6E6E6E', roughness=0.25))
    kit.box('Light switch', (0.08, 0.012, 0.12), (-0.55, WALL_Y - 0.006, 1.25), trim, bevel=0.004)
    # Filing cabinet with an ashtray and a burning cigarette: the smoke's source is on screen.
    cab = kit.material('Cabinet steel', '#3C3C3C', roughness=0.45, metallic=0.6)
    kit.box('Filing cabinet', (0.48, 0.6, 1.05), (1.47, -0.33, 0.525), cab, bevel=0.01)
    for k in range(3):
        kit.box('Drawer front', (0.42, 0.01, 0.3), (1.47, -0.635, 0.2 + k * 0.33), cab, bevel=0.006)
        kit.box('Drawer pull', (0.12, 0.02, 0.02), (1.47, -0.65, 0.3 + k * 0.33), metal, bevel=0.004)
    kit.lathe('Ashtray', [(0.0, 0.0), (0.075, 0.0), (0.08, 0.02), (0.07, 0.025), (0.06, 0.008), (0.0, 0.008)],
              segments=40, material=kit.glass('Ashtray glass', '#DDDDDD', roughness=0.08),
              location=(1.39, -0.32, 1.05))
    kit.cylinder('Cigarette', 0.0045, 0.08, (1.41, -0.34, 1.075), kit.material('Paper', '#E8E8E8', roughness=0.7),
                 rotation=(0, 80, 20), segments=12)
    kit.sphere('Cigarette ember', 0.005, (1.45, -0.326, 1.082), kit.emissive('Ember', '#FFFFFF', 4.0), segments=10,
               rings=6)

    # The proof camera also sees the adjacent desk, lamp, and upholstered office chair.
    dx, dy = 2.85, -1.37
    kit.box('Writing desk top', (.93, .64, .095), (dx,dy,.82), wainscot, bevel=.028)
    for x in (dx-.39,dx+.39):
        for y in (dy-.25,dy+.25):
            kit.box('Desk leg', (.069,.071,.79), (x,y,.395), trim, bevel=.009)
    kit.box('Desk drawer', (.68,.59,.18), (dx,dy,.706), wainscot, bevel=.016)
    kit.box('Desk blotter', (.48,.34,.011), (dx,dy-.067,.874), felt, bevel=.012)
    kit.box('Paper folders', (.21,.31,.046), (dx+.24,dy+.14,.898), blind, bevel=.008)
    kit.lathe('Desk lamp base', [(0,0),(.116,0),(.126,.022),(.078,.042),(0,.048)],
              segments=30, material=metal, location=(dx-.27,dy+.13,.866))
    kit.tube('Desk lamp arm', [(dx-.27,dy+.13,.89),(dx-.27,dy+.13,1.18),(dx-.22,dy+.04,1.22)],
             .019, metal)
    kit.lathe('Enamel desk lamp shade', [(.131,0),(.12,.055),(.068,.102),(.044,.114),
                                        (.041,.096),(.063,.09),(.112,.05),(.125,0)],
              segments=38, material=metal, location=(dx-.22,dy+.04,1.17))
    cx, cy = 2.70, -2.16
    kit.box('Office chair seat', (.51,.48,.094), (cx,cy,.452), felt, bevel=.045)
    kit.box('Office chair back', (.48,.092,.45), (cx,cy-.23,.688), felt, bevel=.046)
    kit.cylinder('Office chair stem', .056,.37,(cx,cy,.215),metal,segments=18)
    for i in range(5):
        a = math.tau*i/5
        kit.tube('Chair splayed base', [(cx,cy,.074),(cx+.24*math.cos(a),cy+.24*math.sin(a),.056)],
                 .026,metal,resolution=3)

    # ------------------------------------------------------------------ title
    ink = kit.material('Ivory letter paint', '#F2F2F2', roughness=0.67,
                       emission='#DDDDDD', emission_strength=.55)
    nt = ink.node_tree
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    paint = out.inputs['Surface'].links[0].from_socket
    clear = nt.nodes.new('ShaderNodeBsdfTransparent')
    fade = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(clear.outputs[0], fade.inputs[1])
    nt.links.new(paint, fade.inputs[2])
    nt.links.new(fade.outputs[0], out.inputs['Surface'])
    fade.inputs[0].default_value = 0.0
    kit.key(fade.inputs[0], 'default_value', [(0.0, 0.0), (TITLE_IN[0], 0.0), (TITLE_IN[1], 1.0), (1.0, 1.0)])
    kit.text(TITLE, size=TITLE_SIZE, location=(TITLE_X, WALL_Y - 0.004, TITLE_Z), rotation=(90, 0, 0),
             material=ink, extrude=0.002, font=FONT, name='Title', spacing=1.02)
    kit.box('Title rule', (2.3, 0.004, 0.012), (TITLE_X, WALL_Y - 0.002, TITLE_Z - 0.09), ink)

    # ------------------------------------------------------------------ smoke
    smoke = kit.box('Cigarette smoke', (1.4, 0.9, 1.75), (1.12, -0.46, 1.08 + 0.875))
    smat = kit.material('Smoke volume', '#FFFFFF')
    snt = smat.node_tree
    snt.nodes.clear()
    sout = snt.nodes.new('ShaderNodeOutputMaterial')
    vol = snt.nodes.new('ShaderNodeVolumePrincipled')
    vol.inputs['Color'].default_value = kit.color('#D6D6D6')
    vol.inputs['Anisotropy'].default_value = 0.4
    snt.links.new(vol.outputs[0], sout.inputs['Volume'])
    coord = snt.nodes.new('ShaderNodeTexCoord')
    drift = snt.nodes.new('ShaderNodeMapping')
    snt.links.new(coord.outputs['Object'], drift.inputs['Vector'])
    curl = snt.nodes.new('ShaderNodeTexNoise')
    curl.inputs['Scale'].default_value = 2.6
    curl.inputs['Detail'].default_value = 6.0
    curl.inputs['Distortion'].default_value = 1.8
    snt.links.new(drift.outputs['Vector'], curl.inputs['Vector'])
    # Column mask: distance from a rising, leaning axis, widening with height.
    sep = snt.nodes.new('ShaderNodeSeparateXYZ')
    snt.links.new(coord.outputs['Object'], sep.inputs[0])
    height = snt.nodes.new('ShaderNodeMapRange')       # 0 at the ember, 1 at the top of the box
    height.inputs['From Min'].default_value = -0.875
    height.inputs['From Max'].default_value = 0.875
    snt.links.new(sep.outputs['Z'], height.inputs['Value'])
    lean = snt.nodes.new('ShaderNodeMath')              # the plume drifts left as it rises
    lean.operation = 'MULTIPLY_ADD'
    lean.inputs[1].default_value = 0.42
    lean.inputs[2].default_value = 0.0
    snt.links.new(height.outputs['Result'], lean.inputs[0])
    dx = snt.nodes.new('ShaderNodeMath')
    dx.operation = 'ADD'
    snt.links.new(sep.outputs['X'], dx.inputs[0])
    snt.links.new(lean.outputs[0], dx.inputs[1])
    radial = snt.nodes.new('ShaderNodeCombineXYZ')
    snt.links.new(dx.outputs[0], radial.inputs['X'])
    snt.links.new(sep.outputs['Y'], radial.inputs['Y'])
    dist = snt.nodes.new('ShaderNodeVectorMath')
    dist.operation = 'LENGTH'
    snt.links.new(radial.outputs[0], dist.inputs[0])
    width = snt.nodes.new('ShaderNodeMath')
    width.operation = 'MULTIPLY_ADD'
    width.inputs[1].default_value = 0.34
    width.inputs[2].default_value = 0.02
    snt.links.new(height.outputs['Result'], width.inputs[0])
    ratio = snt.nodes.new('ShaderNodeMath')
    ratio.operation = 'DIVIDE'
    snt.links.new(dist.outputs['Value'], ratio.inputs[0])
    snt.links.new(width.outputs[0], ratio.inputs[1])
    mask = snt.nodes.new('ShaderNodeMapRange')
    mask.inputs['From Min'].default_value = 1.0
    mask.inputs['From Max'].default_value = 0.0
    snt.links.new(ratio.outputs[0], mask.inputs['Value'])
    fade_top = snt.nodes.new('ShaderNodeMapRange')       # thins out toward the top
    fade_top.inputs['From Min'].default_value = 1.0
    fade_top.inputs['From Max'].default_value = 0.25
    snt.links.new(height.outputs['Result'], fade_top.inputs['Value'])
    wisps = snt.nodes.new('ShaderNodeMapRange')         # only the denser half of the noise shows
    wisps.inputs['From Min'].default_value = 0.48
    wisps.inputs['From Max'].default_value = 0.72
    snt.links.new(curl.outputs['Fac'], wisps.inputs['Value'])
    m1 = snt.nodes.new('ShaderNodeMath')
    m1.operation = 'MULTIPLY'
    snt.links.new(mask.outputs['Result'], m1.inputs[0])
    snt.links.new(wisps.outputs['Result'], m1.inputs[1])
    m2 = snt.nodes.new('ShaderNodeMath')
    m2.operation = 'MULTIPLY'
    snt.links.new(m1.outputs[0], m2.inputs[0])
    snt.links.new(fade_top.outputs['Result'], m2.inputs[1])
    dens = snt.nodes.new('ShaderNodeMath')
    dens.operation = 'MULTIPLY'
    dens.inputs[1].default_value = 16.0
    snt.links.new(m2.outputs[0], dens.inputs[0])
    snt.links.new(dens.outputs[0], vol.inputs['Density'])
    smoke.data.materials.append(smat)
    smoke.visible_shadow = False
    kit.spot('Cigarette smoke edge', (.98, -.61, 1.07), (1.2, -.45, 2.17),
             power=17, color='#E3E3E3', angle=24, blend=.55, radius=.035)
    # The noise field sinks through the box while the mask stays put: the smoke appears to rise.
    kit.animate(drift.inputs['Location'], 'default_value', lambda t: (0.12 * t, 0.05 * t, -0.9 * t), step=4,
                interpolation='BEZIER')

    # ------------------------------------------------------------------ light
    # A dim neutral world and a faint fill keep the shadow stripes from going to pure black.
    kit.world('#FFFFFF', strength=0.012)
    kit.area('Room fill', (1.5, -3.5, 2.4), (0.6, 0, 1.4), power=12, color='#FFFFFF', size=2.0)
    # The street lamp: a small, distant, hard source outside the window and above it.
    kit.spot('Street lamp through blinds', (ROOM_X0 - 4.6, -1.9, 3.5), (TITLE_X + 0.2, WALL_Y, TITLE_Z - 0.1),
             power=9000, color='#FFFFFF', angle=16, blend=0.08, radius=0.01)
    # A cool, broad glow outside lights the rain streaks and gives the window a value.
    kit.area('Night glow outside', (ROOM_X0 - 6.0, -0.9, 2.0), (ROOM_X0, -0.9, 1.6), power=160, color='#FFFFFF',
             size=3.0)
    kit.render(exposure=0.0, look='AgX - High Contrast', motion_blur=True, shutter=0.5)

    # ------------------------------------------------------------------ camera: slow push-in
    cam = kit.camera((1.45, -4.25, 1.55), target=(-0.12, 0.0, 1.52), lens=28, dof=4.3, fstop=5.6)
    kit.dolly(cam, (1.45, -4.25, 1.55), (1.2, -3.55, 1.58), target_start=(-0.12, 0.0, 1.52),
              target_end=(-0.1, 0.0, 1.55), ease_kind='in_out', power=1.6)
