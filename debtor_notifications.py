"""Debtor notification workflow for DAH messaging channels."""

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
    TenantNotificationRequest,
    default_bill_debt_analytics_payload,
)

APARTMENT_NUMBER_RE = re.compile(
    r"(?:Квартира|приміщення)\s+(\d+(?:,\d+)?(?:-\d+)?)\s*$",
    re.IGNORECASE,
)
DEFAULT_NOTIFICATION_LEDGER_PATH = ".dah-notifications.jsonl"
CONTACT_STATUSES = ("contacted", "no_answer")
NOTIFICATION_METHODS = ("messenger", "tenant", "auto")
PHONE_CALL_METHOD = "phone_call"
RECIPIENT_SCOPES = ("auto", "owners", "others", "owners+others")
PEOPLE_SCOPE_NAMES = {
    "owners": ("owners",),
    "others": ("others",),
    "owners+others": ("owners", "others"),
}
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
    notification_method: str = "auto"
    recipient_scope: str = "auto"
    send: bool = False


@dataclass(slots=True)
class DebtorNotification:
    apartment_number: str
    apartment_label: str
    debt: float
    message: str
    recipient_ids: list[str]
    notification_method: str
    recipient_scope: str
    association_id: str | None = None


class DebtorNotificationService:
    def __init__(self, client: DahApiClient) -> None:
        self.client = client

    def run(self, request: DebtorNotificationRequest) -> dict[str, Any]:
        ledger = NotificationLedger(request.ledger_path)
        apartments = self.apartment_index(request)
        debtors = self.debtors(request)
        notifications = self._build_notifications(request, apartments, debtors, ledger)
        skipped = self._skipped_debtors(request, apartments, debtors, ledger)
        validate_send_confirmation(request, notifications)
        validate_send_limit(request, notifications)
        sent = self._send_notifications(request, notifications, skipped, ledger)
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
        ledger: "NotificationLedger",
    ) -> list[DebtorNotification]:
        notifications = [
            self._notification(
                debtor,
                apartment_for_debtor(debtor, apartments),
                request,
                ledger,
            )
            for debtor in debtors
            if self._can_notify(debtor, apartments, request, ledger)
        ]
        return notifications[: request.limit] if request.limit else notifications

    def _skipped_debtors(
        self,
        request: DebtorNotificationRequest,
        apartments: dict[str, dict[str, Any]],
        debtors: list[dict[str, Any]],
        ledger: "NotificationLedger",
    ) -> list[dict[str, Any]]:
        return [
            self._skip_reason(debtor, apartments, request, ledger)
            for debtor in debtors
            if not self._can_notify(debtor, apartments, request, ledger)
        ]

    def _send(self, notification: DebtorNotification) -> dict[str, Any]:
        if notification.notification_method == "tenant":
            return self._send_tenant_notifications(notification)
        return self._send_messenger_notifications(notification)

    def _send_messenger_notifications(
        self,
        notification: DebtorNotification,
    ) -> dict[str, Any]:
        for owner_user_id in notification.recipient_ids:
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
            "recipients": len(notification.recipient_ids),
        }

    def _send_tenant_notifications(
        self,
        notification: DebtorNotification,
    ) -> dict[str, Any]:
        for tenant_id in notification.recipient_ids:
            self.client.send_tenant_notification(
                TenantNotificationRequest(
                    association_id=notification.association_id,
                    tenant_id=tenant_id,
                    text=notification.message,
                )
            )
        return {
            "apartment": notification.apartment_number,
            "recipients": len(notification.recipient_ids),
        }

    def _send_notifications(
        self,
        request: DebtorNotificationRequest,
        notifications: list[DebtorNotification],
        skipped: list[dict[str, Any]],
        ledger: "NotificationLedger",
    ) -> list[dict[str, Any]]:
        if not request.send:
            return []
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
        request: DebtorNotificationRequest,
        ledger: "NotificationLedger",
    ) -> bool:
        apartment = apartment_for_debtor(debtor, apartments)
        method, scope = notification_route_for(debtor, apartment, request, ledger)
        return bool(apartment and recipient_ids(apartment, method, scope))

    @staticmethod
    def _notification(
        debtor: dict[str, Any],
        apartment: dict[str, Any],
        request: DebtorNotificationRequest,
        ledger: "NotificationLedger",
    ) -> DebtorNotification:
        method, scope = notification_route_for(debtor, apartment, request, ledger)
        return DebtorNotification(
            apartment_number=debtor["number"],
            apartment_label=debtor["label"],
            debt=debtor["debt"],
            message=request.message_template.format(
                apartment_label=message_apartment_label(debtor["label"]),
                debt=format_money(debtor["debt"]),
            ),
            recipient_ids=recipient_ids(apartment, method, scope),
            notification_method=method,
            recipient_scope=scope,
            association_id=request.association_id,
        )

    @staticmethod
    def _preview(notification: DebtorNotification) -> dict[str, Any]:
        return {
            "apartment": notification.apartment_number,
            "debt": round(notification.debt, 2),
            "recipients": len(notification.recipient_ids),
            "notificationMethod": notification.notification_method,
            "recipientScope": notification.recipient_scope,
            "checks": notification_checks(notification.notification_method),
            "message": notification.message,
        }

    @staticmethod
    def _skip_reason(
        debtor: dict[str, Any],
        apartments: dict[str, dict[str, Any]],
        request: DebtorNotificationRequest,
        ledger: "NotificationLedger",
    ) -> dict[str, Any]:
        apartment = apartment_for_debtor(debtor, apartments)
        method, scope = notification_route_for(debtor, apartment, request, ledger)
        reason = "exact apartment match not found"
        if apartment and not recipient_ids(apartment, method, scope):
            reason = f"active {recipient_name(method, scope)} id not found"
        return {
            "apartment": debtor["number"],
            "debt": round(debtor["debt"], 2),
            "notificationMethod": method,
            "recipientScope": scope,
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
    return scoped_user_ids(apartment, "owners")


def active_owner_tenant_ids(apartment: dict[str, Any]) -> list[str]:
    return scoped_tenant_ids(apartment, "owners")


def recipient_ids(
    apartment: dict[str, Any],
    notification_method: str,
    recipient_scope: str = "owners",
) -> list[str]:
    if notification_method == "tenant":
        return scoped_tenant_ids(apartment, recipient_scope)
    return scoped_user_ids(apartment, recipient_scope)


def notification_checks(notification_method: str) -> dict[str, Any]:
    checks = {"exactApartmentFound": True, "recipientFound": True}
    if notification_method == "tenant":
        return {**checks, "tenantNotificationWritable": "checked by send"}
    return {**checks, "personalChatWritable": "checked before send"}


def notification_method_for(
    debtor: dict[str, Any],
    request: DebtorNotificationRequest,
    ledger: "NotificationLedger",
) -> str:
    if request.notification_method != "auto":
        return request.notification_method
    if debtor["number"] in ledger.messenger_notified_numbers():
        return "tenant"
    return "messenger"


def notification_route_for(
    debtor: dict[str, Any],
    apartment: dict[str, Any],
    request: DebtorNotificationRequest,
    ledger: "NotificationLedger",
) -> tuple[str, str]:
    methods = notification_methods_for(debtor, request, ledger)
    scopes = recipient_scopes_for(request)
    for method in methods:
        for scope in scopes:
            if recipient_ids(apartment, method, scope):
                return method, scope
    return methods[0], scopes[0]


def notification_methods_for(
    debtor: dict[str, Any],
    request: DebtorNotificationRequest,
    ledger: "NotificationLedger",
) -> list[str]:
    method = notification_method_for(debtor, request, ledger)
    if request.notification_method != "auto":
        return [method]
    other_method = "messenger" if method == "tenant" else "tenant"
    return [method, other_method]


def recipient_scopes_for(request: DebtorNotificationRequest) -> list[str]:
    if request.recipient_scope != "auto":
        return [request.recipient_scope]
    return ["owners", "others"]


def recipient_name(notification_method: str, recipient_scope: str) -> str:
    field_name = "tenant" if notification_method == "tenant" else "user"
    scope_name = "owner/other" if recipient_scope == "owners+others" else "owner"
    if recipient_scope == "others":
        scope_name = "other"
    return f"{scope_name} {field_name}"


def active_owner_users(apartment: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        owner["user"]
        for owner in active_owners(apartment)
        if isinstance(owner.get("user"), dict)
    ]


def active_owners(apartment: dict[str, Any]) -> list[dict[str, Any]]:
    owners = apartment.get("owners") or []
    return [
        owner
        for owner in owners
        if isinstance(owner, dict)
        if is_active_user(owner.get("user"))
    ]


def scoped_user_ids(apartment: dict[str, Any], recipient_scope: str) -> list[str]:
    user_ids = []
    for person in active_people(apartment, recipient_scope):
        user = person.get("user")
        if isinstance(user, dict):
            append_unique_user_id(user_ids, user.get("userId") or user.get("id"))
    return user_ids


def scoped_tenant_ids(apartment: dict[str, Any], recipient_scope: str) -> list[str]:
    tenant_ids = []
    for person in tenant_people(apartment, recipient_scope):
        append_unique_user_id(tenant_ids, person.get("tenantId"))
    return tenant_ids


def active_people(
    apartment: dict[str, Any],
    recipient_scope: str,
) -> list[dict[str, Any]]:
    return [
        person
        for person in scoped_people(apartment, recipient_scope)
        if is_active_user(person.get("user"))
    ]


def tenant_people(
    apartment: dict[str, Any],
    recipient_scope: str,
) -> list[dict[str, Any]]:
    if recipient_scope == "owners":
        return active_people(apartment, recipient_scope)
    return [
        person
        for person in scoped_people(apartment, recipient_scope)
        if user_active_or_missing(person)
    ]


def scoped_people(
    apartment: dict[str, Any],
    recipient_scope: str,
) -> list[dict[str, Any]]:
    return [
        person
        for scope_name in PEOPLE_SCOPE_NAMES.get(recipient_scope, ("owners",))
        for person in apartment.get(scope_name) or []
        if isinstance(person, dict)
    ]


def user_active_or_missing(person: dict[str, Any]) -> bool:
    user = person.get("user")
    return not isinstance(user, dict) or is_active_user(user)


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

    def messenger_notified_numbers(self) -> set[str]:
        return {
            record["apartment"]
            for record in self.records()
            if is_messenger_sent_record(record)
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
                    "notificationMethod": record_notification_method(request, source),
                    "recipientScope": record_recipient_scope(request, source),
                }
            )

    def record_manual_contact(
        self,
        *,
        apartment_number: str,
        status: str,
        debt: float = 0,
        recipient_scope: str = "owners",
        recipients: int = 1,
        note: str = "",
        kind: str = "apartment",
        contact_date: str | None = None,
    ) -> dict[str, Any]:
        record = manual_contact_record(
            apartment_number=apartment_number,
            status=status,
            debt=debt,
            recipient_scope=recipient_scope,
            recipients=recipients,
            note=note,
            kind=kind,
            contact_date=contact_date,
        )
        self.append(record)
        return record


