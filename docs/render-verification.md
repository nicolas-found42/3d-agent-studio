# Render verification

The prompt-driven acceptance runs use an Apple M5 Pro with a 20-core GPU, Blender 5.2.2 and FFmpeg 9.0.2. The production worker uses Cycles on Metal for the six acceptance scenes. See the [acceptance scenes](../acceptance/README.md) for their exact inputs and scripts.

## What the checks cover

See [Media, timing, and the probe deadline](verification/render-checks.md#what-the-checks-cover).

## CLI and MCP render fixture

See [The square loop, review hashes, and export checks](verification/render-checks.md#cli-and-mcp-render-fixture).

## Acceptance master

See [The Fox Asleep master](verification/acceptance.md#acceptance-master).

## Acceptance evidence

See [Draft evidence for all six scenes](verification/acceptance.md#acceptance-evidence).
