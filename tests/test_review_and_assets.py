"""Offline tests for the asset resolvers and the dev-only Jev review truth table."""
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest import mock
import urllib.error
import zipfile

from agent_studio import assets, ingest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools' / 'review'))
import review  # noqa: E402


def findings(**over):
    f = {'elements': {'a lighthouse': 0.9}, 'defects': {'floating': 0.1, 'noisy': 0.1}, 'quality': 'polished',
         'prompt_match': 'clear', 'references': [], 'control': 0.05}
    f.update(over)
    return f


class Decide(unittest.TestCase):
    def test_truth_table(self):
        self.assertEqual(review.decide(findings())['verdict'], 'pass')
        self.assertEqual(review.decide(findings(elements={'a lighthouse': 0.2}))['verdict'], 'fix')
        self.assertEqual(review.decide(findings(elements={'a lighthouse': 0.5}))['verdict'], 'look')
        self.assertEqual(review.decide(findings(defects={'floating': 0.9}))['verdict'], 'fix')
        self.assertEqual(review.decide(findings(quality='basic'))['verdict'], 'fix')
        self.assertEqual(review.decide(findings(prompt_match='loose'))['verdict'], 'fix')
        self.assertEqual(review.decide(findings(control=0.6))['verdict'], 'look')
        self.assertEqual(review.decide(findings(control=0.9))['verdict'], 'look')
        self.assertEqual(review.decide(findings(text_readable=0.1))['verdict'], 'fix')
        self.assertEqual(review.decide(findings(text_readable=0.3))['verdict'], 'look')
        self.assertEqual(review.decide(findings(text_readable=0.7))['verdict'], 'look')
        for level in review.REFERENCE_LEVELS:
            ref = {'reference': 'ref-2', 'role': 'style', 'level': level}
            with self.subTest(level=level):
                self.assertEqual(review.decide(findings(references=[ref]))['verdict'],
                                 'fix' if level in ('unrelated', 'related') else 'pass')

    def test_noise_is_advisory_at_draft_quality(self):
        noisy = findings(defects={'noisy': 0.9})
        self.assertEqual(review.decide(noisy, 'preview')['verdict'], 'look')
        self.assertEqual(review.decide(noisy, 'master')['verdict'], 'fix')

    def test_references_deduplicated_and_overridable(self):
        refs = [{'reference': 'ref-1', 'role': 'composition', 'level': 'related'}] * 3
        d = review.decide(findings(references=refs))
        self.assertEqual(len(d['fix']), 1)
        d = review.decide(findings(references=refs), overrides=[{'item': 'reference ref-1', 'reason': 'layout checked by eye'}])
        self.assertEqual(d['verdict'], 'pass')
        self.assertEqual(d['overridden'][0]['reason'], 'layout checked by eye')
        with self.assertRaisesRegex(ValueError, 'written reason'):
            review.decide(findings(references=refs), overrides=[{'item': '', 'reason': 'checked'}])

    def test_reference_sampling_hashes_duplicate_frames_and_spreads_calls(self):
        with TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for name, data in [('first', b'a'), ('copy', b'a'), ('next', b'b'), ('still', b'c')]:
                (folder / name).write_bytes(data)

            def pair(ref, path, frame):
                return {'reference': ref, 'role': 'subject', 'reference_path': str(folder / path), 'frame_path': frame}

            pairs = [pair('video', 'first', '1'), pair('video', 'copy', '1'), pair('video', 'next', '1'),
                     pair('video', 'next', '2'), pair('photo', 'still', '1')]
            self.assertEqual(review.reference_sample(pairs), [pairs[0], pairs[4], pairs[3]])
            self.assertEqual(review.reference_sample(pairs, limit=2), [pairs[0], pairs[4]])


