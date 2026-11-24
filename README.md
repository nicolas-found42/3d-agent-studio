# 3D Agent Studio

Turn an art direction brief into an editable Blender scene and a silent vertical or horizontal video. Use the same workflow from a terminal or through a local [MCP](https://modelcontextprotocol.io/) client. No agent SDK, Blender add-on, server port, or model credentials are required to render.

- **Gravity Conveyor** — stacked ceramic pods open in sequence around luminous cores.
- **Orbit Bloom** — radial petals rotate and ripple around a fixed mount.

Both presets support a title, two colors, a seed, and a 2–8 second loop. Choose the orientation in the brief:

| `orientation` | Preview | Master |
|---|---|---|
| `vertical` (default, 9:16) | 360×640 | 1080×1920 |
| `horizontal` (16:9) | 640×360 | 1920×1080 |

Landscape uses its own camera and title layout, not a crop or rotated portrait. Exports are 30 fps, H.264/BT.709. Each stage includes a cover, a two-cycle clip, timeline and seam frames, front/side/reverse angles, and two orthogonal clip sections. This is procedural motion graphics, not arbitrary scene generation or social publishing.

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

> Make a six-second horizontal Orbit Bloom called LUNAR BLOOM, with ceramic white petals and emerald tips. Show me the draft, section proofs and the two-cycle loop before finalizing.

### Use from a terminal

```sh
uv run --locked 3d-agent-studio --output-root ./jobs draft \
  '{"template":"gravity-conveyor","orientation":"horizontal","title":"GRAVITY LAB","seconds":2}' --wait
uv run --locked 3d-agent-studio --output-root ./jobs status JOB_ID
```

Use the same absolute job root for CLI and MCP to inspect or continue a job across clients. The `--output-root` flag overrides `STUDIO_OUTPUT_ROOT`; the default is `~/3d-agent-studio-jobs`. `draft` and `finalize` queue local jobs; `--wait` polls until the stage succeeds or fails. See the [command and tool reference](skills/3d-agent-studio/references/operations.md) for inputs, outputs and retry behavior.

## Local boundaries

Use a dedicated, trusted, user-owned job directory, not a shared or untrusted mount. MCP runs as the local user. Briefs cannot specify files, scripts, commands or external assets. Blender runs headlessly with auto-execution disabled. The MCP server has no network listener or upload tool; the agent service you use may receive any images or text you surface to that agent. Copy the `.blend` outside the managed job before editing it. To promote, use the current draft evidence; edited or missing evidence requires a fresh draft.

## Verification

```sh
uv run --locked --extra mcp python -m unittest discover -s tests -v
uv lock --check
uv build
```

See the [agent verification matrix](docs/compatibility.md#verified-on-local-macos) and the [render verification](docs/render-verification.md). Media checks validate decoded frame order, constant cadence, format, and the two-cycle repeat; they do not establish playback smoothness on a phone or approval by a social platform.

[MIT license](LICENSE).
