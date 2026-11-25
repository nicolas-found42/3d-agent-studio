"""A gothic nave at dawn, from the prompt alone (benchmark: the procedural Laon cathedral).

Elevation in three storeys like an early gothic nave: pointed arcade on clustered piers, a
triforium band of small arches, and a clerestory of lancets under a pointed barrel vault with
transverse and diagonal ribs. Low sun enters the south clerestory through faint haze, so shafts
land on the north arcade and the flagstones. The camera dollies slowly east down the nave.
"""
import math

from mathutils import Vector

BAYS = 8
BAY = 4.6          # bay length along the nave (m)
NAVE = 10.6        # nave width between arcade centrelines
AISLE = 5.0        # aisle width
PIER_H = 6.6       # arcade springing height
ARC_RISE = 3.4
TRI_Z = (10.4, 12.8)
CLER_Z = (13.4, 18.0)
VAULT_SPRING = 18.4
VAULT_RISE = 5.8   # crown at about 24 m, like Laon
LENGTH = BAYS * BAY


def build(kit):
    stone = kit.textured('Limestone ashlar', 'polyhaven:sandstone_blocks_05@1k', scale=0.41, tint='#CBBA9D', bump=0.53)
    smooth = kit.procedural('Dressed limestone', 'stone', colors=['#756C5D', '#A69880', '#C4B399'],
                            scale=1.6, roughness=.76, bump=.25)
    floor_mat = kit.textured('Worn flagstones', 'ambientcg:PavingStones131@1K', scale=0.65, tint='#CFC2AA', bump=0.30)
    glass = kit.material('Clerestory glass', '#9DB7D6', 0.08, transmission=1.0, thin_wall=True)
    y0 = -LENGTH / 2

    # Floor and outer shell (walls beyond the aisles, roof slab) so nothing leaks light by accident.
    kit.box('Nave floor', (NAVE + 2 * AISLE + 2, LENGTH + 16, 0.3), (0, 0, -0.15), floor_mat, ground=True)
    for sx in (-1, 1):
        x_wall = sx * (NAVE / 2 + AISLE + 0.4)
        kit.box(f'Aisle outer wall {sx}', (0.8, LENGTH + 16, 8.6), (x_wall, 0, 4.3), stone)
        kit.box(f'Aisle roof {sx}', (AISLE + 0.8, LENGTH + 16, 0.5), (sx * (NAVE / 2 + AISLE / 2), 0, 8.8), smooth)
        for b in range(BAYS + 1):
            y = y0 + b * BAY
            kit.box(f'Buttress {sx}.{b}', (1.27, .81, 7.9), (x_wall + sx * .68, y, 3.95), stone, bevel=.065)
            kit.box(f'Buttress plinth {sx}.{b}', (1.45, 1.05, .55), (x_wall + sx * .70, y, .28), smooth, bevel=.035)
    kit.box('West wall', (NAVE + 2 * AISLE + 2, 1.0, 26), (0, y0 - 4.5, 13), stone)
    east = -y0 + 7
    kit.box('East face', (NAVE + 2 * AISLE + 2, 1.0, 26), (0, east, 13), stone)
    slate = kit.procedural('Weathered exterior slate', 'stone', colors=['#292F35', '#3F4B56', '#56606A'],
                           scale=2.7, roughness=.82, bump=.4)
    roof_y = (y0 - 4.8, east + .45)
    ridge = 29.0
    for side in (-1, 1):
        x = side * (NAVE / 2 + .81)
        kit.mesh(f'Slate roof slope {side}', [(0, y, ridge) for y in roof_y] + [(x, y, 19.25) for y in roof_y],
                 [(0, 1, 3, 2)], slate)
    for end, name in ((roof_y[0] + .18, 'west'), (roof_y[1] - .18, 'east')):
        kit.mesh(f'Roof gable {name}', [(-6.08, end, 18.9), (6.08, end, 18.9), (0, end, ridge)], [(0, 1, 2)], stone)

    def clustered_pier(name, x, y):
        """A drum with four engaged shafts, base and capital: the Laon pier in simplified form."""
        kit.cylinder(f'{name} core', 0.62, PIER_H, (x, y, PIER_H / 2), smooth, segments=40)
        for k in range(4):
            a = math.pi / 4 + k * math.pi / 2
            kit.cylinder(f'{name} shaft {k}', 0.2, PIER_H, (x + 0.62 * math.cos(a), y + 0.62 * math.sin(a), PIER_H / 2),
                         smooth, segments=20)
        kit.cylinder(f'{name} base', 0.95, 0.5, (x, y, 0.25), smooth, segments=40, bevel=0.06)
        kit.cylinder(f'{name} capital', 0.78, 0.55, (x, y, PIER_H - 0.25), smooth, segments=40, radius_top=0.98)
        for k in range(12):
            a = math.tau * k / 12
            leaf = kit.sphere(f'{name} carved leaf {k}', .20,
                              (x + .76 * math.cos(a), y + .76 * math.sin(a), PIER_H - .25), smooth,
                              segments=12, rings=7)
            leaf.scale = (.72, .72, 1.55)
        kit.box(f'{name} abacus', (2.0, 2.0, 0.22), (x, y, PIER_H + 0.11), smooth, bevel=0.03)

    for side in (-1, 1):
        x = side * NAVE / 2
        for b in range(BAYS + 1):
            y = y0 + b * BAY
            clustered_pier(f'Pier {side}.{b}', x, y)
            # Wall shaft rising from the abacus to the vault springing (carries the ribs).
            kit.cylinder(f'Vault shaft {side}.{b}', 0.17, VAULT_SPRING - PIER_H, (x - side * 0.55, y, (PIER_H + VAULT_SPRING) / 2),
                         smooth, segments=16)
        for b in range(BAYS):
            yc = y0 + (b + 0.5) * BAY
            kit.arch(f'Arcade {side}.{b}', BAY - 1.2, rise=ARC_RISE, depth=1.2, thickness=0.55, kind='gothic',
                     location=(x, yc, PIER_H + 0.22), rotation=(0, 0, 90), material=stone)
            # Spandrel wall above the arcade up to the triforium.
            kit.box(f'Spandrel {side}.{b}', (1.0, BAY, TRI_Z[0] - (PIER_H + ARC_RISE)),
                    (x, yc, (PIER_H + ARC_RISE + TRI_Z[0]) / 2 + 0.25), stone)
            for k in (-1, 0, 1):
                kit.arch(f'Triforium {side}.{b}.{k}', 0.9, rise=0.9, depth=0.8, thickness=0.14, kind='gothic',
                         location=(x, yc + k * 1.25, TRI_Z[0] + 0.9), rotation=(0, 0, 90), material=smooth,
                         pier_height=0.9, pier_width=0.18)
            kit.box(f'Triforium back wall {side}.{b}', (0.4, BAY, TRI_Z[1] - TRI_Z[0]), (x + side * 0.7, yc, sum(TRI_Z) / 2), stone)
            kit.box(f'Triforium string course {side}.{b}', (1.3, BAY, 0.22), (x, yc, TRI_Z[1] + 0.11), smooth, bevel=0.04)
            # Clerestory: wall either side of a tall lancet, a pointed head, and glass.
            win_w = 1.5
            seg = (BAY - win_w) / 2
            for s in (-1, 1):
                kit.box(f'Clerestory wall {side}.{b}.{s}', (1.0, seg, CLER_Z[1] - CLER_Z[0] + 0.6),
                        (x, yc + s * (win_w / 2 + seg / 2), (CLER_Z[0] + CLER_Z[1]) / 2 + 0.3), stone)
            kit.box(f'Clerestory sill {side}.{b}', (1.0, win_w, 0.6), (x, yc, CLER_Z[0] - 0.3 + 0.3), smooth)
            kit.arch(f'Lancet head {side}.{b}', win_w, rise=1.3, depth=1.0, thickness=0.5, kind='gothic',
                     location=(x, yc, CLER_Z[1] - 1.3), rotation=(0, 0, 90), material=stone)
            pane = kit.box(f'Lancet glass {side}.{b}', (0.04, win_w, CLER_Z[1] - CLER_Z[0] - 0.4),
                           (x + side * 0.45, yc, (CLER_Z[0] + CLER_Z[1]) / 2 - 0.2), glass)
            pane.visible_shadow = False   # let sun and sky through as if the glass were clear
            kit.box(f'Upper wall {side}.{b}', (1.0, BAY, VAULT_SPRING - CLER_Z[1] + 0.6), (x, yc, (CLER_Z[1] + VAULT_SPRING) / 2 + 0.3), stone)

    # Vault: one pointed barrel shell, then transverse arches and diagonal ribs on its surface.
    kit.arch('Nave vault', NAVE - 1.1, rise=VAULT_RISE, kind='gothic', depth=LENGTH + 15, thickness=0.45,
             location=(0, 0, VAULT_SPRING), rotation=(0, 0, 0), material=smooth, steps=48)
    profile = kit.arch_profile(NAVE - 1.1, VAULT_RISE, 'gothic', 48)

    def vault_z(x):
        pts = [(p[0], p[1]) for p in profile]
        for (xa, za), (xb, zb) in zip(pts, pts[1:]):
            if min(xa, xb) <= x <= max(xa, xb) and xa != xb:
                return za + (zb - za) * (x - xa) / (xb - xa)
        return 0.0

    rib_mat = kit.material('Clean edge on limestone ribs', '#B3A086', 0.72, bump=(45, 0.21))
    half = (NAVE - 1.1) / 2 - 0.05
    for b in range(BAYS + 1):
        y = y0 + b * BAY
        kit.arch(f'Transverse rib {b}', NAVE - 1.3, rise=VAULT_RISE - 0.2, kind='gothic', depth=0.45, thickness=0.32,
                 location=(0, y, VAULT_SPRING), rotation=(0, 0, 0), material=rib_mat)
    for b in range(BAYS):
        ya = y0 + b * BAY
        for d in (-1, 1):
            pts = []
            for i in range(25):
                s = i / 24
                x = -half + 2 * half * s
                y = ya + BAY * (s if d > 0 else 1 - s)
                pts.append((x, y, VAULT_SPRING + vault_z(x) - 0.42))
            web = [(x, y, z + dz) for x, y, z in pts for dz in (.13, .49)]
            kit.mesh(f'Diagonal rib stone web {b}.{d}', web,
                     [(i, i + 2, i + 3, i + 1) for i in range(0, len(web) - 2, 2)], rib_mat)
            kit.tube(f'Diagonal rib {b}.{d}', pts, radius=0.23, material=rib_mat)
            kit.tube(f'Diagonal rib molding {b}.{d}', [(x, y, z - .14) for x, y, z in pts], radius=.117, material=smooth)
        kit.sphere(f'Boss {b}', 0.35, (0, ya + BAY / 2, VAULT_SPRING + VAULT_RISE - 0.49), rib_mat, segments=24, rings=12)

    # A recessed east end gives the moving shot a visible destination.
    lead = kit.material('Window leading', '#252324', .62, metallic=.38)
    panes = [kit.material(f'Glass {i}', color, .32, emission=color, emission_strength=.8)
             for i, color in enumerate(('#737FC3', '#A76349', '#E3A155', '#63578B'))]
    for col, base_x in enumerate((-2.15, 0, 2.15)):
        base_z = 5.2 if col == 1 else 4.55
        kit.arch(f'East lancet {col}', 1.5, rise=1.3, depth=.45, thickness=.2, kind='gothic',
                 location=(base_x, east - .67, base_z), pier_height=6.9, pier_width=.24, material=smooth)
        outline = [(x, z + 6.9) for x, z, _, _ in kit.arch_profile(1.50, 1.3)]
        face = [(base_x - .75, east - .72, base_z), (base_x + .75, east - .72, base_z)]
        face += [(base_x + x, east - .72, base_z + z) for x, z in reversed(outline)]
        kit.mesh(f'East lancet glass {col}', face, [tuple(range(len(face)))], panes[col])
        for bar in range(1, 4):
            kit.box(f'East lead vertical {col}.{bar}', (.035, .027, 6.9),
                    (base_x - .75 + .375 * bar, east - .75, base_z + 3.45), lead)
        for bar in range(1, 12):
            kit.box(f'East lead horizontal {col}.{bar}', (1.49, .027, .018),
                    (base_x, east - .75, base_z + bar * .575), lead)
    rose_z = 16.8
    rose_y = east - .72
    kit.cylinder('East rose stone backing', 1.39, .26, (0, east - .59, rose_z), smooth,
                 rotation=(90, 0, 0), bevel=.03)
    kit.torus('East rose limestone surround', 1.38, .091, (0, rose_y - .04, rose_z), smooth, rotation=(90, 0, 0))
    kit.torus('East rose lead rim', 1.27, .038, (0, rose_y - .065, rose_z), lead, rotation=(90, 0, 0))
    for petal in range(12):
        start = math.tau * petal / 12
        end = math.tau * (petal + 1) / 12
        rim = [(1.27 * math.cos(a), rose_y, rose_z + 1.27 * math.sin(a))
               for a in [start + (end - start) * n / 4 for n in range(5)]]
        kit.mesh(f'Rose colored glass {petal}', [(0, rose_y, rose_z), *rim], [tuple(range(len(rim) + 1))], panes[petal % 4])
        kit.tube(f'Lead rose spoke {petal}', [(0, rose_y - .07, rose_z), (rim[0][0], rose_y - .07, rim[0][2])], .026, lead)
    oak = kit.procedural('Fumed oak seating', 'wood', colors=['#312019', '#4A3223', '#664B32'], scale=1.5)
    for row in range(12):
        y = y0 + 4 + row * 1.12
        for sign in (-1, 1):
            x = sign * 2.9
            kit.box('Pew seat', (3.03, .49, .08), (x, y, .48), oak, bevel=.018)
            kit.box('Pew back', (3.05, .14, .44), (x, y - .24, .78), oak, bevel=.027)
            for end in (-1, 1):
                kit.box('Pew end', (.12, .51, .84), (x + end * 1.50, y, .42), oak, bevel=.055)

    # Light: low sun from the south through the clerestory, a soft sky, warm practicals in the aisles.
    kit.sky(sun_elevation=24, sun_rotation=-65, strength=0.08, sun_intensity=1.0)
    # The south clerestory is on the +X wall. The sun travels from +X toward the north arcade.
    kit.sun(elevation=24, azimuth=115, strength=4.5, color='#FFD7A8', angle=0.6)
    for b in range(BAYS):
        yc = y0 + (b + 0.5) * BAY
        kit.area(f'Aisle window glow N{b}', (-(NAVE / 2 + AISLE - 0.2), yc, 5), (0, yc, 2), 90, '#CFE0FF', 2.0)
        kit.area(f'Aisle window glow S{b}', ((NAVE / 2 + AISLE - 0.2), yc, 5), (0, yc, 2), 140, '#FFE2BC', 2.0)
    kit.area('East crossing light', (0, -y0 + 5.5, 12), (0, 0, 6), 1600, '#FFE9CC', 9)
    kit.area('High nave bounce', (0, y0 + 6, 11), (0, 6, 9), 2400, '#D3E1F7', 11)
    kit.haze(0.0031, '#FFF2E0', anisotropy=0.53, size=(NAVE + 2 * AISLE, LENGTH + 8, 25), location=(0, 0, 12.5))

    # Camera: slow dolly east down the nave, looking slightly up toward the crossing.
    cam = kit.camera((0.55, y0 - 1.5, 2.15), (0, -y0 + 6, 7.7), lens=18)
    cam.data.shift_y = 0.075
    kit.dolly(cam, (0.55, y0 - 1.5, 2.15), (0.12, y0 + LENGTH * 0.36, 2.4), (0, -y0 + 6, 7.7), (0, -y0 + 6, 8.6),
              ease_kind='in_out', power=2.0)
    kit.render(exposure=0.42, look='AgX - Base Contrast', bounces=6)
