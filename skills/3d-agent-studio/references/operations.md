# Studio operations

Use one local job root across all calls. In the CLI examples `3d-agent-studio` is on PATH (in a checkout, prefix with `uv run --locked`). Put `--output-root /absolute/jobs` before the subcommand, or set `STUDIO_OUTPUT_ROOT`. MCP fixes its root at startup and never takes one from a tool call. JSON arguments in the CLI may be inline or `@file.json`.

| MCP tool | Arguments | CLI | Result |
|---|---|---|---|
| `studio_doctor` | — | `doctor` | Runtime versions (Blender 5.2+), orientations and sizes, fps, brief schema and defaults, reference kinds and roles, asset sources, example count |
| `studio_brief` | `brief` | `brief JSON` | Normalized brief; no writes |
| `studio_ingest` | `path` (absolute), `role`, `max_frames` | `ingest PATH [--role R] [--max-frames N]` | Reference ID (`ref-…`), kind, role, paths; videos list their extracted frames |
| `studio_examples` | `query`, `tags`, `limit` ≤ 12, `include_script` | `examples [QUERY] [--tag T] [--script]` | Matching examples with prompt, tags, poster, clip and script |
| — | — | `check SCRIPT` | Static script check only |
| `studio_probe` | `brief`, `script` (source text) | `probe JSON SCRIPT.py [--wait]` | New job; resolves assets, runs the script, saves `scene.blend`, renders 3 timed stills |
| `studio_draft` | `job_id` of a probed job, or `brief` + `script` | `draft --job ID` or `draft JSON SCRIPT.py` `[--wait]` | Full preview sequence and review boards |
| `studio_status` | `job_id` | `status ID` | Brief, script path, references, assets, credits, `.blend`, and per-stage state, artifacts, estimates, QC, review hashes |
| `studio_view` | `job_id`, `stage`, `board` | open the path from `status` | One board as an image plus its path |
| `studio_compare` | `before`, `after` | `compare A B` | Matching boards stacked, before on top |
| `studio_finalize` | `job_id`, `hashes`, `notes`, optional `budget_minutes`, `quality`, `samples` | `finalize ID REVIEW_JSON [--budget-minutes N] [--quality fast] [--samples N] [--wait]` | Queued master and its render plan |

## Brief

Only `prompt` is required.

| Field | Values | Default |
|---|---|---|
| `prompt` | 1–8000 characters: subject, setting, mood, motion, camera | required |
| `references` | ingest IDs, or `{id, role, note}` to override the role or explain intent | `[]` |
| `assets` | open asset IDs (below) | `[]` |
| `orientation` | `vertical` 9:16 (360×640 / 1080×1920), `horizontal` 16:9 (640×360 / 1920×1080), `square` (360×360 / 1080×1080), `portrait` 4:5 (360×450 / 1080×1350), `ultrawide` 21:9 (840×360 / 2520×1080) | `vertical` |
| `seconds` | 2–30 | 6 |
| `fps` | 24, 30, 60, 120 | 24 |
| `loop` | seamless loop: frame `frames + 1` must equal frame 1 | `false` |
| `seed` | 0–999999 (`kit.rng`, Cycles seed) | 11 |
| `title`, `show_title` | ≤ 48 printable ASCII; drawn in-camera only when `show_title` | `''`, `false` |
| `quality` | `standard` refuses an over-budget master; `fast` lowers master samples (floor 16) to fit | `standard` |
| `budget_minutes` | `{probe, draft, master}`, each 1–1440 | 5, 10, 10 |
| `samples` | `{preview, master}` Cycles samples | 16, 128 |
| `extras` | `prores` (ProRes 4444 `master.mov`), `png` (keep master frames) | `[]` |
| `parent` | job ID this revises | `null` |
| `max_references` | image references per job (video frames count) | 40 |

## References

`studio_ingest` copies a file into `<root>/inputs/ref-…` once (content-addressed) and the brief attaches it to a job.

