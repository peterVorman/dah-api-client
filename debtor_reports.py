"""Read-only debtor reports built on top of the DAH client."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from dah_api import DahApiClient, MoneyTransactionBankListRequest, SmsQuotaRequest
from debtor_data import (
    apartment_for_debtor,
    apartment_kind,
    apartment_pages_finished,
    debtor_kind,
    format_money,
    rows_from,
)
from debtor_notifications import (
    DEFAULT_NOTIFICATION_LEDGER_PATH,
    DebtorNotificationRequest,
    DebtorNotificationService,
    NotificationLedger,
)

DEFAULT_DEBT_SNAPSHOT_PATH = ".dah-debt-snapshots.jsonl"
DEFAULT_DEBT_DASHBOARD_PATH = ".dah-debt-dashboard.jsonl"
DEFAULT_SMS_QUOTA_WARNING_THRESHOLD = 20
DASHBOARD_RECORD_TYPE = "dashboard"
NO_ENTRANCE = "Без підʼїзду"
NO_FLOOR = "Без поверху"
ENTRANCE_KEYS = ("entrance", "entranceNumber", "section", "sectionNumber")
FLOOR_KEYS = ("floor", "floorNumber", "storey")
AREA_KEYS = (
    "area",
    "totalArea",
    "square",
    "squareTotal",
    "apartmentArea",
    "size",
)
ACCOUNT_KEYS = ("pan", "personalAccount", "accountNumber", "account")
MONEY_KEYS = ("amount", "sum", "value", "operationSum", "total")
NUMERIC_DELTA_KEYS = ("count", "debt", "area", "debtPerArea")
COMMUNICATION_DELTA_KEYS = (
    "events",
    "sent",
    "contacted",
    "noAnswer",
    "recipients",
)
CHANNEL_METRIC_KEYS = COMMUNICATION_DELTA_KEYS
EMPTY_CHANNEL_METRICS = {
    "sent": 0,
    "contacted": 0,
    "noAnswer": 0,
}
CHANNEL_STATUS_METRICS = {
    "sent": {"sent": 1},
    "contacted": {"contacted": 1},
    "no_answer": {"noAnswer": 1},
}
STAGE_DELTA_KEYS = ("count", "debt")
STAGE_BY_STATUS = {
    "sent": "notified",
    "contacted": "contacted",
    "no_answer": "no_answer",
    "failed": "unreachable",
    "skipped": "unreachable",
}
STAGE_ORDER = ("new", "notified", "contacted", "no_answer", "unreachable", "unknown")
TRANSACTION_DATE_KEYS = ("date", "transactionDate", "operationDate", "createTime")


@dataclass(slots=True)
class DebtorNextRequest:
    association_id: str | None = None
    date: str | None = None
    debt_filter_accruals: int = 1
    min_debt: float = 0
    limit: int | None = 15
    kind: str = "apartment"
    exclude_notified_today: bool = False
    ledger_path: str = DEFAULT_NOTIFICATION_LEDGER_PATH
    output_format: str = "json"
    notification_method: str = "auto"
    recipient_scope: str = "auto"


@dataclass(slots=True)
class DebtorStructureRequest:
    association_id: str | None = None
    date: str | None = None
    debt_filter_accruals: int = 1
    min_debt: float = 0
    kind: str = "apartment"
    area_adjusted: bool = False


@dataclass(slots=True)
class DebtorAuditRequest:
    apartment_number: str
    from_date: str
    association_id: str | None = None
    date: str | None = None
    debt_filter_accruals: int = 1
    kind: str = "apartment"
    ledger_path: str = DEFAULT_NOTIFICATION_LEDGER_PATH


@dataclass(slots=True)
class DebtSnapshotRequest:
    association_id: str | None = None
    date: str | None = None
    debt_filter_accruals: int = 1
    min_debt: float = 0
    kind: str = "all"
    snapshot_path: str = DEFAULT_DEBT_SNAPSHOT_PATH
    write_snapshot: bool = False


@dataclass(slots=True)
class DebtDashboardRequest:
    association_id: str | None = None
    date: str | None = None
    debt_filter_accruals: int = 2
    min_debt: float = 0
    ledger_path: str = DEFAULT_NOTIFICATION_LEDGER_PATH
    dashboard_path: str = DEFAULT_DEBT_DASHBOARD_PATH
    write_snapshot: bool = False
    sms_quota_warning_threshold: int = DEFAULT_SMS_QUOTA_WARNING_THRESHOLD


class DebtorReportService:
    def __init__(self, client: DahApiClient) -> None:
        self.client = client

    def next_to_notify(self, request: DebtorNextRequest) -> Any:
        report = DebtorNotificationService(self.client).run(
            DebtorNotificationRequest(
                association_id=request.association_id,
                date=request.date,
                debt_filter_accruals=request.debt_filter_accruals,
                min_debt=request.min_debt,
                limit=request.limit,
                kind=request.kind,
                exclude_notified_today=request.exclude_notified_today,
                ledger_path=request.ledger_path,
                notification_method=request.notification_method,
                recipient_scope=request.recipient_scope,
            )
        )
        rows = [
            {
                "apartment": row["apartment"],
                "debt": row["debt"],
                "recipients": row["recipients"],
                "notificationMethod": row["notificationMethod"],
                "recipientScope": row["recipientScope"],
            }
            for row in report["ready"]
        ]
        if request.output_format == "json":
            return {"items": rows, "skipped": report["skipped"]}
        if request.output_format == "table":
            return format_next_rows(rows, table=True)
        return format_next_rows(rows, table=False)

    def by_entrance(self, request: DebtorStructureRequest) -> dict[str, Any]:
        notification_request = DebtorNotificationRequest(
            association_id=request.association_id,
            date=request.date,
            debt_filter_accruals=request.debt_filter_accruals,
            min_debt=request.min_debt,
            kind=request.kind,
        )
        service = DebtorNotificationService(self.client)
        apartments = service.apartment_index(notification_request)
        debtors = service.debtors(notification_request)
        entries = debt_entries(debtors, apartments)
        area_entries = denominator_entries(apartments, request.kind)
        entrances = entrance_summaries(entries, area_entries, request.area_adjusted)
        return {
            "summary": summarize(entries, area_entries, request.area_adjusted),
            "entrances": sorted_groups(entrances, request.area_adjusted),
        }

    def audit(self, request: DebtorAuditRequest) -> dict[str, Any]:
        notification_request = DebtorNotificationRequest(
            association_id=request.association_id,
            date=request.date,
            debt_filter_accruals=request.debt_filter_accruals,
            apartment_numbers=[request.apartment_number],
            kind=request.kind,
        )
        service = DebtorNotificationService(self.client)
        apartments = service.apartment_index(notification_request)
        debtor = first_item(service.debtors(notification_request))
        apartment = exact_apartment(apartments, request) or apartment_for_debtor(
            debtor or {"label": "", "number": request.apartment_number},
            apartments,
        )
        records = ledger_records(request.ledger_path, request.apartment_number)
        payments = attributed_payments(self.client, request, apartment)
        return {
            "apartment": request.apartment_number,
            "kind": request.kind,
            "currentDebt": round(float(debtor["debt"]), 2) if debtor else 0.0,
            "meta": apartment_meta(apartment),
            "ledger": communication_summary(records),
            "payments": payments,
            "paymentTotal": round(sum(float(item["amount"]) for item in payments), 2),
        }

    def snapshot(self, request: DebtSnapshotRequest) -> dict[str, Any]:
        notification_request = DebtorNotificationRequest(
            association_id=request.association_id,
            date=request.date,
            debt_filter_accruals=request.debt_filter_accruals,
            min_debt=request.min_debt,
            kind=request.kind,
        )
        service = DebtorNotificationService(self.client)
        apartments = service.apartment_index(notification_request)
        debtors = service.debtors(notification_request)
        entries = debt_entries(debtors, apartments)
        area_entries = denominator_entries(apartments, request.kind)
        current = snapshot_payload(request, entries, area_entries)
        store = DebtSnapshotStore(request.snapshot_path)
        previous = store.latest_compatible(current)
        if request.write_snapshot:
            store.append(current)
        return {
            "current": current,
            "previous": previous,
            "delta": snapshot_delta(current, previous),
        }

    def dashboard(self, request: DebtDashboardRequest) -> dict[str, Any]:
        notification_request = DebtorNotificationRequest(
            association_id=request.association_id,
            date=request.date,
            debt_filter_accruals=request.debt_filter_accruals,
            min_debt=request.min_debt,
            kind="all",
        )
        service = DebtorNotificationService(self.client)
        apartments = service.apartment_index(notification_request)
        entries = debt_entries(service.debtors(notification_request), apartments)
        area_entries = denominator_entries(apartments, "all")
        current = dashboard_payload(
            request,
            entries,
            area_entries,
            NotificationLedger(request.ledger_path).records(),
            sms_quota_summary(
                self.client.get_sms_quota(
                    SmsQuotaRequest(
                        association_id=request.association_id,
                        refresh=True,
                    )
                ),
                request.sms_quota_warning_threshold,
            ),
        )
        store = DebtSnapshotStore(request.dashboard_path)
        previous = store.latest_before_day(current)
        if request.write_snapshot:
            store.append(current)
        return {
            "current": current,
            "previous": previous,
            "delta": dashboard_delta(current, previous),
        }


class DebtSnapshotStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def append(self, record: dict[str, Any]) -> None:
        prefix = "\n" if self._needs_leading_newline() else ""
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(prefix)
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            handle.write("\n")

    def latest_compatible(self, current: dict[str, Any]) -> dict[str, Any] | None:
        return next(
            (
                record
                for record in reversed(self.records())
                if snapshot_compatible(current, record)
            ),
            None,
        )

    def latest_before_day(self, current: dict[str, Any]) -> dict[str, Any] | None:
        current_day = snapshot_day(current)
        return next(
            (
                record
                for record in reversed(self.records())
                if snapshot_compatible(current, record)
                and snapshot_day(record) < current_day
            ),
            None,
        )

    def records(self) -> list[dict[str, Any]]:
        return [
            value
            for line in self._lines()
            if isinstance(value := json_record(line), dict)
        ]

    def _lines(self) -> list[str]:
        if not self.path.exists():
            return []
        return self.path.read_text(encoding="utf-8").splitlines()

    def _needs_leading_newline(self) -> bool:
        return (
            self.path.exists()
            and self.path.stat().st_size > 0
            and not self.path.read_text(encoding="utf-8").endswith("\n")
        )


def format_next_rows(rows: list[dict[str, Any]], *, table: bool) -> str:
    if not rows:
        return "No ready debtors to notify."
    prefix = ["apartment | debt | recipients", "--- | ---: | ---:"] if table else []
    return "\n".join([*prefix, *(next_row(row, table) for row in rows)])


def next_row(row: dict[str, Any], table: bool) -> str:
    debt = format_money(float(row["debt"]))
    if table:
        return f"{row['apartment']} | {debt} | {row['recipients']}"
    return (
        f"- Квартира {row['apartment']}: {debt} грн, отримувачів: {row['recipients']}"
    )


def first_item(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    return items[0] if items else None


def exact_apartment(
    apartments: dict[str, dict[str, Any]],
    request: DebtorAuditRequest,
) -> dict[str, Any]:
    return apartments.get(
        f"{request.kind}:{request.apartment_number}"
    ) or apartments.get(
        request.apartment_number,
        {},
    )


def apartment_meta(apartment: dict[str, Any]) -> dict[str, Any]:
    return {
        "entrance": entrance_text(apartment),
        "floor": floor_text(apartment),
        "area": field_number(apartment, AREA_KEYS),
    }


def communication_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    dates = sorted(
        {str(record.get("date", "")) for record in records if record.get("date")}
    )
    return {
        "records": len(records),
        "uniqueDates": dates,
        "sent": count_status(records, "sent"),
        "contacted": count_status(records, "contacted"),
        "noAnswer": count_status(records, "no_answer"),
        "byMethod": count_by(records, "notificationMethod"),
    }


def ledger_records(path: str, apartment_number: str) -> list[dict[str, Any]]:
    return [
        record
        for record in NotificationLedger(path).records()
        if record.get("apartment") == apartment_number
    ]


def count_status(records: list[dict[str, Any]], status: str) -> int:
    return sum(1 for record in records if record.get("status") == status)


def count_by(records: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        value = record.get(key) or (
            "messenger" if key == "notificationMethod" else "unknown"
        )
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def attributed_payments(
    client: DahApiClient,
    request: DebtorAuditRequest,
    apartment: dict[str, Any],
) -> list[dict[str, Any]]:
    payments = []
    markers = payment_markers(request, apartment)
    for page in range(100):
        response = client.list_money_transaction_bank(
            MoneyTransactionBankListRequest(
                association_id=request.association_id,
                page=page,
                size=100,
                payload={"direction": "INCOME", "from": request.from_date},
            )
        )
        payments.extend(
            payment_entry(row)
            for row in rows_from(response)
            if payment_matches(row, markers)
        )
        if apartment_pages_finished(response, page):
            break
    return payments


def payment_markers(
    request: DebtorAuditRequest,
    apartment: dict[str, Any],
) -> list[str]:
    number = request.apartment_number
    labels = (
        [f"Квартира {number}"]
        if request.kind == "apartment"
        else [f"Приміщення {number}", f"Нежитлове приміщення {number}"]
    )
    return [normalize_text(marker) for marker in [*labels, *account_markers(apartment)]]


def account_markers(apartment: dict[str, Any]) -> list[str]:
    markers = []
    for key in ACCOUNT_KEYS:
        value = apartment.get(key)
        if isinstance(value, (int, float)):
            markers.append(str(int(value)))
        else:
            markers.extend(string_values(value))
    return [marker for marker in markers if len(marker) >= 4]


def payment_matches(row: dict[str, Any], markers: list[str]) -> bool:
    texts = [normalize_text(text) for text in string_values(row)]
    return any(marker in text for marker in markers for text in texts)


def payment_entry(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": transaction_date(row),
        "amount": round(transaction_amount(row), 2),
    }


def transaction_date(row: dict[str, Any]) -> str | None:
    value = field_value(row, TRANSACTION_DATE_KEYS)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000).isoformat(timespec="seconds")
    return str(value) if value not in (None, "") else None


def transaction_amount(row: dict[str, Any]) -> float:
    value = field_value(row, MONEY_KEYS)
    return abs(number_value(value) or 0)


def number_value(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(" ", "").replace("\xa0", "").replace(",", "."))
        except ValueError:
            return None
    return None


def normalize_text(text: str) -> str:
    return " ".join(text.casefold().split())


def string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return nested_string_values(value.values())
    if isinstance(value, list):
        return nested_string_values(value)
    return []


def nested_string_values(values: Any) -> list[str]:
    return [text for item in values for text in string_values(item)]


def json_record(line: str) -> dict[str, Any] | None:
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def snapshot_payload(
    request: DebtSnapshotRequest,
    entries: list[dict[str, Any]],
    area_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    entrances = entrance_summaries(entries, area_entries, area_adjusted=True)
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "reportDate": request.date,
        "debtFilterAccruals": request.debt_filter_accruals,
        "minDebt": request.min_debt,
        "kind": request.kind,
        "summary": summarize(entries, area_entries, area_adjusted=True),
        "entrances": sorted_groups(entrances, area_adjusted=True),
    }


def dashboard_payload(
    request: DebtDashboardRequest,
    entries: list[dict[str, Any]],
    area_entries: list[dict[str, Any]],
    records: list[dict[str, Any]],
    sms_quota: dict[str, Any],
) -> dict[str, Any]:
    created_at = datetime.now().isoformat(timespec="seconds")
    snapshot_date = dashboard_snapshot_date(request.date, created_at)
    records = records_through_day(records, snapshot_date)
    return {
        "recordType": DASHBOARD_RECORD_TYPE,
        "createdAt": created_at,
        "snapshotDate": snapshot_date,
        "reportDate": request.date,
        "kind": "all",
        "debtFilterAccruals": request.debt_filter_accruals,
        "minDebt": request.min_debt,
        "summary": summarize(entries, area_entries, area_adjusted=True),
        "byKind": kind_summaries(entries, area_entries),
        "entrances": sorted_groups(
            entrance_summaries(entries, area_entries, area_adjusted=True),
            area_adjusted=True,
        ),
        "communications": dashboard_communications(records, snapshot_date),
        "stages": stage_summaries(entries, records),
        "smsQuota": sms_quota,
    }


def sms_quota_summary(
    quota: dict[str, Any],
    warning_threshold: int,
) -> dict[str, Any]:
    remaining = quota["remaining"].get("smsCount")
    enabled = quota["enabled"]
    if not enabled:
        status = "disabled"
    elif remaining is None:
        status = "unavailable"
    elif remaining < warning_threshold:
        status = "below_threshold"
    else:
        status = "ok"
    return {
        "enabled": enabled,
        "remaining": remaining,
        "warningThreshold": warning_threshold,
        "status": status,
        "warning": status != "ok",
    }


def dashboard_snapshot_date(report_date: str | None, created_at: str) -> str:
    return str(report_date or created_at)[:10]


def records_through_day(
    records: list[dict[str, Any]],
    snapshot_date: str,
) -> list[dict[str, Any]]:
    return [
        record
        for record in records
        if ledger_record_day(record) and ledger_record_day(record) <= snapshot_date
    ]


def dashboard_communications(
    records: list[dict[str, Any]],
    snapshot_date: str,
) -> dict[str, list[dict[str, Any]]]:
    return {
        "total": channel_summaries(records),
        "today": channel_summaries(
            [record for record in records if ledger_record_day(record) == snapshot_date]
        ),
    }


def snapshot_delta(
    current: dict[str, Any],
    previous: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not previous:
        return None
    return {
        "summary": numeric_delta(
            current.get("summary", {}),
            previous.get("summary", {}),
        ),
        "entrances": entrance_delta(current, previous),
    }


def dashboard_delta(
    current: dict[str, Any],
    previous: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not previous:
        return None
    current_communications = current.get("communications", {})
    previous_communications = previous.get("communications", {})
    return {
        "summary": numeric_delta(
            current.get("summary", {}), previous.get("summary", {})
        ),
        "byKind": group_delta(
            current.get("byKind", []),
            previous.get("byKind", []),
            "kind",
            NUMERIC_DELTA_KEYS,
        ),
        "entrances": group_delta(
            current.get("entrances", []),
            previous.get("entrances", []),
            "entrance",
            NUMERIC_DELTA_KEYS,
        ),
        "communications": group_delta(
            current_communications.get("total", []),
            previous_communications.get("total", []),
            "channel",
            COMMUNICATION_DELTA_KEYS,
        ),
        "stages": group_delta(
            current.get("stages", []),
            previous.get("stages", []),
            "stage",
            STAGE_DELTA_KEYS,
        ),
    }


def snapshot_compatible(current: dict[str, Any], previous: dict[str, Any]) -> bool:
    return all(
        current.get(key) == previous.get(key)
        for key in ("recordType", "kind", "debtFilterAccruals", "minDebt")
    )


def snapshot_day(record: dict[str, Any]) -> str:
    value = (
        record.get("snapshotDate")
        or record.get("reportDate")
        or record.get("createdAt")
    )
    return str(value or "")[:10]


def entrance_delta(
    current: dict[str, Any],
    previous: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = entrance_delta_rows(
        current.get("entrances", []),
        rows_by_key(previous.get("entrances", []), "entrance"),
    )
    return sorted(
        rows, key=lambda row: abs(float(row.get("debtDelta", 0))), reverse=True
    )


def entrance_delta_rows(
    rows: Any,
    previous_rows: dict[Any, dict[str, Any]],
) -> list[dict[str, Any]]:
    return group_delta(
        rows, list(previous_rows.values()), "entrance", NUMERIC_DELTA_KEYS
    )


def rows_by_key(rows: Any, key: str) -> dict[Any, dict[str, Any]]:
    return {row.get(key): row for row in dict_rows(rows)}


def dict_rows(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def numeric_delta(
    current: Any,
    previous: Any,
    numeric_keys: tuple[str, ...] = NUMERIC_DELTA_KEYS,
) -> dict[str, float]:
    if not dict_pair(current, previous):
        return {}
    return {
        f"{key}Delta": delta_value(current, previous, key)
        for key in delta_keys(current, previous, numeric_keys)
    }


def dict_pair(current: Any, previous: Any) -> bool:
    return isinstance(current, dict) and isinstance(previous, dict)


def delta_keys(
    current: dict[str, Any],
    previous: dict[str, Any],
    numeric_keys: tuple[str, ...],
) -> list[str]:
    return [key for key in numeric_keys if key in current or key in previous]


def delta_value(current: dict[str, Any], previous: dict[str, Any], key: str) -> float:
    return round(float(current.get(key) or 0) - float(previous.get(key) or 0), 2)


def debt_entries(
    debtors: list[dict[str, Any]],
    apartments: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        debt_entry(debtor, apartment_for_debtor(debtor, apartments))
        for debtor in debtors
    ]


def denominator_entries(
    apartments: dict[str, dict[str, Any]],
    kind: str,
) -> list[dict[str, Any]]:
    return [
        area_entry(apartment)
        for apartment in unique_apartments(apartments)
        if kind == "all" or apartment_kind(apartment) == kind
    ]


def entrance_summaries(
    entries: list[dict[str, Any]],
    area_entries: list[dict[str, Any]],
    area_adjusted: bool,
) -> list[dict[str, Any]]:
    area_groups = grouped_by(area_entries, "entrance")
    return [
        entrance_summary(
            entrance,
            rows,
            area_groups.get(entrance, []),
            area_adjusted,
        )
        for entrance, rows in grouped_by(entries, "entrance").items()
    ]


def debt_entry(
    debtor: dict[str, Any],
    apartment: dict[str, Any],
) -> dict[str, Any]:
    return {
        "label": debtor["label"],
        "number": debtor["number"],
        "kind": debtor_kind(debtor["label"]),
        "debt": debtor["debt"],
        "entrance": entrance_text(apartment),
        "floor": floor_text(apartment),
        "area": field_number(apartment, AREA_KEYS),
    }


def area_entry(apartment: dict[str, Any]) -> dict[str, Any]:
    return {
        "debt": 0.0,
        "kind": apartment_kind(apartment),
        "entrance": entrance_text(apartment),
        "floor": floor_text(apartment),
        "area": field_number(apartment, AREA_KEYS),
    }


def entrance_summary(
    entrance: str,
    debt_entries: list[dict[str, Any]],
    area_entries: list[dict[str, Any]],
    area_adjusted: bool,
) -> dict[str, Any]:
    floors = [
        {
            "floor": floor,
            **summarize(
                rows,
                grouped_by(area_entries, "floor").get(floor, []),
                area_adjusted,
            ),
        }
        for floor, rows in grouped_by(debt_entries, "floor").items()
    ]
    return {
        **summarize(debt_entries, area_entries, area_adjusted),
        "entrance": entrance,
        "floors": sorted_groups(floors, area_adjusted),
    }


def kind_summaries(
    entries: list[dict[str, Any]],
    area_entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        kind_summary(entries, area_entries, kind) for kind in ("apartment", "premise")
    ]


def kind_summary(
    entries: list[dict[str, Any]],
    area_entries: list[dict[str, Any]],
    kind: str,
) -> dict[str, Any]:
    return {
        "kind": kind,
        **summarize(
            [entry for entry in entries if entry["kind"] == kind],
            [entry for entry in area_entries if entry["kind"] == kind],
            area_adjusted=True,
        ),
    }


def grouped_by(
    entries: list[dict[str, Any]],
    key: str,
) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        groups.setdefault(str(entry[key]), []).append(entry)
    return dict(sorted(groups.items()))


def channel_summaries(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups = grouped_by([channel_entry(record) for record in records], "channel")
    return [channel_summary(channel, rows) for channel, rows in groups.items()]


def channel_entry(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "channel": str(record.get("notificationMethod") or "messenger"),
        "events": 1,
        "recipients": int(number_value(record.get("recipients")) or 0),
        **EMPTY_CHANNEL_METRICS,
        **CHANNEL_STATUS_METRICS.get(str(record.get("status", "")), {}),
    }


def channel_summary(channel: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "channel": channel,
        **{
            metric: sum(int(row[metric]) for row in rows)
            for metric in CHANNEL_METRIC_KEYS
        },
    }


def stage_summaries(
    entries: list[dict[str, Any]],
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entries_by_key = {debt_entry_key(entry): entry for entry in entries}
    keys_by_number = grouped_by(list(entries_by_key.values()), "number")
    stages = last_stage_by_key(records, keys_by_number)
    ambiguous_keys = ambiguous_stage_keys(records, keys_by_number)
    groups = grouped_by(
        [
            entry_with_stage(key, entry, stages, ambiguous_keys)
            for key, entry in entries_by_key.items()
        ],
        "stage",
    )
    return [
        stage_summary(stage, rows)
        for stage, rows in sorted(
            groups.items(), key=lambda item: STAGE_ORDER.index(item[0])
        )
    ]


def last_stage_by_key(
    records: list[dict[str, Any]],
    keys_by_number: dict[str, list[dict[str, Any]]],
) -> dict[str, str]:
    return {
        entry["key"]: entry["stage"]
        for record in records
        if (entry := stage_record_entry(record, keys_by_number))
    }


def ambiguous_stage_keys(
    records: list[dict[str, Any]],
    keys_by_number: dict[str, list[dict[str, Any]]],
) -> set[str]:
    return {
        debt_entry_key(entry)
        for record in records
        for entry in ambiguous_stage_entries(record, keys_by_number)
    }


def stage_record_entry(
    record: dict[str, Any],
    keys_by_number: dict[str, list[dict[str, Any]]],
) -> dict[str, str] | None:
    stage = STAGE_BY_STATUS.get(str(record.get("status", "")))
    key = ledger_entry_key(record, keys_by_number)
    if not key or not stage:
        return None
    return {"key": key, "stage": stage}


def ambiguous_stage_entries(
    record: dict[str, Any],
    keys_by_number: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    number = str(record.get("apartment", ""))
    matches = keys_by_number.get(number, [])
    is_ambiguous = not record.get("kind") and len(matches) > 1
    has_stage = str(record.get("status", "")) in STAGE_BY_STATUS
    return matches if is_ambiguous and has_stage else []


def entry_with_stage(
    key: str,
    entry: dict[str, Any],
    stages: dict[str, str],
    ambiguous_keys: set[str],
) -> dict[str, Any]:
    return {
        **entry,
        "stage": stages.get(key, "unknown" if key in ambiguous_keys else "new"),
    }


def stage_summary(stage: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "stage": stage,
        "count": len(rows),
        "debt": round(sum(float(row["debt"]) for row in rows), 2),
    }


def debt_entry_key(entry: dict[str, Any]) -> str:
    return f"{entry['kind']}:{entry['number']}"


def ledger_entry_key(
    record: dict[str, Any],
    entries_by_number: dict[str, list[dict[str, Any]]],
) -> str | None:
    number = str(record.get("apartment", ""))
    kind = record.get("kind")
    if kind in {"apartment", "premise"}:
        return f"{kind}:{number}"
    matches = entries_by_number.get(number, [])
    return debt_entry_key(matches[0]) if len(matches) == 1 else None


def ledger_record_day(record: dict[str, Any]) -> str:
    return str(record.get("date", ""))[:10]


def group_delta(
    current_rows: Any,
    previous_rows: Any,
    key: str,
    numeric_keys: tuple[str, ...],
) -> list[dict[str, Any]]:
    current_by_key = rows_by_key(current_rows, key)
    previous_by_key = rows_by_key(previous_rows, key)
    rows = [
        {
            key: value,
            **numeric_delta(
                current_by_key.get(value, {}),
                previous_by_key.get(value, {}),
                numeric_keys,
            ),
        }
        for value in sorted(set(current_by_key) | set(previous_by_key))
    ]
    return sorted(
        rows,
        key=lambda row: max(
            abs(float(row.get(f"{metric}Delta", 0))) for metric in numeric_keys
        ),
        reverse=True,
    )


def summarize(
    debt_entries: list[dict[str, Any]],
    area_entries: list[dict[str, Any]],
    area_adjusted: bool,
) -> dict[str, Any]:
    debt = round(sum(float(entry["debt"]) for entry in debt_entries), 2)
    area = round(sum(float(entry["area"] or 0) for entry in area_entries), 2)
    summary = {"count": len(debt_entries), "debt": debt, "area": area}
    return with_area_adjustment(summary, area_adjusted)


def with_area_adjustment(
    summary: dict[str, Any],
    area_adjusted: bool,
) -> dict[str, Any]:
    if area_adjusted:
        area = float(summary["area"])
        summary["debtPerArea"] = (
            round(float(summary["debt"]) / area, 2) if area else None
        )
    return summary


def sorted_groups(
    groups: list[dict[str, Any]],
    area_adjusted: bool,
) -> list[dict[str, Any]]:
    sort_key = "debtPerArea" if area_adjusted else "debt"
    return sorted(
        groups,
        key=lambda group: float(group.get(sort_key) or 0),
        reverse=True,
    )


def unique_apartments(apartments: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    unique = {}
    for apartment in apartments.values():
        unique.setdefault(
            apartment.get("id") or apartment_key_value(apartment),
            apartment,
        )
    return list(unique.values())


def apartment_key_value(apartment: dict[str, Any]) -> str:
    return f"{apartment_kind(apartment)}:{apartment.get('number', '')}"


def entrance_text(apartment: dict[str, Any]) -> str:
    value = field_text(apartment, ENTRANCE_KEYS)
    return value if value != "unknown" else NO_ENTRANCE


def floor_text(apartment: dict[str, Any]) -> str:
    value = field_text(apartment, FLOOR_KEYS)
    return value if value != "unknown" else NO_FLOOR


def field_text(apartment: dict[str, Any], keys: tuple[str, ...]) -> str:
    value = field_value(apartment, keys)
    if isinstance(value, dict):
        value = value.get("name")
    return str(value).strip() if value not in (None, "") else "unknown"


def field_number(apartment: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    value = field_value(apartment, keys)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.replace(".", "", 1).isdigit():
        return float(value)
    return None


def field_value(apartment: dict[str, Any], keys: tuple[str, ...]) -> Any:
    return next((apartment[key] for key in keys if key in apartment), None)
