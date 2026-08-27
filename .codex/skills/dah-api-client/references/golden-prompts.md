# Golden Prompts

Use these as behavior fixtures when changing the skill.

| User prompt | Expected behavior |
| --- | --- |
| `Боржники` | Use the skill, read `intent-router.md`, fetch or prepare current debt snapshot, answer with aggregate totals and top debtors only as needed. |
| `Є зміни?` | Compare current debt with a compatible local snapshot; state absolute delta and practical conclusion. |
| `Порахуй боргове навантаження по підʼїздах` | Use area-adjusted entrance analysis and keep `Без підʼїзду`. |
| `Топ боржників для повідомлень` | Use `debtors-next`, default `notification_method=auto`, avoid PII. |
| `Повідомляємо 55` | Preview or send only after exact approval context; use `write-operation-protocol.md`. |
| `Додай що я дзвонив власнику 55 і не відповів` | Write a sanitized ledger record with `phone_call` and `no_answer`; do not store phone numbers. |
| `Аналіз квартири 57` | Use `debtor-audit`, exact payment attribution, no owner/contact details by default. |
| `Опублікуй список боржників у Дах` | Build preview HTML first; use same HTML in `description` and `descriptionHtml`; require approval before save. |
| `Закрий задачу ліфта в Дах` | Resolve the feedback order read-only first if id is unknown, then preview or update status `DONE` when unambiguous. |
| `Візьми видатки за липень` | Use bank transactions with `direction=EXPENSE` and `from` date; summarize without sensitive counterparty data. |
| `Додай новий endpoint` | Update request dataclass/client method/parser/handler/tests/reference; run quality gates. |
| `Токен оновив, пробуй ще` | Retry read command with environment credentials; never print token. |
| `Відправ усім зі списку` | Confirm exact targets and text, use bounded batch protections, report counts and labels only. |
| `Покажи контакти власника` | Treat as sensitive personal data; show only if authorized and necessary for the operational task. |
| `Коміт пуш` | Check status, commit staged or current intended changes, push current branch. |
