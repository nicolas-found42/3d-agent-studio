# Render workflow

Studio takes a brief and a Python scene script. The brief records what to render and which inputs the scene may use. The script builds the geometry, materials, lighting, camera, and motion in Blender.

## Attach a reference

Ingest a reference from a file on the render machine. Use the same job root for ingestion and rendering. This example marks a photo as a style reference.

```sh
uv run --locked 3d-agent-studio --output-root /absolute/jobs ingest \
  /absolute/path/photo.jpg --role style
```

Copy the returned reference ID into the brief's `references` array. The script can use the kit to read inputs declared in the brief. See the [reference kinds and roles](../skills/3d-agent-studio/references/operations.md#references) and the [teapot example](examples.md#teapot-from-photo) for a complete photo-based scene.

## Preview and revise

A **probe** builds the scene, saves `scene.blend`, and renders three stills. Check framing, required subjects, and the estimated draft and master times before spending time on every frame.

A **draft** renders the preview clip. Play it and inspect the six-frame timeline, alternate views, and reference or loop boards when present. If a change needs a new draft, create a child job with `parent` set to the previous job ID. Compare their boards before choosing which version to promote.

## Approve a master

Use the exact review hashes from the current draft and write notes about what you checked. Studio uses those hashes to bind approval to the draft you saw. A master delivers the full-resolution MP4 with the scene, script, cover, and credits. Request ProRes 4444 or numbered PNG frames through `extras` when needed.

Find the precise inputs, defaults, and file names in the [operations reference](../skills/3d-agent-studio/references/operations.md#stages-and-evidence). See [render verification](render-verification.md) for measured timing and decoded-media checks.

## Local files and script trust

The CLI takes `--output-root` before the subcommand. It overrides `STUDIO_OUTPUT_ROOT`, which defaults to `~/3d-agent-studio-jobs` when unset. MCP takes the job root at startup. Use the same absolute path so both clients can find the same references and jobs.

Use a dedicated directory you own. Studio executes scene scripts as your local user. Its static checks catch common mistakes and Blender starts headlessly with automatic execution of embedded scripts disabled. Treat a scene script as executable Python and run scripts you trust.

Ingest copies declared files into the job root. Studio fetches declared assets over HTTPS from the [supported sources](../skills/3d-agent-studio/references/operations.md#assets), checks licenses, and records attribution. The MCP server uses local stdio. An agent service may receive images or text you pass to that agent. Copy `scene.blend` outside the managed job before editing it by hand.
