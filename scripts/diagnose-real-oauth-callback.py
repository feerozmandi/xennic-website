#!/usr/bin/env python3
"""Observe only new OAuth proxy output and emit fixed, non-secret diagnostic labels.

No logs are persisted and no request, credential, callback URL, or response body is
printed. This is read-only with respect to the isolated lab containers.
"""
import os
import re
import selectors
import subprocess
import sys
import time

PROJECT = 'xennic-real-oauth-73c028764aa6'
IMAGE = 'quay.io/oauth2-proxy/oauth2-proxy:v7.15.5@sha256:8498b0d0ef0a7b29686414000a08aee467f02d0299c9ed1e006a8f33fc017916'
TIMEOUT = 240
MAX_LINE = 65536


def classify(line: bytes):
    """Return only fixed labels; never interpolate any untrusted log text."""
    rules = (
        (b'Error while parsing OAuth2 callback:', 'CALLBACK_PARSE_OR_PROVIDER_ERROR'),
        (b'Error while parsing OAuth2 state:', 'STATE_ERROR'),
        (b'Error redeeming code during OAuth2 callback:', 'CODE_REDEMPTION_ERROR'),
        (b'Error creating session during OAuth2 callback:', 'SESSION_ENRICHMENT_ERROR'),
        (b'Error saving session state for ', 'SESSION_SAVE_ERROR'),
        (b'Error with authorization:', 'AUTHORIZATION_ERROR'),
    )
    for needle, label in rules:
        if needle in line:
            extra = ''
            rest = line.split(needle, 1)[1]
            if label == 'SESSION_ENRICHMENT_ERROR':
                if rest.strip() == b'missing github user':
                    extra = ' ACCOUNT_NOT_ALLOWED'
                else:
                    # Exact fixed error format from oauth2-proxy v7.15.5
                    match = re.match(rb'\s*unexpected status "([1-5][0-9]{2})":', rest)
                    if match:
                        extra = ' UPSTREAM_HTTP_' + match.group(1).decode('ascii')
            return 'DIAGNOSIS: ' + label + extra
    return None


def docker_output(args):
    result = subprocess.run(['docker', *args], stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            timeout=15, check=True)
    return result.stdout.decode('utf-8').strip()


def check_gate():
    host = os.environ.get('DOCKER_HOST')
    # Avoid ambiguous CLI precedence between a host override and a context override.
    if host and os.environ.get('DOCKER_CONTEXT'):
        raise ValueError('ambiguous daemon selection')
    if not host:
        current = docker_output(['context', 'show'])
        host = docker_output(['context', 'inspect', current, '--format', '{{(index .Endpoints "docker").Host}}'])
    if not host.startswith('unix://'):
        raise ValueError('not a local daemon')
    ids = docker_output(['ps', '-q', '--filter', 'label=com.docker.compose.project=' + PROJECT,
                         '--filter', 'label=com.docker.compose.service=gate']).splitlines()
    if len(ids) != 1 or not re.fullmatch(r'[a-f0-9]{12,64}', ids[0]):
        raise ValueError('lab gate is not uniquely running')
    fmt = '{{.State.Running}} {{index .Config.Labels "com.docker.compose.project"}} {{index .Config.Labels "com.docker.compose.service"}} {{.HostConfig.LogConfig.Type}} {{.Config.Image}}'
    info = docker_output(['inspect', '--format', fmt, ids[0]])
    if info != 'true ' + PROJECT + ' gate none ' + IMAGE:
        raise ValueError('unexpected gate container')
    return ids[0]


def observe(gate_id):
    proc = subprocess.Popen(['docker', 'attach', '--no-stdin', '--sig-proxy=false', gate_id],
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, start_new_session=True)
    selector = selectors.DefaultSelector()
    selector.register(proc.stdout, selectors.EVENT_READ)
    buffer = bytearray()
    discard = False
    start = time.monotonic()
    try:
        # Docker CLI has no attach-ready event; this checks only that the client did
        # not immediately fail, not that a future callback will produce a log line.
        while time.monotonic() - start < 2:
            if proc.poll() is not None:
                print('STOP: could not attach to the running lab gate; no raw output shown', flush=True)
                return 1
            time.sleep(0.1)
        print('READY: retry sign-in from the lab Firefox; waiting up to four minutes.', flush=True)
        deadline = time.monotonic() + TIMEOUT
        while time.monotonic() < deadline:
            for key, _ in selector.select(timeout=0.5):
                chunk = os.read(key.fd, 4096)
                if not chunk:
                    print('STOP: diagnostic stream ended; no raw output shown', flush=True)
                    return 1
                for byte in chunk:
                    if byte == 10:
                        if not discard:
                            result = classify(buffer)
                            if result:
                                print(result, flush=True)
                                return 0
                        buffer.clear()
                        discard = False
                    elif not discard:
                        if len(buffer) >= MAX_LINE:
                            buffer.clear()
                            discard = True
                        else:
                            buffer.append(byte)
            if proc.poll() is not None:
                print('STOP: diagnostic stream ended; no raw output shown', flush=True)
                return 1
        print('DIAGNOSIS: NO_CLASSIFIED_STANDARD_ERROR_OBSERVED', flush=True)
        return 0
    finally:
        selector.close()
        if proc.poll() is None:
            proc.terminate()  # sig-proxy=false: never signal the container
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
        if proc.stdout:
            proc.stdout.close()


def main():
    try:
        gate = check_gate()
        return observe(gate)
    except (OSError, ValueError, UnicodeError, subprocess.SubprocessError):
        print('STOP: lab gate unavailable or verification failed; no raw output shown', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('DIAGNOSIS: LISTENER_STOPPED_BY_USER', flush=True)
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
