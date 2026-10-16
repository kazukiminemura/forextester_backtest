"""Independent lifecycle/HTTP probes, using fake media, timers, and AI responses."""
import base64
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
import json
from pathlib import Path
import shutil
import subprocess
import sys
from threading import Event, Thread

import pytest
from scripts import ytt_jev_vision

sys.modules.setdefault("ytt_jev_vision", ytt_jev_vision)
from scripts import ytt_jev_vision_app as app


HARNESS = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const source=fs.readFileSync(process.argv[1],'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
const h={now:Date.parse('2026-10-16T00:30:00Z'),posts:[],notifications:[],timers:new Map(),intervals:[],events:{},elements:{},videos:[],shared:[],captureCalls:0,permission:'granted',budget:{valid:true,limit_yen:3,remaining_calls:4,remaining_yen:2.4494976}};
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return{resolve,reject,promise};}
function element(id){if(h.elements[id])return h.elements[id];const e={value:id==='symbol'?'USDJPY':id==='tf'?'5':'',style:{},checked:false,hidden:false,disabled:false,textContent:'',addEventListener(){}};if(id==='sharePreview'){Object.assign(e,{readyState:4,videoWidth:1280,videoHeight:720,currentTime:1,play:()=>Promise.resolve(),pause(){}});h.videos.push(e);}return h.elements[id]=e;}
function shared(surface='browser'){const track={stopped:0,onended:null,getSettings:()=>({displaySurface:surface}),stop(){this.stopped++;}};const stream={getTracks:()=>[track],getVideoTracks:()=>[track],track};h.shared.push(stream);return stream;}
function record(payload,action='buy'){return{action,api_called:true,status:'evaluated',reason:action==='hold'?'no_new_signal':action+'_confirmed',metadata:payload.metadata,budget:{...h.budget},judgments:{action:{probabilities:{[action]:.99}},readable:{noul:.99},new_signal:{noul:.99}}};}
h.capture=()=>Promise.resolve(shared());
h.respond=p=>Promise.resolve({ok:true,json:async()=>record(p)});
class FakeDate extends Date{constructor(...a){super(...(a.length?a:[h.now]));}static now(){return h.now;}}
class Notice{static get permission(){return h.permission;}static requestPermission(){h.permission='denied';return Promise.resolve('denied');}constructor(title,options){this.closed=false;this.title=title;h.notifications.push(this);}close(){this.closed=true;}}
let timerId=0;
const c={console,Date:FakeDate,AbortController,Notification:Notice,URL:{createObjectURL:()=>'',revokeObjectURL(){}},FileReader:class{},setTimeout:(f,ms)=>{const id=++timerId;h.timers.set(id,{f,ms});return id;},clearTimeout:id=>h.timers.delete(id),setInterval:f=>{h.intervals.push(f);return h.intervals.length;},clearInterval(){},navigator:{mediaDevices:{getDisplayMedia:()=>{h.captureCalls++;return h.capture();}}},document:{getElementById:element,addEventListener(){},createElement(tag){if(tag==='video'){const v={readyState:4,videoWidth:1280,videoHeight:720,currentTime:1,play:()=>Promise.resolve(),pause(){}};h.videos.push(v);return v;}if(tag==='canvas')return{getContext:()=>({drawImage(){}}),toDataURL:()=> 'data:image/png;base64,aW1hZ2U='};throw Error(tag);}},addEventListener:(name,fn)=>h.events[name]=fn,fetch:async(url,options)=>{if(url==='/api/config')return{ok:true,json:async()=>({token:'fake-csrf',budget:{...h.budget}})};if(url==='/api/latest')return{ok:true,json:async()=>({result:null})};if(options?.signal?.aborted)throw Error('aborted');const p=JSON.parse(options.body);h.posts.push(p);return h.respond(p);}};
c.window=c;vm.createContext(c);vm.runInContext(source,c);
const flush=()=>new Promise(resolve=>setImmediate(resolve));
const run=code=>vm.runInContext(code,c),state=()=>c.monitorTestHooks.getState();
async function begin(){await run('startMonitor()');if(state().confirmReady)await run('confirmMonitor('+state().generation+')');}
async function tick(){assert.equal(h.timers.size,1);const[id,t]=[...h.timers][0];h.timers.delete(id);h.now+=t.ms;h.videos.at(-1).currentTime+=300;await t.f();await flush();}
(async()=>{await flush();
__SCENARIO__
console.log('AUDIT_MONITOR_PASS');})().catch(e=>{console.error(e);process.exitCode=1;});
"""


SCENARIOS = {
    "window_preview_requires_confirmation": r"""
