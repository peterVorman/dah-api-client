# Write Operation Protocol

Use this protocol for DAH writes and external writes based on DAH data.

1. Resolve the exact target using read-only commands.
2. Build a preview or dry-run payload.
3. Show only safe details: target label, counts, message text, and whether the
   operation writes to DAH or an external system.
4. Ask for explicit approval when the user has not already approved the exact
   target, channel, and text.
5. Execute the write with the smallest batch size that satisfies the request.
6. Record local ledger entries for debtor notifications or manual contacts when
   applicable.
7. Report write results by count and target labels. Do not print raw ids or
   credentials.

Write commands:

- `publication-save`: use `--dry-run` first unless already approved.
- `feedback-order-status`: use `--dry-run` when the task id or intended status is
  not fully unambiguous.
- `tenant-notification-send`: requires `--send --confirm-tenant-id`.
- `messenger-send-message`: use `--dry-run` before sending new text.
- `debtors-notify`: requires `--send` plus `--confirm` for every target; use
  `--max-send` or `--one-by-one` for risky batches.

Do not auto-retry write commands after `401 invalid_access_token`; refresh auth
first, then rebuild the preview before sending.
