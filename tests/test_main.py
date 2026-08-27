import argparse
import json
import os
import shlex

import pytest

import main as cli
from dah_api import DahHttpError, DahRequestError


class FakeClient:
    instances = []
    access_error = None
    fail_access_once = False
    debt_response = None
    apartment_response = None
    money_response = None
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
        if type(self).fail_access_once:
            type(self).fail_access_once = False
            raise DahHttpError(
                401, "Unauthorized", '{"message":"invalid_access_token"}'
            )
        return self.record("access")

    def authentication_web_login(self, request):
        self.calls.append(("authentication-web-login", request))
        return {"accessToken": "unit-access-token", "login": request.login}

    def authentication_relogin(self, request):
        self.calls.append(("authentication-relogin", request))
        return {
            "accessToken": "refreshed-token",
            "refreshToken": "unit-refresh-token",
            "deviceId": request.device_id,
        }

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
        if type(self).debt_response is not None:
            self.calls.append(("bill-debt-analytics", request))
            return type(self).debt_response
        return self.record("bill-debt-analytics", request)

    def list_feedback_orders(self, request):
        return self.record("feedback-order-list", request)

    def update_feedback_order_status(self, request):
        return self.record("feedback-order-status", request)

    def send_tenant_notification(self, request):
        return self.record("tenant-notification-send", request)

    def list_apartments(self, request):
        if type(self).apartment_response is not None:
            self.calls.append(("apartment-list", request))
            return type(self).apartment_response
        return self.record("apartment-list", request)

    def list_money_transaction_bank(self, request):
        if type(self).money_response is not None:
            self.calls.append(("money-transaction-bank-list", request))
            return type(self).money_response
        return self.record("money-transaction-bank-list", request)

    def list_messenger_group_messages(self, request):
        return self.record("messenger-group-messages", request)

    def list_messenger_groups(self, request):
        self.calls.append(("messenger-groups-page", request))
        return type(self).groups_pages[request.page]

    def get_messenger_personal_group(self, request):
        return {
            "id": "personal-group-id",
            "interlocutorId": request.interlocutor_id,
            "type": "PERSONAL",
            "canWriteMessage": True,
        }

    def send_messenger_message(self, request):
        return self.record("messenger-send-message", request)


class GroupsClient:
    def __init__(self, pages):
        self.pages = pages
        self.requests = []

    def list_messenger_groups(self, request):
        self.requests.append(request)
        return self.pages[request.page]


class PersonalGroupClient:
    def __init__(self, group):
        self.group = group

    def get_messenger_personal_group(self, request):
        self.request = request
        return self.group


@pytest.fixture
def cli_env(monkeypatch, tmp_path):
    FakeClient.instances = []
    FakeClient.access_error = None
    FakeClient.fail_access_once = False
    FakeClient.debt_response = None
    FakeClient.apartment_response = None
    FakeClient.money_response = None
    FakeClient.groups_pages = [
        {"content": [{"id": "chat-id", "name": "2 підʼїзд"}], "last": True}
    ]
    monkeypatch.setattr(cli, "DahApiClient", FakeClient)
    monkeypatch.setattr(cli, "load_env_file", lambda: None)
    monkeypatch.setenv("DAH_BEARER_TOKEN", "unit-token")
    monkeypatch.delenv("DAH_ASSOCIATION_ID", raising=False)
    monkeypatch.delenv("DAH_REFRESH_TOKEN", raising=False)
    monkeypatch.delenv("DAH_LOGIN", raising=False)
    monkeypatch.delenv("DAH_PASSWORD", raising=False)
    monkeypatch.chdir(tmp_path)


def run_cli(argv, capsys):
    status = cli.DahCli().run(argv)
    streams = capsys.readouterr()
    return status, json.loads(streams.out), streams.err, FakeClient.instances[-1]


def run_cli_text(argv, capsys):
    status = cli.DahCli().run(argv)
    streams = capsys.readouterr()
    return status, streams.out, streams.err, FakeClient.instances[-1]


def last_call(client):
    return client.calls[-1] if client.calls else (None, None)


def attrs(request, names):
    return {name: getattr(request, name) for name in names}


def args(command):
    return shlex.split(command)


def apartment(number, entrance, floor, area):
    return {
        "number": number,
        "entrance": entrance,
        "floor": floor,
        "area": area,
        "owners": [{"user": {"userId": f"user-{number}", "userStatus": "ACTIVE"}}],
    }


