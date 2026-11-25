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
    stone = kit.textured('Limestone ashlar', 'polyhaven:sandstone_blocks_05@1k', scale=0.32, tint='#E9DFCB', bump=0.6)
    smooth = kit.textured('Dressed limestone', 'polyhaven:sandstone_blocks_05@1k', scale=0.08, tint='#EFE6D4',
                          bump=0.25, roughness=0.75)
    floor_mat = kit.textured('Worn flagstones', 'ambientcg:PavingStones131@1K', scale=0.35, tint='#CFC2AA', bump=0.8)
    glass = kit.material('Clerestory glass', '#9DB7D6', 0.08, transmission=1.0, thin_wall=True)
    y0 = -LENGTH / 2

    # Floor and outer shell (walls beyond the aisles, roof slab) so nothing leaks light by accident.
    kit.box('Nave floor', (NAVE + 2 * AISLE + 2, LENGTH + 10, 0.3), (0, 0, -0.15), floor_mat, ground=True)
    for sx in (-1, 1):
        kit.box(f'Aisle outer wall {sx}', (0.8, LENGTH + 10, 8.6), (sx * (NAVE / 2 + AISLE + 0.4), 0, 4.3), stone)
        kit.box(f'Aisle roof {sx}', (AISLE + 0.8, LENGTH + 10, 0.5), (sx * (NAVE / 2 + AISLE / 2), 0, 8.8), smooth)
    kit.box('West wall', (NAVE + 2 * AISLE + 2, 1.0, 26), (0, y0 - 4.5, 13), stone)
    kit.box('Crossing screen', (NAVE + 2 * AISLE + 2, 1.0, 26), (0, -y0 + 6.5, 13), stone)

    def clustered_pier(name, x, y):
        """A drum with four engaged shafts, base and capital: the Laon pier in simplified form."""
        kit.cylinder(f'{name} core', 0.62, PIER_H, (x, y, PIER_H / 2), smooth, segments=40)
        for k in range(4):
            a = math.pi / 4 + k * math.pi / 2
            kit.cylinder(f'{name} shaft {k}', 0.2, PIER_H, (x + 0.62 * math.cos(a), y + 0.62 * math.sin(a), PIER_H / 2),
                         smooth, segments=20)
        kit.cylinder(f'{name} base', 0.95, 0.5, (x, y, 0.25), smooth, segments=40, bevel=0.06)
        kit.cylinder(f'{name} capital', 0.78, 0.55, (x, y, PIER_H - 0.25), smooth, segments=40, radius_top=0.98)
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
    kit.arch('Nave vault', NAVE - 1.1, rise=VAULT_RISE, kind='gothic', depth=LENGTH, thickness=0.45,
             location=(0, 0, VAULT_SPRING), rotation=(0, 0, 0), material=smooth, steps=48)
    profile = kit.arch_profile(NAVE - 1.1, VAULT_RISE, 'gothic', 48)

    def vault_z(x):
        pts = [(p[0], p[1]) for p in profile]
        for (xa, za), (xb, zb) in zip(pts, pts[1:]):
            if min(xa, xb) <= x <= max(xa, xb) and xa != xb:
                return za + (zb - za) * (x - xa) / (xb - xa)
        return 0.0

    rib_mat = kit.material('Rib stone', '#E3D8C2', 0.7, bump=(40, 0.1))
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
                pts.append((x, y, VAULT_SPRING + vault_z(x) - 0.12))
            kit.tube(f'Diagonal rib {b}.{d}', pts, radius=0.16, material=rib_mat)
        kit.sphere(f'Boss {b}', 0.32, (0, ya + BAY / 2, VAULT_SPRING + VAULT_RISE - 0.25), rib_mat, segments=24, rings=12)

    # Light: low sun from the south through the clerestory, a soft sky, warm practicals in the aisles.
    kit.sky(sun_elevation=24, sun_rotation=-90 + 25, strength=0.08, sun_intensity=1.0)
    kit.sun(elevation=24, azimuth=90 + 25 - 180 + 180, strength=4.5, color='#FFD7A8', angle=0.6)
    for b in range(BAYS):
        yc = y0 + (b + 0.5) * BAY
        kit.area(f'Aisle window glow N{b}', (-(NAVE / 2 + AISLE - 0.2), yc, 5), (0, yc, 2), 90, '#CFE0FF', 2.0)
        kit.area(f'Aisle window glow S{b}', ((NAVE / 2 + AISLE - 0.2), yc, 5), (0, yc, 2), 140, '#FFE2BC', 2.0)
    kit.area('East crossing light', (0, -y0 + 5.5, 12), (0, 0, 6), 9000, '#FFE9CC', 10)
    kit.haze(0.018, '#FFF2E0', anisotropy=0.55, size=(NAVE + 2 * AISLE, LENGTH + 8, 25), location=(0, 0, 12.5))

    # Camera: slow dolly east down the nave, looking slightly up toward the crossing.
    cam = kit.camera((0.6, y0 - 1.5, 1.7), (0, -y0 + 6, 9.5), lens=22)
    kit.dolly(cam, (0.6, y0 - 1.5, 1.7), (0.2, y0 + LENGTH * 0.45, 1.9), (0, -y0 + 6, 9.5), (0, -y0 + 6, 10.5),
              ease_kind='in_out', power=2.0)
    kit.render(exposure=0.6, look='AgX - Base Contrast', bounces=6)
