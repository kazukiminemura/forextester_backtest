"""HTTP boundary tests by the independent auditor; no external API calls."""
import base64
from http.client import HTTPConnection
import json
import sys
from threading import Thread

import pytest
from scripts import ytt_jev_vision

sys.modules.setdefault("ytt_jev_vision", ytt_jev_vision)
from scripts import ytt_jev_vision_app as app


@pytest.fixture
def local_app(tmp_path, monkeypatch):
    calls = []

    def fake_analyze(data, metadata, directory, live=False):
        calls.append((data, metadata, directory, live))
        return {"action": "hold", "status": "dry_run", "api_called": False}

    monkeypatch.setattr(app.vision, "analyze", fake_analyze)
    server = app.make_server(port=0, run_root=tmp_path / "runs")
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = "http://127.0.0.1:" + str(server.server_port)

    def request(method, path, body=None, headers=None):
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        connection.request(method, path, body=body, headers=headers or {})
        result = connection.getresponse()
        content = result.read()
        status = result.status
        connection.close()
        return status, content

    token = json.loads(request("GET", "/api/config")[1])["token"]
    headers = {"Origin": origin, "X-CSRF-Token": token, "Content-Type": "application/json"}
    yield request, headers, calls, tmp_path
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def body(**changes):
    value = {"image": base64.b64encode(b"test pixels").decode(), "live": False,
             "metadata": {"symbol": "XAUUSD", "chart_timeframe": "5", "decision_timeframe": "15",
                          "captured_at": "2026-10-16T01:00:00+00:00", "capture_source": "manual"}}
    value.update(changes)
    return json.dumps(value)


@pytest.mark.parametrize("override", [
    {"Origin": "https://example.com"}, {"Origin": "null"}, {"X-CSRF-Token": "wrong"},
    {"Host": "attacker.example"}, {"Content-Type": "text/plain"},
])
def test_reject_untrusted_upload(local_app, override):
    request, headers, calls, _ = local_app
    assert request("POST", "/api/analyze", b"", {**headers, **override})[0] == 403
    assert calls == []


def test_get_and_path_boundaries(local_app):
    request, headers, calls, _ = local_app
    assert request("GET", "/api/config", headers={"Sec-Fetch-Site": "cross-site"})[0] == 403
    for path in ("/../../.env", "/api/image?path=C:/secret", "/result.json"):
        assert request("GET", path)[0] == 404
    assert request("POST", "/api/unknown", b"", headers)[0] == 404
    assert not calls


def test_upload_size_and_live_type(local_app):
    request, headers, calls, _ = local_app
    assert request("POST", "/api/analyze", b"", {**headers, "Content-Length": str(app.MAX_BODY+1)})[0] == 413
    assert request("POST", "/api/analyze", body(live="true"), headers)[0] == 400
    assert request("POST", "/api/analyze", body(image="bad-base64!"), headers)[0] == 400
    assert not calls


def test_server_assigns_output_and_forwards_only_context(local_app):
    request, headers, calls, tmp_path = local_app
    value = json.loads(body())
    value["run_directory"] = "../../escape"
    value["metadata"]["api_key"] = "NOT_A_REAL_KEY"
    assert request("POST", "/api/analyze", json.dumps(value), headers)[0] == 200
    data, meta, directory, live = calls[0]
    assert data == b"test pixels" and live is False
    assert "api_key" not in meta
    assert directory.parent == tmp_path / "runs"


def test_latest_is_local_read_only_without_analyzing(local_app):
    request, headers, calls, tmp_path = local_app
    status, raw = request("GET", "/api/latest")
    assert status == 200 and json.loads(raw)["result"] is None
    run = tmp_path / "runs" / "saved"
    run.mkdir(parents=True)
    recorded = {"action": "hold", "metadata": {"symbol": "XAUUSD"}}
    (run / "result.json").write_text(json.dumps(recorded), encoding="utf-8")
    (run / "chart.png").write_bytes(b"saved image")
    status, raw = request("GET", "/api/latest")
    loaded = json.loads(raw)
    assert status == 200 and loaded["result"] == recorded
    assert base64.b64decode(loaded["image"]) == b"saved image"
    assert request("GET", "/api/latest", headers={"Sec-Fetch-Site": "cross-site"})[0] == 403
    assert calls == []
