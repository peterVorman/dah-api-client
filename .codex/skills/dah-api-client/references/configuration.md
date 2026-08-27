# Configuration

## License And DAH Terms

The repository or skill package `LICENSE` is source-available and restricted-use.
It does not grant rights to DAH services, APIs, data, trademarks, UI,
documentation, or infrastructure. Use the client only with authorized DAH
accounts and within the user's authority for the relevant association.

Treat DAH responses as potentially personal, financial, or association-confidential
data. Do not commit captured API responses, tokens, exported reports, chat
content, phone numbers, emails, names, user ids, or tenant ids unless the user
explicitly asks and the data is appropriate for the repository.

Do not provide DAH access, token acquisition help, account support, billing
support, association support, or operational DAH troubleshooting.

## Environment

Use `DahApiConfig.from_env()` for scripts that should respect the user's shell
environment.

Supported variables:

- `DAH_BASE_URL`: API base URL, default `https://api.dah-online.com`.
- `DAH_BEARER_TOKEN`: bearer token for live API calls.
- `DAH_REFRESH_TOKEN`: refresh token for `authentication-relogin`.
- `DAH_LOGIN`: login for `authentication-web-login`.
- `DAH_PASSWORD`: password for `authentication-web-login`.
- `DAH_ASSOCIATION_ID`: optional association id override. When absent, scoped
  endpoints resolve the single available association id from `get_access`.
- `DAH_TAB_ID`: optional `X-DAH-TabId`.
- `DAH_DEVICE_ID`: device id for `authentication-relogin`.
- `DAH_ORIGIN`: Origin header, default `https://cabinet.dah-online.com`.
- `DAH_REFERER`: Referer header, default `https://cabinet.dah-online.com/`.
- `DAH_USER_AGENT`: User-Agent header.
- `SSL_CERT_FILE`: optional custom CA bundle path. When unset, the client uses
  `certifi` for TLS certificate verification.

`.env.local` supports plain `KEY=value` lines, blank lines, and comments. It does
not implement shell syntax or quoting.

## Authentication Workflow

- `python3 main.py auth-status` inspects token presence, JWT expiry when
  available, and `get_access` reachability without printing token values.
- `python3 main.py authentication-web-login --save-env-local` saves recognized
  auth fields from the sanitized DAH login response into `.env.local`.
- `python3 main.py authentication-relogin --save-env-local` refreshes a session
  from `DAH_REFRESH_TOKEN` and `DAH_DEVICE_ID`.
- `python3 main.py authentication-exit` ends the active DAH session.

Read-only CLI commands retry once on `401` responses that contain
`invalid_access_token`. The retry first uses relogin when `DAH_REFRESH_TOKEN` is
available, then falls back to web login when `DAH_LOGIN` and `DAH_PASSWORD` are
available. Write commands do not auto-retry to avoid duplicate writes.

Never print bearer tokens, refresh tokens, logins, or passwords. Do not pass
tokens through CLI arguments.
