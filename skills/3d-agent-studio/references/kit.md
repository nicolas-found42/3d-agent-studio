# Scene kit reference

Generated from `src/agent_studio/kit.py` by `tools/kit_reference.py`; do not edit by hand.

Scene kit handed to agent-written scripts as `build(kit)`.

Runs inside Blender. Everything here is a convenience over `bpy`: scripts may mix kit calls with
raw `bpy`, `bmesh` and `mathutils`. Units are metres, angles are degrees unless a name says
radians, colors are '#RRGGBB' strings or sRGB tuples, and time `t` runs 0..1 over the shot.

Conventions the studio relies on:
- `kit.camera(...)` (or setting `kit.scene.camera`) chooses the shot camera.
- Animate with keyframes (`kit.animate`, `kit.key`, the camera rigs); handlers and Python drivers
  do not survive into the saved scene.
- For loops (`kit.loop`), frame `kit.frames + 1` must look like frame 1. Use `kit.wave`,
  `kit.loop_noise`, whole turns, or `kit.orbit(..., sweep=360)`.
- Mark big floors with `ground=True` (or use `kit.ground`) and volumes with `kit.haze`, so the
  review overview frames the subject rather than the horizon.

## Module helpers

- `srgb_to_linear(c)` — 
- `rgba(value, alpha=1.0)` — '#RRGGBB', '#RRGGBBAA', an sRGB (r, g, b[, a]) tuple in 0..1, or a gray float -> linear RGBA.
- `hsv(h, s, v)` — Hue 0..1, saturation, value -> '#RRGGBB'.
- `ease(t, kind='in_out', power=3.0)` — Easing of 0..1 progress. kind: linear, in, out, in_out (power sets steepness), smooth,
- `lerp(a, b, t)` — Linear blend of numbers or vectors.
- `segment(t, start, end)` — Local 0..1 progress of `t` within [start, end], clamped.
- `catmull_rom(points, t, closed=False)` — Point on a centripetal-ish uniform Catmull-Rom spline through `points` at 0..1.

## `kit` attributes

`kit.prompt`, `kit.brief`, `kit.seed`, `kit.rng` (seeded `random.Random`), `kit.fps`, `kit.seconds`, `kit.frames` (frame count), `kit.loop`, `kit.orientation`, `kit.width`/`kit.height`/`kit.aspect` (master size), `kit.scene`, `kit.references` (objects with `id`, `kind`, `role`, `name`, `note`, `paths`, and for videos `times`), `kit.assets` (declared asset manifests by ID).


## Time

- `kit.t(frame)`  
  Shot progress of a frame: 0 at frame 1, 1 at the last frame (or frames+1 for loops).
- `kit.frame(t)`
- `kit.key_frames(step=1)`
- `kit.wave(t, cycles=1, phase=0.0)`  
  sin over whole cycles: loop-safe when cycles is an integer.
- `kit.loop_noise(t, seed=0, cycles=1, octaves=2, scale=1.0)`  
  Smooth noise in -1..1 that repeats exactly every 1/cycles of t (sampled on a circle).
- `kit.noise(x, y=0.0, z=0.0, octaves=3, basis='PERLIN_NEW')`

## Animation

- `kit.animate(target, path, fn, step=1, index=-1, interpolation='LINEAR')`  
  Key `target.path` from fn(t) at every `step` frames (t is shot progress 0..1). `target` is any animatable struct (object, light data, material node input, ...).
- `kit.key(target, path, keys, interpolation='BEZIER', index=-1)`  
  Explicit keys: [(t or frame, value), ...]. Floats <= 1 are shot progress; ints are frames.
- `kit.spin(obj, axis='Z', turns=1.0, ease_kind='linear', offset_deg=0.0)`  
  Rotate about a local axis by `turns` over the shot (whole turns are loop-safe).
- `kit.bob(obj, amplitude=0.1, cycles=1, axis='Z', phase=0.0)`
- `kit.pulse(material, low=0.0, high=5.0, cycles=1, phase=0.0)`  
  Animate a material's emission strength between low and high.
