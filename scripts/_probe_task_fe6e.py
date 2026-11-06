# -*- coding: utf-8 -*-
import json
import sys

sys.path.insert(0, r"d:\hermes-hq\scripts")
from collect_01 import db
from report_04.gates import (
    can_advance_to_analysis,
    can_complete_step11,
    get_step_status,
    is_v3_report_tree,
    list_inflight_post_platforms,
    posts_substantively_ready,
)
from report_04.orchestrator import infer_gate_step
from report_04.video_report import can_write_report_after_videos, format_report_wait_hint, list_video_steps

tid = "fe6e72ce-228e-41a7-af4b-602f1d889929"

task = db.fetch_one(
    "SELECT task_id, status, current_phase, session_id, updated_at, finished_at, error_message FROM hermes_tasks WHERE task_id=%s",
    (tid,),
)
print("TASK", json.dumps(task, default=str, ensure_ascii=False))
print("v3", is_v3_report_tree(tid))
print("gate", infer_gate_step(tid))

steps = db.fetch_all(
    """
    SELECT step_key, parent_step_key, status, message, updated_at, started_at, finished_at
    FROM collect_phase_steps WHERE task_id=%s
    ORDER BY step_order, step_key
    """,
    (tid,),
)
print("=== STEPS ===")
for s in steps or []:
    print(
        f"{s.get('step_key'):42} {str(s.get('status') or ''):10} "
        f"parent={s.get('parent_step_key') or '-'} msg={str(s.get('message') or '')[:100]} upd={s.get('updated_at')}"
    )

print("step5_posts", get_step_status(tid, "step5_posts"))
print("step7_report", get_step_status(tid, "step7_report"))
print("posts_ready", posts_substantively_ready(tid))
print("inflight", list_inflight_post_platforms(tid))
print("can_analysis", can_advance_to_analysis(tid))
print("can_write_videos", can_write_report_after_videos(tid))
print("wait_hint", format_report_wait_hint(tid)[:300] if format_report_wait_hint(tid) else "")
print("can_complete_step11", can_complete_step11(tid))
print("video_steps", json.dumps(list_video_steps(tid), default=str, ensure_ascii=False)[:2000])

posts = db.fetch_all(
    """
    SELECT platform, COUNT(*) c, MAX(created_at) latest
    FROM collect_posts WHERE task_id=%s GROUP BY platform ORDER BY c DESC
    """,
    (tid,),
)
print("POSTS_BY_PLAT", json.dumps(posts, default=str, ensure_ascii=False))

# validated
for sql in [
    "SELECT platform, account_id, verdict FROM collect_validated_accounts WHERE task_id=%s",
    "SELECT platform, account_id, verdict FROM validated_accounts WHERE task_id=%s",
]:
    try:
        rows = db.fetch_all(sql, (tid,))
        print("VALID", sql.split()[3], json.dumps(rows, default=str, ensure_ascii=False)[:1500])
        break
    except Exception as e:
        print("VALID_MISS", type(e).__name__, str(e)[:100])

# open post children
open_posts = db.fetch_all(
    """
    SELECT step_key, status, message, updated_at
    FROM collect_phase_steps
    WHERE task_id=%s AND (step_key LIKE 'step5_post%%' OR step_key LIKE 'step5_video%%' OR step_key='step5_posts' OR step_key='phase_content' OR step_key='step7_report' OR step_key='phase_report')
    ORDER BY step_key
    """,
    (tid,),
)
print("POST_RELATED", json.dumps(open_posts, default=str, ensure_ascii=False)[:3000])

# summary / report body?
try:
    summ = db.fetch_one(
        "SELECT LEFT(summary,200) s, updated_at FROM collect_task_summaries WHERE task_id=%s",
        (tid,),
    )
    print("SUMMARY", json.dumps(summ, default=str, ensure_ascii=False))
except Exception as e:
    print("SUMMARY_ERR", e)

# continue payload
payload = db.fetch_one(
    "SELECT payload_json FROM collect_phase_steps WHERE task_id=%s AND step_key='step5_posts'",
    (tid,),
)
print("step5_payload", (payload or {}).get("payload_json", "")[:800])

# session continue / dialogues recent
try:
    dlg = db.fetch_all(
        """
        SELECT role, LEFT(content,180) c, created_at
        FROM hermes_user_dialogues
        WHERE task_id=%s OR session_id=%s
        ORDER BY id DESC LIMIT 8
        """,
        (tid, task.get("session_id") if task else ""),
    )
    print("DIALOGUES", json.dumps(dlg, default=str, ensure_ascii=False)[:2500])
except Exception as e:
    print("DIALOGUE_ERR", e)
