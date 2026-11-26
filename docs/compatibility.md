# Agent compatibility evidence

## Decision

Use one local stdio MCP server for tool discovery and invocation. The MCP client starts the executable as a child process; stdout carries only protocol messages and logs go to stderr.[1] Use one portable Agent Skill with `name`, `description`, and relative references; connect the MCP server separately from installing the skill.[2] Keep the CLI usable without MCP or any agent SDK.

## Host requirements

| Host | Local server registration | What the studio depends on |
|---|---|---|
| Oh My Pi (OMP) | `.omp/mcp.json` or the active agent profile's `mcp.json`; `mcpServers.<name>` uses `command` and `args`.[3] | Keep one effective entry. OMP can import settings from other agents, and a duplicate or user-level `disabledServers` entry can mask the intended server.[3] |
| Codex | `codex mcp add NAME -- COMMAND ARGS…` saves to user config. For project scope, use `[mcp_servers.<name>]` in a trusted workspace's `.codex/config.toml`.[4] | An untrusted workspace can silently ignore the project entry. A clone does not include a machine-specific `.codex/config.toml`. No marketplace install is required. |
| Hermes Agent | `mcp_servers.<name>` in the active profile, with `command` and `args`; stock Hermes discovers tools at session startup.[5] | `hermes mcp add` discovers tools before saving; verify with `hermes mcp test 3d-agent-studio`. Use a fresh session or `/reload-mcp` after adding. |
| Claude Code | `claude mcp add --transport stdio --scope local NAME -- COMMAND ARGS…`. Add and launch from the same workspace directory. User scope shares one job root across workspaces; project `.mcp.json` can require approval.[6] | When using `--env`, put `NAME` **before** `--env KEY=VALUE`, then the `--` separator. `Connected` checks the handshake; `studio_doctor` checks Blender and FFmpeg on the host's actual PATH. |
| Cursor | `.cursor/mcp.json` or `~/.cursor/mcp.json`, with a stdio `command` and `args` under `mcpServers`.[7] | The server may need to be enabled in the workspace; CLI discovery is separate from desktop and cloud sessions. |

Absolute executable and job paths avoid assumptions about the working directory or shell startup. `--output-root` fixes the job boundary at server startup, and render tools never accept shell fragments or tool-supplied paths. Long renders run in local workers; the initial call returns a job ID, so the host does not have to keep one request open for the duration of a Blender render. Review boards are standard MCP image content with a path fallback.

## Skill discovery (separate from MCP)

The checkout's `skills/` directory is the source, not an automatic install location. Copy the entire [3d-agent-studio skill directory](../skills/3d-agent-studio/SKILL.md), including `references/`, into one of these parent directories. Start a fresh session if the skill does not appear.

| Host | Skill parent directory |
|---|---|
| OMP | `<workspace>/.agents/skills/` (native `.omp/skills/` is also supported).[8] |
| Codex | `<workspace>/.agents/skills/` or `~/.agents/skills/`.[9] |
| Claude Code | `<workspace>/.claude/skills/` or `~/.claude/skills/`.[10] |
| Hermes Agent | The intended profile's `skills/` (default `~/.hermes/skills/`). Use the directory containing the file printed by `hermes config path`.[11] |

### Install and test in Hermes

See [Hermes profile setup and discovery](install/hermes-agent.md#use-a-local-checkout).

## Verified on local macOS

See the [tested clients, versions, and verification limits](verification/agent-compatibility.md).

## Sources

[1] https://modelcontextprotocol.io/specification/2025-11-25/basic/transports
[2] https://agentskills.io/specification
[3] https://raw.githubusercontent.com/can1357/oh-my-pi/main/docs/mcp-config.md
[4] https://developers.openai.com/codex/mcp
[5] https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp
[6] https://code.claude.com/docs/en/mcp
[7] https://cursor.com/docs/context/mcp
[8] https://raw.githubusercontent.com/can1357/oh-my-pi/main/docs/skills.md
[9] https://developers.openai.com/codex/skills
[10] https://code.claude.com/docs/en/skills
[11] https://hermes-agent.nousresearch.com/docs/user-guide/features/skills
