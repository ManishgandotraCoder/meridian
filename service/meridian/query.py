"""Aggregate stored facts into the shapes the API and the connector return."""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, Iterable, List, Optional

from meridian.directory import Directory
from meridian.store import money

PLATFORMS = ("claude", "gemini")


def _blank() -> dict:
    return {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "requests": None,
        "cost": Decimal("0"),
    }


def _add(bucket: dict, row: dict) -> None:
    bucket["input_tokens"] += row["input_tokens"]
    bucket["output_tokens"] += row["output_tokens"]
    bucket["total_tokens"] += row["total_tokens"]
    bucket["cost"] += Decimal(row["cost_usd"])
    if row["requests"] is not None:
        bucket["requests"] = (bucket["requests"] or 0) + row["requests"]


def _platform_body(platform: str, bucket: dict) -> dict:
    return {
        "platform": platform,
        "requests": bucket["requests"],
        "input_tokens": bucket["input_tokens"],
        "output_tokens": bucket["output_tokens"],
        "total_tokens": bucket["total_tokens"],
        "cost_usd": money(bucket["cost"]),
    }


def platform_totals(rows: Iterable[dict]) -> List[dict]:
    buckets = {platform: _blank() for platform in PLATFORMS}
    for row in rows:
        _add(buckets[row["platform"]], row)
    return [_platform_body(platform, buckets[platform]) for platform in PLATFORMS]


def totals(platforms: List[dict]) -> dict:
    cost = sum((Decimal(str(item["cost_usd"])) for item in platforms), Decimal("0"))
    return {
        "total_tokens": sum(item["total_tokens"] for item in platforms),
        "cost_usd": money(cost),
    }


def by_group(rows: Iterable[dict]) -> List[dict]:
    buckets: Dict[str, dict] = {}
    for row in rows:
        bucket = buckets.setdefault(row["group_id"], _blank())
        _add(bucket, row)
    result = []
    for group_id in sorted(buckets):
        bucket = buckets[group_id]
        result.append(
            {
                "group": group_id,
                "total_tokens": bucket["total_tokens"],
                "cost_usd": money(bucket["cost"]),
            }
        )
    return result


def by_week(rows: Iterable[dict]) -> List[dict]:
    buckets: Dict[str, dict] = {}
    for row in rows:
        bucket = buckets.setdefault(row["iso_week"], _blank())
        _add(bucket, row)
    result = []
    for week in sorted(buckets):
        bucket = buckets[week]
        result.append(
            {
                "week": week,
                "total_tokens": bucket["total_tokens"],
                "cost_usd": money(bucket["cost"]),
            }
        )
    return result


def detail_rows(rows: Iterable[dict]) -> List[dict]:
    buckets: Dict[tuple, dict] = {}
    for row in rows:
        key = (row["iso_week"], row["group_id"], row["platform"])
        bucket = buckets.setdefault(key, _blank())
        _add(bucket, row)
    result = []
    for week, group_id, platform in sorted(buckets):
        bucket = buckets[(week, group_id, platform)]
        result.append(
            {
                "week": week,
                "group": group_id,
                "platform": platform,
                "input_tokens": bucket["input_tokens"],
                "output_tokens": bucket["output_tokens"],
                "total_tokens": bucket["total_tokens"],
                "requests": bucket["requests"],
                "cost_usd": money(bucket["cost"]),
            }
        )
    return result


def top_users(rows: Iterable[dict], directory: Directory, limit: int) -> List[dict]:
    buckets: Dict[str, dict] = {}
    groups: Dict[str, str] = {}
    for row in rows:
        bucket = buckets.setdefault(row["user_id"], _blank())
        _add(bucket, row)
        groups[row["user_id"]] = row["group_id"]
    ranked = sorted(buckets, key=lambda user_id: (-buckets[user_id]["total_tokens"], user_id))
    result = []
    for user_id in ranked[:limit]:
        user = directory.user(user_id)
        if user is None:
            raise RuntimeError("Usage row for unknown user %s" % user_id)
        bucket = buckets[user_id]
        result.append(
            {
                "user_id": user_id,
                "name": user.name,
                "email": user.email,
                "group": groups[user_id],
                "total_tokens": bucket["total_tokens"],
                "cost_usd": money(bucket["cost"]),
            }
        )
    return result
