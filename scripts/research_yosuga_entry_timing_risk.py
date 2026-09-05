"""Test small entry delays and wider equal-distance SL/TP for Yosuga."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from forextester_backtest import HistoryRepository
from research_yosuga_dow_filters import (
    MIN_TRAIN_TRADES,
    MIN_VALIDATION_TRADES,
    _eligible,
    _passes_unseen_periods,
    _prepare,
    _selection_score,
)
from research_yosuga_dow_htf_filter import HtfCandidate
from research_yosuga_dow_pullback_entry import (
    PullbackCandidate,
    _atr,
    _local_dow_trend,
    _pullback_state,
    _simulate,
)
from research_yosuga_dow_rr_breakeven import _period_stats, _trend_context


ENTRY_DELAYS = (-1, 0, 1, 2)
STOP_BUFFERS_ATR = (0.1, 0.15, 0.2, 0.3)
TARGET_R = 1.0


def _with_protected_rate(
    periods: dict[str, dict[str, float | int | None]],
) -> dict[str, dict[str, float | int | None]]:
    for stats in periods.values():
        trades = int(stats["trades"])
        protected = int(stats["targets"]) + int(stats["breakevens"])
        stats["win_rate_including_breakeven"] = (
            protected * 100.0 / trades if trades else None
        )
    return periods


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-dir", default=r"C:\ForexTester6\data\History")
    parser.add_argument("--symbol", default="EURUSD")
    parser.add_argument("--cost-pct", type=float, default=0.01)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("scripts/yosuga_entry_timing_risk_results.json"),
    )
    args = parser.parse_args()

    repository = HistoryRepository(args.history_dir)
    data = _prepare(repository, args.symbol, datetime(2026, 7, 17, 23, 59, 59))
    htf = HtfCandidate("sma", 20, "slope")
    signal = PullbackCandidate(
        htf=htf,
        pullback_lookback_bars=4,
        require_ma_slope=True,
        breakeven_trigger_r=0.5,
        require_local_dow=True,
    )
    atr = _atr(data)
    pullback = _pullback_state(data)
    local_dow = _local_dow_trend(data)
    trend_context = _trend_context(data, htf)

    rows: list[dict[str, object]] = []
    for entry_delay_bars in ENTRY_DELAYS:
        for stop_buffer_atr in STOP_BUFFERS_ATR:
            periods = _with_protected_rate(
                _period_stats(
                    _simulate(
                        data,
                        args.cost_pct,
                        signal,
                        atr=atr,
                        pullback=pullback,
                        trend_context=trend_context,
                        local_dow=local_dow,
                        entry_delay_bars=entry_delay_bars,
                        stop_buffer_atr=stop_buffer_atr,
                        target_r=TARGET_R,
                    )
                )
            )
            rows.append(
                {
                    "entry_delay_bars": entry_delay_bars,
                    "stop_buffer_atr": stop_buffer_atr,
                    "target_r": TARGET_R,
                    "periods": periods,
                    "eligible": _eligible(periods),
                }
            )

    eligible = [row for row in rows if bool(row["eligible"])]
    selected = (
        max(eligible, key=lambda row: _selection_score(row["periods"]))
        if eligible
        else None
    )
    adopted = (
        selected
        if selected and _passes_unseen_periods(selected["periods"])
        else None
    )
    baseline = next(
        row
        for row in rows
        if row["entry_delay_bars"] == 0 and row["stop_buffer_atr"] == 0.1
    )
    payload = {
        "strategy": {
            "symbol": args.symbol,
            "history_end": data.times[-1].isoformat(),
            "entry_timeframe": "15m",
            "signal": asdict(signal),
            "entry_delay": (
                "-1=MA-contact rejection close; 0=current reacceleration close; "
                "1 or 2=wait that many completed 15m bars, require direction and "
                "MA side still valid, then enter at close"
            ),
            "stop": "pullback extreme through the waiting bar plus ATR buffer",
            "target": "same distance as stop; full exit at strict RR 1:1",
            "breakeven": "0.5R trigger, effective from next bar",
            "round_trip_cost_pct": args.cost_pct,
        },
        "selection_rule": {
            "minimum_train_trades": MIN_TRAIN_TRADES,
            "minimum_validation_trades": MIN_VALIDATION_TRADES,
            "select_using": ["train_2004_2018", "validation_2019_2022"],
            "adopt_only_if_positive": [
                "holdout_2023_2024",
                "true_oos_2025_2026",
            ],
        },
        "baseline": baseline,
        "candidates": rows,
        "selected_by_train_validation": selected,
        "adopted": adopted,
        "adoption_reason": (
            "selected timing/risk variant stayed positive in both unseen periods"
            if adopted
            else "no timing/risk variant passed all four period gates"
        ),
    }
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"selected": selected, "adopted": adopted}, indent=2))
    print(f"WROTE {args.output}", file=sys.stderr)
    return 0 if adopted else 2


if __name__ == "__main__":
    raise SystemExit(main())
