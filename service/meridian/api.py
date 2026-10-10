"""Stable import path for the HTTP service.

Tests and `python -m meridian` come through here. Construction lives in
meridian.app; the routes live in meridian.http.
"""

from meridian.app import app_from_env, create_app, main

__all__ = ["app_from_env", "create_app", "main"]
