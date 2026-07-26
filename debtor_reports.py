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
            )
        )
        rows = [
            {
                "apartment": row["apartment"],
                "debt": row["debt"],
                "recipients": row["recipients"],
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
        entries = [
            structure_entry(debtor, apartments.get(debtor["number"], {}))
            for debtor in debtors
        ]
        entrances = [
            entrance_summary(entrance, rows, request.area_adjusted)
            for entrance, rows in grouped_by(entries, "entrance").items()
        ]
        return {
            "summary": summarize(entries, request.area_adjusted),
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


def entrance_summary(
    entrance: str,
    entries: list[dict[str, Any]],
    area_adjusted: bool,
) -> dict[str, Any]:
    floors = [
        {"floor": floor, **summarize(rows, area_adjusted)}
        for floor, rows in grouped_by(entries, "floor").items()
    ]
    return {
        **summarize(entries, area_adjusted),
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


def summarize(entries: list[dict[str, Any]], area_adjusted: bool) -> dict[str, Any]:
    debt = round(sum(float(entry["debt"]) for entry in entries), 2)
    area = round(sum(float(entry["area"] or 0) for entry in entries), 2)
    summary = {"count": len(entries), "debt": debt, "area": area}
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


def field_text(apartment: dict[str, Any], keys: tuple[str, ...]) -> str:
    value = field_value(apartment, keys)
    return str(value).strip() if value not in (None, "") else "unknown"


def field_number(apartment: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    value = field_value(apartment, keys)
    return float(value) if isinstance(value, (int, float)) else None


def field_value(apartment: dict[str, Any], keys: tuple[str, ...]) -> Any:
    return next((apartment[key] for key in keys if key in apartment), None)
