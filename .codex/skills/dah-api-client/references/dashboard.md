# Daily Debtor Dashboard

## Purpose

Use `debt-dashboard` for an aggregate operational picture of mature debt. It
combines current DAH debt analytics and apartment metadata with the local
notification ledger. It is not a replacement for an individual debtor audit or
a notification queue.

```bash
python3 main.py debt-dashboard
python3 main.py debt-dashboard --write
python3 main.py debt-dashboard --write --debt-filter-accruals 1
python3 main.py debt-dashboard --min-debt 2000
```

The default `debtFilterAccruals=2` is deliberate. Use `1` only when the user
asks for the broader, less mature debt view.

## Read And Storage Boundaries

The command reads:

- DAH debt analytics for the selected threshold and report date;
- DAH apartment metadata to classify a debtor and calculate the area
  denominator;
- `.dah-notifications.jsonl` for local communication history.

It does not send a DAH message or change debt data. `--write` only appends an
aggregate JSONL record to `.dah-debt-dashboard.jsonl`, which is Git-ignored.
Do not commit either local ledger or snapshot file.

Use `--write` once for a deliberate daily baseline. Repeated writes on the same
day remain useful as an audit trail, but do not create a same-day delta.

## Request Controls

| Option | Meaning |
| --- | --- |
| `--date YYYY-MM-DDTHH:MM` | DAH debt-report date and the dashboard calendar date. |
| `--debt-filter-accruals N` | Debt maturity threshold; default is `2`. |
| `--min-debt AMOUNT` | Exclude lower individual balances from the view and baseline. |
| `--ledger-path PATH` | Read communication history from an alternative local ledger. |
| `--dashboard-path PATH` | Read/write an alternative aggregate snapshot history. |
| `--write` | Append the current local aggregate snapshot. |

Do not compare dashboards created with different maturity thresholds or
`minDebt` values. The client enforces this compatibility rule.

## Result Shape

The command returns `current`, `previous`, and `delta`.

### `current`

- `summary`: total debtor count, debt, area denominator, and `debtPerArea`.
- `byKind`: separate rows for `apartment` and `premise`.
- `entrances`: debt and area-adjusted load by entrance, with floor breakdowns.
  Keep `Без підʼїзду`; it often represents non-residential premises and should
  not be folded into another entrance.
- `communications.total`: local ledger activity through the snapshot day,
  grouped by channel.
- `communications.today`: ledger entries whose local `date` matches the
  snapshot day.
- `stages`: current debtors grouped by their latest relevant ledger status.

Each communication row contains `events`, `sent`, `contacted`, `noAnswer`, and
`recipients`. These are ledger events and intended recipient counts, not a
delivery or payment guarantee.

### Stages

| Stage | Meaning |
| --- | --- |
| `new` | No matching local communication record. |
| `notified` | Latest matching record has status `sent`. |
| `contacted` | Latest matching record has status `contacted`. |
| `no_answer` | Latest matching record has status `no_answer`. |
| `unreachable` | Latest matching record has status `failed` or `skipped`. |
| `unknown` | A legacy record without premise type matches more than one current debtor. |

New ledger records include `kind` so an apartment and a non-residential premise
with the same number are never conflated. Do not infer a stage from an
ambiguous legacy record.

### `previous` And `delta`

`previous` is the latest compatible dashboard from an earlier calendar day.
`delta` contains changes in the overall summary, type rows, entrances,
all-time channel activity, and current stages.

When both are `null`, report a new baseline rather than a zero change. A
dashboard from the same calendar day is never used as the comparison baseline.

## Interpretation

1. Use total debt to prioritize cash impact and `debtPerArea` to compare burden
   across entrances of different sizes.
2. Call out `Без підʼїзду` separately. It can dominate the aggregate because
   it includes premises that do not belong to a residential entrance.
3. Treat high floor-level `debtPerArea` values cautiously when the floor's area
   denominator is very small. Confirm both the amount and area before calling
   it a priority.
4. Treat a large `notified` balance as a follow-up queue, not evidence that a
   message failed. Use the individual audit or notification workflow before
   taking action.
5. Distinguish today's communication activity from historical totals and from
   actual payments. Payment analysis requires debt snapshots or debtor audits.

## Safe Response Rules

Summarize the dashboard using aggregate figures. Do not print owner names,
tenant identifiers, phone numbers, emails, raw ledger entries, or credentials.
For a specific debtor, use `debtor-audit`; for a notification batch, use
`debtors-next` and the write-operation protocol.
