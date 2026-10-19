"""Read-only, loopback-only live view of the bounded Jev experiment."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import re
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / 'agent_runs/bb3_jev_20260925'
SYMBOLS = ('USDJPY', 'EURUSD', 'GBPUSD', 'AUDUSD', 'NZDUSD', 'AUDJPY', 'NZDJPY')
METRICS = ('trades', 'win_rate_pct', 'profit_factor', 'profit_factor_r', 'net_pips', 'net_r', 'average_r')


def number(value):
    return value if type(value) in (int, float) and math.isfinite(value) else None


def metrics(value):
    return {key: number(value.get(key)) for key in METRICS} if isinstance(value, dict) else {}


class Status:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.cache = {}
        self.lock = threading.Lock()

    def read(self, path):
        try:
            stat = path.stat()
            stamp = (stat.st_mtime_ns, stat.st_size)
            if path not in self.cache or self.cache[path][0] != stamp:
                self.cache[path] = (stamp, json.loads(path.read_text(encoding='utf-8-sig')))
            return self.cache[path][1], stat.st_mtime
        except (OSError, ValueError):
            return {}, 0

    def snapshot(self):
        with self.lock:
            return self._snapshot()

    def _snapshot(self):
        manifest, updated = self.read(self.directory / 'run_manifest.json')
        candidates, _ = self.read(self.directory / 'candidates.json')
        progress, progress_time = self.read(self.directory / 'progress.json')
        results, result_time = self.read(self.directory / 'results.json')
        updated = max(updated, progress_time, result_time)
        responses, input_tokens = {}, 0
        for path in (self.directory / 'responses').glob('*.json'):
            if not re.fullmatch(r'[a-f0-9]{64}', path.stem):
                continue
            value, modified = self.read(path)
            if not isinstance(value, dict) or 'valid' not in value:
                continue
            responses[path.stem] = value
            updated = max(updated, modified)
            tokens = number(value.get('response', {}).get('usage', {}).get('input_tokens'))
            if tokens is not None and tokens >= 0:
                input_tokens += tokens
        reserved, attempts, ledger_errors = 0., 0, 0
        try:
            ledger = self.directory / 'reservations.jsonl'
            updated = max(updated, ledger.stat().st_mtime)
            for line in ledger.read_text(encoding='utf-8').splitlines():
                try:
                    amount = number(json.loads(line).get('reserved_usd'))
                    if amount is None or amount < 0:
                        raise ValueError('Invalid reservation')
                    reserved += amount
                    attempts += 1
                except (ValueError, AttributeError):
                    ledger_errors += 1
        except OSError:
            pass
        pairs = []
        counts = manifest.get('candidates', {})
        for symbol in SYMBOLS:
            records = [responses.get(c.get('payload_hash')) for c in candidates.get(symbol, [])]
            records = [r for r in records if r is not None]
            accepted = sum(r.get('valid') is True and r.get('accepted') is True for r in records)
            failed = sum(r.get('valid') is not True for r in records)
            pairs.append(dict(symbol=symbol, total=number(counts.get(symbol)),
                              processed=len(records), accepted=accepted, failed=failed,
                              skipped=len(records)-accepted-failed))
        accepted = sum(r.get('valid') is True and r.get('accepted') is True for r in responses.values())
        failed = sum(r.get('valid') is not True for r in responses.values())
        inconsistent = sum(r.get('valid') is not True and r.get('error_type') == 'ValueError'
                           for r in responses.values())
        unique_total = len(manifest['payload_hashes']) if 'payload_hashes' in manifest else None
        phase = progress.get('phase', 'inference' if responses else 'preparing')
        if results and phase not in ('validation', 'complete', 'failed'):
            phase = 'results' if results.get('complete') else 'incomplete'
        totals = {arm: {period: metrics(row) for period, row in periods.items()}
                  for arm, periods in results.get('totals', {}).items() if isinstance(periods, dict)}
        pair_results = [dict(symbol=r.get('symbol'), arm=r.get('arm'), **metrics(r))
                        for r in results.get('pair_summaries', []) if isinstance(r, dict)]
        message = 'Jevの判断を保存しています。' if responses else '検証データの準備を待っています。'
        research_dir = self.directory.parent / 'bb3_jev_refine_20260925'
        research_progress, research_updated = self.read(research_dir / 'progress.json')
        research_results, research_result_time = self.read(research_dir / 'results.json')
        research = None
        if research_progress or research_results:
            review_tokens, review_calls, review_invalid, review_reserved, review_attempts = 0, 0, 0, 0., 0
            for review_path in research_dir.glob('code_review_*.json'):
                if not re.fullmatch(r'code_review_[a-f0-9]{64}', review_path.stem):
                    continue
                review, _ = self.read(review_path)
                if not isinstance(review, dict) or 'valid' not in review:
                    continue
                review_calls += 1
                review_invalid += review.get('valid') is not True
                tokens = number(review.get('response', {}).get('usage', {}).get('input_tokens'))
                if tokens is not None and tokens >= 0:
                    review_tokens += tokens
            review_ledger_errors = 0
            try:
                for line in (research_dir/'code_review_reservations.jsonl').read_text(encoding='utf-8').splitlines():
                    try:
                        amount = number(json.loads(line).get('reserved_usd'))
                        if amount is None or amount < 0:
                            raise ValueError('Invalid reservation')
                        review_reserved += amount
                        review_attempts += 1
                    except (ValueError, AttributeError):
                        review_ledger_errors += 1
            except OSError:
                pass
            research = dict(
                id='bb3_jev_refine_20260925',
                phase=str(research_progress.get('phase', 'results' if research_results else 'preparing')),
                message=str(research_progress.get('message', '改良案を準備しています。')),
                completed_jobs=number(research_progress.get('completed_jobs')),
                total_jobs=number(research_progress.get('total_jobs')),
                stale=bool(time.time()-max(research_updated, research_result_time) > 120
                           and not research_results),
                totals={arm: {period: metrics(row) for period, row in periods.items()}
                        for arm, periods in research_results.get('totals', {}).items()
                        if isinstance(periods, dict)},
                arm_labels={k: v for k, v in research_results.get('arm_labels', {}).items()
                            if isinstance(k, str) and isinstance(v, str)},
                complete=research_results.get('complete'),
                gates={k: v for k, v in research_results.get('gates', {}).items()
                       if isinstance(v, bool)},
                review_calls=review_calls, review_invalid=review_invalid,
                review_attempts=review_attempts, review_ledger_errors=review_ledger_errors,
                review_estimated_yen=review_tokens*.042/1e6*200,
                review_reserved_yen=review_reserved*200,
                total_estimated_yen=(input_tokens+review_tokens)*.042/1e6*200,
                total_reserved_yen=(reserved+review_reserved)*200,
            )
        alternatives_dir = self.directory.parent / 'bb_alternatives_20260925'
        sixyear_dir = self.directory.parent / 'bb_alternatives_2020_2025_20260925'
        sixyear = (sixyear_dir / 'progress.json').exists() or (sixyear_dir / 'results.json').exists()
        if sixyear:
            alternatives_dir = sixyear_dir
        alternative_progress, alternative_updated = self.read(alternatives_dir / 'progress.json')
        alternative_results, alternative_result_time = self.read(alternatives_dir / 'results.json')
        alternatives = None
        if alternative_progress or alternative_results:
            alternatives = dict(
                start_year=2020 if sixyear else 2023,
                phase=str(alternative_progress.get('phase', 'results' if alternative_results else 'preparing')),
                message=str(alternative_progress.get('message', 'BB代替ロジックを検証しています。')),
                completed_jobs=number(alternative_progress.get('completed_jobs')),
                total_jobs=number(alternative_progress.get('total_jobs')),
                stale=bool(time.time()-max(alternative_updated, alternative_result_time) > 120
                           and not alternative_results),
                complete=alternative_results.get('complete'),
                totals={arm: {period: metrics(row) for period, row in periods.items()}
                        for arm, periods in alternative_results.get('totals', {}).items()
                        if isinstance(periods, dict)},
                arm_labels={'original': '元のBB ±3σ', 'bb2_reentry': '±2σからバンド内復帰',
                            'wm': 'W底 / M天井'},
                numeric_gates_pass={k: v for k, v in alternative_results.get('numeric_gates_pass', {}).items()
                                    if isinstance(v, bool)},
            )
        return dict(phase=phase, message=str(progress.get('message', message)),
                    updated_utc=datetime.fromtimestamp(updated, timezone.utc).isoformat() if updated else None,
                    stale=bool(updated and time.time()-updated > 120 and not results),
                    total=unique_total, processed=len(responses), accepted=accepted,
                    skipped=len(responses)-accepted-failed, failed=failed, pairs=pairs,
                    inconsistent=inconsistent, request_failed=failed-inconsistent,
                    unprocessed=max(0, unique_total-len(responses)) if unique_total is not None else None,
                    input_tokens=input_tokens, estimated_yen=input_tokens*.042/1e6*200,
                    reserved_yen=reserved*200, attempts=attempts, ledger_errors=ledger_errors,
                    unknown_attempts=max(0, attempts-len(responses))+failed,
                    budget_yen=500, reservation_limit_yen=460,
                    totals=totals, pair_results=pair_results,
                    complete=results.get('complete') if results else None, research=research,
                    alternatives=alternatives)


def handler_for(status):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/':
                body = Path(__file__).with_suffix('.html').read_bytes()
                content_type = 'text/html; charset=utf-8'
            elif self.path == '/api/status':
                body = json.dumps(status.snapshot(), ensure_ascii=False, allow_nan=False).encode('utf-8')
                content_type = 'application/json; charset=utf-8'
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8768)
    parser.add_argument('--data-dir', type=Path, default=DEFAULT_DATA)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler_for(Status(args.data_dir)))
    print(f'DASHBOARD_URL=http://127.0.0.1:{server.server_port}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
