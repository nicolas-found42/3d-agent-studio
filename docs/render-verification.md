# Render verification

Verified with Blender 5.2.2, FFmpeg 9.0.2 and the Python MCP SDK on macOS. The two-second drafts had 60 decoded frames; the repeated previews had 120. Both templates were rendered in landscape, and Gravity Conveyor in portrait. The portrait Gravity Conveyor preview was byte-identical to the pre-landscape video and all four earlier review boards.

| Promoted draft | Preview | Master | Decoded frames | Two-cycle repeat |
|---|---|---|---|---|
| Gravity Conveyor, vertical | 360×640 | 1080×1920 | 60 at 30 fps | 120 in order |
| Orbit Bloom, horizontal | 640×360 | 1920×1080 | 60 at 30 fps | 120 in order |

Both masters used H.264 High, yuv420p, BT.709 limited range and fast start. FFmpeg decoded and compared both repeat cycles with the single sequence. Both promotion calls rejected a wrong angle-board hash before the correct current evidence was supplied. Local headless Chrome composed frames on each side of the join and reached the end at four seconds for both master repeats. This does not establish native app playback, maximum render performance, or platform acceptance.

## Visual review

- **Gravity Conveyor:** the title, three stations, rail tips and plinth stay in the portrait frame across all six encoded checkpoints. Front and reverse show the twin supports and bracket joins; the near upright occludes parts of the collars from the side. The two perpendicular clip views distinguish shell profiles and cores. The seam strip shows no abrupt alignment or lighting change.
- **Orbit Bloom:** the landscape camera uses the left column for type, with the full petal silhouette, stand and plinth on the right. The side view shows the assembly depth but overlaps petal roots. The two orthogonal cuts expose the hub-and-stand relationship; some petals overlap in projection, so the cuts are not a wall-thickness measurement. The seam strip shows no abrupt crop or exposure jump.
- A matched portrait palette comparison produced all four review boards. A cross-orientation comparison correctly refused to treat different framing as a matched revision. The native landscape clips are not crops of the portrait previews.
