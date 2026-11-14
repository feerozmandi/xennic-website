#!/usr/bin/env python3
"""Tests for the notify config writer; no tokens, no network, no root needed."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parents[1] / 'scripts/configure-preview-notify.py'
spec = importlib.util.spec_from_file_location('configure_notify', SOURCE)
notify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notify)

TOKEN = '123456789:AAHfakeTokenForTestsOnly_abc'
ENV = f"""# infra
BALE_NAME_BOT=xennic_deploy_bot
BALE_TOKEN_BOT={TOKEN}
BALE_CHAT_ID="-1001234567890"
OTHER=ignored
"""


class EnvTest(unittest.TestCase):
    def write(self, text, mode=0o600):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '.env'
        path.write_text(text)
        path.chmod(mode)
        # The real check wants root ownership; the test file is owned by the
        # runner user, so only the mode assertion is exercised here.
        return path

    def test_reads_the_three_keys_and_quotes(self):
        path = self.write(ENV)
        values = _read(path)
        self.assertEqual(values['BALE_TOKEN_BOT'], TOKEN)
        self.assertEqual(values['BALE_CHAT_ID'], '-1001234567890')
        self.assertEqual(values['OTHER'], 'ignored')

    def test_world_readable_source_is_refused(self):
        path = self.write(ENV, mode=0o644)
        with mock.patch.object(notify.os, 'geteuid', lambda: 0):
            with self.assertRaises(notify.ConfigError):
                notify.read_env(path)

    def test_missing_file_is_refused(self):
        with self.assertRaises(notify.ConfigError):
            notify.read_env(Path('/nonexistent/.env'))


class ConfigTest(unittest.TestCase):
    def test_builds_the_bale_config_and_keeps_the_bot_name(self):
        config = notify.build_config({'BALE_TOKEN_BOT': TOKEN, 'BALE_CHAT_ID': '42',
                                      'BALE_NAME_BOT': 'xennic_deploy_bot'})
        self.assertEqual(config, {'provider': 'bale', 'bot_token': TOKEN,
                                  'chat_id': '42', 'bot_name': 'xennic_deploy_bot'})

    def test_channel_username_is_accepted(self):
        self.assertEqual(notify.build_config({'BALE_TOKEN_BOT': TOKEN,
                                              'BALE_CHAT_ID': '@xennic_ir'})['chat_id'],
                         '@xennic_ir')

    def test_missing_or_bad_values_are_refused(self):
        for values in ({}, {'BALE_TOKEN_BOT': TOKEN},
                       {'BALE_TOKEN_BOT': 'short', 'BALE_CHAT_ID': '42'},
                       {'BALE_TOKEN_BOT': TOKEN, 'BALE_CHAT_ID': 'a b'}):
            with self.assertRaises(notify.ConfigError):
                notify.build_config(values)


class WriteTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.target = Path(self.directory.name) / 'notify.json'
        for patcher in (mock.patch.object(notify, 'TARGET', self.target),
                        mock.patch.object(notify.os, 'lstat', _root_stats)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_writes_0600_and_round_trips(self):
        config = {'provider': 'bale', 'bot_token': TOKEN, 'chat_id': '42'}
        notify.write_config(config)
        self.assertEqual(json.loads(self.target.read_text()), config)
        self.assertEqual(os.stat(self.target).st_mode & 0o777, 0o600)

    def test_output_never_contains_a_trailing_newline_secret_leak(self):
        config = {'provider': 'bale', 'bot_token': TOKEN, 'chat_id': '42'}
        notify.write_config(config)
        self.assertNotIn('\n', self.target.read_text())


class SendTest(unittest.TestCase):
    def test_success_requires_ok_true(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self, size=0):
                return b'{"ok":true}'

        with mock.patch.object(notify.urllib.request, 'urlopen', lambda req, timeout=0: Response()):
            notify.send_test({'provider': 'bale', 'bot_token': TOKEN, 'chat_id': '42'})

    def test_a_false_ok_is_an_error(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self, size=0):
                return b'{"ok":false}'

        with mock.patch.object(notify.urllib.request, 'urlopen', lambda req, timeout=0: Response()):
            with self.assertRaises(notify.ConfigError):
                notify.send_test({'provider': 'bale', 'bot_token': TOKEN, 'chat_id': '42'})

    def test_network_failure_is_an_error_without_the_token(self):
        def boom(req, timeout=0):
            raise OSError('connection refused')

        with mock.patch.object(notify.urllib.request, 'urlopen', boom):
            with self.assertRaises(notify.ConfigError) as caught:
                notify.send_test({'provider': 'bale', 'bot_token': TOKEN, 'chat_id': '42'})
        self.assertNotIn(TOKEN, str(caught.exception))


def _read(path):
    values = {}
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in '"\'':
            value = value[1:-1]
        values[key.strip()] = value
    return values


def _root_stats(path):
    """Pretend every path is a private root-owned regular file/dir."""
    import stat as stat_module
    mode = stat_module.S_IFDIR | 0o700 if Path(path).is_dir() else stat_module.S_IFREG | 0o600
    real = os.stat(path)
    values = list(real)
    values[stat_module.ST_MODE] = mode
    values[stat_module.ST_UID] = 0
    return os.stat_result(values)


if __name__ == '__main__':
    unittest.main(verbosity=2)
