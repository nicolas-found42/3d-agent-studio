"""Probe, draft, and package a visually reviewed acceptance scenario.

Run `SLUG --probe`, then `SLUG --job JOB_ID` after inspecting the probe. Open
all draft boards and the clip, record reviewer_notes (and any overrides) in
acceptance.json, then run `SLUG --job JOB_ID --package`. Pass --root each time.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from agent_studio import ingest, pipeline
from agent_studio.cli import wait
from review import review

ROOT = Path(__file__).resolve().parents[1]


def scenario_brief(root, folder, spec, parent):
    references, diagrams = [], set()
    for item in spec.get('inputs', []):
        ref = ingest.ingest(root, str((folder / 'inputs' / item['file']).resolve()),
                            item['role'], item.get('max_frames', ingest.DEFAULT_MAX_FRAMES))
        references.append({'id': ref['id'], 'role': item['role'], 'note': item.get('note', '')})
        if item.get('diagram'):
            diagrams.add(ref['id'])
        print(f'Ingested {item["file"]} as {ref["kind"]} ({ref["id"]})', flush=True)
    return pipeline.validate_brief({**spec['brief'], 'references': references, 'parent': parent}), diagrams


def ffmpeg(*args):
    subprocess.run([pipeline.executables()['ffmpeg'], '-nostdin', '-v', 'error', '-y', *map(str, args)], check=True)


def package(folder, spec, job, out, evidence):
    result = folder / 'result'
    boards = out['preview']['review_hashes']
    notes = spec.get('reviewer_notes', {})
    required = {'probe', 'clip', *(Path(name).stem for name in boards)}
    if spec.get('compare_with'):
        required.add('compare')
    missing = sorted(k for k in required if not isinstance(notes.get(k), str) or not notes[k].strip())
    if missing:
        raise ValueError(f'Add visual reviewer_notes for: {", ".join(missing)}')
    findings = evidence['findings']
    decision = review.decide(findings, overrides=spec.get('overrides', ()))
    if decision['verdict'] == 'fix':
        raise ValueError(f'Revise or record a reason for each fix: {decision["fix"]}')
    src = job / 'preview'
    with TemporaryDirectory(prefix='.result-', dir=folder) as temp:
        staged = Path(temp)
        ffmpeg('-i', src / 'cover.png', '-vf', "scale='min(960,iw)':-2", '-q:v', '3', staged / 'poster.jpg')
        ffmpeg('-i', src / 'reel.mp4', '-vf', "scale='min(640,iw)':-2", '-c:v', 'libx264', '-crf', '28',
               '-preset', 'slow', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-an', staged / 'clip.mp4')
        if (staged / 'clip.mp4').stat().st_size >= 1_500_000:
            raise ValueError('Packaged clip exceeds 1.5 MB')
        for board in boards:
            shutil.copyfile(src / board, staged / board)
        shutil.copyfile(job / 'probe' / 'probe.jpg', staged / 'probe.jpg')
        if spec.get('compare_with'):
            ffmpeg('-i', src / 'cover.png', '-i', (folder / spec['compare_with']).resolve(), '-filter_complex',
                   '[0]scale=-2:540,setsar=1[a];[1]scale=-2:540,setsar=1[b];[a][b]hstack=inputs=2,'
                   'scale=1560:1560:force_original_aspect_ratio=decrease', '-frames:v', '1',
                   staged / 'compare.jpg')
        summary = {'job_id': job.name, 'stage': 'preview', 'brief': out['brief'], 'board_hashes': boards,
                   'script_sha256': pipeline.digest(job / 'scene.py'),
                   'render_code': pipeline.job_manifest(job)['code'],
                   'reviewer_notes': notes, 'qc': out['preview']['qc'],
                   'jev': {'model': evidence['model'], 'decision': decision, **findings}}
        pipeline.write(staged / 'review.json', summary)
        result.mkdir(exist_ok=True)
        for path in staged.iterdir():
            path.replace(result / path.name)
    print(f'Packaged {folder.name} in {result}')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('slug', choices=sorted(p.parent.name for p in (ROOT / 'acceptance').glob('*/acceptance.json')))
    ap.add_argument('--probe', action='store_true', help='Stop after the probe')
    ap.add_argument('--job', help='Reuse a ready probe or draft for this scenario')
    ap.add_argument('--parent', help='Parent job ID for a new revision')
    ap.add_argument('--package', action='store_true', help='Package a draft with its existing Jev results and visual notes')
    ap.add_argument('--root', type=Path, required=True, help='Scratch job root outside this checkout')
    a = ap.parse_args()
    if a.job and (a.probe or a.parent):
        ap.error('--job cannot be combined with --probe or --parent')
    if a.package and not a.job:
        ap.error('--package requires --job')
    root = pipeline.output_root(a.root)
    if root.is_relative_to(ROOT):
        ap.error('Use a scratch job root outside the repository')
    folder = ROOT / 'acceptance' / a.slug
    spec = pipeline.read(folder / 'acceptance.json')
    script = (folder / 'scene.py').read_text(encoding='utf-8')
    try:
        parent = pipeline.status(root, a.job)['parent'] if a.job else a.parent
        brief, diagrams = scenario_brief(root, folder, spec, parent)
        stage = 'probe' if a.probe else 'preview'
        if a.job:
            job = pipeline.job_path(root, a.job)
            status = pipeline.status(root, a.job)
            if status['brief'] != brief or (job / 'scene.py').read_text(encoding='utf-8') != script:
                raise ValueError('The current scenario differs from this job. Start a revision.')
            if a.package:
                pipeline.checked_stage(job, stage)
                evidence = pipeline.read(job / stage / 'jev-review.json')
                if evidence['board_hashes'] != status[stage]['review_hashes']:
                    raise ValueError('The Jev judgment does not match the current review boards')
                package(folder, spec, job, status, evidence)
                return 0
            queued = pipeline.start_draft(root, job_id=a.job) if not status[stage] else {'stage': stage, 'job_id': a.job}
        else:
            start = pipeline.start_probe if a.probe else pipeline.start_draft
            queued = start(root, brief, script)
        print(f'Job {queued["job_id"]}', flush=True)
        status, ok = wait(root, queued['job_id'], queued['stage'])
        if not ok:
            failed = status[stage] or status['probe']
            raise ValueError(failed.get('error', f'{stage} failed'))
        print(json.dumps(status[stage], indent=2))
        if a.probe:
            return 0
        job = pipeline.job_path(root, status['job_id'])
        pipeline.checked_stage(job, stage)
        decision, findings, receipts = review.review(job, stage, brief['prompt'], spec['elements'],
                                                     spec.get('expect_text', False), diagrams)
        evidence = {'model': review.MODEL, 'decision': decision, 'findings': findings,
                    'board_hashes': status[stage]['review_hashes'], 'requests': receipts}
        pipeline.write(job / stage / 'jev-review.json', json.loads(json.dumps(evidence, default=str)))
        print(json.dumps({'decision': decision, **findings}, indent=2))
        return {'pass': 0, 'look': 2, 'fix': 1}[decision['verdict']]
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        sys.exit(str(exc))


if __name__ == '__main__':
    raise SystemExit(main())
