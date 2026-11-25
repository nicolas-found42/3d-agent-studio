"""An old-master tabletop built from hollow vessels, folded linen and hand-placed fruit."""
import math

TAU = math.tau


def build(kit):
    walnut = kit.procedural('Dark oak tabletop', 'wood', ['#241615','#39231A','#61402B'],
                            scale=2.6, roughness=.36, bump=.18)
    linen = kit.procedural('Warm embroidered linen', 'fabric', ['#A89479','#D5BB97','#E1CAA7'],
                           scale=23, roughness=.82, bump=.41)
    pewter = kit.material('Soft tarnished silver', '#B5A28F', .29, metallic=.95, bump=(68,.16))
    leaf = kit.material('Vine leaf', '#50572A', .62, subsurface=.13)
    stem = kit.material('Dried woody stems', '#755536', .71)
    rind = kit.material('Lemon peel', '#E2A92C', .42, coat=.16, bump=(70,.56))
    pith = kit.material('White lemon pith', '#FFF1BA', .57, subsurface=.14)
    pulp = kit.material('Fresh cut pulp', '#E1BA4D', .31, coat=.52, subsurface=.18)
    glass = kit.glass('Roemer glass', '#F7FAEE', .045, 1.48)
    wine = kit.material('Amber wine', '#BC7934', .11, transmission=.84, ior=1.34)
    candle = kit.material('Warm beeswax', '#C8A670', .36, subsurface=.24, bump=(31,.18))
    grape_colors = [
        kit.material(f'Grape wax bloom {i}', h, .38, subsurface=.19, coat=.18, bump=(81,.08))
        for i, h in enumerate(('#4B2E43', '#644359', '#6E505C', '#716748', '#81744B', '#938155'))]
    kit.box('Heavy tabletop', (5.2,3.2,.18), (0,0,-.1), walnut, bevel=.028, ground=True)
    kit.box('Table edge apron', (5.2,.14,.35), (0,-1.53,-.25), walnut, bevel=.03)
    backdrop = kit.procedural('Brown limewash', 'concrete', ['#160F0F','#231916','#3E2821'],
                              scale=.36, roughness=.84, bump=.18)
    kit.box('Shadowed back wall', (10,.14,8), (0,2.6,2.7), backdrop, ground=True)
    verts, faces = [], []
    for row in range(37):
        y = -2.04 + row * .077
        for col in range(27):
            x = -2.05 + col * .083
            front = max(0, -1.59-y)
            z = max(.002, .028 + .038*math.sin(11*x + y*1.5) + .019*math.sin(17*y-8*x))
            verts.append((x + .12*math.sin(y*1.6), max(-1.64,y), z-front*.93))
            if row and col:
                n = len(verts)-1
                faces.append((n-28,n-27,n,n-1))
    drape = kit.mesh('Linen rumpled over the table edge', verts, faces, linen, smooth=True)
    kit.solidify(drape, .012)

    jx,jy = -.68,.39
    profile = [(0,0), (.27,0), (.32,.035), (.29,.18), (.39,.31), (.44,.59), (.38,.9),
               (.24,1.12), (.155,1.18), (.16,1.37), (.23,1.42), (.231,1.47), (.202,1.49),
               (.14,1.38), (.132,1.19), (.22,1.09), (.34,.86), (.37,.59), (.34,.36), (.25,.17), (0,.058)]
    kit.lathe('Hand-raised silver jug', profile, 96, pewter, (jx,jy,.04))
    for z, r in ((.1,.279), (.34,.383), (1.29,.159)):
        kit.torus('Chased metal band', r,.013,(jx,jy,z+.04),pewter,segments=56,sides=10)
    kit.tube('Cast jug handle', [(jx-.23,jy,1.2),(jx-.46,jy,1.26),(jx-.66,jy,1.14),
                                (jx-.73,jy,.97),(jx-.66,jy,.64),(jx-.46,jy,.51),(jx-.36,jy,.51)], .055, pewter)

    gx,gy = .60,.30
    glass_profile = [(0,0),(.22,0),(.225,.034),(.125,.061),(.117,.41),(.21,.459),(.245,.58),
                     (.241,.76),(.233,.775),(.222,.758),(.226,.58),(.196,.48),(.104,.424),(.102,.08),(0,.046)]
    kit.lathe('Prunted wine roemer', glass_profile, 64, glass, (gx,gy,.04))
    kit.lathe('Wine and meniscus', [(0,.46),(.177,.468),(.219,.55),(.226,.65),(.211,.643),(0,.643)],
              64,wine,(gx,gy,.04))
    for i in range(9):
        a = TAU*i/9
        kit.sphere('Roemer stem prunt', .052, (gx+.112*math.cos(a),gy+.112*math.sin(a),.293),
                   glass,segments=11,rings=7)

    kit.lathe('Shallow pewter salver', [(0,0),(.52,0),(.67,.05),(.69,.09),(.65,.103),(.51,.05),(0,.05)],
                        64,pewter,(.12,-.7,0))
    kit.sphere('Half-peeled lemon', .214, (.02,-.77,.223), rind, segments=36,rings=20,scale=(1.36,.86,.86))
    kit.cylinder('Cut lemon pith', .174,.024,(.18,-.77,.251),pith,rotation=(0,61,0),segments=48)
    kit.cylinder('Wet lemon flesh', .157,.026,(.191,-.77,.256),pulp,rotation=(0,61,0),segments=48)
    for j in range(9):
        theta = TAU*j/9
        c,s = math.cos(theta),math.sin(theta)
        kit.tube('Pith membrane', [(.207,-.77,.268),(.207+.064*c,-.77+.145*s,.268-.128*c)], .005, pith,
                 resolution=2)
    peel = [(.02+.078*math.sin(k*.25),-.52-.038*k,.06+.197*math.exp(-k*.06)+.07*math.sin(k*.22))
            for k in range(21)]
    kit.tube('Curl of lemon rind',peel,.023,rind,taper=[.95-(i*.021) for i in range(21)],resolution=4)

    for center, lo in (((-.64,-.52),0), ((.67,-.61),3)):
        for i in range(35):
            a = i*2.399
            radius = .36*math.sqrt(i/35)
            x,y = center[0]+radius*math.cos(a),center[1]+.73*radius*math.sin(a)
            z = .12 + .24*(1-i/35) + kit.rng.uniform(-.04,.05)
            kit.sphere('Grape',kit.rng.uniform(.073,.106),(x,y,z),kit.rng.choice(grape_colors[lo:lo+3]),
                       segments=14,rings=9,scale=(.92,1,1.07))
        kit.tube('Fruit stem', [(center[0]-.04,center[1],.24),(center[0]-.2,center[1]+.24,.34)],.021,stem)
        x,y = center[0]-.2,center[1]+.24
        kit.extrude('Vine leaf', [(0,0),(.10,-.035),(.14,-.11),(.23,-.1),(.27,.015),
                                 (.16,.12),(.08,.1)],.014,leaf,(x,y,.25),rotation=(20,-25,4), bevel=.012)

    cx,cy = .98,.49
    kit.lathe('Candlestick', [(0,0),(.22,0),(.23,.043),(.11,.092),(.075,.3),(.138,.34),(.145,.39),
                             (.1,.4),(.1,.36),(0,.355)], 64,pewter,(cx,cy,0))
    kit.cylinder('Wax candle', .093,.46,(cx,cy,.6),candle,segments=42,bevel=.026)
    wick = kit.material('Charred wick', '#342321', .89)
    kit.tube('Wick',[(cx,cy,.81),(cx+.01,cy,.86)],.01,wick,resolution=3)
    fire = kit.emissive('Candle flame', '#FFB65D', 6)
    tip = kit.lathe('Fluttering flame', [(0.,0.),(.032,.03),(.042,.072),(.032,.119),(.012,.17),(0,.205)],
                    32,fire,(cx,cy,.842))
    kit.animate(tip,'scale',lambda t: (1+.12*math.sin(t*49),1,1+.13*math.sin(t*67)),step=2)
    light = kit.point('Flame spill',(cx,cy,.91),4,'#FFB564',.13)
    kit.animate(light.data,'energy',lambda t: 4+math.sin(53*t),step=3)
    fly = kit.empty('Fly landing', (-.29,-.32,.43))
    kit.sphere('Fly body',.018,(0,0,0),wick,segments=10,rings=6,scale=(.7,1.3,.6)).parent=fly
    for sign in (-1,1):
        kit.sphere('Fly wing',.016,(sign*.013,.008,.009),glass,segments=10,rings=6,
                   scale=(.65,1.3,.11)).parent = fly
    kit.move(fly,[(-1.3,0,1.47),(-.64,-.78,.54),(-.39,-.57,.46),(-.41,-.33,.285)],
             start=.45,end=.83,ease_kind='out')

    kit.world('#3B2723', .20)
    kit.area('Single tall window', (-3,-2.2,4.6),(-.13,-.1,.52),310,'#FFE4B1',1.85,size_y=3.1)
    cam=kit.camera((1.46,-4.55,2.39),(0,-.06,.63),lens=48)
    kit.dolly(cam,(1.46,-4.55,2.39),(1.23,-4.24,2.17),(0,-.06,.63),(0,-.06,.62))
    kit.render(exposure=.55,bounces=5)
