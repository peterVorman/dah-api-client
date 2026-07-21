import gzip
import io
import ssl
import urllib.error

import pytest

import dah_api


def config(**kwargs):
    return dah_api.DahApiConfig(token="unit-token", **kwargs)  # nosec B106


class Response:
    def __init__(self, body, headers=None):
        self.body = body
        self.headers = headers or {}

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class RecordingClient(dah_api.DahApiClient):
    def __init__(self, access=None):
        super().__init__(config())
        self.access = access or {"managerAccess": [{"id": "assoc-id"}]}
        self.calls = []

    def request_json(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs["path"] == "/organization/v1/access":
            return self.access
        return {}


def test_env_config_and_payload_defaults(tmp_path, monkeypatch):
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        """
        # comment
        DAH_BEARER_TOKEN = file-token
        INVALID-NAME=value
        NO_EQUALS
        SPACED_VALUE = value with spaces
        DAH_EXISTING = from-file
        """,
        encoding="utf-8",
    )
    monkeypatch.setenv("DAH_EXISTING", "from-env")
    monkeypatch.delenv("DAH_BEARER_TOKEN", raising=False)
    monkeypatch.delenv("SPACED_VALUE", raising=False)

    dah_api.load_env_file(env_file)
    dah_api.load_env_file(tmp_path / "missing")
    file_token = dah_api.os.environ["DAH_BEARER_TOKEN"]
    monkeypatch.setattr(dah_api, "load_env_file", lambda: None)
    monkeypatch.setenv("DAH_BEARER_TOKEN", "env-token")
    monkeypatch.setenv("DAH_TAB_ID", "tab-id")
    monkeypatch.setenv("DAH_ORIGIN", "https://origin.example")
    monkeypatch.setenv("DAH_REFERER", "https://referer.example/")
    monkeypatch.setenv("DAH_USER_AGENT", "agent")
    monkeypatch.setattr(dah_api, "time", lambda: 1.234)

    cfg = dah_api.DahApiConfig.from_env()
    bill = dah_api.default_bill_debt_analytics_payload(
        date="2026-07-08T15:10",
        debt_filter_accruals=4,
    )

    assert (
        file_token,
        dah_api.os.environ["SPACED_VALUE"],
        dah_api.os.environ["DAH_EXISTING"],
        "INVALID-NAME" in dah_api.os.environ,
        [
            dah_api._parse_env_assignment(line)
            for line in ("DAH_KEY=value", "1BAD=value", "#x", "ignored", " ")
        ],
        (cfg.token, cfg.tab_id, cfg.origin, cfg.referer, cfg.user_agent),
        isinstance(cfg.ssl_context, ssl.SSLContext),
        (bill["date"], bill["debtFilterAccruals"], bill["debtFilterMonths"]),
        dah_api.PublicationsSearchRequest().payload,
        dah_api.AuthenticationWebLoginRequest("login", "password").to_payload(),
        dah_api.AuthenticationReloginRequest("refresh", "device").to_payload(),
        dah_api.FeedbackOrderListRequest().payload,
        dah_api.FeedbackOrderStatusRequest("order-id").to_payload(),
        dah_api.MessengerGroupMessagesRequest("g").payload,
        dah_api.MessengerGroupsPageRequest().payload,
        dah_api.MoneyTransactionBankListRequest().payload,
        dah_api.PublicationSaveRequest({"title": "Hi"}).to_payload("assoc-id"),
        dah_api.MessengerMessageRequest("g", "hi").to_payload(),
    ) == (
        "file-token",
        "value with spaces",
        "from-env",
        False,
        [("DAH_KEY", "value"), None, None, None, None],
        (
            "env-token",
            "tab-id",
            "https://origin.example",
            "https://referer.example/",
            "agent",
        ),
        True,
        ("2026-07-08T15:10", 4, 0),
        {"statuses": ["PUBLISHED"]},
        {
            "clientId": "DAH_CLIENT_WEB",
            "login": "login",
            "password": "password",
        },
        {
            "clientId": "DAH_CLIENT_WEB",
            "clientType": "WEB",
            "deviceId": "device",
            "refreshToken": "refresh",
        },
        {},
        {"status": "DONE"},
        {},
        {},
        {"direction": "EXPENSE"},
        {"associationId": "assoc-id", "title": "Hi"},
        {
            "createTime": 1234,
            "groupId": "g",
            "payload": "hi",
            "type": "TEXT",
        },
    )
    assert "T" in dah_api.default_bill_debt_analytics_payload()["date"]

    for kwargs, message in [
        ({"token": ""}, "Missing bearer token"),
        (
            {"token": "x", "base_url": "http://api.dah-online.com"},
            "DAH base URL",
        ),
    ]:
        with pytest.raises(ValueError, match=message):
            dah_api.DahApiConfig(**kwargs)
    monkeypatch.delenv("DAH_BEARER_TOKEN")
    with pytest.raises(ValueError, match="Missing bearer token"):
        dah_api.DahApiConfig.from_env()


