"""Loopback-only, manual screenshot upload for the experimental Jev classifier."""
from __future__ import annotations
import argparse
import base64
import binascii
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import socket
from threading import Lock
import time
import uuid

import ytt_jev_vision as vision

HTML = Path(__file__).with_suffix('.html')
MAX_BODY = 23 * 1024 * 1024
MONITOR_INTERVAL_SECONDS = 300


def budget_summary():
    """Read-only view of the same permanent reservations used by the classifier."""
    try:
        directory = vision.BUDGET_DIRECTORY
        ledger = directory / 'reservations.jsonl'
        rows = [json.loads(line) for line in ledger.read_text(encoding='utf-8').splitlines()] if ledger.exists() else []
        receipts = {p.stem: json.loads(p.read_text(encoding='utf-8')) for p in (directory / 'receipts').glob('*.json')}
        expected = {r['fingerprint']: r for r in rows}
        if expected != receipts or len(expected) != len(rows):
            raise ValueError('budget_evidence_mismatch')
        if any(r['reserved_yen'] != vision.RESERVATION_YEN for r in rows):
            raise ValueError('invalid_budget_ledger')
        used = sum(r['reserved_yen'] for r in rows)
        remaining = max(0, vision.MAX_YEN - used)
        return {'limit_yen': vision.MAX_YEN, 'reserved_yen': used,
                'remaining_yen': remaining, 'remaining_calls': int((remaining + 1e-10) / vision.RESERVATION_YEN),
                'reservation_per_call_yen': vision.RESERVATION_YEN, 'valid': True}
    except (ValueError, KeyError, TypeError, OSError):
        return {'limit_yen': vision.MAX_YEN, 'remaining_calls': 0, 'valid': False}


def make_server(port=8787, run_root=None):
    root = Path(run_root or vision.ROOT / 'agent_runs/ytt_jev_vision_20261016')
    token = secrets.token_urlsafe(32)
    inference_lock = Lock()
    last_monitor_call = None

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, status, body, kind='application/json; charset=utf-8'):
            payload = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' blob: data:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; connect-src 'self'")
            self.end_headers()
            self.wfile.write(payload)

        def trusted(self, post=False):
            host = '127.0.0.1:' + str(self.server.server_port)
            if self.headers.get('Host') != host:
                return False
            if post:
                return (self.headers.get('Origin') == 'http://' + host
                        and secrets.compare_digest(self.headers.get('X-CSRF-Token', ''), token)
                        and self.headers.get('Content-Type') == 'application/json')
            return self.headers.get('Sec-Fetch-Site', 'none') != 'cross-site'

        def do_GET(self):
            if not self.trusted():
                return self.send(403, {'error': 'local_only'})
            if self.path == '/':
                return self.send(200, HTML.read_bytes(), 'text/html; charset=utf-8')
            if self.path == '/api/config':
                return self.send(200, {'token': token, 'model': vision.MODEL,
                    'limit_yen': vision.MAX_YEN, 'budget': budget_summary(),
                    'monitor_interval_seconds': MONITOR_INTERVAL_SECONDS})
            if self.path == '/api/latest':
                files = list(root.glob('*/result.json'))
                if not files:
                    return self.send(200, {'result': None})
                latest = max(files, key=lambda p: p.stat().st_mtime_ns)
                result = json.loads(latest.read_text(encoding='utf-8'))
                image = latest.parent / 'chart.png'
                return self.send(200, {'result': result, 'image':
                    base64.b64encode(image.read_bytes()).decode() if image.exists() else ''})
            return self.send(404, {'error': 'not_found'})

        def do_POST(self):
            nonlocal last_monitor_call
            if not self.trusted(True):
                return self.send(403, {'error': 'local_only'})
            if self.path != '/api/analyze':
                return self.send(404, {'error': 'not_found'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= MAX_BODY or self.headers.get('Transfer-Encoding'):
                    return self.send(413, {'error': 'image_too_large'})
                self.connection.settimeout(20)
                request = json.loads(self.rfile.read(length))
                source = request.get('source', 'manual')
                if source not in ('manual', 'monitor'):
                    raise ValueError('invalid_source')
                data = base64.b64decode(request['image'], validate=True)
                metadata = {k: request['metadata'].get(k) for k in
                            ('symbol', 'chart_timeframe', 'decision_timeframe', 'captured_at')}
                if type(request.get('live')) is not bool:
                    raise ValueError('invalid_live')
                if source == 'monitor':
                    metadata['capture_provenance'] = 'browser_capture'
                if not inference_lock.acquire(blocking=False):
                    return self.send(409, {'action': 'hold', 'error': 'analysis_busy'})
                try:
                    now = time.monotonic()
                    if (source == 'monitor' and request['live'] and last_monitor_call is not None
                            and now - last_monitor_call < MONITOR_INTERVAL_SECONDS):
                        return self.send(429, {'action': 'hold', 'error': 'monitor_too_soon'})
                    if source == 'monitor' and request['live']:
                        last_monitor_call = now
                    run = root / uuid.uuid4().hex
                    result = vision.analyze(data, metadata, run, live=request['live'])
                    result['budget'] = budget_summary()
                finally:
                    inference_lock.release()
                return self.send(200, result)
            except (ValueError, KeyError, TypeError, binascii.Error):
                return self.send(400, {'action': 'hold', 'error': 'invalid_request'})
            except Exception:
                return self.send(500, {'action': 'hold', 'error': 'analysis_failed'})

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler, bind_and_activate=False)
    server.allow_reuse_address = False
    if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
        server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        server.server_bind()
        server.server_activate()
    except Exception:
        server.server_close()
        raise
    return server


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8787)
    parser.add_argument('--open-browser', action='store_true')
    args = parser.parse_args()
    server = make_server(args.port)
    print(f'http://127.0.0.1:{server.server_port}', flush=True)
    if args.open_browser:
        import webbrowser
        webbrowser.open(f'http://127.0.0.1:{server.server_port}/')
    server.serve_forever()
