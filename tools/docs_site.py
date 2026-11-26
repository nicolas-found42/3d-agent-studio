# /// script
# requires-python = ">=3.11"
# dependencies = ["zensical==0.1.3"]
# ///
"""Build or preview the repository's canonical Markdown with Zensical."""

import argparse
import os
from pathlib import Path
import shutil


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
        *root.glob("docs/assets/*"),
        *root.glob("skills/3d-agent-studio/**/*.md"),
        *root.glob("acceptance/*/acceptance.json"),
        *root.glob("acceptance/*/scene.py"),
        *root.glob("acceptance/*/inputs/CREDITS.txt"),
        *root.glob("acceptance/*/result/*.jpg"),
        *root.glob("acceptance/*/result/*.mp4"),
        *root.glob("acceptance/*/result/*review.json"),
        *root.glob("src/agent_studio/examples/*/scene.py"),
        *root.glob("src/agent_studio/examples/*/review.json"),
    ]
    for path in paths:
        if path.is_file():
            target = source / path.relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)


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
