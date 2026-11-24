# Studio operations

Use one local job root across all calls. In the CLI examples, `3d-agent-studio` is on PATH (for a checkout, prefix with `uv run --locked`). Place `--output-root /absolute/jobs` before the subcommand, or set `STUDIO_OUTPUT_ROOT` in the terminal. MCP selects its root at startup and never accepts it from a tool call.

| MCP tool | Arguments | CLI equivalent | Result |
|---|---|---|---|
| `studio_doctor` | none | `doctor` | Runtime paths/versions, libx264, root, dimensions per orientation and brief schema/defaults |
| `studio_brief` | `brief`: object | `brief 'JSON'` | Normalized brief; no Blender process or writes |
| `studio_draft` | `brief`: object | `draft 'JSON' [--wait]` | Queued job ID and preview directory; outputs a new `.blend` and native preview media |
| `studio_status` | `job_id`: returned ID | `status JOB_ID` | Brief, preview and master states, ready artifacts and QC; `editable_blend` once preview is ready |
| `studio_view` | `job_id`, `stage`: `preview` or `master`, `board`: one of the four JPEG names below | `status JOB_ID`, then open the corresponding file | One validated JPEG as MCP image content plus local path |
| `studio_compare` | `before`, `after`: distinct ready preview IDs | `compare BEFORE AFTER` | Four matched stacked JPEGs (before above after) and a comparison manifest; same template, orientation and duration required |
| `studio_finalize` | `job_id`, `hashes`: object, `notes`: string | `finalize JOB_ID 'REVIEW_JSON' [--wait]` | Queued full-HD master, using the same saved scene and orientation |

## Brief

All fields are optional. `orientation` accepts `vertical` (360×640 preview, 1080×1920 master, default) or `horizontal` (640×360 preview, 1920×1080 master). `title` is 1–24 printable ASCII characters, not only spaces. `template` is `gravity-conveyor` or `orbit-bloom`; `seconds` is an integer 2–8; `primary`/`accent` are `#RRGGBB`; `seed` is an integer 0–999999. Use `doctor` for defaults. Other keys, paths, scripts and asset files are unsupported.

```json
{"title":"ORBIT BLOOM","template":"orbit-bloom","orientation":"horizontal","seconds":2,"primary":"#BBC6F2","accent":"#FF9A62","seed":11}
```

## Job states and review evidence

- Queued/running: poll every few seconds; `step`, `rendered_frames` and `log` indicate progress. `master: null` means it has not started.
- Ready: `artifacts` gives absolute file paths. `qc.json` names the frames and ordering. `timeline.jpg` is six decoded checkpoints, left-to-right then top-to-bottom. `angles.jpg` is front, side, reverse; `sections.jpg` is x=0 then y=0. Both use the same inspection frame. Sections use a camera clip plane and proof-only shading; a flat cut appearance does not imply a watertight cap or a geometry edit. `seam.jpg` is the last two and first two encoded frames, left-to-right then top-to-bottom (one row for vertical, two for horizontal). `reel.mp4` has one cycle, `two-cycles.mp4` has two verified identical decoded sequences, and `cover.png` is a selected decoded frame. Files are silent.
- Failed/stalled: read `error` and the stage `run.log`. Stalled means there has been no stage update for 30 minutes. The studio does not overwrite, rerun or resume stages. Correct the underlying issue and start a new job; keep earlier valid previews for comparison.

## Finalize

Use only after reviewing the actual current images and loop, and when a master is wanted. Copy the exact `preview.review_hashes` object from `status`; include observations in `notes` (12–1800 characters after trimming). The CLI's JSON argument is `{"hashes":{...},"notes":"your concrete review"}`. For MCP, pass `hashes` and `notes` as separate fields alongside `job_id`. The hash object must contain exactly `timeline.jpg`, `angles.jpg`, `sections.jpg` and `seam.jpg`.

File hashes bind your notes to the current evidence; the studio cannot tell whether a human or agent actually looked at it. An edited scene, changed evidence, changed render code or incompatible runtime change requires another draft. A valid earlier draft can still be opened or compared. Open the fresh master boards and play the actual encoded file before handing it off.
