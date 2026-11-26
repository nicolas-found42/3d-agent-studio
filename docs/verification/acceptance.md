# Acceptance render evidence

These results use the [six acceptance scenes](../../acceptance/README.md).

## Acceptance master

Fox Asleep promoted from the current draft board hashes and written visual notes. With the one-minute standard budget, the studio refused the estimated 39.65 minutes at 128 samples. The ten-minute fast plan chose 16 samples and predicted 6.49 minutes. The job finished in 6.08 active minutes, about 7% below the estimate. The 1920×1080 master decoded to 96 frames at 24 fps, and the two-cycle file decoded to 192 in order. The worker removed the PNG sequence because `png` was omitted. The master boards passed visual review and Jev flagged three observations for checking, all recorded in the review. [Master clip](../../acceptance/fox-asleep/result/master.mp4) · [Master evidence](../../acceptance/fox-asleep/result/master-review.json)

## Acceptance evidence

Each `result/review.json` records the draft job, frame and timing measurements, Jev answers, and board observations. The Gothic scenario includes a side-by-side still against the Laon benchmark. The Iceland draft passed media checks and demonstrates the reference and model inputs with a stylized result. Its review keeps the original basic quality grade and documents the visual exceptions.

| Scenario | Input | Draft evidence |
|---|---|---|
| Society village | Animated GIF and journal CSV | 288 frames at 640×360, 24 fps. 7.00 min predicted, 5.75 min active. Jev polished with one diagram-layout override. [Boards and notes](../../acceptance/society-village/result/review.json) |
| Gothic nave | Prompt and open material assets | 120 frames at 640×360, 24 fps. 2.87 min predicted, 2.38 min active. Jev polished and exact. [Laon comparison](../../acceptance/gothic-nave/result/compare.jpg) · [Review notes](../../acceptance/gothic-nave/result/review.json) |
| Teapot from photo | One subject photo | 96 frames at 640×360, 24 fps. 1.55 min predicted, 0.92 min active. Jev polished and close to the paired photograph, with a written prompt-match override. [Boards and notes](../../acceptance/teapot-from-photo/result/review.json) |
| Fox asleep | Prompt-only character loop | 96 frames at 640×360, 24 fps. Jev polished. The 1080p master and both loop cycles passed QC. [Draft notes](../../acceptance/fox-asleep/result/review.json) |
| Iceland falls | Two photos and an OBJ import | 120 frames at 640×360, 24 fps. 3.28 min predicted, 2.79 min active. Jev basic, with documented quality and reference exceptions. [Boards and notes](../../acceptance/iceland-falls/result/review.json) |
| Village motives | CSV, SVG, font and shot list | 120 frames at 640×360, 24 fps. 1.58 min predicted, 1.11 min active. Jev polished with a prompt-match override backed by decoded frames and a data check. [Boards and notes](../../acceptance/village-motives/result/review.json) |
