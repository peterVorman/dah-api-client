import argparse
import json
import shlex

import pytest

import main as cli
from dah_api import DahHttpError, DahRequestError


class FakeClient:
    instances = []
    access_error = None
    groups_pages = [{"content": [{"id": "chat-id", "name": "2 підʼїзд"}], "last": True}]

    def __init__(self, config):
        self.config = config
        self.calls = []
        type(self).instances.append(self)

    def record(self, name, request=None):
        self.calls.append((name, request))
        return {"method": name}

    def get_access(self):
        if type(self).access_error:
            raise type(self).access_error
        return self.record("access")

    def authentication_web_login(self, request):
        return self.record("authentication-web-login", request)

    def authentication_relogin(self, request):
        return self.record("authentication-relogin", request)

    def authentication_exit(self):
        return self.record("authentication-exit")

    def search_publications(self, request):
        return self.record("publications-search", request)

    def get_publication(self, publication_id):
        return self.record("publication-get", publication_id)

    def save_publication(self, request):
        return self.record("publication-save", request)

    def get_default_association_id(self):
        return "assoc-id"

    def get_bill_debt_analytics(self, request):
        return self.record("bill-debt-analytics", request)

    def list_feedback_orders(self, request):
        return self.record("feedback-order-list", request)

    def update_feedback_order_status(self, request):
        return self.record("feedback-order-status", request)

    def list_money_transaction_bank(self, request):
        return self.record("money-transaction-bank-list", request)

    def list_messenger_group_messages(self, request):
        return self.record("messenger-group-messages", request)

    def list_messenger_groups(self, request):
        self.calls.append(("messenger-groups-page", request))
        return type(self).groups_pages[request.page]

    def send_messenger_message(self, request):
        return self.record("messenger-send-message", request)


class GroupsClient:
    def __init__(self, pages):
        self.pages = pages
        self.requests = []

    def list_messenger_groups(self, request):
        self.requests.append(request)
        return self.pages[request.page]


@pytest.fixture
def cli_env(monkeypatch):
    FakeClient.instances = []
    FakeClient.access_error = None
    FakeClient.groups_pages = [
        {"content": [{"id": "chat-id", "name": "2 підʼїзд"}], "last": True}
    ]
    monkeypatch.setattr(cli, "DahApiClient", FakeClient)
    monkeypatch.setattr(cli, "load_env_file", lambda: None)
    monkeypatch.setenv("DAH_BEARER_TOKEN", "unit-token")
    monkeypatch.delenv("DAH_ASSOCIATION_ID", raising=False)
    monkeypatch.delenv("DAH_MESSENGER_GROUP_ID", raising=False)
    monkeypatch.delenv("DAH_REFRESH_TOKEN", raising=False)
    monkeypatch.delenv("DAH_LOGIN", raising=False)
    monkeypatch.delenv("DAH_PASSWORD", raising=False)


def run_cli(argv, capsys):
    status = cli.DahCli().run(argv)
    streams = capsys.readouterr()
    return status, json.loads(streams.out), streams.err, FakeClient.instances[-1]


def last_call(client):
    return client.calls[-1] if client.calls else (None, None)


def attrs(request, names):
    return {name: getattr(request, name) for name in names}


def args(command):
    return shlex.split(command)


def case(argv, response, call, calls, attrs=(), request=None, env=None):
    if request is None:
        request = {}
    if env is None:
        env = {}
    return {
        "argv": argv,
        "response": response,
        "call": call,
        "attrs": attrs,
        "request": request,
        "env": env,
        "calls": calls,
    }


def single(argv, response, call, attrs=(), request=None, env=None):
    return case(argv, response, call, [call], attrs, request, env)


