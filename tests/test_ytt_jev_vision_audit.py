"""Independent auditor probes. All network is replaced by an in-memory transport."""
from datetime import datetime, timedelta, timezone
from io import BytesIO
import json

from PIL import Image
import pytest

from scripts import ytt_jev_vision as target


NOW = datetime(2026, 10, 16, 1, 0, tzinfo=timezone.utc)


def metadata():
    return {"symbol": "OANDA:XAUUSD", "chart_timeframe": "5", "decision_timeframe": "15",
            "captured_at": NOW.isoformat(), "capture_source": "manual"}


def picture():
    stream = BytesIO()
    Image.new("RGB", (560, 320), "white").save(stream, "PNG")
    return stream.getvalue()


def response():
    answers = {}
    for key, q in target.QUESTIONS.items():
        if q["type"] == "noul":
            answers[key] = {"type": "noul", "noul": .99}
        else:
            chosen = "buy" if key == "action" else "buy_confirmed"
            answers[key] = {"type": "choice", "choice": chosen, "confidence": .99,
                            "probabilities": {option: float(option == chosen) for option in q["criteria"]}}
    return {"model": target.MODEL, "answers": answers,
            "usage": {"input_tokens": 1000, "output_tokens": 100}}


def test_screenshot_timestamp_and_decision_frame_are_checked():
    for capture in (NOW - timedelta(seconds=301), NOW + timedelta(seconds=1)):
        with pytest.raises(ValueError):
            target.validate_metadata({**metadata(), "captured_at": capture.isoformat()}, NOW)
    with pytest.raises(ValueError):
        target.validate_metadata({**metadata(), "decision_timeframe": "5"}, NOW)


def test_visually_unclear_and_conflicting_answer_cannot_trade():
    raw = response()
    raw["answers"]["new_signal"]["noul"] = .79
    assert target.decide(raw)[0] == "hold"
    raw = response()
    reason = raw["answers"]["reason"]
    reason["choice"] = "sell_confirmed"
    reason["probabilities"] = {k: float(k == "sell_confirmed") for k in reason["probabilities"]}
    assert target.decide(raw)[0] == "hold"


@pytest.mark.parametrize("corrupt", ["choice", "nan", "boolean_usage", "wrong_model"])
def test_bad_contract_fails_closed_without_retry(tmp_path, monkeypatch, corrupt):
    monkeypatch.setattr(target, "BUDGET_DIRECTORY", tmp_path / "budget")
    raw = response()
    if corrupt == "choice":
        raw["answers"]["action"]["choice"] = "sell"
    elif corrupt == "nan":
        raw["answers"]["readable"]["noul"] = float("nan")
    elif corrupt == "boolean_usage":
        raw["usage"]["input_tokens"] = True
    else:
        raw["model"] = "jev-latest"
    calls = []

    def transport(request, timeout):
        calls.append(request)
        return BytesIO(json.dumps(raw).encode())

    actual = target.analyze(picture(), metadata(), tmp_path / "run", live=True,
                            transport=transport, key="AUDIT_FAKE_KEY", now=NOW)
    assert actual["action"] == "hold" and actual["status"] == "error"
    assert len(calls) == 1
    ledger = (target.BUDGET_DIRECTORY / "reservations.jsonl").read_text()
    assert len(ledger.splitlines()) == 1
    assert "AUDIT_FAKE_KEY" not in "".join(p.read_text(encoding="utf-8") for p in tmp_path.rglob("*.json"))


def test_separate_output_directories_share_five_call_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(target, "BUDGET_DIRECTORY", tmp_path / "budget")
    calls = []

    def transport(request, timeout):
        calls.append(request)
        raise TimeoutError("no network; intentionally failed")

    for index in range(7):
        ctx = {**metadata(), "symbol": "AUDIT" + str(index)}
        result = target.analyze(picture(), ctx, tmp_path / str(index), live=True,
                                transport=transport, key="AUDIT_FAKE_KEY", now=NOW)
        assert result["action"] == "hold"
    assert len(calls) == 5
    assert result["reason"] == "budget_exhausted"