class FakeResponse(io.BytesIO):
    def __init__(self, data, url):
        super().__init__(data)
        self.url = url

    def geturl(self):
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class Resolvers(unittest.TestCase):
    def test_http_retries_rate_limits(self):
        err = urllib.error.HTTPError('https://x', 429, 'Too Many', {'Retry-After': '0'}, None)
        calls = [err, FakeResponse(b'ok', 'https://x/final')]

        def fake(req, timeout):
            item = calls.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        with mock.patch('urllib.request.urlopen', fake), mock.patch('time.sleep') as sleep:
            self.assertEqual(assets.http('https://x'), (b'ok', 'https://x/final'))
            sleep.assert_called_once_with(0)
        with self.assertRaises(ValueError):
            assets.http('http://insecure.example/x')

    def test_retry_after_date_and_capped_backoff(self):
        with mock.patch.object(assets.time, 'time', return_value=784111770):
            self.assertEqual(assets.retry_delay('Sun, 06 Nov 1994 08:49:37 GMT', 0), 7)
        self.assertEqual(assets.retry_delay('600', 0), 30)
        self.assertEqual(assets.retry_delay('invalid', 3), 16)

    def test_polyhaven_texture_and_wikimedia_license(self):
        def get_json(url):
            if 'wikimedia' in url:
                return {'query': {'pages': {'1': {'title': 'File:X.jpg', 'imageinfo': [{
                    'url': 'https://upload.wikimedia.org/wikipedia/commons/a/ab/X.jpg', 'descriptionurl': 'https://commons/x',
                    'extmetadata': {'License': {'value': 'cc-by-sa-4.0'}}}]}}}}
            if 'polyhaven.com/info' in url:
                return {'type': 1, 'name': 'Sandstone', 'authors': {'Rob Tuytel': 'All'}}
            if 'polyhaven.com/files' in url:
                return {'Diffuse': {'1k': {'jpg': {'url': 'https://dl.polyhaven.org/d.jpg'}}},
                        'nor_gl': {'1k': {'jpg': {'url': 'https://dl.polyhaven.org/n.jpg'}}}}
            raise AssertionError(url)
        with TemporaryDirectory() as tmp, mock.patch.object(assets, 'get_json', get_json), \
                mock.patch.object(assets, 'http', lambda url, **k: (b'jpeg-bytes', url)):
            info, folder = assets.resolve(Path(tmp), 'polyhaven:sandstone@1k')
            self.assertEqual((info['kind'], info['license']), ('texture', 'CC0-1.0'))
            self.assertEqual(sorted(info['files']), ['color.jpg', 'normal_gl.jpg'])
            again, _ = assets.resolve(Path(tmp), 'polyhaven:sandstone@1k')
            self.assertEqual(again['files'], info['files'])
            with self.assertRaises(assets.LicenseError):
                assets.resolve(Path(tmp), 'wikimedia:File:X.jpg')
            self.assertFalse(any(p.name.startswith('.fetch-') for p in (Path(tmp) / 'assets-cache').iterdir()))

    def test_commons_thumbnail_rewrite(self):
        self.assertEqual(assets.commons_thumb('https://upload.wikimedia.org/wikipedia/commons/8/83/A.jpg'),
                         'https://upload.wikimedia.org/wikipedia/commons/thumb/8/83/A.jpg/3000px-A.jpg')
        self.assertEqual(assets.commons_thumb('https://example.org/a.jpg'), 'https://example.org/a.jpg')

    def test_direct_url_rejects_landing_page_instead_of_caching_it(self):
        url = 'https://kenney.nl/assets/pack.zip'
        final = 'https://kenney.nl/assets/pack'
        with TemporaryDirectory() as tmp, mock.patch.object(assets, 'http', return_value=(b'\n<!DOCTYPE html>', final)):
            with self.assertRaisesRegex(ValueError, 'web page instead of an asset'):
                assets.resolve(Path(tmp), f'url:{url}')
            self.assertFalse(assets.cache_dir(Path(tmp), f'url:{url}').exists())

        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as archive:
            archive.writestr('models/Block.glb', b'glTF-fixture')
        with TemporaryDirectory() as tmp, mock.patch.object(assets, 'http', return_value=(data.getvalue(), final)):
            info, _ = assets.resolve(Path(tmp), f'url:{url}')
            self.assertEqual((info['kind'], list(info['files'])), ('archive', ['models/Block.glb']))

    def test_resolver_provider_fixtures(self):
        glacier = 'https://upload.wikimedia.org/wikipedia/commons/a/ab/Glacier.jpg'
        download = 'https://files.example/asset'
        ticket = 'https://www.blenderkit.com/api/v1/download'
        khronos = 'https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models/Fox'
        blender_id = '12345678-1234-1234-1234-123456789012'
        fixture = io.BytesIO()
        with zipfile.ZipFile(fixture, 'w') as archive:
            archive.writestr('Pavers_Color.jpg', b'color')
            archive.writestr('Pavers_NormalGL.jpg', b'normal')
        providers = {
            'ambientcg:Pavers@1K': ([{'foundAssets': [{'dataType': 'Material', 'downloadFolders': {'default': {
                'downloadFiletypeCategories': {'zip': {'downloads': [{'attribute': '1K-JPG', 'fullDownloadPath': download}]}}
            }}}]}], 'texture', 'CC0-1.0', ['color.jpg', 'normal_gl.jpg']),
            'fontsource:archivo-black': ([{'family': 'Archivo Black', 'weights': [400], 'license': 'OFL-1.1',
                'variants': {'400': {'normal': {'latin': {'url': {'ttf': download + '.ttf'}}}}}}],
                'font', 'OFL-1.1', ['archivo-black-400-normal.ttf']),
            'khronos:Fox': ([{'legal': [{'license': 'CC0', 'artist': 'Model author'},
                                       {'license': 'CC-BY 4.0', 'artist': 'Texture author'}]},
                              [{'type': 'file', 'name': 'Fox.gltf', 'download_url': download + '.gltf'},
                               {'type': 'file', 'name': 'Fox.bin', 'download_url': download + '.bin'}]],
                            'model', 'CC-BY-4.0 AND CC0-1.0', ['Fox.bin', 'Fox.gltf']),
            'wikimedia:Glacier.jpg': ([{'query': {'pages': {'1': {'title': 'File:Glacier.jpg', 'imageinfo': [{
                'url': glacier, 'thumburl': assets.commons_thumb(glacier), 'descriptionurl': 'https://commons.example',
                'extmetadata': {'License': {'value': 'cc-by-4.0'}, 'Artist': {'value': '<b>Author</b>'}}}]}}}}],
                'image', 'CC-BY-4.0', ['image.jpg']),
            'openverse:glacier': ([{'license': 'by', 'license_version': '2.0', 'url': glacier, 'width': 9000}],
                                  'image', 'CC-BY-2.0', ['image.jpg']),
            'met:12': ([{'isPublicDomain': True, 'primaryImage': download, 'title': 'Vase'}], 'image', 'CC0-1.0', ['image.jpg']),
            'nasa:3D Models/Hubble.glb': ([], 'model', 'LicenseRef-NASA-Media-Guidelines', ['Hubble.glb']),
            f'blenderkit:{blender_id}': ([{'license': 'cc_zero', 'isFree': True,
                                         'files': [{'fileType': 'blend', 'downloadUrl': ticket}]}, {'filePath': download}],
                                        'blend', 'CC0-1.0', ['asset.blend']),
            'url:https://kenney.nl/assets/model.glb': ([], 'model', 'CC0-1.0', ['model.glb']),
        }

        def download_fixture(url, **kwargs):
            if url.startswith(khronos) and url.endswith('.glb'):
                raise ValueError('Model has glTF files only')
            return (fixture.getvalue() if provider.startswith('ambientcg:') else b'asset'), url

        with TemporaryDirectory() as tmp:
            for provider, (responses, kind, license, files) in providers.items():
                with self.subTest(provider=provider), mock.patch.object(assets, 'get_json', side_effect=responses) as api, \
                        mock.patch.object(assets, 'http', side_effect=download_fixture) as http:
                    info, _ = assets.resolve(Path(tmp), provider)
                    self.assertEqual((info['kind'], info['license'], sorted(info['files'])), (kind, license, files))
                    self.assertEqual(api.call_count, len(responses))
                    if provider.startswith(('openverse:', 'wikimedia:')):
                        self.assertEqual(http.call_args.args[0], assets.commons_thumb(glacier))

    def test_provider_rejections_before_download(self):
        rejected = {
            'openverse:no-license': {'url': 'https://example.com/unknown.jpg'},
            'openverse:restricted': {'license': 'by-nc'},
            'fontsource:restricted': {'license': 'GPL'},
            'khronos:Duck': {'legal': [{'license': 'SCEA'}]},
            'khronos:DamagedHelmet': {'legal': [{'license': 'CC-BY-NC'}]},
            'met:123': {'isPublicDomain': False, 'primaryImage': 'https://example.com/art.jpg'},
            'blenderkit:12345678-1234-1234-1234-123456789012': {'license': 'cc_zero', 'isFree': False},
        }
        with TemporaryDirectory() as tmp:
            for provider, response in rejected.items():
                with self.subTest(provider=provider), mock.patch.object(assets, 'get_json', return_value=response), \
                        mock.patch.object(assets, 'http', side_effect=lambda url: (b'fixture', url)) as http:
                    with self.assertRaises(assets.LicenseError):
                        assets.resolve(Path(tmp), provider)
                    http.assert_not_called()

    def test_openverse_uses_provider_preview_for_wikimedia_original(self):
        thumbnail = 'https://api.openverse.org/v1/images/example/thumb/'
        metadata = {'license': 'cc0', 'width': 1900, 'thumbnail': thumbnail,
                    'url': 'https://upload.wikimedia.org/wikipedia/commons/a/ab/Original.svg'}
        with TemporaryDirectory() as tmp, mock.patch.object(assets, 'get_json', return_value=metadata), \
                mock.patch.object(assets, 'http', return_value=(b'jpeg', thumbnail)) as http:
            info, _ = assets.resolve(Path(tmp), 'openverse:example')
            http.assert_called_once_with(thumbnail)
            self.assertEqual(list(info['files']), ['image.jpg'])


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'needs ffmpeg')
class AnimatedGif(unittest.TestCase):
    def test_animated_gif_becomes_video_frames(self):
        with TemporaryDirectory() as tmp:
            gif = Path(tmp) / 'screen.gif'
            subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=red:s=160x120:d=1.5',
                            '-f', 'lavfi', '-i', 'color=c=blue:s=160x120:d=1.5', '-filter_complex',
                            '[0][1]concat=n=2:v=1:a=0,fps=10', str(gif)], check=True)
            still = Path(tmp) / 'still.gif'
            subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=green:s=160x120:d=1',
                            '-frames:v', '1', str(still)], check=True)
            out = ingest.ingest(Path(tmp) / 'jobs', str(gif), 'composition')
            self.assertEqual(out['kind'], 'video')
            self.assertGreaterEqual(len(out['frames']), 2)
            self.assertEqual(ingest.ingest(Path(tmp) / 'jobs', str(still))['kind'], 'image')


if __name__ == '__main__':
    unittest.main()
