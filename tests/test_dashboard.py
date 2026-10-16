import json
import os
import sys
import threading
import urllib.request
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(ROOT))

from core.config import jsonl_read  # noqa: E402
from dashboard import server, state  # noqa: E402

SAMPLE = ROOT / "examples" / "ledger-sample.jsonl"
NOW = datetime(2026, 10, 16, 12, 0, 0)


@pytest.fixture(scope="module")
def board():
    return state.build_state(jsonl_read(SAMPLE), NOW)


def cols(b):
    return {c["id"]: c for c in b["columns"]}


def test_counts_per_column(board):
    got = {cid: c["count"] for cid, c in cols(board).items()}
    assert got == {"plan": 3, "doing": 2, "waiting": 1, "check": 1, "done": 1}
    assert [c["title"] for c in board["columns"]] == [
        "Plan", "Doing", "Waiting on you", "Check", "Done"]


def test_waiting_is_blocked_user_input(board):
    (card,) = cols(board)["waiting"]["cards"]
    assert card["role"] == "user-input" and card["state"] == "blocked"
    assert "storage backend" in card["title"]


def test_blocked_other_role_stays_in_doing():
    ev = [{"ts": "2026-10-16T11:00:00", "task_id": "x", "event": "created", "role": "executor"},
          {"ts": "2026-10-16T11:00:01", "task_id": "x", "event": "assigned", "role": "executor"},
          {"ts": "2026-10-16T11:00:02", "task_id": "x", "event": "started", "role": "executor"},
          {"ts": "2026-10-16T11:00:03", "task_id": "x", "event": "blocked", "role": "executor"}]
    b = state.build_state(ev, NOW)
    assert cols(b)["doing"]["count"] == 1 and cols(b)["waiting"]["count"] == 0


def test_stalled_strip(board):
    assert board["stalled"]["title"] == "Stalled or failed"
    assert {c["state"] for c in board["stalled"]["cards"]} == {"failed", "cancelled"}
    assert board["stalled"]["count"] == 2


def test_older_folded_out_of_columns(board):
    assert board["older"]["count"] == 2
    ids = {c["task_id"] for c in board["older"]["cards"]}
    assert ids == {"t-090", "t-085"}
    shown = {c["task_id"] for col in board["columns"] for c in col["cards"]}
    assert not ids & shown
    assert board["tasks"] == 12


def test_names_come_from_ledger(board):
    models = {c["model"] for col in board["columns"] for c in col["cards"] if c["model"]}
    assert models == {"haiku", "sonnet", "opus"}


def test_empty_ledger():
    b = state.build_state([], NOW)
    assert b["tasks"] == 0 and all(c["count"] == 0 for c in b["columns"])


@pytest.fixture
def live():
    srv = server.make_server(0, SAMPLE)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield "http://127.0.0.1:%d" % srv.server_address[1]
    srv.shutdown()
    srv.server_close()


def test_server_serves_html_and_state(live):
    with urllib.request.urlopen(live + "/") as r:
        assert r.status == 200 and b"swarmtier board" in r.read()
    with urllib.request.urlopen(live + "/state") as r:
        data = json.loads(r.read())
    assert [c["id"] for c in data["columns"]] == ["plan", "doing", "waiting", "check", "done"]
    assert data["tasks"] == 12


def test_server_404(live):
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(live + "/nope")
    assert e.value.code == 404


def test_binds_loopback_only():
    srv = server.make_server(0, SAMPLE)
    try:
        assert srv.server_address[0] == "127.0.0.1"
    finally:
        srv.server_close()


def test_default_port_in_config():
    from core import config
    assert config.load_config()["dashboard_port"] == 8790
