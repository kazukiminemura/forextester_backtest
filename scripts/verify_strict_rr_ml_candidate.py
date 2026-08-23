"""Verify the selected strict-RR ML candidate against every adoption gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from research_strict_rr_portfolio import PERIODS, SYMBOLS


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "result",
        nargs="?",
        type=Path,
        default=Path("scripts/strict_rr_ml_15m_operational_results.json"),
    )
    parser.add_argument("--expected-threshold", type=float, default=0.53)
    parser.add_argument("--require-htf-alignment", action="store_true")
    args = parser.parse_args()
    rows = json.loads(args.result.read_text(encoding="utf-8"))
    selected = [row for row in rows if row.get("selected_by_validation_only")]
    assert len(selected) == 1, f"expected one selected candidate, found {len(selected)}"
    candidate = selected[0]
    if "config" in candidate:
        config = candidate["config"]
        assert config["timeframe"] == "15m"
        assert config["stop_atr"] == 2.0
        assert config["threshold"] == args.expected_threshold
        assert config["session_start"] == 0 and config["session_end"] == 24
        assert config["stride"] == 4
        htf_alignment = bool(config.get("require_htf_alignment", False))
    else:
        model = candidate["model"]
        assert model["trees"] == 20 and model["leaves"] == 15
        assert candidate["threshold"] == args.expected_threshold
        assert tuple(candidate["symbols"]) == SYMBOLS
        htf_alignment = bool(candidate.get("require_htf_alignment", False))
    assert htf_alignment is bool(args.require_htf_alignment)
    assert candidate["prequalified"] and candidate["passes_all"]
    assert tuple(candidate["symbol_periods"]) == SYMBOLS
    for period in PERIODS:
        stats = candidate["periods"][period]
        assert stats["profit_factor"] >= 1.15, (period, stats)
        assert stats["expectancy_r"] > 0.0, (period, stats)
        assert stats["trades_per_month"] >= 3.0, (period, stats)
    for symbol, periods in candidate["symbol_periods"].items():
        assert sum(stats["trades"] for stats in periods.values()) > 0, symbol
    print("VERIFIED: 1 selected candidate; 11 symbols; all strict RR gates passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
