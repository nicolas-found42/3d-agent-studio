"""Make a poster contact sheet and review each example's three nearest tag matches with Jev.

    uv run --locked python tools/review/diversity.py --output /absolute/scratch/diversity

Use --sheet-only to make the contact sheet and cell key locally.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess

from agent_studio import pipeline

import review

TAG_FIELDS = ('camera', 'lighting', 'style', 'motion')
COMMON_WORDS = set('a an and along as at by for from in into is of on the to up with'.split())
TILE_WIDTH, TILE_HEIGHT, COLUMNS = 256, 172, 6


def nearest(examples):
    """Average token overlap across the four tag fields, with stable slug tiebreaks."""
    tags = {entry['slug']: [set(re.findall(r'[a-z0-9]+', entry['tags'][field].lower())) - COMMON_WORDS
                           for field in TAG_FIELDS]
            for entry in examples}

    def similarity(a, b):
        overlaps = [len(left & right) / max(1, len(left | right)) for left, right in zip(tags[a], tags[b])]
        return sum(overlaps) / len(TAG_FIELDS)

    matches = {}
    for slug in tags:
        peers = sorted(((similarity(slug, other), other) for other in tags if other != slug),
                       key=lambda pair: (-pair[0], pair[1]))
        matches[slug] = [{'slug': other, 'similarity': round(score, 4)} for score, other in peers[:3]]
    return matches


def contact_sheet(ffmpeg, examples, posters, output):
    args = [ffmpeg, '-nostdin', '-v', 'error', '-y']
    filters, cells, labels = [], [], []
    for i, entry in enumerate(examples):
        slug = entry['slug']
        args += ['-i', str(posters[slug])]
        column, row = i % COLUMNS, i // COLUMNS
        cells.append(f'{column * TILE_WIDTH}_{row * TILE_HEIGHT}')
        labels.append(f'| {row + 1} | {column + 1} | `{slug}` | {entry["category"]} |')
        filters.append(f'[{i}:v]scale={TILE_WIDTH - 8}:{TILE_HEIGHT - 8}:force_original_aspect_ratio=decrease,'
                       f'pad={TILE_WIDTH}:{TILE_HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=0x141920,setsar=1[t{i}]')
    if len(examples) == 1:
        filters.append('[t0]null[out]')
    else:
        inputs = ''.join(f'[t{i}]' for i in range(len(examples)))
        filters.append(f'{inputs}xstack=inputs={len(examples)}:layout={"|".join(cells)}:fill=0x141920[out]')
    args += ['-filter_complex_threads', '1', '-filter_complex', ';'.join(filters), '-map', '[out]',
             '-frames:v', '1', '-q:v', '2', '-update', '1', str(output / 'contact-sheet.jpg')]
    subprocess.run(args, check=True)
    (output / 'contact-sheet.md').write_text(
        '# Poster contact sheet\n\n| Row | Column | Example | Category |\n|---|---|---|---|\n' +
        '\n'.join(labels) + '\n', encoding='utf-8')


def disposition(probability):
    grade = review.band(probability)
    return {'yes': 'possible_duplicate', 'unsure': 'review', 'no': 'distinct'}[grade]


def judge(a, b, posters, hashes, cache):
    # Cache each unordered poster pair by image hashes and the exact question for safe retries.
    identity = [review.MODEL, review.DIVERSITY_QUESTION, hashes[a], hashes[b]]
    key = sha256(json.dumps(identity).encode()).hexdigest()
    path = cache / f'{key}.json'
    if path.is_file():
        result = json.loads(path.read_text())
    else:
        state = ['image A:', {'image': posters[a]}, 'image B:', {'image': posters[b]}]
        question = {'same_subject_and_composition': review.noul(*review.DIVERSITY_QUESTION)}
        log = []
        answer = review.call(state, question, log)['same_subject_and_composition']
        probability = answer['noul']
        if type(probability) not in (int, float) or not 0 <= probability <= 1:
            raise ValueError(f'Jev returned an invalid probability ({probability!r}) for {a} and {b}')
        result = {'probability': probability, 'model': log[0]['model'], 'usage': log[0]['usage']}
        pipeline.write(path, result)
    return {'examples': [a, b], 'sha256': [hashes[a], hashes[b]], **result,
            'disposition': disposition(result['probability'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--sheet-only', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    examples = sorted(pipeline.example_index(), key=lambda e: (e['category'], e['slug']))
    if not examples:
        raise SystemExit('Build the example index before running the diversity review.')
    posters = {entry['slug']: pipeline.EXAMPLES / entry['slug'] / 'poster.jpg' for entry in examples}
    contact_sheet(os.environ.get('STUDIO_FFMPEG', 'ffmpeg'), examples, posters, output)
    if args.sheet_only:
        return
    if not os.environ.get('OPENROUTER_API_KEY'):
        raise SystemExit('OPENROUTER_API_KEY is not set.')

    matches = nearest(examples)
    pairs = {tuple(sorted((slug, match['slug']))) for slug, neighbors in matches.items() for match in neighbors}
    tag_counts = {field: dict(Counter(entry['tags'][field] for entry in examples).most_common()) for field in TAG_FIELDS}
    hashes = {slug: pipeline.digest(path) for slug, path in posters.items()}
    cache = output / 'pair-cache'
    cache.mkdir(exist_ok=True)
    results, failures = [], []
    with ThreadPoolExecutor(max_workers=4) as pool:
        pending = {pool.submit(judge, *pair, posters, hashes, cache): pair for pair in pairs}
        for future in as_completed(pending):
            try:
                results.append(future.result())
            except Exception as exc:
                failures.append({'examples': list(pending[future]), 'error': str(exc)})
    pipeline.write(output / 'diversity.json', {
        'model': review.MODEL,
        'neighbor_rule': 'Mean Jaccard token overlap across camera, lighting, style and motion after stopword removal.',
        'nearest': matches, 'tag_counts': tag_counts,
        'pairs': sorted(results, key=lambda result: result['examples']),
        'failures': sorted(failures, key=lambda result: result['examples']),
    })
    print(f'{len(examples)} posters, {len(results)}/{len(pairs)} pairs judged.')
    if failures:
        raise SystemExit(f'Review the {len(failures)} failed pair judgments in diversity.json and rerun to retry them.')


if __name__ == '__main__':
    main()
