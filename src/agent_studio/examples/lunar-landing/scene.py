"""Stage a lunar lander with parabolic dust arcs and a low, immobile witness camera."""
import math

MODULE = 'nasa:3D Models/Apollo Lunar Module/Apollo Lunar Module.glb'
CRATERS = ((-3.5,-1.55,1.15), (3.9,-.61,1.43), (-5.2,3.1,1.9), (5,5,2.2), (-.2,5.1,.81),
           (-3.7,6.8,.84),(1.5,5.6,.63),(-7.5,12.2,2.8),(8.1,11.1,1.5),(-9.5,19.3,4.3),(7,24,3.9))


def build(kit):
    soil = kit.procedural('Crushed lunar regolith', 'stone', ['#393A3E','#827B74','#BAAEA0'],
                          scale=15, roughness=.93, bump=.48)

    def elevation(x, y):
        # Warp the slowly rolling terrain. Avoid repeated ridges from a regular wave grid.
        warp = .28*kit.noise(x*.35, y*.27, .93, octaves=3)
        large = 1.05*kit.noise(x*.108 + warp, y*.126 - warp, 2.2, octaves=4)
        grain = kit.noise(x*1.0, y*.96, 3.2, octaves=3)
        z = (large + .119*grain)*min(1., math.hypot(x,y)/4.3)**2
        for cx, cy, r in CRATERS:
            d = math.hypot(x-cx,y-cy)/r
            skew = 1 + .08*math.sin(7*x + 4.5*y)
            z += r*(-.30*math.exp(-3.6*d*d) + .11*math.exp(-32*(d-skew)**2))
        return z

    width = 151
    verts = [(x,y,elevation(x,y)) for j in range(width) for i in range(width)
             for x,y in [(-23.5 + i*.317,-12.0 + j*.317)]]
    faces = [(j*width+i,j*width+i+1,(j+1)*width+i+1,(j+1)*width+i)
             for j in range(width-1) for i in range(width-1)]
    kit.mesh('Cratered mare', verts, faces, soil, smooth=True, ground=True)
    for i in range(170):
        x, y = kit.rng.uniform(-15,15), kit.rng.uniform(-8,32)
        if math.hypot(x,y) < 2.05:
            continue
        r = kit.rng.uniform(.045,.32)
        kit.rock(f'Regolith breccia {i}', r, (x,y,elevation(x,y)+r*.23),
                 soil, seed=i, detail=2, squash=.53)
    for i in range(90):
        x, y = kit.rng.uniform(-4,4), kit.rng.uniform(-5,4)
        if math.hypot(x,y) < 1.8:
            continue
        r = kit.rng.uniform(.012,.061)
        kit.rock(f'Foreground stone {i}', r, (x,y,elevation(x,y)+r*.2),
                 soil, seed=710+i, detail=1, squash=.61)

    # The public NASA model keeps the assembled leg geometry and foil surfaces editable.
    module = kit.import_model(MODULE, size=3.05, rotation=(0,0,34), name='Apollo lunar module')
    craft = kit.empty('Landing motion')
    kit.parent(module, craft)
    materials = {material for obj in module.children_recursive if obj.type == 'MESH'
                 for material in obj.data.materials if material is not None}
    for material in materials:
        bsdf = kit.bsdf(material)
        red, green, blue, _ = bsdf.inputs['Base Color'].default_value
        if red > .58 and red - blue > .38:
            # Preserve the imported foil pattern while giving it metallic highlights.
            bsdf.inputs['Metallic'].default_value = .72
            bsdf.inputs['Roughness'].default_value = .39
        elif .35 < red < .81 and abs(red - blue) < .08:
            bsdf.inputs['Roughness'].default_value = .49
    kit.key(craft,'location',[(0.,(-.14,.1,2.09)),(.22,(-.09,.07,1.67)),(.55,(.004,0,.58)),
                             (.77,(0,0,0)),(.785,(0,0,-.025)),(.82,(0,0,0)),(1.,(0,0,0))])
    kit.key(craft,'rotation_euler',[(0.,(.014,-.024,.071)),(.66,(0,0,0)),(1.,(0,0,0))])

    dust=kit.material('Sunlit dust grains','#AC9C8F',.91)
    # A thin, expanding veil makes the ballistic grains read as a dust ring at preview size.
    veil=kit.haze(.17,'#D3C0AB',.38,(2.4,2.4,.33),(0,0,.2),name='Touchdown dust veil')
    density=next(node for node in veil.data.materials[0].node_tree.nodes if node.type=='PRINCIPLED_VOLUME').inputs['Density']
    dust_nodes=veil.data.materials[0].node_tree
    coords=dust_nodes.nodes.new('ShaderNodeTexCoord')
    radius_node=dust_nodes.nodes.new('ShaderNodeVectorMath')
    radius_node.operation='DISTANCE'
    radius_node.inputs[1].default_value=(.5,.5,.5)
    falloff = dust_nodes.nodes.new('ShaderNodeValToRGB')
    ramp = falloff.color_ramp.elements
    ramp[0].color = (0,0,0,1)
    ramp[1].color = (0,0,0,1)
    for position, level in ((.12,.02),(.22,.72),(.3,1),(.46,0)):
        ramp.new(position).color = (level,level,level,1)
    amount = dust_nodes.nodes.new('ShaderNodeMath')
    amount.operation = 'MULTIPLY'
    dust_nodes.links.new(coords.outputs['Generated'], radius_node.inputs[0])
    dust_nodes.links.new(radius_node.outputs['Value'], falloff.inputs['Fac'])
    dust_nodes.links.new(falloff.outputs['Color'], amount.inputs[0])
    dust_nodes.links.new(amount.outputs[0], density)
    kit.key(amount.inputs[1], 'default_value', [(0.,0.),(.4,0.),(.64,4.2),(.78,3.4),(.96,0.),(1.,0.)])
    kit.key(veil,'scale',[(0.,(.2,.2,1)),(.47,(.2,.2,1)),(.82,(2.1,2.1,1.6)),(1.,(2.8,2.8,1))])
    for i in range(245):
        angle=kit.rng.uniform(0,math.tau)
        speed=kit.rng.uniform(1.15,4.8)
        start=kit.rng.uniform(.44,.745)
        life=kit.rng.uniform(.16,.33)
        radius=kit.rng.uniform(.007,.024)
        particle=kit.sphere(f'Ballistic dust {i}',radius,(0,0,-.8),dust,segments=6,rings=4)
        def trajectory(t,a=angle,v=speed,start=start,life=life):
            age=max(0.,min(1.,(t-start)/life))
            r=.25+v*age
            x,y=r*math.cos(a),r*math.sin(a)
            z=elevation(x,y)+.31*math.sin(math.pi*age) if start<=t<=start+life else -.8
            return x,y,z
        kit.animate(particle,'location',trajectory,step=2)

    # The tiny blue Earth gives the black sky an independent scale reference.
    earth=kit.material('Earth limb','#1D476D',.86,emission='#1A4274',emission_strength=.12)
    nodes,links=earth.node_tree.nodes,earth.node_tree.links
    terrain=nodes.new('ShaderNodeTexNoise')
    terrain.inputs['Scale'].default_value=4.0
    terrain.inputs['Detail'].default_value=3.0
    continents=nodes.new('ShaderNodeValToRGB')
    ramp=continents.color_ramp.elements
    ramp[0].position=.24
    ramp[0].color=kit.color('#102748')
    ramp[1].position=.72
    ramp[1].color=kit.color('#E4D5B3')
    for stop,color in ((.46,'#234F7C'),(.53,'#5189A5'),(.57,'#8CA08C'),(.61,'#CCCDC3')):
        ramp.new(stop).color=kit.color(color)
    links.new(terrain.outputs['Fac'],continents.inputs[0])
    links.new(continents.outputs['Color'],kit.bsdf(earth).inputs['Base Color'])
    planet=kit.sphere('Distant Earth',1.2,(-18.1,27.5,14.5),earth,segments=48,rings=32)
    planet['studio_ground'] = True  # Keep the far planet outside the lander review bounds.
    kit.world('#000000',0)
    kit.sun(19,247,6.9,'#FFF2E5',.38)
    kit.area('Faint surface bounce', (3,-5,1.4),(0,0,1),110,'#F0EAE6',6)
    kit.camera((3.14,-7.55,1.7),(0,0,2.44),lens=46)
    kit.render(look='AgX - Medium High Contrast', bounces=4)
