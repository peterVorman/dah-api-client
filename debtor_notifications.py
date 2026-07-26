"""Debtor notification workflow for DAH messenger."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from dah_api import (
    ApartmentListRequest,
    BillDebtAnalyticsRequest,
    DahApiClient,
    DahRequestError,
    MessengerMessageRequest,
    MessengerPersonalGroupRequest,
    default_bill_debt_analytics_payload,
)

APARTMENT_NUMBER_RE = re.compile(
    r"(?:Квартира|приміщення)\s+(\d+(?:,\d+)?(?:-\d+)?)\s*$",
    re.IGNORECASE,
)
DEFAULT_NOTIFICATION_LEDGER_PATH = ".dah-notifications.jsonl"
DEFAULT_DEBTOR_MESSAGE_TEMPLATE = (
    "Добрий день. За даними DAH по {apartment_label} є заборгованість "
    "{debt} грн.\n\n"
    "Просимо, будь ласка, якнайшвидше погасити борг."
)


@dataclass(slots=True)
class DebtorNotificationRequest:
    association_id: str | None = None
    date: str | None = None
    debt_filter_accruals: int = 1
    min_debt: float = 0
    limit: int | None = None
    kind: str = "all"
    apartment_numbers: list[str] = field(default_factory=list)
    confirm_apartment_numbers: list[str] = field(default_factory=list)
    exclude_notified_today: bool = False
    ledger_path: str = DEFAULT_NOTIFICATION_LEDGER_PATH
    write_ledger: bool = True
    max_send: int | None = None
    message_template: str = DEFAULT_DEBTOR_MESSAGE_TEMPLATE
    send: bool = False


@dataclass(slots=True)
class DebtorNotification:
    apartment_number: str
    apartment_label: str
    debt: float
    message: str
    owner_user_ids: list[str]


class DebtorNotificationService:
    def __init__(self, client: DahApiClient) -> None:
        self.client = client

    def run(self, request: DebtorNotificationRequest) -> dict[str, Any]:
        apartments = self.apartment_index(request)
        debtors = self.debtors(request)
        notifications = self._build_notifications(request, apartments, debtors)
        skipped = self._skipped_debtors(apartments, debtors)
        validate_send_confirmation(request, notifications)
        validate_send_limit(request, notifications)
        sent = self._send_notifications(request, notifications, skipped)
        return {
            "mode": "send" if request.send else "dry-run",
            "ready": [self._preview(notification) for notification in notifications],
            "sent": sent,
            "skipped": skipped,
        }

    def debtors(self, request: DebtorNotificationRequest) -> list[dict[str, Any]]:
        excluded = notified_apartment_numbers(request)
        selected = [d for d in self._debtors(request) if d["number"] not in excluded]
        return sorted(selected, key=lambda item: item["debt"], reverse=True)

    def apartment_index(
        self,
        request: DebtorNotificationRequest,
    ) -> dict[str, dict[str, Any]]:
        index: dict[str, dict[str, Any]] = {}
        for page in range(100):
            response = self.client.list_apartments(
                ApartmentListRequest(
                    association_id=request.association_id,
                    page=page,
                    size=100,
                )
            )
            for apartment in rows_from(response):
                if isinstance(apartment.get("number"), str):
                    index.setdefault(apartment["number"], apartment)
                    index.setdefault(apartment_key(apartment), apartment)
            if apartment_pages_finished(response, page):
                break
        return index

    def _debtors(self, request: DebtorNotificationRequest) -> list[dict[str, Any]]:
        response = self.client.get_bill_debt_analytics(
            BillDebtAnalyticsRequest(
                association_id=request.association_id,
                payload=default_bill_debt_analytics_payload(
                    date=request.date,
                    debt_filter_accruals=request.debt_filter_accruals,
                ),
            )
        )
        return [
            debtor
            for row in rows_from(response)
            if (debtor := debtor_from(row))
            if self._selected(debtor, request)
        ]

    def _build_notifications(
        self,
        request: DebtorNotificationRequest,
        apartments: dict[str, dict[str, Any]],
        debtors: list[dict[str, Any]],
    ) -> list[DebtorNotification]:
        notifications = [
            self._notification(
                debtor,
                apartment_for_debtor(debtor, apartments),
                request,
            )
            for debtor in debtors
            if self._can_notify(debtor, apartments)
        ]
        return notifications[: request.limit] if request.limit else notifications

    def _skipped_debtors(
        self,
        apartments: dict[str, dict[str, Any]],
        debtors: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return [
            self._skip_reason(debtor, apartments)
            for debtor in debtors
            if not self._can_notify(debtor, apartments)
        ]

    def _send(self, notification: DebtorNotification) -> dict[str, Any]:
        for owner_user_id in notification.owner_user_ids:
            group = self.client.get_messenger_personal_group(
                MessengerPersonalGroupRequest(owner_user_id)
            )
            validate_personal_group(group, owner_user_id)
            self.client.send_messenger_message(
                MessengerMessageRequest(
                    group_id=group["id"],
                    payload=notification.message,
                )
            )
        return {
            "apartment": notification.apartment_number,
            "recipients": len(notification.owner_user_ids),
        }

    def _send_notifications(
        self,
        request: DebtorNotificationRequest,
        notifications: list[DebtorNotification],
        skipped: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not request.send:
            return []
        ledger = NotificationLedger(request.ledger_path)
        sent = [self._send_and_record(request, ledger, item) for item in notifications]
        ledger.record_skipped(request, skipped)
        return sent

    def _send_and_record(
        self,
        request: DebtorNotificationRequest,
        ledger: "NotificationLedger",
        notification: DebtorNotification,
    ) -> dict[str, Any]:
        try:
            result = self._send(notification)
        except DahRequestError:
            ledger.record(request, notification, "failed")
            raise
        ledger.record(request, notification, "sent", result)
        return result

    @staticmethod
    def _selected(
        debtor: dict[str, Any],
        request: DebtorNotificationRequest,
    ) -> bool:
        if debtor["debt"] < request.min_debt:
            return False
        if request.kind != "all" and debtor_kind(debtor["label"]) != request.kind:
            return False
        if not request.apartment_numbers:
            return True
        return debtor["number"] in request.apartment_numbers

    @staticmethod
    def _can_notify(
        debtor: dict[str, Any],
        apartments: dict[str, dict[str, Any]],
    ) -> bool:
        apartment = apartment_for_debtor(debtor, apartments)
        return bool(apartment and active_owner_user_ids(apartment))

    @staticmethod
    def _notification(
        debtor: dict[str, Any],
        apartment: dict[str, Any],
        request: DebtorNotificationRequest,
    ) -> DebtorNotification:
        return DebtorNotification(
            apartment_number=debtor["number"],
            apartment_label=debtor["label"],
            debt=debtor["debt"],
            message=request.message_template.format(
                apartment_label=message_apartment_label(debtor["label"]),
                debt=format_money(debtor["debt"]),
            ),
            owner_user_ids=active_owner_user_ids(apartment),
        )

    @staticmethod
    def _preview(notification: DebtorNotification) -> dict[str, Any]:
        return {
            "apartment": notification.apartment_number,
            "debt": round(notification.debt, 2),
            "recipients": len(notification.owner_user_ids),
            "checks": {
                "exactApartmentFound": True,
                "activeOwnerFound": True,
                "personalChatWritable": "checked before send",
            },
            "message": notification.message,
        }

    @staticmethod
    def _skip_reason(
        debtor: dict[str, Any],
        apartments: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        apartment = apartment_for_debtor(debtor, apartments)
        reason = "exact apartment match not found"
        if apartment and not active_owner_user_ids(apartment):
            reason = "active owner user id not found"
        return {
            "apartment": debtor["number"],
            "debt": round(debtor["debt"], 2),
            "reason": reason,
        }


def rows_from(response: Any) -> list[dict[str, Any]]:
    if isinstance(response, list):
        return dict_items(response)
    if not isinstance(response, dict):
        return []
    return dict_items(first_list_value(response) or [])


def dict_items(items: list[Any]) -> list[dict[str, Any]]:
    return [item for item in items if isinstance(item, dict)]


def first_list_value(response: dict[str, Any]) -> list[Any] | None:
    for key in ("rows", "content", "items", "data"):
        value = response.get(key)
        if isinstance(value, list):
            return value
    return None


def debtor_from(row: dict[str, Any]) -> dict[str, Any] | None:
    balance = row.get("endBalance")
    name = row.get("apartmentName")
    if not isinstance(balance, (int, float)) or balance >= 0:
        return None
    if not isinstance(name, str) or not name.strip():
        return None
    return {
        "label": short_apartment_label(name),
        "number": apartment_number(name),
        "debt": abs(float(balance)),
    }


def apartment_number(name: str) -> str:
    match = APARTMENT_NUMBER_RE.search(name)
    return match.group(1) if match else name.strip()


def debtor_kind(label: str) -> str:
    return "apartment" if label.startswith("Квартира ") else "premise"


def apartment_for_debtor(
    debtor: dict[str, Any],
    apartments: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    key = f"{debtor_kind(debtor['label'])}:{debtor['number']}"
    return apartments.get(key) or apartments.get(debtor["number"], {})


def apartment_key(apartment: dict[str, Any]) -> str:
    return f"{apartment_kind(apartment)}:{apartment['number']}"


def apartment_kind(apartment: dict[str, Any]) -> str:
    type_value = apartment.get("type")
    if isinstance(type_value, dict):
        return "apartment" if type_value.get("type") == "APARTMENT" else "premise"
    if isinstance(type_value, str):
        return "apartment" if type_value == "APARTMENT" else "premise"
    return debtor_kind(str(apartment.get("name", "Квартира ")))


def short_apartment_label(name: str) -> str:
    return name.replace("Нежитлове приміщення", "Приміщення").strip()


def message_apartment_label(label: str) -> str:
    if label.startswith("Квартира "):
        return label.replace("Квартира ", "квартирі ", 1)
    if label.startswith("Приміщення "):
        return label.replace("Приміщення ", "приміщенню ", 1)
    return label.lower()


def active_owner_user_ids(apartment: dict[str, Any]) -> list[str]:
    user_ids = []
    for user in active_owner_users(apartment):
        append_unique_user_id(user_ids, user.get("userId") or user.get("id"))
    return user_ids


def active_owner_users(apartment: dict[str, Any]) -> list[dict[str, Any]]:
    owners = apartment.get("owners") or []
    return [
        user
        for owner in owners
        if isinstance(owner, dict)
        if is_active_user(user := owner.get("user"))
    ]


def is_active_user(user: Any) -> bool:
    return isinstance(user, dict) and user.get("userStatus") == "ACTIVE"


def append_unique_user_id(user_ids: list[str], user_id: Any) -> None:
    if isinstance(user_id, str) and user_id and user_id not in user_ids:
        user_ids.append(user_id)


def apartment_pages_finished(response: Any, page: int) -> bool:
    if not isinstance(response, dict):
        return True
    if response.get("last") is True:
        return True
    total_pages = response.get("totalPages")
    return isinstance(total_pages, int) and page + 1 >= total_pages


def validate_personal_group(group: Any, interlocutor_id: str) -> None:
    if not isinstance(group, dict):
        raise DahRequestError("Personal group response is not an object.")
    if group.get("interlocutorId") != interlocutor_id:
        raise DahRequestError("Personal group interlocutor mismatch.")
    if group.get("type") != "PERSONAL":
        raise DahRequestError("Personal group type mismatch.")
    if group.get("canWriteMessage") is not True:
        raise DahRequestError("Personal group is not writable.")
    validate_personal_group_id(group)


def validate_personal_group_id(group: dict[str, Any]) -> None:
    if not isinstance(group.get("id"), str) or not group["id"]:
        raise DahRequestError("Personal group id is missing.")


def format_money(value: float) -> str:
    return f"{value:,.2f}".replace(",", " ").replace(".", ",")


def validate_send_confirmation(
    request: DebtorNotificationRequest,
    notifications: list[DebtorNotification],
) -> None:
    if request.send and missing_confirmations(request, notifications):
        missing = ", ".join(missing_confirmations(request, notifications))
        raise DahRequestError(f"Missing --confirm for apartments: {missing}")


def validate_send_limit(
    request: DebtorNotificationRequest,
    notifications: list[DebtorNotification],
) -> None:
    too_many = (
        request.send
        and request.max_send is not None
        and len(notifications) > request.max_send
    )
    if too_many:
        raise DahRequestError(
            f"Refusing to send {len(notifications)} messages; "
            f"max-send is {request.max_send}."
        )


def missing_confirmations(
    request: DebtorNotificationRequest,
    notifications: list[DebtorNotification],
) -> list[str]:
    confirmed = set(request.confirm_apartment_numbers)
    apartments = [notification.apartment_number for notification in notifications]
    return [apartment for apartment in apartments if apartment not in confirmed]


def format_debtor_notification_report(
    report: dict[str, Any],
    output_format: str,
) -> Any:
    if output_format == "json":
        return report
    rows = report.get("ready", [])
    if output_format == "table":
        return debtor_notification_table(rows)
    return debtor_notification_text(report, rows)


def debtor_notification_table(rows: Any) -> str:
    if not isinstance(rows, list) or not rows:
        return "No ready debtor notifications."
    lines = ["apartment | debt | recipients", "--- | ---: | ---:"]
    lines.extend(table_row(row) for row in rows if isinstance(row, dict))
    return "\n".join(lines)


def table_row(row: dict[str, Any]) -> str:
    return (
        f"{row.get('apartment', '')} | "
        f"{format_money(float(row.get('debt', 0)))} | "
        f"{row.get('recipients', 0)}"
    )


def debtor_notification_text(report: dict[str, Any], rows: Any) -> str:
    mode = report.get("mode", "dry-run")
    if not isinstance(rows, list) or not rows:
        return f"Mode: {mode}\nNo ready debtor notifications."
    items = [text_row(row) for row in rows if isinstance(row, dict)]
    return "\n".join([f"Mode: {mode}", *items])


def text_row(row: dict[str, Any]) -> str:
    return (
        f"- {row.get('apartment', '')}: "
        f"{format_money(float(row.get('debt', 0)))} грн, "
        f"отримувачів: {row.get('recipients', 0)}"
    )


class NotificationLedger:
    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def append(self, record: dict[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            handle.write("\n")

    def notified_numbers(self, record_date: str) -> set[str]:
        return {
            record["apartment"]
            for record in self.records()
            if is_sent_record_for_date(record, record_date)
        }

    def records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            record = ledger_record(line)
            if record:
                records.append(record)
        return records

    def record_skipped(
        self,
        request: DebtorNotificationRequest,
        skipped: list[dict[str, Any]],
    ) -> None:
        for item in skipped:
            self.record(request, item, "skipped")

    def record(
        self,
        request: DebtorNotificationRequest,
        source: Any,
        status: str,
        result: dict[str, Any] | None = None,
    ) -> None:
        if request.write_ledger:
            self.append(
                {
                    "date": today_iso(),
                    "apartment": record_apartment(source),
                    "debt": record_debt(source),
                    "status": status,
                    "recipients": result.get("recipients", 0) if result else 0,
                    "debtFilterAccruals": request.debt_filter_accruals,
                }
            )


def ledger_record(line: str) -> dict[str, Any] | None:
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def is_sent_record_for_date(record: dict[str, Any], record_date: str) -> bool:
    return record.get("date") == record_date and record.get("status") == "sent"


def notified_apartment_numbers(request: DebtorNotificationRequest) -> set[str]:
    if not request.exclude_notified_today:
        return set()
    return NotificationLedger(request.ledger_path).notified_numbers(today_iso())


def today_iso() -> str:
    return date.today().isoformat()


def record_apartment(source: Any) -> str:
    if isinstance(source, DebtorNotification):
        return source.apartment_number
    return str(source.get("apartment", ""))


def record_debt(source: Any) -> float:
    if isinstance(source, DebtorNotification):
        return round(source.debt, 2)
    return float(source.get("debt", 0))
