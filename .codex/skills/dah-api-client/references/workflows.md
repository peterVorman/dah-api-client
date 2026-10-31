# Workflows

## Contents

- Current Debt Snapshot
- Daily Debtor Dashboard
- Entrance And Floor Analysis
- Non-Residential Debt
- Debtor Notification Queue
- Manual Contact Ledger
- Single Apartment Payment Analysis
- Debtor Publication In DAH
- Feedback Order Closure
- Bank Expense Reconciliation
- Server Notification History Sync

## Current Debt Snapshot

Use when the user asks what is happening with debtors or whether there are
changes.

1. Fetch debt analytics with `debtFilterAccruals=1` unless the user asks for a
   different threshold.
2. Normalize rows through `DebtorNotificationService.debtors()` or
   `debt_entries()`.
3. Split totals by `kind`: `apartment`, `premise`, and `all`.
4. Include count, total debt, area, debt per square meter when available, and
   top debtors.
5. Use `python3 main.py debt-snapshot --write` for a local aggregate baseline.
   Later runs compare only against a compatible snapshot with the same `kind`,
   `debtFilterAccruals`, and `minDebt`.
6. State whether movement is mostly apartments, premises, or no meaningful
   movement.

## Daily Debtor Dashboard

Use when the user asks for an operational day-to-day view by premise type,
entrance, communication channel, or contact stage.

```bash
python3 main.py debt-dashboard --write --debt-filter-accruals 2
```

1. The default `debtFilterAccruals=2` focuses the dashboard on mature debt.
   Pass another threshold only when the user asks for it.
2. Use the command without `--write` for an ad-hoc current view. Use `--write`
   for one intentional daily baseline; it appends a local aggregate record and
   never writes to DAH.
3. Report total debt, apartment/premise totals, entrances with area-adjusted
   load, today's and historical ledger activity by channel, and current debtor
   stages. Do not turn the dashboard into a list of people or contact details.
4. Say explicitly when `previous` and `delta` are absent: it is a new baseline,
   not zero day-over-day movement.
5. For field definitions, compatibility rules, and interpretation, read
   [dashboard.md](dashboard.md).

## Entrance And Floor Analysis

Use for entrances, floors, stimulation priorities, or area-adjusted load.

1. Use `DebtorReportService.by_entrance()` or
   `python3 main.py debtors-by-entrance --area-adjusted`.
2. Use apartment metadata from `list_apartments()` as the area denominator, not
   only debtor rows.
3. Preserve the `Без підʼїзду` bucket.
4. Sort by debt per square meter for area-adjusted pressure and by total debt for
   cash-impact analysis.
5. Report both recoverable debt and normalized pressure per square meter.

## Non-Residential Debt

Use when the user asks about нежитлові or приміщення.

1. Fetch debtors with `kind="premise"` and `debtFilterAccruals=1`.
2. Group by `Без підʼїзду`, entrance, floor, and debt buckets.
3. Highlight top premises separately from the long tail.
4. If premises are already processed, exclude those numbers from the next action
   queue but keep them in total debt reporting.
5. Use `Приміщення` in user-facing text unless the user asks for the full DAH
   label.

## Debtor Notification Queue

Use when preparing who to notify next.

1. Run `debtors-next` or `DebtorReportService.next_to_notify()` with
   `notification_method="auto"` and `recipient_scope="auto"` unless specified.
2. Use `--exclude-notified-today` for next debtors after a same-day batch.
3. Show apartment/premise number, debt, recipient count, selected channel, and
   recipient scope. Avoid names, raw user ids, tenant ids, phone numbers, and
   emails unless needed for explicit approval.
4. For writes, require explicit user approval plus `--send` and `--confirm` for
   each target. Use `--max-send` or `--one-by-one` for risky batches.

`notification_method="auto"` starts with messenger. If the debtor has a prior
successful messenger record in `.dah-notifications.jsonl` and still has debt, it
prefers tenant notification. `recipient_scope="auto"` tries owners first, then
falls back to residents/renters stored as `others`. Use
`--recipient-scope owners+others` only when both groups should be contacted.

## Manual Contact Ledger

Use when the user reports a phone call or offline contact result.

```bash
python3 main.py ledger-add-contact --apartment-number 55 --status no_answer --note 'No answer'
```

Record `notificationMethod: "phone_call"`, `status: "contacted"` for successful
contact, and `status: "no_answer"` when nobody answered. Store a short note,
current debt when known, recipient scope, and recipient count. Do not store phone
numbers, emails, personal ids, names, or unnecessary personal details.

## Server Notification History Sync

Use this to backfill the local debtor communication ledger from DAH delivery
history without importing contact details or message bodies.

```bash
python3 main.py notification-history-sync
python3 main.py notification-history-sync --write
```

1. Run the preview first. It fetches only E-mail history and selects successful
   messages that clearly concern debt.
2. `--write` appends only unseen events. A SHA-256 fingerprint of the server
   event and apartment number makes later syncs idempotent without persisting a
   raw DAH server id.
3. Existing local E-mail `sent` records with the same date and apartment are
   treated as already represented to avoid legacy duplicates.
4. Do not sync SMS history into the debtor ledger: the server response contains
   a masked recipient but no reliable apartment or tenant identifier.

## Single Apartment Payment Analysis

Use when the user asks to analyze one apartment or premise.

```bash
python3 main.py debtor-audit --apartment-number <number> --from-date <YYYY-MM-DDT00:00:00>
```

Count local communication history from `.dah-notifications.jsonl`, report both
physical records and unique contact dates, fetch bank income transactions for the
period, and attribute payments only by exact analytics labels or exact account
markers. Finish with current debt, payment found/not found, and movement after
the last contact.

## Debtor Publication In DAH

Prepare a preview first unless the user already approved publication. Use
apartment/premise numbers and debt amounts only; avoid owner names and contact
data. Build valid HTML with paragraphs and lists, then send the same HTML in
`description` and `descriptionHtml`. Verify with `get_publication()` that tags
survived.

## Feedback Order Closure

Fetch current feedback orders when the target id is not known. Match by
title/content conservatively. Preview `FeedbackOrderStatusRequest(status="DONE")`
for ambiguous tasks. Send the update only after explicit approval or a clear user
command to close the identified task.

## Bank Expense Reconciliation

Fetch transactions with `direction="EXPENSE"` and the requested `from` date.
Normalize dates, amounts, and descriptions. Match planned items by exact or
high-confidence amount/date/vendor combinations and call out ambiguous matches.
Avoid raw bank account numbers and personal counterparty data in external task
comments unless the destination is explicitly authorized.
