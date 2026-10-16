from datetime import datetime, timedelta, timezone
from io import BytesIO
import json

from PIL import Image
import pytest

from scripts import ytt_jev_vision as vision

NOW = datetime(2026, 10, 16, 10, 0, 10, tzinfo=timezone.utc)


def image_bytes():
    buf = BytesIO()
    Image.new("RGB", (1800, 1000), "white").save(buf, format="PNG")
    return buf.getvalue()


def metadata():
    return dict(symbol="OANDA:USDJPY", chart_timeframe="5", decision_timeframe="15", captured_at=NOW.isoformat())


def response(side="buy"):
    def choice(options, selected):
        return dict(type="choice", choice=selected, confidence=.9,
                    probabilities={x: .96 if x == selected else .04 / (len(options) - 1) for x in options})
    return dict(model=vision.MODEL, usage=dict(input_tokens=2500, output_tokens=90), answers={
        "action": choice(["buy", "sell", "hold"], side),
        "reason": choice(vision.REASONS, side + "_confirmed"),
        "readable": dict(type="noul", noul=.99), "new_signal": dict(type="noul", noul=.99)})


@pytest.fixture
def budget(tmp_path, monkeypatch):
    path = tmp_path / "global_budget"
    monkeypatch.setattr(vision, "BUDGET_DIRECTORY", path)
    return path


def fake_http(payload, calls):
    def transport(request, timeout):
        calls.append(request)
        assert request.get_header("Typesafe-danger-zone-images") == "true"
        assert timeout == 45
        body = json.loads(request.data)
        assert body["model"] == vision.MODEL
        assert body["state"]["chart"] in body["assets"]
        return BytesIO(json.dumps(payload).encode())
    return transport


def test_dry_run_saves_clean_image_and_allowlisted_metadata(tmp_path):
    meta = {**metadata(), "account_password": "never forward"}
    result = vision.analyze(image_bytes(), meta, tmp_path, now=NOW)
    assert result["status"] == "dry_run" and not result["api_called"]
    assert result["action"] == "hold"
    assert max(result["capture"]["width"], result["capture"]["height"]) == 1568
    assert "account_password" not in (tmp_path / "request.json").read_text(encoding="utf-8")
    with Image.open(tmp_path / "chart.png") as prepared:
        assert not prepared.info


@pytest.mark.parametrize("side", ["buy", "sell"])
def test_live_valid_decision_single_request(tmp_path, budget, side):
    calls = []
    result = vision.analyze(image_bytes(), metadata(), tmp_path / "run", live=True,
        now=NOW, key="secret-test-key", transport=fake_http(response(side), calls))
    assert result["action"] == side and result["status"] == "evaluated"
    assert len(calls) == 1
    assert result["request_reservation_yen"] == vision.RESERVATION_YEN
    assert len((budget / "reservations.jsonl").read_text().splitlines()) == 1
    assert "secret-test-key" not in "".join(p.read_text(encoding="utf-8") for p in (tmp_path / "run").glob("*.json"))


@pytest.mark.parametrize("mutation", [
    lambda r: r["answers"]["action"].update(choice="sell"),
    lambda r: r["answers"]["action"]["probabilities"].update(buy=float("nan")),
    lambda r: r["answers"]["action"]["probabilities"].update(other=0),
    lambda r: r["answers"]["action"].update(confidence=True),
    lambda r: r.update(model="jev-latest"),
    lambda r: r["usage"].update(input_tokens=65537),
])
def test_invalid_response_holds_and_keeps_reservation(tmp_path, budget, mutation):
    payload = response()
    mutation(payload)
    result = vision.analyze(image_bytes(), metadata(), tmp_path / "run", live=True,
        now=NOW, key="test-key", transport=fake_http(payload, []))
    assert result["status"] == "error" and result["action"] == "hold"
    assert len((budget / "reservations.jsonl").read_text().splitlines()) == 1


