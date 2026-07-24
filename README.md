# DAH API Client

Source-available Python client and Codex skill for selected DAH cabinet API
workflows.

## Status And Disclaimer

This project is unofficial and independent. It is not affiliated with,
endorsed by, sponsored by, or supported by DAH, TOV "Dah Development", or
related service operators.

This repository does not grant permission to use DAH services, APIs, accounts,
association data, trademarks, documentation, user interfaces, or infrastructure.
DAH access remains governed by DAH terms, the DAH privacy policy, agreements
with associations, and applicable law.

This repository is source-available, not open source. See [LICENSE](LICENSE).

## Authorized Use Only

Use this code only with a DAH account and association data that you are
authorized to access. Do not use it to discover, bypass, test, scrape, overload,
or extract data from DAH systems without permission.

The maintainer does not provide DAH access, tokens, account help, association
data, billing support, or operational support for DAH services.

## Data And Credentials

DAH responses may contain personal, financial, association-confidential, or chat
data. Keep those records out of public issues, pull requests, logs, screenshots,
fixtures, and commits unless they are intentionally sanitized.

Never publish bearer or refresh tokens, session data, exported DAH reports,
account IDs, chat content, or raw API responses from real associations.

## Usage

This project expects an already authorized DAH bearer token supplied through the
local environment. It does not document how to obtain one.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
export DAH_BEARER_TOKEN="<your authorized token>"
python main.py access
```

For local configuration, prefer `.env.local` with plain `KEY=value` lines. That
file is ignored by git.

TLS certificate verification uses the bundled `certifi` CA bundle by default,
so a manual `SSL_CERT_FILE` export is not required for normal use.

## Quality Checks

```bash
python -m py_compile dah_api.py auth_session.py debtor_notifications.py main.py
python -m pytest
python -m ruff check .
python -m flake8
python -m isort --check-only .
python -m pylint dah_api.py auth_session.py debtor_notifications.py main.py tests
python -m pyright
python -m vulture dah_api.py auth_session.py debtor_notifications.py main.py tests --min-confidence 100 --ignore-names cli_env
python -m bandit -q -r .
python -m radon cc -s -a dah_api.py auth_session.py debtor_notifications.py main.py tests
python -m radon cc -s -n B dah_api.py auth_session.py debtor_notifications.py main.py tests
```

Any output from the final `radon -n B` command should be treated as a failure.
Complexity must stay at grade A.

## Support

No support is provided for this repository. See [SUPPORT.md](SUPPORT.md).

## Security

Do not report DAH production vulnerabilities, leaked real data, tokens, or
account issues in public GitHub content. See [SECURITY.md](SECURITY.md).

## Legal Note

This README is a project notice, not legal advice. Users are responsible for
their own authorization, compliance, data handling, and use of DAH services.
