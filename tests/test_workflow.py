import asyncio
import base64
from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from agent_studio import assets, ingest, pipeline, scriptcheck, worker

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
    cli_timeout = 60

    def cli(self, home, *args):
        return subprocess.run([sys.executable, '-m', 'agent_studio.cli', '--output-root', home, *args],
                              capture_output=True, text=True, timeout=self.cli_timeout)


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
            'import bpy.app.handlers\ndef build(kit): pass': 'reserved',
            'from bpy.app.handlers import persistent\ndef build(kit): pass': 'reserved',
            'from bpy.ops import wm\ndef build(kit): pass': 'reserved',
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
            subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=red:s=160x120:d=1.5', '-f', 'lavfi',
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

    def test_master_prediction_uses_measured_full_resolution(self):
        estimate = {'overhead_seconds': .1, 'seconds_per_megapixel_sample': .001, 'scene_load_seconds': 5,
                    'preview_throughput': {'pixels': 129600, 'samples': 16, 'per_frame_seconds': .25},
                    'master_calibration': {'pixels': 1166400,
                                           'low': {'samples': 16, 'per_frame_seconds': .7},
                                           'high': {'samples': 64, 'per_frame_seconds': 1.66}}}
        frames = 49
        rendering = frames * 2.94
        export = 1.1664 * frames * .14
        expected = rendering + 3 * .25 + 5 + export
        self.assertAlmostEqual(pipeline.predict(estimate, 1166400, 128, frames, loop=True), expected)
        self.assertAlmostEqual(pipeline.predict(estimate, 129600, 16, frames),
                               frames * .25 + 3 * (.1 + .001 * .1296 * 16) + 5 + .1296 * frames * .1)

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
            self.assertEqual(pipeline.read(folder / 'example.json'), entry)
            for artifact in ('poster.jpg', 'clip.mp4', 'review.json'):
                self.assertGreater((folder / artifact).stat().st_size, 0, f'{entry["slug"]}: {artifact}')


