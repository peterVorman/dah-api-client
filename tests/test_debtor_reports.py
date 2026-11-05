import json

from debtor_notifications import today_iso
from debtor_reports import (
    DebtDashboardRequest,
    DebtorAuditRequest,
    DebtorNextRequest,
    DebtorReportService,
    DebtorStructureRequest,
    DebtSnapshotRequest,
    account_markers,
    dict_rows,
    field_number,
    field_text,
    format_next_rows,
    json_record,
    number_value,
    numeric_delta,
    sms_quota_summary,
    stage_summaries,
    string_values,
    transaction_date,
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
                apartment("175", None, 1, 200, kind="PREMISE"),
            ],
            "last": True,
        }

    def list_money_transaction_bank(self, request):
        self.money_request = request
        return {
            "content": [
                {
                    "operationDate": "2026-07-02T12:00:00",
                    "sum": "500,50",
                    "analytics": {"name": "Квартира 55"},
                },
                {
                    "operationDate": "2026-07-03T12:00:00",
                    "sum": 100,
                    "analytics": {"name": "Квартира 5"},
                },
            ],
            "last": True,
        }


class DashboardClient(ReportClient):
    def __init__(self, rows):
        self.rows = rows

    def get_bill_debt_analytics(self, request):
        self.debt_request = request
        return {"rows": self.rows}

    def get_sms_quota(self, request):
        self.sms_quota_request = request
        return {"enabled": True, "remaining": {"smsCount": 12}}


