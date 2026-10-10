"""Map the Claude and Gemini exports onto one daily usage fact.

Grain: one fact per platform × user × group × day × model × product.
Claude's product is chat, claude_code, or cowork. Gemini's product is the
agent label, because billing has no product field.

Units: tokens are counts. Claude cost arrives as a decimal string of cents
and is stored in USD. Gemini cost is already USD. Input tokens for Claude
are uncached input plus cache reads plus both cache-creation buckets, which
is exactly total_tokens minus output_tokens on every row in this export.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from meridian.directory import Directory
from meridian.periods import iso_week

FactKey = Tuple[str, str, str, str, str, str]  # platform, user, group, day, model, product


class IngestError(Exception):
    pass


@dataclass
class UsageFact:
    platform: str
    user_id: str
    group_id: str
    day: str
    iso_week: str
    model: str
    product: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    requests: Optional[int]
    web_search_requests: Optional[int]
    cost_usd: Decimal

    def key(self) -> FactKey:
        return (self.platform, self.user_id, self.group_id, self.day, self.model, self.product)


def _day_from_rfc3339(value: str) -> str:
    # 2026-08-03T00:00:00.000Z
    parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    return parsed.date().isoformat()


def _day_from_bigquery(value: str) -> str:
    # 2026-08-05 00:00:00 UTC
    parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S UTC")
    return parsed.date().isoformat()


def _label_map(items: Iterable[dict]) -> Dict[str, str]:
    return {item["key"]: item["value"] for item in items}


def _require_user_group(directory: Directory, user_id: str, group_id: str, where: str) -> None:
    user = directory.users_by_id.get(user_id)
    if user is None:
        raise IngestError("%s: user %s is not in the directory" % (where, user_id))
    if group_id not in directory.groups_by_id:
        raise IngestError("%s: group %s is not in the directory" % (where, group_id))
    if group_id not in user.group_ids:
        raise IngestError(
            "%s: user %s is in %s, not %s" % (where, user_id, list(user.group_ids), group_id)
        )


def build_facts(data_dir: Path, directory: Directory) -> List[UsageFact]:
    facts: Dict[FactKey, UsageFact] = {}
    _ingest_claude(data_dir / "claude", directory, facts)
    _ingest_gemini(data_dir / "gemini", directory, facts)
    return list(facts.values())


def _ingest_claude(claude_dir: Path, directory: Directory, facts: Dict[FactKey, UsageFact]) -> None:
    usage_doc = json.loads((claude_dir / "user_usage_report.json").read_text(encoding="utf-8"))
    cost_doc = json.loads((claude_dir / "user_cost_report.json").read_text(encoding="utf-8"))

    for index, row in enumerate(usage_doc["data"]):
        where = "claude usage row %d" % index
        user_id = row["actor"]["user_id"]
        rbac = row["rbac_group_id"]
        group = directory.groups_by_rbac.get(rbac)
        if group is None:
            raise IngestError("%s: unknown rbac_group_id %s" % (where, rbac))
        _require_user_group(directory, user_id, group.group_id, where)
        if row["actor"]["email"] != directory.users_by_id[user_id].email:
            raise IngestError("%s: actor email does not match the directory" % where)

        cache = row["cache_creation"]
        input_tokens = (
            row["uncached_input_tokens"]
            + row["cache_read_input_tokens"]
            + cache["ephemeral_5m_input_tokens"]
            + cache["ephemeral_1h_input_tokens"]
        )
        output_tokens = row["output_tokens"]
        total_tokens = row["total_tokens"]
        if input_tokens + output_tokens != total_tokens:
            raise IngestError(
                "%s: input %d + output %d != total %d"
                % (where, input_tokens, output_tokens, total_tokens)
            )

        day = _day_from_rfc3339(row["starting_at"])
        fact = UsageFact(
            platform="claude",
            user_id=user_id,
            group_id=group.group_id,
            day=day,
            iso_week=iso_week(day),
            model=row["model"],
            product=row["product"],
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            requests=int(row["requests"]),
            web_search_requests=int(row["server_tool_use"]["web_search_requests"]),
            cost_usd=Decimal("0"),
        )
        if fact.key() in facts:
            raise IngestError("%s: duplicate usage key %s" % (where, fact.key()))
        facts[fact.key()] = fact

    seen_cost = set()
    for index, row in enumerate(cost_doc["data"]):
        where = "claude cost row %d" % index
        if row.get("currency") != "USD":
            raise IngestError("%s: expected USD, got %r" % (where, row.get("currency")))
        user_id = row["actor"]["user_id"]
        group = directory.groups_by_rbac.get(row["rbac_group_id"])
        if group is None:
            raise IngestError("%s: unknown rbac_group_id" % where)
        day = _day_from_rfc3339(row["starting_at"])
        key: FactKey = ("claude", user_id, group.group_id, day, row["model"], row["product"])
        fact = facts.get(key)
        if fact is None:
            raise IngestError("%s: cost has no matching usage row" % where)
        # amount is a decimal string of cents. "88.900050" cents is $0.88900050.
        fact.cost_usd += Decimal(row["amount"]) / Decimal(100)
        seen_cost.add(key)

    missing = [key for key in facts if key[0] == "claude" and key not in seen_cost]
    if missing:
        raise IngestError("Claude usage rows with no cost: %d" % len(missing))


def _ingest_gemini(gemini_dir: Path, directory: Directory, facts: Dict[FactKey, UsageFact]) -> None:
    paths = sorted(gemini_dir.glob("*.jsonl"))
    if not paths:
        raise IngestError("No Gemini billing export in %s" % gemini_dir)

    for path in paths:
        with path.open(encoding="utf-8") as handle:
            for index, line in enumerate(handle):
                if not line.strip():
                    continue
                row = json.loads(line)
                where = "%s line %d" % (path.name, index)
                sku = row["sku"]["description"]
                if "Input" in sku:
                    direction = "input"
                elif "Output" in sku:
                    direction = "output"
                else:
                    raise IngestError("%s: cannot tell input from output in %r" % (where, sku))

                labels = _label_map(row.get("labels") or [])
                email = labels.get("owner")
                model = labels.get("model")
                agent = labels.get("agent")
                if not email or not model or not agent:
                    raise IngestError("%s: owner, model, and agent labels are required" % where)
                user = directory.users_by_email.get(email)
                if user is None:
                    raise IngestError("%s: owner %s is not in the directory" % (where, email))
                project_id = row["project"]["id"]
                group = directory.groups_by_project.get(project_id)
                if group is None:
                    raise IngestError("%s: unknown project %s" % (where, project_id))
                _require_user_group(directory, user.user_id, group.group_id, where)

                project_labels = _label_map(row["project"].get("labels") or [])
                if project_labels.get("team") != group.group_id:
                    raise IngestError("%s: project team label does not match the directory group" % where)

                day = _day_from_bigquery(row["usage_start_time"])
                key: FactKey = ("gemini", user.user_id, group.group_id, day, model, agent)
                fact = facts.get(key)
                if fact is None:
                    fact = UsageFact(
                        platform="gemini",
                        user_id=user.user_id,
                        group_id=group.group_id,
                        day=day,
                        iso_week=iso_week(day),
                        model=model,
                        product=agent,
                        input_tokens=0,
                        output_tokens=0,
                        total_tokens=0,
                        requests=None,
                        web_search_requests=None,
                        cost_usd=Decimal("0"),
                    )
                    facts[key] = fact

                tokens = int(row["usage"]["amount"])
                if direction == "input":
                    fact.input_tokens += tokens
                else:
                    fact.output_tokens += tokens
                fact.total_tokens = fact.input_tokens + fact.output_tokens
                if row.get("currency") != "USD":
                    raise IngestError("%s: expected USD" % where)
                fact.cost_usd += Decimal(str(row["cost"]))
