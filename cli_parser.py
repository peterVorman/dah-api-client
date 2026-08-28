"""Argument parser construction for the DAH CLI."""

from __future__ import annotations

import argparse
import os

from dah_api import (
    DEFAULT_BASE_URL,
    DEFAULT_ORIGIN,
    DEFAULT_REFERER,
    DEFAULT_USER_AGENT,
)
from debtor_notifications import (
    CONTACT_STATUSES,
    DEFAULT_DEBTOR_MESSAGE_TEMPLATE,
    DEFAULT_NOTIFICATION_LEDGER_PATH,
    NOTIFICATION_METHODS,
    RECIPIENT_SCOPES,
)
from debtor_reports import DEFAULT_DEBT_SNAPSHOT_PATH


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Send requests to the DAH cabinet API.",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("DAH_BASE_URL", DEFAULT_BASE_URL),
        help="API base URL.",
    )
    parser.add_argument(
        "--tab-id",
        default=os.getenv("DAH_TAB_ID"),
        help="X-DAH-TabId header. Defaults to DAH_TAB_ID when set.",
    )
    parser.add_argument(
        "--origin",
        default=os.getenv("DAH_ORIGIN", DEFAULT_ORIGIN),
        help="Origin header value.",
    )
    parser.add_argument(
        "--referer",
        default=os.getenv("DAH_REFERER", DEFAULT_REFERER),
        help="Referer header value.",
    )
    parser.add_argument(
        "--user-agent",
        default=os.getenv("DAH_USER_AGENT", DEFAULT_USER_AGENT),
        help="User-Agent header value.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30,
        help="HTTP timeout in seconds.",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Print compact JSON instead of pretty JSON.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "access",
        help="GET /organization/v1/access",
        description="Fetch organization access data.",
    )

    subparsers.add_parser(
        "auth-status",
        help="Inspect local bearer token state and get_access reachability.",
        description="Show sanitized local DAH authentication status.",
    )

    login_parser = subparsers.add_parser(
        "authentication-web-login",
        help="POST /authentication/web/login",
        description="Authenticate through the DAH web login endpoint.",
    )
    login_parser.add_argument(
        "--client-id",
        default="DAH_CLIENT_WEB",
        help="Client id value. Defaults to DAH_CLIENT_WEB.",
    )
    login_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the login request body without sending it.",
    )
    add_save_env_argument(login_parser)
    add_body_arguments(login_parser)

    relogin_parser = subparsers.add_parser(
        "authentication-relogin",
        help="POST /authentication/relogin",
        description="Refresh DAH authentication through the relogin endpoint.",
    )
    relogin_parser.add_argument(
        "--device-id",
        default=os.getenv("DAH_DEVICE_ID"),
        help="Device id. Defaults to DAH_DEVICE_ID when set.",
    )
    relogin_parser.add_argument(
        "--client-id",
        default="DAH_CLIENT_WEB",
        help="Client id value. Defaults to DAH_CLIENT_WEB.",
    )
    relogin_parser.add_argument(
        "--client-type",
        default="WEB",
        help="Client type value. Defaults to WEB.",
    )
    relogin_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the relogin request body without sending it.",
    )
    add_save_env_argument(relogin_parser)
    add_body_arguments(relogin_parser)

    subparsers.add_parser(
        "authentication-exit",
        help="GET /authentication/exit",
        description="Exit the current DAH authenticated session.",
    )

    publications_parser = subparsers.add_parser(
        "publications-search",
        help="POST /publications/search",
        description="Search publications.",
    )
    add_paging_arguments(publications_parser, size=5)
    add_body_arguments(publications_parser)

    publication_get_parser = subparsers.add_parser(
        "publication-get",
        help="GET /publications/get/{publicationId}",
        description="Fetch a publication by id.",
    )
    publication_get_parser.add_argument(
        "publication_id",
        help="Publication id path parameter.",
    )

    publication_save_parser = subparsers.add_parser(
        "publication-save",
        help="POST /publications/v2/add/web or PUT /publications/v2/edit/web",
        description="Create or edit a publication. Include id to edit.",
    )
    publication_save_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the publication request body without saving it.",
    )
    add_body_arguments(publication_save_parser, required=True)

    debt_analytics_parser = subparsers.add_parser(
        "bill-debt-analytics",
        help="POST /accounting/v1/report/bill/{associationId}/debt/analytics",
        description="Fetch bill debt analytics.",
    )
    add_association_id_argument(debt_analytics_parser)
    debt_analytics_parser.add_argument(
        "--date",
        help=("Report date in YYYY-MM-DDTHH:MM. Defaults to the current local minute."),
    )
    debt_analytics_parser.add_argument(
        "--debt-filter-accruals",
        type=int,
        default=1,
        help="Value for debtFilterAccruals in the default request body.",
    )
    add_body_arguments(debt_analytics_parser)

    reconciliation_parser = subparsers.add_parser(
        "bill-reconciliation",
        help="POST /accounting/v1/report/bill/{apartmentId}/reconciliation",
        description="Fetch an apartment or premise bill reconciliation report.",
    )
    add_bill_reconciliation_arguments(reconciliation_parser)
    add_body_arguments(reconciliation_parser)

    reconciliation_download_parser = subparsers.add_parser(
        "bill-reconciliation-download",
        help="POST /accounting/v1/report/bill/{apartmentId}/reconciliation/download",
        description="Download an apartment or premise bill reconciliation report.",
    )
    add_bill_reconciliation_arguments(reconciliation_download_parser)
    reconciliation_download_parser.add_argument(
        "--output",
        required=True,
        help="Output file path for the downloaded report.",
    )
    reconciliation_download_parser.add_argument(
        "--as-pdf",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Request PDF output. Use --no-as-pdf for the default non-PDF export.",
    )
    add_body_arguments(reconciliation_download_parser)

    reconciliation_send_parser = subparsers.add_parser(
        "bill-reconciliation-send",
        help="Download a bill reconciliation report and send it in DAH messenger.",
        description=(
            "Send an apartment or premise bill reconciliation report to a personal "
            "DAH messenger chat. Defaults to dry-run preview."
        ),
    )
    add_bill_reconciliation_arguments(reconciliation_send_parser)
    reconciliation_send_parser.add_argument(
        "--description",
        default="",
        help="Optional file message description.",
    )
    reconciliation_send_parser.add_argument(
        "--file-name",
        help="Messenger attachment filename. Defaults to a generated PDF name.",
    )
    reconciliation_send_parser.add_argument(
        "--recipient-scope",
        choices=("owners", "others", "owners+others"),
        default="owners",
        help="People to notify from the apartment card. Defaults to owners.",
    )
    reconciliation_send_parser.add_argument(
        "--as-pdf",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Request PDF output. Use --no-as-pdf for the default non-PDF export.",
    )
    reconciliation_send_parser.add_argument(
        "--send",
        action="store_true",
        help="Upload the report and send the messenger file message.",
    )
    reconciliation_send_parser.add_argument(
        "--confirm",
        help="Exact apartment or premise number required with --send.",
    )
    add_body_arguments(reconciliation_send_parser)

    notify_parser = subparsers.add_parser(
        "debtors-notify",
        help="Notify debtors through DAH messenger or tenant notifications.",
        description=(
            "Build or send DAH debtor notifications. Defaults to dry-run "
            "preview and automatic channel selection; use --send to write."
        ),
    )
    add_association_id_argument(notify_parser)
    add_debt_report_arguments(notify_parser, default_kind="all", default_limit=None)
    add_notification_method_argument(notify_parser)
    add_recipient_scope_argument(notify_parser)
    notify_parser.add_argument(
        "--apartment-number",
        action="append",
        default=[],
        help="Exact apartment number to include. Can be passed multiple times.",
    )
    notify_parser.add_argument(
        "--message-template",
        default=DEFAULT_DEBTOR_MESSAGE_TEMPLATE,
        help="Message template with {apartment_label} and {debt}.",
    )
    notify_parser.add_argument(
        "--send",
        action="store_true",
        help="Actually send messages. Omit for dry-run preview.",
    )
    notify_parser.add_argument(
        "--confirm",
        action="append",
        default=[],
        help="Apartment number confirmed for --send. Repeat for batches.",
    )
    notify_parser.add_argument(
        "--max-send",
        type=int,
        help="Refuse --send when more than this many messages are ready.",
    )
    notify_parser.add_argument(
        "--one-by-one",
        action="store_true",
        help="Shortcut for --max-send 1.",
    )
    add_ledger_arguments(notify_parser)
    notify_parser.add_argument(
        "--exclude-notified-today",
        action="store_true",
        help="Exclude apartments with sent records in today's ledger.",
    )
    notify_parser.add_argument(
        "--format",
        choices=("json", "table", "text"),
        default="json",
        help="Output format. Defaults to json.",
    )

    next_parser = subparsers.add_parser(
        "debtors-next",
        help="Show next ready debtor notifications.",
        description=(
            "List next debtors ready for the selected DAH notification method."
        ),
    )
    add_association_id_argument(next_parser)
    add_debt_report_arguments(next_parser)
    add_notification_method_argument(next_parser)
    add_recipient_scope_argument(next_parser)
    next_parser.add_argument(
        "--exclude-notified-today",
        action="store_true",
        help="Exclude apartments with sent records in today's ledger.",
    )
    add_ledger_path_argument(next_parser)
    next_parser.add_argument(
        "--format",
        choices=("json", "table", "text"),
        default="json",
        help="Output format. Defaults to json.",
    )

    structure_parser = subparsers.add_parser(
        "debtors-by-entrance",
        help="Analyze debtor debt by entrance and floor.",
        description="Group current debtor debt by apartment entrance and floor.",
    )
    add_association_id_argument(structure_parser)
    add_debt_report_arguments(
        structure_parser,
        default_kind="apartment",
        include_limit=False,
    )
    structure_parser.add_argument(
        "--area-adjusted",
        action="store_true",
        help="Include and sort by debt per known area.",
    )

    audit_parser = subparsers.add_parser(
        "debtor-audit",
        help="Analyze one debtor with ledger contacts and matched payments.",
        description=(
            "Fetch current debt, local communication history, and exact "
            "bank-income payment matches for one apartment or premise."
        ),
    )
    add_association_id_argument(audit_parser)
    add_debt_report_arguments(
        audit_parser,
        default_kind="apartment",
        include_limit=False,
    )
    audit_parser.add_argument(
        "--apartment-number",
        required=True,
        help="Exact apartment or premise number to audit.",
    )
    audit_parser.add_argument(
        "--from-date",
        required=True,
        help=("Start date/time for payment matching; example: 2026-07-01T00:00:00."),
    )
    add_ledger_path_argument(audit_parser)

    snapshot_parser = subparsers.add_parser(
        "debt-snapshot",
        help="Create or compare an aggregate local debt snapshot.",
        description=(
            "Build aggregate debt totals and compare them with the latest "
            "local snapshot. Use --write to append the current snapshot."
        ),
    )
    add_association_id_argument(snapshot_parser)
    add_debt_report_arguments(
        snapshot_parser,
        default_kind="all",
        include_limit=False,
    )
    snapshot_parser.add_argument(
        "--snapshot-path",
        default=DEFAULT_DEBT_SNAPSHOT_PATH,
        help="Local JSONL aggregate debt snapshot path.",
    )
    snapshot_parser.add_argument(
        "--write",
        action="store_true",
        help="Append the current aggregate snapshot to the local file.",
    )

    ledger_parser = subparsers.add_parser(
        "ledger-add-contact",
        help="Append a manual debtor contact result to the local ledger.",
        description="Record a safe local phone/offline contact outcome.",
    )
    ledger_parser.add_argument(
        "--apartment-number",
        required=True,
        help="Exact apartment or premise number.",
    )
    ledger_parser.add_argument(
        "--kind",
        choices=("apartment", "premise"),
        default="apartment",
        help="Ledger subject kind. Defaults to apartment.",
    )
    ledger_parser.add_argument(
        "--status",
        choices=CONTACT_STATUSES,
        required=True,
        help="Manual contact outcome.",
    )
    ledger_parser.add_argument(
        "--debt",
        type=float,
        default=0,
        help="Current debt amount when known.",
    )
    ledger_parser.add_argument(
        "--recipients",
        type=int,
        default=1,
        help="Number of contacted or attempted recipients.",
    )
    ledger_parser.add_argument(
        "--recipient-scope",
        choices=RECIPIENT_SCOPES[1:],
        default="owners",
        help="Contacted recipient source.",
    )
    ledger_parser.add_argument(
        "--note",
        default="",
        help="Short sanitized note. Do not include phone numbers or emails.",
    )
    ledger_parser.add_argument(
        "--date",
        dest="contact_date",
        help="Contact date in YYYY-MM-DD. Defaults to today.",
    )
    add_ledger_path_argument(ledger_parser)

    feedback_order_parser = subparsers.add_parser(
        "feedback-order-list",
        help="POST /feedback/order/list/{associationId}",
        description="Fetch feedback order list.",
    )
    add_association_id_argument(feedback_order_parser)
    add_body_arguments(feedback_order_parser)

    feedback_status_parser = subparsers.add_parser(
        "feedback-order-status",
        help="PUT /feedback/order/comment/{orderId}",
        description="Update feedback order status.",
    )
    feedback_status_parser.add_argument(
        "order_id",
        help="Feedback order id path parameter.",
    )
    feedback_status_parser.add_argument(
        "--status",
        default="DONE",
        help="Status value to send. Defaults to DONE.",
    )
    feedback_status_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the status request body without sending it.",
    )

    tenant_notification_parser = subparsers.add_parser(
        "tenant-notification-send",
        help=("POST /communication/v1/client/notification/{associationId}/tenant/send"),
        description=(
            "Build or send a DAH tenant notification. Defaults to preview; "
            "use --send with --confirm-tenant-id to write."
        ),
    )
    add_association_id_argument(tenant_notification_parser)
    tenant_notification_parser.add_argument(
        "--tenant-id",
        help="Tenant id used as tenantId in the request body.",
    )
    tenant_notification_parser.add_argument(
        "--text",
        help="Plain text notification body.",
    )
    tenant_notification_parser.add_argument(
        "--text-html",
        help="HTML notification body. Defaults to escaped --text wrapped in <p>.",
    )
    tenant_notification_parser.add_argument(
        "--send",
        action="store_true",
        help="Actually send the tenant notification. Omit for preview.",
    )
    tenant_notification_parser.add_argument(
        "--confirm-tenant-id",
        help="Tenant id confirmation required with --send.",
    )
    add_body_arguments(tenant_notification_parser)

    apartment_parser = subparsers.add_parser(
        "apartment-list",
        help="POST /organization/v1/apartment/{associationId}/list",
        description="Fetch apartments and owner metadata.",
    )
    add_association_id_argument(apartment_parser)
    add_paging_arguments(apartment_parser)
    add_body_arguments(apartment_parser)

    money_transaction_parser = subparsers.add_parser(
        "money-transaction-bank-list",
        help="POST /accounting/v1/money/transaction/{associationId}/list/bank",
        description="Fetch bank money transactions.",
    )
    add_association_id_argument(money_transaction_parser)
    add_paging_arguments(money_transaction_parser)
    money_transaction_parser.add_argument(
        "--direction",
        default="EXPENSE",
        help="Transaction direction in the default request body.",
    )
    money_transaction_parser.add_argument(
        "--from-date",
        help=(
            "Start date/time for the default request body, "
            "for example 2026-07-01T00:00:00."
        ),
    )
    add_body_arguments(money_transaction_parser)

    messenger_parser = subparsers.add_parser(
        "messenger-group-messages",
        help="POST /messenger/groups/{groupId}/messages",
        description="Fetch messenger group messages.",
    )
    messenger_parser.add_argument(
        "--group-id",
        help="Messenger group id path parameter.",
    )
    add_paging_arguments(messenger_parser)
    add_body_arguments(messenger_parser)

    messenger_groups_parser = subparsers.add_parser(
        "messenger-groups-page",
        help="POST /messenger/groups/page",
        description="Fetch messenger groups page.",
    )
    add_paging_arguments(messenger_groups_parser)
    add_body_arguments(messenger_groups_parser)

    send_message_parser = subparsers.add_parser(
        "messenger-send-message",
        help="POST /messenger/messages",
        description="Send a text message to a messenger chat.",
    )
    chat_target_group = send_message_parser.add_mutually_exclusive_group(
        required=True,
    )
    chat_target_group.add_argument(
        "--chat-name",
        help="Exact messenger chat name to resolve before sending.",
    )
    chat_target_group.add_argument(
        "--group-id",
        help="Messenger group id. Use this to skip chat-name lookup.",
    )
    chat_target_group.add_argument(
        "--interlocutor-id",
        help="Owner/user id used to resolve a personal messenger group.",
    )
    send_message_parser.add_argument(
        "--message-type",
        default="TEXT",
        help="Message type. Defaults to TEXT.",
    )
    send_message_parser.add_argument(
        "--create-time",
        type=int,
        help="createTime value in epoch milliseconds. Defaults to now.",
    )
    send_message_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the message request body without sending it.",
    )
    send_message_parser.add_argument(
        "message",
        help="Message text to send.",
    )

    personal_group_parser = subparsers.add_parser(
        "messenger-personal-group-get",
        help="GET /messenger/groups/personal/{interlocutorId}/get",
        description="Fetch or create a personal messenger group by user id.",
    )
    personal_group_parser.add_argument(
        "interlocutor_id",
        help="Owner/user id for the personal messenger group.",
    )

    return parser


