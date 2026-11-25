"""Dev-only chained Jev review of a studio draft (not part of the installed package).

Jev answers narrow visual judgments; this file's code turns them into a verdict.

    uv run --locked python tools/review/review.py JOB_DIR --elements "a lighthouse; crashing waves" \
        [--stage preview] [--expect-text] [--out review.json]

Needs OPENROUTER_API_KEY in the environment. Uses the pinned model typesafe/jev-1.14 and the
OpenRouter Decisions API. Request payloads (with image paths instead of image bytes) are written
next to the verdict so any answer can be replayed.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.request

MODEL = 'typesafe/jev-1.14'
ENDPOINT = 'https://openrouter.ai/api/alpha/decisions'
YES, NO = 0.7, 0.3
# Asked in every review; a yes means the board did not settle what is visible, so a person looks.
CONTROL = 'a giraffe'

# --- Question wording lives here, in one place. ---------------------------------------------
BOARD_INTRO = {
    'timeline.jpg': 'Six frames from an animated 3D render, in time order left-to-right then top-to-bottom.',
    'angles.jpg': 'Three review views of the same 3D scene: a wider lens from the shot camera, a three-quarter view '
                  'of the whole set, and a top-down overview where a pink line is the camera path.',
    'probe.jpg': 'The first, middle and last frame of an animated 3D render, left to right.',
}
DEFECTS = {
    'floating': ('Does any object in `frames` float in the air when it should rest on a surface?',
                 'An object that should be grounded hangs visibly above the floor or its support.',
                 'Every object meant to rest on something touches it, or is meant to fly.'),
    'interpenetration': ('Do solid objects in `frames` visibly pass through each other?',
                         'Two solid objects overlap in a way real objects could not.',
                         'Objects meet at contacts without passing through one another.'),
    'too_dark': ('Is any frame in `frames` so dark that the subject cannot be made out?',
                 'Most of a frame is near black and the main subject is hard to see.',
                 'The subject is visible in every frame, even if the mood is dark.'),
    'blown_out': ('Is any frame in `frames` washed out, with large areas of flat white?',
                  'Large parts of a frame are clipped to white and lose detail.',
                  'Highlights keep detail; bright areas are small or intended.'),
    'noisy': ('Do the frames in `frames` show grain, blotches or smeared denoising artifacts?',
              'Visible speckle, blotchy patches or waxy smearing on surfaces.',
              'Surfaces look clean and consistent.'),
    'clipping': ('Does the camera in `frames` cut through geometry, with walls or objects sliced open near the lens?',
                 'Part of the frame shows the inside of an object or a wall cut open by the camera.',
                 'Nothing is sliced by the camera.'),
    'placeholder': ('Do the frames in `frames` look like an unfinished blockout made of plain untextured primitives?',
                    'Mostly default-looking boxes, spheres or cylinders with flat uniform materials and no detail.',
                    'Objects have designed shapes, materials and detail.'),
    'empty': ('Is the main subject too small or lost in empty space in `frames`?',
              'The subject occupies a small part of the frame surrounded by empty floor or sky.',
              'The subject fills a deliberate part of the frame.'),
}
QUALITY_LEVELS = {
    'blockout': 'A rough blockout: plain primitives, flat lighting, no material detail.',
    'basic': 'A simple but complete scene: recognisable objects, basic materials and lighting.',
    'polished': 'A polished render: considered composition, lighting with depth, convincing materials.',
    'cinematic': 'A cinematic, professional render: striking composition, rich light, fine detail throughout.',
}
MATCH_LEVELS = {
    'unrelated': 'The frames show something unrelated to the description.',
    'loose': 'Some elements of the description appear, but the main idea is missing or wrong.',
    'clear': 'The frames clearly show what the description asks for.',
    'exact': 'The frames show the description closely, including its mood and details.',
}
REFERENCE_LEVELS = {
    'unrelated': 'The render has nothing visible in common with the reference.',
    'related': 'The render shares a few traits with the reference.',
    'clearly_related': 'A viewer would see the reference in the render.',
    'close': 'The render closely matches the reference in this respect.',
}
ROLE_QUESTION = {
    'subject': 'How closely does the subject in `render` resemble the subject of `reference`?',
    'style': 'How closely does the visual style of `render` (rendering look, materials, color, light) match `reference`?',
    'composition': 'How closely does the framing and layout of `render` match `reference`?',
    'palette': 'How closely do the colors of `render` match the palette of `reference`?',
    'storyboard': 'How closely does `render` match the shot drawn in `reference`?',
    'motion': 'How closely does the subject in `render` resemble the subject of `reference`?',
}


def image_part(path):
    """JPEG within Jev's limits (280-1568 px per side); sources outside them are fitted, never stretched."""
    fit = ("scale='min(iw,1560)':'min(ih,1560)':force_original_aspect_ratio=decrease,"
           "pad='max(iw,280)':'max(ih,280)':(ow-iw)/2:(oh-ih)/2:color=0x141920")
    r = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(path), '-vf', fit, '-frames:v', '1',
                        '-q:v', '3', '-f', 'image2', '-c:v', 'mjpeg', 'pipe:1'], capture_output=True, check=True)
    data = base64.b64encode(r.stdout).decode()
    return {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{data}'}}


def call(state, questions, log):
    """POST one Decisions request; keep a replayable copy with image paths in place of bytes."""
    key = os.environ.get('OPENROUTER_API_KEY')
    if not key:
        raise SystemExit('OPENROUTER_API_KEY is not set')
    wire = [image_part(p['image']) if isinstance(p, dict) else p for p in state]
    body = json.dumps({'model': MODEL, 'state': wire, 'questions': questions}).encode()
    req = urllib.request.Request(ENDPOINT, body, {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json',
                                                  'TypeSafe-Danger-Zone-Images': 'true'})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            out = json.loads(r.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'Jev request failed ({exc.code}): {exc.read()[:500]!r}') from exc
    model = out.get('model', '')
    if not model.startswith(('jev-1.14', 'typesafe/jev-1.14')):
        raise RuntimeError(f'Unexpected model in response: {model!r}')
    missing = set(questions) - set(out.get('answers', {}))
    if missing:
        raise RuntimeError(f'Jev returned no answer for {sorted(missing)}')
    log.append({'state': state, 'questions': questions, 'model': model, 'answers': out['answers'],
                'usage': out.get('usage')})
    return out['answers']


def noul(instructions, true=None, false=None):
    q = {'type': 'noul', 'instructions': instructions}
    if true:
        q['criteria'] = {'true': true, 'false': false}
    return q


def score(instructions, levels):
    """Levels are named in code; Jev sees only the ordered descriptions."""
    return {'type': 'score', 'instructions': instructions, 'criteria': list(levels.values())}


def level(answer, levels):
    """Index of the most probable level (the score position can hide two-peaked answers)."""
    probs = answer.get('probabilities')
    if isinstance(probs, list) and probs:
        return max(range(len(probs)), key=probs.__getitem__)
    if isinstance(probs, dict) and probs:
        best = max(probs, key=probs.get)
        descriptions = list(levels.values())
        return int(best) if str(best).isdigit() else descriptions.index(best) if best in descriptions else list(levels).index(best)
    return round(answer['score'])


def band(p):
    return 'yes' if p > YES else 'no' if p < NO else 'unsure'


def review(job, stage, prompt, elements, expect_text=False):
    stage_dir = job / stage
    log = []
    findings = {'elements': {}, 'defects': {}, 'quality': None, 'prompt_match': None, 'references': []}
    boards = ['probe.jpg'] if stage == 'probe' else ['timeline.jpg', 'angles.jpg']
    main = boards[0]
    # Request 1: everything asked of the main board shares one state.
    questions = {f'el{i}': noul(f'Is {e} visible in `frames`?') for i, e in enumerate(elements)}
    questions['control'] = noul(f'Is {CONTROL} visible in `frames`?')
    for key, (q, t, f) in DEFECTS.items():
        questions[f'defect_{key}'] = noul(q, t, f)
    if expect_text:
        questions['text_readable'] = noul('Is the text shown in `frames` legible?')
    questions['quality'] = score('How finished and professional do the renders in `frames` look?', QUALITY_LEVELS)
    questions['prompt_match'] = score('How well do `frames` show what `description` asks for?', MATCH_LEVELS)
    state = [f'description: {prompt}', f'frames: {BOARD_INTRO[main]}', {'image': stage_dir / main}]
    answers = call(state, questions, log)
    for i, e in enumerate(elements):
        findings['elements'][e] = answers[f'el{i}']['noul']
    for key in DEFECTS:
        findings['defects'][key] = answers[f'defect_{key}']['noul']
    findings['control'] = answers['control']['noul']
    if expect_text:
        findings['text_readable'] = answers['text_readable']['noul']
    findings['quality'] = list(QUALITY_LEVELS)[level(answers['quality'], QUALITY_LEVELS)]
    findings['quality_probabilities'] = answers['quality'].get('probabilities')
    findings['prompt_match'] = list(MATCH_LEVELS)[level(answers['prompt_match'], MATCH_LEVELS)]
    # Request 2: the angles board, only for set completeness (cheap, separate image).
    if stage != 'probe':
        a = call(['frames: ' + BOARD_INTRO['angles.jpg'], {'image': stage_dir / 'angles.jpg'}],
                 {'set_unfinished': noul('In the three-quarter view in `frames`, does the scene look like a thin '
                                         'facade with obviously missing or unfinished parts?')}, log)
        findings['defects']['set_unfinished'] = a['set_unfinished']['noul']
    # Request 3+: one request per reference pair (each needs its own two images).
    pairs_file = stage_dir / 'pairs.json'
    pairs = json.loads(pairs_file.read_text()) if pairs_file.is_file() else []
    for pr in pairs[:8]:
        ans = call(['reference:', {'image': pr['reference_path']}, 'render:', {'image': pr['frame_path']}],
                   {'match': score(ROLE_QUESTION[pr['role']], REFERENCE_LEVELS)}, log)
        findings['references'].append({'reference': pr['reference'], 'role': pr['role'], 'frame': Path(pr['frame_path']).name,
                                       'level': list(REFERENCE_LEVELS)[level(ans['match'], REFERENCE_LEVELS)]})
    return decide(findings), findings, log


def decide(f):
    """The truth table: code, not Jev, decides pass, fix or look."""
    fixes, looks = [], []
    for e, p in f['elements'].items():
        (looks if band(p) == 'unsure' else fixes if band(p) == 'no' else []).append(f'element: {e} ({p:.2f})')
    for d, p in f['defects'].items():
        (looks if band(p) == 'unsure' else fixes if band(p) == 'yes' else []).append(f'defect: {d} ({p:.2f})')
    if f.get('text_readable') is not None and band(f['text_readable']) != 'yes':
        (fixes if band(f['text_readable']) == 'no' else looks).append(f'text legibility ({f["text_readable"]:.2f})')
    if f['quality'] in ('blockout', 'basic'):
        fixes.append(f'quality: {f["quality"]}')
    if f['prompt_match'] in ('unrelated', 'loose'):
        fixes.append(f'prompt match: {f["prompt_match"]}')
    for r in f['references']:
        if r['level'] in ('unrelated', 'related'):
            fixes.append(f'reference {r["reference"]} ({r["role"]}): {r["level"]}')
    if f['control'] >= NO:
        looks.append(f'control: "{CONTROL}" answered {f["control"]:.2f}; element answers are unreliable on this board')
    verdict = 'fix' if fixes else 'look' if looks else 'pass'
    return {'verdict': verdict, 'fix': fixes, 'look': looks}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('job', type=Path)
    ap.add_argument('--stage', default='preview', choices=['probe', 'preview', 'master'])
    ap.add_argument('--elements', required=True, help='Semicolon-separated visible elements the prompt requires')
    ap.add_argument('--prompt', help='Defaults to the job brief prompt')
    ap.add_argument('--expect-text', action='store_true')
    ap.add_argument('--out', type=Path)
    a = ap.parse_args()
    job = a.job.resolve()
    prompt = a.prompt or json.loads((job / 'job.json').read_text())['brief']['prompt']
    elements = [e.strip() for e in a.elements.split(';') if e.strip()]
    decision, findings, log = review(job, a.stage, prompt, elements, a.expect_text)
    out = a.out or (job / a.stage / 'jev-review.json')
    out.write_text(json.dumps({'model': MODEL, 'decision': decision, 'findings': findings,
                               'requests': json.loads(json.dumps(log, default=str))}, indent=2))
    cost = sum((r.get('usage') or {}).get('cost', 0) for r in log)
    print(json.dumps({'decision': decision, 'quality': findings['quality'], 'prompt_match': findings['prompt_match'],
                      'elements': findings['elements'], 'defects': {k: round(v, 2) for k, v in findings['defects'].items()},
                      'control': round(findings['control'], 2), 'references': findings['references'], 'requests': len(log),
                      'cost_usd': round(cost, 6), 'saved': str(out)}, indent=1))
    return 0 if decision['verdict'] == 'pass' else 2 if decision['verdict'] == 'look' else 1


if __name__ == '__main__':
    sys.exit(main())
