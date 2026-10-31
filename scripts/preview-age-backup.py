#!/usr/bin/env python3
"""Age-encrypted DB/media bundle format. No privileged CLI or transport.

Not an operational backup helper: no authenticated sender provenance, offsite
transport or snapshot coordination is implemented. Age authenticates ciphertext
integrity, not who created it: anyone with the recipient can create a bundle.
Callers must quiesce writers and use a trusted private working directory.
Plaintext temporary files are created during packing and restoration. A caller
must not apply either restored file unless restore_bundle returns successfully
and its provenance and trusted release metadata have been independently verified.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile

AGE = '/usr/bin/age'
ENV = {'PATH': '/usr/bin:/bin', 'HOME': '/nonexistent', 'LANG': 'C'}
MAX_METADATA = 16 * 1024 * 1024
MAX_MEDIA_FILES = 100000
MAX_MEDIA_BYTES = 1024 ** 4


class BackupError(RuntimeError):
    pass


def _private_dir(path):
    path = Path(path)
    s = path.lstat()
    if not path.is_absolute() or not stat.S_ISDIR(s.st_mode) or s.st_uid != os.geteuid() or s.st_mode & 0o077:
        raise BackupError('working directory must be private and owned by the caller')
    return path


def _hash(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for part in iter(lambda: f.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def _media_inventory(path):
    result = []
    seen = set()
    total = 0
    with tarfile.open(path, 'r:gz') as archive:
        for member in archive:
            name = member.name
            if len(name) > 512 or '\\' in name or name.startswith('/'):
                raise BackupError('unsafe media path')
            parts = PurePosixPath(name).parts
            if '..' in parts:
                raise BackupError('unsafe media path')
            normalized = str(PurePosixPath(name))
            if normalized in seen:
                raise BackupError('duplicate media path')
            seen.add(normalized)
            if member.isdir():
                continue
            if not member.isfile() or normalized == '.':
                raise BackupError('unsupported media entry')
            total += member.size
            if len(result) >= MAX_MEDIA_FILES or total > MAX_MEDIA_BYTES:
                raise BackupError('media archive exceeds safety limits')
            source = archive.extractfile(member)
            if source is None:
                raise BackupError('unreadable media entry')
            digest = hashlib.sha256()
            with source:
                for chunk in iter(lambda: source.read(1024 * 1024), b''):
                    digest.update(chunk)
            result.append({'path': normalized, 'size': member.size, 'sha256': digest.hexdigest()})
    return sorted(result, key=lambda item: item['path'])


def _metadata(database, media, program_commit, migrations):
    if not isinstance(program_commit, str) or not re.fullmatch('[0-9a-f]{40}', program_commit):
        raise BackupError('invalid program commit')
    if (not isinstance(migrations, list) or len(migrations) > 10000 or
        any(not isinstance(x, dict) or set(x) != {'name', 'batch'} or
            not isinstance(x['name'], str) or not re.fullmatch('[A-Za-z0-9_-]{1,200}', x['name']) or
            type(x['batch']) is not int or x['batch'] < 0 for x in migrations)):
        raise BackupError('invalid migration ledger')
    if len({x['name'] for x in migrations}) != len(migrations):
        raise BackupError('duplicate migration')
    return {'format': 'xennic-preview-age-v1', 'program_commit': program_commit,
            'migrations': sorted(migrations, key=lambda item: item['name']),
            'database_sha256': _hash(database), 'media_archive_sha256': _hash(media),
            'media_files': _media_inventory(media)}


def _age(args, source, destination):
    try:
        with open(source, 'rb') as src, open(destination, 'xb', buffering=0) as dst:
            os.fchmod(dst.fileno(), 0o600)
            result = subprocess.run([AGE, *args], stdin=src, stdout=dst, stderr=subprocess.DEVNULL,
                                    env=ENV, check=False)
            if result.returncode != 0:
                raise BackupError('age operation failed')
            os.fsync(dst.fileno())
    except OSError as exc:
        raise BackupError('age operation unavailable') from exc


def create_bundle(database, media, output, recipient, program_commit, migrations):
    output = Path(output)
    parent = _private_dir(output.parent)
    if not re.fullmatch(r'age1[023456789acdefghjklmnpqrstuvwxyz]{58}', recipient):
        raise BackupError('invalid age recipient')
    metadata = _metadata(database, media, program_commit, migrations)
    raw = json.dumps(metadata, sort_keys=True, separators=(',', ':')).encode()
    if len(raw) > MAX_METADATA:
        raise BackupError('metadata too large')
    with tempfile.TemporaryDirectory(prefix='.age-pack-', dir=parent) as scratch:
        archive = Path(scratch) / 'bundle.tar'
        encrypted = Path(scratch) / 'bundle.age'
        meta = Path(scratch) / 'metadata.json'
        meta.write_bytes(raw)
        os.chmod(meta, 0o600)
        with tarfile.open(archive, 'w') as tar:
            for name, path in [('metadata.json', meta), ('database.dump', database), ('media.tar.gz', media)]:
                tar.add(path, arcname=name, recursive=False)
        os.chmod(archive, 0o600)
        _age(['-r', recipient], archive, encrypted)
        os.link(encrypted, output)  # atomic, no overwrite; same private filesystem
    return metadata


def restore_bundle(encrypted, identity, directory):
    directory = _private_dir(directory)
    published = []
    try:
        with tempfile.TemporaryDirectory(prefix='.age-restore-', dir=directory) as scratch:
            scratch = Path(scratch)
            archive = scratch / 'bundle.tar'
            # Authenticate the whole age file before inspecting or applying its contents.
            _age(['-d', '-i', str(identity)], encrypted, archive)
            with tarfile.open(archive, 'r:') as tar:
                members = tar.getmembers()
                if (len(members) != 3 or {m.name for m in members} != {'metadata.json', 'database.dump', 'media.tar.gz'} or
                    any(not m.isfile() for m in members)):
                    raise BackupError('invalid bundle entries')
                for member in members:
                    if member.name == 'metadata.json' and member.size > MAX_METADATA:
                        raise BackupError('metadata too large')
                    path = scratch / member.name
                    source = tar.extractfile(member)
                    if source is None:
                        raise BackupError('invalid bundle entry')
                    with source, open(path, 'xb') as target:
                        os.fchmod(target.fileno(), 0o600)
                        shutil.copyfileobj(source, target, 1024 * 1024)
            try:
                meta = json.loads((scratch / 'metadata.json').read_bytes())
                if not isinstance(meta, dict) or set(meta) != {'format', 'program_commit', 'migrations', 'database_sha256', 'media_archive_sha256', 'media_files'}:
                    raise BackupError('invalid metadata')
                expected = _metadata(scratch / 'database.dump', scratch / 'media.tar.gz', meta['program_commit'], meta['migrations'])
                if meta != expected:
                    raise BackupError('backup content does not match metadata')
            except (ValueError, TypeError, KeyError, UnicodeError, tarfile.TarError) as exc:
                raise BackupError('invalid backup content') from exc
            for name, target in [('database.dump', 'db.restored'), ('media.tar.gz', 'media.restored')]:
                dest = directory / target
                os.link(scratch / name, dest)
                published.append(dest)
            return meta
    except Exception:
        for path in published:
            path.unlink(missing_ok=True)
        raise
