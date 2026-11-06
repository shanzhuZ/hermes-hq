# -*- coding: utf-8 -*-
"""同会话续跑：对已有 session 发 continue 并长挂 SSE。"""
from __future__ import annotations

import json
import sys
from urllib import request

BASE = "http://127.0.0.1:8642"
API_KEY = "dc9b5db558aa4844d0a29d79deb296b75aba58a670c79ecff3ed922839b2c86b"


def main() -> None:
    if len(sys.argv) < 4:
        raise SystemExit("usage: keep_stream.py <session_id> <task_id> <message>")
    session_id = sys.argv[1]
    task_id = sys.argv[2]
    message = sys.argv[3]
    print("open_stream", session_id, task_id, flush=True)
    body = json.dumps({"input": message}, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        BASE + "/api/sessions/" + session_id + "/chat/stream",
        data=body,
        method="POST",
    )
    req.add_header("Authorization", "Bearer " + API_KEY)
    req.add_header("Content-Type", "application/json; charset=utf-8")
    req.add_header("Accept", "text/event-stream")
    req.add_header("X-Hermes-Session-Key", "task:" + task_id)
    conn = request.urlopen(req, timeout=600)
    print("http", conn.status, flush=True)
    for line in conn:
        text = line.decode("utf-8", errors="replace").rstrip()
        if not text:
            continue
        if text.startswith("event:"):
            print(text, flush=True)
        elif text.startswith("data:"):
            # 工具名预览，便于盯 LinkedIn
            low = text.lower()
            if any(
                k in low
                for k in (
                    "linkedin",
                    "harvestapi",
                    "tool_name",
                    "error",
                    "connection",
                )
            ):
                print(text[:320], flush=True)
        if "run.completed" in text or "run.failed" in text:
            print("DONE", text, flush=True)
            break


if __name__ == "__main__":
    main()
