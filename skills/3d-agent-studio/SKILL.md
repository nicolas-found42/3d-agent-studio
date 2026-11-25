---
name: 3d-agent-studio
description: Turn any prompt, with or without reference photos, videos, models, data, logos or shot lists, into an animated Blender scene and a silent video, then review and promote it.
---

# 3D Agent Studio

You write the scene. The studio has no presets: you author a Blender Python script, `def build(kit): ...`, and the studio checks it, runs it, saves the editable `.blend`, renders it on the GPU, and gates promotion on your review. Use `studio_*` via MCP or `3d-agent-studio` in a terminal. Read [Operations](references/operations.md) for exact arguments and [the kit reference](references/kit.md) for every helper.

## 1. Understand the request

- Restate the subject, setting, mood, motion and camera in a few lines before writing code. If the user points at a project or repository (for example "represent my society sim"), read enough of it to name its real entities, mechanics and look, and put that understanding into the brief's `prompt`. The studio never reads repositories.
- Ingest every file the user supplies with `studio_ingest(path, role)`: images as `subject`, `style`, `composition`, `palette` or `storyboard`; a video becomes up to 20 scene frames (`max_frames` to change); models are `asset`; CSV/JSON are `data`; SVG is a `logo`; fonts; text shot lists. Look at reference images yourself before modelling. A `style` reference sets the look, not the content; a `subject` reference is what must be recognisable.
- Pick `orientation` (vertical 9:16, horizontal 16:9, square, portrait 4:5, ultrawide 21:9), `seconds` (2–30), `fps` (24 default; 30, 60, 120), and `loop` only when a seamless loop is wanted. Add open assets by ID in `brief.assets` (`studio_doctor` lists the sources; licenses are checked and credited automatically).

## 2. Study examples, then design

Search `studio_examples` with words from the request. Read scripts from at least three categories with `include_script: true`. If one category dominates the results, search the others by category. Borrow a technique, such as a camera rig or a material recipe, and design the shot around the new brief.

- **Camera:** dolly, orbit, crane, path flythrough, push-in, rack focus, locked-off with subject motion, handheld. Pick the move that reveals the idea; give it a start and an end frame worth stopping on.
- **Light:** physical sky, HDRI, studio three-point, practicals, single hard key, silhouette, night with emissives, volumetric shafts (`kit.haze`). Light the subject, then the room. Start at sky strength `0.12` outdoors. For a window-lit interior, start near `0.08` with `kit.render(exposure=1)` and judge the probe highlights and shadows.
- **Material look:** photoreal scans (`kit.textured`), procedural (`kit.procedural`), stylized/toon (`kit.toon` + EEVEE), flat graphic (`kit.flat`), ink lines (`kit.render(freestyle=True)`, `kit.outline`).
- **Scale and detail:** real-world metres; secondary detail at three scales (silhouette, mid forms, surface). Bevel hard edges. Avoid floating objects and empty voids around the subject.
- **Abstract requests** (a system, an idea, a dataset): find a physical metaphor with moving parts that map to the real thing, and drive motion from `kit.data(...)` where data exists.

For a data animation with one visible label per step, compute each label's last visible frame before the next label's first frame. `kit.visible` includes both endpoints. Search for Population Bars Time to see this with a camera-mounted legend.

Use `kit.glow()` for compositor fog glow and `kit.tube(spline='POLY')` when a route must pass exactly through its control points. Scene-specific Blender features can use raw `bpy`. The marble, rigid-body, and walk examples show how to author mechanisms that need custom geometry, simulation settings, or planted steps.

## 3. Probe, iterate, draft

1. Validate the brief with `studio_brief`. Use the CLI `check` when you want feedback on the script before Blender starts.
2. `studio_probe(brief, script)`: runs the script, saves the scene, renders three timed stills. Poll `studio_status`; read `probe.checks.warnings` and `probe.estimate`. Open `probe.jpg` (and `references.jpg`) with `studio_view`. Fix composition, exposure and scale here; each probe is a new job and costs about a minute.
3. Call `studio_draft(job_id=...)` once the probe shows the intended subject, framing and exposure. The draft renders every frame at preview size. If the estimate exceeds `budget_minutes.draft` (default 10), simplify, lower `samples.preview`, or raise the budget.
4. A failed script returns its traceback in `error`; fix and start a new job. Never edit files inside a job.

## 4. Review honestly

Open `timeline.jpg` and `angles.jpg` with `studio_view`. Open `references.jpg` for visual inputs and `seam.jpg` for loops. Play `reel.mp4` or the loop's `two-cycles.mp4`. Record what you observed on each board and in the clip:

- Does each element of the prompt appear, recognisably? Does each subject reference read as itself, each style reference as the look?
- Framing at the target aspect; nothing important clipped; horizon and verticals intended.
- Exposure: no crushed blacks or blown whites unless intended; `qc.warnings` is empty or explained.
- Physical plausibility: contact with the ground, no interpenetration, believable scale.
- Motion: readable speed, eases where moves start and stop, no pops; loops do not jump.
- Variety: this does not look like the nearest example or your last scene.

A QC pass, a hash or a path is not a review. If you cannot see images or play video, ask the user to review and do not finalize. With Jev tools available, chain judgments per board (element visibility, defects, reference match) and treat answers between 0.3 and 0.7 as needing your own look.

## 5. Revise

State the defect and the fix, then make a new job with `brief.parent` set to the old job and the edited script. Keep the old job. `studio_compare` stacks matching boards (same orientation, duration, fps, loop): old on top.

## 6. Promote and deliver

When the user wants the master, call `studio_finalize` with the exact `preview.review_hashes` and notes describing what you saw on each board. It refuses with a time estimate if the master would exceed its budget (default 10 minutes): pass `budget_minutes`, fewer `samples`, or `quality: "fast"` (which lowers samples to fit). Poll `master.state`, confirm `master.qc.passed` and an empty or explained `warnings`, open the master boards, and deliver `reel.mp4`, the `.blend`, `scene.py`, `cover.png` and `CREDITS.txt`. Nothing is posted anywhere.
