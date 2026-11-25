"""A close orbital passage across foreground ring ice and a banded gas giant."""
import math

PLANET_RADIUS = 3.2
RINGS = ((3.91,4.11,'#787576'),(4.16,4.55,'#A39991'),(4.58,5.05,'#BDB2A3'),
         (5.07,5.25,'#4F535B'),(5.33,5.96,'#C1B6A5'),(6.0,6.33,'#756E6D'),
         (6.4,6.85,'#9E958A'),(6.94,7.18,'#716A65'))


def build(kit):
    planet = kit.material('Hydrogen cloud bands', '#D2B790', .88)
    tree = planet.node_tree
    nodes, links = tree.nodes, tree.links
    coord=nodes.new('ShaderNodeTexCoord')
    multiply=nodes.new('ShaderNodeVectorMath')
    multiply.operation='MULTIPLY'
    multiply.inputs[1].default_value=(3,3,22)
    noise=nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value=3.5
    noise.inputs['Detail'].default_value=5
    waves=nodes.new('ShaderNodeTexWave')
    waves.wave_type='BANDS'
    waves.bands_direction='Z'
    waves.inputs['Scale'].default_value=6.4
    waves.inputs['Distortion'].default_value=4.2
    waves.inputs['Detail Scale'].default_value=1.2
    blend=nodes.new('ShaderNodeMixRGB')
    blend.blend_type='MULTIPLY'
    blend.inputs[0].default_value=.29
    ramp_node=nodes.new('ShaderNodeValToRGB')
    ramp=ramp_node.color_ramp
    ramp.elements[0].color=kit.color('#554451')
    ramp.elements[1].color=kit.color('#CFAD80')
    for pos,hue in ((.19,'#8C6E60'),(.36,'#BF9473'),(.54,'#ECD7AC'),
                    (.70,'#AB8066'),(.87,'#F6DFB6')):
        ramp.elements.new(pos).color=kit.color(hue)
    for first,second in ((coord.outputs['Generated'],multiply.inputs[0]),
                         (coord.outputs['Generated'],waves.inputs['Vector']),
                         (multiply.outputs[0],noise.inputs[0]),(waves.outputs['Fac'],blend.inputs[1]),
                         (noise.outputs['Fac'],blend.inputs[2]),(blend.outputs[0],ramp_node.inputs[0]),
                         (ramp_node.outputs['Color'],kit.bsdf(planet).inputs['Base Color'])):
        links.new(first,second)
    kit.sphere('Banded gas giant', PLANET_RADIUS, material=planet, segments=112,rings=64,scale=(1,1,.94))

    for index,(inner,outer,hue) in enumerate(RINGS):
        mat=kit.procedural(f'Icy ring striation {index}', 'stone',[hue,'#A69B91',hue],scale=3.4,roughness=.82,bump=.12)
        verts=[]
        for i in range(256):
            theta=math.tau*i/256
            for radius in (inner,outer):
                verts.append((radius*math.cos(theta),radius*math.sin(theta),0))
        faces=[(2*i,2*i+1,(2*i+3)%512,(2*i+2)%512) for i in range(256)]
        kit.mesh(f'Ring band {index+1}',verts,faces,mat)
    ice=kit.procedural('Rock and ice fragments','stone',['#575253','#BEB6AA','#E8E0CE'],
                       scale=5.0,roughness=.77,bump=.25)
    for i in range(340):
        a=kit.rng.uniform(-2.6,.4)
        radius=kit.rng.uniform(4.5,7.22)
        size=kit.rng.uniform(.013,.092)*(1.6 if i<35 else 1)
        kit.rock(f'Ring ice fragment {i}', size, (radius*math.cos(a),radius*math.sin(a),kit.rng.uniform(-.13,.125)),
                 material=ice,seed=i,squash=.67,detail=1)
    star=kit.emissive('Distant stars','#EBECFF',2.7)
    for i in range(170):
        x,z=kit.rng.uniform(-35,35),kit.rng.uniform(-16,20)
        kit.sphere(f'Star {i}',kit.rng.uniform(.014,.032),(x,22,z),star,segments=6,rings=4)
    kit.world('#02040A',.06)
    kit.sun(20,228,4.6,'#FFF2E2',.6)
    cam=kit.camera((6.4,-9.3,.92),(0,0,.13),lens=23)
    kit.path(cam,[(6.4,-9.3,.92),(3.9,-6.35,.2),(1.8,-5.66,.63),(.1,-7,2.8)],
             targets=[(0,0,.1),(0,0,.1),(0,0,.18),(0,0,.18)],ease_kind='linear')
    kit.zoom(cam, 23, 26)
    kit.render(bounces=4)
