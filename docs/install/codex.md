# Codex

## Install the release

Complete the [shared release prerequisites](../marketplace.md#install-a-release), then run:

```sh
codex plugin marketplace add nicolas-found42/3d-agent-studio
codex plugin add 3d-agent-studio@found42-studio
```

## Use a local checkout

Set the [checkout paths](../agents.md#choose-paths-once) and register in your Codex user configuration.

```sh
codex mcp add 3d-agent-studio -- "$STUDIO_MCP" --output-root "$STUDIO_JOBS"
codex mcp list
```

For a project-scoped setup, put this table in a trusted workspace's `.codex/config.toml`. Replace both values with absolute paths. Runtime overrides go in the server's `env` table or in `codex mcp add --env KEY=VALUE`.

```toml
[mcp_servers."3d-agent-studio"]
command = "/absolute/checkout/.venv/bin/3d-agent-studio-mcp"
args = ["--output-root", "/absolute/jobs"]
```

Link the checkout's Studio skill under `~/.agents/skills/` or the workspace's `.agents/skills/`. Start a fresh session or restart Codex, check `/mcp`, and [verify the Studio tools](../verification/agent-install.md). [Codex MCP configuration](https://developers.openai.com/codex/mcp) · [Plugin setup](https://developers.openai.com/plugins/build/plugins)
