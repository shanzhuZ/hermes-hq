# -*- coding: utf-8 -*-
import json
import sys
import traceback

sys.path.insert(0, r"d:\hermes-hq\scripts")
tid = "fe6e72ce-228e-41a7-af4b-602f1d889929"

from collect_01 import db

print("=== gates ===", flush=True)
try:
    from report_04.gates import (
        can_advance_to_analysis,
        can_complete_step11,
        get_step_status,
        is_v3_report_tree,
        list_inflight_post_platforms,
        posts_substantively_ready,
    )

    print("v3", is_v3_report_tree(tid), flush=True)
    print("step5", get_step_status(tid, "step5_posts"), "step7", get_step_status(tid, "step7_report"), flush=True)
    print("posts_ready", posts_substantively_ready(tid), flush=True)
    print("inflight", list_inflight_post_platforms(tid), flush=True)
    print("can_analysis", can_advance_to_analysis(tid), flush=True)
    print("can_complete11", can_complete_step11(tid), flush=True)
except Exception:
    traceback.print_exc()

print("=== video ===", flush=True)
try:
    from report_04.video_report import can_write_report_after_videos, format_report_wait_hint, list_video_steps

    print("videos", list_video_steps(tid), flush=True)
    print("can_write", can_write_report_after_videos(tid), flush=True)
    print("hint", format_report_wait_hint(tid), flush=True)
except Exception:
    traceback.print_exc()

print("=== gate step ===", flush=True)
try:
    from report_04.orchestrator import infer_gate_step

    print("infer_gate", infer_gate_step(tid), flush=True)
except Exception:
    traceback.print_exc()

print("=== next action ===", flush=True)
try:
    from report_04.session_continue import (
        build_continue_message,
        continue_inflight,
        infer_continue_kind,
        next_agent_action,
        _payload,
    )

    print("action", next_agent_action(tid), flush=True)
    print("kind", infer_continue_kind(tid), flush=True)
    print("inflight_cont", continue_inflight(tid), flush=True)
    print("payload", json.dumps(_payload(tid), default=str, ensure_ascii=False)[:1200], flush=True)
    kind = infer_continue_kind(tid)
    if kind:
        print("continue_msg", build_continue_message(kind, tid)[:500], flush=True)
except Exception:
    traceback.print_exc()

print("=== posts/validated ===", flush=True)
print("posts", db.fetch_one("SELECT COUNT(*) c FROM collect_posts WHERE task_id=%s", (tid,)), flush=True)
# try validated table variants
for sql in [
    "SELECT platform, account_id, verdict FROM collect_validated_accounts WHERE task_id=%s",
    "SELECT platform, account_id FROM collect_accounts WHERE task_id=%s LIMIT 20",
]:
    try:
        rows = db.fetch_all(sql, (tid,))
        print(sql.split()[3], json.dumps(rows, default=str, ensure_ascii=False)[:1000], flush=True)
    except Exception as e:
        print("skip", e, flush=True)

print("=== step5_post children ===", flush=True)
rows = db.fetch_all(
    """
    SELECT step_key, status, message, payload_json, updated_at
    FROM collect_phase_steps
    WHERE task_id=%s AND (step_key LIKE 'step5_%%' OR step_key IN ('step7_report','phase_report','phase_content'))
    """,
    (tid,),
)
for r in rows or []:
    pj = r.get("payload_json") or ""
    print(r["step_key"], r["status"], (r.get("message") or "")[:100], "payload=", str(pj)[:200], flush=True)

print("=== recent dialogues ===", flush=True)
task = db.fetch_one("SELECT session_id FROM hermes_tasks WHERE task_id=%s", (tid,))
sid = (task or {}).get("session_id")
for sql in [
    "SELECT id, role, LEFT(content,220) c, created_at FROM hermes_user_dialogues WHERE task_id=%s ORDER BY id DESC LIMIT 6",
    "SELECT id, role, LEFT(content,220) c, created_at FROM hermes_user_dialogues WHERE session_id=%s ORDER BY id DESC LIMIT 6",
]:
    try:
        arg = tid if "task_id" in sql else sid
        rows = db.fetch_all(sql, (arg,))
        if rows:
            print(sql.split()[-7], json.dumps(rows, default=str, ensure_ascii=False)[:2500], flush=True)
            break
    except Exception as e:
        print("dlg", e, flush=True)

print("=== done ===", flush=True)
