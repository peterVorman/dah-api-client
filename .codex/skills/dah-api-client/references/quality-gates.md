# Quality Gates

Use the active project Python environment. In this repository that is usually
`.venv/bin/python`.

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

Treat any output from the final `radon -n B` command as failure. Complexity must
stay grade A.

CI uses the same `PYTHON_FILES` set in `.github/workflows/ci.yml`.
