"""API failures that are not permission denials.

Permission denials stay in meridian.auth. These are the other refusals
the HTTP boundary turns into a status code and a JSON body: a missing
caller, a bad argument, a missing row.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from meridian.auth import PermissionDenied


class APIError(Exception):
    def __init__(self, status_code: int, body: dict) -> None:
        super().__init__(body.get("reason", ""))
        self.status_code = status_code
        self.body = body


def permission_denied(_request: Request, exc: PermissionDenied) -> JSONResponse:
    return JSONResponse(status_code=403, content=exc.as_dict())


def api_error(_request: Request, exc: APIError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.body)


def bad_group() -> APIError:
    return APIError(400, {"error": "invalid_argument", "reason": "Unknown group."})
