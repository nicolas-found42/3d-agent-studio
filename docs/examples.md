# Rendered examples

Open an example for its draft, brief, scene script, and review board.

<div class="studio-samples studio-gallery-index" markdown="1">

<div class="studio-sample" markdown="1">

## [Gothic Nave](examples/gothic-nave.md)

[![A long nave with pointed arches, a central aisle, and amber light](../acceptance/gothic-nave/result/poster.jpg)](examples/gothic-nave.md)

Warm daylight travels across the stone aisle as the camera moves through pointed arches. The scene uses a prompt and open-licensed materials.

</div>

<div class="studio-sample" markdown="1">

## [Fox Asleep](examples/fox-asleep.md)

[![An orange fox curled up in the snow](../acceptance/fox-asleep/result/poster.jpg)](examples/fox-asleep.md)

A fox breathes while snow falls around it. The four-second loop was also rendered as a 1080p master and checked over two cycles.

</div>

<div class="studio-sample" markdown="1">

## [Teapot from Photo](examples/teapot-from-photo.md)

[![A dark glazed teapot with red trim on a studio table](../acceptance/teapot-from-photo/result/poster.jpg)](examples/teapot-from-photo.md)

One subject photo guides the charcoal glaze, red trim, and rounded silhouette. The reference board pairs the photo with the closest render frame.

</div>

<div class="studio-sample" markdown="1">

## [Village Motives](examples/village-motives.md)

[![A dimensional area chart inside an illuminated exhibit case](../acceptance/village-motives/result/poster.jpg)](examples/village-motives.md)

A physical chart builds from 90 days of simulation data. The scene also uses an SVG emblem, a font, and a shot list.

</div>

</div>

## Browse all 36 scenes

Studio ships 36 examples across 12 categories, each with a scene script, poster, and clip. Search by subject or category from a checkout, or ask your agent to call `studio_examples`.

```sh
uv run --locked 3d-agent-studio examples --tag character --limit 3 --script
```

The CLI prints JSON with the scene source and local media paths. Browse the [full poster contact sheet](example-library-review.md) or open the [shipped example files](https://github.com/nicolas-found42/3d-agent-studio/tree/v0.3.0/src/agent_studio/examples). See the [six acceptance scenarios](../acceptance/README.md) for a full set of input types.
