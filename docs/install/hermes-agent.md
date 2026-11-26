# Hermes Agent

## Install the release

Complete the [shared release prerequisites](../marketplace.md#install-a-release), then run:

```sh
hermes plugins install nicolas-found42/3d-agent-studio
```

Approve the dependency and enable prompts after reviewing the package. Noninteractive installers that already have consent can pass `--yes-deps --enable`. Start a fresh session and call `studio_doctor`. In Hermes v0.23.3, `hermes mcp test` checks manual registrations. For the plugin, use the [tool verification](../verification/agent-install.md) instead.

## Use a local checkout

Set the [checkout paths](../agents.md#choose-paths-once) and confirm the intended profile before adding the server.

```sh
hermes config path
hermes mcp add 3d-agent-studio --command "$STUDIO_MCP" --args --output-root "$STUDIO_JOBS"
hermes mcp test 3d-agent-studio
```

Put any `--env KEY=VALUE` overrides before `--args` and confirm the discovered tools. Link the checkout's Studio skill in the profile's `skills/` directory beside the file reported by `hermes config path` (default `~/.hermes/skills/`). Start a fresh session or use `/reload-mcp`, then [verify the Studio tools](../verification/agent-install.md). [Hermes MCP setup](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp) · [Plugin installation](https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins)
