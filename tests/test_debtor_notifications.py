import pytest

from dah_api import (
    DahRequestError,
    MessengerMessageRequest,
    TenantNotificationRequest,
)
from debtor_notifications import (
    DebtorNotificationRequest,
    DebtorNotificationService,
    active_owner_user_ids,
    apartment_number,
    debtor_from,
    debtor_notification_table,
    debtor_notification_text,
    format_debtor_notification_report,
    format_money,
    message_apartment_label,
    missing_confirmations,
    rows_from,
    short_apartment_label,
    today_iso,
    validate_personal_group,
)


class NotificationClient:
    def __init__(self):
        self.sent = []

    def get_bill_debt_analytics(self, request):
        self.debt_request = request
        return {
            "rows": [
                {"apartmentName": "Квартира 55", "endBalance": -4203.9},
                {"apartmentName": "Квартира 84", "endBalance": -3644.52},
                {"apartmentName": "Квартира 99", "endBalance": -300},
                {"apartmentName": "Квартира 20", "endBalance": 1},
            ]
        }

    def list_apartments(self, request):
        self.apartment_request = request
        return {
            "content": [
                {
                    "number": "55",
                    "owners": [
                        {
                            "user": {
                                "userId": "user-55",
                                "userStatus": "ACTIVE",
                            },
                            "tenantId": "tenant-55",
                        }
                    ],
                },
                {
                    "number": "84",
                    "owners": [
                        {
                            "user": {
                                "userId": "user-84",
                                "userStatus": "REGISTRATION",
                            }
                        }
                    ],
                },
            ],
            "last": True,
        }

    def get_messenger_personal_group(self, request):
        return {
            "id": f"group-{request.interlocutor_id}",
            "interlocutorId": request.interlocutor_id,
            "type": "PERSONAL",
            "canWriteMessage": True,
        }

    def send_messenger_message(self, request):
        assert isinstance(request, MessengerMessageRequest)
        self.sent.append(request)
        return {"ok": True}

    def send_tenant_notification(self, request):
        assert isinstance(request, TenantNotificationRequest)
        self.sent.append(request)
        return {}


