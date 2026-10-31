# Intent Router

Use this table before choosing a command or reference file.

| User intent | Read | Prefer command |
| --- | --- | --- |
| Current debtor state, "боржники зараз" | `workflows.md`, `output-templates.md` | `debt-snapshot` |
| Debt dynamics, "є зміни" | `workflows.md`, `output-templates.md` | `debt-snapshot --write` when a baseline is needed |
| Daily operations dashboard by type, entrance, channel, or stage | `dashboard.md`, `output-templates.md` | `debt-dashboard --write` |
| Top debtors or next notification queue | `workflows.md`, `safety-decision-table.md` | `debtors-next` |
| Notify debtors | `write-operation-protocol.md`, `safety-decision-table.md` | `debtors-notify` |
| One apartment or premise audit | `workflows.md`, `output-templates.md` | `debtor-audit` |
| Apartment or premise reconciliation act | `endpoints.md`, `safety-decision-table.md` | `bill-reconciliation` or `bill-reconciliation-download` |
| Send reconciliation act in DAH messenger | `endpoints.md`, `write-operation-protocol.md`, `safety-decision-table.md` | `bill-reconciliation-send` dry-run first |
| Entrance/floor debt load | `workflows.md`, `output-templates.md` | `debtors-by-entrance --area-adjusted` |
| Non-residential debt | `workflows.md`, `output-templates.md` | `debtors-next --kind premise` or `debtors-by-entrance --kind premise` |
| DAH publication | `write-operation-protocol.md`, `endpoints.md` | `publication-save --dry-run` first |
| Feedback/order closure | `write-operation-protocol.md`, `endpoints.md` | `feedback-order-status --dry-run` first |
| Messenger group read/write | `write-operation-protocol.md`, `endpoints.md` | `messenger-group-messages` or `messenger-send-message --dry-run` |
| Tenant notification | `write-operation-protocol.md`, `safety-decision-table.md` | `tenant-notification-send` |
| DAH SMS or E-mail delivery history | `endpoints.md`, `safety-decision-table.md` | `notification-history --channel sms` or `--channel email` |
| Synchronize DAH E-mail debt notices with the local ledger | `endpoints.md`, `workflows.md` | `notification-history-sync`, then `--write` after preview |
| Bank expense or income matching | `workflows.md`, `endpoints.md` | `money-transaction-bank-list` |
| Add a new endpoint | `endpoints.md`, `quality-gates.md` | update `dah_api.py`, `cli_parser.py`, `main.py`, tests |
| Auth/session issue | `configuration.md` | `auth-status`, `authentication-relogin`, `authentication-web-login` |

When the user asks for an operational write, start with the dry-run or preview
command unless they already gave explicit approval for the exact target and text.
