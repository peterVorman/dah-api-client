---
name: dah-api-client
description: Work with the DAH cabinet API through the local Python client in /Users/pvorman/home_projects/Dah. Use when Codex needs to query DAH/Dah Online API data, call organization access, publications search, accounting bill debt analytics, feedback order list, messenger groups page, messenger group messages, or send messenger message endpoints, inspect DAH API responses, create small API scripts, or extend the existing dah_api.py client and main.py CLI instead of writing a separate HTTP client.
---

# DAH API Client

## Core Rule

Use the existing client code in `/Users/pvorman/home_projects/Dah` as the integration boundary. Do not reimplement authentication, headers, TLS fallback, JSON decoding, or endpoint URLs unless the task is explicitly to change that client.

## Workflow

1. Set the working directory to `/Users/pvorman/home_projects/Dah`.
2. Inspect `dah_api.py` and `main.py` before changing behavior; preserve their public interfaces unless the user asks for a broader refactor.
3. Prefer `DahApiClient` for Python work and `main.py` for quick command-line queries.
4. Read `references/client-usage.md` when you need exact imports, CLI examples, endpoint details, or extension patterns.
5. Keep tokens out of final answers, logs, fixtures, screenshots, and committed test data. Prefer `DAH_BEARER_TOKEN` from the environment.

## Validation

For local code changes, run the narrowest useful check first:

```bash
python3 -m py_compile dah_api.py main.py
```

For live API calls, warn the user that the request will contact `api.dah-online.com` if that is not already obvious from the request. Use read-oriented endpoints by default.

For write endpoints, such as sending messenger messages, prefer `--dry-run` first and only send when the user explicitly asks to perform the write.

If a live call returns `401 Unauthorized`, treat it as an authentication/token freshness issue first. Ask for or use a fresh `DAH_BEARER_TOKEN`; do not replace the client or hard-code a new token unless the user explicitly asks.

## Error Handling

Handle these exceptions from `dah_api.py` explicitly in scripts and examples:

- `DahHttpError`: API responded with a non-2xx HTTP status; include status and reason, but avoid dumping sensitive bodies unless needed.
- `DahRequestError`: network, TLS, or request-layer failure.

When TLS verification fails, the client already retries once without certificate checks unless `insecure=True`; do not add a second custom retry layer without a reason.
