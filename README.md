# 3D Agent Studio

Turn any prompt, with or without reference photos, videos, 3D models, data, logos, fonts or shot lists, into an editable Blender scene and a silent animated video. Use the same workflow from a terminal or through a local [MCP](https://modelcontextprotocol.io/) client. No agent SDK, Blender add-on, server port, or model credentials are required to render.

There are no presets. Your agent writes a Blender Python scene script (`def build(kit): ...`) using the studio's scene kit: geometry, procedural and scanned materials, physical sky and HDRI lighting, haze, camera rigs, easing and loop-safe motion, imported models, figures, particles and rigid bodies. The studio checks the script, resolves open-licensed assets, runs it in Blender, renders on the GPU, and gates the master on a visual review. A searchable [example library](src/agent_studio/examples/) spans architecture, nature, products, characters, data and systems, mechanics, physics, typography, still life, micro and macro scale, and space.

| `orientation` | Aspect | Preview | Master |
|---|---|---|---|
| `vertical` (default) | 9:16 | 360×640 | 1080×1920 |
| `horizontal` | 16:9 | 640×360 | 1920×1080 |
| `square` | 1:1 | 360×360 | 1080×1080 |
| `portrait` | 4:5 | 360×450 | 1080×1350 |
| `ultrawide` | 21:9 | 840×360 | 2520×1080 |

Shots run 2–30 seconds at 24, 30, 60 or 120 fps, linear or as seamless loops, rendered with Cycles (AgX, denoised, motion blur). Each job has three stages, each with a wall-clock budget you can raise: a **probe** (three timed stills, 5 min), a **draft** (every frame at preview size, 10 min) and a **master** (full size, 10 min). The probe predicts the later stages, so an over-budget stage refuses with an estimate instead of running for hours. Review boards show a six-frame timeline, alternate angles with the camera path, each reference beside its closest frame, and the loop seam. Exports are H.264/BT.709 MP4, plus the `.blend`, the script, a cover, `CREDITS.txt`, and optionally ProRes 4444 or PNG frames.

## Marketplace install

Add the **[Found42 Studio marketplace](docs/marketplace.md)** for Claude Code, Codex, or Oh My Pi, or install the portable GitHub package in Hermes Agent. The guide also covers Cursor team imports, direct MCP setup for personal Cursor and OpenCode, and live development from one checkout.

Claude Code also supports a single command in an agent session:

```text
/plugin install 3d-agent-studio --marketplace nicolas-found42/3d-agent-studio
```

## Quick start

Install Python 3.11+, [uv](https://docs.astral.sh/uv/), Blender (tested with 5.2), and FFmpeg with `libx264` and `ffprobe`.

```sh
git clone https://github.com/nicolas-found42/3d-agent-studio.git
cd 3d-agent-studio
uv sync --locked --extra mcp
uv run --locked --extra mcp 3d-agent-studio doctor
```

Without MCP, omit `--extra mcp`. For pip, install `.` or `.[mcp]` into a Python virtual environment. If your host cannot see the renderer binaries on its `PATH`, set the absolute executable paths in `STUDIO_BLENDER`, `STUDIO_FFMPEG` and `STUDIO_FFPROBE` in that host's server environment.

### Use from an agent

Start with [agent setup](docs/agents.md) or the [compatibility and verification matrix](docs/compatibility.md) for **Oh My Pi, Codex, Hermes Agent, Claude Code, Cursor**, and generic local stdio clients. Give the agent the bundled [3D Agent Studio skill](skills/3d-agent-studio/SKILL.md), which explains all tools and the review gate. For agents without MCP, point them to the same skill and give them terminal access on the render machine.

> Make an eight-second horizontal video of a fog-filled gothic nave at dawn, slow dolly toward the crossing. Use these two photos for the stonework. Show me the probe and draft boards before finalizing.

### Use from a terminal

```sh
uv run --locked 3d-agent-studio --output-root ./jobs examples nave --script
uv run --locked 3d-agent-studio --output-root ./jobs ingest /absolute/path/photo.jpg --role style
uv run --locked 3d-agent-studio --output-root ./jobs draft \
  '{"prompt":"A red cube turning on a grey floor","orientation":"square","seconds":4,"loop":true}' scene.py --wait
uv run --locked 3d-agent-studio --output-root ./jobs status JOB_ID
```

Use the same absolute job root for CLI and MCP to inspect or continue a job across clients. The `--output-root` flag overrides `STUDIO_OUTPUT_ROOT`; the default is `~/3d-agent-studio-jobs`. `draft` and `finalize` queue local jobs; `--wait` polls until the stage succeeds or fails. See the [command and tool reference](skills/3d-agent-studio/references/operations.md) for inputs, outputs and retry behavior.

## Local boundaries

Use a dedicated, trusted, user-owned job directory, not a shared or untrusted mount. MCP runs as the local user. Scene scripts are agent-written Python executed in Blender as that user: a static check rejects file I/O, process and network imports, `exec`/`eval`, handlers and saving, which catches mistakes but is not a sandbox. Local files enter only through `ingest`. Assets are fetched over HTTPS only from the keyless open sources listed in the [operations reference](skills/3d-agent-studio/references/operations.md#assets), license-checked and credited. Blender runs headlessly with auto-execution of embedded scripts disabled. The MCP server has no network listener or upload tool; the agent service you use may receive any images or text you surface to that agent. Copy the `.blend` outside the managed job before editing it. To promote, use the current draft evidence; edited or missing evidence requires a fresh draft.

## Verification

```sh
uv run --locked --extra mcp python -m unittest discover -s tests -v
STUDIO_RENDER_TESTS=1 uv run --locked --extra mcp python -m unittest tests.test_workflow.Render -v
uv run --locked python tools/kit_reference.py   # after changing the kit
uv lock --check
uv build
```

See the [agent verification matrix](docs/compatibility.md#verified-on-local-macos) and the [render verification](docs/render-verification.md). Media checks validate decoded frame order, constant cadence, format, and the two-cycle repeat; they do not establish playback smoothness on a phone or approval by a social platform.

[MIT license](LICENSE).
