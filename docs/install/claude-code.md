# Claude Code

## Install the release

Complete the [shared release prerequisites](../marketplace.md#install-a-release), then run:

```sh
claude plugin marketplace add nicolas-found42/3d-agent-studio
claude plugin install 3d-agent-studio@found42-studio --scope user
```

## Use a local checkout

Set the [checkout paths](../agents.md#choose-paths-once), then run this in the workspace you want Claude Code to use.

```sh
claude mcp add --transport stdio --scope local 3d-agent-studio -- \
  "$STUDIO_MCP" --output-root "$STUDIO_JOBS"
claude mcp list
```

Use `--scope user` to make the same entry and job root available across workspaces. If you supply environment overrides, put `--env KEY=VALUE` after the server name and before the `--` separator. Link the checkout's Studio skill under `~/.claude/skills/` or the workspace's `.claude/skills/`.

Check that the server reports `Connected`, then [verify the Studio tools](../verification/agent-install.md) in a fresh session. [Claude Code MCP setup](https://code.claude.com/docs/en/mcp) · [Plugin marketplaces](https://code.claude.com/docs/en/plugin-marketplaces)
