# Connect an agent

Connect an editable checkout to a host that can run local commands. For the tagged plugin, use the [release install guide](marketplace.md). Complete [Check the renderer](quickstart.md#check-the-renderer) before registering a local server. The host handles its model connection, and Studio runs Blender on the render machine.

## Choose paths once

Run these commands from the checkout on your render machine.

```sh
uv sync --locked --extra mcp
STUDIO_MCP="$PWD/.venv/bin/3d-agent-studio-mcp"
STUDIO_JOBS="$HOME/3d-agent-studio-jobs"
```

The render worker uses POSIX file locking. Use absolute paths in host settings, even if the host supports variables. The job root is configured when the local server starts. Use separate roots for projects whose artifacts should stay isolated.

## Oh My Pi (OMP) and Cursor

Merge this entry into the project's `.omp/mcp.json` (OMP) or `.cursor/mcp.json` (Cursor). For user-level configuration, use [`~/.omp/agent/mcp.json` or the active profile's config](https://github.com/can1357/oh-my-pi/blob/main/docs/mcp-config.md), or [`~/.cursor/mcp.json`](https://cursor.com/docs/context/mcp). Preserve existing entries. Replace both example paths with your absolute paths:

```json
{
  "mcpServers": {
    "3d-agent-studio": {
      "command": "/absolute/checkout/.venv/bin/3d-agent-studio-mcp",
      "args": ["--output-root", "/absolute/jobs"]
    }
  }
}
```

- **OMP:** Open a fresh session in the project; use `/mcp list` and `/mcp test 3d-agent-studio` to check discovery and connection. If project MCP config is disabled, use the active profile's user file instead. OMP can also discover Cursor and other hosts' configurations, so keep only one effective entry per project.
- **Cursor:** In **Customize → MCP**, enable the server and inspect the tools. In Cursor CLI, `cursor-agent mcp enable 3d-agent-studio` approves that entry, and `cursor-agent mcp list-tools 3d-agent-studio` lists its tools.

## Claude Code

Run this in the workspace you want Claude to use. `--scope local` keeps the entry personal to the workspace. Choose `--scope user` only if you want the same root available across all projects.

```sh
claude mcp add --transport stdio --scope local 3d-agent-studio -- \
  "$STUDIO_MCP" --output-root "$STUDIO_JOBS"
claude mcp list
```

See [Claude Code's MCP setup guide](https://code.claude.com/docs/en/mcp).

## Codex

This command registers the server in your Codex user configuration:

```sh
codex mcp add 3d-agent-studio -- "$STUDIO_MCP" --output-root "$STUDIO_JOBS"
codex mcp list
```

For a project-scoped setup, put this table in a trusted workspace's `.codex/config.toml` instead:

```toml
[mcp_servers."3d-agent-studio"]
command = "/absolute/checkout/.venv/bin/3d-agent-studio-mcp"
args = ["--output-root", "/absolute/jobs"]
```

Restart Codex or start a fresh session and use `/mcp` to check the tools. See [Codex MCP configuration](https://developers.openai.com/codex/mcp).

## Hermes Agent and OpenCode

In the intended Hermes profile, confirm `hermes config path`, then run:

```sh
hermes mcp add 3d-agent-studio --command "$STUDIO_MCP" --args --output-root "$STUDIO_JOBS"
hermes mcp test 3d-agent-studio
```

Confirm the discovered tools when prompted. Start a new session or use `/reload-mcp`. Use `$HERMES_HOME/skills` for the live skill link.

For current OpenCode releases that support non-interactive `mcp add`:

```sh
opencode mcp add 3d-agent-studio --global -- "$STUDIO_MCP" --output-root "$STUDIO_JOBS"
opencode mcp list
```

Check `opencode mcp add --help` for older releases. OpenCode can read the skill from `~/.config/opencode/skills` or a compatible global root such as `~/.agents/skills` ([discovery order](https://opencode.ai/docs/skills/)).

## Other agents

For any client with **local stdio MCP**, use the executable as the command, and pass `--output-root` and the path as separate arguments. The server's stdout is MCP transport; use `3d-agent-studio doctor` for a human-readable runtime probe from the terminal. Add `STUDIO_BLENDER`, `STUDIO_FFMPEG` and `STUDIO_FFPROBE` as server environment variables if the agent GUI starts with a limited `PATH`. These are absolute executable paths (not shell snippets). In Codex this is a server `env` table or `codex mcp add --env KEY=VALUE`; in Claude use `claude mcp add --env KEY=VALUE`; in JSON configs add an `env` object alongside `args`.

For a client that can run commands but not MCP, use the standalone CLI. Give the agent the entire [skill directory](../skills/3d-agent-studio/SKILL.md), including `references/`. Install it in the client's skill location if supported, or explicitly tell it to read `SKILL.md` from the checkout. A remote-only host without local stdio or shell access cannot run Blender on your computer. There is no hosted renderer.

## Verification

1. Call `studio_doctor` in a fresh session. Check the job root and the Blender, FFmpeg and FFprobe versions.
2. Call `studio_examples` with `query: "product"` and `include_script: true`. Check that you get a scene script and local poster and clip paths.
3. Call `studio_draft` with `brief: {"prompt":"A red cube turns on a grey floor","orientation":"square","seconds":2}` and this Python as `script`.

   ```python
   def build(kit):
       kit.ground()
       cube = kit.box("Cube", 1, (0, 0, .5), kit.material("Red", "#BD3026"))
       kit.spin(cube)
       kit.sun()
       kit.camera()
   ```

4. Poll `studio_status` until `preview.state` is `ready`. Use `studio_view` for `timeline.jpg` and `angles.jpg`. If the host does not show MCP images inline, open the local paths. The six images in the timeline should show the cube turning.
