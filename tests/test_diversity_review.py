"""Offline checks for the dev-only poster diversity helper."""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from agent_studio import pipeline

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools' / 'review'))
import diversity  # noqa: E402


class Diversity(unittest.TestCase):
    def test_nearest_compares_separate_fields_and_limits_peers(self):
        def entry(slug, camera, lighting, style, motion):
            return {'slug': slug, 'tags': dict(zip(diversity.TAG_FIELDS, (camera, lighting, style, motion)))}

        examples = [
            entry('subject', 'dolly', 'warm key', 'clay', 'walk'),
            entry('full', 'DOLLY', 'warm key', 'clay', 'walk'),
            entry('same-light', 'handheld', 'warm key', 'clay', 'sit'),
            entry('moved-words', 'walk', 'dolly', 'warm key', 'clay'),
            entry('a-tie', 'orbit', 'sun', 'clay', 'blink'),
            entry('z-tie', 'crane', 'cloud', 'clay', 'jump'),
        ]
        self.assertEqual(diversity.nearest(examples)['subject'], [
            {'slug': 'full', 'similarity': 1.0},
            {'slug': 'same-light', 'similarity': 0.5},
            {'slug': 'a-tie', 'similarity': 0.25},
        ])

    def test_cache_reuses_judgment_only_for_the_same_poster_content(self):
        def call(_state, _questions, log):
            log.append({'model': 'typesafe/jev-1.14-fixture', 'usage': None})
            return {'same_subject_and_composition': {'noul': 0.7}}

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            posters = {name: root / f'{name}.jpg' for name in ('left', 'right')}
            posters['left'].write_bytes(b'left poster fixture')
            posters['right'].write_bytes(b'right poster fixture')

            def judge():
                hashes = {slug: pipeline.digest(path) for slug, path in posters.items()}
                return diversity.judge('left', 'right', posters, hashes, root)

            with mock.patch.object(diversity.review, 'call', side_effect=call) as provider:
                original = judge()
                self.assertEqual(original['disposition'], 'review')
                self.assertEqual(judge(), original)
                self.assertEqual(provider.call_count, 1)
                posters['right'].write_bytes(b'replacement poster fixture')
                revised = judge()
                self.assertNotEqual(revised['sha256'], original['sha256'])
                self.assertEqual(provider.call_count, 2)


if __name__ == '__main__':
    unittest.main()
