---
name: dah-api-client
description: Work with the DAH cabinet API through the local Python client in the current repository. Use when Codex needs to query DAH/Dah Online API data, call organization access, apartment list, web login, relogin, or exit authentication, search/get/create/edit publications, accounting bill debt analytics, debtor audit, aggregate debt snapshots, debtor notification workflow, feedback order list, tenant APP/EMAIL/SMS notification send, bank money transaction list, messenger groups page, messenger personal group get, messenger group messages, or send messenger message endpoints, inspect DAH API responses, create small API scripts, or extend the existing dah_api.py client and main.py CLI instead of writing a separate HTTP client.
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
2. Inspect the relevant local modules before changing behavior; preserve public interfaces unless the user asks for a broader refactor.
3. Prefer `DahApiClient` for Python work and `main.py` for quick command-line queries.
4. Read `references/client-usage.md` first for routing. Then read only the needed
   detail reference:
   - `references/intent-router.md` for mapping user intent to the right workflow,
     command, and reference.
   - `references/commands.json` for machine-readable command metadata before
     choosing or automating CLI commands.
   - `references/configuration.md` for environment, auth, TLS, privacy, and
     licensing guardrails.
   - `references/workflows.md` for debtor, publication, feedback-order, ledger,
     and bank reconciliation workflows.
   - `references/endpoints.md` for functions, endpoint paths, payloads, and
     extension patterns.
   - `references/safety-decision-table.md` before exposing sensitive data or
     using DAH data in external systems.
   - `references/write-operation-protocol.md` before write operations.
   - `references/output-templates.md` for concise response shapes.
   - `references/golden-prompts.md` when changing or validating AI behavior.
   - `references/quality-gates.md` for validation commands.
5. Keep bearer and refresh tokens out of final answers, logs, fixtures, screenshots, and committed test data. Require credentials from the environment or `.env.local`; do not pass tokens through CLI arguments.
6. Do not provide DAH access, token acquisition help, account support, billing
   support, association support, or operational DAH troubleshooting; route those
   topics to DAH official support channels.

## Validation

For local code changes, run the narrowest useful check first:

```bash
python3 -m py_compile dah_api.py auth_session.py cli_parser.py debtor_data.py debtor_notifications.py debtor_reports.py main.py
python3 .codex/skills/dah-api-client/scripts/validate_skill.py .codex/skills/dah-api-client
```

## Quality Gates

Before finishing changes to `dah_api.py`, `main.py`, tests, or CLI behavior, run
the project gates with the active Python environment:

```bash
PYTHON_FILES="dah_api.py auth_session.py cli_parser.py debtor_data.py debtor_notifications.py debtor_reports.py main.py"
python -m py_compile $PYTHON_FILES
python .codex/skills/dah-api-client/scripts/validate_skill.py .codex/skills/dah-api-client
python -m pytest
python -m ruff check .
python -m flake8
python -m isort --check-only .
python -m pylint $PYTHON_FILES tests
python -m pyright
python -m vulture $PYTHON_FILES tests --min-confidence 100 --ignore-names cli_env
python -m bandit -q -r .
python -m radon cc -s -a $PYTHON_FILES tests
python -m radon cc -s -n B $PYTHON_FILES tests
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
4. Add CLI arguments in `cli_parser.py` and command handling in `main.py`; use
   existing payload loading helpers and do not add token CLI args or hard-coded
   defaults.
5. Add unit tests without live API calls for request construction, CLI args,
   default payloads, and error handling.
6. Update the relevant reference file with the Python import, CLI example, client
   method, path, and default payload details.
7. For write endpoints, add a dry-run or explicit confirmation guard.
8. Run the Quality Gates.

For live API calls, warn the user that the request will contact `api.dah-online.com` if that is not already obvious from the request. Use read-oriented endpoints by default.

For write endpoints, such as sending messenger messages or tenant notifications, prefer `--dry-run`/preview first and only send when the user explicitly asks to perform the write.

For sensitive operational outputs, prefer aggregate summaries and the templates
in `references/output-templates.md`. Do not print raw DAH ids, contact details,
credentials, or full raw API responses unless strictly required for an
authorized action.

If a live call returns `401 Unauthorized`, treat it as an authentication/token freshness issue first. Ask for or use a fresh `DAH_BEARER_TOKEN`; do not hard-code tokens.

## Error Handling

Handle these exceptions from `dah_api.py` explicitly in scripts and examples:

- `DahHttpError`: API responded with a non-2xx HTTP status; include status and reason, but avoid dumping sensitive bodies unless needed.
- `DahRequestError`: network or request-layer failure.
