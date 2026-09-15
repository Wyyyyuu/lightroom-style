import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('setup_lightroom', ROOT / 'lightroom-style/scripts/setup_lightroom.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / 'bundle'
        self.source.mkdir()
        for name in setup.PLUGIN_FILES:
            (self.source / name).write_bytes(name.encode())
        self.destination = self.root / 'Modules' / setup.PLUGIN_NAME

    def test_install_and_repeat_preserve_runtime_files(self):
        result = setup.install_plugin(self.source, self.destination)
        self.assertEqual(result['status'], 'installed')
        self.assertFalse(result['connection_verified'])
        for name in setup.PLUGIN_FILES:
            self.assertEqual((self.destination / name).read_bytes(), name.encode())
        log = self.destination / 'bridge-startup.log'
        log.write_text('keep', encoding='utf-8')
        result = setup.install_plugin(self.source, self.destination)
        self.assertEqual(result['status'], 'already_installed')
        self.assertEqual(log.read_text(encoding='utf-8'), 'keep')

    def test_different_installation_is_not_overwritten(self):
        self.destination.mkdir(parents=True)
        existing = self.destination / 'Info.lua'
        existing.write_bytes(b'user version')
        result = setup.install_plugin(self.source, self.destination)
        self.assertEqual(result['status'], 'existing_installation_differs')
        self.assertEqual(existing.read_bytes(), b'user version')
        self.assertEqual(len(list(self.destination.iterdir())), 1)

    def test_missing_bundle_does_not_create_destination(self):
        (self.source / 'Init.lua').rename(self.source / 'Init.missing')
        with self.assertRaises(ValueError):
            setup.install_plugin(self.source, self.destination)
        self.assertFalse(self.destination.exists())

    def test_invalid_destination_is_rejected(self):
        with self.assertRaises(ValueError):
            setup.install_plugin(self.source, self.root / 'unrelated')
        self.assertFalse((self.root / 'unrelated').exists())


if __name__ == '__main__':
    unittest.main()
