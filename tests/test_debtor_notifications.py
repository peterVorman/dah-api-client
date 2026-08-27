import pytest

from dah_api import (
    DahRequestError,
    MessengerMessageRequest,
    TenantNotificationRequest,
)
from debtor_notifications import (
    DebtorNotificationRequest,
    DebtorNotificationService,
    NotificationLedger,
    active_owner_tenant_ids,
    active_owner_user_ids,
    active_owner_users,
    apartment_kind,
    apartment_number,
    apartment_pages_finished,
    debtor_from,
    debtor_notification_table,
    debtor_notification_text,
    first_list_value,
    format_debtor_notification_report,
    format_money,
    ledger_record,
    message_apartment_label,
    missing_confirmations,
    recipient_name,
    record_apartment,
    record_debt,
    record_notification_method,
    record_recipient_scope,
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


def test_debtor_notification_owners_plus_others_scope(tmp_path):
    class CombinedRecipientClient(NotificationClient):
        def list_apartments(self, request):
            self.apartment_request = request
            return {
                "content": [
                    {
                        "number": "55",
                        "owners": [
                            {
                                "tenantId": "owner-tenant",
                                "user": {
                                    "userId": "owner-user",
                                    "userStatus": "ACTIVE",
                                },
                            }
                        ],
                        "others": [
                            {
                                "tenantId": "other-tenant",
                                "user": {
                                    "userId": "other-user",
                                    "userStatus": "ACTIVE",
                                },
                            }
                        ],
                    }
                ],
                "last": True,
            }

    client = CombinedRecipientClient()
    report = DebtorNotificationService(client).run(
        DebtorNotificationRequest(
            apartment_numbers=["55"],
            confirm_apartment_numbers=["55"],
            ledger_path=str(tmp_path / "ledger.jsonl"),
            notification_method="messenger",
            recipient_scope="owners+others",
            send=True,
        )
    )

    assert (
        report["ready"][0]["recipientScope"],
        report["ready"][0]["recipients"],
        report["sent"],
        [item.group_id for item in client.sent],
    ) == (
        "owners+others",
        2,
        [{"apartment": "55", "recipients": 2}],
        ["group-owner-user", "group-other-user"],
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


def test_debtor_notification_failed_send_records_ledger(tmp_path):
    class FailedSendClient(NotificationClient):
        def send_messenger_message(self, request):
            raise DahRequestError("send failed")

    ledger_path = tmp_path / "ledger.jsonl"
    with pytest.raises(DahRequestError, match="send failed"):
        DebtorNotificationService(FailedSendClient()).run(
            DebtorNotificationRequest(
                apartment_numbers=["55"],
                confirm_apartment_numbers=["55"],
                ledger_path=str(ledger_path),
                send=True,
            )
        )

    assert '"status": "failed"' in ledger_path.read_text(encoding="utf-8")


def test_debtor_notification_ledger_records_skipped(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    request = DebtorNotificationRequest(ledger_path=str(ledger_path))
    NotificationLedger(str(ledger_path)).record_skipped(
        request,
        [{"apartment": "84", "debt": 10, "notificationMethod": "messenger"}],
    )

    assert '"status": "skipped"' in ledger_path.read_text(encoding="utf-8")


def test_debtor_notification_manual_contact_ledger(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    record = NotificationLedger(str(ledger_path)).record_manual_contact(
        apartment_number="55",
        status="no_answer",
        debt=123.456,
        recipient_scope="owners+others",
        recipients=2,
        note="No answer.",
    )

    assert (
        record["apartment"],
        record["status"],
        record["debt"],
        record["notificationMethod"],
        record["recipientScope"],
        record["recipients"],
        record["note"],
        NotificationLedger(str(ledger_path)).records(),
    ) == (
        "55",
        "no_answer",
        123.46,
        "phone_call",
        "owners+others",
        2,
        "No answer.",
        [record],
    )


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


def test_debtor_notification_edge_helpers():
    active_user = {"userId": "u", "userStatus": "ACTIVE"}
    source = {
        "apartment": "55",
        "debt": 7,
        "notificationMethod": "tenant",
        "recipientScope": "others",
    }
    request = DebtorNotificationRequest(
        notification_method="auto",
        recipient_scope="auto",
    )

    assert (
        rows_from([{"ok": True}, "bad"]),
        first_list_value({}),
        debtor_from({"apartmentName": "", "endBalance": -1}),
        apartment_kind({"type": {"type": "PREMISE"}}),
        apartment_kind({"type": "APARTMENT"}),
        message_apartment_label("Other"),
        active_owner_tenant_ids({"owners": [{"tenantId": "t", "user": active_user}]}),
        active_owner_users({"owners": [{"user": active_user}]}),
        recipient_name("messenger", "others"),
        apartment_pages_finished([], 0),
        apartment_pages_finished({"totalPages": 1}, 0),
        ledger_record("{"),
        record_apartment(source),
        record_debt(source),
        record_notification_method(request, source),
        record_notification_method(request, {}),
        record_recipient_scope(request, source),
        record_recipient_scope(request, {}),
    ) == (
        [{"ok": True}],
        None,
        None,
        "premise",
        "apartment",
        "other",
        ["t"],
        [active_user],
        "other user",
        True,
        True,
        None,
        "55",
        7.0,
        "tenant",
        "auto",
        "others",
        "auto",
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