def apartment_with_other_recipient(number):
    return {
        "number": number,
        "owners": [
            {
                "tenantId": "owner-tenant",
                "user": {"userId": "owner-user", "userStatus": "REGISTRATION"},
            }
        ],
        "others": [{"tenantId": "other-tenant"}],
    }


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
        args("auth-status"),
        {
            "bearerTokenPresent": True,
            "bearerTokenExpiresAt": None,
            "bearerTokenExpired": None,
            "accessCheck": {"ok": True},
        },
        "access",
    ),
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
        {"response": {"accessToken": "<redacted>", "login": "<redacted>"}},
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
        {
            "response": {
                "accessToken": "<redacted>",
                "deviceId": "device",
                "refreshToken": "<redacted>",
            }
        },
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
    case(
        [
            "tenant-notification-send",
            "--tenant-id",
            "tenant-id",
            "--text",
            "Hello\nPay",
        ],
        {
            "details": [
                {"type": "APP", "enabled": True},
                {"type": "EMAIL", "enabled": True},
                {"type": "SMS", "enabled": True},
            ],
            "tenantId": "tenant-id",
            "text": "Hello\nPay",
            "textHtml": "<p>Hello<br>Pay</p>",
        },
        None,
        calls=[],
    ),
    single(
        args(
            "tenant-notification-send --association-id assoc-id "
            "--tenant-id tenant-id --text Hello --send --confirm-tenant-id tenant-id"
        ),
        {"method": "tenant-notification-send"},
        "tenant-notification-send",
        ("association_id", "tenant_id", "text"),
        {"association_id": "assoc-id", "tenant_id": "tenant-id", "text": "Hello"},
    ),
    single(
        args("apartment-list --association-id assoc-id --page 1 --size 25"),
        {"method": "apartment-list"},
        "apartment-list",
        ("association_id", "page", "size", "payload"),
        {"association_id": "assoc-id", "page": 1, "size": 25, "payload": {}},
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
        args("messenger-personal-group-get user-id"),
        {
            "id": "personal-group-id",
            "interlocutorId": "user-id",
            "type": "PERSONAL",
            "canWriteMessage": True,
        },
        None,
        [],
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
    single(
        args("messenger-send-message --interlocutor-id user-id hello"),
        {"method": "messenger-send-message"},
        "messenger-send-message",
        ("group_id", "payload"),
        {"group_id": "personal-group-id", "payload": "hello"},
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


def test_cli_retries_read_only_after_invalid_token(cli_env, capsys, monkeypatch):
    monkeypatch.setenv("DAH_BEARER_TOKEN", "expired-token")
    monkeypatch.setenv("DAH_REFRESH_TOKEN", "refresh-token")
    monkeypatch.setattr(
        cli,
        "save_auth_env",
        lambda response: {"path": ".env.local", "keys": sorted(response)},
    )
    FakeClient.fail_access_once = True

    status, response, _, _ = run_cli(["access"], capsys)

    assert (
        status,
        response,
        [client.config.token for client in FakeClient.instances],
        os.environ["DAH_BEARER_TOKEN"],
    ) == (
        0,
        {"method": "access"},
        ["expired-token", "", "refreshed-token"],
        "refreshed-token",
    )


def test_cli_retry_auth_falls_back_to_login(cli_env, monkeypatch):
    class LoginClient:
        def authentication_relogin(self, request):
            raise DahHttpError(401, "Unauthorized", "expired")

        def authentication_web_login(self, request):
            return {"accessToken": "login-token", "login": request.login}

    monkeypatch.setenv("DAH_REFRESH_TOKEN", "bad-refresh")
    monkeypatch.setenv("DAH_LOGIN", "login")
    monkeypatch.setenv("DAH_PASSWORD", "password")

    assert cli.DahCli._refresh_auth_response(LoginClient()) == {
        "accessToken": "login-token",
        "login": "login",
    }


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (argparse.Namespace(command="access"), True),
        (argparse.Namespace(command="publication-save", dry_run=True), True),
        (argparse.Namespace(command="publication-save", dry_run=False), False),
        (argparse.Namespace(command="debtors-notify", send=False), True),
        (argparse.Namespace(command="debtors-notify", send=True), False),
        (argparse.Namespace(command="tenant-notification-send", send=False), True),
        (argparse.Namespace(command="messenger-send-message", dry_run=True), True),
        (argparse.Namespace(command="feedback-order-status", dry_run=False), False),
    ],
)
def test_command_is_read_only(args, expected):
    assert cli.command_is_read_only(args) is expected