def manual_contact_record(
    *,
    apartment_number: str,
    status: str,
    debt: float = 0,
    recipient_scope: str = "owners",
    recipients: int = 1,
    note: str = "",
    kind: str = "apartment",
    contact_date: str | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "date": contact_date or today_iso(),
        "apartment": apartment_number,
        "kind": kind,
        "debt": round(debt, 2),
        "status": status,
        "recipients": recipients,
        "notificationMethod": PHONE_CALL_METHOD,
        "recipientScope": recipient_scope,
    }
    if note:
        record["note"] = note
    return record


def ledger_record(line: str) -> dict[str, Any] | None:
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def is_sent_record_for_date(record: dict[str, Any], record_date: str) -> bool:
    return record.get("date") == record_date and record.get("status") == "sent"


def is_messenger_sent_record(record: dict[str, Any]) -> bool:
    return (
        record.get("status") == "sent"
        and record.get("notificationMethod", "messenger") == "messenger"
    )


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


def record_notification_method(
    request: DebtorNotificationRequest,
    source: Any,
) -> str:
    if isinstance(source, DebtorNotification):
        return source.notification_method
    if isinstance(source, dict) and isinstance(source.get("notificationMethod"), str):
        return source["notificationMethod"]
    return request.notification_method


def record_recipient_scope(
    request: DebtorNotificationRequest,
    source: Any,
) -> str:
    if isinstance(source, DebtorNotification):
        return source.recipient_scope
    if isinstance(source, dict) and isinstance(source.get("recipientScope"), str):
        return source["recipientScope"]
    return request.recipient_scope