def test_uncertainty_or_direction_conflict_holds():
    payload = response()
    payload["answers"]["new_signal"]["noul"] = .5
    assert vision.decide(payload) == ("hold", "insufficient_visible_evidence")
    payload = response()
    payload["answers"]["reason"] = response("sell")["answers"]["reason"]
    assert vision.decide(payload) == ("hold", "conflicting_answers")
    payload = response()
    payload["answers"]["action"]["confidence"] = .4
    assert vision.decide(payload) == ("hold", "low_confidence")


@pytest.mark.parametrize("change", [
    {"captured_at": (NOW - timedelta(seconds=301)).isoformat()},
    {"captured_at": (NOW + timedelta(seconds=1)).isoformat()},
    {"captured_at": "2026-10-16T10:00:10"},
    {"decision_timeframe": "5"}, {"symbol": ""}])
def test_invalid_metadata_never_sends(tmp_path, budget, change):
    calls = []
    result = vision.analyze(image_bytes(), {**metadata(), **change}, tmp_path, live=True,
        now=NOW, key="test-key", transport=fake_http(response(), calls))
    assert result["action"] == "hold" and not calls
    assert not (budget / "reservations.jsonl").exists()


def test_corrupt_image_and_same_folder_reuse(tmp_path, budget):
    result = vision.analyze(b"not an image", metadata(), tmp_path, live=True, now=NOW, key="test-key")
    assert result["action"] == "hold" and not result["api_called"]
    original = (tmp_path / "result.json").read_bytes()
    with pytest.raises(FileExistsError):
        vision.analyze(image_bytes(), metadata(), tmp_path, now=NOW)
    assert (tmp_path / "result.json").read_bytes() == original


def test_global_budget_and_duplicate_blocked_across_run_folders(tmp_path, budget):
    calls = []
    for index in range(6):
        meta = {**metadata(), "captured_at": (NOW - timedelta(seconds=index)).isoformat()}
        result = vision.analyze(image_bytes(), meta, tmp_path / str(index), live=True,
            now=NOW, key="test-key", transport=fake_http(response(), calls))
    assert len(calls) == 5 and result["reason"] == "budget_exhausted"
    result = vision.analyze(image_bytes(), metadata(), tmp_path / "duplicate", live=True,
        now=NOW, key="test-key", transport=fake_http(response(), calls))
    assert result["reason"] == "already_attempted" and len(calls) == 5


def test_timeout_no_retry_no_secret_logging(tmp_path, budget):
    calls = []
    def failing_transport(request, timeout):
        calls.append(request)
        raise RuntimeError("Authorization: Bearer super-secret")
    result = vision.analyze(image_bytes(), metadata(), tmp_path / "run", live=True,
        now=NOW, key="super-secret", transport=failing_transport)
    assert len(calls) == 1 and result["action"] == "hold"
    assert "super-secret" not in (tmp_path / "run/result.json").read_text()
    assert len((budget / "reservations.jsonl").read_text().splitlines()) == 1


def test_ledger_deleted_cannot_reset_budget(tmp_path, budget):
    calls = []
    vision.analyze(image_bytes(), metadata(), tmp_path / "first", live=True,
        now=NOW, key="test-key", transport=fake_http(response(), calls))
    (budget / "reservations.jsonl").unlink()
    result = vision.analyze(image_bytes(), metadata(), tmp_path / "second", live=True,
        now=NOW, key="test-key", transport=fake_http(response(), calls))
    assert result["reason"] == "budget_evidence_mismatch" and len(calls) == 1


def test_redirects_refused():
    with pytest.raises(ValueError, match="redirect_refused"):
        vision._NoRedirect().redirect_request(None, None, 302, "", {}, "https://elsewhere.invalid")


def test_response_arriving_after_expiry_holds(tmp_path, budget, monkeypatch):
    class Clock:
        reads = 0
        @classmethod
        def now(cls, tz):
            cls.reads += 1
            return NOW if cls.reads == 1 else NOW + timedelta(seconds=301)
        fromisoformat = staticmethod(datetime.fromisoformat)
    monkeypatch.setattr(vision, "datetime", Clock)
    result = vision.analyze(image_bytes(), metadata(), tmp_path / "run", live=True,
        key="test-key", transport=fake_http(response(), []))
    assert result["action"] == "hold" and result["reason"] == "stale_or_future_image"
