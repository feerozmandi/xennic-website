#!/usr/bin/python3
"""Write the deployment notification config from the existing infra env file.

The bot credentials already live in one place on the host
(`/home/xennic/xennic-infra/.env`). Rather than copying them by hand into a
second file, this reads the three Bale keys from that file and writes
`/srv/xennic-preview/secrets/notify.json` as root, 0600, atomically.

    sudo python3 configure-preview-notify.py                       # write config
    sudo python3 configure-preview-notify.py --send-test           # write + send one message
    sudo python3 configure-preview-notify.py --source /path/.env   # other env file

It never prints a token: the summary shows only the provider, the chat id and
the token's length. A `--source` file that is not root-owned and 0600 is
refused, because a world-readable file with a bot token is the problem this
script is supposed to avoid, not reproduce.
"""
import json
import os
from pathlib import Path
import re
import stat
import sys
import urllib.error
import urllib.request

sys.dont_write_bytecode = True

SOURCE = Path('/home/xennic/xennic-infra/.env')
TARGET = Path('/srv/xennic-preview/secrets/notify.json')
PROVIDER = 'bale'
MAX_SOURCE = 256 * 1024
KEYS = {'token': 'BALE_TOKEN_BOT', 'chat': 'BALE_CHAT_ID', 'name': 'BALE_NAME_BOT'}
TOKEN_RE = re.compile(r'[A-Za-z0-9:_-]{20,200}')
CHAT_RE = re.compile(r'-?\d{1,20}|@[A-Za-z][A-Za-z0-9_]{3,31}')


class ConfigError(RuntimeError):
    pass


def read_env(path):
    """Minimal dotenv reader: KEY=VALUE, optional quotes, comments, no expansion."""
    try:
        info = os.lstat(path)
    except OSError as exc:
        raise ConfigError(f'{path} is missing') from exc
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0:
        raise ConfigError(f'{path} must be a regular file owned by root')
    if info.st_mode & 0o077:
        raise ConfigError(f'{path} is readable by others; chmod 600 it first')
    if info.st_size > MAX_SOURCE:
        raise ConfigError(f'{path} is unexpectedly large')
    values = {}
    for line in Path(path).read_text('utf-8', 'replace').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        key = key.strip()
        if key.startswith('export '):
            key = key[7:].strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in '"\'':
            value = value[1:-1]
        values[key] = value
    return values


def build_config(values):
    token = values.get(KEYS['token'], '')
    chat = values.get(KEYS['chat'], '')
    if not TOKEN_RE.fullmatch(token):
        raise ConfigError(f'{KEYS["token"]} is missing or malformed in the env file')
    if not CHAT_RE.fullmatch(chat):
        raise ConfigError(f'{KEYS["chat"]} is missing or malformed in the env file')
    config = {'provider': PROVIDER, 'bot_token': token, 'chat_id': chat}
    name = values.get(KEYS['name'], '').strip()
    if name and re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', name):
        config['bot_name'] = name
    return config


def write_config(config):
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    info = os.lstat(TARGET.parent)
    if info.st_uid != 0 or info.st_mode & 0o022:
        raise ConfigError(f'{TARGET.parent} is not private to root')
    staged = TARGET.with_name('.notify.staged')
    if os.path.lexists(staged):
        raise ConfigError('a staged config already exists; inspect it by hand')
    payload = json.dumps(config, separators=(',', ':')).encode()
    fd = os.open(staged, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    with os.fdopen(fd, 'wb') as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(staged, 0o600)
    os.replace(staged, TARGET)


def send_test(config):
    body = json.dumps({'chat_id': config['chat_id'],
                       'text': 'Xennic: deployment notifications are connected.',
                       'disable_web_page_preview': True}).encode()
    request = urllib.request.Request(
        f'https://tapi.bale.ai/bot{config["bot_token"]}/sendMessage', data=body,
        method='POST', headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read(8192) or b'{}')
    except (OSError, urllib.error.HTTPError, ValueError) as exc:
        # The reason is useful; the token is never in it because urllib reports
        # only the status, and we discard the body on error.
        raise ConfigError(f'Bale rejected the test message ({type(exc).__name__})') from exc
    if payload.get('ok') is not True:
        raise ConfigError('Bale did not acknowledge the test message')


def main(argv):
    if os.geteuid() != 0:
        print('configure-preview-notify requires root', file=sys.stderr)
        return 1
    source, test = SOURCE, False
    args = argv[1:]
    while args:
        if args[0] == '--send-test':
            test, args = True, args[1:]
        elif args[0] == '--source' and len(args) >= 2:
            source, args = Path(args[1]), args[2:]
        else:
            print('usage: configure-preview-notify.py [--source FILE] [--send-test]', file=sys.stderr)
            return 2
    os.umask(0o077)
    try:
        config = build_config(read_env(source))
        write_config(config)
        print(f'notify.json written: provider={config["provider"]} '
              f'chat={config["chat_id"]} token_length={len(config["bot_token"])}')
        if test:
            send_test(config)
            print('test message accepted by Bale')
    except ConfigError as exc:
        print(f'configure-preview-notify: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