def test_debtor_notification_preview_and_send(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    client = NotificationClient()
    service = DebtorNotificationService(client)
    preview = service.run(
        DebtorNotificationRequest(
            association_id="assoc-id",
            date="2026-07-24T10:00",
            min_debt=1000,
            apartment_numbers=["55", "84"],
            ledger_path=str(ledger_path),
        )
    )
    sent = service.run(
        DebtorNotificationRequest(
            apartment_numbers=["55"],
            confirm_apartment_numbers=["55"],
            ledger_path=str(ledger_path),
            send=True,
        )
    )

    assert preview == {
        "mode": "dry-run",
        "ready": [
            {
                "apartment": "55",
                "debt": 4203.9,
                "recipients": 1,
                "notificationMethod": "messenger",
                "recipientScope": "owners",
                "checks": {
                    "exactApartmentFound": True,
                    "recipientFound": True,
                    "personalChatWritable": "checked before send",
                },
                "message": (
                    "Добрий день. За даними DAH по квартирі 55 є "
                    "заборгованість 4 203,90 грн.\n\n"
                    "Просимо, будь ласка, якнайшвидше погасити борг."
                ),
            }
        ],
        "sent": [],
        "skipped": [
            {
                "apartment": "84",
                "debt": 3644.52,
                "notificationMethod": "messenger",
                "recipientScope": "owners",
                "reason": "active owner user id not found",
            }
        ],
    }
    assert (
        sent["mode"],
        sent["sent"],
        len(client.sent),
        client.sent[0].group_id,
    ) == ("send", [{"apartment": "55", "recipients": 1}], 1, "group-user-55")
    with pytest.raises(DahRequestError, match="Missing --confirm"):
        service.run(
            DebtorNotificationRequest(
                apartment_numbers=["55"],
                ledger_path=str(ledger_path),
                send=True,
            )
        )


def test_debtor_notification_tenant_method():
    client = NotificationClient()
    report = DebtorNotificationService(client).run(
        DebtorNotificationRequest(
            apartment_numbers=["55"],
            confirm_apartment_numbers=["55"],
            notification_method="tenant",
            send=True,
        )
    )

    assert (
        report["ready"][0]["notificationMethod"],
        report["ready"][0]["recipientScope"],
        report["ready"][0]["checks"],
        report["sent"],
        len(client.sent),
        client.sent[0].tenant_id,
    ) == (
        "tenant",
        "owners",
        {
            "exactApartmentFound": True,
            "recipientFound": True,
            "tenantNotificationWritable": "checked by send",
        },
        [{"apartment": "55", "recipients": 1}],
        1,
        "tenant-55",
    )


def test_debtor_notification_auto_escalates_after_messenger(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    ledger_path.write_text(
        '{"date":"2026-07-28","apartment":"55","status":"sent"}\n',
        encoding="utf-8",
    )
    client = NotificationClient()
    report = DebtorNotificationService(client).run(
        DebtorNotificationRequest(
            apartment_numbers=["55"],
            confirm_apartment_numbers=["55"],
            ledger_path=str(ledger_path),
            notification_method="auto",
            send=True,
        )
    )

    assert (
        report["ready"][0]["notificationMethod"],
        report["ready"][0]["recipientScope"],
        report["sent"],
        len(client.sent),
        client.sent[0].tenant_id,
        '"notificationMethod": "tenant"' in ledger_path.read_text(encoding="utf-8"),
    ) == (
        "tenant",
        "owners",
        [{"apartment": "55", "recipients": 1}],
        1,
        "tenant-55",
        True,
    )


def test_debtor_notification_auto_falls_back_to_others():
    class OtherRecipientClient(NotificationClient):
        def list_apartments(self, request):
            self.apartment_request = request
            return {
                "content": [
                    {
                        "number": "84",
                        "owners": [
                            {
                                "tenantId": "owner-tenant",
                                "user": {
                                    "userId": "owner-user",
                                    "userStatus": "REGISTRATION",
                                },
                            }
                        ],
                        "others": [{"tenantId": "other-tenant"}],
                    }
                ],
                "last": True,
            }

    client = OtherRecipientClient()
    report = DebtorNotificationService(client).run(
        DebtorNotificationRequest(
            apartment_numbers=["84"],
            confirm_apartment_numbers=["84"],
            send=True,
        )
    )

    assert (
        report["ready"][0]["notificationMethod"],
        report["ready"][0]["recipientScope"],
        report["sent"],
        len(client.sent),
        client.sent[0].tenant_id,
    ) == (
        "tenant",
        "others",
        [{"apartment": "84", "recipients": 1}],
        1,
        "other-tenant",
    )


def test_debtor_notification_ledger(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    client = NotificationClient()
    service = DebtorNotificationService(client)
    sent = service.run(
        DebtorNotificationRequest(
            apartment_numbers=["55"],
            confirm_apartment_numbers=["55"],
            ledger_path=str(ledger_path),
            send=True,
        )
    )
    excluded = service.run(
        DebtorNotificationRequest(
            apartment_numbers=["55"],
            exclude_notified_today=True,
            ledger_path=str(ledger_path),
        )
    )

    assert sent["sent"] == [{"apartment": "55", "recipients": 1}]
    assert excluded["ready"] == []
    assert '"apartment": "55"' in ledger_path.read_text(encoding="utf-8")
    assert f'"date": "{today_iso()}"' in ledger_path.read_text(encoding="utf-8")


def test_debtor_notification_extract_helpers():
    assert (
        rows_from({"content": [{"ok": True}, "bad"]}),
        rows_from("bad"),
        debtor_from({"apartmentName": "Нежитлове приміщення 175", "endBalance": -1}),
        debtor_from({"apartmentName": "Квартира 1", "endBalance": 1}),
        apartment_number("Квартира 119"),
        apartment_number("Нежитлове приміщення 2,11"),
        short_apartment_label("Нежитлове приміщення 175"),
        message_apartment_label("Приміщення 175"),
        active_owner_user_ids(
            {"owners": [{"user": {"id": "u", "userStatus": "ACTIVE"}}]}
        ),
        format_money(1234.5),
        missing_confirmations(DebtorNotificationRequest(), []),
    ) == (
        [{"ok": True}],
        [],
        {"label": "Приміщення 175", "number": "175", "debt": 1.0},
        None,
        "119",
        "2,11",
        "Приміщення 175",
        "приміщенню 175",
        ["u"],
        "1 234,50",
        [],
    )


def test_debtor_notification_format_helpers():
    report = {
        "mode": "dry-run",
        "ready": [{"apartment": "55", "debt": 4203.9, "recipients": 1}],
    }
    assert format_debtor_notification_report(report, "json") == report


def test_debtor_notification_table_format():
    rows = [{"apartment": "55", "debt": 4203.9, "recipients": 1}]
    assert debtor_notification_table([]) == "No ready debtor notifications."
    assert "55 | 4 203,90 | 1" in debtor_notification_table(rows)


def test_debtor_notification_text_format():
    report = {
        "mode": "dry-run",
        "ready": [{"apartment": "55", "debt": 4203.9, "recipients": 1}],
    }
    assert "Mode: dry-run" in debtor_notification_text(report, report["ready"])
    assert "No ready" in debtor_notification_text(report, [])


@pytest.mark.parametrize(
    ("group", "message"),
    [
        ([], "not an object"),
        ({"interlocutorId": "other"}, "mismatch"),
        ({"interlocutorId": "u", "type": "GROUP"}, "type"),
        ({"interlocutorId": "u", "type": "PERSONAL"}, "not writable"),
        (
            {"interlocutorId": "u", "type": "PERSONAL", "canWriteMessage": True},
            "id is missing",
        ),
    ],
)
def test_validate_personal_group_errors(group, message):
    with pytest.raises(DahRequestError, match=message):
        validate_personal_group(group, "u")
