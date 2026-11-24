# Connect an agent

Install and run `3d-agent-studio doctor` first (see the [README](../README.md)). Then choose one connection method. All hosts use the same local stdio server; neither this server nor the CLI requires a model account. Agent-host accounts and policies are separate.

## Choose paths once

On macOS/Linux, from the checkout after `uv sync --locked --extra mcp`:

```sh
STUDIO_MCP="$PWD/.venv/bin/3d-agent-studio-mcp"
STUDIO_JOBS="$HOME/3d-agent-studio-jobs"
```

For Windows paths, use `.venv\Scripts\3d-agent-studio-mcp.exe`, and escape backslashes inside JSON strings. Windows rendering has not been verified. Use absolute paths in host settings, even if the host supports variables. A configured job root belongs to the local server process, not the current working directory of the agent. Use separate roots for projects whose artifacts should not be visible to each other.

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

## Other agents

For any client with **local stdio MCP**, use the executable as the command, and pass `--output-root` and the path as separate arguments. The server's stdout is MCP transport; use `3d-agent-studio doctor` for a human-readable runtime probe from the terminal. Add `STUDIO_BLENDER`, `STUDIO_FFMPEG` and `STUDIO_FFPROBE` as server environment variables if the agent GUI starts with a limited `PATH`. These are absolute executable paths (not shell snippets). In Codex this is a server `env` table or `codex mcp add --env KEY=VALUE`; in Claude use `claude mcp add --env KEY=VALUE`; in JSON configs add an `env` object alongside `args`.

For a client that can run commands but not MCP, use the standalone CLI. Give the agent the entire [skill directory](../skills/3d-agent-studio/), including `references/`. Install it in the client's skill location if supported, or explicitly tell it to read `SKILL.md` from the checkout. A remote-only host without local stdio or shell access cannot run Blender on your computer. There is no hosted renderer.

## Verification

Use a fresh session and ask the agent to run `studio_doctor`. It should return the chosen job root, the three runtime versions, and the brief defaults. Follow up with `studio_brief` and a two-second test. If the agent can read MCP image content, `studio_view` returns the JPEG directly; otherwise open the local path in an image viewer. Review media stays local unless you or the host send it elsewhere.
