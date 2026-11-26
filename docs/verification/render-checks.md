# Render checks and fixtures

Studio's verification covers video integrity, render timing, and the CLI and MCP outputs.

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
