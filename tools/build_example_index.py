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


def entry(meta):
    folder = meta.parent
    info = pipeline.read(meta)
    if set(info) != set(FIELDS):
        raise ValueError(f'expected exactly these metadata fields: {", ".join(FIELDS)}')
    if info['slug'] != folder.name or info['category'] not in CATEGORIES or set(info['tags']) != set(TAGS):
        raise ValueError('slug, category or tags invalid')
    if not all(isinstance(t, str) and t.strip() for t in info['tags'].values()):
        raise ValueError('tags must be nonempty text')
    techniques = info['techniques']
    if not isinstance(techniques, list) or not 3 <= len(techniques) <= 8 or not all(isinstance(t, str) and t.strip() for t in techniques):
        raise ValueError('provide three to eight techniques')
    brief = pipeline.validate_brief(info['brief'])
    if brief['prompt'] != info['prompt'] or brief['references']:
        raise ValueError('the prompt must match the brief and the example must be self-contained')
    absent = [f for f in ('scene.py', 'poster.jpg', 'clip.mp4', 'review.json') if not (folder / f).is_file()]
    if absent:
        raise ValueError(f'missing {", ".join(absent)}')
    if problems := scriptcheck.check((folder / 'scene.py').read_text(encoding='utf-8')):
        raise ValueError(f'script check: {problems[0]}')
    if not 0 < (folder / 'clip.mp4').stat().st_size < 1_500_000:
        raise ValueError('the draft clip must be nonempty and under 1.5 MB')
    review = pipeline.read(folder / 'review.json')
    judgment = review['jev']
    decision = judgment.get('decision', judgment)
    if decision['verdict'] not in ('pass', 'look') or decision.get('fix') or judgment['quality'] not in ('polished', 'cinematic'):
        raise ValueError('publish a polished or cinematic draft with any Jev fixes resolved')
    required = ('timeline', 'angles', 'seam') if brief['loop'] else ('timeline', 'angles')
    if not all(isinstance(review['notes'].get(k), str) and review['notes'][k].strip() for k in required):
        raise ValueError(f'missing visual notes for boards: {", ".join(required)}')
    return {k: info[k] for k in FIELDS}


def main():
    entries, problems = [], []
    for meta in sorted(pipeline.EXAMPLES.glob('*/example.json')):
        try:
            entries.append(entry(meta))
        except (OSError, ValueError, TypeError, KeyError) as exc:
            problems.append(f'{meta.parent.name}: {exc}')
    (pipeline.EXAMPLES / 'index.json').write_text(json.dumps(entries, indent=1) + '\n')
    print(f'{len(entries)} examples indexed')
    for p in problems:
        print('PROBLEM', p)
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main())
