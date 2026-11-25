"""Dimensional poster lettering with color cues, impact easing, and framing cuts."""
import math

WORDS = ('MAKE', 'THINGS', 'MOVE')
FONT = 'fontsource:archivo-black@400'
PALETTE = ('#FF6548', '#FFCD36', '#51DCC4')
BACK = ('#843B57', '#AB581E', '#1B777D')


def build(kit):
    panel = kit.material('Cobalt screen-print board', '#223988', .67, coat=.23, bump=(112,.12))
    well = kit.material('Ink-black case', '#111832', .64, metallic=.13)
    edge = kit.material('Indigo case fronts', '#4658AA', .55, metallic=.21)
    dots = kit.flat('Silkscreen grid', '#4B61A8')
    ivory = kit.material('Ivory paper letter faces', '#FFF0D4', .32, coat=.28, bump=(89,.085))

    # A deep powder-coated cabinet backs the artwork and catches the grazing light in the angle proof.
    kit.box('Display cabinet', (6.95,.84,11.78), (0,1.41,0), well, bevel=.14)
    kit.box('Blue poster stock', (6.81,.12,11.62), (0,.927,0), panel, bevel=.035)
    kit.box('Recessed foot', (7.5,2.75,.45), (0,1.25,-5.9), well, bevel=.13)
    kit.box('Low studio platform', (23,18,.24), (0,2,-6.24), edge, bevel=.1, ground=True)
    for s in (-1,1):
        kit.box('Anodized cabinet edge',(.08,.11,11.48),(s*3.28,.83,0),edge,bevel=.014)
        for r in (-4.8,-2.4,0,2.4,4.8):
            kit.cylinder('Anodized screw',.036,.019,(s*3.28,.766,r),ivory,
                         rotation=(90,0,0),segments=12)
    for col in range(8):
        for row in range(13):
            kit.cylinder('Printed halftone dot',.022,.002,(-2.5+.72*col,.865,-4.45+.74*row),
                         dots,rotation=(90,0,0),segments=8)
    swatches = [kit.material(f'Graphic color field {i+1}',color,.43,coat=.28,bump=(105,.08)) for i,color in enumerate(PALETTE)]

    def semicircle(name, x, z, r, thickness, orientation, material):
        positions=[]
        for i in range(46):
            angle=orientation+math.pi*i/45
            for distance in (r-thickness,r):
                positions.append((x+distance*math.cos(angle),.772,z+distance*math.sin(angle)))
        quads=[(2*i,2*i+1,2*i+3,2*i+2) for i in range(45)]
        motif=kit.mesh(name,positions,quads,material)
        kit.solidify(motif,.058)
        kit.bevel(motif,.011,2)

    # Half rings enter from the edges and mark the three distinct acts without extra copy.
    semicircle('Coral crown print',-1.88,3.52,1.71,.32,-.74,swatches[0])
    semicircle('Coral crown accent',-1.88,3.52,1.13,.07,-.74,swatches[0])
    semicircle('Amber hinge print',1.67,.17,1.68,.25,1.43,swatches[1])
    semicircle('Amber hinge accent',1.67,.17,1.10,.07,1.43,swatches[1])
    semicircle('Jade rising print',-1.54,-3.21,1.68,.3,-.42,swatches[2])
    semicircle('Jade rising accent',-1.54,-3.21,.97,.09,-.42,swatches[2])
    for i in range(6):
        x=.75+i*.21
        kit.box('Ink registration hatch',(.34,.023,.025),(x,.79,-3.69-i*.13),swatches[2],
                rotation=(0,0,0),bevel=.003)

    for i,(word,hue) in enumerate(zip(WORDS,PALETTE)):
        z = 1.78 - 1.78*i
        cue = .035 + .236*i
        s = 1 if i%2==0 else -1
        root=kit.empty(f'{word} stage rig')
        back=kit.material(f'{word} printed extrusion',BACK[i],.48)
        tint=swatches[i]
        # Separate color channels on the glyphs and one short, cut-corner base.
        glyph=kit.text(word,1.32,(0,-.285,-.079),material=ivory,font=FONT,extrude=.16,bevel=.037)
        glyph.scale.x=(1.05,.84,1.06)[i]
        glyph.parent=root
        shade=kit.text(word,1.32,(.07,-.05,-.128),material=back,font=FONT,extrude=.17,bevel=.022)
        shade.scale.x=glyph.scale.x
        shade.parent=root
        shape=[(-2.28,-.61),(2.05,-.61),(2.32,-.35),(2.32,.63),(-1.98,.63),(-2.28,.35)]
        # Local extrusion uses Z; the 90-degree transform stands the card into the XZ plane.
        tile=kit.extrude('Press plate with chamfered corners',shape,.108,tint,(0,.068,0),
                         rotation=(90,0,0),bevel=.027)
        tile.parent=root
        for x in (-2.05,2.08):
            mark=kit.cylinder('Pressed-in rivet',.043,.031,(x,-.052,.44),back,
                              rotation=(90,0,0),segments=14)
            mark.parent=root
        initial=(.04,-.51,z) if i==0 else (s*2.17,.21,z+.43)
        rotation=(.18,-.14,.22) if i==0 else (.15,s*.65,s*.42)
        kit.key(root,'location',[(0.,initial),(cue,initial),(cue+.13,(-s*.24,.063,z-.113)),
                                (cue+.21,(0,0,z)),(1.,(0,0,z))])
        kit.key(root,'rotation_euler',[(0.,rotation),(cue,rotation),(cue+.118,(-.105,-s*.088,-s*.043)),
                                     (cue+.205,(.016,s*.038,0)),(1.,(.016,s*.038,0))])
        if i:
            for obj in root.children:
                kit.visible(obj,cue+.02,1.)

    cam=kit.camera((.66,-4.8,1.22),(0,0,.95),ortho_scale=9.72)
    cues=[(0.,.95,9.52),(.225,.95,9.42),(.234,.39,9.82),(.455,.39,9.71),
          (.462,0,10.09),(.739,0,10.00),(.748,0,9.66),(1.,0,9.45)]
    kit.key(cam,'location',[(t,(.66-.56*t,-4.8,z+.26)) for t,z,size in cues],interpolation='LINEAR')
    kit.key(kit.target_of(cam),'location',[(t,(0,0,z)) for t,z,size in cues],interpolation='LINEAR')
    kit.key(cam.data,'ortho_scale',[(t,size) for t,z,size in cues],interpolation='LINEAR')
    kit.world('#BECCE7',.12)
    kit.area('Warm grazed key',(-2.8,-2.8,4.25),(0,.05,0),470,'#FFF0D8',2.2,size_y=4.8)
    kit.area('Cool fill',(3.65,-2.8,-1.9),(0,0,0),170,'#B4CAFF',3.4)
    kit.area('Cabinet side rim',(4.15,.75,3.2),(0,1,0),195,'#EEE3FF',2.2,size_y=5.2)
    kit.render(look='AgX - Medium High Contrast',bounces=4,motion_blur=True,shutter=.24)
