# Plan: prompt-driven scenes (v0.3.0)

Status: agreed 2026-11-24 in a design interview; this file records the decisions and the build order.

## Goal

Replace the two fixed presets with scenes made from whatever the user supplies: a prompt, with or without reference images, videos, models, data, logos, fonts, sketches or shot lists. Quality benchmark: the procedural Laon cathedral interior and dolly in `resurrection-site/scripts/cathedral`.

## Decisions

| # | Decision |
|---|---|
| Authoring | The calling agent writes a Blender Python **scene script** (`def build(kit): ...`). The studio checks, runs, renders, QCs and gates it. No model calls or agent SDK inside the studio. |
| Presets | `gravity-conveyor` and `orbit-bloom` are deleted as products. A large **example library** (about 36 scripts in 12 categories, varied camera, lighting, material style and motion) is searchable via `studio_examples`; agents study at least three examples from different categories and copy none. |
| Script safety | Static pre-run check: imports limited to `bpy`, `bmesh`, `mathutils`, `math`, `random`, `colorsys`, `itertools`, `functools`, `statistics`, `numpy`; no `open`, `exec`, `eval`, `__import__`, dunder access, handlers, text blocks, `bpy.ops.wm`/`bpy.ops.render`. Catches mistakes; not a sandbox. |
| Inputs | `studio_ingest(path, role)` is the only way files enter. Images (roles subject/style/composition/palette/storyboard), video (scene-detected frames, cap 20, overridable), 3D models (GLB/glTF, OBJ, FBX, USD, .blend), data (CSV/JSON), SVG logos, fonts, text shot lists. Repos are summarized into the prompt by the agent. 40 image references per job, overridable. Audio deferred; output is silent. |
| Revisions | A revision is a new job with `parent`; the script, references and assets are the source of truth, not the `.blend`. |
| Assets | Studio-resolved before Blender, by ID, cached and hash-pinned, SPDX license recorded, `CREDITS.txt` per job. Keyless sources only: Poly Haven, ambientCG, Fontsource, Khronos glTF samples, Wikimedia Commons, Openverse, NASA 3D Resources, Smithsonian 3D, NIH 3D, Met Open Access, BlenderKit (CC0), plus direct files from the CC0 hosts Kenney, ShareTextures, cgbookcase and 3D Textures. Allowed: CC0, public domain, CC-BY (attributed). NC, ND, SA and missing licenses are rejected. Sources that turn out to need a key are dropped and documented. |
| Brief | `prompt` (required), `references`, `assets`, `orientation` (vertical 9:16, horizontal 16:9, square 1:1, portrait 4:5, ultrawide 21:9), `seconds` 2–30, `loop`, `fps` 24/30/60/120, `seed`, optional `title` drawn only with `show_title`, `quality` (`standard`/`fast`), `budget_minutes`, `extras` (`prores`, `png`), `parent`, `max_references`. |
| Stages | **probe** (build + 3 timed stills, 5 min), **draft** (full sequence at preview size, Cycles 16 spp denoised, 10 min), **master** (full size, 128 spp, 10 min). Caps are overridable per brief. The probe's timing predicts the later stages; a stage predicted over budget refuses to start with the estimate. `quality: fast` instead lowers master samples (floor 16) to fit; `standard` never drops below 64 spp. One GPU lock per job root serializes renders. |
| Render defaults | Cycles on Metal GPU, denoised, AgX, motion blur, 35 mm-equivalent lens, fixed seed. Blender 5.2 or newer. Master MP4 H.264, plus `.blend`, script, poster, `CREDITS.txt`; ProRes 4444 and PNG frames on request. |
| Review | Boards: `timeline.jpg`, `angles.jpg` (wide, overview with camera path, three-quarter), `references.jpg` (each reference beside its closest render frame; only with image references), `seam.jpg` (loops only). Finalize stays hash-bound to the current boards with written notes. |
| Judging | Dev-only `tools/review/` runs chained Jev judgments (OpenRouter `typesafe/jev-1.14`): per-element visibility Nouls, defect Nouls, reference Scores, diversity checks. Code decides: required elements > 0.7, defects < 0.3, references at least "clearly related"; the 0.3–0.7 band goes to manual review. End-user agents use Jev MCP tools when they have them. |
| Kit | `agent_studio.kit`, generalized from the cathedral helpers: geometry, materials (procedural, scanned, glass, toon/outline), lights, sky/HDRI, haze, camera rigs (dolly, orbit, crane, path, handheld), easing and loop-safe motion, keyframe sampling, scatter, text, imports, reference planes, data, figures. Raw `bpy` stays allowed. |

## Build order (branch `prompt-scenes`)

1. Contract, ingest, script check, assets, kit; unit tests.
2. Probe stage, budgets, GPU lock, generic boards, extras.
3. Example library (multi-agent workflow), `studio_examples`, Jev review tool.
4. Acceptance suite (society sim, gothic interior vs. the cathedral, product from one photo, character loop, landscape from photos, data visualization), docs, v0.3.0 and marketplace pin.

## Acceptance

- Unit tests: `uv run --locked --extra mcp python -m unittest discover -s tests -v`.
- Each acceptance scenario and example has a ready draft whose boards were looked at and passed the Jev chain, with notes in `examples/<slug>/review.json` or `acceptance/<slug>/review.json`.
