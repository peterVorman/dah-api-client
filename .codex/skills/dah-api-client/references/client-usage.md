# DAH Client Usage

## Repository

The local DAH client lives in the current repository root:

```text
$PWD
```

Important files:

- `dah_api.py`: object-oriented API client, configuration, request types, and exceptions.
- `auth_session.py`: sanitized auth-status, JWT expiry inspection, and optional
  `.env.local` auth updates.
- `main.py`: CLI wrapper around the client.

## License And DAH Terms

The repository or skill package `LICENSE` is source-available and restricted-use.
It does not grant rights to DAH services, APIs, data, trademarks, UI,
documentation, or infrastructure. Use the client only with authorized DAH
accounts and within the user's authority for the relevant association.

Treat DAH responses as potentially personal, financial, or association-confidential
data. Do not commit captured API responses, tokens, exported reports, or chat
content unless the user explicitly asks and the data is appropriate for the repo.

Do not provide DAH access, token acquisition help, account support, billing
support, association support, or operational DAH troubleshooting.

## Configuration

Use `DahApiConfig.from_env()` for scripts that should respect the user's shell environment.

Supported environment variables:

- `DAH_BASE_URL`: API base URL, default `https://api.dah-online.com`.
- `DAH_BEARER_TOKEN`: bearer token. Required by default for live API calls.
- `DAH_REFRESH_TOKEN`: optional refresh token for `authentication-relogin`.
- `DAH_LOGIN`: optional login for `authentication-web-login`.
- `DAH_PASSWORD`: optional password for `authentication-web-login`.
- `DAH_ASSOCIATION_ID`: optional association id override. When absent, scoped endpoints resolve the single available id from `get_access`.
- `DAH_TAB_ID`: optional `X-DAH-TabId` header.
- `DAH_DEVICE_ID`: optional device id for `authentication-relogin`.
- `DAH_ORIGIN`: Origin header, default `https://cabinet.dah-online.com`.
- `DAH_REFERER`: Referer header, default `https://cabinet.dah-online.com/`.
- `DAH_USER_AGENT`: User-Agent header.
- `DAH_MESSENGER_GROUP_ID`: optional default group id for `messenger-group-messages`.
- `SSL_CERT_FILE`: optional custom CA bundle path. When unset, the client uses
  `certifi` for TLS certificate verification.

Never print bearer tokens, refresh tokens, logins, or passwords. Avoid
committing newly captured credentials.

When using `.env.local`, keep entries as plain `KEY=value` lines. The local
loader ignores blank lines and comments, and it does not implement shell syntax
or shell quoting such as `export KEY=value` or `KEY="value"`.

If a live request returns `401 Unauthorized`, first assume the active token is expired or missing. Use a fresh `DAH_BEARER_TOKEN` from the environment instead of editing code or hard-coding tokens.

## Python Quick Start

