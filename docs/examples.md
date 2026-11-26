# Rendered examples

Explore four drafts, from a prompt-only character loop to a reference photo and a data exhibit. Each includes the brief, scene script, and a review board.

<section class="studio-case" markdown="1">

## Gothic Nave

<div class="studio-case__media" markdown="1">

[![A long nave with pointed arches, a central aisle, and amber light](../acceptance/gothic-nave/result/poster.jpg)](../acceptance/gothic-nave/result/clip.mp4)

</div>

<div class="studio-case__copy" markdown="1">

Warm daylight travels across the stone aisle as the camera moves through pointed arches. The scene uses a prompt and open-licensed materials.

> The camera dollies east past clustered limestone piers, pointed arcades, a recessed triforium and ribbed vaults.

[MP4 clip](../acceptance/gothic-nave/result/clip.mp4) · [Scenario and brief](../acceptance/gothic-nave/acceptance.json) · [Scene script](../acceptance/gothic-nave/scene.py) · [Timeline](../acceptance/gothic-nave/result/timeline.jpg)

</div>
</section>

<section class="studio-case" markdown="1">

## Fox Asleep

<div class="studio-case__media" markdown="1">

[![An orange fox curled up in the snow](../acceptance/fox-asleep/result/poster.jpg)](../acceptance/fox-asleep/result/clip.mp4)

</div>

<div class="studio-case__copy" markdown="1">

A fox breathes while snow falls around it. The four-second loop was also rendered as a 1080p master and checked over two cycles.

> The flank rises gently with each breath while snow falls in a seamless loop.

[MP4 clip](../acceptance/fox-asleep/result/clip.mp4) · [Scenario and brief](../acceptance/fox-asleep/acceptance.json) · [Scene script](../acceptance/fox-asleep/scene.py) · [Loop seam](../acceptance/fox-asleep/result/seam.jpg)

</div>
</section>

<section class="studio-case" markdown="1">

## Teapot from Photo

<div class="studio-case__media" markdown="1">

[![A dark glazed teapot with red trim on a studio table](../acceptance/teapot-from-photo/result/poster.jpg)](../acceptance/teapot-from-photo/result/clip.mp4)

</div>

<div class="studio-case__copy" markdown="1">

One subject photo guides the charcoal glaze, red trim, and rounded silhouette. The reference board pairs the photo with the closest render frame.

> A slow rightward slide reveals the curve of the handle and keeps the entire silhouette in view.

[MP4 clip](../acceptance/teapot-from-photo/result/clip.mp4) · [Scenario and brief](../acceptance/teapot-from-photo/acceptance.json) · [Scene script](../acceptance/teapot-from-photo/scene.py) · [Reference board](../acceptance/teapot-from-photo/result/references.jpg) · [Photo credit](../acceptance/teapot-from-photo/inputs/CREDITS.txt)

</div>
</section>

<section class="studio-case" markdown="1">

## Village Motives

<div class="studio-case__media" markdown="1">

[![A dimensional area chart inside an illuminated exhibit case](../acceptance/village-motives/result/poster.jpg)](../acceptance/village-motives/result/clip.mp4)

</div>

<div class="studio-case__copy" markdown="1">

A physical chart builds from 90 days of simulation data. The scene also uses an SVG emblem, a font, and a shot list.

> Six colored bands follow the daily action counts in the CSV.

[MP4 clip](../acceptance/village-motives/result/clip.mp4) · [Scenario and brief](../acceptance/village-motives/acceptance.json) · [Scene script](../acceptance/village-motives/scene.py) · [Timeline](../acceptance/village-motives/result/timeline.jpg)

</div>
</section>

On GitHub, open an MP4 link and choose **View raw** or **Download raw file**.

## Browse all 36 scenes

Studio ships 36 examples across 12 categories, each with a scene script, poster, and clip. Search by subject or category from a checkout, or ask your agent to call `studio_examples`.

```sh
uv run --locked 3d-agent-studio examples --tag character --limit 3 --script
```

The CLI prints JSON with the scene source and local media paths. Browse the [full poster contact sheet](example-library-review.md) or open the [shipped example files](https://github.com/nicolas-found42/3d-agent-studio/tree/v0.3.0/src/agent_studio/examples). See the [six acceptance scenarios](../acceptance/README.md) for a full set of input types.
