from debtor_notifications import today_iso
from debtor_reports import (
    DebtorNextRequest,
    DebtorReportService,
    DebtorStructureRequest,
    field_number,
    field_text,
    format_next_rows,
)


class ReportClient:
    def get_bill_debt_analytics(self, request):
        self.debt_request = request
        return {
            "rows": [
                {"apartmentName": "Квартира 55", "endBalance": -1000},
                {"apartmentName": "Квартира 84", "endBalance": -2000},
                {"apartmentName": "Нежитлове приміщення 175", "endBalance": -3000},
            ]
        }

    def list_apartments(self, request):
        self.apartment_request = request
        return {
            "content": [
                apartment("55", "1", 2, 50),
                apartment("84", "1", 3, 100),
                apartment("99", "1", 2, 50),
                apartment("175", None, 1, 200),
            ],
            "last": True,
        }


def apartment(number, entrance, floor, area):
    return {
        "number": number,
        "entrance": entrance,
        "floor": floor,
        "area": area,
        "owners": [{"user": {"userId": f"user-{number}", "userStatus": "ACTIVE"}}],
    }


def test_next_to_notify_excludes_ledger(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    ledger_path.write_text(
        f'{{"date":"{today_iso()}","apartment":"84","status":"sent"}}\n',
        encoding="utf-8",
    )
    report = DebtorReportService(ReportClient()).next_to_notify(
        DebtorNextRequest(
            limit=5,
            exclude_notified_today=True,
            ledger_path=str(ledger_path),
        )
    )

    assert report["items"] == [{"apartment": "55", "debt": 1000.0, "recipients": 1}]
    assert report["skipped"] == []


def test_next_to_notify_formats():
    rows = [{"apartment": "55", "debt": 1000.0, "recipients": 1}]
    assert "55 | 1 000,00 | 1" in format_next_rows(rows, table=True)
    assert "Квартира 55" in format_next_rows(rows, table=False)
    assert format_next_rows([], table=True) == "No ready debtors to notify."
    assert format_next_rows([], table=False) == "No ready debtors to notify."


def test_by_entrance_area_adjusted():
    report = DebtorReportService(ReportClient()).by_entrance(
        DebtorStructureRequest(kind="all", area_adjusted=True)
    )

    assert_structure_summary(report)
    assert_entrance_summary(report["entrances"])


def assert_structure_summary(report):
    assert report["summary"] == {
        "count": 3,
        "debt": 6000.0,
        "area": 400.0,
        "debtPerArea": 15.0,
    }


def assert_entrance_summary(entrances):
    assert (
        entrances[0]["entrance"],
        entrances[0]["area"],
        entrances[0]["floors"][0]["floor"],
        entrances[0]["floors"][0]["debtPerArea"],
        entrances[1]["entrance"],
    ) == ("1", 200.0, "3", 20.0, "Без підʼїзду")


def test_field_helpers():
    assert (
        field_text({"section": {"name": "Під’їзд 1"}}, ("entrance", "section")),
        field_text({}, ("entrance",)),
        field_number({"size": 10}, ("area", "size")),
        field_number({"area": "10"}, ("area",)),
    ) == ("Під’їзд 1", "unknown", 10.0, 10.0)