- `kit.grow(obj, start=0.0, end=0.3, ease_kind='back_out', from_scale=0.0)`  
  Scale an object up from `from_scale` during the [start, end] part of the shot.
- `kit.move(obj, points, start=0.0, end=1.0, ease_kind='in_out', closed=False)`  
  Move an object along a smooth path through `points` during [start, end].
- `kit.visible(obj, start=0.0, end=1.0)`  
  Show an object only while shot progress is within [start, end] (hard cuts).

## Collections

- `kit.collection(name)`
- `kit.empty(name='Empty', location=(0, 0, 0), display='PLAIN_AXES', size=0.5, collection=None)`
- `kit.parent(child, parent, keep_transform=True)`  
  Parent an object, preserving its current world transform by default.
- `kit.look_at(obj, target, up='Y')`

## Materials

- `kit.material(name, color='#BBBBBB', roughness=0.5, metallic=0.0, emission=None, emission_strength=0.0, transmission=0.0, ior=1.45, alpha=1.0, subsurface=0.0, subsurface_radius=(1, 0.2, 0.1), coat=0.0, sheen=0.0, specular=0.5, bump=None, thin_wall=False)`  
  Principled BSDF material. bump=(scale, strength) adds procedural surface noise.
- `kit.bsdf(mat)`
- `kit.glass(name='Glass', color='#FFFFFF', roughness=0.0, ior=1.45)`
- `kit.emissive(name='Emission', color='#FFFFFF', strength=5.0)`
- `kit.flat(name='Flat', color='#FFFFFF')`  
  Unlit flat color (holdout of lighting): graphic, poster and data-viz looks.
- `kit.gradient_material(name, colors, axis='Z', low=0.0, high=1.0, roughness=0.5, emission_strength=0.0)`  
  Color ramp along an object-space axis between `low` and `high`.
- `kit.color_ramp(nt, colors, interpolation='LINEAR')`  
  Add a color-ramp node to a shader tree from colors or (position, color) pairs.
- `kit.procedural(name, kind='stone', colors=None, scale=1.0, roughness=None, bump=0.3)`  
  Procedural surfaces: stone, marble, wood, concrete, brushed_metal, rust, fabric, ground, sand, plastic, ceramic, terrazzo, bark, leaf, snow, lava, water.
- `kit.image(source, index=0, non_color=False)`  
  Load an image from a reference ID (index picks a video frame) or an asset ID.
- `kit.file(source, index=0, filename=None, kinds=None)`  
  Filesystem path for a reference ID or declared asset ID (optionally a file inside it).
- `kit.textured(name, source, scale=1.0, projection='BOX', bump=1.0, displacement=0.0, roughness=None, tint=None, metallic=None)`  
  PBR material from a texture asset (color/normal_gl/roughness/... maps), box-projected in object space so it needs no UVs. `scale` is texture repeats per metre.
- `kit.image_material(name, source, index=0, emission=0.0, roughness=0.5, alpha=True)`  
  Material showing a reference/asset image via the object's UVs (e.g. on kit.image_plane).
- `kit.toon(name, color='#E0E0E0', shades=3, shadow='#303040')`  
  Cel-shaded material (EEVEE only: call kit.render(engine='EEVEE')). In Cycles it falls back to its diffuse base.
- `kit.assign(obj, mat, slot=None)`

## Geometry

- `kit.mesh(name, verts, faces, material=None, location=(0, 0, 0), rotation=(0, 0, 0), smooth=False, collection=None, ground=False, edges=())`
- `kit.box(name='Box', size=(1, 1, 1), location=(0, 0, 0), material=None, rotation=(0, 0, 0), bevel=0.0, collection=None, ground=False)`  
  Axis-aligned box centred on `location` (size is full extents).
