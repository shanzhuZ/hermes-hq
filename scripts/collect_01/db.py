"""MySQL 连接与通用写入。"""

from __future__ import annotations

import json
import logging
import threading
from contextlib import contextmanager
from typing import Any, Dict, Generator, Iterable, List, Optional, Tuple

from collect_01.config import db_config, persist_enabled

logger = logging.getLogger(__name__)

# Hook 子进程内复用同一连接，避免远程 MySQL 每次建连 ~1s 把 120s 墙钟耗尽
_TLS = threading.local()


class DbError(RuntimeError):
    pass


def _connect():
    if not persist_enabled():
        raise DbError("HERMES_PERSIST_ENABLED=0，跳过入库")
    try:
        import pymysql
    except ImportError as exc:
        raise DbError(
            "未安装 pymysql，请执行: pip install -r scripts/requirements-persist.txt"
        ) from exc
    cfg = db_config()
    return pymysql.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        charset=cfg["charset"],
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=5,
        read_timeout=30,
        write_timeout=30,
    )


@contextmanager
def hook_connection_scope() -> Generator[None, None, None]:
    """单次 Hook 生命周期内复用连接；嵌套调用复用外层。"""
    depth = int(getattr(_TLS, "scope_depth", 0) or 0)
    owned = False
    if depth <= 0 or getattr(_TLS, "conn", None) is None:
        _TLS.conn = _connect()
        owned = True
        depth = 0
    _TLS.scope_depth = depth + 1
    try:
        yield
        conn = getattr(_TLS, "conn", None)
        if owned and conn is not None:
            try:
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                raise
    except Exception:
        conn = getattr(_TLS, "conn", None)
        if owned and conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        raise
    finally:
        _TLS.scope_depth = max(0, int(getattr(_TLS, "scope_depth", 1) or 1) - 1)
        if owned:
            conn = getattr(_TLS, "conn", None)
            _TLS.conn = None
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass


def _borrow_conn() -> Tuple[Any, bool]:
    """返回 (conn, owned)。owned=True 表示调用方负责 close。"""
    shared = getattr(_TLS, "conn", None)
    if shared is not None:
        return shared, False
    return _connect(), True


@contextmanager
def transaction() -> Generator[Any, None, None]:
    conn, owned = _borrow_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        if owned:
            try:
                conn.close()
            except Exception:
                pass


def execute(sql: str, params: Optional[Tuple | Dict] = None) -> int:
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return int(cur.rowcount)


def insert_returning_id(sql: str, params: Optional[Tuple | Dict] = None) -> int:
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return int(cur.lastrowid)


def fetch_one(sql: str, params: Optional[Tuple | Dict] = None) -> Optional[Dict[str, Any]]:
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            row = cur.fetchone()
            return dict(row) if row else None


def fetch_all(sql: str, params: Optional[Tuple | Dict] = None) -> List[Dict[str, Any]]:
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return [dict(r) for r in cur.fetchall()]


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def upsert_many(table: str, rows: Iterable[Dict[str, Any]], unique_keys: List[str]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    cols = list(rows[0].keys())
    placeholders = ", ".join(f"%({c})s" for c in cols)
    col_list = ", ".join(f"`{c}`" for c in cols)
    updates = ", ".join(f"`{c}`=VALUES(`{c}`)" for c in cols if c not in unique_keys)
    sql = (
        f"INSERT INTO `{table}` ({col_list}) VALUES ({placeholders}) "
        f"ON DUPLICATE KEY UPDATE {updates}"
    )
    count = 0
    with transaction() as conn:
        with conn.cursor() as cur:
            for row in rows:
                cur.execute(sql, row)
                count += 1
    return count
