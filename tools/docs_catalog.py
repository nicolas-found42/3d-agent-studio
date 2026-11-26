"""Build the public example library from the shipped scene index."""

from collections import defaultdict
import json
from pathlib import Path
from posixpath import relpath
import re
import shutil


EXAMPLES = Path("src/agent_studio/examples")
LIBRARY = Path("docs/example-library.md")
EXAMPLE_FILES = ("poster.jpg", "clip.mp4", "scene.py", "example.json", "review.json")


def relative_link(page: Path, target: Path) -> str:
    return relpath(target.as_posix(), page.parent.as_posix())


def card(title: str, target: str, poster: str, alt: str, description: str) -> str:
    return f"""<div class="studio-sample" markdown="1">

## [{title}]({target})

[![{alt}]({poster})]({target})

{description}

</div>"""


def grid(cards: list[str], *, overview: bool = False) -> str:
    classes = "studio-samples studio-library"
    if overview:
        classes += " studio-library-index"
    contents = "\n\n".join(cards)
    return f'<div class="{classes}" markdown="1">\n\n{contents}\n\n</div>'


def write_example(source: Path, page: Path, category_page: Path, category_title: str, example: dict) -> None:
    title = example["title"]
    folder = EXAMPLES / example["slug"]
    links = {name: relative_link(page, folder / name) for name in EXAMPLE_FILES}
    brief = example["brief"]
    settings = [
        f"{brief[key]}{suffix}"
        for key, suffix in (("orientation", ""), ("seconds", " seconds"), ("fps", " fps"))
        if key in brief
    ]
    if brief.get("loop"):
        settings.append("loop")
    settings_line = " · ".join(settings).capitalize()
    techniques = "\n".join(f"- {technique}" for technique in example["techniques"])
    (source / page).write_text(
        f"""[Example library]({relative_link(page, LIBRARY)}) › [{category_title}]({relative_link(page, category_page)})

# {title}

{example["description"]}

{settings_line}

<div class="studio-case__media" markdown="1">

[![Draft poster for {title}]({links["poster.jpg"]})]({links["clip.mp4"]})

</div>

## Prompt

{example["prompt"]}

## Techniques

{techniques}

## Scene and review

[MP4 clip]({links["clip.mp4"]}) · [Scene script]({links["scene.py"]}) · [Brief and metadata]({links["example.json"]}) · [Review record]({links["review.json"]})

[Back to the category]({relative_link(page, category_page)})
""",
        encoding="utf-8",
    )


def stage_catalog(root: Path, source: Path) -> None:
    index = root / EXAMPLES / "index.json"
    examples = json.loads(index.read_text(encoding="utf-8"))
    categories = defaultdict(list)
    seen = set()
    for example in examples:
        category, slug = example["category"], example["slug"]
        if not all(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value) for value in (category, slug)):
            raise ValueError(f"Invalid example category or slug: {category}/{slug}")
        if slug in seen:
            raise ValueError(f"Duplicate example slug: {slug}")
        seen.add(slug)
        categories[category].append(example)

    (source / EXAMPLES).mkdir(parents=True, exist_ok=True)
    shutil.copyfile(index, source / EXAMPLES / index.name)
    library_cards = []
    for category, members in sorted(categories.items()):
        category_title = "Micro/macro" if category == "micro-macro" else category.replace("-", " ").capitalize()
        category_page = LIBRARY.with_suffix("") / f"{category}.md"
        (source / category_page.with_suffix("")).mkdir(parents=True, exist_ok=True)
        category_cards = []
        for example in members:
            slug, title = example["slug"], example["title"]
            folder = EXAMPLES / slug
            (source / folder).mkdir(parents=True, exist_ok=True)
            for name in EXAMPLE_FILES:
                shutil.copyfile(root / folder / name, source / folder / name)
            page = category_page.with_suffix("") / f"{slug}.md"
            write_example(source, page, category_page, category_title, example)
            category_cards.append(card(
                title, relative_link(category_page, page),
                relative_link(category_page, folder / "poster.jpg"),
                f"Draft poster for {title}", example["description"],
            ))
        (source / category_page).write_text(
            f"# {category_title}\n\n[All example categories]({relative_link(category_page, LIBRARY)})\n\n"
            f"{grid(category_cards)}\n",
            encoding="utf-8",
        )
        cover = members[0]
        library_cards.append(card(
            category_title, relative_link(LIBRARY, category_page),
            relative_link(LIBRARY, EXAMPLES / cover["slug"] / "poster.jpg"),
            f"Draft poster for {cover['title']}", f"{len(members)} scenes",
        ))

    intro = (source / LIBRARY).read_text(encoding="utf-8").rstrip()
    (source / LIBRARY).write_text(
        f"{intro}\n\n**{len(examples)} shipped scenes across {len(categories)} categories**\n\n"
        f"{grid(library_cards, overview=True)}\n",
        encoding="utf-8",
    )
