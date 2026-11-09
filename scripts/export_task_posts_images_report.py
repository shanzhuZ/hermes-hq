# -*- coding: utf-8 -*-
"""导出任务：发文 / 图片 / 最终报告 三份 JSON，并生成最终报告 Word。"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pymysql

DB = dict(
    host="192.168.3.124",
    port=3306,
    user="root",
    password="Yvns!niwo^coc57Qpoi",
    database="hermes-xa",
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_UL_RE = re.compile(r"^[-*•]\s+(.*)$")
_OL_RE = re.compile(r"^(\d+)[\.、]\s+(.*)$")


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


def parse_json_fields(rows):
    keys = (
        "display_fields",
        "media_json",
        "payload_json",
        "extra_json",
        "raw_json",
        "seed_json",
        "subject_json",
        "tool_args",
    )
    for row in rows:
        for k, v in list(row.items()):
            if not isinstance(v, str):
                continue
            if v[:1] not in ("{", "["):
                continue
            if k in keys or k.endswith("_json"):
                try:
                    row[k] = json.loads(v)
                except Exception:
                    pass
    return rows


def _add_runs(paragraph, text):
    """把含 **粗体** 的文本写入段落。"""
    pos = 0
    for m in _BOLD_RE.finditer(text or ""):
        if m.start() > pos:
            paragraph.add_run(text[pos : m.start()])
        run = paragraph.add_run(m.group(1))
        run.bold = True
        pos = m.end()
    if pos < len(text or ""):
        paragraph.add_run(text[pos:])
    if not text:
        paragraph.add_run("")


def _write_report_docx_impl(content: str, out_path: Path, title: str | None = None) -> None:
    """把最终报告 Markdown 写成 Word（需可用的 python-docx）。"""
    from docx import Document
    from docx.oxml.ns import qn
    from docx.shared import Pt

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "宋体"
    style.font.size = Pt(12)
    style._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")

    if title:
        p = doc.add_heading(title, level=0)
        for run in p.runs:
            run.font.name = "黑体"
            run._element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")

    text = (content or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        doc.add_paragraph("（无最终报告内容）")
        doc.save(str(out_path))
        return

    for raw in text.split("\n"):
        line = raw.rstrip()
        if not line.strip():
            continue

        hm = _HEADING_RE.match(line.strip())
        if hm:
            level = min(len(hm.group(1)), 3)
            p = doc.add_heading(hm.group(2).strip(), level=level)
            for run in p.runs:
                run.font.name = "黑体"
                run._element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")
            continue

        um = _UL_RE.match(line.strip())
        if um:
            p = doc.add_paragraph(style="List Bullet")
            _add_runs(p, um.group(1).strip())
            continue

        om = _OL_RE.match(line.strip())
        if om:
            p = doc.add_paragraph(style="List Number")
            _add_runs(p, om.group(2).strip())
            continue

        p = doc.add_paragraph()
        _add_runs(p, line.strip())

    doc.save(str(out_path))


def write_report_docx(content: str, out_path: Path, title: str | None = None) -> None:
    """优先本进程写 Word；venv 缺 docx/lxml 时回退系统 Python。"""
    try:
        _write_report_docx_impl(content, out_path, title=title)
        return
    except Exception:
        pass

    import os
    import subprocess
    import tempfile

    helper = Path(__file__).resolve()
    payload = {
        "content": content or "",
        "out_path": str(out_path),
        "title": title,
    }
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", suffix=".json", delete=False
    ) as tf:
        json.dump(payload, tf, ensure_ascii=False)
        tmp = tf.name
    py_candidates = [
        os.environ.get("HERMES_PYTHON") or "",
        sys.executable,
        r"D:\environment\python\python.exe" if os.name == "nt" else "",
        "python3",
        "python",
        "py" if os.name == "nt" else "",
    ]
    py_candidates = [p for p in py_candidates if p]
    last_err = None
    try:
        for py in py_candidates:
            cmd = [
                py if py != "py" else "py",
                "-3" if py == "py" else None,
                str(helper),
                "--docx-only",
                tmp,
            ]
            cmd = [c for c in cmd if c is not None]
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            except Exception as e:
                last_err = e
                continue
            if r.returncode == 0:
                return
            last_err = RuntimeError(r.stderr or r.stdout or "docx fallback failed")
        raise SystemExit("生成 Word 失败: %s" % last_err)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task-id", required=False)
    ap.add_argument("--name", required=False, help="文件名前缀，如 AlenaDouhan")
    ap.add_argument(
        "--out-dir",
        default=r"C:\Users\zhr\Desktop\json与报告-xa",
    )
    ap.add_argument(
        "--no-docx",
        action="store_true",
        help="只导出 JSON，不生成 Word",
    )
    ap.add_argument(
        "--docx-only",
        metavar="PAYLOAD_JSON",
        help=argparse.SUPPRESS,
    )
    args = ap.parse_args()

    if args.docx_only:
        payload = json.loads(Path(args.docx_only).read_text(encoding="utf-8"))
        _write_report_docx_impl(
            payload.get("content") or "",
            Path(payload["out_path"]),
            title=payload.get("title"),
        )
        return

    if not args.task_id or not args.name:
        ap.error("--task-id 与 --name 必填")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    conn = pymysql.connect(**DB)
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM hermes_tasks WHERE task_id=%s", (args.task_id,))
        if not cur.fetchone():
            raise SystemExit("task not found: %s" % args.task_id)

        cur.execute(
            "SELECT * FROM collect_posts WHERE task_id=%s "
            "ORDER BY published_at DESC, id DESC",
            (args.task_id,),
        )
        posts = parse_json_fields(list(cur.fetchall()))

        cur.execute(
            "SELECT * FROM collect_images WHERE task_id=%s "
            "ORDER BY created_at ASC, image_id ASC",
            (args.task_id,),
        )
        images = parse_json_fields(list(cur.fetchall()))

        cur.execute(
            "SELECT * FROM hermes_user_dialogues "
            "WHERE task_id=%s AND msg_type='summary' "
            "ORDER BY id DESC LIMIT 1",
            (args.task_id,),
        )
        report = cur.fetchone()
        if not report:
            cur.execute(
                "SELECT * FROM hermes_user_dialogues "
                "WHERE task_id=%s AND role='assistant' "
                "ORDER BY CHAR_LENGTH(content) DESC, id DESC LIMIT 1",
                (args.task_id,),
            )
            report = cur.fetchone()
        if report:
            parse_json_fields([report])

        report_obj = {
            "task_id": args.task_id,
            "msg_type": report.get("msg_type") if report else None,
            "role": report.get("role") if report else None,
            "created_at": report.get("created_at") if report else None,
            "content": report.get("content") if report else None,
            "payload_json": report.get("payload_json") if report else None,
        }

        p1 = out_dir / ("%s-发文.json" % args.name)
        p2 = out_dir / ("%s-图片分析.json" % args.name)
        p3 = out_dir / ("%s-最终报告.json" % args.name)

        p1.write_text(
            json.dumps(
                {"task_id": args.task_id, "count": len(posts), "records": posts},
                ensure_ascii=False,
                indent=2,
                default=json_default,
            ),
            encoding="utf-8",
        )
        p2.write_text(
            json.dumps(
                {"task_id": args.task_id, "count": len(images), "records": images},
                ensure_ascii=False,
                indent=2,
                default=json_default,
            ),
            encoding="utf-8",
        )
        p3.write_text(
            json.dumps(report_obj, ensure_ascii=False, indent=2, default=json_default),
            encoding="utf-8",
        )

        print("posts", len(posts), p1)
        print("images", len(images), p2)
        print(
            "report_len",
            len(str(report_obj.get("content") or "")),
            "msg_type=",
            report_obj.get("msg_type"),
            p3,
        )

        if not args.no_docx:
            p4 = out_dir / ("%s.docx" % args.name)
            write_report_docx(
                report_obj.get("content") or "",
                p4,
                title=args.name,
            )
            print("docx", p4)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