def test_cli_without_token_commands(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "load_env_file", lambda: None)
    monkeypatch.delenv("DAH_BEARER_TOKEN", raising=False)
    monkeypatch.delenv("DAH_LOGIN", raising=False)
    monkeypatch.delenv("DAH_PASSWORD", raising=False)
    with pytest.raises(SystemExit, match="Missing bearer token"):
        cli.DahCli().run(["access"])

    assert cli.DahCli().run(["authentication-web-login", "--dry-run"]) == 0
    assert (
        cli.DahCli().run(
            [
                "ledger-add-contact",
                "--apartment-number",
                "55",
                "--status",
                "no_answer",
                "--ledger-path",
                str(tmp_path / "ledger.jsonl"),
            ]
        )
        == 0
    )

    monkeypatch.setenv("DAH_BEARER_TOKEN", "unit-token")
    with pytest.raises(SystemExit, match="Missing messenger group id"):
        cli.DahCli().run(["messenger-group-messages"])


def test_cli_payloads_and_main(monkeypatch, tmp_path):
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


def test_cli_tenant_notification_guards(cli_env, capsys):
    FakeClient.access_error = DahRequestError("offline")
    status, response, _, _ = run_cli(args("auth-status"), capsys)
    assert (status, response["accessCheck"]) == (
        0,
        {"ok": False, "error": "offline"},
    )

    for command, message in [
        ("tenant-notification-send --text Hello", "Missing tenant id"),
        ("tenant-notification-send --tenant-id tenant-id", "Missing tenant"),
        (
            'tenant-notification-send --body \'{"tenantId":"tenant-id",'
            '"text":"Hello","details":{}}\'',
            "details must be a JSON array",
        ),
        (
            "tenant-notification-send --tenant-id tenant-id --text Hello "
            "--send --confirm-tenant-id other",
            "Missing --confirm-tenant-id",
        ),
    ]:
        with pytest.raises(SystemExit, match=message):
            cli.DahCli().run(args(command))


def test_cli_debtors_notify(cli_env, capsys):
    FakeClient.debt_response = {
        "rows": [{"apartmentName": "Квартира 55", "endBalance": -4203.9}]
    }
    FakeClient.apartment_response = {
        "content": [
            {
                "number": "55",
                "owners": [{"user": {"userId": "user-id", "userStatus": "ACTIVE"}}],
            }
        ],
        "last": True,
    }

    status, response, _, client = run_cli(
        args("debtors-notify --association-id assoc-id --apartment-number 55"),
        capsys,
    )

    assert (
        status,
        response["mode"],
        response["ready"][0]["apartment"],
        response["ready"][0]["checks"]["exactApartmentFound"],
        [name for name, _ in client.calls],
    ) == (
        0,
        "dry-run",
        "55",
        True,
        ["apartment-list", "bill-debt-analytics"],
    )


def test_cli_debtors_notify_tenant_method(cli_env, capsys):
    FakeClient.debt_response = {
        "rows": [{"apartmentName": "Квартира 55", "endBalance": -4203.9}]
    }
    FakeClient.apartment_response = {
        "content": [
            {
                "number": "55",
                "owners": [
                    {
                        "tenantId": "tenant-id",
                        "user": {"userId": "user-id", "userStatus": "ACTIVE"},
                    }
                ],
            }
        ],
        "last": True,
    }

    status, response, _, client = run_cli(
        args(
            "debtors-notify --notification-method tenant "
            "--apartment-number 55 --send --confirm 55"
        ),
        capsys,
    )
    call, request = last_call(client)

    assert (
        status,
        response["ready"][0]["notificationMethod"],
        response["sent"],
        call,
        request.tenant_id,
        [name for name, _ in client.calls],
    ) == (
        0,
        "tenant",
        [{"apartment": "55", "recipients": 1}],
        "tenant-notification-send",
        "tenant-id",
        ["apartment-list", "bill-debt-analytics", "tenant-notification-send"],
    )


