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
- `DAH_ASSOCIATION_ID`: optional association id override. When absent, scoped endpoints resolve the single available id from `get_access`.
- `DAH_TAB_ID`: optional `X-DAH-TabId` header.
- `DAH_ORIGIN`: Origin header, default `https://cabinet.dah-online.com`.
- `DAH_REFERER`: Referer header, default `https://cabinet.dah-online.com/`.
- `DAH_USER_AGENT`: User-Agent header.
- `DAH_MESSENGER_GROUP_ID`: optional default group id for `messenger-group-messages`.

Never print the bearer token. Avoid committing newly captured tokens.

When using `.env.local`, keep entries as plain `KEY=value` lines. The local loader ignores blank lines and comments, and it does not implement shell syntax such as `export KEY=value`.

If a live request returns `401 Unauthorized`, first assume the active token is expired or missing. Use a fresh `DAH_BEARER_TOKEN` from the environment instead of editing code or hard-coding tokens.

## Python Quick Start

```python
from dah_api import (
    DahApiClient,
    DahApiConfig,
    DahHttpError,
    DahRequestError,
    BillDebtAnalyticsRequest,
    FeedbackOrderListRequest,
    MoneyTransactionBankListRequest,
    MessengerGroupMessagesRequest,
    MessengerGroupsPageRequest,
    MessengerMessageRequest,
    PublicationsSearchRequest,
    default_bill_debt_analytics_payload,
)

client = DahApiClient(DahApiConfig.from_env())

try:
    access = client.get_access()
    publications = client.search_publications(PublicationsSearchRequest(page=0, size=5))
    debt = client.get_bill_debt_analytics(
        BillDebtAnalyticsRequest(
            payload=default_bill_debt_analytics_payload(date="2026-07-08T15:10"),
        )
    )
    feedback_orders = client.list_feedback_orders(FeedbackOrderListRequest())
    bank_transactions = client.list_money_transaction_bank(
        MoneyTransactionBankListRequest(page=0, size=50)
    )
    groups = client.list_messenger_groups(MessengerGroupsPageRequest(page=0, size=50))
    messages = client.list_messenger_group_messages(
        MessengerGroupMessagesRequest(group_id="<messenger group id>", page=0, size=50)
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
python3 main.py publications-search --page 0 --size 5
python3 main.py publications-search --body '{"associationId":"<association id>","statuses":["PUBLISHED"]}'
python3 main.py publications-search --body-file request.json --compact
python3 main.py bill-debt-analytics --date 2026-07-08T15:10 --debt-filter-accruals 1
python3 main.py feedback-order-list
python3 main.py money-transaction-bank-list --direction EXPENSE --from-date 2026-07-01T00:00:00 --page 0 --size 50
python3 main.py messenger-groups-page --page 0 --size 50
python3 main.py messenger-group-messages --group-id '<messenger group id>' --page 0 --size 50
python3 main.py messenger-send-message --chat-name '1 підʼїзд' --dry-run 'Ліфт відновив роботу'
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

`DahApiClient.search_publications()` calls:

```text
POST /publications/search?page=<page>&size=<size>
```

`DahApiClient.get_bill_debt_analytics()` calls:

```text
POST /accounting/v1/report/bill/<associationId>/debt/analytics
```

`DahApiClient.list_feedback_orders()` calls:

```text
POST /feedback/order/list/<associationId>
```

`DahApiClient.list_money_transaction_bank()` calls:

```text
POST /accounting/v1/money/transaction/<associationId>/list/bank?page=<page>&size=<size>
```

`DahApiClient.list_messenger_group_messages()` calls:

```text
POST /messenger/groups/<groupId>/messages?page=<page>&size=<size>
```

`DahApiClient.list_messenger_groups()` calls:

```text
POST /messenger/groups/page?page=<page>&size=<size>
```

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

Default publications payload:

```json
{
  "statuses": ["PUBLISHED"]
}
```

When `associationId` is missing from the publications payload, the client resolves it from `get_access` if exactly one unique association id is available.

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
