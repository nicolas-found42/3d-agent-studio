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

From the checkout after `uv sync --locked --extra mcp`, run these commands for the intended profile and confirm the studio tools when prompted. Put any `--env STUDIO_BLENDER=/absolute/Blender STUDIO_FFMPEG=/absolute/ffmpeg STUDIO_FFPROBE=/absolute/ffprobe` override **before** `--args`. Open a fresh conversation or run `/reload-mcp`.

```sh
hermes config path
hermes mcp add 3d-agent-studio --command "$PWD/.venv/bin/3d-agent-studio-mcp" \
  --args --output-root "$HOME/3d-agent-studio-jobs"
hermes mcp list
hermes mcp test 3d-agent-studio
```

## Verified on local macOS

**Claude Code 2.1.319, v0.3.0 checkout.** A model-driven session loaded the local server from a temporary MCP config. The tool results in order were `studio_doctor` (Blender 5.2.2, FFmpeg and FFprobe 9.0.2, libx264), `studio_ingest` (two rows from a local CSV), `studio_examples` (an architecture example) and `studio_probe` (queued a new square job). The render worker completed the probe. Its motion check warned that the three sampled poses of the spinning cube looked similar. The test used OpenRouter as the Claude Code model gateway and a synthetic fixture. [Gateway configuration](https://openrouter.ai/docs/cookbook/coding-agents/claude-code-integration)

The following host results were collected against v0.2.0. Run the [current host verification](agents.md#verification) after installing v0.3.0.

- **Oh My Pi 19.1.1:** `/mcp list` showed the configuration; `/mcp test 3d-agent-studio` over `omp --mode rpc --no-ui --no-session` confirmed a real connection and all seven tools. The first-party SDK separately invoked `studio_brief` with `orientation: horizontal` and discovered the skill under `.agents/skills`. No interactive model turn.
- **Codex CLI 0.169.0:** added the server in a disposable Codex home. App-server `mcpServerStatus/list` returned seven tools; `mcpServer/tool/call` invoked `studio_brief` and returned its normalized brief. No model turn.
- **Hermes Agent 0.23.3:** in an isolated Hermes home, `mcp test` found all seven studio tools, and dispatch through the Hermes tool registry returned a normalized brief from `mcp__3d_agent_studio__studio_brief`. Hermes also registered its own resource and prompt helpers; they are not studio tools. No model turn.
- **Claude Code 2.1.319:** `mcp add --scope local` and `mcp list` in a disposable config reported `Connected`. This proves a connection, not a model-generated tool call.
- **Cursor CLI 2026.11.17-f532c45:** the disposable workspace entry was approved, then `cursor-agent mcp list-tools 3d-agent-studio` showed seven tools. Desktop UI and cloud behavior were not exercised.
- **Portable core:** Python MCP SDK and the CLI agreed on job status for real Blender previews in both orientations. All four MCP JPEG responses matched the files on disk. Stdio worked from a separate working directory with a space in the configured path. The official Agent Skills validator accepted the bundled skill. These checks do not establish that every host surfaces image content the same way.

For runtime paths, draft verification and image fallbacks, see [agent setup](agents.md#verification).

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
