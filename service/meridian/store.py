"""SQLite store. Usage is rebuilt from the exports on startup. Capability rows are not."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from meridian.config import CAPABILITIES, Environment
from meridian.ingest import UsageFact


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Store:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def close(self) -> None:
        self._conn.close()

    def init(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS usage_daily (
                platform TEXT NOT NULL,
                user_id TEXT NOT NULL,
                group_id TEXT NOT NULL,
                day TEXT NOT NULL,
                iso_week TEXT NOT NULL,
                model TEXT NOT NULL,
                product TEXT NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                total_tokens INTEGER NOT NULL,
                requests INTEGER,
                web_search_requests INTEGER,
                cost_usd TEXT NOT NULL,
                PRIMARY KEY (platform, user_id, group_id, day, model, product)
            );
            CREATE INDEX IF NOT EXISTS idx_usage_group_day
                ON usage_daily (group_id, day);
            CREATE TABLE IF NOT EXISTS capabilities (
                group_id TEXT NOT NULL,
                capability TEXT NOT NULL,
                enabled INTEGER NOT NULL,
                updated_at TEXT,
                updated_by TEXT,
                PRIMARY KEY (group_id, capability)
            );
            """
        )
        self._conn.commit()

    def replace_usage(self, facts: Iterable[UsageFact]) -> None:
        self._conn.execute("DELETE FROM usage_daily")
        self._conn.executemany(
            """
            INSERT INTO usage_daily (
                platform, user_id, group_id, day, iso_week, model, product,
                input_tokens, output_tokens, total_tokens, requests,
                web_search_requests, cost_usd
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    fact.platform,
                    fact.user_id,
                    fact.group_id,
                    fact.day,
                    fact.iso_week,
                    fact.model,
                    fact.product,
                    fact.input_tokens,
                    fact.output_tokens,
                    fact.total_tokens,
                    fact.requests,
                    fact.web_search_requests,
                    format(fact.cost_usd, "f"),
                )
                for fact in facts
            ],
        )
        self._conn.commit()

    def seed_capabilities(self, env: Environment, group_ids: Sequence[str]) -> None:
        for group_id in group_ids:
            for capability in CAPABILITIES:
                enabled = 1 if env.capability_enabled(capability, group_id) else 0
                self._conn.execute(
                    """
                    INSERT OR IGNORE INTO capabilities
                        (group_id, capability, enabled, updated_at, updated_by)
                    VALUES (?, ?, ?, NULL, NULL)
                    """,
                    (group_id, capability, enabled),
                )
        self._conn.commit()

    def usage_rows(
        self,
        group_ids: Optional[Sequence[str]] = None,
        iso_week: Optional[str] = None,
        day_start: Optional[str] = None,
        day_end_exclusive: Optional[str] = None,
    ) -> List[dict]:
        clauses = ["1 = 1"]
        params: list = []
        if group_ids is not None:
            if not group_ids:
                return []
            marks = ",".join("?" for _ in group_ids)
            clauses.append("group_id IN (%s)" % marks)
            params.extend(group_ids)
        if iso_week:
            clauses.append("iso_week = ?")
            params.append(iso_week)
        if day_start:
            clauses.append("day >= ?")
            params.append(day_start)
        if day_end_exclusive:
            clauses.append("day < ?")
            params.append(day_end_exclusive)
        sql = "SELECT * FROM usage_daily WHERE %s" % " AND ".join(clauses)
        return [dict(row) for row in self._conn.execute(sql, params)]

    def weeks(self) -> List[str]:
        rows = self._conn.execute("SELECT DISTINCT iso_week FROM usage_daily ORDER BY iso_week")
        return [row[0] for row in rows]

    def capabilities(self, group_ids: Sequence[str]) -> List[dict]:
        if not group_ids:
            return []
        marks = ",".join("?" for _ in group_ids)
        rows = self._conn.execute(
            """
            SELECT group_id, capability, enabled, updated_at, updated_by
            FROM capabilities
            WHERE group_id IN (%s)
            ORDER BY group_id, capability
            """
            % marks,
            list(group_ids),
        )
        return [
            {
                "group": row["group_id"],
                "capability": row["capability"],
                "enabled": bool(row["enabled"]),
                "updated_at": row["updated_at"],
                "updated_by": row["updated_by"],
            }
            for row in rows
        ]

    def set_capability(
        self, group_id: str, capability: str, enabled: bool, updated_by: str
    ) -> dict:
        updated_at = _utc_now()
        cursor = self._conn.execute(
            """
            UPDATE capabilities
            SET enabled = ?, updated_at = ?, updated_by = ?
            WHERE group_id = ? AND capability = ?
            """,
            (1 if enabled else 0, updated_at, updated_by, group_id, capability),
        )
        self._conn.commit()
        if cursor.rowcount != 1:
            raise KeyError("No capability row for %s / %s" % (group_id, capability))
        return {
            "group": group_id,
            "capability": capability,
            "enabled": enabled,
            "updated_at": updated_at,
            "updated_by": updated_by,
        }


def money(value: Decimal) -> float:
    """JSON number. Eight decimal places covers Claude's fractional cents."""
    return float(value.quantize(Decimal("0.00000001")))
