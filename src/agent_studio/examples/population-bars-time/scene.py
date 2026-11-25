"""A 3D bar chart of five species over ten years, growing year by year under a big year counter.

Teaches:
- data-driven animation from an inline table: one bar per (species, year), each grown in its
  own time slot so the chart fills in row by row;
- growing bevelled bars with a shape key (base -> full height) instead of object scale, so the
  bevel modifier keeps round, unstretched edges at every height;
- a "changing" year label built from ten text objects switched with kit.visible (text bodies cannot
  be keyframed), and value labels that appear as each row lands;
- labels that stay readable through a camera orbit with a Locked Track constraint;
- a clean infographic look: matte flat colours, a floor grid of thin bevelled strips, an off-white
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
INK = '#23262D'
FLOOR = '#F1EFEA'


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
    kit.world('#E9E7E2', strength=0.9)
    kit.area('Gallery key', location=(-6, -4, 11), target=(0, 4, 0), power=5200, color='#FFF6EC', size=7)
    kit.area('Gallery fill', location=(9, 2, 5), target=(0, 4, 1), power=900, color='#EEF3FF', size=6)
    floor = kit.material('Gallery floor', FLOOR, roughness=0.85)
    kit.ground(floor, size=200)

    # ---------------------------------------------------------------- floor grid
    # Thin, slightly raised strips under the chart: rows between years, columns between species.
    grid = kit.material('Grid line', '#C9C6BF', roughness=0.8)
    x_lo, x_hi = x_of(0) - COL * 0.65, x_of(len(SPECIES) - 1) + COL * 0.65
    y_lo, y_hi = y_of(0) - ROW * 0.6, y_of(len(YEARS) - 1) + ROW * 0.6
    for k in range(len(YEARS) + 1):
        y = y_lo + k * (y_hi - y_lo) / len(YEARS)
        kit.box(f'Grid row {k}', (x_hi - x_lo, 0.025, 0.006), ((x_lo + x_hi) / 2, y, 0.003), grid)
    for i in range(len(SPECIES) + 1):
        x = x_lo + i * (x_hi - x_lo) / len(SPECIES)
        kit.box(f'Grid column {i}', (0.025, y_hi - y_lo, 0.006), (x, (y_lo + y_hi) / 2, 0.003), grid)
    plinth = kit.material('Chart plinth', '#E3E0D9', roughness=0.7)
    kit.box('Chart plinth', (x_hi - x_lo + 0.5, y_hi - y_lo + 0.5, 0.05),
            ((x_lo + x_hi) / 2, (y_lo + y_hi) / 2, -0.024), plinth, bevel=0.02)

    # ---------------------------------------------------------------- camera: quarter-turn orbit
    centre = Vector((0.0, y_of(len(YEARS) - 1) / 2, 0.0))
    cam = kit.camera(location=(0, -12, 7), target=centre + Vector((0, 0, 1.4)), lens=38.0)
    kit.orbit(cam, center=centre, radius=12.5, height=7.2, start=-50.0, sweep=90.0, ease_kind='in_out',
              target_height=1.3)

    ink = kit.material('Label ink', INK, roughness=0.6)

    # ---------------------------------------------------------------- bars
    for i, (name, colour, values) in enumerate(SPECIES):
        mat = kit.material(f'{name} bar', colour, roughness=0.55, specular=0.3)
        for k, (year, v) in enumerate(zip(YEARS, values)):
            obj, grow = bar(kit, f'{name} {year}', v * PER_K, mat, (x_of(i), y_of(k)))
            start = T0 + k * SLOT
            # Each row rises over 1.4 slots, overlapping the next a little, with a soft overshoot.
            kit.animate(grow, 'value', lambda t, s=start: kit.ease(kit.segment(t, s, s + SLOT * 1.4), 'back_out'),
                        step=1)
            # Value label above the bar: visible from when the row lands until the next row lands.
            label = kit.text(f'{v}k', size=0.3, location=(x_of(i), y_of(k), v * PER_K + 0.28),
                             rotation=(90, 0, 0), material=ink, extrude=0.01, name=f'Value {name} {year}')
            face_camera(kit, label, cam)
            end = 1.0 if k == len(YEARS) - 1 else T0 + (k + 1) * SLOT + SLOT * 1.2
            kit.visible(label, start + SLOT * 1.2, end)
        # Species name flat on the floor in front of its column, in its own colour.
        kit.text(name, size=0.3, location=(x_of(i), y_lo - 0.55, 0.01), rotation=(0, 0, 0),
                 material=kit.material(f'{name} label', colour, roughness=0.6), extrude=0.008,
                 name=f'Species label {name}')
        kit.box(f'{name} swatch', (0.72, 0.1, 0.02), (x_of(i), y_lo - 0.2, 0.01), mat, bevel=0.005)

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
    counter_at = Vector((x_hi + 0.4, y_hi + 1.2, 4.6))
    accent = kit.material('Year counter', '#23262D', roughness=0.4)
    for k, year in enumerate(YEARS):
        label = kit.text(str(year), size=1.5, location=counter_at, rotation=(90, 0, 0), material=accent,
                         extrude=0.06, bevel=0.01, name=f'Year counter {year}')
        face_camera(kit, label, cam)
        start = 0.0 if k == 0 else T0 + k * SLOT
        end = 1.0 if k == len(YEARS) - 1 else T0 + (k + 1) * SLOT
        kit.visible(label, start, end)
    caption = kit.text('Wildlife populations, thousands', size=0.32, location=counter_at - Vector((0, 0, 1.05)),
                       rotation=(90, 0, 0), material=kit.material('Caption', '#6B6F78', roughness=0.6),
                       extrude=0.004, name='Chart caption')
    face_camera(kit, caption, cam)

    kit.render(exposure=0.0, look='AgX - Base Contrast', motion_blur=False)