```python
from debtor_notifications import DebtorNotificationRequest, DebtorNotificationService
from dah_api import (
    ApartmentListRequest,
    DahApiClient,
    DahApiConfig,
    DahHttpError,
    DahRequestError,
    AuthenticationReloginRequest,
    AuthenticationWebLoginRequest,
    BillDebtAnalyticsRequest,
    FeedbackOrderListRequest,
    FeedbackOrderStatusRequest,
    MoneyTransactionBankListRequest,
    MessengerGroupMessagesRequest,
    MessengerGroupsPageRequest,
    MessengerMessageRequest,
    MessengerPersonalGroupRequest,
    PublicationSaveRequest,
    PublicationsSearchRequest,
    TenantNotificationRequest,
    default_bill_debt_analytics_payload,
)

client = DahApiClient(DahApiConfig.from_env())

try:
    login = client.authentication_web_login(
        AuthenticationWebLoginRequest(
            login="<login>",
            password="<password>",
        )
    )
    access = client.get_access()
    relogin = client.authentication_relogin(
        AuthenticationReloginRequest(
            refresh_token="<refresh token>",
            device_id="<device id>",
        )
    )
    exit_response = client.authentication_exit()
    publications = client.search_publications(PublicationsSearchRequest(page=0, size=5))
    publication = client.get_publication("<publication id>")
    saved_publication = client.save_publication(
        PublicationSaveRequest(
            {
                "associationId": "<association id>",
                "group": {"id": "<messenger group id>", "name": "Загальний"},
                "title": "Оголошення",
                "type": "DISCUSSION",
                "description": "<p>HTML body</p>",
                "descriptionHtml": "<p>HTML body</p>",
                "attachments": [],
                "commentsEnabled": True,
            }
        )
    )
    debt = client.get_bill_debt_analytics(
        BillDebtAnalyticsRequest(
            payload=default_bill_debt_analytics_payload(date="2026-07-08T15:10"),
        )
    )
    debtor_notifications = DebtorNotificationService(client).run(
        DebtorNotificationRequest(
            min_debt=3000,
            apartment_numbers=["55"],
        )
    )
    feedback_orders = client.list_feedback_orders(FeedbackOrderListRequest())
    closed_order = client.update_feedback_order_status(
        FeedbackOrderStatusRequest(
            order_id="<feedback order id>",
            status="DONE",
        )
    )
    tenant_notification = client.send_tenant_notification(
        TenantNotificationRequest(
            association_id="<association id>",
            tenant_id="<tenant id>",
            text="Добрий день.\nПросимо погасити борг.",
        )
    )
    apartments = client.list_apartments(ApartmentListRequest(page=0, size=50))
    bank_transactions = client.list_money_transaction_bank(
        MoneyTransactionBankListRequest(page=0, size=50)
    )
    groups = client.list_messenger_groups(MessengerGroupsPageRequest(page=0, size=50))
    messages = client.list_messenger_group_messages(
        MessengerGroupMessagesRequest(group_id="<messenger group id>", page=0, size=50)
    )
    personal_group = client.get_messenger_personal_group(
        MessengerPersonalGroupRequest(interlocutor_id="<owner user id>")
    )
    sent_message = client.send_messenger_message(
        MessengerMessageRequest(
            group_id="<messenger group id>",
            payload="Ліфт відновив роботу",
        )
    )
except DahHttpError as exc:
    print(f"HTTP {exc.status_code} {exc.reason}")
except DahRequestError as exc:
    print(f"Request failed: {exc}")
```

## CLI Quick Start

Run commands from the repository root.

```bash
python3 main.py access
python3 main.py auth-status
python3 main.py authentication-web-login --dry-run
python3 main.py authentication-web-login --save-env-local
python3 main.py authentication-relogin --device-id "$DAH_DEVICE_ID" --dry-run
python3 main.py authentication-relogin --save-env-local
python3 main.py authentication-exit
python3 main.py publications-search --page 0 --size 5
python3 main.py publications-search --body '{"associationId":"<association id>","statuses":["PUBLISHED"]}'
python3 main.py publications-search --body-file request.json --compact
python3 main.py publication-get '<publication id>'
python3 main.py publication-save --body-file publication.json --dry-run
python3 main.py bill-debt-analytics --date 2026-07-08T15:10 --debt-filter-accruals 1
python3 main.py debtors-notify --min-debt 3000 --limit 10
python3 main.py debtors-notify --min-debt 3000 --format table
python3 main.py debtors-notify --apartment-number 55 --send --confirm 55
python3 main.py debtors-notify --notification-method auto --apartment-number 55
python3 main.py debtors-notify --notification-method tenant --apartment-number 55 --send --confirm 55
python3 main.py debtors-notify --recipient-scope others --apartment-number 114
python3 main.py debtors-notify --send --one-by-one --confirm 55 --apartment-number 55
python3 main.py debtors-next --exclude-notified-today --limit 15 --format table
python3 main.py debtors-next --notification-method auto --limit 15
python3 main.py debtors-next --notification-method tenant --limit 15
python3 main.py debtors-by-entrance --area-adjusted --kind apartment
python3 main.py feedback-order-list
python3 main.py feedback-order-status '<feedback order id>' --status DONE --dry-run
python3 main.py tenant-notification-send --tenant-id '<tenant id>' --text 'Повідомлення'
python3 main.py tenant-notification-send --tenant-id '<tenant id>' --text 'Повідомлення' --send --confirm-tenant-id '<tenant id>'
python3 main.py apartment-list --page 0 --size 50
python3 main.py money-transaction-bank-list --direction EXPENSE --from-date 2026-07-01T00:00:00 --page 0 --size 50
python3 main.py messenger-groups-page --page 0 --size 50
python3 main.py messenger-group-messages --group-id '<messenger group id>' --page 0 --size 50
python3 main.py messenger-personal-group-get '<owner user id>'
python3 main.py messenger-send-message --chat-name '1 підʼїзд' --dry-run 'Ліфт відновив роботу'
python3 main.py messenger-send-message --interlocutor-id '<owner user id>' --dry-run 'Повідомлення'
```

