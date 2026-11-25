import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from agent_studio import assets, ingest, pipeline, scriptcheck

GOOD_SCRIPT = '''
import math


def build(kit):
    kit.ground(kit.material('Floor', '#777777'))
    cube = kit.box('Cube', 1, (0, 0, 0.5), kit.material('Red', '#CC3333'))
    kit.spin(cube, 'Z', 1)
    kit.sun(40, 30, 3)
    kit.camera((0, -5, 2), (0, 0, 0.5))
'''
HAVE_FFMPEG = bool(shutil.which('ffmpeg') and shutil.which('ffprobe'))


class Cli(unittest.TestCase):
    def cli(self, home, *args):
        return subprocess.run([sys.executable, '-m', 'agent_studio.cli', '--output-root', home, *args],
                              capture_output=True, text=True, timeout=60)


class Brief(unittest.TestCase):
    def test_defaults_and_normalization(self):
        b = pipeline.validate_brief({'prompt': '  A lighthouse at dusk  '})
        self.assertEqual(b['prompt'], 'A lighthouse at dusk')
        self.assertEqual((b['orientation'], b['seconds'], b['fps'], b['loop']), ('vertical', 6, 24, False))
        self.assertEqual(b['budget_minutes'], {'probe': 5, 'draft': 10, 'master': 10})
        self.assertEqual(b['max_references'], 40)
        b = pipeline.validate_brief({'prompt': 'x', 'references': ['ref-0123456789abcdef'], 'budget_minutes': {'master': 60}})
        self.assertEqual(b['references'], [{'id': 'ref-0123456789abcdef'}])
        self.assertEqual(b['budget_minutes']['master'], 60)

    def test_every_orientation_and_fps(self):
        for orientation in ('vertical', 'horizontal', 'square', 'portrait', 'ultrawide'):
            for fps in (24, 30, 60, 120):
                self.assertEqual(pipeline.validate_brief({'prompt': 'x', 'orientation': orientation, 'fps': fps})['fps'], fps)

    def test_rejections(self):
        bad = [
            {}, {'prompt': ''}, {'prompt': 'x', 'template': 'orbit-bloom'}, {'prompt': 'x', 'script': 'print(1)'},
            {'prompt': 'x', 'orientation': '16:9'}, {'prompt': 'x', 'fps': 25}, {'prompt': 'x', 'seconds': 31},
            {'prompt': 'x', 'seconds': True}, {'prompt': 'x', 'loop': 'yes'}, {'prompt': 'x', 'show_title': True},
            {'prompt': 'x', 'title': 'x\nrogue'}, {'prompt': 'x', 'budget_minutes': {'draft': 0}},
            {'prompt': 'x', 'budget_minutes': {'render': 5}}, {'prompt': 'x', 'extras': ['gif']},
            {'prompt': 'x', 'assets': ['polyhaven']}, {'prompt': 'x', 'assets': ['ftp:thing']},
            {'prompt': 'x', 'references': [{'id': 'a', 'path': '/etc/passwd'}]},
            {'prompt': 'x', 'references': ['a', 'a']}, {'prompt': 'x', 'parent': '../job'},
            {'prompt': 'x', 'samples': {'master': 0}}, [],
        ]
        for brief in bad:
            with self.subTest(brief=brief):
                with self.assertRaises(ValueError):
                    pipeline.validate_brief(brief)


