#!/usr/bin/env python3
"""Disposable CI-only HTTPS upstream: synthetic GitHub evidence, never production."""
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import BytesIO
import json
from pathlib import Path
import re
import zipfile

FIXTURE = Path('/srv/xennic-preview/config/ci-github-fixture.json')
BASE = '/repos/feerozmandi/xennic-website'


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def reply(self, status, data, content='application/json'):
        self.send_response(status); self.send_header('Content-Type', content); self.send_header('Content-Length', str(len(data)))
        self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        if self.headers.get('Authorization') != 'Bearer synthetic-token':
            return self.reply(401, b'{}')
        data = json.loads(FIXTURE.read_text())
        current = data['current']
        release = data['releases'][current]
        run_id = release['run_number'] + 10000
        if self.path == BASE + '/commits/dev':
            return self.reply(200, json.dumps({'sha': release['commit']}).encode())
        if self.path == BASE + '/actions/workflows/ci.yml/runs?branch=dev&event=push&per_page=100':
            run = {'id': run_id, 'run_number': release['run_number'], 'run_attempt': 1, 'head_sha': release['commit'],
                   'head_branch': 'dev', 'event': 'push', 'status': 'completed', 'conclusion': 'success'}
            return self.reply(200, json.dumps({'workflow_runs': [run]}).encode())
        if self.path == BASE + f'/actions/runs/{run_id}/artifacts?per_page=100':
            return self.reply(200, json.dumps({'artifacts': [{'id': run_id, 'name': 'xennic-preview-release-1', 'expired': False}]}).encode())
        if self.path == BASE + f'/actions/artifacts/{run_id}/zip':
            output = BytesIO()
            evidence = {'version': 1, 'run_id': run_id, 'run_attempt': 1, 'release': release}
            with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('xennic-preview-release.json', json.dumps(evidence))
            return self.reply(200, output.getvalue(), 'application/zip')
        self.reply(404, b'{}')


HTTPServer(('127.0.0.1', 58001), Handler).serve_forever()