Common flags:

- `--tab-id`: send `X-DAH-TabId`.
- `--timeout`: set HTTP timeout seconds.
- `--compact`: print compact JSON.

## Operational Workflows

These workflows capture the recurring DAH operations used in this repository.
Keep outputs concise, aggregate by default, and expose apartment/premise numbers
only when the user is performing an authorized debtor operation.

### Current Debt Snapshot

Use when the user asks "what is happening with debtors" or asks whether there
are changes.

1. Fetch current debt analytics with `debtFilterAccruals=1`.
2. Normalize rows through `DebtorNotificationService.debtors()` or
   `debt_entries()`.
3. Split totals by `kind`: `apartment`, `premise`, and `all`.
4. Include count, total debt, area, debt per square meter when available, and
   top debtors.
5. Compare with the most recent known baseline from the conversation or a saved
   local snapshot. If no baseline exists, say it is a fresh snapshot.
6. State the practical conclusion: whether movement is mostly apartments,
   premises, or no meaningful movement.

### Entrance And Floor Debt Analysis

Use for requests about entrances, floors, "who to stimulate", or area-adjusted
load.

1. Use `DebtorReportService.by_entrance()` or
   `python3 main.py debtors-by-entrance --area-adjusted`.
2. Use apartment metadata from `list_apartments()` as the area denominator, not
   only debtor rows; otherwise debt load is overstated.
3. Preserve the `Без підʼїзду` bucket. Do not drop it when grouping.
4. Sort by debt per square meter for area-adjusted analysis, and by total debt
   for cash-impact analysis.
5. Report both metrics when recommending where to focus: total recoverable debt
   and normalized pressure per square meter.

### Non-Residential Debt Follow-Up

Use when the user asks about нежитлові/приміщення.

1. Fetch debtors with `kind="premise"` and `debtFilterAccruals=1`.
2. Group by `Без підʼїзду`, entrance, floor, and debt buckets.
3. Highlight concentration in the top premises separately from the long tail.
4. If the user marks premises as already processed, exclude those numbers from
   the next actionable queue but keep them in total debt reporting.
5. Use `Приміщення` in user-facing text unless the user asks for the full DAH
   label.

### Debtor Notification Queue

Use when preparing who to notify next.

1. Run `debtors-next` or `DebtorReportService.next_to_notify()` with
   `notification_method="auto"` and `recipient_scope="auto"` unless the user
   specifies otherwise.
2. Use `--exclude-notified-today` when the request is about "next" debtors after
   a same-day batch.
3. Show apartment/premise number, debt, recipient count, selected channel, and
   recipient scope. Do not show names, raw user ids, tenant ids, phone numbers,
   emails, or message bodies unless needed for approval.
4. For sending, use `--send` only after explicit user approval and include
   `--confirm` for each target. Use `--max-send` or `--one-by-one` for risky
   batches.

### Automatic Notification Method

Use `notification_method="auto"` as the default debtor-notification behavior.

1. If the debtor has a prior successful messenger record in
   `.dah-notifications.jsonl`, auto prefers tenant notification.
2. Otherwise auto starts with messenger.
3. If the selected channel has no reachable owner recipient, `recipient_scope`
   auto falls back from `owners` to `others`.
4. Auto selects one route. It does not mean "send to owners and others at the
   same time".
5. To notify both owners and residents/renters in one operation, perform an
   explicit custom flow that merges `owners` and `others`, deduplicates user ids,
   and records `recipientScope` as `owners+others`.