| Kind | Extensions | Roles (first is default) | In the script |
|---|---|---|---|
| image | png jpg webp tif bmp gif heic exr hdr | subject, style, composition, palette, storyboard | `kit.image`, `kit.image_plane`, `kit.image_material` |
| video | mp4 mov m4v webm mkv avi | as image, plus motion | each frame is an image: `ref.paths[i]`, `ref.times[i]` |
| model | glb gltf (self-contained) obj fbx usd usda usdc usdz blend stl ply | asset | `kit.import_model(ref_id, size=…)` |
| data | csv tsv json | data | `kit.data(ref_id)` |
| vector | svg | logo, asset | `kit.svg(ref_id)` |
| font | ttf otf | font | `kit.text(..., font=ref_id)` |
| text | txt md | shotlist, notes | `kit.read_text(ref_id)` |

## Assets

Asset IDs are resolved before Blender runs, cached under `<root>/assets-cache`, hash-pinned, and credited in the job's `CREDITS.txt`. Allowed licenses: CC0, public domain, CC-BY (attributed), OFL/Apache/MIT for fonts. NC, ND, SA, custom or missing licenses are refused.

| Source | ID form | Contents |
|---|---|---|
| Poly Haven | `polyhaven:<slug>[@1k\|2k\|4k]` | HDRIs, PBR textures, models |
| ambientCG | `ambientcg:<AssetId>[@1K\|2K\|4K]` | PBR materials, HDRIs |
| Fontsource | `fontsource:<id>[@weight][:italic]` | Fonts |
| Khronos glTF samples | `khronos:<ModelName>` | CC0/CC-BY sample models only |
| Wikimedia Commons | `wikimedia:File:<name>` | Images |
| Openverse | `openverse:<uuid>` | Images |
| The Met | `met:<objectID>` | Public-domain object photos |
| NASA 3D Resources | `nasa:<path in the repo>` | Spacecraft, planets, textures |
| BlenderKit | `blenderkit:<asset uuid>` | Free CC0 materials and models (`.blend`) |
| Direct CC0 host | `url:https://…` on kenney.nl, sharetextures.com, cgbookcase.com, 3dtextures.me, quaternius.com, polyhaven.org, ambientcg.com | Files or zips from those hosts |

Smithsonian 3D and NIH 3D were evaluated and left out: the former exposes no license field without a key, the latter no reachable API. Sketchfab, Poly Pizza and Europeana require keys.

## Stages and evidence

- **probe**: `probe.jpg` (first, middle, last frame), `references.jpg` (with image references), `estimate.json` (fitted render cost and predicted draft and master minutes), `checks.json` (scene stats and `warnings`). The saved `scene.blend` comes from this stage.
- **preview** (draft) and **master**: `reel.mp4`, `timeline.jpg` (six decoded frames), `angles.jpg` (wide, three-quarter, overview with camera path), `references.jpg`, `seam.jpg` and `two-cycles.mp4` for loops, `cover.png`, `qc.json` (video checks, frame statistics, reference pairs, `warnings`). Master adds `master.mov` with `extras: ["prores"]`.
- Review hashes are the preview's board JPEGs; finalize must quote them exactly with 12–4000 characters of notes.
- States: `queued`, `running` (with `step`; `waiting for the GPU lock` means another render in this root is using the GPU), `ready`, `failed` (read `error` and `run.log`), `stalled` (no update for 30 minutes). Stages never resume or overwrite; start a new job.
- Edited scripts, scenes or evidence, or changed studio code, invalidate a job: make a new one.

## Script contract

`build(kit)` must create a camera (`kit.camera`) and renderable geometry, and animate with keyframes. Imports are limited to `bpy`, `bmesh`, `mathutils`, `math`, `random`, `colorsys`, `itertools`, `functools`, `statistics`, `numpy`, `dataclasses`, `typing`, `enum`, `collections`, `string`, `textwrap`. File I/O, `exec`/`eval`, dunder access, handlers, text blocks, saving and rendering are the studio's. This check catches mistakes; it is not a sandbox, so scripts still run as the local user.
