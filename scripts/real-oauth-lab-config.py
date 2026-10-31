#!/usr/bin/env python3
"""Write an OAuth2 Proxy configuration to a new private local file, never stdout."""
import base64
import getpass
import ipaddress
import json
import os
from pathlib import Path
import secrets
import sys
import warnings


def render_config(client_id: str, client_secret: str, proxy_ip: str, cookie_key: str) -> str:
    ip = ipaddress.ip_address(proxy_ip)
    if ip.version != 4 or not ip.is_private:
        raise ValueError('expected a private IPv4 proxy address')
    for value in (client_id, client_secret):
        if not value or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError('empty or invalid credential')
    if len(base64.urlsafe_b64decode(cookie_key)) != 32:
        raise ValueError('invalid generated cookie key')
    quote = lambda value: json.dumps(value, ensure_ascii=True)
    return '\n'.join([
        'provider = "github"',
        'github_users = ["feerozmandi"]',
        'email_domains = ["*"]',
        'scope = "user:email"',
        'reverse_proxy = true',
        'trusted_proxy_ips = [' + quote(str(ip) + '/32') + ']',
        'http_address = "0.0.0.0:4180"',
        'redirect_url = "https://preview.xennic.ir/oauth2/callback"',
        'upstreams = ["static://202"]',
        'whitelist_domains = ["preview.xennic.ir"]',
        'cookie_name = "__Host-preview_gate"',
        'cookie_secure = true',
        'cookie_httponly = true',
        'cookie_samesite = "lax"',
        'cookie_expire = "1h"',
        'cookie_refresh = "0"',
        'skip_jwt_bearer_tokens = false',
        'skip_auth_preflight = false',
        'pass_basic_auth = false',
        'pass_authorization_header = false',
        'set_authorization_header = false',
        'pass_access_token = false',
        'set_xauthrequest = false',
        'request_logging = false',
        'auth_logging = false',
        'client_id = ' + quote(client_id),
        'client_secret = ' + quote(client_secret),
        'cookie_secret = ' + quote(cookie_key),
        '',
    ])


def main() -> int:
    if len(sys.argv) != 3:
        print('STOP: expected new config path and Caddy IP', file=sys.stderr)
        return 1
    path = Path(sys.argv[1])
    # Refuse to fall back to an echoing password prompt, including with redirected stdin.
    warnings.simplefilter('error', getpass.GetPassWarning)
    try:
        with open('/dev/tty', 'r+', encoding='utf-8') as tty:
            client_id = getpass.getpass('Local GitHub OAuth App Client ID (hidden): ', stream=tty).strip()
            client_secret = getpass.getpass('Local GitHub OAuth App Client Secret (hidden): ', stream=tty).strip()
        key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('ascii')
        content = render_config(client_id, client_secret, sys.argv[2], key)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as output:
                output.write(content)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
    except (OSError, ValueError, getpass.GetPassWarning, EOFError, KeyboardInterrupt):
        print('STOP: could not safely create private OAuth configuration', file=sys.stderr)
        return 1
    print('PASS: private OAuth configuration created (values not printed)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
