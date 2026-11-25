"""A 3D bar chart of five species over ten years, growing year by year under a big year counter.

Teaches:
- data-driven animation from an inline table: one bar per (species, year), with the first row present from
  the beginning and the others growing in individual time slots;
- growing bevelled bars with a shape key (base -> full height) instead of object scale, so the
  bevel modifier keeps round, unstretched edges at every height;
- a "changing" year label built from ten text objects switched with kit.visible (text bodies cannot
  be keyframed), and a set of persistent legend cards with values that change as each row lands;
- screen-aligned legend cards and upright chart axis labels for a camera orbit;
- a clean infographic look: matte flat colours, a floor grid of thin bevelled strips, an blue
  gallery world and one big soft key light for gentle contact shadows.
"""
import math

import bpy
from mathutils import Vector

# ---------------------------------------------------------------- inline data (thousands)
YEARS = list(range(2015, 2025))
SPECIES = [
    # name,          colour,    population per year
    ('Red fox',      '#E4572E', [31, 32, 34, 33, 35, 37, 36, 38, 40, 41]),
    ('Hedgehog',     '#F3A712', [42, 39, 36, 34, 31, 29, 27, 26, 24, 22]),
    ('Barn owl',     '#2E86AB', [8, 9, 11, 12, 14, 15, 17, 20, 22, 25]),
    ('Otter',        '#3BB273', [5, 6, 6, 8, 9, 11, 12, 13, 15, 16]),
    ('Red squirrel', '#8E5572', [18, 17, 17, 16, 15, 15, 14, 14, 13, 13]),
]

# ---------------------------------------------------------------- layout (metres)
COL = 1.25            # spacing between species (X)
ROW = 0.95            # spacing between years (Y, front to back)
BAR = (0.72, 0.58)    # bar footprint
PER_K = 0.085         # metres of bar per thousand animals
BASE_H = 0.02         # height of a bar before it grows
T0, T1 = 0.04, 0.84   # the ten years play out over this part of the shot, then hold
SLOT = (T1 - T0) / len(YEARS)
INK = '#F2F8FA'
FLOOR = '#283F57'


def x_of(i):
    return (i - (len(SPECIES) - 1) / 2) * COL


def y_of(k):
    return k * ROW


def face_camera(kit, obj, cam):
    """Keep an upright label turned toward the camera around Z only (it never tilts).

    Text reads from its local +Z; kit.text's rotation (90, 0, 0) turns that to world -Y. We parent
    the label to a pivot empty and let the pivot's -Y axis track the camera with Z locked.
    """
    pivot = kit.empty(f'{obj.name} pivot', tuple(obj.location), size=0.1)
    obj.parent = pivot
    obj.location = (0, 0, 0)
    con = pivot.constraints.new('LOCKED_TRACK')
    con.target, con.track_axis, con.lock_axis = cam, 'TRACK_NEGATIVE_Y', 'LOCK_Z'
    return pivot


def bar(kit, name, height, material, location):
    """Bevelled bar with origin at its base and a 'Grow' shape key from BASE_H to `height`."""
    w, d = BAR
    obj = kit.box(name, (w, d, BASE_H), (location[0], location[1], BASE_H / 2), material)
    # Move the origin to the base so growth goes up from the floor.
    for v in obj.data.vertices:
        v.co.z += BASE_H / 2
    obj.location.z = 0.0
    obj.shape_key_add(name='Basis')
    grow = obj.shape_key_add(name='Grow', from_mix=False)
    for v in grow.data:
        if v.co.z > BASE_H * 0.5:
            v.co.z = height
    kit.bevel(obj, width=0.035, segments=3)
    return obj, grow


