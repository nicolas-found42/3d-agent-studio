"""Validate, render, inspect, and promote local Blender animation jobs."""
import argparse
import json
from pathlib import Path
import subprocess
import time

from . import pipeline


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-root', type=Path, help='Jobs directory (also STUDIO_OUTPUT_ROOT; defaults to ~/3d-agent-studio-jobs)')
    sub = p.add_subparsers(dest='mode', required=True)
    sub.add_parser('doctor', help='Check runtime and report the brief schema')
    for mode in ('brief', 'draft'):
        q = sub.add_parser(mode)
        q.add_argument('brief', help='JSON object')
        if mode == 'draft':
            q.add_argument('--wait', action='store_true')
    q = sub.add_parser('status'); q.add_argument('job_id')
    q = sub.add_parser('finalize')
    q.add_argument('job_id'); q.add_argument('review', help='JSON object with hashes and notes')
    q.add_argument('--wait', action='store_true')
    q = sub.add_parser('compare'); q.add_argument('before'); q.add_argument('after')
    a = p.parse_args()
    root = pipeline.output_root(a.output_root)
    try:
        if a.mode == 'doctor':
            out = pipeline.doctor(root)
        elif a.mode == 'brief':
            out = pipeline.validate_brief(json.loads(a.brief))
        elif a.mode == 'draft':
            out = pipeline.start_draft(root, json.loads(a.brief))
        elif a.mode == 'status':
            out = pipeline.status(root, a.job_id)
        elif a.mode == 'finalize':
            out = pipeline.finalize(root, a.job_id, json.loads(a.review))
        else:
            out = pipeline.compare(root, a.before, a.after)
        if getattr(a, 'wait', False):
            job, stage = out['job_id'], out['stage']
            deadline = time.monotonic() + 1810
            while time.monotonic() < deadline:
                out = pipeline.status(root, job)
                if out[stage]['state'] not in ('queued', 'running'):
                    print(json.dumps(out))
                    return 0 if out[stage]['state'] == 'ready' else 1
                time.sleep(1)
            raise ValueError(f'Wait expired; inspect status for {job}')
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as exc:
        print(json.dumps({'error': str(exc)}))
        return 1
    print(json.dumps(out))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
