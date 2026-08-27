"""Shared DAH debtor and apartment normalization helpers."""

from __future__ import annotations

import re
from typing import Any

APARTMENT_NUMBER_RE = re.compile(
    r"(?:Квартира|приміщення)\s+(\d+(?:,\d+)?(?:-\d+)?)\s*$",
    re.IGNORECASE,
)


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


def apartment_pages_finished(response: Any, page: int) -> bool:
    if not isinstance(response, dict):
        return True
    if response.get("last") is True:
        return True
    total_pages = response.get("totalPages")
    return isinstance(total_pages, int) and page + 1 >= total_pages


def format_money(value: float) -> str:
    return f"{value:,.2f}".replace(",", " ").replace(".", ",")