### Manual Contact Ledger

Use when the user reports a phone call or offline contact result.

1. Append one JSONL record to `.dah-notifications.jsonl`.
2. Use `notificationMethod: "phone_call"` for calls.
3. Use `status: "contacted"` when contact was established and
   `status: "no_answer"` when nobody answered.
4. Store apartment/premise number, current debt when known, recipient scope,
   recipient count, and a short note.
5. Do not store phone numbers, emails, personal ids, or unnecessary personal
   details in the ledger.

Example record shape:

```json
{
  "date": "YYYY-MM-DD",
  "apartment": "<number>",
  "debt": 0.0,
  "status": "contacted",
  "notificationMethod": "phone_call",
  "recipientScope": "owners",
  "recipients": 1,
  "note": "Contact established. They said they should pay."
}
```

### Single Apartment Payment Analysis

Use when the user asks to analyze one apartment or premise.

1. Count local communication history from `.dah-notifications.jsonl`.
2. Report both physical ledger records and unique contact dates because older
   batches may contain duplicate records.
3. Fetch bank income transactions from the requested period, usually the last
   two months.
4. Attribute payments only by exact analytics match such as `Квартира <number>`
   or exact account marker such as `050<number>`. Avoid broad number searches
   because transaction ids and comments can contain unrelated numeric matches.
5. Fetch debt analytics on relevant historical dates to show debt movement
   before and after payments and monthly accruals.
6. Finalize with a clear conclusion: payment found or not, current debt, and
   whether debt moved after the last contact.

### Debtor Publication In DAH

Use when publishing debtor lists or debt summaries inside DAH.

1. Prepare a preview first unless the user already gave explicit approval.
2. Use only apartment/premise numbers and debt amounts; avoid owner names or
   other personal data in public/group publications.
3. Build valid HTML with paragraphs and lists, then send the same HTML in
   `description` and `descriptionHtml`.
4. Verify the saved publication with `get_publication()` and confirm that
   formatting tags survived.
5. If the user asks for a public summary, prefer aggregate totals and dynamics;
   individual debtor lists require explicit authorization.

### Feedback Order Closure

Use when closing DAH tasks such as completed maintenance/order work.

1. Fetch current feedback orders with `list_feedback_orders()` if the target id
   is not already known.
2. Match by task title/content conservatively.
3. Add any requested comment through the available task system first if
   applicable.
4. Preview `FeedbackOrderStatusRequest(status="DONE")` for ambiguous tasks.
5. Send `update_feedback_order_status()` only after explicit approval or a clear
   user command to close the identified task.

### Bank Expense Reconciliation

Use when matching planned payments against DAH bank transactions.

1. Fetch bank transactions with `direction="EXPENSE"` and the requested
   `from` date.
2. Normalize dates, amounts, and descriptions.
3. Match planned items by exact or high-confidence amount/date/vendor
   combinations; call out ambiguous matches instead of forcing them.
4. When posting results to an external task system, avoid raw bank account
   numbers and personal counterparty data unless the destination is explicitly
   authorized for that data.

## Function Reference

Use this section as the quick map from user intent to client function or CLI
command. Keep live data out of examples; use placeholders for ids and secrets.

### Authentication And Access

- `DahApiConfig.from_env()`: build the client configuration from `.env.local`
  and environment variables. Use it for normal scripts and CLI-backed workflows.
- `DahApiClient.get_access()`: read the authenticated user's available DAH
  organization/association access. Scoped methods use it to resolve a single
  association id when `DAH_ASSOCIATION_ID` is not set.
- `DahApiClient.authentication_web_login()`: call web login with
  `AuthenticationWebLoginRequest`. Use only with authorized credentials from the
  environment or an explicit user-provided body.
- `DahApiClient.authentication_relogin()`: refresh an existing session with
  `AuthenticationReloginRequest`, usually from `DAH_REFRESH_TOKEN` and
  `DAH_DEVICE_ID`.
- `DahApiClient.authentication_exit()`: end the active DAH session.
- `python3 main.py auth-status`: inspect local auth state without printing token
  values.

### Publications

