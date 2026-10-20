"""Kullanıcının hesap özetleri için SQLite geçmişi. Ham veri buraya yazılmaz."""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY,
    created_at TEXT,
    asset_id TEXT,
    date TEXT,
    s INT,
    L INT,
    t INT,
    p REAL,
    restricted TEXT,
    mode TEXT,
    ci_kind TEXT,
    status TEXT,
    delta_pct REAL,
    daily_delta_pct REAL,
    baseline_kg REAL,
    scenario_kg REAL,
    param_kwh REAL
)
"""
COLUMNS = ["id", "created_at", "asset_id", "date", "s", "L", "t", "p", "restricted", "mode",
           "ci_kind", "status", "delta_pct", "daily_delta_pct", "baseline_kg", "scenario_kg",
           "param_kwh"]


def default_path() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "CarbonDelta" / "history.db"


class HistoryDB:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else default_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(SCHEMA)
        self.conn.commit()

    def add(self, *, asset_id: str, date: str, s: int, L: int, t: int, p: float,
            restricted: list[int], mode: str, ci_kind: str, status: str,
            delta_pct: float | None, daily_delta_pct: float | None,
            baseline_kg: float, scenario_kg: float, param_kwh: float | None = None) -> int:
        cur = self.conn.execute(
            "INSERT INTO history (created_at, asset_id, date, s, L, t, p, restricted, mode, "
            "ci_kind, status, delta_pct, daily_delta_pct, baseline_kg, scenario_kg, param_kwh) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (datetime.now().isoformat(timespec="seconds"), asset_id, date, s, L, t, p,
             ",".join(str(h) for h in sorted(restricted)), mode, ci_kind, status,
             delta_pct, daily_delta_pct, baseline_kg, scenario_kg, param_kwh),
        )
        self.conn.commit()
        return cur.lastrowid

    def list(self, limit: int | None = None) -> list[dict]:
        sql = "SELECT * FROM history ORDER BY id DESC"
        params: tuple = ()
        if limit is not None:
            sql += " LIMIT ?"
            params = (limit,)
        return [self._row(r) for r in self.conn.execute(sql, params)]

    def get(self, row_id: int) -> dict | None:
        r = self.conn.execute("SELECT * FROM history WHERE id = ?", (row_id,)).fetchone()
        return self._row(r) if r else None

    def latest(self) -> dict | None:
        rows = self.list(limit=1)
        return rows[0] if rows else None

    def delete(self, row_id: int) -> None:
        self.conn.execute("DELETE FROM history WHERE id = ?", (row_id,))
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    @staticmethod
    def _row(r: sqlite3.Row) -> dict:
        d = dict(r)
        d["restricted"] = [int(h) for h in d["restricted"].split(",") if h] if d["restricted"] else []
        return d