def add_association_id_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--association-id",
        default=os.getenv("DAH_ASSOCIATION_ID"),
        help=(
            "Association id path parameter. Defaults to DAH_ASSOCIATION_ID "
            "or a single id resolved from get_access."
        ),
    )


def add_paging_arguments(
    parser: argparse.ArgumentParser,
    *,
    size: int = 50,
) -> None:
    parser.add_argument(
        "--page",
        type=int,
        default=0,
        help="0-based page number.",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=size,
        help="Page size.",
    )


def add_body_arguments(
    parser: argparse.ArgumentParser,
    *,
    required: bool = False,
) -> None:
    body_group = parser.add_mutually_exclusive_group(required=required)
    body_group.add_argument(
        "--body",
        help="Inline JSON body to send to the endpoint.",
    )
    body_group.add_argument(
        "--body-file",
        help="Path to a JSON file containing the request body.",
    )


def add_bill_reconciliation_arguments(parser: argparse.ArgumentParser) -> None:
    add_association_id_argument(parser)
    apartment_group = parser.add_mutually_exclusive_group(required=True)
    apartment_group.add_argument(
        "--apartment-id",
        help="DAH apartment/premise id path parameter.",
    )
    apartment_group.add_argument(
        "--apartment-number",
        help="Exact apartment or premise number to resolve through apartment-list.",
    )
    parser.add_argument(
        "--kind",
        choices=("apartment", "premise"),
        default="apartment",
        help="Number lookup kind. Defaults to apartment.",
    )
    parser.add_argument(
        "--from-date",
        help="Start date/time for the report body; example: 2026-07-01T00:00:00.",
    )
    parser.add_argument(
        "--to-date",
        help="End date/time for the report body; example: 2026-07-31T23:59:59.",
    )
    parser.add_argument(
        "--flow-item-details",
        action="store_true",
        help="Set flowItemDetails=true in the default request body.",
    )


