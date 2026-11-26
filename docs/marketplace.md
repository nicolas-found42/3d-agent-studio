# Install Studio for your agent

Choose your agent for its release and checkout instructions. Studio starts a local MCP server and uses the bundled scene-authoring skill on the machine running Blender.

## Install a release

Install `uv` (including `uvx`), Git, Blender, and FFmpeg with `ffprobe` and `libx264` on the render machine. Make sure the agent can find `uvx` on its own `PATH`. The [v0.3.0 plugin](https://github.com/nicolas-found42/3d-agent-studio/releases/tag/v0.3.0) installs the tagged Python package on first use. Its plugin ID is `3d-agent-studio` and its catalog is `found42-studio`.

- <a id="claude-code"></a>[Claude Code](install/claude-code.md)
- <a id="codex"></a>[Codex](install/codex.md)
- <a id="oh-my-pi"></a>[Oh My Pi](install/oh-my-pi.md)
- <a id="hermes-agent"></a>[Hermes Agent](install/hermes-agent.md)
- <a id="cursor"></a>[Cursor](install/cursor.md)
- [OpenCode](install/opencode.md)
- <a id="other-hosts"></a>[Other hosts and terminal-only setup](agents.md#other-agents)

## Next steps

- <a id="verify-the-install"></a>[Check tool discovery and render a draft](verification/agent-install.md) in a fresh agent session.
- <a id="develop-against-one-checkout"></a>[Prepare an editable checkout](agents.md) and follow the local setup for your host. Use one effective Studio MCP registration per host.
- <a id="distribution-references"></a>[Read the Agent Plugins specification](https://agent-plugins.org/specification) for the portable manifest. Each host page links to its installation reference.
