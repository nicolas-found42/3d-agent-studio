# Plan: prompt-driven scenes (v0.3.0)

Agreed in the November 24, 2026 design interview. Implementation and visual verification are complete on `prompt-scenes`. Publishing v0.3.0 requires the owner's go-ahead. See [status and handoff](#status-and-handoff).

## Goal

Replace the two fixed presets with scenes made from whatever the user supplies: a prompt, with or without reference images, videos, models, data, logos, fonts, sketches or shot lists. Quality benchmark: the procedural Laon cathedral interior and dolly in `resurrection-site/scripts/cathedral`.

## Decisions

| # | Decision |
|---|---|
| Authoring | The calling agent writes a Blender Python **scene script** (`def build(kit): ...`). The studio checks, runs, renders, QCs and gates it. No model calls or agent SDK inside the studio. |
| Presets | `gravity-conveyor` and `orbit-bloom` are deleted as products. A large **example library** (about 36 scripts in 12 categories, varied camera, lighting, material style and motion) is searchable via `studio_examples`; agents study at least three examples from different categories and copy none. |
| Script safety | Chosen option (b), no OS sandbox. Static pre-run check: imports limited to `bpy`, `bmesh`, `mathutils`, `math`, `random`, `colorsys`, `itertools`, `functools`, `statistics`, `numpy`; no `open`, `exec`, `eval`, `__import__`, dunder access, handlers, text blocks, `bpy.ops.wm`/`bpy.ops.render`. Catches mistakes; not a sandbox. |
| Inputs | `studio_ingest(path, role)` is the only way files enter. Images (roles subject/style/composition/palette/storyboard), video (scene-detected frames, cap 20, overridable), 3D models (GLB/glTF, OBJ, FBX, USD, .blend), data (CSV/JSON), SVG logos, fonts, text shot lists. Repos are summarized into the prompt by the agent. 40 image references per job, overridable. Audio deferred; output is silent. |
| Revisions | A revision is a new job with `parent`; the script, references and assets are the source of truth, not the `.blend`. |
| Assets | Studio-resolved before Blender, by ID, cached and hash-pinned, SPDX license recorded, `CREDITS.txt` per job. Keyless sources only: Poly Haven, ambientCG, Fontsource, Khronos glTF samples, Wikimedia Commons, Openverse, NASA 3D Resources, Met Open Access, BlenderKit (CC0), plus direct files from the CC0 hosts Kenney, ShareTextures, cgbookcase, 3D Textures and Quaternius. Smithsonian 3D (no license field without a key) and NIH 3D (no reachable API) were evaluated and dropped. Allowed: CC0, public domain, CC-BY (attributed). NC, ND, SA and missing licenses are rejected. Sources that turn out to need a key are dropped and documented. |
| Brief | `prompt` (required), `references`, `assets`, `orientation` (vertical 9:16, horizontal 16:9, square 1:1, portrait 4:5, ultrawide 21:9), `seconds` 2–30, `loop`, `fps` 24/30/60/120, `seed`, optional `title` drawn only with `show_title`, `quality` (`standard`/`fast`), `budget_minutes`, `extras` (`prores`, `png`), `parent`, `max_references`. |
| Stages | **probe** (build, three review stills and short timing samples at preview and master resolution, 5 min), **draft** (full sequence at preview size, Cycles 16 spp denoised, 10 min), **master** (full size, 128 spp, 10 min). Each cap can be overridden. Plans reserve 10% of the budget for uncertainty. `quality: fast` lowers master samples to fit, with a default floor of 16. `standard` refuses with an estimate when the requested samples exceed the budget. The active deadline includes packaging. One GPU lock per job root serializes renders. |
| Render defaults | Cycles on Metal GPU, denoised, AgX, motion blur, 35 mm-equivalent lens, fixed seed. Blender 5.2 or newer. Master MP4 H.264, plus `.blend`, script, poster, `CREDITS.txt`; ProRes 4444 and PNG frames on request. |
| Review | Boards: `timeline.jpg`, `angles.jpg` (wide, three-quarter, top-down overview with camera path), `references.jpg` (each reference beside its closest render frame; only with image references), `seam.jpg` (loops only). Finalize stays hash-bound to the current boards with written notes. Every board fits 280–1568 px per side so vision judges such as Jev accept it unchanged. |
| Judging | Dev-only `tools/review/` runs chained Jev judgments (OpenRouter `typesafe/jev-1.14`): per-element visibility Nouls, defect Nouls, reference Scores, diversity checks. Code decides: required elements > 0.7, defects < 0.3, references at least "clearly related"; the 0.3–0.7 band goes to manual review. End-user agents use Jev MCP tools when they have them. |
| Kit | `agent_studio.kit`, generalized from the cathedral helpers: geometry, materials (procedural, scanned, glass, toon/outline), lights, sky/HDRI, haze, camera rigs (dolly, orbit, crane, path, handheld), easing and loop-safe motion, keyframe sampling, scatter, text, imports, reference planes, data, figures. Raw `bpy` stays allowed. |