def test_association_resolution_success():
    client = RecordingClient(
        {
            "managerAccess": [{"id": "assoc-id"}, {"id": ""}, {"id": 3}],
            "tenantAccess": [{"id": "assoc-id"}, "ignored"],
        }
    )
    assert (
        client.get_default_association_id(),
        client.get_default_association_id(),
        len(client.calls),
        dah_api.DahApiClient._extract_access_association_ids("bad"),
        dah_api.DahApiClient._extract_access_association_ids(
            {"managerAccess": [{"id": "a"}], "tenantAccess": [{"id": "b"}]}
        ),
    ) == ("assoc-id", "assoc-id", 1, [], ["a", "b"])


@pytest.mark.parametrize(
    "access",
    [
        {"managerAccess": []},
        {"managerAccess": [{"id": "a"}], "tenantAccess": [{"id": "b"}]},
    ],
)
def test_association_resolution_errors(access):
    with pytest.raises(dah_api.DahRequestError, match="Unable to resolve"):
        RecordingClient(access).get_default_association_id()


def test_endpoint_requests():
    client = RecordingClient()
    client.authentication_web_login(
        dah_api.AuthenticationWebLoginRequest("login", "password")
    )
    client.search_publications(dah_api.PublicationsSearchRequest(page=1, size=2))
    client.authentication_relogin(
        dah_api.AuthenticationReloginRequest("refresh", "device")
    )
    client.authentication_exit()
    client.get_publication("publication/id")
    client.save_publication(dah_api.PublicationSaveRequest({"title": "New"}))
    client.save_publication(
        dah_api.PublicationSaveRequest({"id": "publication-id", "title": "Edited"})
    )
    client._default_association_id = "assoc/id"
    client.get_bill_debt_analytics(
        dah_api.BillDebtAnalyticsRequest(payload={"debt": True}),
        tab_id="tab",
    )
    client.list_feedback_orders(
        dah_api.FeedbackOrderListRequest("feedback/id", {"feedback": True})
    )
    client.update_feedback_order_status(
        dah_api.FeedbackOrderStatusRequest("order/id", "DONE")
    )
    client.list_money_transaction_bank(
        dah_api.MoneyTransactionBankListRequest(
            "money/id",
            3,
            4,
            {"direction": "INCOME"},
        )
    )
    client.list_messenger_group_messages(
        dah_api.MessengerGroupMessagesRequest("group/id", 5, 6, {"messages": True})
    )
    client.list_messenger_groups(
        dah_api.MessengerGroupsPageRequest(7, 8, {"q": "chat"})
    )
    client.send_messenger_message(
        dah_api.MessengerMessageRequest("group-id", "hello", create_time=9)
    )

    assert [call["path"] for call in client.calls] == [
        "/authentication/web/login",
        "/organization/v1/access",
        "/publications/search",
        "/authentication/relogin",
        "/authentication/exit",
        "/publications/get/publication%2Fid",
        "/publications/v2/add/web",
        "/publications/v2/edit/web",
        "/accounting/v1/report/bill/assoc%2Fid/debt/analytics",
        "/feedback/order/list/feedback%2Fid",
        "/feedback/order/comment/order%2Fid",
        "/accounting/v1/money/transaction/money%2Fid/list/bank",
        "/messenger/groups/group%2Fid/messages",
        "/messenger/groups/page",
        "/messenger/messages",
    ]
    assert (
        client.calls[0]["payload"],
        client.calls[2]["query"],
        client.calls[2]["payload"]["associationId"],
        client.calls[3]["payload"],
        client.calls[4]["method"],
        client.calls[5]["method"],
        client.calls[6]["payload"],
        client.calls[7]["payload"],
        client.calls[8]["payload"],
        client.calls[8]["tab_id"],
        client.calls[10]["payload"],
        client.calls[11]["query"],
        client.calls[14]["payload"],
    ) == (
        {
            "clientId": "DAH_CLIENT_WEB",
            "login": "login",
            "password": "password",
        },
        {"page": 1, "size": 2},
        "assoc-id",
        {
            "clientId": "DAH_CLIENT_WEB",
            "clientType": "WEB",
            "deviceId": "device",
            "refreshToken": "refresh",
        },
        "GET",
        "GET",
        {"associationId": "assoc-id", "title": "New"},
        {"associationId": "assoc-id", "id": "publication-id", "title": "Edited"},
        {"debt": True},
        "tab",
        {"status": "DONE"},
        {"page": 3, "size": 4},
        {
            "createTime": 9,
            "groupId": "group-id",
            "payload": "hello",
            "type": "TEXT",
        },
    )


