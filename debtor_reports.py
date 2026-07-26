"""Read-only debtor reports built on top of the DAH client."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dah_api import DahApiClient
from debtor_notifications import (
    DEFAULT_NOTIFICATION_LEDGER_PATH,
    DebtorNotificationRequest,
    DebtorNotificationService,
    debtor_kind,
    format_money,
)

ENTRANCE_KEYS = ("entrance", "entranceNumber", "section", "sectionNumber")
FLOOR_KEYS = ("floor", "floorNumber", "storey")
AREA_KEYS = ("area", "totalArea", "square", "squareTotal", "apartmentArea")


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


@dataclass(slots=True)
class DebtorStructureRequest:
    association_id: str | None = None
    date: str | None = None
    debt_filter_accruals: int = 1
    min_debt: float = 0
    kind: str = "apartment"
    area_adjusted: bool = False


class DebtorReportService:
    def __init__(self, client: DahApiClient) -> None:
        self.client = client

    def next_to_notify(self, request: DebtorNextRequest) -> Any:
        notification_request = debtor_notification_request(request)
        report = DebtorNotificationService(self.client).run(notification_request)
        rows = next_rows(report)
        if request.output_format == "json":
            return {"items": rows, "skipped": report["skipped"]}
        if request.output_format == "table":
            return next_table(rows)
        return next_text(rows)

    def by_entrance(self, request: DebtorStructureRequest) -> dict[str, Any]:
        notification_request = debtor_structure_notification_request(request)
        service = DebtorNotificationService(self.client)
        apartments = service.apartment_index(notification_request)
        debtors = service.debtors(notification_request)
        entries = structure_entries(debtors, apartments)
        grouped = grouped_structure(entries, request.area_adjusted)
        return {
            "summary": structure_summary(entries, request.area_adjusted),
            "entrances": grouped,
        }


def debtor_notification_request(
    request: DebtorNextRequest,
) -> DebtorNotificationRequest:
    return DebtorNotificationRequest(
        association_id=request.association_id,
        date=request.date,
        debt_filter_accruals=request.debt_filter_accruals,
        min_debt=request.min_debt,
        limit=request.limit,
        kind=request.kind,
        exclude_notified_today=request.exclude_notified_today,
        ledger_path=request.ledger_path,
    )


def debtor_structure_notification_request(
    request: DebtorStructureRequest,
) -> DebtorNotificationRequest:
    return DebtorNotificationRequest(
        association_id=request.association_id,
        date=request.date,
        debt_filter_accruals=request.debt_filter_accruals,
        min_debt=request.min_debt,
        kind=request.kind,
    )


def next_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "apartment": row["apartment"],
            "debt": row["debt"],
            "recipients": row["recipients"],
        }
        for row in report["ready"]
    ]


def next_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No ready debtors to notify."
    lines = ["apartment | debt | recipients", "--- | ---: | ---:"]
    lines.extend(next_table_row(row) for row in rows)
    return "\n".join(lines)


def next_table_row(row: dict[str, Any]) -> str:
    return (
        f"{row['apartment']} | {format_money(float(row['debt']))} | "
        f"{row['recipients']}"
    )


def next_text(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No ready debtors to notify."
    return "\n".join(next_text_row(row) for row in rows)


def next_text_row(row: dict[str, Any]) -> str:
    return (
        f"- Квартира {row['apartment']}: "
        f"{format_money(float(row['debt']))} грн, "
        f"отримувачів: {row['recipients']}"
    )


def structure_entries(
    debtors: list[dict[str, Any]],
    apartments: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        structure_entry(debtor, apartments.get(debtor["number"], {}))
        for debtor in debtors
    ]


def structure_entry(
    debtor: dict[str, Any],
    apartment: dict[str, Any],
) -> dict[str, Any]:
    return {
        "label": debtor["label"],
        "kind": debtor_kind(debtor["label"]),
        "debt": debtor["debt"],
        "entrance": field_text(apartment, ENTRANCE_KEYS),
        "floor": field_text(apartment, FLOOR_KEYS),
        "area": field_number(apartment, AREA_KEYS),
    }


def grouped_structure(
    entries: list[dict[str, Any]],
    area_adjusted: bool,
) -> list[dict[str, Any]]:
    entrances = sorted({entry["entrance"] for entry in entries})
    groups = [
        entrance_group(entries, entrance, area_adjusted)
        for entrance in entrances
    ]
    return sort_groups(groups, area_adjusted)


def entrance_group(
    entries: list[dict[str, Any]],
    entrance: str,
    area_adjusted: bool,
) -> dict[str, Any]:
    rows = [entry for entry in entries if entry["entrance"] == entrance]
    return {
        **structure_summary(rows, area_adjusted),
        "entrance": entrance,
        "floors": floor_groups(rows, area_adjusted),
    }


def floor_groups(
    entries: list[dict[str, Any]],
    area_adjusted: bool,
) -> list[dict[str, Any]]:
    floors = sorted({entry["floor"] for entry in entries})
    groups = [floor_group(entries, floor, area_adjusted) for floor in floors]
    return sort_groups(groups, area_adjusted)


def floor_group(
    entries: list[dict[str, Any]],
    floor: str,
    area_adjusted: bool,
) -> dict[str, Any]:
    rows = [entry for entry in entries if entry["floor"] == floor]
    return {**structure_summary(rows, area_adjusted), "floor": floor}


def structure_summary(
    entries: list[dict[str, Any]],
    area_adjusted: bool,
) -> dict[str, Any]:
    debt = sum(float(entry["debt"]) for entry in entries)
    area = sum(float(entry["area"] or 0) for entry in entries)
    summary = {"count": len(entries), "debt": round(debt, 2), "area": round(area, 2)}
    return adjusted_summary(summary, area_adjusted)


def adjusted_summary(
    summary: dict[str, Any],
    area_adjusted: bool,
) -> dict[str, Any]:
    if area_adjusted:
        summary["debtPerArea"] = debt_per_area(summary)
    return summary


def debt_per_area(summary: dict[str, Any]) -> float | None:
    area = float(summary["area"])
    return round(float(summary["debt"]) / area, 2) if area else None


def sort_value(group: dict[str, Any], area_adjusted: bool) -> float:
    if area_adjusted:
        return float(group.get("debtPerArea") or 0)
    return float(group["debt"])


def sort_groups(
    groups: list[dict[str, Any]],
    area_adjusted: bool,
) -> list[dict[str, Any]]:
    return sorted(
        groups,
        key=lambda group: sort_value(group, area_adjusted),
        reverse=True,
    )


def field_text(apartment: dict[str, Any], keys: tuple[str, ...]) -> str:
    value = field_value(apartment, keys)
    return str(value).strip() if value not in (None, "") else "unknown"


def field_number(apartment: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    value = field_value(apartment, keys)
    return float(value) if isinstance(value, (int, float)) else None


def field_value(apartment: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in apartment:
            return apartment[key]
    return None