def add_save_env_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--save-env-local",
        action="store_true",
        help="Save returned auth tokens to .env.local without printing them.",
    )


def add_debt_report_arguments(
    parser: argparse.ArgumentParser,
    *,
    default_kind: str = "apartment",
    include_limit: bool = True,
    default_limit: int | None = 15,
) -> None:
    parser.add_argument(
        "--date",
        help="Report date in YYYY-MM-DDTHH:MM. Defaults to the current local minute.",
    )
    parser.add_argument(
        "--debt-filter-accruals",
        type=int,
        default=1,
        help="Value for debtFilterAccruals in the default debt request body.",
    )
    parser.add_argument(
        "--min-debt",
        type=float,
        default=0,
        help="Minimum debt amount to include. Defaults to 0.",
    )
    if include_limit:
        help_text = "Maximum number of rows to include."
        if default_limit is not None:
            help_text += f" Defaults to {default_limit}."
        parser.add_argument(
            "--limit",
            type=int,
            default=default_limit,
            help=help_text,
        )
    parser.add_argument(
        "--kind",
        choices=("all", "apartment", "premise"),
        default=default_kind,
        help=f"Debtor kind to include. Defaults to {default_kind}.",
    )


def add_notification_method_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--notification-method",
        choices=NOTIFICATION_METHODS,
        default="auto",
        help=(
            "Notification transport. Defaults to auto, which switches current "
            "debtors with previous messenger sends to tenant notifications."
        ),
    )


def add_recipient_scope_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--recipient-scope",
        choices=RECIPIENT_SCOPES,
        default="auto",
        help=(
            "Recipient source. Defaults to auto: owners first, then others as "
            "fallback. Use owners+others to target both sources."
        ),
    )


def add_ledger_arguments(parser: argparse.ArgumentParser) -> None:
    add_ledger_path_argument(parser)
    parser.add_argument(
        "--no-ledger",
        action="store_true",
        help="Do not write notification results to the local ledger.",
    )


def add_ledger_path_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--ledger-path",
        default=DEFAULT_NOTIFICATION_LEDGER_PATH,
        help="Local JSONL notification ledger path.",
    )
