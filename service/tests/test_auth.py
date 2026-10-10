import pytest

from meridian.auth import PermissionDenied, can_see_group, require_read, require_write
from meridian.config import environment_path, load_environment

from tests.conftest import CHLOE, DANIEL, MEI, PRIYA, ROOT


def _env(name):
    return load_environment(environment_path(ROOT, name))


def _denied(action, fragment):
    with pytest.raises(PermissionDenied) as caught:
        action()
    assert fragment in caught.value.reason
    return caught.value


def test_prod_team_lead_sees_only_their_group(directory):
    env = _env("prod")
    priya = directory.user(PRIYA)
    require_read(priya, env, "clinical-operations")
    denied = _denied(lambda: require_read(priya, env, "finance"), "own group")
    assert denied.required_scope is None
    assert can_see_group(priya, env, "regulatory-affairs") is False


def test_prod_member_cannot_read_or_write(directory):
    env = _env("prod")
    daniel = directory.user(DANIEL)
    denied = _denied(lambda: require_read(daniel, env, "clinical-operations"), "usage:read")
    assert denied.required_scope == "usage:read"
    _denied(lambda: require_write(daniel, env, "clinical-operations"), "capabilities:write")


def test_prod_admin_can_read_and_write_every_group(directory):
    env = _env("prod")
    chloe = directory.user(CHLOE)
    require_read(chloe, env, "hr")
    require_write(chloe, env, "medical-writing")


def test_prod_team_lead_cannot_change_capabilities(directory):
    env = _env("prod")
    denied = _denied(
        lambda: require_write(directory.user(PRIYA), env, "clinical-operations"),
        "capabilities:write",
    )
    assert denied.required_scope == "capabilities:write"


def test_dev_member_can_read_any_group_but_not_write(directory):
    env = _env("dev")
    daniel = directory.user(DANIEL)
    require_read(daniel, env, "finance")
    _denied(lambda: require_write(daniel, env, "clinical-operations"), "capabilities:write")


def test_staging_lead_can_write_own_group_only(directory):
    env = _env("staging")
    priya = directory.user(PRIYA)
    mei = directory.user(MEI)
    require_write(priya, env, "clinical-operations")
    _denied(lambda: require_write(priya, env, "regulatory-affairs"), "own group")
    require_read(mei, env, "regulatory-affairs")
    _denied(lambda: require_read(mei, env, "clinical-operations"), "own group")