def apartment(number, entrance, floor, area, kind="APARTMENT"):
    return {
        "number": number,
        "entrance": entrance,
        "floor": floor,
        "area": area,
        "type": {"type": kind},
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

    assert report["items"] == [
        {
            "apartment": "55",
            "debt": 1000.0,
            "recipients": 1,
            "notificationMethod": "messenger",
            "recipientScope": "owners",
        }
    ]
    assert report["skipped"] == []


def test_next_to_notify_formats():
    rows = [{"apartment": "55", "debt": 1000.0, "recipients": 1}]
    assert "55 | 1 000,00 | 1" in format_next_rows(rows, table=True)
    assert "Квартира 55" in format_next_rows(rows, table=False)
    assert format_next_rows([], table=True) == "No ready debtors to notify."
    assert format_next_rows([], table=False) == "No ready debtors to notify."


def test_next_to_notify_service_formats():
    table = DebtorReportService(ReportClient()).next_to_notify(
        DebtorNextRequest(output_format="table", limit=1)
    )
    text = DebtorReportService(ReportClient()).next_to_notify(
        DebtorNextRequest(output_format="text", limit=1)
    )

    assert "84 | 2 000,00 | 1" in table
    assert "Квартира 84" in text


def test_by_entrance_area_adjusted():
    report = DebtorReportService(ReportClient()).by_entrance(
        DebtorStructureRequest(kind="all", area_adjusted=True)
    )

    assert_structure_summary(report)
    assert_entrance_summary(report["entrances"])


def test_debtor_audit_with_ledger_and_payments(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    ledger_path.write_text(
        "\n".join(
            [
                json.dumps({"date": "2026-07-01", "apartment": "55", "status": "sent"}),
                json.dumps(
                    {
                        "date": "2026-07-02",
                        "apartment": "55",
                        "status": "contacted",
                        "notificationMethod": "phone_call",
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    client = ReportClient()
    report = DebtorReportService(client).audit(
        DebtorAuditRequest(
            apartment_number="55",
            from_date="2026-07-01T00:00:00",
            ledger_path=str(ledger_path),
        )
    )

    assert (
        report["currentDebt"],
        report["meta"],
        report["ledger"]["records"],
        report["ledger"]["uniqueDates"],
        report["ledger"]["byMethod"],
        report["payments"],
        report["paymentTotal"],
        client.money_request.payload,
    ) == (
        1000.0,
        {"entrance": "1", "floor": "2", "area": 50.0},
        2,
        ["2026-07-01", "2026-07-02"],
        {"messenger": 1, "phone_call": 1},
        [{"date": "2026-07-02T12:00:00", "amount": 500.5}],
        500.5,
        {"direction": "INCOME", "from": "2026-07-01T00:00:00"},
    )


def test_debt_snapshot_compares_and_writes(tmp_path):
    snapshot_path = tmp_path / "snapshots.jsonl"
    previous = {
        "kind": "all",
        "debtFilterAccruals": 1,
        "minDebt": 0,
        "summary": {"count": 2, "debt": 5000, "area": 400, "debtPerArea": 12.5},
        "entrances": [{"entrance": "1", "debt": 2500, "area": 200}],
    }
    snapshot_path.write_text(json.dumps(previous), encoding="utf-8")

    report = DebtorReportService(ReportClient()).snapshot(
        DebtSnapshotRequest(
            snapshot_path=str(snapshot_path),
            write_snapshot=True,
        )
    )

    assert (
        report["previous"],
        report["current"]["summary"],
        report["delta"]["summary"]["debtDelta"],
        next(row for row in report["delta"]["entrances"] if row["entrance"] == "1")[
            "debtDelta"
        ],
        len(snapshot_path.read_text(encoding="utf-8").splitlines()),
    ) == (
        previous,
        {"count": 3, "debt": 6000.0, "area": 400.0, "debtPerArea": 15.0},
        1000.0,
        500.0,
        2,
    )


def test_debt_snapshot_uses_latest_compatible_snapshot(tmp_path):
    snapshot_path = tmp_path / "snapshots.jsonl"
    compatible = {
        "kind": "all",
        "debtFilterAccruals": 1,
        "minDebt": 0,
        "summary": {"count": 2, "debt": 5000, "area": 400, "debtPerArea": 12.5},
        "entrances": [{"entrance": "1", "debt": 2500, "area": 200}],
    }
    incompatible = {
        "kind": "premise",
        "debtFilterAccruals": 1,
        "minDebt": 0,
        "summary": {"count": 1, "debt": 3000, "area": 200, "debtPerArea": 15},
        "entrances": [{"entrance": "Без підʼїзду", "debt": 3000, "area": 200}],
    }
    snapshot_path.write_text(
        f"{json.dumps(compatible)}\n{json.dumps(incompatible)}\n",
        encoding="utf-8",
    )

    report = DebtorReportService(ReportClient()).snapshot(
        DebtSnapshotRequest(
            snapshot_path=str(snapshot_path),
            write_snapshot=False,
        )
    )

    assert (
        report["previous"],
        report["delta"]["summary"]["debtDelta"],
        next(row for row in report["delta"]["entrances"] if row["entrance"] == "1")[
            "debtDelta"
        ],
    ) == (compatible, 1000.0, 500.0)


def test_debt_dashboard_writes_and_compares_days(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    dashboard_path = tmp_path / "dashboard.jsonl"
    ledger_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "date": "2026-07-01",
                        "apartment": "55",
                        "status": "sent",
                        "notificationMethod": "messenger",
                        "recipients": 1,
                    }
                ),
                json.dumps(
                    {
                        "date": "2026-07-02",
                        "apartment": "84",
                        "kind": "apartment",
                        "status": "contacted",
                        "notificationMethod": "phone_call",
                        "recipients": 1,
                    }
                ),
                json.dumps(
                    {
                        "date": "2026-07-03",
                        "apartment": "175",
                        "kind": "premise",
                        "status": "no_answer",
                        "notificationMethod": "phone_call",
                        "recipients": 1,
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    client = DashboardClient(
        [
            {"apartmentName": "Квартира 55", "endBalance": -1000},
            {"apartmentName": "Нежитлове приміщення 175", "endBalance": -3000},
        ]
    )
    service = DebtorReportService(client)
    baseline = service.dashboard(
        DebtDashboardRequest(
            date="2026-07-01T12:00",
            ledger_path=str(ledger_path),
            dashboard_path=str(dashboard_path),
            write_snapshot=True,
        )
    )
    client.rows = [
        {"apartmentName": "Квартира 55", "endBalance": -1000},
        {"apartmentName": "Квартира 84", "endBalance": -2000},
        {"apartmentName": "Нежитлове приміщення 175", "endBalance": -3000},
    ]
    report = service.dashboard(
        DebtDashboardRequest(
            date="2026-07-04T12:00",
            ledger_path=str(ledger_path),
            dashboard_path=str(dashboard_path),
            write_snapshot=True,
        )
    )

    assert (
        baseline["previous"],
        report["previous"]["snapshotDate"],
        len(dashboard_path.read_text(encoding="utf-8").splitlines()),
        client.sms_quota_request.refresh,
    ) == (None, "2026-07-01", 2, True)
    assert (
        report["current"]["summary"],
        report["current"]["byKind"],
        report["current"]["communications"],
        report["current"]["stages"],
        report["current"]["smsQuota"],
    ) == (
        {"count": 3, "debt": 6000.0, "area": 400.0, "debtPerArea": 15.0},
        [
            {
                "kind": "apartment",
                "count": 2,
                "debt": 3000.0,
                "area": 200.0,
                "debtPerArea": 15.0,
            },
            {
                "kind": "premise",
                "count": 1,
                "debt": 3000.0,
                "area": 200.0,
                "debtPerArea": 15.0,
            },
        ],
        {
            "total": [
                {
                    "channel": "messenger",
                    "events": 1,
                    "sent": 1,
                    "contacted": 0,
                    "noAnswer": 0,
                    "recipients": 1,
                },
                {
                    "channel": "phone_call",
                    "events": 2,
                    "sent": 0,
                    "contacted": 1,
                    "noAnswer": 1,
                    "recipients": 2,
                },
            ],
            "today": [],
        },
        [
            {"stage": "notified", "count": 1, "debt": 1000.0},
            {"stage": "contacted", "count": 1, "debt": 2000.0},
            {"stage": "no_answer", "count": 1, "debt": 3000.0},
        ],
        {
            "enabled": True,
            "remaining": 12,
            "warningThreshold": 20,
            "status": "below_threshold",
            "warning": True,
        },
    )
    assert (
        report["delta"]["summary"]["debtDelta"],
        {row["stage"]: row["debtDelta"] for row in report["delta"]["stages"]},
    ) == (
        2000.0,
        {
            "contacted": 2000.0,
            "new": -3000.0,
            "no_answer": 3000.0,
            "notified": 0.0,
        },
    )


def test_sms_quota_summary():
    assert [
        sms_quota_summary({"enabled": True, "remaining": {"smsCount": 20}}, 20),
        sms_quota_summary({"enabled": True, "remaining": {"smsCount": 19}}, 20),
        sms_quota_summary({"enabled": False, "remaining": {"smsCount": 20}}, 20),
        sms_quota_summary({"enabled": True, "remaining": {}}, 20),
    ] == [
        {
            "enabled": True,
            "remaining": 20,
            "warningThreshold": 20,
            "status": "ok",
            "warning": False,
        },
        {
            "enabled": True,
            "remaining": 19,
            "warningThreshold": 20,
            "status": "below_threshold",
            "warning": True,
        },
        {
            "enabled": False,
            "remaining": 20,
            "warningThreshold": 20,
            "status": "disabled",
            "warning": True,
        },
        {
            "enabled": True,
            "remaining": None,
            "warningThreshold": 20,
            "status": "unavailable",
            "warning": True,
        },
    ]


def test_debt_dashboard_marks_ambiguous_legacy_records_unknown():
    entries = [
        {"kind": "apartment", "number": "1", "debt": 10},
        {"kind": "premise", "number": "1", "debt": 20},
    ]
    records = [
        {"apartment": "1", "status": "sent"},
        {"apartment": "1", "status": "ignored"},
    ]

    assert stage_summaries(entries, records) == [
        {"stage": "unknown", "count": 2, "debt": 30.0}
    ]


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


def test_report_edge_helpers():
    assert (
        account_markers({"pan": 12345}),
        transaction_date({"createTime": 1000}).endswith(":01"),
        number_value("bad"),
        number_value([]),
        string_values(["x", {"y": "z"}]),
        json_record("{"),
        dict_rows("bad"),
        numeric_delta([], {}),
        field_number({"area": "10x"}, ("area",)),
    ) == (
        ["12345"],
        True,
        None,
        None,
        ["x", "z"],
        None,
        [],
        {},
        None,
    )
