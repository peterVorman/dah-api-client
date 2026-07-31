"""Read-only debtor reports built on top of the DAH client."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dah_api import DahApiClient
from debtor_notifications import (
    DEFAULT_NOTIFICATION_LEDGER_PATH,
    DebtorNotificationRequest,
    DebtorNotificationService,
    apartment_for_debtor,
    apartment_kind,
    debtor_kind,
    format_money,
)

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
        f"- Квартира {row['apartment']}: "
        f"{debt} грн, отримувачів: {row['recipients']}"
    )


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
        "kind": debtor_kind(debtor["label"]),
        "debt": debtor["debt"],
        "entrance": entrance_text(apartment),
        "floor": floor_text(apartment),
        "area": field_number(apartment, AREA_KEYS),
    }


def area_entry(apartment: dict[str, Any]) -> dict[str, Any]:
    return {
        "debt": 0.0,
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


def grouped_by(
    entries: list[dict[str, Any]],
    key: str,
) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        groups.setdefault(str(entry[key]), []).append(entry)
    return dict(sorted(groups.items()))


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