CASES = [
    single(args("--compact access"), {"method": "access"}, "access"),
    single(
        args("authentication-exit"),
        {"method": "authentication-exit"},
        "authentication-exit",
    ),
    case(
        args("authentication-web-login --dry-run"),
        {"clientId": "DAH_CLIENT_WEB", "login": "login", "password": "password"},
        None,
        calls=[],
        env={"DAH_LOGIN": "login", "DAH_PASSWORD": "password"},
    ),
    single(
        args(
            "authentication-web-login --body "
            '\'{"clientId":"DAH_CLIENT_WEB","login":"login","password":"password"}\''
        ),
        {"method": "authentication-web-login"},
        "authentication-web-login",
        ("client_id", "login", "password"),
        {
            "client_id": "DAH_CLIENT_WEB",
            "login": "login",
            "password": "password",
        },
    ),
    case(
        args("authentication-relogin --device-id device --dry-run"),
        {
            "clientId": "DAH_CLIENT_WEB",
            "clientType": "WEB",
            "deviceId": "device",
            "refreshToken": "refresh",
        },
        None,
        calls=[],
        env={"DAH_REFRESH_TOKEN": "refresh"},
    ),
    single(
        args(
            "authentication-relogin --body "
            '\'{"clientId":"DAH_CLIENT_WEB","clientType":"WEB",'
            '"deviceId":"device","refreshToken":"refresh"}\''
        ),
        {"method": "authentication-relogin"},
        "authentication-relogin",
        ("client_id", "client_type", "device_id", "refresh_token"),
        {
            "client_id": "DAH_CLIENT_WEB",
            "client_type": "WEB",
            "device_id": "device",
            "refresh_token": "refresh",
        },
    ),
    single(
        args('publications-search --page 2 --size 3 --body \'{"statuses":["DRAFT"]}\''),
        {"method": "publications-search"},
        "publications-search",
        ("page", "size", "payload"),
        {"page": 2, "size": 3, "payload": {"statuses": ["DRAFT"]}},
    ),
    single(
        ["publications-search"],
        {"method": "publications-search"},
        "publications-search",
        ("payload",),
        {"payload": {"associationId": "assoc-id", "statuses": ["PUBLISHED"]}},
        {"DAH_ASSOCIATION_ID": "assoc-id"},
    ),
    single(
        args("publication-get publication-id"),
        {"method": "publication-get"},
        "publication-get",
        (),
        {},
    ),
    case(
        args('publication-save --dry-run --body \'{"title":"New"}\''),
        {"associationId": "assoc-id", "title": "New"},
        None,
        calls=[],
    ),
    single(
        args(
            "publication-save --body "
            '\'{"id":"publication-id","associationId":"assoc-id","title":"Edited"}\''
        ),
        {"method": "publication-save"},
        "publication-save",
        ("payload",),
        {
            "payload": {
                "id": "publication-id",
                "associationId": "assoc-id",
                "title": "Edited",
            }
        },
    ),
    single(
        args(
            "bill-debt-analytics --association-id assoc-id "
            "--date 2026-07-08T15:10 --debt-filter-accruals 4 "
            "--body '{\"marker\":true}'"
        ),
        {"method": "bill-debt-analytics"},
        "bill-debt-analytics",
        ("association_id", "payload"),
        {"association_id": "assoc-id", "payload": {"marker": True}},
    ),
    single(
        args(
            'feedback-order-list --association-id assoc-id --body \'{"status":"OPEN"}\''
        ),
        {"method": "feedback-order-list"},
        "feedback-order-list",
        ("association_id", "payload"),
        {"association_id": "assoc-id", "payload": {"status": "OPEN"}},
    ),
    single(
        args("feedback-order-status order-id --status DONE"),
        {"method": "feedback-order-status"},
        "feedback-order-status",
        ("order_id", "status"),
        {"order_id": "order-id", "status": "DONE"},
    ),
    case(
        args("feedback-order-status order-id --dry-run"),
        {"status": "DONE"},
        None,
        calls=[],
    ),
    single(
        args(
            "money-transaction-bank-list --association-id assoc-id "
            "--page 1 --size 25 --direction EXPENSE "
            "--from-date 2026-07-01T00:00:00"
        ),
        {"method": "money-transaction-bank-list"},
        "money-transaction-bank-list",
        ("page", "size", "payload"),
        {
            "page": 1,
            "size": 25,
            "payload": {"direction": "EXPENSE", "from": "2026-07-01T00:00:00"},
        },
    ),
    single(
        args(
            "messenger-group-messages --group-id group-id "
            "--page 4 --size 10 --body "
            "'{\"cursor\":true}'"
        ),
        {"method": "messenger-group-messages"},
        "messenger-group-messages",
        ("group_id", "page", "payload"),
        {"group_id": "group-id", "page": 4, "payload": {"cursor": True}},
    ),
    single(
        ["messenger-groups-page", "--page", "0", "--size", "50"],
        {"content": [{"id": "chat-id", "name": "2 підʼїзд"}], "last": True},
        "messenger-groups-page",
        ("page", "size"),
        {"page": 0, "size": 50},
    ),
    case(
        args(
            "messenger-send-message --group-id group-id --create-time 7 --dry-run hello"
        ),
        {"createTime": 7, "groupId": "group-id", "payload": "hello", "type": "TEXT"},
        None,
        calls=[],
    ),
    single(
        args("messenger-send-message --group-id group-id hello"),
        {"method": "messenger-send-message"},
        "messenger-send-message",
        ("group_id", "payload"),
        {"group_id": "group-id", "payload": "hello"},
    ),
    case(
        args("messenger-send-message --chat-name '2 підʼїзд' hello"),
        {"method": "messenger-send-message"},
        "messenger-send-message",
        ["messenger-groups-page", "messenger-send-message"],
        ("group_id",),
        {"group_id": "chat-id"},
    ),
]