- `DahApiClient.search_publications()`: list DAH publications using
  `PublicationsSearchRequest`; defaults to published items.
- `DahApiClient.get_publication(publication_id)`: fetch one publication by id.
- `DahApiClient.save_publication()`: create or edit a DAH publication through
  `PublicationSaveRequest`. Include `id` to edit; omit it to create. For
  formatted announcements, send the same HTML in `description` and
  `descriptionHtml`.

### Debt And Reports

- `default_bill_debt_analytics_payload()`: build the standard DAH debt analytics
  payload. `debt_filter_accruals` controls the accrual threshold, and `date`
  selects the report timestamp.
- `DahApiClient.get_bill_debt_analytics()`: fetch raw DAH debt rows for the
  selected association.
- `DebtorNotificationService.debtors()`: normalize raw debt analytics rows into
  sorted debtor records with label, number, kind, and positive debt amount.
- `DebtorReportService.next_to_notify()`: preview debtors that have a reachable
  notification route, without sending.
- `DebtorReportService.by_entrance()`: group current debt by entrance/floor and,
  with `area_adjusted=True`, include debt per square meter.
- `python3 main.py debtors-by-entrance`: CLI entrypoint for entrance/floor debt
  structure.
- `python3 main.py debtors-next`: CLI entrypoint for the next notification queue.

### Debtor Notifications

- `DebtorNotificationService.run()`: build a dry-run or send batch for debtors.
  It returns `ready`, `sent`, and `skipped`; writes require `send=True` and
  per-apartment confirmation.
- `DebtorNotificationRequest.notification_method`: choose `messenger`, `tenant`,
  or `auto`. `auto` uses messenger first, then tenant notification after prior
  successful messenger contact in the local ledger.
- `DebtorNotificationRequest.recipient_scope`: choose `owners`, `others`, or
  `auto`. `auto` tries owners first, then residents/renters stored as `others`.
- `NotificationLedger`: local JSONL record of sent/skipped/manual contact
  outcomes. The default file `.dah-notifications.jsonl` is local and gitignored.
- `python3 main.py debtors-notify`: CLI entrypoint for dry-run and confirmed
  debtor notification sends.

### Apartments And Contacts

- `DahApiClient.list_apartments()`: fetch apartment/premise records and owner or
  other occupant metadata. Treat returned people data as personal data.
- `apartment_for_debtor()`: match a normalized debtor to an apartment record by
  exact kind and apartment number.
- `recipient_ids()`: extract reachable recipient ids for messenger or tenant
  notification from owner/other records.
- `DahApiClient.get_messenger_personal_group()`: fetch or create a personal DAH
  messenger group for an exact user id before sending a direct message.

### Messenger

- `DahApiClient.list_messenger_groups()`: page through DAH messenger groups.
- `DahApiClient.list_messenger_group_messages()`: read messages from one group.
- `DahApiClient.send_messenger_message()`: send a text message to a DAH
  messenger group with `MessengerMessageRequest`.
- `python3 main.py messenger-send-message`: CLI entrypoint for dry-run or
  confirmed group/personal messenger messages.

### Feedback Orders And Accounting

- `DahApiClient.list_feedback_orders()`: list DAH feedback/service orders.
- `DahApiClient.update_feedback_order_status()`: update an order status with
  `FeedbackOrderStatusRequest`; use CLI `--dry-run` before writes.
- `DahApiClient.list_money_transaction_bank()`: list bank transactions, filtered
  by payload fields such as `direction` and `from`. Use exact apartment account
  or analytics matching when attributing payments.
- `python3 main.py money-transaction-bank-list`: CLI entrypoint for bank
  transaction queries.

## Current Client Surface

`DahApiClient.get_access()` calls:

```text
GET /organization/v1/access
```

`DahApiClient.authentication_web_login()` calls:

```text
POST /authentication/web/login
```

Default login payload:

```json
{
  "clientId": "DAH_CLIENT_WEB",
  "login": "<login>",
  "password": "<password>"
}
```

Use `DAH_LOGIN` and `DAH_PASSWORD`, or pass a JSON body/body file. Treat both
values as credentials and avoid putting real values in committed files or shell
history.

