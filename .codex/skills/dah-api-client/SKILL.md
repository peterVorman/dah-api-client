---
name: dah-api-client
description: Work with the DAH cabinet API through the local Python client in the current repository. Use when Codex needs to query DAH/Dah Online API data, call organization access, relogin authentication, search/get/create/edit publications, accounting bill debt analytics, feedback order list, bank money transaction list, messenger groups page, messenger group messages, or send messenger message endpoints, inspect DAH API responses, create small API scripts, or extend the existing dah_api.py client and main.py CLI instead of writing a separate HTTP client.
---

# DAH API Client

## Core Rule

Use the existing client code in the repository root as the integration boundary. Do not reimplement authentication, headers, JSON decoding, or endpoint URLs unless the task is explicitly to change that client.

For DAH publications, use `get_publication`/`save_publication`. Formatted
publication bodies must send the same HTML in both `description` and
`descriptionHtml`; otherwise DAH can save the announcement as unformatted plain
text.

Respect the repository or skill package `LICENSE`: this is source-available
restricted-use tooling for authorized DAH accounts only. Do not present it as an
official DAH integration, do not imply rights to DAH services, APIs, data,
trademarks, or infrastructure, and keep personal, financial, association, and
credential data out of artifacts unless the user explicitly asks for a necessary
authorized operation.

## Workflow

1. Set the working directory to the repository root that contains `dah_api.py` and `main.py`.
2. Inspect `dah_api.py` and `main.py` before changing behavior; preserve their public interfaces unless the user asks for a broader refactor.
3. Prefer `DahApiClient` for Python work and `main.py` for quick command-line queries.
4. Read `references/client-usage.md` when you need exact imports, CLI examples, endpoint details, or extension patterns.
5. Keep bearer and refresh tokens out of final answers, logs, fixtures, screenshots, and committed test data. Require credentials from the environment or `.env.local`; do not pass tokens through CLI arguments.
6. Do not provide DAH access, token acquisition help, account support, billing
   support, association support, or operational DAH troubleshooting; route those
   topics to DAH official support channels.

## Validation

For local code changes, run the narrowest useful check first:

```bash
python3 -m py_compile dah_api.py main.py
```

## Quality Gates

Before finishing changes to `dah_api.py`, `main.py`, tests, or CLI behavior, run
the project gates with the active Python environment:

```bash
python -m py_compile dah_api.py main.py
python -m pytest
python -m ruff check .
python -m flake8
python -m isort --check-only .
python -m bandit -q -r .
python -m radon cc -s -a dah_api.py main.py tests
python -m radon cc -s -n B dah_api.py main.py tests
```

Treat any output from the final `radon -n B` command as a failure: complexity
must stay at grade A. Fix failing gates before committing or reporting success.

## Endpoint Extension Checklist

When adding a DAH endpoint:

1. Add a small request dataclass in `dah_api.py` when query params, path params,
   or payload shape matter.
2. Add a `DahApiClient` method that delegates to `request_json`; keep auth,
   headers, JSON decoding, URL building, and association resolution in the
   existing client helpers.
3. Quote path ids with `urllib.parse.quote(..., safe="")`; use
   `get_default_association_id()` only for association-scoped endpoints.
4. Add a CLI subcommand and handler in `main.py`; use existing payload loading
   helpers and do not add token CLI args or hard-coded defaults.
5. Add unit tests without live API calls for request construction, CLI args,
   default payloads, and error handling.
6. Update `references/client-usage.md` with the Python import, CLI example,
   client method, path, and default payload details.
7. Run the Quality Gates.

For live API calls, warn the user that the request will contact `api.dah-online.com` if that is not already obvious from the request. Use read-oriented endpoints by default.

For write endpoints, such as sending messenger messages, prefer `--dry-run` first and only send when the user explicitly asks to perform the write.

If a live call returns `401 Unauthorized`, treat it as an authentication/token freshness issue first. Ask for or use a fresh `DAH_BEARER_TOKEN`; do not hard-code tokens.

## Error Handling

Handle these exceptions from `dah_api.py` explicitly in scripts and examples:

- `DahHttpError`: API responded with a non-2xx HTTP status; include status and reason, but avoid dumping sensitive bodies unless needed.
- `DahRequestError`: network or request-layer failure.