- `kit.cylinder(name='Cylinder', radius=0.5, depth=1.0, location=(0, 0, 0), material=None, rotation=(0, 0, 0), segments=48, bevel=0.0, smooth=True, cap=True, collection=None, radius_top=None)`
- `kit.cone(name='Cone', radius=0.5, depth=1.0, location=(0, 0, 0), material=None, rotation=(0, 0, 0), segments=48, radius_top=0.0, smooth=True, collection=None)`
- `kit.sphere(name='Sphere', radius=0.5, location=(0, 0, 0), material=None, segments=48, rings=24, smooth=True, collection=None, scale=(1, 1, 1))`
- `kit.ico(name='Ico', radius=0.5, location=(0, 0, 0), material=None, subdivisions=3, smooth=False, collection=None)`
- `kit.torus(name='Torus', radius=1.0, thickness=0.25, location=(0, 0, 0), material=None, rotation=(0, 0, 0), segments=64, sides=24, collection=None)`
- `kit.plane(name='Plane', size=(2, 2), location=(0, 0, 0), material=None, rotation=(0, 0, 0), subdivisions=0, collection=None, ground=False)`
- `kit.ground(material=None, size=400, z=0.0, name='Ground')`  
  Large floor marked as ground so the review overview ignores its extent.
- `kit.lathe(name, profile, segments=64, material=None, location=(0, 0, 0), rotation=(0, 0, 0), smooth=True, collection=None)`  
  Revolve a (radius, z) profile around Z. Close the ends by starting/ending at radius 0.
- `kit.extrude(name, polygon, height=1.0, material=None, location=(0, 0, 0), rotation=(0, 0, 0), bevel=0.0, collection=None)`  
  Prism from a 2D (x, y) outline (counter-clockwise) extruded up by `height`.
- `kit.arch_profile(span, rise=None, kind='gothic', steps=24)`  
  Intrados of an arch as [(x, z, cx, cz)]: points from left to right springing, each with the centre of the arc it lies on. kind: gothic (two-centred, pointed), round, segmental. A gothic rise near or below half the span is replaced by the equilateral rise.
- `kit.arch(name='Arch', span=2.0, rise=None, kind='gothic', depth=0.5, thickness=0.3, location=(0, 0, 0), rotation=(0, 0, 0), material=None, pier_height=0.0, pier_width=None, collection=None, steps=24)`  
  An arch ring in the XZ plane (depth along Y), springing at z=pier_height, with optional square piers below. Returns the ring object (piers are parented to it).
- `kit.tube(name, points, radius=0.05, material=None, closed=False, resolution=12, collection=None, taper=None, smooth=True, spline=None)`  
  Sweep a circular tube along control points. Use spline='POLY' for exact corners or 'NURBS' for smooth movable control points. The default uses Bézier for up to 64 points.
- `kit.text(body, size=1.0, location=(0, 0, 0), rotation=(90, 0, 0), material=None, extrude=0.0, bevel=0.0, align='CENTER', font=None, name=None, collection=None, spacing=1.0)`  
  3D text. font is a reference ID, a fontsource:/asset ID, or None for Blender's default.
- `kit.font(source)`
- `kit.instance(obj, location=(0, 0, 0), rotation=(0, 0, 0), scale=1.0, name=None, collection=None)`  
  Linked duplicate sharing mesh data: cheap repetition.
- `kit.array(obj, count, offset=(1, 0, 0), rotation_step=(0, 0, 0), name=None)`  
  `count` linked copies stepped by `offset` (and rotation_step degrees). Returns them all.
- `kit.scatter(prototypes, count, area=(-10, 10, -10, 10), surface=None, scale=(0.8, 1.2), rotate=True, min_distance=0.0, seed=None, z=0.0, align_to_normal=False, collection=None, avoid=())`  
  Scatter linked copies of prototype object(s). With `surface`, drop each onto it by raycast. `avoid` is a list of (x, y, radius) circles to keep clear. Returns the instances.
- `kit.terrain(name='Terrain', size=40.0, resolution=160, height=4.0, roughness=0.5, scale=0.08, seed=None, material=None, flatten_center=0.0, ridged=False, ground=True, location=(0, 0, 0))`  
  Heightfield landscape from fractal noise. flatten_center (metres) keeps a level area.
- `kit.height_at(obj, x, y)`
- `kit.rock(name='Rock', radius=1.0, location=(0, 0, 0), material=None, seed=None, roughness=0.35, squash=0.7, detail=3, collection=None)`
- `kit.tree(name='Tree', height=6.0, location=(0, 0, 0), style='broadleaf', bark=None, leaves=None, seed=None, collection=None)`  
  Stylized procedural tree: broadleaf, conifer, palm or bare. Returns the root empty.

