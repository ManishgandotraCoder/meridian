"""Admin and connector routes.

Every read and write loads the caller from the header, then asks
meridian.auth before it touches a number. A refusal is a 403 with the
denial object and no usage figures.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from meridian.auth import PermissionDenied, can_write_group, require_read, require_write, visible_group_ids
from meridian.config import CAPABILITIES, DATA_AS_OF, Environment
from meridian.directory import User
from meridian.http.errors import APIError, bad_group
from meridian.http.identity import current_user, directory_of
from meridian.periods import InvalidPeriod, resolve_period
from meridian.query import by_group, by_week, detail_rows, platform_totals, top_users, totals
from meridian.store import Store

router = APIRouter()


class CapabilityUpdate(BaseModel):
    group: str
    capability: str
    enabled: bool


def _env(request: Request) -> Environment:
    return request.app.state.env


def _store(request: Request) -> Store:
    return request.app.state.store


def _window(period: str):
    try:
        return resolve_period(period)
    except InvalidPeriod as exc:
        raise APIError(400, {"error": "invalid_argument", "reason": str(exc)}) from exc


def _readable_groups(request: Request, user: User, group: Optional[str]) -> list:
    env = _env(request)
    directory = directory_of(request)
    visible = visible_group_ids(user, env, directory.group_ids())
    if user.role not in env.usage_read_roles:
        raise PermissionDenied(
            "%s does not have usage:read in %s." % (user.role, env.name),
            "usage:read",
        )
    if group is None:
        return visible
    if group not in directory.groups_by_id:
        raise bad_group()
    require_read(user, env, group)
    return [group]


def _one_group(request: Request, user: User, group: Optional[str]) -> str:
    if group is None:
        return user.own_group
    if group not in directory_of(request).groups_by_id:
        raise bad_group()
    return group


@router.get("/api/health")
def health(request: Request) -> dict:
    return {"ok": True, "environment": _env(request).name}


@router.get("/api/meta")
def meta(request: Request) -> dict:
    env = _env(request)
    return {
        "environment": env.name,
        "server_name": env.server_name,
        "group_visibility": env.group_visibility,
        "usage_read_roles": list(env.usage_read_roles),
        "write_roles": list(env.write_roles),
        "as_of": DATA_AS_OF,
    }


@router.get("/api/directory/users")
def list_users(request: Request) -> dict:
    directory = directory_of(request)
    users = [
        {
            "user_id": user.user_id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "group_ids": list(user.group_ids),
        }
        for user in directory.users_by_id.values()
    ]
    users.sort(key=lambda item: (item["group_ids"][0], item["name"]))
    groups = [
        {"group_id": group.group_id, "name": group.name}
        for group in directory.groups_by_id.values()
    ]
    groups.sort(key=lambda item: item["name"])
    return {"users": users, "groups": groups}


@router.get("/api/me")
def me(request: Request) -> dict:
    user = current_user(request)
    env = _env(request)
    directory = directory_of(request)
    return {
        "user_id": user.user_id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "groups": list(user.group_ids),
        "visible_groups": visible_group_ids(user, env, directory.group_ids()),
        "writable_groups": [
            group_id
            for group_id in directory.group_ids()
            if can_write_group(user, env, group_id)
        ],
    }


@router.get("/api/usage")
def usage(request: Request, group: Optional[str] = None, week: Optional[str] = None) -> dict:
    user = current_user(request)
    rows = _store(request).usage_rows(group_ids=_readable_groups(request, user, group), iso_week=week)
    return {
        "group": group,
        "week": week,
        "by_platform": platform_totals(rows),
        "by_group": by_group(rows),
        "by_week": by_week(rows),
        "rows": detail_rows(rows),
        "weeks": _store(request).weeks(),
    }


@router.get("/api/usage/summary")
def usage_summary(request: Request, period: str, group: Optional[str] = None) -> dict:
    user = current_user(request)
    window = _window(period)
    group_id = _one_group(request, user, group)
    require_read(user, _env(request), group_id)
    rows = _store(request).usage_rows(
        group_ids=[group_id],
        day_start=window.start.isoformat(),
        day_end_exclusive=window.end_exclusive.isoformat(),
    )
    platforms = platform_totals(rows)
    return {
        "group": group_id,
        "period": window.as_dict(),
        "platforms": platforms,
        "totals": totals(platforms),
    }


@router.get("/api/usage/top-users")
def usage_top_users(
    request: Request,
    period: str,
    group: Optional[str] = None,
    limit: int = 10,
) -> list:
    user = current_user(request)
    if limit < 1 or limit > 25:
        raise APIError(400, {"error": "invalid_argument", "reason": "limit must be from 1 to 25."})
    window = _window(period)
    group_id = _one_group(request, user, group)
    require_read(user, _env(request), group_id)
    rows = _store(request).usage_rows(
        group_ids=[group_id],
        day_start=window.start.isoformat(),
        day_end_exclusive=window.end_exclusive.isoformat(),
    )
    return top_users(rows, directory_of(request), limit)


@router.get("/api/capabilities")
def capability_status(request: Request, group: Optional[str] = None) -> list:
    user = current_user(request)
    env = _env(request)
    directory = directory_of(request)
    if group is None:
        group_ids = visible_group_ids(user, env, directory.group_ids())
        if not group_ids and user.role not in env.usage_read_roles:
            raise PermissionDenied(
                "%s does not have usage:read in %s." % (user.role, env.name),
                "usage:read",
            )
        return _store(request).capabilities(group_ids)
    if group not in directory.groups_by_id:
        raise bad_group()
    require_read(user, env, group)
    return _store(request).capabilities([group])


@router.put("/api/capabilities")
def set_capability(request: Request, body: CapabilityUpdate) -> dict:
    user = current_user(request)
    directory = directory_of(request)
    if body.group not in directory.groups_by_id:
        raise bad_group()
    if body.capability not in CAPABILITIES:
        raise APIError(
            400,
            {
                "error": "invalid_argument",
                "reason": "capability must be one of %s." % ", ".join(CAPABILITIES),
            },
        )
    require_write(user, _env(request), body.group)
    try:
        return _store(request).set_capability(body.group, body.capability, body.enabled, user.user_id)
    except KeyError as exc:
        raise APIError(404, {"error": "not_found", "reason": str(exc)}) from exc
