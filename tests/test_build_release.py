"""Verify distribution boundaries without launching Lightroom."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release_builder', ROOT / 'tools/build_release.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.manifest = self.root / 'release-manifest.json'
        self.entries = json.loads((ROOT / 'release-manifest.json').read_text(encoding='utf-8'))['files']
        for entry in self.entries:
            target = self.root / entry
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / entry, target)
        self.patch = patch.multiple(builder, ROOT=self.root, MANIFEST=self.manifest)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def save_manifest(self, entries):
        self.manifest.write_text(json.dumps({'files': entries}), encoding='utf-8')

    def test_both_archives_are_self_contained_and_licensed(self):
        output = builder.build(builder.checked_files())
        for filename, prefix in [('photo-style-match-repository.zip', 'photo-style-match-repository'),
                                 ('photo-style-match-skill.zip', 'photo-style-match')]:
            with ZipFile(output / filename) as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(archive.read(prefix + '/LICENSE'), (ROOT / 'LICENSE').read_bytes())
                self.assertFalse(any('/evals/' in name or '/private-notes/' in name or name.endswith('/VALIDATION.md')
                                     for name in archive.namelist()))
        clean = output / 'photo-style-match-repository'
        with patch.multiple(builder, ROOT=clean, MANIFEST=clean / 'release-manifest.json'):
            self.assertEqual(builder.checked_files(), sorted(self.entries))

    def test_standalone_license_is_required(self):
        self.save_manifest([entry for entry in self.entries if entry != 'photo-style-match/LICENSE'])
        with self.assertRaisesRegex(ValueError, 'licenses must be packaged'):
            builder.checked_files()

    def test_license_mismatch_is_rejected(self):
        (self.root / 'photo-style-match/LICENSE').write_text('Different terms', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'license mismatch'):
            builder.checked_files()

    def test_private_documents_and_experiments_cannot_be_added(self):
        for entry in ['VALIDATION.md', 'docs/DEVELOPMENT.md', 'docs/EVALUATION.md',
                      'photo-style-match/evals/evals.json', 'experiments/trial/SKILL.md',
                      'photo-sessions/session.md']:
            with self.subTest(entry=entry):
                path = self.root / entry
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('Private fixture', encoding='utf-8')
                self.save_manifest([*self.entries, entry])
                with self.assertRaisesRegex(ValueError, 'Unsafe release path'):
                    builder.checked_files()


if __name__ == '__main__':
    unittest.main()
