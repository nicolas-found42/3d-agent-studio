# Agent compatibility tests

## Verified on local macOS

**Claude Code 2.1.319, v0.3.0 checkout.** A model-driven session loaded the local server from a temporary MCP config. The tool results in order were `studio_doctor` (Blender 5.2.2, FFmpeg and FFprobe 9.0.2, libx264), `studio_ingest` (two rows from a local CSV), `studio_examples` (an architecture example) and `studio_probe` (queued a new square job). The render worker completed the probe. Its motion check warned that the three sampled poses of the spinning cube looked similar. The test used OpenRouter as the Claude Code model gateway and a synthetic fixture. [Gateway configuration](https://openrouter.ai/docs/cookbook/coding-agents/claude-code-integration)

The following host results were collected against v0.2.0. Run the [current host verification](agent-install.md) after installing v0.3.0.

- **Oh My Pi 19.1.1:** `/mcp list` showed the configuration; `/mcp test 3d-agent-studio` over `omp --mode rpc --no-ui --no-session` confirmed a real connection and all seven tools. The first-party SDK separately invoked `studio_brief` with `orientation: horizontal` and discovered the skill under `.agents/skills`. No interactive model turn.
- **Codex CLI 0.169.0:** added the server in a disposable Codex home. App-server `mcpServerStatus/list` returned seven tools; `mcpServer/tool/call` invoked `studio_brief` and returned its normalized brief. No model turn.
- **Hermes Agent 0.23.3:** in an isolated Hermes home, `mcp test` found all seven studio tools, and dispatch through the Hermes tool registry returned a normalized brief from `mcp__3d_agent_studio__studio_brief`. Hermes also registered its own resource and prompt helpers; they are not studio tools. No model turn.
- **Claude Code 2.1.319:** `mcp add --scope local` and `mcp list` in a disposable config reported `Connected`. This proves a connection, not a model-generated tool call.
- **Cursor CLI 2026.11.17-f532c45:** the disposable workspace entry was approved, then `cursor-agent mcp list-tools 3d-agent-studio` showed seven tools. Desktop UI and cloud behavior were not exercised.
- **Portable core:** Python MCP SDK and the CLI agreed on job status for real Blender previews in both orientations. All four MCP JPEG responses matched the files on disk. Stdio worked from a separate working directory with a space in the configured path. The official Agent Skills validator accepted the bundled skill. These checks do not establish that every host surfaces image content the same way.

For runtime paths, draft verification and image fallbacks, see [agent setup](agent-install.md).
