"""Make, review and promote prompt-driven Blender scenes from the terminal."""
import argparse
import json
from pathlib import Path
import subprocess
import time

from . import ingest, pipeline


def load_json(text):
    """A JSON object given inline, or @path to a JSON file."""
    if text.startswith('@'):
        text = Path(text[1:]).expanduser().read_text(encoding='utf-8')
    return json.loads(text)


def load_script(path):
    return Path(path).expanduser().read_text(encoding='utf-8')


def wait(root, job, stage):
    """Poll until the stage settles; a probe queued with then=preview waits for the preview too."""
    deadline = time.monotonic() + 6 * 3600
    while time.monotonic() < deadline:
        out = pipeline.status(root, job)
        info = out[stage]
        if info and info['state'] not in ('queued', 'running'):
            if stage == 'probe' and info['state'] == 'ready' and info.get('then') == 'preview':
                stage = 'preview'
                continue
            return out, info['state'] == 'ready'
        time.sleep(2)
    raise ValueError(f'Wait expired; inspect status for {job}')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-root', type=Path, help='Jobs directory (also STUDIO_OUTPUT_ROOT; defaults to ~/3d-agent-studio-jobs)')
    sub = p.add_subparsers(dest='mode', required=True)
    sub.add_parser('doctor', help='Check runtime and report the brief schema, sources and limits')
    q = sub.add_parser('brief', help='Validate a brief'); q.add_argument('brief', help='JSON object or @file')
    q = sub.add_parser('ingest', help='Copy a reference file into the job root')
    q.add_argument('path'); q.add_argument('--role'); q.add_argument('--max-frames', type=int, default=ingest.DEFAULT_MAX_FRAMES)
    q = sub.add_parser('check', help='Check a scene script without running it'); q.add_argument('script')
    for mode in ('probe', 'draft'):
        q = sub.add_parser(mode)
        q.add_argument('brief', nargs='?', help='JSON object or @file')
        q.add_argument('script', nargs='?', help='Path to the scene script (.py defining build(kit))')
        if mode == 'draft':
            q.add_argument('--job', help='Draft an already probed job instead')
        q.add_argument('--wait', action='store_true')
    q = sub.add_parser('status'); q.add_argument('job_id')
    q = sub.add_parser('finalize')
    q.add_argument('job_id'); q.add_argument('review', help='JSON object with hashes and notes, or @file')
    q.add_argument('--budget-minutes', type=int); q.add_argument('--quality', choices=['standard', 'fast'])
    q.add_argument('--samples', type=int); q.add_argument('--wait', action='store_true')
    q = sub.add_parser('compare'); q.add_argument('before'); q.add_argument('after')
    q = sub.add_parser('examples', help='Search the example library')
    q.add_argument('query', nargs='?', default=''); q.add_argument('--tag', action='append', default=[])
    q.add_argument('--limit', type=int, default=8); q.add_argument('--script', action='store_true')
    a = p.parse_args()
    root = pipeline.output_root(a.output_root)
    try:
        if a.mode == 'doctor':
            out = pipeline.doctor(root)
        elif a.mode == 'brief':
            out = pipeline.validate_brief(load_json(a.brief))
        elif a.mode == 'ingest':
            out = ingest.ingest(root, str(Path(a.path).expanduser().resolve()), a.role, a.max_frames)
        elif a.mode == 'check':
            from . import scriptcheck
            problems = scriptcheck.check(load_script(a.script))
            out = {'ok': not problems, 'problems': problems}
        elif a.mode == 'probe':
            out = pipeline.start_probe(root, load_json(a.brief), load_script(a.script))
        elif a.mode == 'draft':
            if a.job:
                out = pipeline.start_draft(root, job_id=a.job)
            else:
                if not (a.brief and a.script):
                    raise ValueError('draft needs BRIEF and SCRIPT, or --job JOB_ID')
                out = pipeline.start_draft(root, load_json(a.brief), load_script(a.script))
        elif a.mode == 'status':
            out = pipeline.status(root, a.job_id)
        elif a.mode == 'finalize':
            out = pipeline.finalize(root, a.job_id, load_json(a.review), a.budget_minutes, a.quality, a.samples)
        elif a.mode == 'compare':
            out = pipeline.compare(root, a.before, a.after)
        else:
            out = pipeline.examples(a.query, a.tag, a.limit, a.script)
        if getattr(a, 'wait', False):
            out, ok = wait(root, out['job_id'], out['stage'])
            print(json.dumps(out))
            return 0 if ok else 1
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as exc:
        print(json.dumps({'error': str(exc)}))
        return 1
    print(json.dumps(out))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