## Build order (branch `prompt-scenes`)

1. Contract, ingest, script check, assets, kit; unit tests.
2. Probe stage, budgets, GPU lock, generic boards, extras.
3. Example library (multi-agent workflow), `studio_examples`, Jev review tool.
4. Acceptance suite (society sim, gothic interior vs. the cathedral, product from one photo, character loop, landscape from photos, data visualization), docs, v0.3.0 and marketplace pin.

## Acceptance

- Unit tests: `uv run --locked --extra mcp python -m unittest discover -s tests -v`.
- Every example and acceptance scenario has a ready draft with visual board notes and Jev results. Example evidence lives under `src/agent_studio/examples/<slug>/review.json`. Acceptance evidence lives under `acceptance/<slug>/result/review.json`.

## Status and handoff

- The CLI and stdio MCP use the brief, scene script, declared inputs and open assets to build and render a local job. The normal tests cover GIF frame selection, asset resolver behavior, review policy and the example index.
- All 36 examples are indexed with scripts, posters, clips and visual notes. The independent critique includes the contact sheet, cover revisions, and Jev results for all 78 tag-neighbor pairs. [Example library review](../example-library-review.md)
- All six scenarios have packaged draft evidence. Fox Asleep also has a 1080p master. The Iceland scene retains its basic Jev grade with written exceptions for the stylized finish and reference fidelity. [Acceptance scenes](../../acceptance/README.md) · [Render verification](../render-verification.md)
- The opt-in Blender suite covers promotion, revisions and comparisons, exact board bytes through MCP, ProRes 4444, PNG plates and a one-minute timeout. The measured draft and master predictions are recorded separately from GPU queue time. [Render verification](../render-verification.md)

**GitHub acceptance checklist**

| Issue | Work |
|---|---|
| [#1](https://github.com/nicolas-found42/3d-agent-studio/issues/1) | Finish the 36-example library: full spec, per-slug state and procedure |
| [#10](https://github.com/nicolas-found42/3d-agent-studio/issues/10) | Art-direction and diversity review of the library (after #1) |
| [#2](https://github.com/nicolas-found42/3d-agent-studio/issues/2) | Finish the 6 acceptance scenarios |
| [#6](https://github.com/nicolas-found42/3d-agent-studio/issues/6) | Exercise master/finalize, compare, extras and budgets end to end |
| [#3](https://github.com/nicolas-found42/3d-agent-studio/issues/3) | Animated GIF ingest and society diagram coverage |
| [#4](https://github.com/nicolas-found42/3d-agent-studio/issues/4) | Bounded retry, Kenney landing-page handling and resolver fixtures |
| [#5](https://github.com/nicolas-found42/3d-agent-studio/issues/5) | Diagram judgments, duplicate pairs, draft noise and decision tests |
| [#7](https://github.com/nicolas-found42/3d-agent-studio/issues/7) | Kit gaps |
| [#8](https://github.com/nicolas-found42/3d-agent-studio/issues/8) | Docs for v0.3.0 |
| [#9](https://github.com/nicolas-found42/3d-agent-studio/issues/9) | Release v0.3.0 (last) |

The release is prepared as one pull request. Publish the tag with the owner's go-ahead and check installation from that tag. [Migration notes](../v0.3.0.md) · [Marketplace installs](../marketplace.md)

**Environment notes**
- Reference machine: Apple M5 Pro (20-core GPU, 48 GB), Blender 5.2.2 at `/Applications/Blender.app`, FFmpeg with libx264. A 640×360 draft frame at 16 spp takes about 0.6–2 s; the first GPU render after a Blender update compiles kernels (~2 min).
- Use a scratch job root outside the repo for renders (`--output-root /absolute/path`); never commit job folders.
- `tools/review/review.py` needs `OPENROUTER_API_KEY`; a review costs about $0.0005.
- Changing any file in `pipeline.CODE_FILES` invalidates existing jobs (they must be re-created), by design.
