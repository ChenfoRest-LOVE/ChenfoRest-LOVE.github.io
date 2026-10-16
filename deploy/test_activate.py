"""Linux integration tests for archive validation and atomic release switching."""
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('activate', Path(__file__).with_name('activate.py'))
activate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(activate)


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        activate.BASE = root / 'site'
        activate.INCOMING = root / 'incoming'
        (activate.BASE / 'releases').mkdir(parents=True)
        activate.INCOMING.mkdir()

    def bundle(self, revision, extra=None, omit=None):
        with tarfile.open(activate.INCOMING / (revision + '.tar'), 'w',
                          format=tarfile.PAX_FORMAT, pax_headers={'comment': revision}) as archive:
            for name in sorted(activate.REQUIRED - {omit}):
                content = b'[]' if name.endswith('.json') else b'static fixture'
                entry = tarfile.TarInfo(name)
                entry.size = len(content)
                archive.addfile(entry, io.BytesIO(content))
            if extra:
                archive.addfile(extra, io.BytesIO(b'') if extra.isfile() else None)

    def test_release_switch_and_previous(self):
        first, second = 'a' * 40, 'b' * 40
        for revision in (first, second):
            self.bundle(revision)
            activate.install(revision)
        self.assertEqual(activate.release_target(activate.BASE / 'current'), 'releases/' + second)
        self.assertEqual(activate.release_target(activate.BASE / 'previous'), 'releases/' + first)
        activate.switch(activate.release_target(activate.BASE / 'previous'))
        self.assertEqual((activate.BASE / 'current' / '.release-revision').read_text().strip(), first)
        activate.install(first)  # Same commit is safe to republish.

    def test_unsafe_archive_keeps_active_release(self):
        current = 'a' * 40
        self.bundle(current)
        activate.install(current)
        for name, kind in [('assets/../escape', tarfile.REGTYPE),
                           ('assets/link', tarfile.SYMTYPE),
                           ('docs/private.txt', tarfile.REGTYPE)]:
            bad = tarfile.TarInfo(name)
            bad.type = kind
            bad.linkname = '/etc/passwd' if kind == tarfile.SYMTYPE else ''
            self.bundle('b' * 40, extra=bad)
            with self.assertRaises(ValueError):
                activate.install('b' * 40)
            self.assertEqual((activate.BASE / 'current' / '.release-revision').read_text().strip(), current)

    def test_incomplete_release_is_not_activated(self):
        self.bundle('c' * 40, omit='index.html')
        with self.assertRaises(ValueError):
            activate.install('c' * 40)
        self.assertFalse((activate.BASE / 'current').exists())


if __name__ == '__main__':
    unittest.main()
