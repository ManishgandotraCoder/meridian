"""Simulated caller. The X-User-Id header is a directory user id, not a session."""

from __future__ import annotations

from fastapi import Request

from meridian.directory import Directory, User
from meridian.http.errors import APIError


def directory_of(request: Request) -> Directory:
    return request.app.state.directory


def current_user(request: Request) -> User:
    user_id = request.headers.get("x-user-id")
    if not user_id:
        raise APIError(401, {"error": "unauthenticated", "reason": "Send the X-User-Id header."})
    user = directory_of(request).user(user_id)
    if user is None:
        raise APIError(401, {"error": "unauthenticated", "reason": "Unknown user."})
    return user
