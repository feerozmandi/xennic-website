#!/usr/bin/env python3
"""Synthetic forward-auth endpoint, disposable CI only; not an OAuth proxy."""
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        cookies = (part.strip() for part in self.headers.get('Cookie', '').split(';'))
        self.send_response(202 if '__Host-preview_gate=ci-valid' in cookies else 401)
        self.end_headers()

    def log_message(self, *args):
        pass


HTTPServer(('0.0.0.0', 4180), Handler).serve_forever()
