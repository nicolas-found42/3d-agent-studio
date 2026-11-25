"""Build an overhead café plate with layered pastry, berries, and a looped stirring spoon."""
import math

TAU = math.tau


def build(kit):
    linen = kit.procedural('Oat linen weave', 'fabric', ['#BAA88D', '#DDD0A8', '#E7D8B8'],
                          scale=18, roughness=.82, bump=.3)
    glaze = kit.material('Warm ivory ceramic', '#F7EEE1', .28, coat=.62, bump=(70, .08))
    green = kit.material('Sage side plate', '#6E9277', .29, coat=.45)
    gold = kit.material('Brassy spoon', '#D2AA62', .21, metallic=.88)
    coffee = kit.material('Dark roast coffee', '#38211A', .17, coat=.72)
    crema = kit.material('Crema swirl', '#CC8C42', .32)
    pastry = kit.procedural('Laminated baked dough', 'wood', ['#783621', '#BD6325', '#E8A045', '#FFC16A'],
                            scale=13, roughness=.46, bump=.41)
    crust = kit.material('Flaked shiny pastry glaze', '#D27C36', .29, coat=.31)
    berry = kit.material('Raspberry', '#A62145', .38, subsurface=.21)
    blue = kit.material('Blueberry bloom', '#3C476D', .5, bump=(95, .25))
    jam = kit.material('Blackberry preserves', '#52253E', .32, transmission=.24, coat=.5)
    glass = kit.glass('Jam jar glass', '#F8F7F2', .17)
    kit.ground(linen, 11)
    napkin=kit.procedural('Dusty teal ticking','fabric',['#558689','#80AAAB','#B3C6B5'],
                          scale=20,roughness=.88,bump=.17)
    kit.box('Folded breakfast napkin',(1.82,2.55,.025),(-1.04,-.36,.013),napkin,
            rotation=(0,0,10),bevel=.039)
    kit.lathe('Sage saucer', [(0, 0), (.64, 0), (.79, .045), (.83, .095), (.8, .105), (.63, .05), (0, .05)],
              64, green, (-.94, .61, .027))
    cx, cy = -.94, .61
    kit.lathe('Coffee cup', [(0, .05), (.36, .05), (.39, .09), (.47, .36), (.48, .44), (.456, .448),
                            (.43, .37), (.33, .1), (0, .1)], 72, glaze, (cx, cy, 0))
    kit.torus('Coffee handle', .21, .045, (cx+.52, cy, .25), glaze, rotation=(90, 0, 0))
    kit.cylinder('Coffee surface', .425, .014, (cx, cy, .365), coffee, segments=72)
    for j in range(5):
        pts = [(cx + (.14 + j*.04) * math.cos(i * .115), cy + (.125 + j*.042) * math.sin(i * .115), .375)
               for i in range(7+j*3, 42)]
        kit.tube(f'Crema arc {j}', pts, .011 + .002*(j % 2), crema, resolution=3)
    spoon = kit.empty('Spoon stir axis', (cx, cy, .389))
    kit.tube('Spoon handle', [(.22, 0, 0), (.39, .01, .045), (.66, .01, .11), (.85, 0, .12)],
             .026, gold, resolution=5).parent = spoon
    kit.sphere('Spoon bowl', .13, (.135, 0, -.006), gold, segments=24, rings=12, scale=(1.25, .66, .19)).parent = spoon
    kit.spin(spoon, turns=1)

    kit.lathe('Pastry plate', [(0, 0), (.86, 0), (.98, .06), (1.03, .12), (.99, .14), (.84, .067), (0, .067)],
              72, glaze, (.64, -.58, 0))
    px, py = .62, -.6
    for j in range(15):
        u = j / 14
        angle = -.89 + 1.85 * u
        x, y = px + .86 * math.sin(angle), py + .39 * (1 - math.cos(angle * 2.12))
        r = .078 + .25 * math.sin(math.pi * u)**.65
        dough = kit.sphere(f'Butter layer {j + 1}', r, (x, y, .081 + r * .58), pastry,
                           segments=24, rings=16, scale=(.41, 1.22, .8))
        dough.rotation_euler.z = angle * .57
        for i in range(4):
            z = .09 + r * (1.05 + .037*i)
            kit.tube('Curled pastry flake', [(x-.22*r, y + r * (.16+i*.13), z),
                                             (x, y + r * (.21+i*.13), z+.13*r),
                                             (x+.19*r, y + r * (.22+i*.13), z+.05*r)], .007,
                     crust, resolution=2)

    for i, (x, y) in enumerate(((.35, 1.03), (.6, .85), (.82, .95), (.73, 1.17), (.56, 1.27))):
        for j in range(17):
            a = j * 2.4
            z = (j % 5) * .021
            r = .059 * math.sin(math.pi * (j%5 + 1) / 6)
            kit.sphere(f'Raspberry {i}.{j}', .036, (x+r*math.cos(a), y+r*math.sin(a), .035+z),
                       berry, segments=10, rings=6)
    for i in range(15):
        x, y = kit.rng.uniform(-.44, 1.43), kit.rng.uniform(1.13, 1.52)
        if .32 < x < .9 and y < 1.35:
            y += .27
        kit.sphere(f'Blueberry {i}', .058, (x, y, .053), blue, segments=12, rings=8)
    jx, jy = -1.16, -1.02
    kit.lathe('Jam jar', [(0,0), (.307,0), (.34,.06), (.34,.4), (.28,.48), (.28,.53), (.252,.53),
                         (.255,.45), (.306,.39), (.306,.055), (0,.055)], 64, glass, (jx,jy,0))
    kit.cylinder('Jar of preserves', .302, .37, (jx, jy, .23), jam, segments=48, bevel=.025)
    lid_x, lid_y = jx - .39, jy - .43
    kit.cylinder('Jar brass lid', .295, .075, (lid_x, lid_y, .054), gold, segments=56, bevel=.014)
    for i in range(42):
        angle = math.tau * i/42
        kit.box('Jar lid knurl', (.015,.017,.049), (lid_x+.295*math.cos(angle),lid_y+.295*math.sin(angle),.054),
                gold, rotation=(0,0,math.degrees(angle)))
    steam = kit.emissive('Soft warm steam', '#F6E5CB', .82)
    nt = steam.node_tree
    emit = next(n for n in nt.nodes if n.type == 'EMISSION')
    output = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    clear = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(clear.outputs[0], mix.inputs[1])
    nt.links.new(emit.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], output.inputs['Surface'])
    mix.inputs[0].default_value = .19
    for i in range(3):
        points = [(cx-.17 + .103*i + .059*math.sin(k*.38+i), cy+.07+.061*k, .42+.039*k)
                  for k in range(15)]
        taper = [math.sin(math.pi * (k + 1) / 16)**.64 for k in range(15)]
        wisp = kit.tube(f'Drifting steam thread {i}', points, .039, steam, resolution=3, taper=taper)
        kit.bob(wisp, amplitude=.036, cycles=2, axis='X', phase=i*.5)
    kit.animate(mix.inputs[0], 'default_value', lambda t: .16+.07*math.sin(TAU*2*t), step=3)
    cam = kit.camera((0, 0, 7), (0, 0, 0), ortho_scale=4.35)
    kit.world('#E2EEFF', .44)
    kit.area('Large north-facing window', (-2.6, 2.1, 4.5), (0, 0, 0), 375, '#FFF3D8', 4.5)
    kit.area('Editorial bounce', (2.6, -1, 3), (0, 0, 0), 75, '#D9EDFF', 4)
    kit.render(bounces=5, motion_blur=False)