h.capture=()=>Promise.resolve(shared('window'));await run('startMonitor()');assert.equal(h.posts.length,0);assert.equal(state().confirmReady,true);assert.equal(element('symbol').disabled,true);const oldClick=element('confirm').onclick;run('stopMonitor()');await oldClick();assert.equal(h.posts.length,0);await run('startMonitor()');await oldClick();assert.equal(h.posts.length,0);await element('confirm').onclick();assert.equal(h.posts.length,1);assert.equal(state().monitoring,true);
""",
    "preview_ended_and_pagehide_never_send": r"""
await run('startMonitor()');assert.equal(h.posts.length,0);h.shared.at(-1).track.onended();assert.equal(state().confirmReady,false);await run('startMonitor()');const click=element('confirm').onclick;h.events.pagehide();await click();assert.equal(h.posts.length,0);assert.equal(state().monitoring,false);
""",
    "notification_test_has_no_api": r"""
await run('testNotification()');assert.equal(h.posts.length,0);assert.equal(h.notifications.length,1);assert.match(h.notifications[0].title,/テスト/);
""",
    "notification_test_permission_cancelled": r"""
h.permission='default';const d=deferred();Notice.requestPermission=()=>d.promise;const pending=run('testNotification()');await flush();h.events.pagehide();h.permission='granted';d.resolve('granted');await pending;assert.equal(h.notifications.length,0);assert.equal(h.posts.length,0);
""",
    "restart_drops_old_api_response": r"""
const d=deferred();h.respond=()=>d.promise;const old=begin();await flush();run('stopMonitor()');h.respond=p=>Promise.resolve({ok:true,json:async()=>record(p,'sell')});await begin();assert.equal(h.notifications.length,1);assert.match(h.notifications[0].title,/売り候補/);d.resolve({ok:true,json:async()=>record(h.posts[0],'buy')});await old;assert.equal(h.notifications.length,1);assert.equal(state().monitoring,true);assert.equal(h.timers.size,1);
""",
    "stop_permission_wait_and_double_start": r"""const d=deferred();h.capture=()=>d.promise;const pending=begin();await begin();assert.equal(h.captureCalls,1);assert.equal(state().starting,true);run('stopMonitor()');const s=shared();d.resolve(s);await pending;assert.equal(s.track.stopped,1);assert.equal(h.posts.length,0);assert.equal(state().monitoring,false);
""",
    "stop_pending_response": r"""const d=deferred();h.respond=()=>d.promise;const pending=begin();await flush();assert.equal(h.posts.length,1);run('stopMonitor()');d.resolve({ok:true,json:async()=>record(h.posts[0])});await pending;assert.equal(h.notifications.length,0);assert.equal(h.timers.size,0);assert.equal(state().monitoring,false);
""",
    "dedup_hold_then_new_direction": r"""await begin();assert.equal(h.notifications.length,1);assert.equal([...h.timers.values()][0].ms,300000);await tick();assert.equal(h.notifications.length,1);h.respond=p=>Promise.resolve({ok:true,json:async()=>record(p,'hold')});await tick();h.respond=p=>Promise.resolve({ok:true,json:async()=>record(p,'buy')});await tick();assert.equal(h.notifications.length,2);assert.equal(h.posts.length,4);
""",
    "permission_denied_fallback": r"""h.permission='default';await begin();assert.equal(h.notifications.length,0);assert.match(element('notice').textContent,/買い候補/);assert.equal(state().monitoring,true);
""",
    "track_ended_and_pagehide": r"""await begin();h.shared.at(-1).track.onended();assert.equal(state().monitoring,false);assert.equal(h.timers.size,0);assert.equal(h.notifications[0].closed,true);await begin();h.events.pagehide();assert.equal(state().monitoring,false);assert.equal(h.timers.size,0);assert.equal(h.notifications.at(-1).closed,true);
""",
    "stale_and_error_do_not_notify": r"""h.respond=p=>{const r=record(p);r.metadata={...p.metadata,captured_at:new FakeDate(h.now-300001).toISOString()};return Promise.resolve({ok:true,json:async()=>r});};await begin();assert.equal(h.notifications.length,0);h.respond=p=>Promise.resolve({ok:true,json:async()=>({action:'hold',status:'error',reason:'budget_exhausted'})});await tick();assert.equal(state().monitoring,false);assert.equal(h.timers.size,0);assert.equal(h.notifications.length,0);
""",
    "reject_whole_screen": r"""h.capture=()=>Promise.resolve(shared('monitor'));await begin();assert.equal(h.posts.length,0);assert.equal(h.shared[0].track.stopped,1);assert.equal(state().monitoring,false);