def build(kit):
    # ---------------------------------------------------------------- gallery light
    kit.world('#BCD9E9', strength=0.43)
    kit.area('Gallery key', location=(-5, -3, 10), target=(0, 4, 0), power=3700, color='#FFF3DF', size=5)
    kit.area('Gallery fill', location=(9, 2, 5), target=(0, 4, 1), power=540, color='#E5EEFF', size=5)
    floor = kit.material('Gallery floor', FLOOR, roughness=0.85)
    kit.ground(floor, size=2000, z=-0.43)
    kit.area('Blue edge', location=(3, 13, 8), target=(0, 4, 1.0), power=1690, color='#B9DAFF', size=4)

    # ---------------------------------------------------------------- floor grid
    # Thin, slightly raised strips under the chart: rows between years, columns between species.
    grid = kit.material('Grid line', '#638494', roughness=0.65)
    x_lo, x_hi = x_of(0) - COL * 0.65, x_of(len(SPECIES) - 1) + COL * 0.65
    y_lo, y_hi = y_of(0) - ROW * 0.6, y_of(len(YEARS) - 1) + ROW * 0.6
    for k in range(len(YEARS) + 1):
        y = y_lo + k * (y_hi - y_lo) / len(YEARS)
        kit.box(f'Grid row {k}', (x_hi - x_lo, 0.025, 0.006), ((x_lo + x_hi) / 2, y, 0.003), grid)
    for i in range(len(SPECIES) + 1):
        x = x_lo + i * (x_hi - x_lo) / len(SPECIES)
        kit.box(f'Grid column {i}', (0.025, y_hi - y_lo, 0.006), (x, (y_lo + y_hi) / 2, 0.003), grid)
    centre_y = (y_lo + y_hi) / 2
    plinth = kit.material('Chart plinth', '#3B5268', roughness=0.55)
    foot = kit.material('Recessed plinth edge', '#1D2C3D', roughness=0.44, coat=0.24)
    kit.box('Lipped chart deck', (x_hi - x_lo + 1.45, y_hi - y_lo + 0.80, 0.16),
            (-0.18, centre_y, -0.08), plinth, bevel=0.075)
    kit.box('Recessed base', (x_hi - x_lo + 1.21, y_hi - y_lo + 0.59, 0.27),
            (-0.18, centre_y, -0.295), foot, bevel=0.09)

    # ---------------------------------------------------------------- camera: quarter-turn orbit
    centre = Vector((0.0, y_of(len(YEARS) - 1) / 2, 0.0))
    cam = kit.camera(location=(0, -12, 7), target=centre + Vector((0, 0, 1.4)), lens=38.0)
    kit.orbit(cam, center=centre, radius=14.85, height=10.6, start=-52, sweep=80, ease_kind='in_out',
              target_height=1.35)

    ink = kit.flat('Label ink', INK)

    # Each interval ends one frame before the next begins. The visibility helper includes both endpoints.
    year_starts = [1, *(round(kit.frame(T0 + k * SLOT)) for k in range(1, len(YEARS))), kit.frames + 1]

    # ---------------------------------------------------------------- bars
    for i, (name, colour, values) in enumerate(SPECIES):
        mat = kit.material(f'{name} bar', colour, roughness=0.39, specular=0.36, coat=0.18)
        for k, (year, v) in enumerate(zip(YEARS, values)):
            _, grow = bar(kit, f'{name} {year}', v * PER_K, mat, (x_of(i), y_of(k)))
            start = T0 + k * SLOT
            # Open on 2015; each remaining row grows into a clean, readable chart.
            if k == 0:
                grow.value = 1.0
            else:
                kit.animate(grow, 'value', lambda t, s=start: kit.ease(kit.segment(t, s, s + SLOT * 0.82), 'out'),
                            step=1)
    # Year ticks flat along the left edge.
    for k, year in enumerate(YEARS):
        kit.text(str(year), size=0.26, location=(x_lo - 0.55, y_of(k), 0.01), rotation=(0, 0, 0),
                 material=ink, extrude=0.006, align='CENTER', name=f'Year tick {year}')

    # Value axis: an upright scale at the back-left corner with ticks every 10k.
    axis_x, axis_y = x_lo - 0.15, y_hi + 0.15
    kit.cylinder('Value axis', 0.02, 45 * PER_K, (axis_x, axis_y, 45 * PER_K / 2), ink, segments=12)
    for v in range(0, 50, 10):
        kit.box(f'Axis tick {v}', (0.18, 0.02, 0.02), (axis_x + 0.09, axis_y, v * PER_K), ink)
        tick = kit.text(f'{v}k', size=0.24, location=(axis_x - 0.32, axis_y, v * PER_K), rotation=(90, 0, 0),
                        material=ink, extrude=0.005, name=f'Axis label {v}k')
        face_camera(kit, tick, cam)

    # ---------------------------------------------------------------- the big year counter
    # Keep the year and caption in camera space so the orbit cannot crop them.
    counter_at = (0, 1.48, -4.0)
    accent = kit.flat('Year counter', '#EAF2F5')
    for k, year in enumerate(YEARS):
        label = kit.text(str(year), size=0.49, location=counter_at, rotation=(0, 0, 0),
                         material=accent, extrude=0.01, bevel=0.001, name=f'Year counter {year}')
        label.parent = cam
        label.visible_shadow = False
        label['studio_ground'] = True
        kit.visible(label, kit.t(year_starts[k]), kit.t(year_starts[k + 1] - 1))
    caption = kit.text('Wildlife populations', size=0.181, location=(0, 1.19, -4),
                       rotation=(0, 0, 0), material=kit.flat('Caption', '#A8C3D3'), name='Chart caption')
    labels = [caption]
    card = kit.flat('Legend panel', '#151F2D')
    for i, ((name, color, values), short_name) in enumerate(zip(SPECIES, ('Fox', 'Hedgehog', 'Owl', 'Otter', 'Squirrel'))):
        x = -1.37 + i * 0.685
        tint = kit.flat(f'{name} legend color', color)
        panel = kit.box(f'{name} data card', (0.63, 0.40, 0.025), (x, -1.46, -4.07), card, bevel=0.028)
        rule = kit.box(f'{name} swatch', (0.39, 0.018, 0.007), (x, -1.290, -4.0), tint, bevel=0.006)
        label = kit.text(short_name, 0.112, (x, -1.56, -4), (0, 0, 0), ink, name=f'Species label {name}')
        labels.extend((panel, rule, label))
        for k, (year, value) in enumerate(zip(YEARS, values)):
            figure = kit.text(f'{value}k', 0.205, (x, -1.43, -4), (0, 0, 0), ink, name=f'Value {name} {year}')
            kit.visible(figure, kit.t(year_starts[k]), kit.t(year_starts[k + 1] - 1))
            labels.append(figure)
    for label in labels:
        label.parent = cam
        label.visible_shadow = False
        label['studio_ground'] = True

    kit.render(exposure=-0.1, look='AgX - Base Contrast', motion_blur=False)
