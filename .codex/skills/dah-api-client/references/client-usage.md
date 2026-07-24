# DAH Client Usage

## Repository

The local DAH client lives in the current repository root:

```text
$PWD
```

Important files:

- `dah_api.py`: object-oriented API client, configuration, request types, and exceptions.
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
    feedback_orders = client.list_feedback_orders(FeedbackOrderListRequest())
    closed_order = client.update_feedback_order_status(
        FeedbackOrderStatusRequest(
            order_id="<feedback order id>",
            status="DONE",
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
python3 main.py authentication-web-login --dry-run
python3 main.py authentication-relogin --device-id "$DAH_DEVICE_ID" --dry-run
python3 main.py authentication-exit
python3 main.py publications-search --page 0 --size 5
python3 main.py publications-search --body '{"associationId":"<association id>","statuses":["PUBLISHED"]}'
python3 main.py publications-search --body-file request.json --compact
python3 main.py publication-get '<publication id>'
python3 main.py publication-save --body-file publication.json --dry-run
python3 main.py bill-debt-analytics --date 2026-07-08T15:10 --debt-filter-accruals 1
python3 main.py feedback-order-list
python3 main.py feedback-order-status '<feedback order id>' --status DONE --dry-run
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

`DahApiClient.authentication_exit()` calls:

```text
GET /authentication/exit
```

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

For CLI support, add a subparser in `DahCli._build_parser()` and add the command to the local handler map in `DahCli.run()`. Keep response printing centralized through `_print_response`.

## Testing Without Live API Calls

For compile-level checks:

```bash
python3 -m py_compile dah_api.py main.py
```

For request construction tests, instantiate `DahApiClient` with a test `DahApiConfig` and call private `_build_request` only when the task is specifically about headers, URL construction, or serialized JSON. Prefer public methods for behavior-level examples.
