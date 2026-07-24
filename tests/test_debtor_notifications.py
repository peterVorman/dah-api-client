import pytest

from dah_api import DahRequestError, MessengerMessageRequest
from debtor_notifications import (
    DebtorNotificationRequest,
    DebtorNotificationService,
    active_owner_user_ids,
    apartment_number,
    debtor_from,
    format_money,
    message_apartment_label,
    rows_from,
    short_apartment_label,
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
                            }
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


def test_debtor_notification_preview_and_send():
    client = NotificationClient()
    service = DebtorNotificationService(client)
    preview = service.run(
        DebtorNotificationRequest(
            association_id="assoc-id",
            date="2026-07-24T10:00",
            min_debt=1000,
            apartment_numbers=["55", "84"],
        )
    )
    sent = service.run(
        DebtorNotificationRequest(apartment_numbers=["55"], send=True)
    )

    assert preview == {
        "mode": "dry-run",
        "ready": [
            {
                "apartment": "55",
                "debt": 4203.9,
                "recipients": 1,
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


def test_debtor_notification_helpers_and_errors():
    assert (
        rows_from({"content": [{"ok": True}, "bad"]}),
        rows_from("bad"),
        debtor_from({"apartmentName": "Нежитлове приміщення 175", "endBalance": -1}),
        debtor_from({"apartmentName": "Квартира 1", "endBalance": 1}),
        apartment_number("Квартира 119"),
        short_apartment_label("Нежитлове приміщення 175"),
        message_apartment_label("Приміщення 175"),
        active_owner_user_ids(
            {"owners": [{"user": {"id": "u", "userStatus": "ACTIVE"}}]}
        ),
        format_money(1234.5),
    ) == (
        [{"ok": True}],
        [],
        {"label": "Приміщення 175", "number": "175", "debt": 1.0},
        None,
        "119",
        "Приміщення 175",
        "приміщенню 175",
        ["u"],
        "1 234,50",
    )

    for group, message in [
        ([], "not an object"),
        ({"interlocutorId": "other"}, "mismatch"),
        ({"interlocutorId": "u", "type": "GROUP"}, "type"),
        ({"interlocutorId": "u", "type": "PERSONAL"}, "not writable"),
        (
            {"interlocutorId": "u", "type": "PERSONAL", "canWriteMessage": True},
            "id is missing",
        ),
    ]:
        with pytest.raises(DahRequestError, match=message):
            validate_personal_group(group, "u")
