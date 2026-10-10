import json
from decimal import Decimal

import pytest

from meridian.ingest import IngestError, _require_user_group

PRIYA = "user_E7691888F28227066DD2FB86"


def _sum(facts, platform, field):
    return sum(getattr(fact, field) for fact in facts if fact.platform == platform)


def test_claude_rows_keep_their_grain_and_units(facts):
    claude = [fact for fact in facts if fact.platform == "claude"]
    assert len(claude) == 1346
    assert _sum(claude, "claude", "input_tokens") == 173583297
    assert _sum(claude, "claude", "output_tokens") == 25175697
    assert _sum(claude, "claude", "total_tokens") == 198758994
    assert _sum(claude, "claude", "requests") == 35972
    assert _sum(claude, "claude", "web_search_requests") == 2344
    assert sum((fact.cost_usd for fact in claude), Decimal("0")) == Decimal("2830.28776008")
    for fact in claude:
        assert fact.input_tokens + fact.output_tokens == fact.total_tokens
        assert fact.requests is not None


def test_known_claude_cost_row_converts_cents(facts):
    match = [
        fact
        for fact in facts
        if fact.platform == "claude"
        and fact.user_id == PRIYA
        and fact.day == "2026-08-03"
        and fact.product == "chat"
        and fact.model == "claude-opus-5-5"
    ]
    assert len(match) == 1
    fact = match[0]
    assert fact.group_id == "clinical-operations"
    assert fact.total_tokens == 57516
    assert fact.input_tokens == 50550
    assert fact.output_tokens == 6966
    assert fact.requests == 7
    assert fact.web_search_requests == 1
    # 88.900050 cents of tokens + 1.000000 cent of web search.
    assert fact.cost_usd == Decimal("0.89900050")
    assert fact.iso_week == "2026-W32"


def test_gemini_billing_rows_collapse_to_input_and_output(facts, root):
    gemini = [fact for fact in facts if fact.platform == "gemini"]
    assert len(gemini) == 495
    assert _sum(gemini, "gemini", "input_tokens") == 132840265
    assert _sum(gemini, "gemini", "output_tokens") == 38712681
    assert _sum(gemini, "gemini", "total_tokens") == 171552946
    assert all(fact.requests is None and fact.web_search_requests is None for fact in gemini)

    cost = Decimal("0")
    with (root / "starter-kit/data/gemini/gcp_billing_export_v1_01A2B3_C4D5E6_F7A8B9.jsonl").open() as handle:
        for line in handle:
            cost += Decimal(str(json.loads(line)["cost"]))
    assert sum((fact.cost_usd for fact in gemini), Decimal("0")) == cost

    match = [
        fact
        for fact in facts
        if fact.platform == "gemini"
        and fact.user_id == PRIYA
        and fact.day == "2026-08-05"
        and fact.model == "gemini-2.5-flash"
        and fact.product == "site-monitoring-assistant"
    ]
    assert len(match) == 1
    assert match[0].input_tokens == 358546
    assert match[0].output_tokens == 55301
    assert match[0].cost_usd == Decimal("0.107564") + Decimal("0.138253")
    assert match[0].group_id == "clinical-operations"


def test_every_fact_lands_on_the_users_own_group(facts, directory):
    products = set()
    weeks = set()
    for fact in facts:
        user = directory.user(fact.user_id)
        assert user is not None
        assert fact.group_id in user.group_ids
        assert fact.platform in ("claude", "gemini")
        products.add((fact.platform, fact.product))
        weeks.add(fact.iso_week)
    assert ("claude", "chat") in products
    assert ("claude", "claude_code") in products
    assert ("claude", "cowork") in products
    assert ("gemini", "site-monitoring-assistant") in products
    assert weeks == {"2026-W32", "2026-W33", "2026-W34", "2026-W35", "2026-W36", "2026-W37", "2026-W38", "2026-W39"}


def test_a_row_that_points_at_another_group_is_rejected(directory):
    with pytest.raises(IngestError, match="not finance"):
        _require_user_group(directory, PRIYA, "finance", "test")
