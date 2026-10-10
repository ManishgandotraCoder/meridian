import json

from tests.conftest import CHLOE, DANIEL, PRIYA


def _as(user_id):
    return {"X-User-Id": user_id}


def test_team_lead_summary_defaults_to_own_group(client):
    api = client()
    response = api.get("/api/usage/summary", params={"period": "2026-W32"}, headers=_as(PRIYA))
    assert response.status_code == 200
    body = response.json()
    assert body["group"] == "clinical-operations"
    assert body["period"] == {"start": "2026-08-03", "end_exclusive": "2026-08-10"}
    assert [row["platform"] for row in body["platforms"]] == ["claude", "gemini"]
    assert body["totals"]["total_tokens"] > 0
    assert body["totals"]["cost_usd"] > 0


def test_cross_group_read_is_a_denial_without_figures(client):
    api = client()
    response = api.get(
        "/api/usage/summary",
        params={"period": "last_30_days", "group": "finance"},
        headers=_as(PRIYA),
    )
    assert response.status_code == 403
    body = response.json()
    assert body["error"] == "permission_denied"
    assert "own group" in body["reason"]
    assert "required_scope" not in body
    encoded = json.dumps(body)
    assert "total_tokens" not in encoded
    assert "cost" not in encoded
    assert "platforms" not in encoded


def test_prod_member_is_denied_on_usage_and_capabilities(client):
    api = client()
    response = api.get("/api/usage", headers=_as(DANIEL))
    assert response.status_code == 403
    assert response.json()["required_scope"] == "usage:read"
    caps = api.get("/api/capabilities", headers=_as(DANIEL))
    assert caps.status_code == 403
    assert "total_tokens" not in json.dumps(caps.json())


def test_admin_can_read_another_group_and_change_a_capability(client, tmp_path):
    db = tmp_path / "persist.db"
    api = client(db_name="persist.db")
    summary = api.get(
        "/api/usage/summary",
        params={"period": "2026-09", "group": "hr"},
        headers=_as(CHLOE),
    )
    assert summary.status_code == 200
    assert summary.json()["group"] == "hr"

    before = api.get("/api/capabilities", params={"group": "finance"}, headers=_as(CHLOE))
    code = next(row for row in before.json() if row["capability"] == "code-execution")
    assert code["enabled"] is False
    assert code["updated_by"] is None

    updated = api.put(
        "/api/capabilities",
        headers=_as(CHLOE),
        json={"group": "finance", "capability": "code-execution", "enabled": True},
    )
    assert updated.status_code == 200
    assert updated.json()["enabled"] is True
    assert updated.json()["updated_by"] == CHLOE

    refused = api.put(
        "/api/capabilities",
        headers=_as(PRIYA),
        json={"group": "clinical-operations", "capability": "web-search", "enabled": False},
    )
    assert refused.status_code == 403
    assert refused.json()["required_scope"] == "capabilities:write"

    api.app.state.store.close()
    again = client(db_name="persist.db")
    kept = again.get("/api/capabilities", params={"group": "finance"}, headers=_as(CHLOE))
    code = next(row for row in kept.json() if row["capability"] == "code-execution")
    assert code["enabled"] is True
    web = next(row for row in kept.json() if row["capability"] == "web-search")
    # Priya's refused write did not land, including on her own group.
    priya_caps = again.get(
        "/api/capabilities", params={"group": "clinical-operations"}, headers=_as(CHLOE)
    )
    priya_web = next(row for row in priya_caps.json() if row["capability"] == "web-search")
    assert priya_web["enabled"] is True
    assert web["enabled"] is True
    assert db.exists()


def test_staging_lead_can_toggle_own_group_only(client):
    api = client("staging")
    ok = api.put(
        "/api/capabilities",
        headers=_as(PRIYA),
        json={"group": "clinical-operations", "capability": "code-execution", "enabled": True},
    )
    assert ok.status_code == 200
    denied = api.put(
        "/api/capabilities",
        headers=_as(PRIYA),
        json={"group": "hr", "capability": "code-execution", "enabled": True},
    )
    assert denied.status_code == 403
    assert denied.json()["error"] == "permission_denied"
    hr = api.get("/api/capabilities", params={"group": "hr"}, headers=_as(CHLOE))
    # Chloe can read hr in staging. The toggle above must not have changed it.
    assert hr.status_code == 200
    code = next(row for row in hr.json() if row["capability"] == "code-execution")
    assert code["enabled"] is False


def test_dev_member_can_read_another_group(client):
    api = client("dev")
    response = api.get(
        "/api/usage/top-users",
        params={"period": "last_7_days", "group": "medical-writing", "limit": 3},
        headers=_as(DANIEL),
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) <= 3
    assert body
    assert {row["group"] for row in body} == {"medical-writing"}
    assert body[0]["total_tokens"] >= body[-1]["total_tokens"]


def test_usage_page_breaks_down_by_platform_group_and_week(client):
    api = client()
    response = api.get("/api/usage", params={"week": "2026-W39"}, headers=_as(CHLOE))
    assert response.status_code == 200
    body = response.json()
    assert {row["week"] for row in body["by_week"]} == {"2026-W39"}
    assert {row["platform"] for row in body["by_platform"]} == {"claude", "gemini"}
    assert len(body["by_group"]) == 6


def test_missing_identity_is_not_a_usage_response(client):
    api = client()
    response = api.get("/api/usage/summary", params={"period": "last_7_days"})
    assert response.status_code == 401
    assert response.json()["error"] == "unauthenticated"
