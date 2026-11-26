# Prompt-driven acceptance scenes

Open a scenario for its brief and input declarations. The checkout also contains each Blender scene script and its packaged evidence in `result/`. Start with the [rendered examples](../docs/examples.md) to see clips, scripts, and review boards. The [released fixtures](https://github.com/nicolas-found42/3d-agent-studio/tree/v0.3.0/acceptance) include the source inputs.

| Scene | Inputs and technique |
|---|---|
| [Society village](society-village/acceptance.json) | Simulation journal CSV and animated GIF of the observer as a layout diagram |
| [Gothic nave](gothic-nave/acceptance.json) | Prompt, scanned public asset materials, and a side-by-side comparison with the Laon benchmark |
| [Teapot from photo](teapot-from-photo/acceptance.json) | One subject photograph reconstructed with turned and swept geometry |
| [Fox asleep](fox-asleep/acceptance.json) | Prompt, a procedural character, breathing and snowfall in a seamless loop |
| [Iceland falls](iceland-falls/acceptance.json) | Subject and palette photos, imported OBJ and a moving whitewater material |
| [Village motives](village-motives/acceptance.json) | A 90-day CSV, SVG, TrueType font and text shot list |

## Reproduce a scenario

Use a scratch root outside the checkout. The review stage uses the dev-only Jev chain over OpenRouter and needs `OPENROUTER_API_KEY`. Confirm you can send the selected reference and rendered images before running it.

```sh
uv run --locked python tools/run_acceptance.py fox-asleep --probe --root /absolute/scratch/jobs
uv run --locked python tools/run_acceptance.py fox-asleep --job PROBE_JOB_ID --root /absolute/scratch/jobs
```

After the probe, inspect its stills and checks before running the draft. After the draft, open the timeline, angles, references and seam as applicable, then play `reel.mp4`. Record your observations per board and any justified Jev overrides in the scenario's `acceptance.json`. Package the reviewed draft with `--job JOB_ID --package --root /absolute/scratch/jobs`. Use `--probe --parent JOB_ID` to start a revision after a scene change.

The nave's comparison image is read at packaging time from the sibling `resurrection-site` checkout named in its spec. The studio renders the nave from the brief and its declared asset IDs.