def test_cli_debtors_notify_auto_method(cli_env, capsys, tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    ledger_path.write_text(
        '{"date":"2026-07-28","apartment":"55","status":"sent"}\n',
        encoding="utf-8",
    )
    FakeClient.debt_response = {
        "rows": [{"apartmentName": "Квартира 55", "endBalance": -4203.9}]
    }
    FakeClient.apartment_response = {
        "content": [
            {
                "number": "55",
                "owners": [
                    {
                        "tenantId": "tenant-id",
                        "user": {"userId": "user-id", "userStatus": "ACTIVE"},
                    }
                ],
            }
        ],
        "last": True,
    }

    status, response, _, client = run_cli(
        args(f"debtors-notify --apartment-number 55 --ledger-path {ledger_path}"),
        capsys,
    )

    assert (
        status,
        response["ready"][0]["notificationMethod"],
        response["ready"][0]["recipientScope"],
        response["ready"][0]["recipients"],
        [name for name, _ in client.calls],
    ) == (
        0,
        "tenant",
        "owners",
        1,
        ["apartment-list", "bill-debt-analytics"],
    )


def test_cli_debtors_notify_others_recipient_scope(cli_env, capsys):
    FakeClient.debt_response = {
        "rows": [{"apartmentName": "Квартира 84", "endBalance": -3644.52}]
    }
    FakeClient.apartment_response = {
        "content": [apartment_with_other_recipient("84")],
        "last": True,
    }

    status, response, _, client = run_cli(
        args(
            "debtors-notify --notification-method tenant "
            "--recipient-scope others --apartment-number 84 "
            "--send --confirm 84"
        ),
        capsys,
    )
    call, request = last_call(client)

    assert (
        status,
        response["ready"][0]["notificationMethod"],
        response["ready"][0]["recipientScope"],
        response["sent"],
        call,
        request.tenant_id,
    ) == (
        0,
        "tenant",
        "others",
        [{"apartment": "84", "recipients": 1}],
        "tenant-notification-send",
        "other-tenant",
    )


def test_cli_debtors_notify_owners_plus_others_scope(cli_env, capsys):
    FakeClient.debt_response = {
        "rows": [{"apartmentName": "Квартира 84", "endBalance": -3644.52}]
    }
    FakeClient.apartment_response = {
        "content": [
            {
                "number": "84",
                "owners": [
                    {
                        "user": {
                            "userId": "owner-user",
                            "userStatus": "ACTIVE",
                        }
                    }
                ],
                "others": [
                    {
                        "user": {
                            "userId": "other-user",
                            "userStatus": "ACTIVE",
                        }
                    }
                ],
            }
        ],
        "last": True,
    }

    status, response, _, _ = run_cli(
        args("debtors-notify --recipient-scope owners+others --apartment-number 84"),
        capsys,
    )

    assert (
        status,
        response["ready"][0]["recipientScope"],
        response["ready"][0]["recipients"],
    ) == (0, "owners+others", 2)


def test_cli_debtors_notify_formats_and_confirm(cli_env, capsys, tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    FakeClient.debt_response = {
        "rows": [{"apartmentName": "Квартира 55", "endBalance": -4203.9}]
    }
    FakeClient.apartment_response = {
        "content": [
            {
                "number": "55",
                "owners": [{"user": {"userId": "user-id", "userStatus": "ACTIVE"}}],
            }
        ],
        "last": True,
    }

    text = run_cli_text(args("debtors-notify --format text"), capsys)[1]
    table = run_cli_text(args("debtors-notify --format table"), capsys)[1]
    failed_status = cli.DahCli().run(args("debtors-notify --send"))
    failed_streams = capsys.readouterr()
    status, response, _, client = run_cli(
        args(f"debtors-notify --send --confirm 55 --ledger-path {ledger_path}"),
        capsys,
    )

    assert (
        "Mode: dry-run" in text,
        "55 | 4 203,90 | 1" in table,
        failed_status,
        "Missing --confirm" in failed_streams.err,
        status,
        response["mode"],
        response["sent"],
        [name for name, _ in client.calls],
    ) == (
        True,
        True,
        1,
        True,
        0,
        "send",
        [{"apartment": "55", "recipients": 1}],
        [
            "apartment-list",
            "bill-debt-analytics",
            "messenger-send-message",
        ],
    )
    assert '"status": "sent"' in ledger_path.read_text(encoding="utf-8")


def test_cli_debtors_next_and_entrance(cli_env, capsys, tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    ledger_path.write_text(
        '{"date":"2099-01-01","apartment":"55","status":"sent"}\n',
        encoding="utf-8",
    )
    FakeClient.debt_response = {
        "rows": [
            {"apartmentName": "Квартира 55", "endBalance": -4203.9},
            {"apartmentName": "Квартира 84", "endBalance": -3644.52},
        ]
    }
    FakeClient.apartment_response = {
        "content": [
            apartment("55", "1", 2, 50),
            apartment("84", "1", 3, 100),
        ],
        "last": True,
    }

    status, response, _, client = run_cli(
        args(
            "debtors-next --notification-method messenger "
            f"--limit 2 --ledger-path {ledger_path}"
        ),
        capsys,
    )
    by_entrance = run_cli(
        args("debtors-by-entrance --area-adjusted --kind apartment"),
        capsys,
    )[1]

    assert (
        status,
        response["items"][0]["apartment"],
        by_entrance["summary"]["debtPerArea"],
        by_entrance["entrances"][0]["floors"][0]["floor"],
        [name for name, _ in client.calls],
    ) == (
        0,
        "55",
        52.32,
        "2",
        ["apartment-list", "bill-debt-analytics"],
    )


def test_cli_debtor_audit_and_snapshot(cli_env, capsys, tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    snapshot_path = tmp_path / "snapshots.jsonl"
    ledger_path.write_text(
        '{"date":"2026-07-01","apartment":"55","status":"sent"}\n',
        encoding="utf-8",
    )
    FakeClient.debt_response = {
        "rows": [{"apartmentName": "Квартира 55", "endBalance": -4203.9}]
    }
    FakeClient.apartment_response = {
        "content": [apartment("55", "1", 2, 50)],
        "last": True,
    }
    FakeClient.money_response = {
        "content": [
            {
                "operationDate": "2026-07-03T12:00:00",
                "amount": 1000,
                "analytics": {"name": "Квартира 55"},
            }
        ],
        "last": True,
    }

    audit = run_cli(
        args(
            f"debtor-audit --apartment-number 55 --ledger-path {ledger_path} "
            "--from-date 2026-07-01T00:00:00"
        ),
        capsys,
    )[1]
    snapshot = run_cli(
        args(f"debt-snapshot --write --snapshot-path {snapshot_path}"),
        capsys,
    )[1]

    assert (
        audit["currentDebt"],
        audit["ledger"]["records"],
        audit["paymentTotal"],
        snapshot["current"]["summary"]["debt"],
        snapshot["previous"],
        len(snapshot_path.read_text(encoding="utf-8").splitlines()),
    ) == (4203.9, 1, 1000.0, 4203.9, None, 1)


def test_cli_debtors_notify_send_limits(cli_env, capsys):
    FakeClient.debt_response = {
        "rows": [
            {"apartmentName": "Квартира 55", "endBalance": -4203.9},
            {"apartmentName": "Квартира 84", "endBalance": -3644.52},
        ]
    }
    FakeClient.apartment_response = {
        "content": [
            apartment("55", "1", 2, 50),
            apartment("84", "1", 3, 100),
        ],
        "last": True,
    }

    status = cli.DahCli().run(
        args("debtors-notify --send --confirm 55 --confirm 84 --one-by-one")
    )
    streams = capsys.readouterr()

    assert status == 1
    assert "max-send is 1" in streams.err


def test_cli_auth_save_env_local(cli_env, capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    status, response, _, _ = run_cli(
        args(
            "authentication-web-login --body "
            '\'{"login":"login","password":"password"}\' --save-env-local'
        ),
        capsys,
    )

    assert (
        status,
        response["response"]["accessToken"],
        response["response"]["login"],
        response["env"],
        (tmp_path / ".env.local").read_text(encoding="utf-8"),
    ) == (
        0,
        "<redacted>",
        "<redacted>",
        {"path": ".env.local", "keys": ["DAH_BEARER_TOKEN"]},
        "DAH_BEARER_TOKEN=unit-access-token\n",
    )


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


def test_personal_group_resolver():
    resolver = cli.PersonalGroupResolver(
        PersonalGroupClient(
            {
                "id": "group-id",
                "interlocutorId": "user-id",
                "type": "PERSONAL",
                "canWriteMessage": True,
            }
        )
    )
    assert resolver.resolve("user-id") == "group-id"

    for group, message in [
        ([], "unexpected response"),
        (
            {"id": "group-id", "interlocutorId": "other"},
            "interlocutor mismatch",
        ),
        (
            {"id": "group-id", "interlocutorId": "user-id", "type": "GROUP"},
            "not PERSONAL",
        ),
        (
            {
                "id": "group-id",
                "interlocutorId": "user-id",
                "type": "PERSONAL",
                "canWriteMessage": False,
            },
            "cannot write",
        ),
        (
            {
                "interlocutorId": "user-id",
                "type": "PERSONAL",
                "canWriteMessage": True,
            },
            "missing group id",
        ),
    ]:
        with pytest.raises(SystemExit, match=message):
            cli.PersonalGroupResolver(PersonalGroupClient(group)).resolve("user-id")
