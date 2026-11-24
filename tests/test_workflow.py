import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


class Contract(unittest.TestCase):
    def cli(self, home, *args):
        return subprocess.run([sys.executable, '-m', 'agent_studio.cli', '--output-root', home, *args],
                              capture_output=True, text=True, timeout=20)

    def test_structured_brief_normalizes_without_starting_blender(self):
        with TemporaryDirectory() as home:
            r = self.cli(home, 'brief', '{"template":"gravity-conveyor","title":"Gravity Lab","accent":"#00ffaa"}')
            self.assertEqual(r.returncode, 0, r.stderr)
            doc = json.loads(r.stdout)
            self.assertEqual(doc['seconds'], 6)
            self.assertEqual(doc['accent'], '#00FFAA')
            self.assertEqual(doc['title'], 'Gravity Lab')
            self.assertFalse(list(Path(home).iterdir()))

    def test_brief_rejects_untrusted_paths_code_and_out_of_bounds(self):
        with TemporaryDirectory() as home:
            for brief in ({'title':'x','script':'print(1)'}, {'title':'x','path':'/tmp'},
                          {'title':'x','seconds':9}, {'title':'x','seconds':True},
                          {'title':'x','template':'../gravity'}, {'title':'x','accent':'red'},
                          {'title':'x\nRogue'}, {'title':'✨'}, []):
                with self.subTest(brief=brief):
                    r = self.cli(home, 'brief', json.dumps(brief))
                    self.assertNotEqual(r.returncode, 0)
                    self.assertIn('error', json.loads(r.stdout))
            self.assertFalse(list(Path(home).iterdir()))

    def test_output_orientation_is_optional_but_bounded(self):
        with TemporaryDirectory() as home:
            for brief, expected in (({}, 'vertical'), ({'orientation': 'horizontal'}, 'horizontal')):
                with self.subTest(brief=brief):
                    r = self.cli(home, 'brief', json.dumps(brief))
                    self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                    self.assertEqual(json.loads(r.stdout)['orientation'], expected)
            for invalid in ('square', '16:9', True, ['horizontal'], None):
                with self.subTest(orientation=invalid):
                    r = self.cli(home, 'brief', json.dumps({'orientation': invalid}))
                    self.assertNotEqual(r.returncode, 0)
                    self.assertIn('orientation', json.loads(r.stdout)['error'])
            self.assertFalse(list(Path(home).iterdir()))

    def test_unknown_id_cannot_escape_job_root(self):
        with TemporaryDirectory() as home:
            r = self.cli(home, 'status', '../../.hermes')
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('job ID', json.loads(r.stdout)['error'])

    def test_final_cannot_start_without_completed_matching_preview(self):
        with TemporaryDirectory() as home:
            id_ = '3b9d044234f1462cb44c3a8115d2cf0d'
            (Path(home) / id_).mkdir()
            proof = json.dumps({'timeline':'abc','angles':'abc','sections':'abc','notes':'Looked fine.'})
            r = self.cli(home, 'finalize', id_, proof)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('preview', json.loads(r.stdout)['error'])
            self.assertFalse((Path(home) / id_ / 'master').exists())


if __name__ == '__main__':
    unittest.main()
