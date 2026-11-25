"""Make a stacked area graph directly from CSV counts and reveal it on its day axis."""
from math import ceil

MOTIVES = ('fear', 'duty', 'hunger', 'thirst', 'kinship', 'promise')
COLORS = ('#E47A62', '#7299EA', '#EABC66', '#63C6DC', '#A488D3', '#7AD6A3')
X0, X1 = -7.5, 7.5
Z0, Z1 = -2.12, 2.30


def build(kit):
    source = {ref.kind: ref.id for ref in kit.references}
    rows = sorted(kit.data(source['data']), key=lambda row: row['day'])
    title = kit.read_text(source['text']).splitlines()[0].lstrip('# ')
    limit = ceil(max(sum(row[k] for k in MOTIVES) for row in rows) / 50) * 50
    first, last = rows[0]['day'], rows[-1]['day']
    panel = kit.material('Textured indigo enamel', '#142239', .58, metallic=.22, bump=(98, .10))
    surround = kit.procedural('Graphite exhibit frame', 'brushed_metal', colors=['#192437', '#2E4355', '#445C68'],
                              scale=1.6, roughness=.38, bump=.06)
    nickel = kit.material('Bead-blasted titanium rail', '#678392', .30, metallic=.65)
    floor = kit.material('Deep blue gallery floor', '#152334', .55, metallic=.2)
    ink = kit.flat('Text white', '#EDF4FA')
    secondary = kit.flat('Annotation slate', '#B0C6DB')
    grid = kit.flat('Fine grid', '#4B5E75')
    accent = kit.emissive('Day marker mint', '#8DE8D4', 1.04)
    kit.ground(floor, z=-4.52, size=85)
    kit.box('Enamel chart body', (17.40, .54, 8.16), (0, .60, .06), panel, bevel=.085)
    for side in (-1, 1):
        kit.box('Machined vertical edge', (.23, .89, 8.58), (side * 8.81, .51, .06), surround, bevel=.10)
        kit.box('Inlaid vertical rail', (.045, .07, 8.10), (side * 8.68, .16, .06), nickel, bevel=.017)
        kit.box('Inset mounting support', (.64, 1.34, .65), (side * 7.0, .62, -4.19), surround, bevel=.105)
        kit.box('Machined horizontal edge', (17.82, .89, .22), (0, .51, .06 + side * 4.19), surround, bevel=.10)
        kit.box('Inlaid horizontal rail', (17.30, .078, .050), (0, .16, .06 + side * 4.05), nickel, bevel=.017)
    kit.box('Rear spine', (14.00, .32, 6.02), (0, 1.04, .06), surround, bevel=.12)

    def label(body, x, z, size=.24, mat=ink, align='CENTER', font=None):
        return kit.text(body, size, (x, -.28, z), material=mat, align=align, font=font)

    kit.svg(source['vector'], .52, .025, accent, (-7.37, -.33, 3.45))
    label(title.upper(), -6.91, 3.48, .67, align='LEFT', font=source['font'])
    label('ACTIONS PER DAY', X0, 2.69, .30, secondary, 'LEFT')
    for number in range(0, limit + 1, 50):
        z = Z0 + (Z1 - Z0) * number / limit
        kit.box(f'Grid {number} actions', (X1 - X0, .012, .014), (0, .26, z), grid)
        if number % 100 == 0 or number == limit:
            label(str(number), X0 - .27, z, .29, secondary, 'RIGHT')
    for day in (1, 30, 60, 90):
        x = kit.lerp(X0, X1, (day - 1) / (last - first))
        kit.box(f'Grid day {day}', (.015, .012, Z1 - Z0), (x, .26, (Z0 + Z1) / 2), grid)
        label(str(day), x, Z0 - .30, .31, secondary)
    label('DAY', 0, Z0 - .67, .28, secondary)

    def progress(t):
        return kit.lerp(X0, X1, kit.segment(t, 0, .79))

    lower = [0] * len(rows)
    for i, (motive, color) in enumerate(zip(MOTIVES, COLORS)):
        upper = [base + row[motive] for base, row in zip(lower, rows)]
        band = kit.material(f'{motive} pigmented relief', color, roughness=.33, coat=.13,
                            metallic=.10, emission=color, emission_strength=.17)
        nodes, links = band.node_tree.nodes, band.node_tree.links
        x = nodes.new('ShaderNodeSeparateXYZ')
        links.new(nodes.new('ShaderNodeNewGeometry').outputs['Position'], x.inputs['Vector'])
        visibility = nodes.new('ShaderNodeMath')
        visibility.operation = 'LESS_THAN'
        links.new(x.outputs['X'], visibility.inputs[0])
        kit.animate(visibility.inputs[1], 'default_value', progress, step=2)
        fade = nodes.new('ShaderNodeMixShader')
        links.new(visibility.outputs[0], fade.inputs[0])
        links.new(nodes.new('ShaderNodeBsdfTransparent').outputs[0], fade.inputs[1])
        links.new(kit.bsdf(band).outputs[0], fade.inputs[2])
        links.new(fade.outputs[0], nodes['Material Output'].inputs['Surface'])
        coords, faces = [], []
        front_y = -.97 + (.080 * i)
        for row, low, high in zip(rows, lower, upper):
            day = X0 + (X1 - X0) * (row['day'] - first) / (last - first)
            bottom = Z0 + (Z1 - Z0) * low / limit
            top = Z0 + (Z1 - Z0) * high / limit
            coords.extend(((day, front_y, bottom), (day, front_y, top), (day, .285, top), (day, .285, bottom)))
        for j in range(len(rows) - 1):
            for side in range(4):
                a = 4 * j + side
                b = 4 * j + (side + 1) % 4
                faces.append((a, a + 4, b + 4, b))
        faces.extend(((0, 1, 2, 3), tuple(range(len(coords) - 1, len(coords) - 5, -1))))
        relief = kit.mesh(f'{motive} stacked daily counts', coords, faces, band)
        # Unrevealed geometry must neither darken nor reflect in the enamel panel.
        relief.visible_shadow = False
        relief.visible_glossy = False
        lower = upper
        legend_x = X0 + 2.54 * i
        kit.box(f'{motive} swatch', (.35, .16, .23), (legend_x, -.21, -3.42), kit.flat(f'{motive} key', color), bevel=.04)
        label(motive.capitalize(), legend_x + .28, -3.42, .40, ink, 'LEFT')

    marker = kit.box('Current day scan line', (.056, .079, Z1 - Z0 + .22), (X0, -1.07, (Z0 + Z1) / 2), accent,
                     bevel=.026)
    kit.animate(marker, 'location', lambda t: (progress(t), -1.07, (Z0 + Z1) / 2), step=2)
    for offset in range(last - first + 1):
        txt = label(f'DAY {1 + offset:02}', X1, 3.47, .54, accent, 'RIGHT')
        if offset == 0:
            keys = [(1, False)]
        else:
            start = ceil(kit.frame(.79 * offset / (last - first)))
            keys = [(1, True), (start, False)]
        if offset < last - first:
            end = ceil(kit.frame(.79 * (offset + 1) / (last - first)))
            keys.append((end, True))
        kit.key(txt, 'hide_render', keys, interpolation='CONSTANT')

    kit.world('#43617C', strength=.20)
    kit.area('Gallery key', (-8, -9, 10), (0, 0, 0), 4000, '#E8F3FF', 11, size_y=8)
    kit.area('Rail highlight', (6, 0, 8), (0, .3, -.2), 2600, '#B2D5FF', 8)
    kit.area('Depth on the glass', (5, -8, 3), (0, 0, 0), 1500, '#FFD9B9', 9)
    camera = kit.camera((17, -22, 5.0), (0, 0, .16), lens=45, ortho_scale=18.5)
    kit.dolly(camera, (17, -22, 5.0), (.18, -25, .48), (0, 0, .16), (0, 0, .19))
    kit.render(view_transform='Standard', motion_blur=False, bounces=4)
    # At shallow angles several hidden relief bands can overlap along one ray before the reveal.
    kit.scene.cycles.transparent_max_bounces = 32
