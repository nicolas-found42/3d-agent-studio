# OpenCode

Use a local checkout. Set the [checkout paths](../agents.md#choose-paths-once), then register the MCP server in your OpenCode user configuration.

```sh
opencode mcp add 3d-agent-studio --global -- "$STUDIO_MCP" --output-root "$STUDIO_JOBS"
opencode mcp list
```

For older releases, check `opencode mcp add --help` for the available registration options. Link the Studio skill in `~/.config/opencode/skills/` or the compatible `~/.agents/skills/` root. Open a new session and [verify the Studio tools](../verification/agent-install.md). [OpenCode skill discovery](https://opencode.ai/docs/skills/)
