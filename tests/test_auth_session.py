import base64
import json
from datetime import UTC, datetime, timedelta

from auth_session import (
    auth_env_updates,
    auth_status,
    jwt_payload,
    sanitize_auth_response,
    save_auth_env,
)


def encoded_payload(payload):
    raw = json.dumps(payload).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def invalid_json_payload():
    return base64.urlsafe_b64encode(b"{").decode("ascii").rstrip("=")


def test_auth_status_and_jwt_payload():
    exp = int((datetime.now(UTC) + timedelta(hours=1)).timestamp())
    token = f"header.{encoded_payload({'exp': exp, 'sub': 'user'})}.signature"

    assert (
        jwt_payload(token),
        jwt_payload(f"header.{invalid_json_payload()}.signature"),
        auth_status(token, {"id": "access"})["accessCheck"],
        auth_status("")["accessCheck"],
        auth_status(token)["bearerTokenExpiresAt"],
    ) == (
        {"exp": exp, "sub": "user"},
        {},
        {"ok": True},
        {"ok": False, "error": "missing bearer token"},
        datetime.fromtimestamp(exp, UTC).isoformat(),
    )
    assert auth_status(token)["bearerTokenExpired"] is False


def test_auth_env_update_save_and_sanitize(tmp_path):
    response = [
        {
            "login": "login",
            "nested": {
                "accessToken": "access-token",
                "refreshToken": "refresh-token",
                "deviceId": "device-id",
                "visible": "kept",
            },
        }
    ]
    env_path = tmp_path / ".env.local"
    env_path.write_text("DAH_BEARER_TOKEN=old\nOTHER=value\n", encoding="utf-8")

    assert (
        auth_env_updates(response),
        save_auth_env(response, env_path),
        env_path.read_text(encoding="utf-8"),
        sanitize_auth_response(response),
    ) == (
        {
            "DAH_BEARER_TOKEN": "access-token",
            "DAH_REFRESH_TOKEN": "refresh-token",
            "DAH_DEVICE_ID": "device-id",
        },
        {
            "path": str(env_path),
            "keys": ["DAH_BEARER_TOKEN", "DAH_DEVICE_ID", "DAH_REFRESH_TOKEN"],
        },
        (
            "DAH_BEARER_TOKEN=access-token\n"
            "OTHER=value\n"
            "DAH_REFRESH_TOKEN=refresh-token\n"
            "DAH_DEVICE_ID=device-id\n"
        ),
        [
            {
                "login": "<redacted>",
                "nested": {
                    "accessToken": "<redacted>",
                    "refreshToken": "<redacted>",
                    "deviceId": "device-id",
                    "visible": "kept",
                },
            }
        ],
    )
