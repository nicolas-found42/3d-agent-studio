"""Retrieve incident evidence from independent processes using isolated job roots."""
from contextlib import redirect_stderr
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from agent_studio import ingest, observability, pipeline, worker


class Observability(unittest.TestCase):
    def cli(self, root, *arguments, env=None):
        return subprocess.run(
            [sys.executable, '-m', 'agent_studio.cli', '--output-root', str(root), *arguments],
            capture_output=True, text=True, timeout=15, env=env,
        )

    def launch_fixture(self, root, mode):
        sentinel = 'marker-not-for-the-journal'
        executable = root / 'fake-blender'
        executable.write_text(f'#!{sys.executable}\n'
                              'import sys, time\n'
                              'if "--version" in sys.argv:\n'
                              '    print("Blender 5.2.2")\n'
                              '    sys.exit(0)\n'
                              f'print("{sentinel}", file=sys.stderr, flush=True)\n'
                              + ('time.sleep(45)\n' if mode == 'wait' else 'sys.exit(37)\n'))
        executable.chmod(0o700)
        script = root / 'scene.py'
        script.write_text('def build(kit):\n    pass\n')
        env = {**os.environ, **dict.fromkeys(pipeline.RUNTIME_OVERRIDES.values(), str(executable))}
        launched = self.cli(root, 'probe', json.dumps({'prompt': sentinel}), str(script), env=env)
        self.assertEqual(launched.returncode, 0, launched.stdout + launched.stderr)
        return json.loads(launched.stdout)['job_id'], sentinel

    def wait_for_event(self, root, job, name, *, tool=None):
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            result = pipeline.diagnostics(root, job_id=job)
            for event in result['events']:
                if event['event'] == name and (tool is None or event['details'].get('tool') == tool):
                    return event
            time.sleep(.05)
        self.fail(f'Missing {name} in retained history: {result}')

    def test_worker_nonzero_exit_is_retrievable_after_launcher_exits(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            job, sentinel = self.launch_fixture(root, 'fail')
            observed = self.wait_for_event(root, job, 'stage_failed')
            first = self.cli(root, 'diagnostics', '--job', job, '--limit', '3')
            self.assertEqual(first.returncode, 0, first.stderr)
            page = json.loads(first.stdout)
            self.assertIsNotNone(page['next_after'])
            found = self.cli(root, 'diagnostics', '--operation', observed['operation_id'])
            self.assertEqual(found.returncode, 0, found.stderr)
            report = json.loads(found.stdout)
            self.assertEqual(report['source'], 'readable')
            self.assertEqual(page['job_sources']['probe']['state'], 'failed')
            self.assertNotIn(sentinel, found.stdout)
            events = report['events']
            queue = next(e for e in events if e['event'] == 'queued')
            worker = next(e for e in events if e['event'] == 'worker_started')
            self.assertEqual(queue['attempt_id'], worker['attempt_id'])
            self.assertNotEqual(queue['pid'], worker['pid'])
            self.assertLess(queue['id'], worker['id'])
            self.assertEqual(queue['origin'], 'cli')
            exit_event = next(e for e in events if e['event'] == 'dependency_finished'
                              and e['details']['tool'] == 'blender')
            self.assertEqual(exit_event['details']['returncode'], 37)
            self.assertEqual(observed['details']['phase'], 'blender')
            self.assertIn(sentinel, (root / job / 'probe' / 'run.log').read_text())

    def test_lost_worker_stays_without_terminal_evidence(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            job, _ = self.launch_fixture(root, 'wait')
            worker = self.wait_for_event(root, job, 'worker_spawned')['details']['worker_pid']
            try:
                self.wait_for_event(root, job, 'dependency_started', tool='blender')
            finally:
                try:
                    os.killpg(worker, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            result = self.cli(root, 'diagnostics', '--job', job)
            data = json.loads(result.stdout)
            self.assertEqual(data['job_sources']['probe']['state'], 'running')
            events = {e['event'] for e in data['events']}
            self.assertIn('gpu_acquired', events)
            self.assertFalse(events & {'stage_ready', 'stage_failed'})

    def test_preview_handoff_failure_leaves_completed_probe(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            bins = dict.fromkeys(pipeline.RUNTIME_OVERRIDES, '/fixture/blender')
            with patch.object(pipeline, 'executables', return_value=bins):
                job = pipeline.create_job(root, {'prompt': 'fixture'}, 'def build(kit): pass')
                stage = job / 'probe'
                stage.mkdir()
                pipeline.write(stage / 'state.json', {'state': 'queued', 'then': 'preview'})

                def evidence(*_):
                    (job / 'scene.blend').write_bytes(b'scene')
                    for name in pipeline.evidence('probe', {}, False):
                        (stage / name).write_bytes(b'evidence')

                with (patch.object(worker, 'run', return_value='Blender 5.2.2'),
                      patch.object(worker, 'probe_outputs', side_effect=evidence),
                      patch.object(pipeline, 'launch', side_effect=PermissionError),
                      redirect_stderr(io.StringIO()), patch('builtins.print')):
                    worker.work(job, 'probe')
            data = pipeline.diagnostics(root, job_id=job.name)
            self.assertEqual(data['job_sources']['probe']['state'], 'ready')
            self.assertEqual(data['job_sources']['preview']['state_source'], 'absent')
            events = [e['event'] for e in data['events']]
            self.assertLess(events.index('stage_ready'), events.index('chained_launch_failed'))
            self.assertNotIn('stage_failed', events)

    def test_outage_and_read_pagination(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            notes = root / 'notes.txt'
            notes.write_text('private scene notes')
            blocked = root / '.diagnostics'
            blocked.write_text('blocks the journal directory')
            with patch.object(observability, '_storage_errors', set()), redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(ingest.ingest(root, str(notes))['kind'], 'text')
                self.assertIn('STUDIO_DIAGNOSTIC_WRITE_UNAVAILABLE', stderr.getvalue())
                self.assertNotIn(str(notes), stderr.getvalue())
            blocked.unlink()
            with patch.object(observability, 'MAX_EVENTS', 5):
                for _ in range(4):
                    ingest.ingest(root, str(notes))
                first = pipeline.diagnostics(root, limit=2)
                self.assertTrue(first['retained']['cursor_gap'])
                other = pipeline.diagnostics(root, after=first['next_after'], limit=3)
                ids = [e['id'] for page in (first, other) for e in page['events']]
                self.assertEqual(len(ids), 5)
                self.assertEqual(ids, sorted(set(ids)))
                self.assertIsNone(other['next_after'])
                future = pipeline.diagnostics(root, since='2099-01-01T00:00:00Z')
                self.assertEqual(future['source'], 'readable')
                self.assertEqual(future['events'], [])
            (blocked / 'events.sqlite3').write_bytes(b'invalid sqlite file')
            self.assertEqual(pipeline.diagnostics(root)['source'], 'unavailable')