""",
    "budget_last_call_stops": r"""h.respond=p=>{const r=record(p);r.budget.remaining_calls=0;return Promise.resolve({ok:true,json:async()=>r});};await begin();assert.equal(h.posts.length,1);assert.equal(state().monitoring,false);assert.equal(h.timers.size,0);await begin();assert.equal(h.posts.length,1);
""",
    "no_overlap_or_catchup": r"""const d=deferred();h.respond=()=>d.promise;const pending=begin();await flush();h.now+=1800000;assert.equal(h.posts.length,1);assert.equal(h.timers.size,0);d.resolve({ok:true,json:async()=>record(h.posts[0],'hold')});await pending;assert.equal(h.posts.length,1);assert.equal([...h.timers.values()][0].ms,300000);
""",
}


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_browser_lifecycle_with_fake_media(scenario):
    node = shutil.which("node")
    assert node, "Node is required to execute the independent offline browser harness"
    source = HARNESS.replace("__SCENARIO__", SCENARIOS[scenario])
    result = subprocess.run([node, "-e", source, str(app.HTML)], capture_output=True, text=True,
                            encoding="utf-8", timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "AUDIT_MONITOR_PASS" in result.stdout


@pytest.fixture
def monitor_server(tmp_path, monkeypatch):
    monkeypatch.setattr(app.vision, "BUDGET_DIRECTORY", tmp_path / "budget")
    calls, block, entered = [], Event(), Event()
    slow = [False]

    def analyze(data, metadata, directory, live=False):
        calls.append((metadata, live))
        if slow[0]:
            entered.set()
            assert block.wait(3)
        return {"action": "hold", "api_called": False, "status": "dry_run"}

    monkeypatch.setattr(app.vision, "analyze", analyze)
    server = app.make_server(0, run_root=tmp_path / "runs")
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = "http://127.0.0.1:" + str(server.server_port)

    def request(method, path, body=None, headers=None):
        conn = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        conn.request(method, path, body=body, headers=headers or {})
        res = conn.getresponse()
        out = res.status, json.loads(res.read())
        conn.close()
        return out

    token = request("GET", "/api/config")[1]["token"]
    headers = {"Origin": origin, "X-CSRF-Token": token, "Content-Type": "application/json"}

    def post(source="monitor", live=True):
        return request("POST", "/api/analyze", json.dumps({"source": source, "live": live,
            "image": base64.b64encode(b"fake").decode(), "metadata": {"symbol": "USDJPY",
            "chart_timeframe": "5", "decision_timeframe": "15", "captured_at": "2026-10-16T00:30:00Z",
            "capture_provenance": "untrusted", "secret": "never_forward"}}), headers)

    yield post, calls, slow, block, entered
    block.set()
    server.shutdown()
    server.server_close()
    thread.join(2)


def test_monitor_source_provenance_and_rate(monitor_server):
    post, calls, *_ = monitor_server
    assert post(source="arbitrary")[0] == 400
    assert calls == []
    assert post()[0] == 200
    assert calls[0][0]["capture_provenance"] == "browser_capture"
    assert "secret" not in calls[0][0]
    assert post()[0] == 429
    assert len(calls) == 1


def test_monitor_and_manual_requests_cannot_overlap(monitor_server):
    post, calls, slow, block, entered = monitor_server
    slow[0] = True
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(post)
        assert entered.wait(2)
        assert post(source="manual")[0] == 409
        block.set()
        assert first.result()[0] == 200
    assert len(calls) == 1


def test_budget_summary_preserves_previous_reservation(tmp_path, monkeypatch):
    budget = tmp_path / "budget"
    monkeypatch.setattr(app.vision, "BUDGET_DIRECTORY", budget)
    assert app.budget_summary()["remaining_calls"] == 5
    receipts = budget / "receipts"
    receipts.mkdir(parents=True)
    row = {"fingerprint": "a"*64, "reserved_yen": app.vision.RESERVATION_YEN,
           "model": app.vision.MODEL, "at": "2026-10-16T00:00:00Z"}
    (receipts / (row["fingerprint"]+".json")).write_text(json.dumps(row))
    (budget / "reservations.jsonl").write_text(json.dumps(row)+"\n")
    summary = app.budget_summary()
    assert summary["valid"] and summary["remaining_calls"] == 4
    assert summary["reserved_yen"] == app.vision.RESERVATION_YEN
    (budget / "reservations.jsonl").unlink()
    assert app.budget_summary()["valid"] is False
    assert app.budget_summary()["remaining_calls"] == 0
