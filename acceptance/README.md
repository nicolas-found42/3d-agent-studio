# Prompt-driven acceptance scenes

Open a case study to see its draft, brief, scene script, and review boards. The checkout also contains each Blender scene script and its packaged evidence in `result/`. Start with the [acceptance case studies](../docs/examples.md) to see clips, scripts, and review boards. The [released fixtures](https://github.com/nicolas-found42/3d-agent-studio/tree/v0.3.0/acceptance) include the source inputs.

| Scene | Inputs and technique | Scenario file |
|---|---|---|
| [Society village](../docs/examples/society-village.md) | Simulation journal CSV and animated GIF of the observer as a layout diagram | [Brief and inputs](society-village/acceptance.json) |
| [Gothic nave](../docs/examples/gothic-nave.md) | Prompt, scanned public asset materials, and a side-by-side comparison with the Laon benchmark | [Brief and inputs](gothic-nave/acceptance.json) |
| [Teapot from photo](../docs/examples/teapot-from-photo.md) | One subject photograph reconstructed with turned and swept geometry | [Brief and inputs](teapot-from-photo/acceptance.json) |
| [Fox asleep](../docs/examples/fox-asleep.md) | Prompt, a procedural character, breathing and snowfall in a seamless loop | [Brief and inputs](fox-asleep/acceptance.json) |
| [Iceland falls](../docs/examples/iceland-falls.md) | Subject and palette photos, imported OBJ and a moving whitewater material | [Brief and inputs](iceland-falls/acceptance.json) |
| [Village motives](../docs/examples/village-motives.md) | A 90-day CSV, SVG, TrueType font and text shot list | [Brief and inputs](village-motives/acceptance.json) |

## Reproduce a scenario

Use a scratch root outside the checkout. The review stage uses the dev-only Jev chain over OpenRouter and needs `OPENROUTER_API_KEY`. Confirm you can send the selected reference and rendered images before running it.

```sh
uv run --locked python tools/run_acceptance.py fox-asleep --probe --root /absolute/scratch/jobs
uv run --locked python tools/run_acceptance.py fox-asleep --job PROBE_JOB_ID --root /absolute/scratch/jobs
```

After the probe, inspect its stills and checks before running the draft. After the draft, open the timeline, angles, references and seam as applicable, then play `reel.mp4`. Record your observations per board and any justified Jev overrides in the scenario's `acceptance.json`. Package the reviewed draft with `--job JOB_ID --package --root /absolute/scratch/jobs`. Use `--probe --parent JOB_ID` to start a revision after a scene change.

The nave's comparison image is read at packaging time from the sibling `resurrection-site` checkout named in its spec. The studio renders the nave from the brief and its declared asset IDs.