The CLI command sanitizes real login responses before printing them. Use
`--save-env-local` only when the returned auth response should update
`.env.local` with recognized token fields. The command stores only recognized
auth keys and prints the saved key names, not token values.

`DahApiClient.authentication_relogin()` calls:

```text
POST /authentication/relogin
```

Default relogin payload:

```json
{
  "clientId": "DAH_CLIENT_WEB",
  "clientType": "WEB",
  "deviceId": "<device id>",
  "refreshToken": "<refresh token>"
}
```

Use `DAH_REFRESH_TOKEN` and `DAH_DEVICE_ID`, or pass a JSON body/body file.
Treat `refreshToken` as a credential and avoid putting real values in committed
files or shell history.

The CLI command supports `--save-env-local` with the same sanitized output rules
as `authentication-web-login`.

`DahApiClient.authentication_exit()` calls:

```text
GET /authentication/exit
```

`python3 main.py auth-status` inspects the local bearer token without printing
it. When the token is JWT-shaped, it reports the `exp` timestamp as
`bearerTokenExpiresAt`; otherwise expiry is `null`. If a bearer token is
present, the command also checks `get_access` reachability and returns only an
`ok` flag or sanitized error text.

`DahApiClient.search_publications()` calls:

```text
POST /publications/search?page=<page>&size=<size>
```

`DahApiClient.get_publication()` calls:

```text
GET /publications/get/<publicationId>
```

`DahApiClient.save_publication()` calls one of:

```text
POST /publications/v2/add/web
PUT /publications/v2/edit/web
```

Include `id` in the payload to edit; omit `id` to create. When
`associationId` is missing, the client resolves the single available id from
`get_access`.

For formatted DAH publications, put the HTML body in both `description` and
`descriptionHtml`. DAH stores a plain-text `description` and the rendered
`descriptionHtml`; if `description` is plain text during save, the backend can
overwrite `descriptionHtml` with unformatted text.

`DahApiClient.get_bill_debt_analytics()` calls:

```text
POST /accounting/v1/report/bill/<associationId>/debt/analytics
```

`DahApiClient.list_feedback_orders()` calls:

```text
POST /feedback/order/list/<associationId>
```

`DahApiClient.update_feedback_order_status()` calls:

```text
PUT /feedback/order/comment/<orderId>
```

Default status payload:

```json
{
  "status": "DONE"
}
```

Use `python3 main.py feedback-order-status '<feedback order id>' --dry-run` to
preview the body before changing a DAH feedback order status.

`DahApiClient.send_tenant_notification()` calls:

```text
POST /communication/v1/client/notification/<associationId>/tenant/send
```

Default tenant notification payload:

```json
{
  "details": [
    {"type": "APP", "enabled": true},
    {"type": "EMAIL", "enabled": true},
    {"type": "SMS", "enabled": true}
  ],
  "tenantId": "<tenant id>",
  "text": "<plain text>",
  "textHtml": "<p>escaped text with <br> for line breaks</p>"
}
```

Use `python3 main.py tenant-notification-send --tenant-id '<tenant id>' --text '...'`
to preview the body. Add `--send --confirm-tenant-id '<tenant id>'` only after
the tenant id and message are confirmed. Pass `--text-html` or `--body-file`
when DAH needs explicit HTML.

`DahApiClient.list_money_transaction_bank()` calls:

```text
POST /accounting/v1/money/transaction/<associationId>/list/bank?page=<page>&size=<size>
```

`DahApiClient.list_apartments()` calls:

```text
POST /organization/v1/apartment/<associationId>/list?page=<page>&size=<size>
```

Use this endpoint to fetch apartment records and inspect `owners[].user.userId`
for authorized direct DAH messenger operations. Treat owner metadata as personal
data and avoid committing captured responses.

`DahApiClient.list_messenger_group_messages()` calls:

```text
POST /messenger/groups/<groupId>/messages?page=<page>&size=<size>
```

`DahApiClient.list_messenger_groups()` calls:

```text
POST /messenger/groups/page?page=<page>&size=<size>
```

`DahApiClient.get_messenger_personal_group()` calls:

