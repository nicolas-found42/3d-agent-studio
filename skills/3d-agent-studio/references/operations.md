# Studio operations

Use one local job root across all calls. In the CLI examples `3d-agent-studio` is on PATH (in a checkout, prefix with `uv run --locked`). Put `--output-root /absolute/jobs` before the subcommand, or set `STUDIO_OUTPUT_ROOT`. MCP fixes its root at startup and never takes one from a tool call. JSON arguments in the CLI may be inline or `@file.json`.

## Commands and MCP tools

### `studio_doctor`

CLI `doctor`. Call without arguments for runtime versions, available sizes and frame rates, the brief schema, reference roles, asset sources, and the shipped example count.

### `studio_brief`

CLI `brief JSON`. Pass `brief` for a normalized brief without writing a job.

### `studio_ingest`

CLI `ingest PATH [--role R] [--max-frames N]`. Pass the absolute `path`, with optional `role` and `max_frames`. Returns a reference ID, kind, and local paths. Video references include the extracted frames.

### `studio_examples`

CLI `examples [QUERY] [--tag T] [--script]`. Filter by `query` and `tags`, set `limit` to at most 12, and set `include_script` to include source. Returns each match's prompt, tags, poster, and clip.

### `studio_probe`

CLI `probe JSON SCRIPT.py [--wait]`. Pass `brief` and `script` source to start a job. The probe resolves assets, runs the script, saves `scene.blend`, and renders three timed stills.

### `studio_draft`

CLI `draft --job ID [--wait]` or `draft JSON SCRIPT.py [--wait]`. Pass a probed `job_id` or provide `brief` and `script`. Returns the job for the full preview sequence and its review boards.

### `studio_status`

CLI `status ID`. Pass `job_id` to read stage state, paths, estimates, QC, and review hashes, along with the job's brief, parent, script, references, assets, and credits.

### `studio_view`

Pass `job_id`, `stage`, and `board` for one review image and its path. From the CLI, open the path listed by `status ID`.

### `studio_compare`

CLI `compare A B`. Pass job IDs as `before` and `after`. Matching boards stack vertically with `before` on top.

### `studio_finalize`

CLI `finalize ID REVIEW_JSON [--budget-minutes N] [--quality fast] [--samples N] [--wait]`. Pass `job_id`, the current draft board `hashes`, and written `notes`. Set `budget_minutes`, `quality`, or `samples` to override the brief. Returns the queued master job and its render plan.

### Check a script locally

CLI `check SCRIPT` runs the static script check without rendering.

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
| image | png jpg webp tif bmp gif (single frame) heic exr hdr | subject, style, composition, palette, storyboard | `kit.image`, `kit.image_plane`, `kit.image_material` |
| video | mp4 mov m4v webm mkv avi, animated gif | as image, plus motion | each frame is an image: `ref.paths[i]`, `ref.times[i]` |
| model | glb gltf (self-contained) obj fbx usd usda usdc usdz blend stl ply | asset | `kit.import_model(ref_id, size=…)`; `kit.play_animation(root)` loops an embedded rig animation |
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
| Khronos glTF samples | `khronos:<ModelName>` | CC0/CC-BY sample models only (e.g. `khronos:Fox`, a rigged walking fox, CC0 AND CC-BY-4.0) |
| Wikimedia Commons | `wikimedia:File:<name>` | Images |
| Openverse | `openverse:<uuid>` | Images |
| The Met | `met:<objectID>` | Public-domain object photos |
| NASA 3D Resources | `nasa:<path in the repo>` | Spacecraft, planets, textures |
| BlenderKit | `blenderkit:<asset uuid>` | Free CC0 materials and models (`.blend`) |
| Direct CC0 host | `url:https://…` on kenney.nl, sharetextures.com, cgbookcase.com, 3dtextures.me, quaternius.com, polyhaven.org, ambientcg.com | Files or zips from those hosts |

Downloads retry HTTP 429, 502, 503 and 504 with bounded backoff and honor `Retry-After` up to 30 seconds. The resolver prefers 3000 px thumbnails for large Wikimedia Commons originals. Kenney file requests can redirect to a landing page in a script. In that case, download the CC0 pack in the browser and ingest the extracted model. For mirrors on itch.io or OpenGameArt, check the specific pack's CC0 license first. Verify the original pack's license on its page, such as the [Kenney Space Kit](https://kenney.nl/assets/space-kit). Smithsonian 3D lacks a keyless license field, NIH 3D has no reachable API, and Sketchfab, Poly Pizza and Europeana require keys.

## Stages and evidence

- **probe**: `probe.jpg` (first, middle, last frame), `references.jpg` (with image references), `estimate.json` (fitted render cost and predicted draft and master minutes), `checks.json` (scene stats and `warnings`). The saved `scene.blend` comes from this stage.
- **preview** (draft) and **master**: `reel.mp4`, `timeline.jpg` (six decoded frames), `angles.jpg` (wide, three-quarter, overview with camera path), `references.jpg` when visual references exist, `seam.jpg` and `two-cycles.mp4` for loops, `cover.png`, and `qc.json`. QC records video checks, frame statistics, reference pairs, warnings, and predicted and actual minutes. Master adds `master.mov` with `extras: ["prores"]` and retains numbered plates with `extras: ["png"]`.

The probe measures short sequences at preview and master resolution to forecast render time. Draft and master plans reserve 10% of the budget for estimation uncertainty. The active deadline covers rendering and packaging after the job acquires the GPU lock.
- Review hashes are the preview's board JPEGs; finalize must quote them exactly with 12–4000 characters of notes.
- Stage budgets cover work after the GPU lock is acquired, including encoding and review evidence. Time waiting for the lock is excluded. Read `error` and `run.log` if a stage fails or has no result after its deadline. Start a new job to retry a failed stage.
- Edited scripts, scenes or evidence, or changed studio code, invalidate a job: make a new one.

## Script contract

`build(kit)` must create a camera (`kit.camera`) and renderable geometry. Use keyframes for scripted motion. Imports are limited to `bpy`, `bmesh`, `mathutils`, `math`, `random`, `colorsys`, `itertools`, `functools`, `statistics` and `numpy`. Use the kit for file inputs and the studio for rendering and saving. The static check catches mistakes. Scripts still execute with the permissions of the local user.
