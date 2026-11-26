# /// script
# requires-python = ">=3.11"
# dependencies = ["zensical==0.1.3"]
# ///
"""Build or preview the repository's canonical Markdown with Zensical."""

import argparse
import os
from pathlib import Path
import re
import shutil

from markdown.extensions.toc import slugify

from docs_catalog import stage_catalog


SKILL_DIRECTORY = Path("skills/3d-agent-studio")
REFERENCE_TOPICS = {
    SKILL_DIRECTORY / "references/operations.md": (
        ("commands", "CLI and MCP tools", "Commands and MCP tools"),
        ("inputs", "Briefs and references", "Brief"),
        ("assets", "Asset sources", "Assets"),
        ("rendering", "Render stages and review evidence", "Stages and evidence"),
    ),
    SKILL_DIRECTORY / "references/kit.md": (
        ("basics", "Scene kit basics", "Module helpers"),
        ("motion", "Time and animation", "Time"),
        ("materials", "Collections and materials", "Collections"),
        ("modeling", "Geometry and modifiers", "Geometry"),
        ("lighting-and-camera", "Lights, world, and camera", "Lights & world"),
        ("inputs-and-figures", "Imports and figures", "Imports"),
        ("physics-and-rendering", "Physics, render settings, and utilities", "Physics"),
    ),
    SKILL_DIRECTORY / "SKILL.md": (
        ("prepare", "Understand, design, and render a draft", "1. Understand the request"),
        ("review", "Review, revise, and deliver", "4. Review honestly"),
    ),
}


def stage_reference(path: Path, target: Path, topics: tuple[tuple[str, str, str], ...]) -> None:
    # Keep the bundled reference intact. Only the Pages build changes its reading layout.
    introduction, *sections = re.split(r"(?m)(?=^## )", path.read_text())
    headings = [section.splitlines()[0][3:] for section in sections]
    boundaries = [headings.index(first_heading) for _, _, first_heading in topics]
    if boundaries[0] != 0 or boundaries != sorted(set(boundaries)):
        raise ValueError(f"Topic boundaries are out of order in {path}")
    boundaries.append(len(sections))

    children = target.with_suffix("")
    children.mkdir(parents=True, exist_ok=True)
    overview = [introduction.strip()]
    for (slug, title, _), start, end in zip(topics, boundaries, boundaries[1:]):
        body = "".join(sections[start:end]).strip()
        page = f"{slug}.md"
        (children / page).write_text(
            f"# {title}\n\n[Back to the overview](../{target.name})\n\n{body}\n"
        )
        relative = f"{children.name}/{page}"
        overview.append(f"**[{title}]({relative})**")
        # Preserve the old full-page fragments as links to their new destinations.
        links = []
        for heading in re.findall(r"(?m)^#{2,3} (.+)$", body):
            anchor = slugify(heading.replace("`", ""), "-")
            links.append(f"- [{heading}]({relative}#{anchor}){{ #{anchor} }}")
        overview.append("\n".join(links))
    target.write_text("\n\n".join(overview) + "\n")


def stage_sources(root: Path) -> None:
    source = root / "build/docs-source"
    if source.exists():
        shutil.rmtree(source)

    paths = [
        root / "index.md",
        root / "LICENSE",
        root / "mcp.json",
        root / "acceptance/README.md",
        root / "tools/review/diversity.py",
        *root.glob("docs/*.md"),
        *(
            page
            for folder in ("install", "examples", "verification", "library-review")
            for page in (root / "docs" / folder).glob("*.md")
        ),
        *root.glob("docs/assets/*"),
        *root.glob("skills/3d-agent-studio/**/*.md"),
        *root.glob("acceptance/*/acceptance.json"),
        *root.glob("acceptance/*/scene.py"),
        *root.glob("acceptance/*/inputs/CREDITS.txt"),
        *root.glob("acceptance/*/result/*.jpg"),
        *root.glob("acceptance/*/result/*.mp4"),
        *root.glob("acceptance/*/result/*review.json"),
    ]
    for path in paths:
        if path.is_file():
            relative = path.relative_to(root)
            target = source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if relative in REFERENCE_TOPICS:
                stage_reference(path, target, REFERENCE_TOPICS[relative])
            else:
                shutil.copyfile(path, target)
    stage_catalog(root, source)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("build", "serve"))
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    stage_sources(root)
    command = ["zensical", args.mode]
    if args.mode == "build":
        command.extend(("--clean", "--strict"))
    os.chdir(root)
    os.execvp(command[0], command)


if __name__ == "__main__":
    main()