class ScriptCheck(unittest.TestCase):
    def test_accepts_kit_script(self):
        self.assertEqual(scriptcheck.check(GOOD_SCRIPT), [])

    def test_rejects_unsafe_or_incomplete(self):
        cases = {
            'import os\ndef build(kit): pass': 'import',
            'import subprocess\ndef build(kit): pass': 'import',
            'from pathlib import Path\ndef build(kit): pass': 'import',
            'def build(kit):\n    open("/etc/passwd")': 'open',
            'def build(kit):\n    __import__("os")': '__import__',
            'import bpy\ndef build(kit):\n    bpy.ops.wm.save_mainfile()': 'reserved',
            'import bpy as b\ndef build(kit):\n    b.ops.render.render()': 'reserved',
            'from bpy.app import handlers\ndef build(kit):\n    handlers.frame_change_pre.append(1)': 'reserved',
            'import bpy\ndef build(kit):\n    bpy.data.texts.new("x")': 'reserved',
            'def build(kit):\n    kit.__class__': 'dunder',
            'def build(kit):\n    eval("1")': 'eval',
            'def make(kit): pass': 'build(kit)',
            'def build(kit)': 'Syntax',
            '': 'empty',
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                problems = scriptcheck.check(source)
                self.assertTrue(problems)
                self.assertIn(expected, ' '.join(problems))


class Licenses(unittest.TestCase):
    def test_policy(self):
        ok = {'cc0': 'CC0-1.0', 'CC0 1.0': 'CC0-1.0', 'pdm': 'LicenseRef-PublicDomain', 'Public domain': 'LicenseRef-PublicDomain',
              'by': 'CC-BY-4.0', 'CC BY 2.0': 'CC-BY-2.0', 'cc-by-4.0': 'CC-BY-4.0', 'OFL-1.1': 'OFL-1.1', 'Apache-2.0': 'Apache-2.0'}
        for raw, expected in ok.items():
            self.assertEqual(assets.spdx(raw), expected, raw)
        for raw in ('CC-BY-NC-4.0', 'cc-by-sa-3.0', 'CC BY-ND 4.0', 'GPL-3.0', 'SCEA', 'Royalty Free', '', None):
            with self.subTest(raw=raw):
                with self.assertRaises(assets.LicenseError):
                    assets.spdx(raw)

    def test_ids_and_hosts(self):
        self.assertEqual(assets.parse('nasa:3D Models/Hubble/Hubble.glb'), ('nasa', '3D Models/Hubble/Hubble.glb'))
        for bad in ('sketchfab:abc', 'polyhaven', 'url:', 'x' * 700):
            with self.assertRaises(ValueError):
                assets.parse(bad)
        with self.assertRaises(assets.LicenseError):
            assets.resolve_url('https://example.com/model.glb', None)
        self.assertTrue(assets.host_ok('https://www.kenney.nl/a.zip', assets.CC0_HOSTS))
        self.assertFalse(assets.host_ok('https://kenney.nl.evil.com/a.zip', assets.CC0_HOSTS))
        self.assertEqual(assets.texture_name('Bricks076C_1K-JPG_NormalGL.jpg'), 'normal_gl.jpg')
        self.assertIsNone(assets.texture_name('Bricks076C_1K-JPG_NormalDX.jpg'))
        self.assertEqual(assets.texture_name('x_diff_2k.jpg'), 'color.jpg')


class Ingest(unittest.TestCase):
    def test_files_roles_and_rejections(self):
        with TemporaryDirectory() as tmp:
            root, src = Path(tmp) / 'jobs', Path(tmp) / 'src'
            src.mkdir()
            (src / 'stats.csv').write_text('year,value\n2020,1\n2021,3\n')
            (src / 'shots.md').write_text('1. wide\n2. push in\n')
            (src / 'broken.json').write_text('{not json')
            (src / 'external.gltf').write_text(json.dumps({'buffers': [{'uri': 'mesh.bin'}]}))
            (src / 'notes.exe').write_bytes(b'MZ')
            data = ingest.ingest(root, str(src / 'stats.csv'))
            self.assertEqual((data['kind'], data['role'], data['data']['rows']), ('data', 'data', 2))
            again = ingest.ingest(root, str(src / 'stats.csv'))
            self.assertEqual(again['id'], data['id'])
            self.assertEqual(ingest.ingest(root, str(src / 'shots.md'), 'shotlist')['kind'], 'text')
            for path, role, message in ((src / 'notes.exe', None, 'Unsupported'), (src / 'broken.json', None, 'parse'),
                                        (src / 'external.gltf', None, 'glb'), (src / 'stats.csv', 'style', 'Role'),
                                        (Path('relative.csv'), None, 'absolute'), (src / 'missing.png', None, 'readable')):
                with self.subTest(path=path.name):
                    with self.assertRaisesRegex(ValueError, message):
                        ingest.ingest(root, str(path), role)
            with self.assertRaises(ValueError):
                ingest.ref_dir(root, '../escape')

    @unittest.skipUnless(HAVE_FFMPEG, 'needs ffmpeg')
    def test_video_becomes_scene_frames(self):
        with TemporaryDirectory() as tmp:
            clip = Path(tmp) / 'cuts.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=red:s=160x120:d=1.5', '-f', 'lavfi',
                            '-i', 'color=c=blue:s=160x120:d=1.5', '-filter_complex', '[0][1]concat=n=2:v=1:a=0',
                            '-r', '24', str(clip)], check=True)
            out = ingest.ingest(Path(tmp) / 'jobs', str(clip), 'motion', max_frames=4)
            self.assertEqual(out['kind'], 'video')
            self.assertLessEqual(len(out['frames']), 4)
            self.assertTrue(any(f['scene_cut'] and 1.3 < f['time_seconds'] < 1.7 for f in out['frames']), out['frames'])
            self.assertEqual(out['image_references'], len(out['frames']))


