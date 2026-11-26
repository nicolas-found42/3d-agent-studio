# Oh My Pi

## Install the release

Complete the [shared release prerequisites](../marketplace.md#install-a-release), then run:

```sh
omp plugin marketplace add nicolas-found42/3d-agent-studio
omp plugin install 3d-agent-studio@found42-studio --scope user
```

In the clean OMP 19.1.1 test profile, the catalog install succeeded and the server was absent from `/mcp list`. If that happens, copy the Studio entry from the [release's `mcp.json`](../../mcp.json) into `mcpServers` in `~/.omp/agent/mcp.json`. The fallback passed `studio_doctor` and `studio_brief`. If the skill is missing too, link it from a local checkout as described below.

## Use a local checkout

Add the [stdio entry](../agents.md#stdio-configuration) to the workspace's `.omp/mcp.json` or your active profile's `mcp.json` (default `~/.omp/agent/mcp.json`). Use the profile file if project MCP is disabled. OMP can import other hosts' settings, so keep one effective entry.

Link the checkout's Studio skill under the workspace's `.agents/skills/` or `.omp/skills/`, or the shared user root `~/.agents/skills/`. In a new session, run `/mcp test 3d-agent-studio`, then [verify the Studio tools](../verification/agent-install.md). [OMP MCP configuration](https://github.com/can1357/oh-my-pi/blob/main/docs/mcp-config.md) · [Marketplace](https://raw.githubusercontent.com/can1357/oh-my-pi/main/docs/marketplace.md)
