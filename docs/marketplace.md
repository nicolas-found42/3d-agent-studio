# Found42 Studio marketplace

The public catalog is `nicolas-found42/3d-agent-studio`. The plugin is `3d-agent-studio`; the catalog name is `found42-studio`. The repository ships one Agent Plugins 1.0 package (skill and local stdio MCP) plus catalog manifests for hosts that use their own formats.

## Install a release

Install `uv` (including `uvx`), Git, Blender, and FFmpeg with `ffprobe` and `libx264` on the machine running your agent. The agent must be able to find `uvx` on its own `PATH`, which may differ from your shell's. The MCP launcher installs the tagged Python package on first use. Rendering happens locally and does not require a Blender add-on, model credentials, or a network listener.

The Codex marketplace entry selects the repository's local plugin package. The portable `plugin.json` carries the version and `mcp.json` pins the Python launcher to the release tag.

**Claude Code** — in a shell:

```sh
claude plugin marketplace add nicolas-found42/3d-agent-studio
claude plugin install 3d-agent-studio@found42-studio --scope user
```

**Codex** — in a shell:

```sh
codex plugin marketplace add nicolas-found42/3d-agent-studio
codex plugin add 3d-agent-studio@found42-studio
```

**Oh My Pi** — in a shell:

```sh
omp plugin marketplace add nicolas-found42/3d-agent-studio
omp plugin install 3d-agent-studio@found42-studio --scope user
```

In OMP 19.1.1 the catalog install succeeded, but the released server did not appear in `/mcp list` in the clean test profile. If that happens, merge the `3d-agent-studio` entry from [the release's `mcp.json`](../mcp.json) into your OMP `mcpServers` in `~/.omp/agent/mcp.json`. Copy the entry, not the `$schema` or the entire config. That fallback was tested with `studio_doctor` and `studio_brief`. If the skill is also missing, point OMP to the [skill directory](../skills/3d-agent-studio/) from a local checkout.

**Hermes Agent** — install the same portable package directly from GitHub and consent to enable it:

```sh
hermes plugins install nicolas-found42/3d-agent-studio
```

Approve the dependency and enable prompts after reviewing the package. Noninteractive installers that already have consent can pass `--yes-deps --enable`. Start a new session and call `studio_doctor`: `hermes mcp test` checks manually configured servers, not portable plugin registrations on Hermes v0.23.3.

**Cursor** — a team admin can import the repo under **Dashboard → Plugins & MCPs → Team Marketplaces** on eligible plans. This repo is not a listing in Cursor's curated public marketplace. Personal users can use the local MCP and skill setup below without a team marketplace.

**OpenCode and other hosts** — use [local MCP and skill setup](agents.md). For a shell-capable host with no MCP, use the [standalone CLI](../README.md#use-from-a-terminal). A cloud-only host that cannot launch a process on the render machine cannot use this local renderer. Every host needs no more than one Studio MCP registration; remove or disable one path before switching to another.

After installing, run the [host verification](agents.md#verification) from a fresh agent session. `studio_doctor` checks the runtime and `studio_draft` makes a short render. If the host cannot find a renderer executable, configure the absolute paths in [agent setup](agents.md).

## Develop against one checkout

1. Clone the repo and run `uv sync --locked --extra mcp` in it. The install is editable.
2. Use the host's [direct MCP registration](agents.md) with the checkout's `.venv/bin/3d-agent-studio-mcp`. Pass `--output-root` and an absolute development job directory. Use the same directory across hosts if you want to inspect the same jobs.
3. Symlink the checkout's `skills/3d-agent-studio` directory into the host's user skill directory. Use the native or compatible skill location, not both when the host loads both. This keeps the skill and its references on the same source as the server.
4. Restart the host or reload its MCP connection after a Python edit. Run `uv sync --locked --extra mcp` again after dependency changes. Open a new session to rediscover the skill. Call `studio_doctor` and the same `studio_brief` on each host; for image parity, call `studio_view` on the same ready job and board.

Adding the local checkout as a marketplace source is useful for testing catalog discovery. **Installing from that catalog is not live-code mode.** Marketplace installs use the tagged launcher, and some hosts copy the skill and manifest into an install cache. Keep the release install disabled or use a disposable profile while testing it. Unlink development mode by removing just the `3d-agent-studio` MCP entry and the skill symlink, not the checkout or the jobs.

## Distribution references

- [Agent Plugins specification](https://agent-plugins.org/specification)
- [Claude Code plugin marketplaces](https://code.claude.com/docs/en/plugin-marketplaces)
- [Codex plugin marketplace setup](https://developers.openai.com/plugins/build/plugins)
- [Oh My Pi marketplace](https://raw.githubusercontent.com/can1357/oh-my-pi/main/docs/marketplace.md)
- [Hermes plugin installation](https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins)
- [Cursor team marketplaces](https://cursor.com/docs/plugins) and [manifest reference](https://cursor.com/docs/plugins/building)
- [OpenCode global skill locations](https://opencode.ai/docs/skills/)
