"""Layer a stylized coat over a curled silhouette, then animate breathing and wrapped snowfall."""
import math
import random


def build(kit):
    rng = random.Random(kit.brief['seed'])
    russet = kit.material('Russet winter coat', '#BC4D16', .73, sheen=.43, bump=(81, .45))
    sienna = kit.material('Copper guard hairs', '#DB702D', .80, sheen=.48, bump=(98, .30))
    cream = kit.material('Ivory guard hairs', '#F4DBC0', .75, sheen=.42, bump=(98, .33))
    black = kit.material('Dark legs and lashes', '#2B2121', .78, sheen=.35, bump=(93, .25))
    nose = kit.material('Cold nose', '#19171C', .28)
    ear = kit.material('Weathered pink ear lining', '#A4514D', .83, subsurface=.09)
    snow = kit.procedural('Snow crust', 'ground', colors=['#8AA4C4', '#CBD9EB', '#F2F4F7'], scale=2.3, bump=.20)
    kit.terrain('Snow bank', size=22, resolution=85, height=.19, scale=.51, material=snow, flatten_center=3)

    def ellipsoid(name, xyz, size, mat, angle=0):
        o = kit.sphere(name, 1, xyz, mat, segments=48, rings=24)
        o.scale = size
        o.rotation_euler.z = math.radians(angle)
        return o

    flank = ellipsoid('Curled flank', (-.34, .24, .48), (.95, .62, .47), russet, -12)
    kit.animate(flank, 'scale', lambda t: (.95, .62 + .011 * math.sin(math.tau * t),
                                          .47 + .020 * math.sin(math.tau * t)), step=3)
    ellipsoid('Fur collar', (.34, -.02, .40), (.52, .43, .34), sienna, -28)
    ellipsoid('Pale cheek', (.45, -.32, .34), (.36, .27, .23), cream, -24)
    ellipsoid('Head', (.62, -.29, .43), (.39, .28, .27), sienna, -35)
    ellipsoid('Pale tapering muzzle', (.83, -.56, .24), (.28, .136, .123), cream, -53)
    ellipsoid('Nose', (.985, -.74, .224), (.081, .060, .053), nose, -53)
    ellipsoid('Forepaw', (.51, -.63, .105), (.27, .14, .085), black, -11)
    ellipsoid('Far paw', (.26, -.55, .086), (.25, .13, .071), black, 7)
    kit.tube('Closed eyelid', [(.52, -.590, .444), (.595, -.613, .411), (.672, -.628, .407),
                             (.76, -.623, .426)], .014, black)
    kit.tube('Muzzle contour', [(.73, -.59, .191), (.84, -.63, .173), (.94, -.705, .198)], .012, black)

    for x, y, lean in ((.40, -.27, -.11), (.71, -.15, .13)):
        a, b, tip = (x - .13, y, .58), (x + .14, y + .03, .60), (x + lean, y + .01, 1.00)
        outer = kit.mesh('Pointed ear', [a, b, tip, (x, y + .15, .64)], [(0, 1, 2), (0, 2, 3),
                                                                      (1, 3, 2), (0, 3, 1)], russet)
        kit.bevel(outer, .014, segments=3)
        kit.mesh('Inner ear', [(x - .075, y - .009, .626), (x + .081, y - .009, .64),
                               (x + lean * .77, y, .896)], [(0, 1, 2)], ear)

    tail = [(-.76, .44, .35), (-1.15, .17, .27), (-1.18, -.29, .235), (-.90, -.65, .219),
            (-.48, -.81, .198), (-.06, -.82, .161), (.23, -.80, .13)]
    kit.tube('Orange brush', tail[:6], .23, sienna, resolution=20, taper=[.77, 1, 1.04, .99, .92, .56])
    kit.tube('Pale tail tip', tail[4:], .227, cream, resolution=20, taper=[.91, .54, .055])

    needles = kit.material('Spruce needles in dusk', '#203D39', .93, bump=(24, .15))
    for i in range(8):
        x = -9 + i * 2.6 + rng.uniform(-.7, .7)
        kit.tree(f'Spruce {i}', rng.uniform(3.6, 6), (x, 6.5 + rng.random() * 3, 0), 'conifer', leaves=needles, seed=i)
    for i in range(16):
        x, y = rng.uniform(-4.5, 4.5), rng.choice((-1, 1)) * rng.uniform(1.2, 3)
        kit.tube(f'Dry grass {i}', [(x, y, 0), (x + .035, y, .17), (x + .10, y + .025, .31)], .012, black)

    flake = kit.material('Snow crystal', '#EBF1FF', .43, emission='#A3BAE4', emission_strength=.22)
    for i in range(106):
        x, y, p = rng.uniform(-5, 5), rng.uniform(-3, 4), rng.random()
        size = rng.uniform(.012, .045)
        o = kit.ico(f'Snow crystal {i:03}', size, (x, y, 0), flake, subdivisions=1)
        # Wrap out of shot, where the lower/upper borders hide the position discontinuity.
        kit.animate(o, 'location', lambda t, x=x, y=y, p=p: (
            x + .19 * math.sin(math.tau * (t + p)), y, -.7 + 7.2 * ((p - t) % 1)), step=1)

    kit.world('#556C9F', strength=.25)
    kit.area('Snow-lit sky', (-3, -3, 5), (0, 0, .3), 345, '#A6CBFF', 5)
    kit.area('Last daylight', (2, 3, 3.5), (0, 0, .45), 515, '#FFD2A5', 3)
    kit.area('Face bounce', (1, -4, 1.8), (.5, 0, .28), 90, '#E3D8E4', 2.8)
    kit.camera((1.2, -5.55, 1.61), (-.09, -.02, .37), lens=54, dof=5.60, fstop=2.6)
    kit.render(exposure=.13, motion_blur=False)
