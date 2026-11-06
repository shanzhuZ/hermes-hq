# -*- coding: utf-8 -*-
"""按 task_id 导出 MySQL 业务表 JSON 到桌面目录。"""
from __future__ import annotations

import json
import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pymysql

TASK_ID = "954dd006-6f6e-44dc-9fe0-d34769980f2b"
OUT_DIR = Path(r"C:\Users\zhr\Desktop\json与报告-xa")

# 与 clients/hermes-xa/src/main/resources/application.yml 一致
DB = {
    "host": "192.168.3.124",
    "port": 3306,
    "user": "root",
    "password": "Yvns!niwo^coc57Qpoi",
    "database": "hermes-xa",
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}

# 按 task_id 过滤的表（存在才导）
TASK_TABLES = [
    "hermes_tasks",
    "hermes_user_dialogues",
    "hermes_tool_outputs",
    "hermes_thought_events",
    "collect_phase_steps",
    "collect_task_summaries",
    "collect_profiles",
    "collect_posts",
    "collect_validated_accounts",
    "collect_identity_streams",
    "collect_display_records",
    "collect_images",
    "collect_videos",
    "collect_osint_hits",
    "cross_platform_candidates",
]


def json_default(o):
    if isinstance(o, datetime):
        return o.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(o, date):
        return o.strftime("%Y-%m-%d")
    if isinstance(o, Decimal):
        return float(o)
    if isinstance(o, (bytes, bytearray)):
        return o.decode("utf-8", errors="replace")
    return str(o)


def table_exists(cur, name: str) -> bool:
    cur.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema=%s AND table_name=%s LIMIT 1",
        (DB["database"], name),
    )
    return cur.fetchone() is not None


def fetch_rows(cur, table: str, task_id: str):
    # hermes_tasks 主键是 task_id
    cur.execute(f"SELECT * FROM `{table}` WHERE task_id=%s", (task_id,))
    return list(cur.fetchall())


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = pymysql.connect(**DB)
    try:
        cur = conn.cursor()
        summary = {
            "task_id": TASK_ID,
            "db": f"{DB['host']}:{DB['port']}/{DB['database']}",
            "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "tables": {},
        }
        bundle = {"task_id": TASK_ID, "tables": {}}

        for table in TASK_TABLES:
            if not table_exists(cur, table):
                print(f"[skip] 无表 {table}")
                continue
            rows = fetch_rows(cur, table, TASK_ID)
            # 尝试把 JSON 字符串字段解析成对象，便于阅读
            for row in rows:
                for k, v in list(row.items()):
                    if isinstance(v, str) and v[:1] in ("{", "[") and k.endswith(
                        ("_json", "json", "payload", "fields", "display_fields", "media_json", "payload_json")
                    ):
                        try:
                            row[k] = json.loads(v)
                        except Exception:
                            pass
                    elif isinstance(v, str) and k == "display_fields":
                        try:
                            row[k] = json.loads(v)
                        except Exception:
                            pass

            out_file = OUT_DIR / f"{TASK_ID}_{table}.json"
            out_file.write_text(
                json.dumps(rows, ensure_ascii=False, indent=2, default=json_default),
                encoding="utf-8",
            )
            summary["tables"][table] = {"count": len(rows), "file": out_file.name}
            bundle["tables"][table] = rows
            print(f"[ok] {table}: {len(rows)} -> {out_file.name}")

        # 汇总一份
        all_file = OUT_DIR / f"{TASK_ID}_all.json"
        all_file.write_text(
            json.dumps(bundle, ensure_ascii=False, indent=2, default=json_default),
            encoding="utf-8",
        )
        summary_file = OUT_DIR / f"{TASK_ID}_export_summary.json"
        summary_file.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, default=json_default),
            encoding="utf-8",
        )
        print(f"[ok] all -> {all_file}")
        print(f"[ok] summary -> {summary_file}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
