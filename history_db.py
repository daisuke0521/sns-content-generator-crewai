"""生成履歴をSQLiteに保存・読み込みするためのモジュール。"""

import os
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "history.db")

_HISTORY_COLUMNS = (
    "created_at", "industry", "target", "theme", "store_name",
    "dialect", "tone", "provider", "model",
    "x_post", "x_post_b", "instagram", "blog", "hashtags",
)

_LIST_COLUMNS = (
    "id", "created_at", "industry", "target", "theme",
    "store_name", "dialect", "tone", "provider", "model",
)

_LIST_HEADERS = (
    "ID", "日時", "業種", "ターゲット", "テーマ",
    "店名", "方言", "トーン", "プロバイダー", "モデル",
)


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                industry TEXT,
                target TEXT,
                theme TEXT,
                store_name TEXT,
                dialect TEXT,
                tone TEXT,
                provider TEXT,
                model TEXT,
                x_post TEXT,
                x_post_b TEXT,
                instagram TEXT,
                blog TEXT,
                hashtags TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def save_record(record: dict) -> int:
    """生成結果を1件保存し、新規レコードのIDを返す。"""
    conn = sqlite3.connect(DB_PATH)
    try:
        values = [datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
        values += [record.get(col, "") or "" for col in _HISTORY_COLUMNS[1:]]
        placeholders = ",".join("?" for _ in _HISTORY_COLUMNS)
        cur = conn.execute(
            f"INSERT INTO history ({','.join(_HISTORY_COLUMNS)}) VALUES ({placeholders})",
            values,
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_recent(limit: int = 20):
    """履歴一覧（メタ情報のみ）をリスト形式で返す。先頭にヘッダー行は含めない。"""
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            f"SELECT {','.join(_LIST_COLUMNS)} FROM history ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [list(row) for row in rows]
    finally:
        conn.close()


def get_record(record_id: int):
    """指定IDの履歴1件を辞書で返す（存在しない場合はNone）。"""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM history WHERE id = ?", (record_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_history_headers():
    return list(_LIST_HEADERS)


# モジュール読み込み時にテーブルを初期化
init_db()
