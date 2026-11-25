# Render verification

The prompt-driven acceptance runs use an Apple M5 Pro with a 20-core GPU, Blender 5.2.2 and FFmpeg 9.0.2. The production worker uses Cycles on Metal for the six acceptance scenes. See the [acceptance scenes](../acceptance/README.md) for their exact inputs and scripts.

## What the checks cover

- `qc.json` verifies that the H.264 High MP4 has one silent stream, continuous 24 fps timestamps for these scenarios, BT.709 limited-range color, and fast-start layout. For loops it decodes the repeated video and compares its frame hashes to two copies of the single cycle. The loop-seam board shows the transition. Machine checks cover sequence integrity. Read the visual notes for motion, visibility and composition.
- The probe measures a short preview sequence and separate full-resolution sequences at 16 and 64 samples. Draft and master QC record predicted and actual active minutes. Time spent queued for the shared GPU lock is excluded. Changes in scene complexity and one-time kernel or lighting setup can affect the estimate.
- The opt-in Blender test drives the CLI through a draft, a revision and a master. It checks board hashes, a comparison, board images through the MCP wire interface, a 4444 ProRes export, PNG plates and a hard probe timeout.

## CLI and MCP render fixture

The two-second square loop produced 48 decoded frames at 24 fps in the 360×360 draft and the 1080×1080 master. The two-cycle files decoded to 96 frames in order. The approved master retained 49 PNG plates including the extra seam frame and exported a ProRes 4444 movie. The test rejected invalid review hashes, then compared the top and bottom image pixels against the older and revised boards. MCP `studio_view` returned byte-identical JPEG or PNG images for every available board in the probe, draft and master.

| Stage | Predicted minutes | Actual minutes | Difference |
|---|---:|---:|---:|
| Square draft | 0.32 | 0.421 | 24% low |
| Revised square draft | 0.33 | 0.314 | 5% high |
| Square master at 64 samples, three-minute budget | 2.35 | 2.270 | 4% high |

A separate Blender probe deliberately exceeded its one-minute budget. The worker reported the timeout and left the stage failed. The original moonlit desert run also hit the ten-minute draft deadline during its angle proofs after a 6.68-minute estimate. The timed-out job had no ready preview. The square fixture's earlier master forecast scaled a preview measurement to 1080p and predicted 0.66 minutes for a 2.29-minute run at 128 samples. Full-resolution calibration changed the fast plan to 64 samples under the three-minute budget.

The Blender kit test confirmed that a new child keeps its world position when parented and that object and material socket keys use the requested constant or linear interpolation. The Village Motives scene was checked frame by frame against the same keyframe fix. All 120 frames had the expected single day label, all 90 day numbers appeared, and 540 band boundaries matched the CSV. The imported SVG measured 0.52 metres wide. In Society Village, the saved scene matched the journal's gem colors and settled positions for 12 villagers across turns 325–336.

## Acceptance master

Fox Asleep promoted from the current draft board hashes and written visual notes. With the one-minute standard budget, the studio refused the estimated 39.65 minutes at 128 samples. The ten-minute fast plan chose 16 samples and predicted 6.49 minutes. The job finished in 6.08 active minutes, about 7% below the estimate. The 1920×1080 master decoded to 96 frames at 24 fps, and the two-cycle file decoded to 192 in order. The worker removed the PNG sequence because `png` was omitted. The master boards passed visual review and Jev flagged three observations for checking, all recorded in the review. [Master clip](../acceptance/fox-asleep/result/master.mp4) · [Master evidence](../acceptance/fox-asleep/result/master-review.json)

## Acceptance evidence

Each `result/review.json` records the draft job, frame and timing measurements, Jev answers, and board observations. The Gothic scenario includes a side-by-side still against the Laon benchmark. The Iceland draft passed media checks and demonstrates the reference and model inputs with a stylized result. Its review keeps the original basic quality grade and documents the visual exceptions.

| Scenario | Input | Draft evidence |
|---|---|---|
| Society village | Animated GIF and journal CSV | 288 frames at 640×360, 24 fps. 7.00 min predicted, 5.75 min active. Jev polished with one diagram-layout override. [Boards and notes](../acceptance/society-village/result/review.json) |
| Gothic nave | Prompt and open material assets | 120 frames at 640×360, 24 fps. 2.87 min predicted, 2.38 min active. Jev polished and exact. [Laon comparison](../acceptance/gothic-nave/result/compare.jpg) · [Review notes](../acceptance/gothic-nave/result/review.json) |
| Teapot from photo | One subject photo | 96 frames at 640×360, 24 fps. 1.55 min predicted, 0.92 min active. Jev polished and close to the paired photograph, with a written prompt-match override. [Boards and notes](../acceptance/teapot-from-photo/result/review.json) |
| Fox asleep | Prompt-only character loop | 96 frames at 640×360, 24 fps. Jev polished. The 1080p master and both loop cycles passed QC. [Draft notes](../acceptance/fox-asleep/result/review.json) |
| Iceland falls | Two photos and an OBJ import | 120 frames at 640×360, 24 fps. 3.28 min predicted, 2.79 min active. Jev basic, with documented quality and reference exceptions. [Boards and notes](../acceptance/iceland-falls/result/review.json) |
| Village motives | CSV, SVG, font and shot list | 120 frames at 640×360, 24 fps. 1.58 min predicted, 1.11 min active. Jev polished with a prompt-match override backed by decoded frames and a data check. [Boards and notes](../acceptance/village-motives/result/review.json) |
