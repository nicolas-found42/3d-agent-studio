"""A cinematic black-hole illustration with an animated disc and emissive lensing arcs."""
import math

TAU = math.tau


def annulus(kit, name, low, high, material):
    radial = 20
    angular = 192
    verts, faces = [], []
    for i in range(radial + 1):
        r = low + (high - low) * i / radial
        for j in range(angular):
            a = TAU * j / angular
            verts.append((r * math.cos(a), r * math.sin(a), 0))
    for i in range(radial):
        for j in range(angular):
            a=i*angular+j
            b=i*angular+(j+1)%angular
            faces.append((a,b,b+angular,a+angular))
    return kit.mesh(name, verts, faces, material)


def build(kit):
    mat = kit.emissive('Turbulent disc plasma', '#FFE7A9', 7.4)
    tree = mat.node_tree
    nodes, links = tree.nodes, tree.links
    coord = nodes.new('ShaderNodeTexCoord').outputs['Object']
    radius = nodes.new('ShaderNodeVectorMath')
    radius.operation = 'LENGTH'
    links.new(coord, radius.inputs[0])
    normalized = nodes.new('ShaderNodeMapRange')
    normalized.inputs['From Min'].default_value = 1.25
    normalized.inputs['From Max'].default_value = 3.78
    links.new(radius.outputs['Value'], normalized.inputs['Value'])
    color = nodes.new('ShaderNodeValToRGB')
    elements = color.color_ramp.elements
    elements[0].color = kit.color('#FFF9D3')
    elements[1].color = kit.color('#000000')
    for p, hue in ((.12, '#FFD178'), (.3, '#E67335'), (.56, '#8A2F15'), (.81, '#2B1107')):
        elements.new(p).color = kit.color(hue)
    links.new(normalized.outputs[0], color.inputs[0])

    def expression(operation, *operands):
        node = nodes.new('ShaderNodeMath')
        node.operation = operation
        for i, value in enumerate(operands):
            if isinstance(value, (int, float)):
                node.inputs[i].default_value = value
            else:
                links.new(value, node.inputs[i])
        return node.outputs[0]

    mapping = nodes.new('ShaderNodeMapping')
    links.new(coord, mapping.inputs[0])
    kit.animate(mapping.inputs['Rotation'], 'default_value', lambda t: (0, 0, -TAU * t), step=2)
    turbulence = nodes.new('ShaderNodeTexNoise')
    turbulence.inputs['Scale'].default_value = 6.5
    turbulence.inputs['Detail'].default_value = 4
    links.new(mapping.outputs[0], turbulence.inputs[0])
    sep = nodes.new('ShaderNodeSeparateXYZ')
    links.new(mapping.outputs[0], sep.inputs['Vector'])
    angle = expression('ARCTAN2', sep.outputs['Y'], sep.outputs['X'])
    radial_phase = expression('MULTIPLY_ADD', radius.outputs['Value'], 34, 0)
    angular_phase = expression('MULTIPLY_ADD', angle, 3, radial_phase)
    turbulent_phase = expression('MULTIPLY_ADD', turbulence.outputs['Fac'], 7, angular_phase)
    intensity = expression('MULTIPLY_ADD', expression('SINE', turbulent_phase), 1.15, 3.1)
    emit = next(node for node in nodes if node.type == 'EMISSION')
    links.new(intensity, emit.inputs['Strength'])
    links.new(color.outputs['Color'], emit.inputs['Color'])
    annulus(kit, 'Continuous accretion disk', 1.25, 3.78, mat)
    dark=kit.emissive('Event horizon matte black','#000000',0)
    kit.sphere('Event horizon shadow',1.24,material=dark,segments=96,rings=56)
    photon=kit.emissive('Hot photon ring','#FFE5A9',6.8)
    lens=kit.emissive('Lensed rear of disc','#EB8434',1.7)
    ghost=kit.emissive('Soft outer lensing bands','#A74E22',.58)
    group=kit.empty('Lensing arcs track camera azimuth')
    for i,(r,diam,material) in enumerate(((1.277,.014,photon),(1.37,.037,lens),(1.49,.034,lens),
                                         (1.61,.019,ghost),(1.74,.014,ghost),(1.81,.008,ghost))):
        pts=[]
        samples=144 if i==0 else 88
        for j in range(samples+1):
            a=TAU*j/samples if i==0 else -.12+(math.pi+.24)*j/samples
            pts.append((r*math.cos(a),0,r*math.sin(a)*(1 if i==0 else .96)))
        kit.tube(f'Optical arc {i}',pts,diam,material,resolution=4).parent=group
        if i in (2,3,4):
            kit.tube(f'Lower lensed reflection {i}', [(x, -.009, -.89*z) for x,_,z in pts],
                     diam*.58,ghost,resolution=4).parent=group
    n=96
    colors=[kit.emissive('Far bright star','#FFF4EC',1.4),kit.emissive('Far blue star','#AACBF2',1.25)]
    for i in range(n):
        z=kit.rng.uniform(-21,21)
        a=kit.rng.uniform(0,TAU)
        kit.sphere(f'Background star {i}',kit.rng.uniform(.022,.057),(22*math.cos(a),22*math.sin(a),z),
                   colors[i%2],segments=6,rings=4)
    kit.world('#03040A',.19)
    cam=kit.camera((0,-10,3.4),(0,0,0),lens=46)
    def swing(t):
        return .34*math.sin(TAU*t)
    kit.animate(cam,'location',lambda t:(10*math.sin(swing(t)),-10*math.cos(swing(t)),
                                          3.25+.55*math.sin(TAU*t)),step=2)
    kit.animate(group,'rotation_euler',lambda t:(-.31-.045*math.sin(TAU*t),0,swing(t)),step=2)
    kit.render(bounces=3, exposure=-.18, motion_blur=False)
