"""One command, three environments.

Reads starter-kit/environments/*.yaml and writes a permissions manifest plus
the Claude Desktop and Gemini CLI registration files for each one. The YAML
stays the source. Nothing under build/ is meant to be hand-edited: run this
again.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from meridian.config import CAPABILITIES, ROLES, expand_capability_defaults, load_environment
from meridian.directory import load_directory

ENVIRONMENTS = ("dev", "staging", "prod")


class ProvisionError(Exception):
    pass


def render_all(root: Path, output: Path) -> List[Path]:
    directory = load_directory(root / "starter-kit" / "data" / "directory")
    group_ids = list(directory.group_ids())
    written: List[Path] = []
    seen_names = set()
    for name in ENVIRONMENTS:
        env = load_environment(root / "starter-kit" / "environments" / ("%s.yaml" % name))
        if env.server_name in seen_names:
            raise ProvisionError("server_name %s is used more than once" % env.server_name)
        seen_names.add(env.server_name)
        permissions = permissions_manifest(env, group_ids)
        claude = claude_desktop_config(root, env)
        gemini = gemini_settings(root, env)
        validate(permissions, claude, gemini, group_ids)
        dest = output / name
        dest.mkdir(parents=True, exist_ok=True)
        written.append(_write(dest / "permissions.json", permissions))
        written.append(_write(dest / "claude_desktop_config.json", claude))
        written.append(_write(dest / "gemini_cli_settings.json", gemini))
    return written


def permissions_manifest(env, group_ids: List[str]) -> dict:
    return {
        "environment": env.name,
        "scopes": {
            "usage:read": {
                "roles": list(env.usage_read_roles),
                "group_visibility": env.group_visibility,
            },
            "capabilities:write": {
                "roles": list(env.write_roles),
            },
        },
        "capability_defaults": expand_capability_defaults(env, group_ids),
        "host": {"server_name": env.server_name},
    }


def claude_desktop_config(root: Path, env) -> dict:
    entry = _server_entry(root, env)
    return {"mcpServers": {env.server_name: entry}}


def gemini_settings(root: Path, env) -> dict:
    # This fragment is merged into Gemini settings.json. ${extensionPath} and
    # ${workspacePath} are substituted only inside an extension manifest, so
    # the rendered file uses the checkout path. The actor is left empty.
    entry = _server_entry(root, env)
    entry["cwd"] = str(root / "connector")
    return {"mcpServers": {env.server_name: entry}}


def _server_entry(root: Path, env) -> dict:
    return {
        "command": "node",
        "args": [str(root / "connector" / "dist" / "index.js")],
        "env": {
            "MERIDIAN_ENV": env.name,
            "MERIDIAN_ROOT": str(root),
            "MERIDIAN_API_URL": "http://127.0.0.1:8000",
            "MERIDIAN_ACTOR_USER_ID": "",
        },
    }


def validate(permissions: dict, claude: dict, gemini: dict, group_ids: List[str]) -> None:
    name = permissions["environment"]
    if name not in ENVIRONMENTS:
        raise ProvisionError("unexpected environment %s" % name)
    read = permissions["scopes"]["usage:read"]
    write = permissions["scopes"]["capabilities:write"]
    for role in read["roles"] + write["roles"]:
        if role not in ROLES:
            raise ProvisionError("%s grants an unknown role %s" % (name, role))
    if read["group_visibility"] not in ("all", "own_group"):
        raise ProvisionError("%s has a bad group_visibility" % name)
    defaults = permissions["capability_defaults"]
    if set(defaults) != set(CAPABILITIES):
        raise ProvisionError("%s capability set is %s" % (name, sorted(defaults)))
    for capability, groups in defaults.items():
        if set(groups) != set(group_ids):
            raise ProvisionError("%s did not expand %s to every group" % (name, capability))
        if not all(isinstance(value, bool) for value in groups.values()):
            raise ProvisionError("%s left a shorthand default in %s" % (name, capability))

    if name == "dev":
        if read["group_visibility"] != "all":
            raise ProvisionError("dev must be able to read every group")
        if "member" not in read["roles"]:
            raise ProvisionError("dev must grant usage:read to members")
        if set(write["roles"]) != {"team_lead", "platform_admin"}:
            raise ProvisionError("dev write roles drifted")
    if name in ("staging", "prod"):
        if read["group_visibility"] != "own_group":
            raise ProvisionError("%s must limit group visibility to the caller's group" % name)
        if "member" in read["roles"]:
            raise ProvisionError("%s must not grant usage:read to members" % name)
    if name == "prod":
        if write["roles"] != ["platform_admin"]:
            raise ProvisionError("prod capabilities:write must be platform_admin only")
        connector = defaults["usage-connector"]
        enabled = sorted(group for group, on in connector.items() if on)
        if enabled != ["clinical-operations", "it-platform"]:
            raise ProvisionError("prod usage-connector enabled for %s" % enabled)
        if any(defaults["code-execution"].values()):
            raise ProvisionError("prod code-execution must be disabled")
        if not all(defaults["web-search"].values()):
            raise ProvisionError("prod web-search must be enabled")
    if name == "staging":
        if set(write["roles"]) != {"team_lead", "platform_admin"}:
            raise ProvisionError("staging write roles drifted")
        if any(defaults["code-execution"].values()):
            raise ProvisionError("staging code-execution must be disabled")

    server_name = permissions["host"]["server_name"]
    if not server_name:
        raise ProvisionError("%s is missing a server name" % name)
    for document, label in ((claude, "claude"), (gemini, "gemini")):
        servers = document["mcpServers"]
        if list(servers) != [server_name]:
            raise ProvisionError("%s %s registration is not named %s" % (name, label, server_name))
        entry = servers[server_name]
        if entry["command"] != "node" or not entry["args"]:
            raise ProvisionError("%s %s registration does not start the connector" % (name, label))
        if entry["env"]["MERIDIAN_ENV"] != name:
            raise ProvisionError("%s %s registration points at the wrong environment" % (name, label))
        if entry["env"].get("MERIDIAN_ACTOR_USER_ID"):
            raise ProvisionError("refusing to bake a user id into %s %s" % (name, label))
        if "MERIDIAN_ACTOR_USER_ID" not in entry["env"]:
            raise ProvisionError("%s %s registration is missing the actor variable" % (name, label))
    script = gemini["mcpServers"][server_name]["args"][0]
    if "${" in script or not (
        script.endswith("connector/dist/index.js") or script.endswith("connector\\dist\\index.js")
    ):
        raise ProvisionError(
            "%s gemini registration must point at the built connector" % name
        )


def _write(path: Path, document: dict) -> Path:
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return path