class Jobs(Cli):
    def test_rejected_script_creates_no_job(self):
        with TemporaryDirectory() as home:
            script = Path(home) / 'bad.py'
            script.write_text('import os\ndef build(kit): os.system("true")')
            r = self.cli(home, 'probe', '{"prompt":"x"}', str(script))
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('Scene script rejected', json.loads(r.stdout)['error'])
            self.assertFalse([p for p in Path(home).iterdir() if pipeline.JOB.fullmatch(p.name)])

    def test_unknown_reference_creates_no_job(self):
        with TemporaryDirectory() as home:
            script = Path(home) / 'scene.py'
            script.write_text(GOOD_SCRIPT)
            r = self.cli(home, 'probe', '{"prompt":"x","references":["ref-0000000000000000"]}', str(script))
            self.assertIn('Unknown reference', json.loads(r.stdout)['error'])
            self.assertFalse([p for p in Path(home).iterdir() if pipeline.JOB.fullmatch(p.name)])

    def test_ids_cannot_escape_and_finalize_needs_preview(self):
        with TemporaryDirectory() as home:
            r = self.cli(home, 'status', '../../.hermes')
            self.assertIn('job ID', json.loads(r.stdout)['error'])
            job = '3b9d044234f1462cb44c3a8115d2cf0d'
            (Path(home) / job).mkdir()
            r = self.cli(home, 'finalize', job, json.dumps({'hashes': {}, 'notes': 'Looked fine to me.'}))
            self.assertIn('preview', json.loads(r.stdout)['error'])
            self.assertFalse((Path(home) / job / 'master').exists())

    def test_master_plan_respects_budget_and_quality(self):
        with TemporaryDirectory() as home:
            job = Path(home) / ('a' * 32)
            (job / 'probe').mkdir(parents=True)
            brief = pipeline.validate_brief({'prompt': 'x', 'orientation': 'horizontal', 'seconds': 10})
            pipeline.write(job / 'job.json', {'brief': brief})
            # 0.05 s per megapixel-sample: 1080p at 128 spp is ~13 s/frame, ~53 min for 240 frames.
            pipeline.write(job / 'probe' / 'estimate.json', {'seconds_per_megapixel_sample': 0.05,
                                                             'overhead_seconds': 0.1, 'scene_load_seconds': 5})
            plan = pipeline.master_plan(job)
            self.assertIsNone(plan['samples'])
            self.assertGreater(plan['predicted_minutes'], 10)
            fast = pipeline.master_plan(job, quality='fast')
            self.assertIsNotNone(fast['samples'])
            self.assertGreaterEqual(fast['samples'], pipeline.FAST_FLOOR)
            self.assertLessEqual(fast['predicted_minutes'], 10)
            roomy = pipeline.master_plan(job, budget_minutes=600)
            self.assertEqual(roomy['samples'], 128)

    def test_kit_reference_is_current(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
        import kit_reference
        self.assertEqual(kit_reference.OUT.read_text(), kit_reference.render(),
                         'Run: uv run --locked python tools/kit_reference.py')

    def test_examples_index_is_searchable(self):
        found = pipeline.examples('', limit=12)
        self.assertEqual(found['total'], len(pipeline.example_index()))
        for entry in pipeline.example_index():
            folder = pipeline.EXAMPLES / entry['slug']
            self.assertTrue((folder / 'scene.py').is_file(), entry['slug'])
            self.assertEqual(scriptcheck.check((folder / 'scene.py').read_text()), [], entry['slug'])
            pipeline.validate_brief(entry['brief'])


@unittest.skipUnless(os.environ.get('STUDIO_RENDER_TESTS') == '1', 'set STUDIO_RENDER_TESTS=1 to render with Blender')
class Render(Cli):
    def test_probe_and_draft_real_blender(self):
        with TemporaryDirectory() as home:
            script = Path(home) / 'scene.py'
            script.write_text(GOOD_SCRIPT)
            brief = {'prompt': 'A red cube turning on a grey floor', 'orientation': 'square', 'seconds': 2, 'loop': True}
            r = self.cli(home, 'draft', json.dumps(brief), str(script), '--wait')
            self.assertEqual(r.returncode, 0, r.stdout[-3000:])
            out = json.loads(r.stdout)
            self.assertEqual(out['preview']['state'], 'ready')
            self.assertEqual(set(out['preview']['review_hashes']), {'timeline.jpg', 'angles.jpg', 'seam.jpg'})
            self.assertEqual(out['preview']['qc']['warnings'], [])


if __name__ == '__main__':
    unittest.main()
