"""Build the canyon from irregular basalt benches and animate whitewater along the falls."""
import math
import random

from mathutils import Vector, noise


def build(kit):
    rng = random.Random(kit.brief['seed'])
    rock = kit.textured('Fractured basalt', 'polyhaven:cliff_side@1k', scale=1.34, tint='#9A9B91', roughness=.82, bump=.76)
    moss = kit.textured('Tundra lichen and moss', 'polyhaven:mossy_rock@1k', scale=1.65, tint='#B9D48F',
                        roughness=.90, bump=.53)
    water = kit.procedural('Glacial runoff', 'water', colors=['#163944', '#446F79', '#7A999E'],
                           scale=1.28, roughness=.22, bump=.43)
    foam = kit.material('Aerated whitewater', '#D7E5E8', .29, coat=.13, subsurface=.08)
    nodes, links = foam.node_tree.nodes, foam.node_tree.links
    coord = nodes.new('ShaderNodeTexCoord')
    travel = nodes.new('ShaderNodeMapping')
    travel.inputs['Scale'].default_value = (9, 1.85, 1)
    links.new(coord.outputs['UV'], travel.inputs['Vector'])
    flow = nodes.new('ShaderNodeTexNoise')
    flow.inputs['Scale'].default_value = 3.4
    flow.inputs['Detail'].default_value = 5
    links.new(travel.outputs['Vector'], flow.inputs['Vector'])
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = .23
    ramp.color_ramp.elements[0].color = kit.color('#375661')
    ramp.color_ramp.elements[1].position = .70
    ramp.color_ramp.elements[1].color = kit.color('#EFF7F7')
    links.new(flow.outputs['Fac'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], kit.bsdf(foam).inputs['Base Color'])
    ridges = nodes.new('ShaderNodeBump')
    ridges.inputs['Strength'].default_value = .54
    ridges.inputs['Distance'].default_value = .10
    links.new(flow.outputs['Fac'], ridges.inputs['Height'])
    links.new(ridges.outputs['Normal'], kit.bsdf(foam).inputs['Normal'])
    kit.animate(travel.inputs['Location'], 'default_value', lambda t: (0, -t * 2.8, 0), step=5)

    # A continuous valley surface closes the sides and joins both ledges to the riverbed.
    # Keep displacement shallow at the two lips, where the whitewater leaves the rock.
    def terrain_height(x, y):
        edge = kit.ease(kit.segment(abs(x + .7 * math.sin(y * .09)), 9.0, 22.0), 'smooth')
        distance = abs(x - 1.7)
        edge_detail = kit.ease(kit.segment(distance, 3.3, 14.0), 'smooth')
        cross = (.45 * math.sin(x * .62) + .25 * math.sin(x * .19 + .83)) * edge_detail
        lower = kit.ease(kit.segment(y + cross, 2.18, 3.50), 'smooth')
        upper = kit.ease(kit.segment(y + cross, 9.76, 11.51), 'smooth')
        details = noise.noise(Vector((.81 * x, .86 * y, 3.1))) + .32 * noise.noise(Vector((2.8 * x, 2.8 * y, 3.1)))
        hillside = noise.fractal(Vector((.12 * x, .15 * y, 5.2)), 1.0, 2.0, 4)
        back = kit.ease(kit.segment(y, 12, 29), 'smooth')
        return (-1.68 + 3.69 * lower + 6.20 * upper + (0.53 + .48 * edge_detail) * details
                + edge * (2.88 + 2.45 * hillside) + back * (1.6 + 4.1 * hillside))

    x_steps, y_steps = 180, 184
    xs = [kit.lerp(-39, 39, i / x_steps) for i in range(x_steps + 1)]
    ys = [kit.lerp(-30, 45, j / y_steps) for j in range(y_steps + 1)]
    vertices = [(x, y, terrain_height(x, y)) for y in ys for x in xs]
    stride = x_steps + 1
    faces = [(j * stride + i, j * stride + i + 1, (j + 1) * stride + i + 1, (j + 1) * stride + i)
             for j in range(y_steps) for i in range(x_steps)]
    valley = rock.copy()
    valley.name = 'Basalt and growing moss'
    canyon = kit.mesh('Continuous basalt valley', vertices, faces, valley, smooth=True)
    weights = canyon.data.attributes.new('moss coverage', 'FLOAT', 'POINT')
    for index, (x, y, z) in enumerate(vertices):
        steep = abs(terrain_height(x, y + .12) - terrain_height(x, y - .12)) / .24
        lichens = noise.noise(Vector((x * .53, y * .51, 2.18)))
        shallow = 1.0 - kit.ease(kit.segment(steep, .2, 2.1), 'smooth')
        patch = kit.ease(kit.segment(lichens + .42 * shallow, .05, .58), 'smooth')
        shore = max(kit.segment(y, 11.7, 13.4), kit.segment(abs(x - 1.4), 4.4, 6.8))
        weights.data[index].value = patch * shore * kit.ease(kit.segment(z, -.16, .40), 'smooth')
    nodes, links = valley.node_tree.nodes, valley.node_tree.links
    base = kit.bsdf(valley).inputs['Base Color']
    rock_color = base.links[0].from_socket
    coverage = nodes.new('ShaderNodeAttribute')
    coverage.attribute_name = weights.name
    moss_texture = nodes.new('ShaderNodeTexImage')
    moss_texture.image = next(node.image for node in moss.node_tree.nodes if node.type == 'TEX_IMAGE')
    moss_texture.projection, moss_texture.projection_blend = 'BOX', .35
    mapped = next(node for node in nodes if node.type == 'MAPPING')
    links.new(mapped.outputs['Vector'], moss_texture.inputs['Vector'])
    mix = nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    links.new(coverage.outputs['Fac'], mix.inputs['Factor'])
    links.new(rock_color, mix.inputs['A'])
    links.new(moss_texture.outputs['Color'], mix.inputs['B'])
    links.new(mix.outputs['Result'], base)
    for row, z in enumerate((3.25, 4.78, 6.12, 7.39)):
        for i in range(33):
            x = -20 + i * 1.24 + rng.uniform(-.53, .53)
            if -.1 < x < 4.4:
                continue
            surface_z = z + rng.uniform(-.24, .24)
            near, far = 8.8, 12.5
            if terrain_height(x, near) >= surface_z:
                continue
            for _ in range(10):
                middle = (near + far) / 2
                if terrain_height(x, middle) < surface_z:
                    near = middle
                else:
                    far = middle
            column = kit.rock(f'Exposed basalt column {row}.{i}', rng.uniform(.31, .91),
                              (x, far, surface_z), moss if i % 5 == 2 else rock,
                              squash=rng.uniform(.46, .90), detail=2, roughness=.38)
            column.scale.y = rng.uniform(.69, 1.0)

    def surface(name, points, widths, material, phase):
        cols = 34
        vertices = []
        # Subdivide each span with a cubic interpolation to remove visible fold lines.
        sections = [Vector((*point, width)) for point, width in zip(points, widths)]
        dense = []
        for i in range(len(sections) - 1):
            a, b = sections[max(0, i - 1)], sections[i]
            c, d = sections[i + 1], sections[min(i + 2, len(sections) - 1)]
            for j in range(6):
                t = j / 6
                dense.append(b + .5 * ((c - a) * t + (2 * a - 5 * b + 4 * c - d) * t * t
                                       + (-a + 3 * b - 3 * c + d) * t ** 3))
        dense.append(sections[-1])
        for row, (cx, cy, cz, width) in enumerate(dense):
            for col in range(cols):
                u = col / (cols - 1)
                edge = .10 * math.sin(row * .58 + phase) + .06 * math.cos(row * 1.71 + phase)
                x = cx + (u - .5) * width * (1 + edge)
                flutes = .08 * math.sin(u * 113 + phase + row * .13) + .05 * math.sin(u * 54 + row * .21)
                vertices.append((x, cy + flutes, cz + flutes * .42))
        quads = [(r * cols + c, r * cols + c + 1, (r + 1) * cols + c + 1, (r + 1) * cols + c)
                 for r in range(len(dense) - 1) for c in range(cols - 1)]
        flow_sheet = kit.mesh(name, vertices, quads, material, smooth=True)
        mesh = flow_sheet.data
        uv = mesh.uv_layers.new(name='Across and downstream')
        for loop in mesh.loops:
            row, col = divmod(loop.vertex_index, cols)
            uv.data[loop.index].uv = (col / (cols - 1), row / (len(dense) - 1))
        return flow_sheet

    # Narrow upper sheets can be read against dark rock; the lower run splits over a shelf.
    high = [(3.0, 15, 8.57), (2.99, 12.7, 8.61), (2.93, 11.0, 8.37), (2.8, 10.1, 7.51),
            (2.67, 9.80, 6.26), (2.53, 9.65, 4.8), (2.4, 9.35, 3.35), (2.3, 8.92, 2.17)]
    surface('Upper ribbon', high, [1.1, .91, .89, .94, 1.06, 1.16, 1.32, 1.85], foam, 0)
    surface('Thin neighboring runnel', [(x - 2.0, y + .15, z - .03) for x, y, z in high[2:]],
            [.11, .12, .16, .21, .34, .53], foam, 1.36)
    low = [(1.6, 10.2, 2.24), (1.38, 7.1, 2.21), (.67, 5.4, 2.23), (.13, 3.34, 2.17),
           (0, 2.81, 1.92), (-.12, 2.49, 1.39), (-.18, 2.30, .76), (-.22, 2.06, .35), (-.27, 1.63, .04)]
    # Stagger the curtain into channels around the basalt noses and soften the foot with spray.
    for offset, span, phase in ((-3.18, 2.25, .4), (-.49, 3.02, 2.15), (2.83, 2.88, 4.1)):
        channel = [(x + offset * (.78 + .26 * i / 8), y + .15 * offset, z + .035 * offset)
                   for i, (x, y, z) in enumerate(low)]
        surface(f'Lower cataract channel {phase}', channel,
                [span * factor for factor in (.70, .82, .99, 1, .91, .89, .97, 1.02, 1.18)], foam, phase)
    kit.plane('Glacial pool', (67, 51), (0, -12, -.025), water, ground=True)
    wake = kit.material('Broken white foam on the pool', '#A6C5C6', .41)
    for i in range(42):
        x, flow_offset = rng.uniform(-5.4, 5.4), rng.random()
        z = .04 + rng.uniform(0, .015)
        length = rng.uniform(.12, .58)
        streak = kit.tube(f'Broken water foam {i}', [(-length, 0, 0), (-length * .21, -.13, .009),
                                                    (length * .52, -.20, .006), (length, -.24, 0)],
                          rng.uniform(.008, .018), wake, resolution=3, taper=[.06, 1, .78, .04])
        kit.animate(streak, 'location', lambda t, x=x, z=z, offset=flow_offset: (
            x + .30 * math.sin(math.tau * (t + offset)), 1.95 - 7.0 * ((t * .8 + offset) % 1), z), step=1)
        kit.animate(streak, 'scale', lambda t, offset=flow_offset: (max(.001, math.sin(math.pi * ((t * .8 + offset) % 1))),) * 3,
                    step=1)
    droplet = kit.material('Suspended splash', '#D4E7E8', .28, transmission=.25)
    for i in range(108):
        x, p = rng.uniform(-4.6, 4.6), rng.random()
        reach = rng.uniform(.22, 1.26)
        bead = kit.ico(f'Cataract splash {i}', rng.uniform(.019, .046), (0, 0, 0), droplet, subdivisions=1)

        def spray(t, x=x, p=p, reach=reach):
            q = (t * 4 + p) % 1.0
            return (x - .45 * q, 1.94 - 1.8 * q, .06 + math.sin(math.pi * q) * reach)

        kit.animate(bead, 'location', spray, step=1)
    model = next(r.id for r in kit.references if r.kind == 'model')
    marker_x, marker_y = 8.1, -7.8
    marker = kit.import_model(model, (marker_x, marker_y, terrain_height(marker_x, marker_y)),
                              rotation=(0, 0, -20), size=3.40)
    for obj in marker.children_recursive:
        if obj.type == 'MESH':
            obj.data.materials.append(rock)
    for i in range(90):
        right_bank = i >= 34
        x = rng.uniform(7, 28) if right_bank else rng.uniform(-24, -8.0)
        y = rng.uniform(-14, 20)
        radius = rng.uniform(.17, 1.05)
        z = terrain_height(x, y) + .15 * radius
        stone = kit.rock(f'Basalt scree {i:03}', radius, (x, y, z), rock if i % 7 else moss, detail=2)
        stone.scale = (1.18, rng.uniform(.66, 1.42), rng.uniform(.55, .91))
    stalk = kit.material('Sunlit sedge and heath', '#67763D', .84)
    blades, leaves = [], []
    for i in range(360):
        x = rng.choice((rng.uniform(-14, -7), rng.uniform(8, 17)))
        y = rng.uniform(-13, 21)
        z = terrain_height(x, y)
        if z < .11:
            continue
        for _ in range(3):
            a = rng.uniform(0, math.tau)
            bend, length = rng.uniform(.03, .14), rng.uniform(.16, .48)
            px, py = x + rng.uniform(-.11, .11), y + rng.uniform(-.12, .12)
            idx = len(blades)
            blades.extend(((px - .017, py, z), (px + .017, py, z),
                           (px + bend * math.cos(a), py + bend * math.sin(a), z + length)))
            leaves.append((idx, idx + 1, idx + 2))
    kit.mesh('Tufts on the local banks', blades, leaves, stalk)
    for i, (x, span) in enumerate(((-3.3, 3.2), (0, 4.2), (2.7, 3.4))):
        mist = kit.haze(.20, '#D9E9F0', anisotropy=.35, size=(span, 3.1, 2.5), location=(x, 1.4, .64),
                        name=f'Broken drift of spray {i}')
        drift = mist.data.materials[0].node_tree
        coord = drift.nodes.new('ShaderNodeTexCoord')
        distance = drift.nodes.new('ShaderNodeVectorMath')
        distance.operation = 'DISTANCE'
        distance.inputs[1].default_value = (.5, .5, .40)
        drift.links.new(coord.outputs['Generated'], distance.inputs[0])
        density = drift.nodes.new('ShaderNodeMapRange')
        density.inputs['From Min'].default_value = .13
        density.inputs['From Max'].default_value = .52
        density.inputs['To Min'].default_value = .31
        density.inputs['To Max'].default_value = 0
        drift.links.new(distance.outputs['Value'], density.inputs['Value'])
        volume = next(node for node in drift.nodes if node.type == 'PRINCIPLED_VOLUME')
        drift.links.new(density.outputs['Result'], volume.inputs['Density'])
        kit.animate(mist, 'location', lambda t, x=x, i=i: (
            x + .95 * t, 1.4 - .54 * t, .68 + .16 * math.sin(t * 6 + i)), step=6)
    kit.haze(.0036, '#D5E6F2', size=(34, 23, 14), location=(0, 1.5, 6.0))
    kit.hdri('polyhaven:kloofendal_48d_partly_cloudy_puresky@1k', strength=.57, rotation=148)
    kit.sun(38, -48, 1.2, '#FFF0D9', 19)
    kit.area('Cold overcast fill', (-9, -10, 18), (0, 6, 3.5), 4850, '#C0D9F5', 11)
    cam = kit.camera((11.7, -18.2, 4.32), (1.8, 6.8, 4.85), lens=33)
    kit.dolly(cam, (11.7, -18.2, 4.32), (7.2, -14.8, 4.75), (1.8, 6.8, 4.85), (1.4, 6.85, 4.72))
    kit.render(exposure=.24, bounces=6)