## Modifiers

- `kit.bevel(obj, width=0.02, segments=3, harden=True)`
- `kit.subdivide(obj, levels=2, render_levels=None)`
- `kit.displace(obj, strength=0.2, scale=1.0, kind='CLOUDS', seed=None, detail=2)`
- `kit.solidify(obj, thickness=0.05, offset=-1.0)`
- `kit.boolean(obj, cutter, operation='DIFFERENCE', hide_cutter=True)`
- `kit.outline(obj, thickness=0.02, color='#111111')`  
  Inverted-hull ink outline (works in Cycles and EEVEE).

## Lights & world

- `kit.world(color='#1A1D22', strength=1.0, top=None)`  
  Flat (or two-tone gradient if top is given) world light and background.
- `kit.sky(sun_elevation=35.0, sun_rotation=0.0, strength=0.12, altitude=0.0, air=1.0, aerosol=1.0, ozone=1.0, sun_disc=True, sun_intensity=1.0)`  
  Physical multiple-scattering daylight sky that lights the scene with its own sun. Its physical intensity is high: strength 0.08-0.2 suits exteriors at exposure 0; an interior lit through windows wants about 0.08 with kit.render(exposure=1).
- `kit.hdri(source, strength=1.0, rotation=0.0, background=None, background_strength=1.0)`  
  Image-based lighting from an HDRI asset. background='#RRGGBB' hides the image behind a color.
- `kit.sun(elevation=45.0, azimuth=30.0, strength=3.0, color='#FFF4E5', angle=1.0, name='Sun')`  
  Directional sunlight; azimuth is degrees from +Y toward +X; strength in W/m^2.
- `kit.area(name='Area', location=(0, -4, 4), target=(0, 0, 0), power=500.0, color='#FFFFFF', size=2.0, shape='RECTANGLE', size_y=None, spread=180.0)`
- `kit.point(name='Point', location=(0, 0, 3), power=200.0, color='#FFFFFF', radius=0.1)`
- `kit.spot(name='Spot', location=(0, -4, 4), target=(0, 0, 0), power=800.0, color='#FFFFFF', angle=35.0, blend=0.3, radius=0.1)`
- `kit.three_point(target=(0, 0, 1), distance=6.0, power=800.0, warm='#FFE2C2', cool='#C9DCFF', azimuth=0.0)`  
  Studio key, fill and rim lights around `target`, rotated by azimuth degrees.
- `kit.haze(density=0.02, color='#FFFFFF', anisotropy=0.3, size=(60, 60, 30), location=(0, 0, 15), name='Atmospheric haze')`  
  Low-density volume box for light shafts and depth. Keep it around, not just behind, the shot.

## Camera

- `kit.camera(location=(0, -10, 2), target=(0, 0, 1), lens=35.0, name='Camera', sensor=36.0, shift=(0, 0), clip=(0.05, 2000.0), ortho_scale=None, dof=None, fstop=4.0, active=True)`  
  Create the shot camera. `target` adds a 'Camera target' empty with a Track To constraint; animate that empty to change where the camera looks. dof=distance or object focuses.
- `kit.target_of(cam)`
- `kit.dolly(cam, start, end, target_start=None, target_end=None, ease_kind='in_out', power=2.5, t0=0.0, t1=1.0)`  
  Straight move from start to end (and optionally move the look target).
- `kit.orbit(cam, center=(0, 0, 0), radius=8.0, height=2.0, start=0.0, sweep=360.0, ease_kind='linear', target_height=None, height_wave=0.0)`  
  Circle around center. sweep=360 with linear ease is seamless for loops.
- `kit.crane(cam, base, rise=4.0, push=2.0, ease_kind='in_out', look=None)`  
  Rise up while pushing toward the look target.
- `kit.path(cam, points, targets=None, ease_kind='in_out', power=2.0, closed=False, look_ahead=0.0)`  
  Smooth constant-speed camera path through `points`. `targets` moves the look target along its own spline; look_ahead (0..0.2) aims down the path instead.