@unittest.skipUnless(HAVE_FFMPEG, 'needs ffmpeg')
class ReferenceBoards(unittest.TestCase):
    def test_default_reference_limit_fits_in_one_board(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            bins = pipeline.executables()

            def color_patch(path, color):
                path.write_bytes(b'P6\n16 16\n255\n' + bytes(color) * 256)

            frame = root / 'comparison.ppm'
            color_patch(frame, (13, 64, 226))
            pairs, expected = [], []
            for i in range(40):
                reference = root / f'reference-{i:02d}.ppm'
                color = (30 + 40 * (i % 5), 28 + 25 * (i // 5), 55)
                color_patch(reference, color)
                pairs.append({'reference_path': reference, 'frame_path': frame})
                expected.append(color)

            board = root / 'references.jpg'
            with redirect_stdout(StringIO()):
                worker.reference_board(bins, pairs, board)
            result = subprocess.run([bins['ffprobe'], '-v', 'error', '-show_entries', 'stream=width,height',
                                     '-of', 'json', board], capture_output=True, check=True)
            size = json.loads(result.stdout)['streams'][0]
            self.assertEqual((size['width'], size['height']), (1552, 1140))
            pixels = subprocess.run([bins['ffmpeg'], '-nostdin', '-v', 'error', '-i', board,
                                     '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                                    capture_output=True, check=True).stdout
            for index, wanted in enumerate(expected):
                row, col = divmod(index, 4)
                for x, rgb in ((col * 388 + 103, wanted), (col * 388 + 285, (13, 64, 226))):
                    offset = 3 * ((row * 114 + 57) * size['width'] + x)
                    sample = pixels[offset:offset + 3]
                    self.assertEqual(len(sample), 3)
                    self.assertLess(max(abs(a - b) for a, b in zip(sample, rgb)), 12, (index, sample, rgb))


@unittest.skipUnless(os.environ.get('STUDIO_RENDER_TESTS') == '1', 'set STUDIO_RENDER_TESTS=1 to render with Blender')
class Render(Cli):
    cli_timeout = 900

    def test_kit_key_interpolation_and_parenting_in_blender(self):
        root = Path(__file__).resolve().parents[1] / 'src'
        program = f'''
from pathlib import Path
import sys
from itertools import product
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector
sys.path.insert(0, {str(root)!r})
from agent_studio.formats import MASTER_SIZES, stage_size
from agent_studio.kit import Kit
from agent_studio.runner import frame_proof, pair_references, proof_camera, scene_stats

kit = Kit({{'job': '.', 'brief': {{'prompt': 'Kit test', 'seed': 2, 'fps': 24, 'seconds': 2,
                                   'loop': False, 'orientation': 'square'}}, 'size': (360,360)}})
child = kit.box('Child', 1, (1, 2, 3))
parent = kit.empty('Parent', (7, 8, 9))
kit.parent(child, parent)
bpy.context.view_layer.update()
assert tuple(child.matrix_world.translation) == (1, 2, 3)
kit.key(child, 'location', [(1, 0), (21, 20)], index=0, interpolation='LINEAR')
kit.key(child, 'location', [(21, 20), (41, 40)], index=0, interpolation='CONSTANT')
emission = kit.emissive('Animated material')
child.data.materials.append(emission)
strength = emission.node_tree.nodes['Emission'].inputs['Strength']
kit.key(strength, 'default_value', [(1, 0), (21, 20)], interpolation='LINEAR')
kit.scene.frame_set(11)
assert abs(child.location.x - 10) < 1e-5 and abs(strength.default_value - 10) < 1e-5
kit.scene.frame_set(31)
assert child.location.x == 20
cut = kit.tube('Exact corners', [(0,0,0), (1,0,0), (1,1,0)], spline='POLY')
assert cut.data.splines[0].type == 'POLY'
kit.key(cut.data, 'bevel_factor_end', [(1, 0), (21, 1)])
assert cut.data.name in scene_stats(kit.scene)['animated']
assert kit.glow().inputs['Type'].default_value == 'Fog Glow'

for extent in (((-1, -30, -1), (3, 5, 14)), ((-10000, -10000, 0), (10000, 10000, 2))):
    lo, hi = map(Vector, extent)
    centre = (lo + hi) / 2
    for orientation in MASTER_SIZES:
        kit.scene.render.resolution_x, kit.scene.render.resolution_y = stage_size(orientation, 'preview')
        top = proof_camera('Top', centre + Vector((0, 0, 1)), centre, ortho=1)
        oblique = proof_camera('Oblique', centre + Vector((1, -1, 0.9)), centre)
        for camera in (top, oblique):
            frame_proof(kit.scene, camera, lo, hi)
            bpy.context.view_layer.update()
            for corner in product(*zip(lo, hi)):
                proj = world_to_camera_view(kit.scene, camera, Vector(corner))
                assert 0.06 < proj.x < 0.94 and 0.06 < proj.y < 0.94, proj
                assert camera.data.clip_start < proj.z < camera.data.clip_end, (camera.name, proj)

with TemporaryDirectory() as tmp:
    folder = Path(tmp)
    image = bpy.data.images.new('Synthetic HDR reference', width=32, height=16, float_buffer=True)
    image.pixels.foreach_set([4.0, 0.8, 0.12, 1.0] * (32 * 16))
    original, frame = folder / 'source.exr', folder / 'render.png'
    kit.scene.render.image_settings.file_format = 'OPEN_EXR'
    image.save_render(str(original), scene=kit.scene)
    kit.scene.render.image_settings.file_format = 'PNG'
    image.save_render(str(frame), scene=kit.scene)
    bpy.data.images.remove(image)
    source_bytes = original.read_bytes()
    ref = SimpleNamespace(kind='image', role='palette', id='ref-0123456789abcdef', name=original.name,
                          paths=[original])
    context = SimpleNamespace(references=[ref], scene=kit.scene)
    pairs = pair_references(context, [frame], folder)
    assert len(pairs) == 1 and pairs[0]['frame_path'] == str(frame), pairs
    preview = Path(pairs[0]['reference_path'])
    assert preview.suffix == '.png' and preview.is_file() and original.read_bytes() == source_bytes

    svg = folder / 'mark.svg'
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
                   '<rect x="10" y="20" width="80" height="60"/></svg>')
    kit.references.append(SimpleNamespace(id='mark', kind='vector', paths=[svg]))
    logo = kit.svg('mark', size=.52, extrude=.025, location=(-7.37, -.33, 3.45))
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    points = []
    for child in logo.children:
        evaluated = child.evaluated_get(depsgraph)
        points.extend(evaluated.matrix_world @ v.co for v in evaluated.to_mesh().vertices)
        evaluated.to_mesh_clear()
    widths = [max(axis) - min(axis) for axis in zip(*points)]
    assert abs(widths[0] - .52) < 1e-5 and abs(widths[1] - .05) < 1e-5, widths
'''
        cmd = [pipeline.executables()['blender'], '-b', '--factory-startup', '--disable-autoexec',
               '--python-exit-code', '1', '--python-expr', program]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=pipeline.render_env())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    async def assert_mcp_evidence(self, home, status, compare):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        server = StdioServerParameters(command=sys.executable, args=['-m', 'agent_studio.mcp_server',
                                                                   '--output-root', home])
        async with stdio_client(server) as streams, ClientSession(*streams) as client:
            await client.initialize()
            comparison = await client.call_tool('studio_compare', {'before': status['parent'], 'after': status['job_id']})
            self.assertFalse(comparison.isError, comparison.content)
            actual = comparison.structuredContent
            for key in ('before_top', 'after_bottom'):
                self.assertEqual(actual[key], compare[key])
            self.assertEqual(set(actual['artifacts']), set(compare['artifacts']))
            for board, path in actual['artifacts'].items():
                self.assertEqual(Path(path).read_bytes(), Path(compare['artifacts'][board]).read_bytes())

            for stage in ('probe', 'preview', 'master'):
                for board, path in status[stage]['artifacts'].items():
                    if not board.endswith(('.jpg', '.png')):
                        continue
                    result = await client.call_tool('studio_view', {'job_id': status['job_id'], 'stage': stage, 'board': board})
                    self.assertFalse(result.isError, result.content)
                    self.assertEqual(result.content[0].text, path)
                    image = result.content[1]
                    self.assertEqual(image.mimeType, 'image/png' if board.endswith('.png') else 'image/jpeg')
                    self.assertEqual(base64.b64decode(image.data), Path(path).read_bytes())

    def test_draft_revision_compare_and_finalize_real_blender(self):
        with TemporaryDirectory() as home:
            script = Path(home) / 'scene.py'
            script.write_text(GOOD_SCRIPT)
            ref = Path(home) / 'reference.png'
            bins = pipeline.executables()
            subprocess.run([bins['ffmpeg'], '-nostdin', '-v', 'error', '-f', 'lavfi', '-i',
                            'color=c=red:s=360x360', '-frames:v', '1', '-update', '1', ref], check=True)
            reference = ingest.ingest(Path(home), str(ref), 'palette')
            brief = {'prompt': 'A red cube turning on a grey floor', 'orientation': 'square', 'seconds': 2,
                     'loop': True, 'references': [reference['id']], 'extras': ['prores', 'png']}

            def command(*args):
                result = self.cli(home, *args)
                self.assertEqual(result.returncode, 0, result.stdout[-3000:] + result.stderr[-1000:])
                return json.loads(result.stdout)

            old = command('draft', json.dumps(brief), str(script), '--wait')
            script.write_text(GOOD_SCRIPT.replace('#CC3333', '#AA2233'))
            revised = command('draft', json.dumps({**brief, 'parent': old['job_id']}), str(script), '--wait')
            boards = {'timeline.jpg', 'angles.jpg', 'seam.jpg', 'references.jpg'}
            self.assertEqual(revised['parent'], old['job_id'])
            self.assertEqual(revised['preview']['state'], 'ready')
            self.assertEqual(set(revised['preview']['review_hashes']), boards)
            self.assertEqual(revised['preview']['qc']['warnings'], [])
            compare = command('compare', old['job_id'], revised['job_id'])
            self.assertEqual((compare['before_top'], compare['after_bottom']), (old['job_id'], revised['job_id']))
            self.assertEqual(set(compare['artifacts']), boards)
            self.assertNotEqual(old['preview']['review_hashes'], revised['preview']['review_hashes'])
            timeline = 'timeline.jpg'

            def pixels(path, crop=''):
                return subprocess.run([bins['ffmpeg'], '-nostdin', '-v', 'error', '-i', path,
                                       '-vf', crop + 'scale=24:16', '-frames:v', '1', '-f', 'rawvideo',
                                       '-pix_fmt', 'rgb24', '-'], check=True, capture_output=True).stdout

            def distance(a, b):
                self.assertEqual(len(a), len(b))
                return sum(abs(x - y) for x, y in zip(a, b))

            before = pixels(old['preview']['artifacts'][timeline])
            after = pixels(revised['preview']['artifacts'][timeline])
            top = pixels(compare['artifacts'][timeline], 'crop=iw:ih/2:0:0,')
            bottom = pixels(compare['artifacts'][timeline], 'crop=iw:ih/2:0:ih/2,')
            self.assertLess(distance(top, before), distance(top, after))
            self.assertLess(distance(bottom, after), distance(bottom, before))

            notes = 'Cube stays in frame, wide angles ground it, reference is red and the loop aligns.'
            invalid = self.cli(home, 'finalize', revised['job_id'], json.dumps({'hashes': {}, 'notes': notes}))
            self.assertNotEqual(invalid.returncode, 0)
            self.assertIn('exact current board hashes', invalid.stdout)
            approved = json.dumps({'hashes': revised['preview']['review_hashes'], 'notes': notes})
            budget = next(n for n in range(2, 31) if pipeline.master_plan(Path(home) / revised['job_id'], n, 'fast')['samples'])
            done = command('finalize', revised['job_id'], approved, '--quality', 'fast', '--budget-minutes', str(budget + 1), '--wait')
            master = done['master']
            self.assertEqual(master['state'], 'ready')
            self.assertGreaterEqual(master['plan']['samples'], pipeline.FAST_FLOOR)
            self.assertEqual(master['qc']['video']['frames'], 48)
            self.assertEqual(master['qc']['two_cycles']['frames'], 96)
            self.assertEqual(master['qc']['video']['width'], 1080)
            self.assertGreater(master['qc']['timing']['actual_minutes'], 0)
            self.assertEqual(len(list(Path(master['frames_directory']).glob('frame-*.png'))), 49)
            movie = subprocess.run([bins['ffprobe'], '-v', 'error', '-show_entries', 'stream=codec_name,profile',
                                    '-of', 'json', master['artifacts']['master.mov']], check=True, capture_output=True)
            self.assertEqual(json.loads(movie.stdout)['streams'], [{'codec_name': 'prores', 'profile': '4444'}])
            asyncio.run(self.assert_mcp_evidence(home, done, compare))

    def test_probe_enforces_one_minute_budget(self):
        with TemporaryDirectory() as home:
            script = Path(home) / 'scene.py'
            script.write_text('import math\n\ndef build(kit):\n    for i in range(10 ** 12):\n        math.sqrt(i)\n')
            brief = json.dumps({'prompt': 'Deliberately expensive build', 'budget_minutes': {'probe': 1}})
            result = self.cli(home, 'probe', brief, str(script), '--wait')
            self.assertNotEqual(result.returncode, 0)
            out = json.loads(result.stdout)
            self.assertEqual(out['probe']['state'], 'failed')
            self.assertIn('probe exceeded its 1 min budget', out['probe']['error'])
            self.assertIsNone(out['editable_blend'])


if __name__ == '__main__':
    unittest.main()
