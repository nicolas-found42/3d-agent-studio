# Example library art direction

The contact sheet uses the shipped posters in category and slug order. The individual poster notes link to the scene scripts. The [example library](example-library.md) pairs every script with its draft and review record. Open the [shipped catalog](https://github.com/nicolas-found42/3d-agent-studio/tree/v0.3.0/src/agent_studio/examples) for clips and review receipts.

![Contact sheet of all 36 example posters](assets/example-contact-sheet.jpg)

## Cover revisions

- **Neon Sign Sting** originally reached its automatic cover while the cyan LATE line was still dark. The revised ignition cues preserve letter-by-letter flicker and finish both lines before the one-third-frame cover. The new poster shows the reflection in the foreground puddle. [Review receipt](../src/agent_studio/examples/neon-sign-sting/review.json)
- **Noir Title Card** originally showed a bare wall and blind shadows in its cover. The revised fade starts earlier and the ivory paint is brighter. The opening retains the unlettered wall, and the normal cover contains the legible title inside the projected stripes. [Review receipt](../src/agent_studio/examples/noir-title-card/review.json)

## Library patterns

- Cool navy and cyan recur in Jellyfish Drift, the three micro/macro studies and City Network Pulses. Their distinct silhouettes, panel proportions and viewpoints keep them readable as a tall bell, a raked membrane, a vertical ladder, a centered dendrite and a street map.
- The dark centered shots in Neon Sign Sting, Noir Title Card, Black Hole Accretion and Hangar Door Reveal use legible contrasts in lighting and depth. Neon uses two saturated tubes, Noir projects diagonal hard stripes, the black hole has a luminous circular void, and the hangar holds a small figure in a bright rear doorway.
- Pendulum Wave and Clockwork Gear Train both use brass and a dark field. The pendulum shows the full diagonal machine from above. The macro gear shot places the viewer level with the teeth. Dutch Still Life uses similar warm highlights on reflective metal in a tighter tabletop arrangement.
- Paper City Isometric, Market Town Agents and Breakfast Flatlay use high views that emphasize position. The pastel city has an isolated isometric footprint, the village has a raked central plaza with full-scale perspective cues, and the flat lay organizes food and linens directly overhead.
- The three architectural examples use a centered nave, an upward view of a façade, and an isolated isometric city. Their warm stone haze, hard concrete shadows, and light pastel materials maintain distinct lighting and framing.

Twelve categories contain three scenes each. The library contains 12 horizontal, seven square, six vertical, six ultrawide and five portrait scenes. Lighting and style strings are unique across the set. Camera and motion have 35 unique strings each. Noir Title Card and Perfume Bottle Light share “slow push-in”. Gothic Nave Dawn and Brutalist Courtyard Noon share “camera only”.

## Jev similarity

Jev reviewed all 78 unique pairs from 108 directed neighbor links. Every pair stayed in the distinct band, with a maximum probability of 0.02 of sharing both a subject and shot composition. All 36 posters were inspected visually at gallery size.

The three nearest neighbors are ranked by mean token overlap across the camera, lighting, style and motion tags. Each pair is judged on subject **and** composition together. The tool records the original probability and a code-derived band for every pair. [Diversity tool](../tools/review/diversity.py)

```sh
uv run --locked python tools/build_example_index.py
uv run --locked python tools/review/diversity.py --output /absolute/scratch/diversity
```

## Individual posters

- [Places and environments](library-review/places.md) · Architecture, Landscape, Space, Still life
- [Motion and characters](library-review/motion.md) · Abstract, Character, Mechanical, Physics
- [Data, products, and fine detail](library-review/detail.md) · Data, Micro/macro, Product, Typography
