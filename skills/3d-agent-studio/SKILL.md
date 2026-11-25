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

Call `studio_examples` with words from the request and read at least three scripts from **different** categories (`include_script: true`). Borrow techniques (a camera rig, a material recipe, a lighting rig), never a composition. Then decide deliberately, and vary from what you made last time:

- **Camera:** dolly, orbit, crane, path flythrough, push-in, rack focus, locked-off with subject motion, handheld. Pick the move that reveals the idea; give it a start and an end frame worth stopping on.
- **Light:** physical sky, HDRI, studio three-point, practicals, single hard key, silhouette, night with emissives, volumetric shafts (`kit.haze`). Light the subject, then the room.
- **Material look:** photoreal scans (`kit.textured`), procedural (`kit.procedural`), stylized/toon (`kit.toon` + EEVEE), flat graphic (`kit.flat`), ink lines (`kit.render(freestyle=True)`, `kit.outline`).
- **Scale and detail:** real-world metres; secondary detail at three scales (silhouette, mid forms, surface). Bevel hard edges. Avoid floating objects and empty voids around the subject.
- **Abstract requests** (a system, an idea, a dataset): find a physical metaphor with moving parts that map to the real thing, and drive motion from `kit.data(...)` where data exists.

## 3. Probe, iterate, draft

1. `studio_brief` to validate. Optionally `check` the script in the CLI.
2. `studio_probe(brief, script)`: runs the script, saves the scene, renders three timed stills. Poll `studio_status`; read `probe.checks.warnings` and `probe.estimate`. Open `probe.jpg` (and `references.jpg`) with `studio_view`. Fix composition, exposure and scale here; each probe is a new job and costs about a minute.
3. `studio_draft(job_id=...)` on a good probe (or `studio_draft(brief, script)` to do both). The draft renders every frame at preview size. If it is predicted to exceed `budget_minutes.draft` (default 10), it refuses with the estimate: simplify, lower `samples.preview`, or raise the budget.
4. A failed script returns its traceback in `error`; fix and start a new job. Never edit files inside a job.

## 4. Review honestly

Open every board with `studio_view`: `timeline.jpg` (six frames), `angles.jpg` (wider lens from the shot camera, three-quarter set view, top-down overview with the camera path in pink), `references.jpg` (each reference beside the most similar frame) and `seam.jpg` for loops. Play `reel.mp4` (or `two-cycles.mp4`). Check, and write down:

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
