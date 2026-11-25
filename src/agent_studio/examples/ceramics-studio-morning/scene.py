"""A working potter's studio dressed with procedural glazes and differently thrown shapes."""
import math

GLAZES = ('#315E63','#A5704B','#B8A378','#7A8660','#D0BDA4','#3D505B','#89635D')


def vessel_profile(radius, height, kind):
    """The return profile is the inside wall, ending just above the bottom."""
    if kind == 'vase':
        outline=((.55,0),(.62,.10),(.92,.24),(1,.44),(.82,.68),(.54,.86),(.57,.96),(.64,1))
    elif kind == 'bowl':
        outline=((.43,0),(.48,.11),(.68,.23),(.9,.56),(1,.92),(.97,1))
    else:
        outline=((.68,0),(.74,.12),(.87,.3),(.96,.78),(1,.95),(.98,1))
    return ([(0,0)] + [(r*radius,z*height) for r,z in outline] +
            [(max(0,r*radius-.025),max(.024,z*height-.018)) for r,z in reversed(outline)] + [(0,.024)])


def build(kit):
    tones = [kit.material(f'Glaze {i}', color, .24+.03*(i%3), coat=.42, bump=(76,.16))
             for i,color in enumerate(GLAZES)]
    clay=kit.material('Fired red earthenware', '#AC7458',.61,bump=(81,.32))
    wood=kit.procedural('Old maple workbench','wood',['#6B4C35','#9D754D','#CE9E6A'],scale=2.4,roughness=.53,bump=.24)
    plaster=kit.procedural('Pale limewashed plaster','concrete',['#B6B4A2','#CBC9AE','#F4D8B2'],scale=.66,roughness=.82,bump=.18)
    iron=kit.material('Worn wheel metal','#666B6A',.3,metallic=.72)
    kit.ground(wood, 25)
    kit.box('Plaster rear wall',(12,.16,5),(0,1.73,2.5), plaster)
    pegboard=kit.material('Dark slate tool hooks','#465245',.56,bump=(47,.17))
    kit.box('Pegboard behind bench',(1.28,.035,.66),(2.34,1.627,2.42),pegboard,bevel=.014)
    for i in range(7):
        x=1.83+i*.17
        kit.torus('Hanging loop tool',.057,.006,(x,1.58,2.5),iron,rotation=(90,0,0),segments=18,sides=5)
        kit.cylinder('Tool handle',.016,.23+.028*(i%3),(x,1.57,2.32),wood,segments=10)
    kit.box('Shelf plinth rail',(7.8,.11,.13),(-.28,1.66,.19),wood,bevel=.03)
    # The shelves carry five distinct silhouettes, staged with small irregular spacing.
    for level in range(3):
        z=.79+level*.63
        kit.box(f'Open studio shelf {level+1}',(7.8,.64,.085),(-.28,1.33,z),wood,bevel=.024)
        for column in range(12):
            x=-3.76+column*.64+kit.rng.uniform(-.07,.07)
            y=1.26+kit.rng.uniform(-.09,.07)
            kind=('bowl','jar','vase')[(column+level*2)%3]
            radius=kit.rng.uniform(.14,.23)
            height=kit.rng.uniform(.14,.23) if kind=='bowl' else kit.rng.uniform(.27,.48)
            item=f'{kind.title()} {level+1}.{column+1}'
            kit.lathe(item,vessel_profile(radius,height,kind),44,tones[(column+level)%len(tones)],(x,y,z+.044))
            kit.torus('Unglazed foot',radius*.53,.012,(x,y,z+.052),clay,segments=28,sides=8)
    for x in (-3.8,-1.98,1.51,3.22):
        kit.box('Shelf support',(.086,.55,2.42),(x,1.47,1.22),wood,bevel=.012)
    kit.box('Potter bench',(5.3,1.1,.11),(.31,-.52,.81),wood,bevel=.032)
    for x in (-2.14,2.75):
        for y in (-.86,-.17):
            kit.box('Workbench leg',(.15,.15,.8),(x,y,.4),wood,bevel=.015)
    wheel_xy=(-.71,-.48)
    kit.cylinder('Wheel flywheel case',.35,.22,(*wheel_xy,.93),iron,segments=64,bevel=.032)
    wheel=kit.cylinder('Potter wheel head',.41,.067,(*wheel_xy,1.065),iron,segments=64,bevel=.021)
    kit.spin(wheel,turns=2.2)
    for i in range(7):
        kit.torus('Wheel scribe circle', .16+.032*i, .0027, (*wheel_xy,1.1),wood,segments=48,sides=5)
    piece=kit.lathe('Ware being thrown',vessel_profile(.217,.31,'bowl'),64,clay,(*wheel_xy,1.103))
    kit.spin(piece,turns=2.2)
    for i in range(6):
        x=.77+.25*i
        p=[(x,-.91,.884),(x+.04,-.6,.884),(x+.12,-.36,.889)]
        kit.tube(f'Boxwood tool {i}',p,.015+(.004*(i%2)),wood,resolution=3)
        kit.torus('Wire trimming loop',.043,.006,(x+.13,-.32,.894),iron,segments=22,sides=5)
    kit.lathe('Slip bowl',vessel_profile(.28,.17,'bowl'),64,tones[0],(-1.91,-.53,.87))
    kit.lathe('Brush jar',vessel_profile(.19,.36,'jar'),48,tones[4],(2.42,-.35,.87))
    for i in range(8):
        a=kit.rng.uniform(.04,.15)
        kit.tube('Brush handle',[(2.42,-.35,1.0),(2.42+a*math.cos(i),-.35+a*math.sin(i),1.38+.034*i)],
                 .016,wood,resolution=3)
    sky=kit.emissive('Diffused window glass','#FFF0C2',1.4)
    for i in range(4):
        kit.box('Lit window pane',(.045,.52,.74),(-3.04,.13+.56*(i%2),2.37+.79*(i//2)),sky,bevel=.009)
    kit.box('Window sill',(.26,1.25,.082),(-3.06,.42,1.94),wood,bevel=.017)
    dust=kit.emissive('Backlit dust','#FFE1A2',2)
    for i in range(37):
        x,y,z=kit.rng.uniform(-3.3,2),kit.rng.uniform(-1.8,.9),kit.rng.uniform(.7,2.6)
        particle=kit.sphere(f'Dust {i}',kit.rng.uniform(.003,.013),(x,y,z),dust,segments=7,rings=4)
        kit.animate(particle,'location',lambda t,x=x,y=y,z=z,i=i:(x+.13*t,y+.06*math.sin(i+4*t),z+.07*math.cos(i+5*t)),step=8)
    kit.haze(.03, '#FFEBD6', .54, (7, 4, 3), (0, -.05, 1.4))
    kit.world('#DFEAFF',.18)
    kit.sun(38,251,2.6,'#FFDFC2',4)
    kit.area('Soft window bounce',(-3.31,-.31,2.86),(1.32,-.1,.6),370,'#FFF0D1',2.65)
    for i in range(2):
        kit.spot('Window shaft',(-3.27,.11+.5*i,2.64+.17*i),(1.51,-.44+.32*i,.78),
                 power=1550,color='#FFDA9C',angle=20,blend=.27,radius=.15)
    kit.area('Pale fill',(3.1,-3.2,3.3),(0,.8,1.4),180,'#DEEEFF',4.2)
    cam=kit.camera((-2.72,-4.22,2.08),(-.64,.41,1.4),lens=31)
    kit.dolly(cam,(-2.72,-4.22,2.08),(2.59,-4.78,2.19),(-.64,.41,1.4),(.66,.36,1.51))
    kit.render(bounces=4)
