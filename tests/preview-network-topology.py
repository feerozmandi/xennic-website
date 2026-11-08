#!/usr/bin/env python3
"""Read-only topology checks; the real Compose/network path is tested separately in CI."""
import copy
import importlib.machinery
import importlib.util
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
path = Path(__file__).resolve().parents[1] / 'scripts/preview-fixed-operations.py'
spec = importlib.util.spec_from_file_location('fixed_network_test', path)
fixed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixed)


def valid():
    return {'services': {
        'app': {'image': 'ghcr.io/feerozmandi/xennic-website@sha256:' + 'a' * 64,
                'pull_policy': 'never', 'networks': {'default': {}, 'gateway': {}},
                'volumes': [{'type': 'volume', 'source': 'preview_media', 'target': '/app/media'}]},
        'postgres': {'image': 'postgres:16.14-bookworm', 'networks': {'default': {}},
                     'volumes': [{'type': 'volume', 'source': 'preview_db', 'target': '/var/lib/postgresql/data'}]},
    }, 'volumes': {k: {'name': 'xennic-preview_' + k} for k in ('preview_db', 'preview_media')},
        'networks': {k: {'name': 'xennic-preview_' + k, 'internal': True} for k in ('default', 'gateway')}}


class TopologyTest(unittest.TestCase):
    def test_exact_isolated_stack(self):
        fixed.validate_topology(valid())

    def test_exposed_or_unrecognized_resources_rejected(self):
        for mutation in (
            lambda x: x['services']['app'].update(ports=[{'host_ip': '127.0.0.1', 'published': '3000'}]),
            lambda x: x['services']['postgres'].update(ports=[{'published': '5432'}]),
            lambda x: x['services']['postgres']['networks'].update(gateway={}),
            lambda x: x['services']['app']['networks'].update(untrusted={}),
            lambda x: x['services']['app'].update(network_mode='host'),
            lambda x: x['services']['app'].update(privileged=True),
            lambda x: x['services'].update(gate={}),
            lambda x: x['networks']['gateway'].update(internal=False),
            lambda x: x['networks']['default'].update(external=True),
            lambda x: x['networks']['gateway'].update(name='other-project'),
            lambda x: x['volumes']['preview_db'].update(external=True),
        ):
            with self.subTest(mutation=mutation):
                config = valid(); mutation(config)
                with self.assertRaises(fixed.Rejected): fixed.validate_topology(config)


if __name__ == '__main__': unittest.main()
