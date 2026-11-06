# -*- coding: utf-8 -*-
"""hermes-hq 冒烟：预建写报任务 → Gateway chat/stream，写入 hermes-hq 库。"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime
from pathlib import Path
from urllib import request

import pymysql

_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS))

from report_04.phases import initial_steps  # noqa: E402

DB = dict(
    host="192.168.3.124",
    port=3306,
    user="root",
    password="Yvns!niwo^coc57Qpoi",
    database="hermes-hq",
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)
BASE = "http://127.0.0.1:8642"
API_KEY = "dc9b5db558aa4844d0a29d79deb296b75aba58a670c79ecff3ed922839b2c86b"
# 模板人物：公开资料核查冒烟
MESSAGE = "account-intelligence-report twitter @Murray_Aitken"


def _http_json(method: str, url: str, body: dict | None = None, headers: dict | None = None):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + API_KEY)
    req.add_header("Content-Type", "application/json; charset=utf-8")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    with request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return resp.status, raw


def create_session() -> str:
    code, raw = _http_json("POST", BASE + "/api/sessions", {})
    if code >= 300:
        raise SystemExit("create session failed: %s %s" % (code, raw))
    obj = json.loads(raw)
    sid = obj.get("id") or obj.get("session_id")
    if not sid and isinstance(obj.get("session"), dict):
        sid = obj["session"].get("id") or obj["session"].get("session_id")
    if not sid:
        raise SystemExit("no session id: %s" % raw)
    return str(sid)


def insert_task(conn, task_id: str, session_id: str) -> None:
    seed = {
        "platform": "twitter",
        "account_handle": "Murray_Aitken",
        "account_hint": "Murray_Aitken",
        "parse_status": "pending",
    }
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO hermes_tasks
        (task_id, task_type, session_id, status, current_phase, cross_platform, seed_json, created_at, updated_at)
        VALUES (%s,'account_report',%s,'pending','seed',1,%s,NOW(3),NOW(3))
        """,
        (task_id, session_id, json.dumps(seed, ensure_ascii=False)),
    )
    cur.execute(
        """
        INSERT INTO hermes_user_dialogues
        (task_id, session_id, role, msg_type, content, created_at)
        VALUES (%s,%s,'user','user_input',%s,NOW(3))
        """,
        (task_id, session_id, MESSAGE),
    )
    for s in initial_steps("twitter"):
        cur.execute(
            """
            INSERT INTO collect_phase_steps
            (task_id, step_key, parent_step_key, step_order, step_node, title, status, created_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,'pending',NOW(3),NOW(3))
            """,
            (
                task_id,
                s.step_key,
                s.parent_step_key,
                s.step_order,
                s.step_node,
                s.title,
            ),
        )
    conn.commit()


def start_stream(session_id: str, task_id: str) -> None:
    body = json.dumps({"input": MESSAGE}, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        BASE + "/api/sessions/" + session_id + "/chat/stream",
        data=body,
        method="POST",
    )
    req.add_header("Authorization", "Bearer " + API_KEY)
    req.add_header("Content-Type", "application/json; charset=utf-8")
    req.add_header("Accept", "text/event-stream")
    req.add_header("X-Hermes-Session-Key", "task:" + task_id)
    # 异步：只确认 HTTP 打通，读几行后交给后台会话
    conn = request.urlopen(req, timeout=120)
    print("stream_http", conn.status, flush=True)
    # 读一小段确认开跑，不阻塞盯库
    for i, line in enumerate(conn):
        text = line.decode("utf-8", errors="replace").rstrip()
        if text:
            print("sse:", text[:200], flush=True)
        if i >= 40:
            break
    print("stream_probe_done (gateway continues)", flush=True)


def main() -> None:
    task_id = str(uuid.uuid4())
    print("task_id", task_id, flush=True)
    session_id = create_session()
    print("session_id", session_id, flush=True)
    conn = pymysql.connect(**DB)
    try:
        insert_task(conn, task_id, session_id)
        cur = conn.cursor()
        cur.execute(
            "UPDATE hermes_tasks SET status='running', started_at=NOW(3), updated_at=NOW(3) WHERE task_id=%s",
            (task_id,),
        )
        conn.commit()
        cur.execute(
            "SELECT COUNT(*) c FROM collect_phase_steps WHERE task_id=%s", (task_id,)
        )
        print("steps", cur.fetchone()["c"], flush=True)
    finally:
        conn.close()
    print("at", datetime.now().isoformat(), "starting stream…", flush=True)
    start_stream(session_id, task_id)
    print("BOOTSTRAP_OK", task_id, flush=True)


if __name__ == "__main__":
    main()
