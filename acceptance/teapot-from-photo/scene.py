"""Reconstruct the reference silhouette with turned clay profiles and a hollow swept spout."""
import math

from mathutils import Vector


def build(kit):
    clay = kit.material('Charcoal satin glaze', '#1E2227', roughness=0.34, coat=0.22, bump=(108, 0.23))
    lip = kit.material('Oxblood glaze', '#981F19', roughness=0.27, coat=0.36, bump=(88, 0.09))
    stone = kit.procedural('Warm limestone counter', 'stone', colors=['#544538', '#756454', '#9E8C79'],
                           scale=2.4, roughness=0.56, bump=0.19)
    kit.ground(stone, size=70)
    wall = kit.procedural('Defocused workshop wall', 'wood', colors=['#263439', '#3D4844', '#6C5A45'],
                          scale=0.65, roughness=.80, bump=.15)
    kit.box('Workshop backdrop', (16, .23, 7), (0, 6.4, 3.25), wall, bevel=.16, ground=True)
    mullion = kit.material('Window mullions', '#383028', .78)
    for i in range(5):
        kit.box(f'Distant dark mullion {i}', (.09, .34, 2.5), (-3.8 + i * 1.25, 6.15, 2.46), mullion, bevel=.026, ground=True)
    kit.lathe('Thrown body', [(0, .018), (.51, .018), (.60, .04), (.62, .11), (.73, .15), (.87, .24),
                             (.99, .42), (1.04, .59), (1.03, .77), (.96, .94), (.85, 1.10),
                             (.74, 1.21), (.71, 1.29), (.73, 1.33), (.70, 1.36), (0, 1.36)], 112, clay)
    kit.lathe('Glossy red lip', [(.69, 1.32), (.735, 1.32), (.77, 1.36), (.756, 1.397), (.716, 1.40),
                                (.69, 1.37), (.69, 1.32)], 112, lip)
    kit.lathe('Shallow domed lid', [(0, 1.365), (.699, 1.365), (.704, 1.41), (.66, 1.447), (.56, 1.477),
                                   (.44, 1.512), (.28, 1.55), (.16, 1.569), (0, 1.575)], 112, clay)
    kit.lathe('Black porcelain finial', [(0, 1.56), (.135, 1.56), (.12, 1.62), (.105, 1.68), (.145, 1.74),
                                         (.157, 1.805), (.14, 1.865), (.088, 1.906), (0, 1.927)], 64, clay)
    kit.tube('Continuous round handle', [(0.86, 0, 1.05), (1.09, 0, 1.20), (1.43, 0, 1.18),
                                        (1.63, 0, .96), (1.59, 0, .68), (1.37, 0, .44), (1.01, 0, .30),
                                        (.82, 0, .31)], .104, clay, resolution=24)

    # Ring centers and radii follow the rising centerline. The final rings turn back inside the mouth.
    profile = [(-.75, .37, .28), (-.97, .46, .27), (-1.12, .60, .23), (-1.22, .78, .19),
               (-1.27, .98, .16), (-1.33, 1.19, .15), (-1.42, 1.38, .16), (-1.45, 1.425, .151),
               (-1.45, 1.425, .109), (-1.41, 1.34, .102), (-1.36, 1.22, .083), (-1.32, 1.15, .001)]
    vertices, quads = [], []
    rings = 48
    for k, (cx, cz, radius) in enumerate(profile):
        before, after = profile[max(0, k - 1)], profile[min(k + 1, len(profile) - 1)]
        forward = Vector((after[0] - before[0], 0, after[1] - before[1])).normalized()
        if k >= 8:
            forward = -forward
        for i in range(rings):
            a = math.tau * i / rings
            vertices.append((cx + radius * math.cos(a) * forward.z, radius * math.sin(a),
                             cz - radius * math.cos(a) * forward.x))
    for j in range(len(profile) - 1):
        for i in range(rings):
            a, b = j * rings + i, j * rings + (i + 1) % rings
            quads.append((a, a + rings, b + rings, b))
    spout = kit.mesh('Hollow ceramic spout', vertices, quads, clay, smooth=True)
    spout.data.materials.append(lip)
    for polygon in spout.data.polygons[6 * rings:8 * rings]:
        polygon.material_index = 1

    linen = kit.procedural('Woven grey flax', 'fabric', colors=['#51493C', '#887A66', '#B9A98D'], scale=3)
    for i in range(3):
        kit.box(f'Linen fold {i + 1}', (1.40 - i * .12, 1.12 - i * .15, .055), (-2.03, .58, .035 + i * .045),
                linen, rotation=(0, 0, -14 + i * 5), bevel=.025)
    kit.world('#464F63', strength=.20)
    kit.area('Warm window', (-3.1, -2.4, 4.4), (0, 0, .72), 530, '#FFE2B4', 2.9, size_y=3.6)
    kit.area('Cool glaze reflection', (1.8, -2.8, 2.6), (0, 0, .80), 115, '#B3D2FE', 2.4, size_y=.65)
    kit.area('Copper edge light', (1.5, 2.3, 3.7), (0, 0, .78), 365, '#FFD096', 2.5, size_y=1.1)
    cam = kit.camera((-1.37, -6.96, 3.30), (0, 0, .88), lens=54, dof=7.25, fstop=4.8)
    kit.dolly(cam, (-1.37, -6.96, 3.30), (1.22, -6.53, 2.70), (0, 0, .88), (0, 0, .87))
    kit.render(exposure=.35)
