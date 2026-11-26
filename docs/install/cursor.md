# Cursor

## Install for a team

On eligible plans, a team admin can import `nicolas-found42/3d-agent-studio` under **Dashboard → Plugins & MCPs → Team Marketplaces**. Studio is distributed through this team import. For personal accounts, configure a local checkout.

## Use a local checkout

Add the [stdio entry](../agents.md#stdio-configuration) to the workspace's `.cursor/mcp.json` or your user `~/.cursor/mcp.json`. In **Customize → MCP**, enable Studio and inspect its tools. In Cursor CLI, run:

```sh
cursor-agent mcp enable 3d-agent-studio
cursor-agent mcp list-tools 3d-agent-studio
```

Give the agent the bundled [Studio skill](../../skills/3d-agent-studio/SKILL.md) from the checkout, then [verify the Studio tools](../verification/agent-install.md). [Cursor MCP configuration](https://cursor.com/docs/context/mcp) · [Team marketplaces](https://cursor.com/docs/plugins)
