# Endpoints

## Contents

- Function Map
- Default Payloads
- Endpoint Extension Checklist

## Function Map

- `DahApiConfig.from_env()`: build client config from `.env.local` and
  environment variables.
- `DahApiClient.get_access()`: `GET /organization/v1/access`.
- `DahApiClient.authentication_web_login()`: `POST /authentication/web/login`.
- `DahApiClient.authentication_relogin()`: `POST /authentication/relogin`.
- `DahApiClient.authentication_exit()`: `GET /authentication/exit`.
- `DahApiClient.search_publications()`: `POST /publications/search`.
- `DahApiClient.get_publication(publication_id)`:
  `GET /publications/get/<publicationId>`.
- `DahApiClient.save_publication()`: `POST /publications/v2/add/web` or
  `PUT /publications/v2/edit/web`.
- `DahApiClient.get_bill_debt_analytics()`:
  `POST /accounting/v1/report/bill/<associationId>/debt/analytics`.
- `DahApiClient.list_feedback_orders()`:
  `POST /feedback/order/list/<associationId>`.
- `DahApiClient.update_feedback_order_status()`:
  `PUT /feedback/order/comment/<orderId>`.
- `DahApiClient.send_tenant_notification()`:
  `POST /communication/v1/client/notification/<associationId>/tenant/send`.
- `DahApiClient.list_money_transaction_bank()`:
  `POST /accounting/v1/money/transaction/<associationId>/list/bank`.
- `DahApiClient.list_apartments()`:
  `POST /organization/v1/apartment/<associationId>/list`.
- `DahApiClient.list_messenger_groups()`: `POST /messenger/groups/page`.
- `DahApiClient.list_messenger_group_messages()`:
  `POST /messenger/groups/<groupId>/messages`.
- `DahApiClient.get_messenger_personal_group()`:
  `GET /messenger/groups/personal/<interlocutorId>/get`.
- `DahApiClient.send_messenger_message()`: `POST /messenger/messages`.

## Default Payloads

Authentication web login:

```json
{
  "clientId": "DAH_CLIENT_WEB",
  "login": "<login>",
  "password": "<password>"
}
```

Authentication relogin:

```json
{
  "clientId": "DAH_CLIENT_WEB",
  "clientType": "WEB",
  "deviceId": "<device id>",
  "refreshToken": "<refresh token>"
}
```

Bill debt analytics:

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

Tenant notification:

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

Messenger message:

```json
{
  "createTime": "<epoch milliseconds>",
  "groupId": "<messenger group id>",
  "payload": "<message text>",
  "type": "TEXT"
}
```

Money transaction bank list:

```json
{
  "direction": "EXPENSE",
  "from": "<--from-date, optional>"
}
```

Feedback order status:

```json
{
  "status": "DONE"
}
```

## Endpoint Extension Checklist

1. Add endpoint-specific request data as a small dataclass in `dah_api.py` when
   query params, path params, or payload shape matter.
2. Add a `DahApiClient` method that delegates to `request_json`.
3. Quote path ids with `urllib.parse.quote(..., safe="")`.
4. Add CLI arguments in `cli_parser.py` using existing parser helpers.
5. Add command dispatch and request construction in `main.py`.
6. Add dry-run or explicit confirmation for write endpoints.
7. Add unit tests without live API calls for request construction, CLI args,
   default payloads, and error handling.
8. Update this reference and run the quality gates.

For formatted DAH publications, put the same HTML body in `description` and
`descriptionHtml`; otherwise DAH can save the announcement as unformatted text.

For live API calls, warn the user that the request will contact
`api.dah-online.com` if that is not already obvious. Use read-oriented endpoints
by default. For write endpoints, preview first and send only after explicit user
approval.
