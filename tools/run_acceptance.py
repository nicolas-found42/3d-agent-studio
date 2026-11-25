"""Run one acceptance scenario end to end: ingest inputs, probe or draft, Jev review, package.

    uv run --locked python tools/run_acceptance.py SLUG [--probe] [--root JOB_ROOT]

Each scenario lives in acceptance/<slug>/ with scene.py, acceptance.json and inputs/. The
JSON holds the brief (without references), the inputs with roles, the elements the Jev chain
checks, and optionally a comparison image path. Results land in acceptance/<slug>/result/.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JOBS = Path(os.environ.get('STUDIO_OUTPUT_ROOT', Path.home() / '3d-agent-studio-jobs'))


def studio(jobs, *args):
    r = subprocess.run(['uv', 'run', '--locked', '3d-agent-studio', '--output-root', str(jobs), *map(str, args)],
                       cwd=ROOT, capture_output=True, text=True)
    out = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {'error': r.stderr[-2000:]}
    return r.returncode, out


def ffmpeg(*args):
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', *map(str, args)], check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('slug')
    ap.add_argument('--probe', action='store_true', help='Stop after the probe')
    ap.add_argument('--root', type=Path, default=DEFAULT_JOBS)
    a = ap.parse_args()
    folder = ROOT / 'acceptance' / a.slug
    spec = json.loads((folder / 'acceptance.json').read_text())
    refs, diagrams = [], []
    for item in spec.get('inputs', []):
        code, out = studio(a.root, 'ingest', (folder / 'inputs' / item['file']).resolve(), '--role', item['role'],
                           *(['--max-frames', item['max_frames']] if 'max_frames' in item else []))
        if code:
            raise SystemExit(f'ingest failed for {item["file"]}: {out}')
        refs.append({'id': out['id'], 'role': item['role'], 'note': item.get('note', '')})
        if item.get('diagram'):
            diagrams.append(out['id'])
        print('ingested', item['file'], out['id'], out['kind'], out.get('image_references'))
    brief = {**spec['brief'], 'references': refs}
    brief_file = a.root / 'briefs' / f'{a.slug}.json'
    brief_file.parent.mkdir(parents=True, exist_ok=True)
    brief_file.write_text(json.dumps(brief))
    mode = 'probe' if a.probe else 'draft'
    code, out = studio(a.root, mode, f'@{brief_file}', folder / 'scene.py', '--wait')
    job_id = out.get('job_id')
    stage = 'probe' if a.probe else 'preview'
    info = (out.get(stage) or {}) if job_id else {}
    print(json.dumps({'job_id': job_id, 'state': info.get('state'), 'error': (info.get('error') or out.get('error') or '')[-3000:],
                      'warnings': (info.get('checks') or info.get('qc') or {}).get('warnings')}, indent=1))
    if code or info.get('state') != 'ready':
        return 1
    job = a.root / job_id
    review = [sys.executable, str(ROOT / 'tools' / 'review' / 'review.py'), str(job), '--stage', stage,
              '--elements', '; '.join(spec['elements'])] + (['--expect-text'] if spec.get('expect_text') else [])
    for ref in diagrams:
        review += ['--diagram', ref]
    if spec.get('overrides'):
        overrides = a.root / 'briefs' / f'{a.slug}-overrides.json'
        overrides.write_text(json.dumps(spec['overrides']))
        review += ['--overrides', str(overrides)]
    verdict = subprocess.run(review, cwd=ROOT, capture_output=True, text=True)
    print(verdict.stdout[-3000:], verdict.stderr[-1500:])
    result = folder / 'result'
    result.mkdir(exist_ok=True)
    src = job / stage
    if stage == 'probe':
        shutil.copy(src / 'probe.jpg', result / 'probe.jpg')
    else:
        ffmpeg('-i', src / 'cover.png', '-vf', "scale='min(960,iw)':-2", '-q:v', '3', result / 'poster.jpg')
        ffmpeg('-i', src / 'reel.mp4', '-vf', "scale='min(640,iw)':-2", '-c:v', 'libx264', '-crf', '28', '-preset', 'slow',
               '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-an', result / 'clip.mp4')
        for board in ('timeline.jpg', 'angles.jpg', 'references.jpg', 'seam.jpg'):
            if (src / board).is_file():
                shutil.copy(src / board, result / board)
    if spec.get('compare_with'):
        target = result / 'compare.jpg'
        image = src / ('probe.jpg' if stage == 'probe' else 'cover.png')
        ffmpeg('-i', image, '-i', spec['compare_with'], '-filter_complex',
               '[0]scale=-2:540,setsar=1[a];[1]scale=-2:540,setsar=1[b];[a][b]hstack=inputs=2', '-frames:v', '1', target)
    jev = json.loads((src / 'jev-review.json').read_text())
    (result / 'review.json').write_text(json.dumps({'job_id': job_id, 'stage': stage, 'brief': brief,
                                                    'reviewer_notes': spec.get('reviewer_notes', {}),
                                                    'jev': {'decision': jev['decision'], 'quality': jev['findings']['quality'],
                                                            'prompt_match': jev['findings']['prompt_match'],
                                                            'elements': jev['findings']['elements'],
                                                            'defects': jev['findings']['defects'],
                                                            'references': jev['findings']['references']}}, indent=1) + '\n')
    print('packaged', result)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
