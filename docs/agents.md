# Connect an editable checkout

<a id="connect-an-agent"></a>

Use an editable checkout so the renderer and scene-authoring skill follow your source changes. For a tagged install, see the [release and host guides](marketplace.md).

## Choose paths once

Complete [Check the renderer](quickstart.md#check-the-renderer), then run these commands from the checkout in the same shell you'll use for MCP registration.

```sh
uv sync --locked --extra mcp
STUDIO_MCP="$PWD/.venv/bin/3d-agent-studio-mcp"
STUDIO_JOBS="$HOME/3d-agent-studio-jobs"
```

Use absolute paths. The render worker uses POSIX file locking and the server fixes the job root at startup. Share a root across hosts to inspect the same jobs, or use separate roots to keep workspaces isolated.

- <a id="claude-code"></a>[Claude Code](install/claude-code.md#use-a-local-checkout)
- <a id="codex"></a>[Codex](install/codex.md#use-a-local-checkout)
- <a id="oh-my-pi-omp-and-cursor"></a>[Oh My Pi](install/oh-my-pi.md#use-a-local-checkout) and [Cursor](install/cursor.md#use-a-local-checkout)
- <a id="hermes-agent-and-opencode"></a>[Hermes Agent](install/hermes-agent.md#use-a-local-checkout) and [OpenCode](install/opencode.md)

## Keep the checkout live

Link the complete `skills/3d-agent-studio` directory into one skill root for the host. The host pages name their skill roots. Restart its MCP connection after Python edits and run `uv sync --locked --extra mcp` after dependency changes. Start a fresh agent session to rediscover the skill.

A marketplace entry added from a local checkout still launches the tagged release. Disable that entry while developing with a direct MCP registration. To unlink development mode, remove the Studio MCP entry and skill symlink. Keep your checkout and jobs.

## Stdio configuration

Use this entry with clients that store MCP servers under `mcpServers`. Replace both values with absolute paths and preserve existing entries.

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

If a host starts with a limited `PATH`, set `STUDIO_BLENDER`, `STUDIO_FFMPEG`, and `STUDIO_FFPROBE` to absolute executable paths. Use the host's server environment, such as a JSON `env` object.

## Other agents

A local stdio client can launch the executable above with the job root as two separate arguments. MCP uses stdout for protocol traffic. Use `3d-agent-studio doctor` for a human-readable runtime check from the terminal.

For a shell-capable agent without MCP, use the [standalone CLI](quickstart.md). Give it the [full skill directory](../skills/3d-agent-studio/SKILL.md), including its references. The agent needs shell or stdio access to the machine running Blender. The host handles its model connection separately.

## Verification

[Verify the connection, render a draft, and open its review boards](verification/agent-install.md).