```text
GET /messenger/groups/personal/<interlocutorId>/get
```

Use an exact `owners[].user.userId` value as `interlocutorId`. Validate that the
response is a writable `PERSONAL` group whose `interlocutorId` matches before
sending a direct message.

`DahApiClient.send_messenger_message()` calls:

```text
POST /messenger/messages
```

Message body:

```json
{
  "createTime": "<epoch milliseconds>",
  "groupId": "<messenger group id>",
  "payload": "<message text>",
  "type": "TEXT"
}
```

Use `python3 main.py messenger-send-message --chat-name '<exact chat name>' --dry-run '<message>'` to resolve a chat by exact name and preview the body before sending.
Use `python3 main.py messenger-send-message --interlocutor-id '<owner user id>' --dry-run '<message>'` to resolve a personal chat from an exact owner user id.

## Debtor Notifications

`python3 main.py debtors-notify` builds individual DAH debtor notifications
from bill debt analytics and apartment owner data. It supports three
notification modes:

- `--notification-method auto`: default; uses messenger for first contact, then
  tenant notifications for current debtors that already have a successful
  messenger send in the local ledger.
- `--notification-method messenger`: resolves active owner `userId`
  values to personal messenger groups and sends `/messenger/messages`.
- `--notification-method tenant`: uses active owner `tenantId` values and sends
  `/communication/v1/client/notification/<associationId>/tenant/send`, using the
  same message template for `text` and generated `textHtml`.

It also supports recipient source selection:

- `--recipient-scope auto`: default; tries `owners` first, then falls back to
  `others` when owners have no reachable recipient for the selected channel.
- `--recipient-scope owners`: only use `owners`.
- `--recipient-scope others`: only use `others`, such as residents or renters
  stored on the apartment record.

The workflow is:

1. Fetch bill debt analytics with the requested `debtFilterAccruals`.
2. Fetch apartments through `list_apartments()`.
3. Match each debtor to an apartment by exact apartment `number`.
4. Select a recipient source. By default, owners are tried first and `others`
   are used as a fallback.
5. Select a notification method. In `auto`, any current debtor with a prior
   successful messenger ledger record is escalated to tenant notification; old
   ledger records without `notificationMethod` are treated as messenger records.
6. Select recipients from `<scope>[].user.userId` for messenger or
   `<scope>[].tenantId` for tenant notifications.
7. Send only when `--send` is explicitly passed.

The command defaults to dry-run preview and returns `ready`, `sent`, and
`skipped` arrays. It does not print owner names, phone numbers, or raw user ids.
Use `--apartment-number` multiple times to target exact apartments, `--kind`
to select `apartment`, `premise`, or `all`, `--min-debt` to filter small debts,
and `--limit` to cap the ready notifications.

Use `--format json`, `--format table`, or `--format text` for machine-readable
or operator-readable output. `--send` requires `--confirm <apartment number>`
for every ready notification; repeat `--confirm` for batches. Dry-run previews
include readiness checks for exact apartment match, recipient presence, and the
selected notification method and recipient source.

Notification safety:

- `--one-by-one` is a shortcut for `--max-send 1`.
- `--max-send N` refuses a write if more than `N` notifications are ready.
- Sent and skipped outcomes are written to `.dah-notifications.jsonl` by
  default; the file is local and gitignored.
- Use `--ledger-path <path>` to choose another local JSONL ledger.
- Use `--no-ledger` to disable ledger writes for a single run.
- Use `--exclude-notified-today` to skip apartments already sent today.

`python3 main.py debtors-next` returns the next ready debtors without sending.
It uses the same exact apartment and recipient-readiness checks as
`debtors-notify`; combine it with `--exclude-notified-today` to build the next
operator queue.

`python3 main.py debtors-by-entrance` groups current debtors by entrance and
floor using apartment metadata from `apartment-list`. Use `--area-adjusted` to
include `debtPerArea` and sort groups by debt per square meter instead of total
debt.

Default publications payload:

```json
{
  "statuses": ["PUBLISHED"]
}
```

When `associationId` is missing from the publications payload, the client resolves it from `get_access` if exactly one unique association id is available.