- `kit.handheld(cam, amount=0.6, cycles=2, seed=3)`  
  Loop-safe subtle rotational shake in degrees (applied as delta rotation).
- `kit.rack_focus(cam, distances, fstop=2.0)`  
  Animate focus distance: distances=[(t, metres), ...].
- `kit.zoom(cam, lens_start, lens_end, ease_kind='in_out')`

## Imports

- `kit.import_model(source, location=(0, 0, 0), rotation=(0, 0, 0), size=None, scale=1.0, on_ground=True, name=None)`  
  Import a model reference or asset (glb/gltf/obj/fbx/usd/stl/ply/blend). Returns a parent empty. size=metres fits the largest dimension; on_ground puts its lowest point at z=location.z.
- `kit.play_animation(root, speed=1.0, action=None, start=0.0)`  
  Repeat an imported model's embedded action. `action` filters action names on this model, `start` is shot progress, and `speed` multiplies the source frame rate. For a seamless loop the speed-adjusted clip duration must divide the shot duration.
- `kit.blend_material(source)`  
  Append the first material from a .blend asset (e.g. a BlenderKit material).
- `kit.image_plane(source, height=2.0, location=(0, 0, 1), rotation=(90, 0, 0), index=0, emission=0.0, name=None)`  
  A plane sized to the image's aspect, showing a reference or asset image.
- `kit.data(source)`  
  Parsed data reference: JSON value, or a list of row dicts for CSV/TSV (numbers converted).
- `kit.read_text(source)`  
  Text of a shot list or notes reference.
- `kit.svg(source, size=2.0, extrude=0.02, material=None, location=(0, 0, 0), rotation=(90, 0, 0))`  
  Import an SVG logo as curves under a parent empty, fitted to `size` metres wide.
- `kit.references_by_role(role)`

## Figures

- `kit.figure(name='Figure', height=1.75, location=(0, 0, 0), material=None, head_material=None, build=1.0, facing=0.0)`  
  Stylized jointed mannequin. Returns a dict of joint empties (root, hips, chest, neck, head, shoulder_l/r, elbow_l/r, hip_l/r, knee_l/r). Rotate joints (kit.walk, kit.idle, kit.wave_hand).
- `kit.walk(J, cycles=2, stride=30.0, arm_swing=25.0, bounce=0.03, travel=None)`  
  Loop-safe walk cycle on a kit.figure. travel=(start, end) also moves the root (not loop-safe).
- `kit.idle(J, cycles=1, breathe=0.015, sway=2.0)`  
  Loop-safe breathing and weight shift.
- `kit.wave_hand(J, side='r', cycles=3, start=0.0, end=1.0)`

## Physics

- `kit.particles(emitter, count=500, lifetime=None, velocity=2.0, random_velocity=0.5, gravity=1.0, instance=None, size=0.05, size_random=0.3, start=0.0, end=0.7, seed=None, physics='NEWTON', render_emitter=False)`  
  Particle system on `emitter`; the studio bakes it into the saved scene. instance= an object to use as each particle (hidden at origin by default).
- `kit.rigid_body(obj, kind='ACTIVE', mass=1.0, shape='CONVEX_HULL', friction=0.5, bounce=0.2)`  
  Rigid body simulation (baked by the studio). Passive bodies are static colliders.

## Render

- `kit.glow(strength=0.35, size=0.25, threshold=1.0)`  
  Add fog glow to bright pixels in a new scene compositor and return its Glare node. For a custom compositor, configure the Glare node in that graph directly.
- `kit.render(engine=None, motion_blur=None, shutter=None, exposure=None, look=None, bounces=None, transparent=None, film_filter=None, view_transform=None, gamma=None, freestyle=None, line_thickness=1.5, line_color='#111111', volume_step=None)`  
  Override render defaults. engine='EEVEE' for toon/stylized looks; look is an AgX look such as 'AgX - Punchy' or 'AgX - Base Contrast'. Samples are controlled by the studio stage.

## Utilities

- `kit.bounds(objects)`
- `kit.note(text)`  
  Log a line to the stage run.log (e.g. how a reference was interpreted).
