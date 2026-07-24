"""Authentication session helpers for the DAH CLI."""

from __future__ import annotations

import base64
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

AUTH_TOKEN_KEYS = ("accessToken", "bearerToken", "token", "jwt")
AUTH_REFRESH_TOKEN_KEYS = ("refreshToken",)
AUTH_DEVICE_ID_KEYS = ("deviceId",)
ENV_PATH = ".env.local"


def auth_status(token: str, access_data: Any = None, error: str | None = None) -> dict:
    payload = jwt_payload(token)
    exp = payload.get("exp") if payload else None
    return {
        "bearerTokenPresent": bool(token),
        "bearerTokenExpiresAt": expires_at(exp),
        "bearerTokenExpired": expired(exp),
        "accessCheck": access_check(access_data, error, bool(token)),
    }


def jwt_payload(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    try:
        return json.loads(decode_urlsafe_base64(parts[1]))
    except (ValueError, TypeError, json.JSONDecodeError):
        return {}


def decode_urlsafe_base64(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def expires_at(exp: Any) -> str | None:
    if not isinstance(exp, int):
        return None
    return datetime.fromtimestamp(exp, UTC).isoformat()


def expired(exp: Any) -> bool | None:
    if not isinstance(exp, int):
        return None
    return datetime.now(UTC).timestamp() >= exp


def access_check(access_data: Any, error: str | None, has_token: bool) -> dict:
    if error:
        return {"ok": False, "error": error}
    if not has_token:
        return {"ok": False, "error": "missing bearer token"}
    return {"ok": access_data is not None}


def save_auth_env(response: Any, path: str | os.PathLike[str] = ENV_PATH) -> dict:
    updates = auth_env_updates(response)
    if updates:
        update_env_file(path, updates)
    return {"path": str(path), "keys": sorted(updates)}


def auth_env_updates(response: Any) -> dict[str, str]:
    return {
        env_key: value
        for env_key, keys in {
            "DAH_BEARER_TOKEN": AUTH_TOKEN_KEYS,
            "DAH_REFRESH_TOKEN": AUTH_REFRESH_TOKEN_KEYS,
            "DAH_DEVICE_ID": AUTH_DEVICE_ID_KEYS,
        }.items()
        if (value := first_string_for_keys(response, keys))
    }


def first_string_for_keys(value: Any, keys: tuple[str, ...]) -> str | None:
    if isinstance(value, dict):
        return first_string_from_dict(value, keys)
    if isinstance(value, list):
        return first_string_from_list(value, keys)
    return None


def first_string_from_dict(value: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        if isinstance(value.get(key), str) and value[key]:
            return value[key]
    return first_string_from_list(list(value.values()), keys)


def first_string_from_list(values: list[Any], keys: tuple[str, ...]) -> str | None:
    for item in values:
        if found := first_string_for_keys(item, keys):
            return found
    return None


def update_env_file(path: str | os.PathLike[str], updates: dict[str, str]) -> None:
    env_path = Path(path)
    lines = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    env_path.write_text(env_text(lines, updates), encoding="utf-8")


def env_text(lines: list[str], updates: dict[str, str]) -> str:
    seen = set()
    rendered = [env_line(line, updates, seen) for line in lines]
    rendered.extend(
        f"{key}={value}" for key, value in updates.items() if key not in seen
    )
    return "\n".join(rendered).rstrip() + "\n"


def env_line(line: str, updates: dict[str, str], seen: set[str]) -> str:
    key = line.split("=", 1)[0].strip()
    if key in updates:
        seen.add(key)
        return f"{key}={updates[key]}"
    return line


def sanitize_auth_response(response: Any) -> Any:
    if isinstance(response, dict):
        return sanitize_auth_dict(response)
    if isinstance(response, list):
        return sanitize_auth_list(response)
    return response


def sanitize_auth_dict(response: dict[str, Any]) -> dict[str, Any]:
    return {
        key: sanitized_auth_value(key, value)
        for key, value in response.items()
    }


def sanitize_auth_list(response: list[Any]) -> list[Any]:
    return [sanitize_auth_response(item) for item in response]


def sanitized_auth_value(key: str, value: Any) -> Any:
    if sensitive_key(key):
        return "<redacted>"
    return sanitize_auth_response(value)


def sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return "token" in lowered or lowered in {"password", "login"}