@pytest.mark.parametrize("case", CASES)
def test_cli_commands(cli_env, capsys, monkeypatch, case):
    for key, value in case["env"].items():
        monkeypatch.setenv(key, value)
    status, response, _, client = run_cli(case["argv"], capsys)
    call, request = last_call(client)

    assert {
        "status": status,
        "response": response,
        "call": call,
        "calls": [name for name, _ in client.calls],
        "request": attrs(request, case.get("attrs", ())),
    } == {
        "status": 0,
        "response": case["response"],
        "call": case["call"],
        "calls": case["calls"],
        "request": case["request"],
    }


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (DahHttpError(500, "Boom", "failure body"), "HTTP 500 Boom\nfailure body"),
        (DahRequestError("offline"), "offline"),
    ],
)
def test_cli_reports_client_errors(cli_env, capsys, error, expected):
    FakeClient.access_error = error
    status = cli.DahCli().run(["access"])
    streams = capsys.readouterr()
    assert status == 1
    assert expected in streams.err
    assert FakeClient.instances[-1].calls == []


def test_cli_errors_payloads_and_main(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "load_env_file", lambda: None)
    monkeypatch.delenv("DAH_BEARER_TOKEN", raising=False)
    monkeypatch.delenv("DAH_LOGIN", raising=False)
    monkeypatch.delenv("DAH_PASSWORD", raising=False)
    with pytest.raises(SystemExit, match="Missing bearer token"):
        cli.DahCli().run(["access"])

    assert cli.DahCli().run(["authentication-web-login", "--dry-run"]) == 0

    monkeypatch.setenv("DAH_BEARER_TOKEN", "unit-token")
    with pytest.raises(SystemExit, match="Missing messenger group id"):
        cli.DahCli().run(["messenger-group-messages"])

    body_file = tmp_path / "body.json"
    body_file.write_text('{"file": true}', encoding="utf-8")
    assert {
        "default": cli.load_payload(
            argparse.Namespace(body=None, body_file=None),
            {"default": True},
        ),
        "inline": cli.load_payload(
            argparse.Namespace(body='{"inline": true}', body_file=None),
            {},
        ),
        "file": cli.load_payload(
            argparse.Namespace(body=None, body_file=str(body_file)),
            {},
        ),
    } == {
        "default": {"default": True},
        "inline": {"inline": True},
        "file": {"file": True},
    }
    for action, message in [
        (
            lambda: cli.load_payload(argparse.Namespace(body="{", body_file=None), {}),
            "Invalid JSON body",
        ),
        (
            lambda: cli.read_body_file(str(tmp_path / "missing.json")),
            "Unable to read body file",
        ),
    ]:
        with pytest.raises(SystemExit, match=message):
            action()

    class ExitCli:
        def run(self):
            return 7

    monkeypatch.setattr(cli, "DahCli", ExitCli)
    assert cli.main() == 7


def test_messenger_group_resolver():
    resolver = cli.MessengerGroupResolver(
        GroupsClient(
            [
                {"content": [{"id": "first", "name": "Chat"}], "totalPages": 2},
                {"content": [{"id": "second", "name": "Other"}], "last": True},
            ]
        )
    )
    assert {
        "resolved": resolver.resolve(" chat "),
        "groups": list(
            cli.MessengerGroupResolver(
                GroupsClient([{"content": [{"id": "one"}], "totalPages": 1}])
            ).iter_groups()
        ),
        "formatted": cli.MessengerGroupResolver.format_group_ids(
            [{"id": "a"}, {"id": "b"}]
        ),
    } == {"resolved": "first", "groups": [{"id": "one"}], "formatted": "a, b"}

    for action, message in [
        (
            lambda: cli.MessengerGroupResolver(
                GroupsClient([{"content": [], "last": True}])
            ).resolve("Missing"),
            "Chat not found",
        ),
        (
            lambda: cli.MessengerGroupResolver(
                GroupsClient(
                    [
                        {
                            "content": [
                                {"id": "a", "name": "Chat"},
                                {"id": "b", "name": "Chat"},
                            ],
                            "last": True,
                        }
                    ]
                )
            ).resolve("Chat"),
            "Multiple chats found",
        ),
        (lambda: resolver.select_single_id([{"name": "Chat"}], "Chat"), "no usable id"),
        (lambda: cli.MessengerGroupResolver.extract_groups([]), "unexpected"),
        (
            lambda: cli.MessengerGroupResolver.extract_groups({"content": {}}),
            "missing groups content",
        ),
    ]:
        with pytest.raises(SystemExit, match=message):
            action()
