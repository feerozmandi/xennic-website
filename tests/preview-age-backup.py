#!/usr/bin/env python3
import io
import importlib.util
import tarfile
import tempfile
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('age_backup_test', Path(__file__).resolve().parents[1] / 'scripts/preview-age-backup.py')
age = importlib.util.module_from_spec(spec)
spec.loader.exec_module(age)


class FormatTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / 'db'
        self.db.write_bytes(b'synthetic database dump')
        self.media = self.root / 'media.tgz'

    def tar(self, name='asset.png', kind=tarfile.REGTYPE, data=b'fixture'):
        with tarfile.open(self.media, 'w:gz') as archive:
            item = tarfile.TarInfo(name)
            item.type = kind
            if kind == tarfile.REGTYPE:
                item.size = len(data)
                archive.addfile(item, io.BytesIO(data))
            else:
                item.linkname = '/etc/passwd'
                archive.addfile(item)

    def test_metadata_includes_commit_migrations_and_media_hashes(self):
        self.tar('./asset.png')
        data = age._metadata(self.db, self.media, 'a' * 40, [{'name': 'baseline', 'batch': 1}])
        self.assertEqual(data['program_commit'], 'a' * 40)
        self.assertEqual(data['migrations'], [{'name': 'baseline', 'batch': 1}])
        self.assertEqual(data['media_files'][0]['path'], 'asset.png')
        self.assertEqual(len(data['media_files'][0]['sha256']), 64)

    def test_reject_traversal_and_links(self):
        for name, kind in [('../escape', tarfile.REGTYPE), ('/absolute', tarfile.REGTYPE), ('link', tarfile.SYMTYPE), ('hardlink', tarfile.LNKTYPE)]:
            self.tar(name, kind)
            with self.assertRaises(age.BackupError): age._media_inventory(self.media)

    def test_reject_duplicate_normalized_names(self):
        with tarfile.open(self.media, 'w:gz') as archive:
            for name in ('file', './file'):
                item = tarfile.TarInfo(name)
                archive.addfile(item, io.BytesIO())
        with self.assertRaises(age.BackupError): age._media_inventory(self.media)

    def test_reject_bad_migration_and_commit(self):
        self.tar()
        for commit, ledger in [('bad', []), ('a' * 40, [{'name': 'bad migration', 'batch': 1}]), ('a' * 40, [{'name': 'baseline', 'batch': -1}])]:
            with self.assertRaises(age.BackupError): age._metadata(self.db, self.media, commit, ledger)

    def test_reject_public_working_directory(self):
        self.root.chmod(0o755)
        with self.assertRaises(age.BackupError): age._private_dir(self.root)


if __name__ == '__main__': unittest.main()
