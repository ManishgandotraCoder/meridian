import json

import pytest

from provision.render import ProvisionError, render_all, validate


def test_render_writes_three_environments_and_validates(tmp_path):
    from pathlib import Path

    repo = Path(__file__).resolve().parents[2]
    output = tmp_path / "environments"
    written = render_all(repo, output)
    assert len(written) == 9
    prod = json.loads((output / "prod" / "permissions.json").read_text())
    assert prod["scopes"]["capabilities:write"]["roles"] == ["platform_admin"]
    assert prod["capability_defaults"]["usage-connector"]["finance"] is False
    assert prod["capability_defaults"]["usage-connector"]["clinical-operations"] is True
    assert prod["capability_defaults"]["usage-connector"]["it-platform"] is True
    desktop = json.loads((output / "dev" / "claude_desktop_config.json").read_text())
    assert "meridian-usage-dev" in desktop["mcpServers"]
    assert desktop["mcpServers"]["meridian-usage-dev"]["env"]["MERIDIAN_ACTOR_USER_ID"] == ""
    gemini = json.loads((output / "staging" / "gemini_cli_settings.json").read_text())
    staging = gemini["mcpServers"]["meridian-usage-staging"]
    assert staging["env"]["MERIDIAN_ENV"] == "staging"
    assert staging["env"]["MERIDIAN_ROOT"] == str(repo)
    assert staging["env"]["MERIDIAN_ACTOR_USER_ID"] == ""
    assert staging["args"] == [str(repo / "connector" / "dist" / "index.js")]
    assert staging["cwd"] == str(repo / "connector")


def test_validator_rejects_a_prod_manifest_that_widens_write(tmp_path):
    from pathlib import Path

    repo = Path(__file__).resolve().parents[2]
    output = tmp_path / "environments"
    render_all(repo, output)
    permissions = json.loads((output / "prod" / "permissions.json").read_text())
    claude = json.loads((output / "prod" / "claude_desktop_config.json").read_text())
    gemini = json.loads((output / "prod" / "gemini_cli_settings.json").read_text())
    permissions["scopes"]["capabilities:write"]["roles"] = ["team_lead", "platform_admin"]
    with pytest.raises(ProvisionError, match="platform_admin only"):
        validate(permissions, claude, gemini, list(permissions["capability_defaults"]["web-search"]))
