"""Rebuild src/agent_studio/examples/index.json from each examples/<slug>/example.json.

Run: uv run --locked python tools/build_example_index.py
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from agent_studio import pipeline, scriptcheck  # noqa: E402

FIELDS = ('slug', 'title', 'category', 'prompt', 'description', 'brief', 'tags', 'techniques')
CATEGORIES = ('architecture', 'landscape', 'product', 'character', 'abstract', 'data', 'mechanical', 'physics',
              'typography', 'still-life', 'micro-macro', 'space')
TAGS = ('camera', 'lighting', 'style', 'motion')


def main():
    entries, problems = [], []
    for meta in sorted(pipeline.EXAMPLES.glob('*/example.json')):
        folder = meta.parent
        e = json.loads(meta.read_text())
        missing = [f for f in FIELDS if f not in e]
        if missing:
            problems.append(f'{folder.name}: missing {missing}')
            continue
        if e['slug'] != folder.name or e['category'] not in CATEGORIES or set(TAGS) - set(e['tags']):
            problems.append(f'{folder.name}: slug, category or tags invalid')
        if scriptcheck.check((folder / 'scene.py').read_text()):
            problems.append(f'{folder.name}: scene.py fails the script check')
        pipeline.validate_brief(e['brief'])
        absent = [f for f in ('poster.jpg', 'clip.mp4', 'review.json') if not (folder / f).is_file()]
        if absent:
            problems.append(f'{folder.name}: not indexed, missing {absent}')
            continue
        entries.append({k: e[k] for k in FIELDS})
    (pipeline.EXAMPLES / 'index.json').write_text(json.dumps(entries, indent=1) + '\n')
    print(f'{len(entries)} examples indexed')
    for p in problems:
        print('PROBLEM', p)
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main())