## Publishing Debtors In DAH

For a DAH-internal debtors announcement:

1. Fetch debt analytics with `debtFilterAccruals=4`.
2. Read rows from the `rows` key. DAH reports debt as negative `endBalance`, so
   display debt as `-endBalance`.
3. Replace `Нежитлове приміщення` with `Приміщення` in display text when the
   user wants the shorter label.
4. Build an HTML body with paragraphs and list tags, for example
   `<p>...</p><hr><p><strong>Квартири (...)</strong></p><ul><li><p>...</p></li></ul>`.
5. Save the publication through `PublicationSaveRequest`, passing the same HTML
   string in `description` and `descriptionHtml`.
6. Verify with `get_publication()` that `descriptionHtml` still contains tags
   such as `<p>`, `<ul>`, and `<li>`.

Default bill debt analytics payload:

```json
{
  "pan": false,
  "sort": "BALANCE_ASC",
  "order": ["APARTMENT"],
  "owner": false,
  "debtFilterType": "ACCRUALS",
  "apartmentFilter": {},
  "debtFilterMonths": 0,
  "debtFilterAccruals": "<--debt-filter-accruals, default 1>",
  "splitApartmentName": false,
  "accrualTypesExclude": false,
  "flowItemsFilterExclude": false,
  "flowItemCategoriesExclude": false,
  "date": "<current local minute or --date>",
  "accrualTypes": []
}
```

Default money transaction bank list payload:

```json
{
  "direction": "EXPENSE",
  "from": "<--from-date, optional>"
}
```

## Adding an Endpoint

Add endpoint-specific request data as a small dataclass when query parameters or payload shape matter. Then add a method to `DahApiClient` that delegates to `request_json`.

Pattern:

```python
@dataclass(slots=True)
class ExampleRequest:
    page: int = 0
    size: int = 20


def example_endpoint(
    self,
    request: ExampleRequest | None = None,
    *,
    tab_id: str | None = None,
) -> Any:
    effective_request = request or ExampleRequest()
    return self.request_json(
        method="GET",
        path="/example/path",
        query={"page": effective_request.page, "size": effective_request.size},
        tab_id=tab_id,
    )
```

For CLI support, add a subparser in `DahCli._build_parser()` and add the
command to the local dispatch map. Reuse parser helpers such as
`add_association_id_argument`, `add_paging_arguments`, and `add_body_arguments`
instead of repeating common flags. Keep response printing centralized through
`_print_response`.

Endpoint extension checklist:

1. Add the request dataclass if path params, query params, or payload shape
   matter.
2. Add the `DahApiClient` method and delegate to `request_json`.
3. Quote path ids with `urllib.parse.quote(..., safe="")`.
4. Add CLI args using existing helper functions.
5. Add dry-run or explicit confirmation for write endpoints.
6. Add tests without live API calls.
7. Update this reference doc and run the quality gates.

## Testing Without Live API Calls

For compile-level checks:

```bash
python3 -m py_compile dah_api.py auth_session.py debtor_notifications.py debtor_reports.py main.py
python3 -m pytest
python3 -m ruff check .
python3 -m flake8
python3 -m isort --check-only .
python3 -m pylint dah_api.py auth_session.py debtor_notifications.py debtor_reports.py main.py tests
python3 -m pyright
python3 -m vulture dah_api.py auth_session.py debtor_notifications.py debtor_reports.py main.py tests --min-confidence 100 --ignore-names cli_env
python3 -m bandit -q -r .
python3 -m radon cc -s -n B dah_api.py auth_session.py debtor_notifications.py debtor_reports.py main.py tests
```

Additional static gates:

- `pylint`: enables only `duplicate-code` and `unreachable` through `.pylintrc`.
- `pyright`: uses `pyrightconfig.json` with `reportUnreachable` enabled.
- `vulture`: reports 100% confidence dead/unreachable code only; pytest
  fixture argument `cli_env` is ignored.

For request construction tests, instantiate `DahApiClient` with a test `DahApiConfig` and call private `_build_request` only when the task is specifically about headers, URL construction, or serialized JSON. Prefer public methods for behavior-level examples.
