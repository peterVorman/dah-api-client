# DAH Client Usage

## Repository

Run from the workspace root that contains `dah_api.py` and `main.py`.

Important files:

- `dah_api.py`: API client, request dataclasses, endpoint methods, errors.
- `auth_session.py`: sanitized auth status, JWT expiry inspection, `.env.local`
  auth updates.
- `cli_parser.py`: CLI parser and command arguments.
- `main.py`: CLI dispatch, request building, write guards, auth retry.
- `debtor_data.py`: shared debtor/apartment normalization.
- `debtor_notifications.py`: debtor notification workflow and local ledger.
- `debtor_reports.py`: debtor queues, audits, structure reports, snapshots.

## Reference Routing

Read only the reference needed for the task:

- `configuration.md`: environment, login/relogin/logout, token storage, TLS,
  privacy and licensing guardrails.
- `intent-router.md`: user intent to command/reference routing.
- `commands.json`: machine-readable command metadata for mode, approval, dry-run,
  and required environment.
- `workflows.md`: recurring debtor, publication, feedback-order, ledger, and
  bank-reconciliation workflows.
- `endpoints.md`: function map, endpoint paths, default payloads, and endpoint
  extension checklist.
- `safety-decision-table.md`: what can be shown, stored, or written.
- `write-operation-protocol.md`: exact protocol for DAH/external writes.
- `output-templates.md`: stable answer shapes.
- `golden-prompts.md`: AI behavior fixtures for future skill changes.
- `quality-gates.md`: local and CI validation commands.

## CLI Quick Start

```bash
python3 main.py access
python3 main.py auth-status
python3 main.py authentication-web-login --dry-run
python3 main.py authentication-web-login --save-env-local
python3 main.py authentication-relogin --save-env-local
python3 main.py authentication-exit
python3 main.py publications-search --page 0 --size 5
python3 main.py publication-get '<publication id>'
python3 main.py publication-save --body-file publication.json --dry-run
python3 main.py bill-debt-analytics --debt-filter-accruals 1
python3 main.py bill-reconciliation --apartment-number 55 --from-date YYYY-MM-DDT00:00:00 --to-date YYYY-MM-DDT23:59:59
python3 main.py bill-reconciliation-download --apartment-number 55 --from-date YYYY-MM-DDT00:00:00 --to-date YYYY-MM-DDT23:59:59 --output act.pdf
python3 main.py bill-reconciliation-send --apartment-number 55 --from-date YYYY-MM-DDT00:00:00 --to-date YYYY-MM-DDT23:59:59
python3 main.py bill-reconciliation-send --apartment-number 55 --from-date YYYY-MM-DDT00:00:00 --to-date YYYY-MM-DDT23:59:59 --send --confirm 55
python3 main.py debtors-next --notification-method auto --limit 15
python3 main.py debtors-notify --apartment-number 55
python3 main.py debtors-notify --apartment-number 55 --send --confirm 55
python3 main.py debtors-by-entrance --area-adjusted --kind apartment
python3 main.py debtor-audit --apartment-number 55 --from-date YYYY-MM-DDT00:00:00
python3 main.py debt-snapshot --write --kind all
python3 main.py ledger-add-contact --apartment-number 55 --status contacted --note 'Contact established'
python3 main.py feedback-order-list
python3 main.py feedback-order-status '<feedback order id>' --status DONE --dry-run
python3 main.py tenant-notification-send --tenant-id '<tenant id>' --text 'Повідомлення'
python3 main.py apartment-list --page 0 --size 50
python3 main.py money-transaction-bank-list --direction EXPENSE --from-date YYYY-MM-DDT00:00:00
python3 main.py messenger-groups-page --page 0 --size 50
python3 main.py messenger-group-messages --group-id '<messenger group id>'
python3 main.py messenger-personal-group-get '<owner user id>'
python3 main.py messenger-send-message --chat-name '1 підʼїзд' --dry-run 'Повідомлення'
```

Common flags:

- `--compact`: compact JSON output.
- `--base-url`, `--origin`, `--referer`, `--user-agent`: request context
  overrides.
- `--tab-id`: optional `X-DAH-TabId`.
- `--timeout`: HTTP timeout seconds.

## Python Quick Start

```python
from dah_api import BillDebtAnalyticsRequest, BillReconciliationRequest, DahApiClient, DahApiConfig
from debtor_notifications import DebtorNotificationRequest, DebtorNotificationService
from debtor_reports import DebtorReportService, DebtSnapshotRequest

client = DahApiClient(DahApiConfig.from_env())
debt = client.get_bill_debt_analytics(BillDebtAnalyticsRequest())
act = client.get_bill_reconciliation(
    BillReconciliationRequest(
        apartment_id="<apartment id>",
        payload={"from": "YYYY-MM-DDT00:00:00", "to": "YYYY-MM-DDT23:59:59"},
    )
)
queue = DebtorNotificationService(client).run(DebtorNotificationRequest(limit=10))
snapshot = DebtorReportService(client).snapshot(DebtSnapshotRequest(write_snapshot=True))
```

Use request dataclasses from `dah_api.py`, `debtor_notifications.py`, and
`debtor_reports.py` instead of building URLs by hand.

## Skill Scripts

```bash
python3 .codex/skills/dah-api-client/scripts/debtor_audit.py --apartment-number 55 --from-date YYYY-MM-DDT00:00:00
python3 .codex/skills/dah-api-client/scripts/debt_snapshot.py --write
python3 .codex/skills/dah-api-client/scripts/validate_skill.py .codex/skills/dah-api-client
```