def test_request_json_success(monkeypatch):
    client = dah_api.DahApiClient(config(tab_id="configured-tab", timeout=12))
    seen = []

    def success(request, timeout, context):
        seen.append((request, timeout, context))
        return Response(gzip.compress(b'{"ok": true}'), {"Content-Encoding": "gzip"})

    monkeypatch.setattr(dah_api.urllib.request, "urlopen", success)
    assert client.request_json(
        method="POST",
        path="/test",
        query={"name": "two words"},
        payload={"x": 1},
    ) == {"ok": True}
    request, timeout, context = seen[0]
    headers = {key.lower(): value for key, value in request.header_items()}
    assert (
        timeout,
        isinstance(context, ssl.SSLContext),
        request.full_url,
        request.data,
        request.get_method(),
        headers["authorization"],
        headers["x-dah-tabid"],
        headers["content-type"],
    ) == (
        12,
        True,
        "https://api.dah-online.com/test?name=two+words",
        b'{"x":1}',
        "POST",
        "Bearer unit-token",
        "configured-tab",
        "application/json",
    )


def test_build_request_without_body():
    plain = dah_api.DahApiClient(config())._build_request(
        method="GET",
        path="/plain",
        query=None,
        payload=None,
        tab_id="manual-tab",
    )
    headers = {key.lower(): value for key, value in plain.header_items()}
    assert (
        plain.full_url,
        plain.data,
        headers["x-dah-tabid"],
        headers.get("content-type"),
    ) == ("https://api.dah-online.com/plain", None, "manual-tab", None)


def test_build_request_without_token():
    request = dah_api.DahApiClient(
        dah_api.DahApiConfig(require_token=False)
    )._build_request(
        method="POST",
        path="/authentication/web/login",
        query=None,
        payload={},
        tab_id=None,
    )
    headers = {key.lower(): value for key, value in request.header_items()}
    assert "authorization" not in headers


def test_request_json_errors(monkeypatch):
    client = dah_api.DahApiClient(config())

    def http_error(request, timeout, context):
        raise urllib.error.HTTPError(
            request.full_url,
            418,
            "Teapot",
            hdrs={},
            fp=io.BytesIO(b'{"error": true}'),
        )

    monkeypatch.setattr(dah_api.urllib.request, "urlopen", http_error)
    with pytest.raises(dah_api.DahHttpError) as exc_info:
        client.request_json(method="GET", path="/broken")
    assert (exc_info.value.status_code, exc_info.value.reason, exc_info.value.body) == (
        418,
        "Teapot",
        '{"error": true}',
    )

    def url_error(request, timeout, context):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(dah_api.urllib.request, "urlopen", url_error)
    with pytest.raises(dah_api.DahRequestError, match="Request failed"):
        client.request_json(method="GET", path="/offline")
