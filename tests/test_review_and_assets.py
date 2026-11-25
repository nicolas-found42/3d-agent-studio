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
        self.assertEqual(review.decide(findings(text_readable=0.1))['verdict'], 'fix')

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
        with mock.patch('urllib.request.urlopen', fake), mock.patch('time.sleep'):
            self.assertEqual(assets.http('https://x'), (b'ok', 'https://x/final'))
        with self.assertRaises(ValueError):
            assets.http('http://insecure.example/x')

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
            if 'wikimedia' in url:
                return {'query': {'pages': {'1': {'title': 'File:X.jpg', 'imageinfo': [{
                    'url': 'https://upload.wikimedia.org/wikipedia/commons/a/ab/X.jpg', 'descriptionurl': 'https://commons/x',
                    'extmetadata': {'License': {'value': 'cc-by-sa-4.0'}}}]}}}}
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
