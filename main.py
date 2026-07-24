#!/usr/bin/env python3
"""CLI wrapper for the DAH API client."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from auth_session import auth_status, sanitize_auth_response, save_auth_env
from dah_api import (
    DEFAULT_BASE_URL,
    DEFAULT_ORIGIN,
    DEFAULT_REFERER,
    DEFAULT_USER_AGENT,
    MISSING_BEARER_TOKEN_MESSAGE,
    ApartmentListRequest,
    AuthenticationReloginRequest,
    AuthenticationWebLoginRequest,
    BillDebtAnalyticsRequest,
    DahApiClient,
    DahApiConfig,
    DahHttpError,
    DahRequestError,
    FeedbackOrderListRequest,
    FeedbackOrderStatusRequest,
    MessengerGroupMessagesRequest,
    MessengerGroupsPageRequest,
    MessengerMessageRequest,
    MessengerPersonalGroupRequest,
    MoneyTransactionBankListRequest,
    PublicationSaveRequest,
    PublicationsSearchRequest,
    default_bill_debt_analytics_payload,
    load_env_file,
)
from debtor_notifications import (
    DEFAULT_DEBTOR_MESSAGE_TEMPLATE,
    DebtorNotificationRequest,
    DebtorNotificationService,
    format_debtor_notification_report,
)

MISSING_MESSENGER_GROUP_ID_MESSAGE = (
    "Missing messenger group id. Set DAH_MESSENGER_GROUP_ID or pass --group-id."
)


class DahCli:
    def __init__(self) -> None:
        load_env_file()
        self.parser = self._build_parser()

    def run(self, argv: list[str] | None = None) -> int:
        args = self.parser.parse_args(argv)
        client = DahApiClient(self._build_config(args))

        try:
            response_data = self._dispatch(args, client)
        except DahHttpError as exc:
            return self._print_http_error(exc)
        except DahRequestError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        self._print_response(response_data, args.compact)
        return 0

    def _dispatch(self, args: argparse.Namespace, client: DahApiClient) -> Any:
        handlers = {
            "access": client.get_access,
            "auth-status": lambda: self._auth_status(client),
            "authentication-web-login": lambda: self._login_or_preview(args, client),
            "authentication-relogin": lambda: self._relogin_or_preview(args, client),
            "authentication-exit": client.authentication_exit,
            "publications-search": lambda: self._publications_search(args, client),
            "publication-get": lambda: client.get_publication(args.publication_id),
            "publication-save": lambda: self._save_or_preview_publication(args, client),
            "bill-debt-analytics": lambda: self._bill_debt_analytics(args, client),
            "debtors-notify": lambda: self._debtors_notify(args, client),
            "feedback-order-list": lambda: self._feedback_orders(args, client),
            "feedback-order-status": lambda: self._update_or_preview_order_status(
                args, client
            ),
            "apartment-list": lambda: self._apartments(args, client),
            "money-transaction-bank-list": lambda: self._bank_transactions(
                args, client
            ),
            "messenger-group-messages": lambda: self._messenger_group_messages(
                args, client
            ),
            "messenger-groups-page": lambda: self._messenger_groups(args, client),
            "messenger-personal-group-get": lambda: (
                client.get_messenger_personal_group(
                    MessengerPersonalGroupRequest(args.interlocutor_id)
                )
            ),
            "messenger-send-message": lambda: self._send_or_preview_message(
                args, client
            ),
        }
        return handlers[args.command]()

    @staticmethod
    def _print_http_error(exc: DahHttpError) -> int:
        print(f"HTTP {exc.status_code} {exc.reason}", file=sys.stderr)
        if exc.body:
            print(exc.body, file=sys.stderr)
        return 1

    @staticmethod
    def _print_response(response_data: Any, compact: bool) -> None:
        if isinstance(response_data, str):
            print(response_data)
            return
        indent = None if compact else 2
        print(json.dumps(response_data, ensure_ascii=False, indent=indent))

    def _auth_status(self, client: DahApiClient) -> dict[str, Any]:
        error = None
        access_data = None
        if client.config.token:
            try:
                access_data = client.get_access()
            except (DahHttpError, DahRequestError) as exc:
                error = str(exc)
        return auth_status(client.config.token, access_data, error)

    def _publications_search(
        self,
        args: argparse.Namespace,
        client: DahApiClient,
    ) -> Any:
        return client.search_publications(self._build_publications_request(args))

    def _bill_debt_analytics(
        self,
        args: argparse.Namespace,
        client: DahApiClient,
    ) -> Any:
        return client.get_bill_debt_analytics(
            self._build_bill_debt_analytics_request(args)
        )

    def _feedback_orders(
        self,
        args: argparse.Namespace,
        client: DahApiClient,
    ) -> Any:
        return client.list_feedback_orders(
            self._build_feedback_order_list_request(args)
        )

    def _apartments(
        self,
        args: argparse.Namespace,
        client: DahApiClient,
    ) -> Any:
        return client.list_apartments(self._build_apartment_list_request(args))

    def _bank_transactions(
        self,
        args: argparse.Namespace,
        client: DahApiClient,
    ) -> Any:
        return client.list_money_transaction_bank(
            self._build_money_transaction_bank_list_request(args)
        )

    def _messenger_group_messages(
        self,
        args: argparse.Namespace,
        client: DahApiClient,
    ) -> Any:
        return client.list_messenger_group_messages(
            self._build_messenger_group_messages_request(args)
        )

    def _messenger_groups(
        self,
        args: argparse.Namespace,
        client: DahApiClient,
    ) -> Any:
        return client.list_messenger_groups(
            self._build_messenger_groups_page_request(args)
        )

    def _update_or_preview_order_status(
        self,
        args: argparse.Namespace,
        client: DahApiClient,
    ) -> Any:
        request = FeedbackOrderStatusRequest(args.order_id, args.status)
        if args.dry_run:
            return request.to_payload()
        return client.update_feedback_order_status(request)

    def _login_or_preview(
        self,
        args: argparse.Namespace,
        client: DahApiClient,
    ) -> Any:
        request = self._build_authentication_web_login_request(args)
        if args.dry_run:
            return request.to_payload()
        return self._auth_response(
            client.authentication_web_login(request),
            args.save_env_local,
        )

    def _relogin_or_preview(
        self,
        args: argparse.Namespace,
        client: DahApiClient,
    ) -> Any:
        request = self._build_authentication_relogin_request(args)
        if args.dry_run:
            return request.to_payload()
        return self._auth_response(
            client.authentication_relogin(request),
            args.save_env_local,
        )

    def _auth_response(self, response: Any, save_env_local: bool) -> dict[str, Any]:
        result = {"response": sanitize_auth_response(response)}
        if save_env_local:
            result["env"] = save_auth_env(response)
        return result

    def _save_or_preview_publication(
        self,
        args: argparse.Namespace,
        client: DahApiClient,
    ) -> Any:
        request = PublicationSaveRequest(load_payload(args, {}))
        if args.dry_run:
            return request.to_payload(client.get_default_association_id())
        return client.save_publication(request)

    def _send_or_preview_message(
        self,
        args: argparse.Namespace,
        client: DahApiClient,
    ) -> Any:
        message_request = self._build_messenger_message_request(args, client)
        if args.dry_run:
            return message_request.to_payload()
        return client.send_messenger_message(message_request)

    def _debtors_notify(
        self,
        args: argparse.Namespace,
        client: DahApiClient,
    ) -> Any:
        report = DebtorNotificationService(client).run(
            self._build_debtor_notification_request(args)
        )
        return format_debtor_notification_report(report, args.format)

    def _build_parser(self) -> argparse.ArgumentParser:
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
            help=(
                "Report date in YYYY-MM-DDTHH:MM. Defaults to the current local minute."
            ),
        )
        debt_analytics_parser.add_argument(
            "--debt-filter-accruals",
            type=int,
            default=1,
            help="Value for debtFilterAccruals in the default request body.",
        )
        add_body_arguments(debt_analytics_parser)

        notify_parser = subparsers.add_parser(
            "debtors-notify",
            help="Notify debtors through DAH personal messenger chats.",
            description=(
                "Build or send direct DAH messenger notifications for debtors. "
                "Defaults to dry-run preview; use --send to write."
            ),
        )
        add_association_id_argument(notify_parser)
        notify_parser.add_argument(
            "--date",
            help=(
                "Report date in YYYY-MM-DDTHH:MM. Defaults to the current local minute."
            ),
        )
        notify_parser.add_argument(
            "--debt-filter-accruals",
            type=int,
            default=1,
            help="Value for debtFilterAccruals in the default debt request body.",
        )
        notify_parser.add_argument(
            "--min-debt",
            type=float,
            default=0,
            help="Minimum debt amount to include. Defaults to 0.",
        )
        notify_parser.add_argument(
            "--limit",
            type=int,
            help="Maximum number of ready notifications to include.",
        )
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
            "--format",
            choices=("json", "table", "text"),
            default="json",
            help="Output format. Defaults to json.",
        )

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
            default=os.getenv("DAH_MESSENGER_GROUP_ID"),
            help=(
                "Messenger group id path parameter. Defaults to DAH_MESSENGER_GROUP_ID."
            ),
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

    def _build_config(self, args: argparse.Namespace) -> DahApiConfig:
        auth_command = args.command in {
            "auth-status",
            "authentication-relogin",
            "authentication-web-login",
        }
        token = os.getenv("DAH_BEARER_TOKEN", "")
        if not token:
            if not auth_command:
                raise SystemExit(MISSING_BEARER_TOKEN_MESSAGE)
        return DahApiConfig(
            token=token,
            base_url=args.base_url,
            tab_id=args.tab_id,
            origin=args.origin,
            referer=args.referer,
            user_agent=args.user_agent,
            timeout=args.timeout,
            require_token=not auth_command,
        )

    def _build_publications_request(
        self,
        args: argparse.Namespace,
    ) -> PublicationsSearchRequest:
        payload = {"statuses": ["PUBLISHED"]}
        if association_id := os.getenv("DAH_ASSOCIATION_ID"):
            payload["associationId"] = association_id
        return PublicationsSearchRequest(
            page=args.page,
            size=args.size,
            payload=load_payload(args, payload),
        )

    def _build_authentication_web_login_request(
        self,
        args: argparse.Namespace,
    ) -> AuthenticationWebLoginRequest:
        default_payload = AuthenticationWebLoginRequest(
            login=os.getenv("DAH_LOGIN", ""),
            password=os.getenv("DAH_PASSWORD", ""),
            client_id=args.client_id,
        ).to_payload()
        payload = load_payload(args, default_payload)
        return AuthenticationWebLoginRequest(
            login=str(payload.get("login", "")),
            password=str(payload.get("password", "")),
            client_id=str(payload.get("clientId", "DAH_CLIENT_WEB")),
        )

    def _build_authentication_relogin_request(
        self,
        args: argparse.Namespace,
    ) -> AuthenticationReloginRequest:
        default_payload = AuthenticationReloginRequest(
            refresh_token=os.getenv("DAH_REFRESH_TOKEN", ""),
            device_id=args.device_id,
            client_id=args.client_id,
            client_type=args.client_type,
        ).to_payload()
        payload = load_payload(args, default_payload)
        return AuthenticationReloginRequest(
            refresh_token=str(payload.get("refreshToken", "")),
            device_id=payload.get("deviceId"),
            client_id=str(payload.get("clientId", "DAH_CLIENT_WEB")),
            client_type=str(payload.get("clientType", "WEB")),
        )

    def _build_bill_debt_analytics_request(
        self,
        args: argparse.Namespace,
    ) -> BillDebtAnalyticsRequest:
        return BillDebtAnalyticsRequest(
            association_id=args.association_id,
            payload=load_payload(
                args,
                default_bill_debt_analytics_payload(
                    date=args.date,
                    debt_filter_accruals=args.debt_filter_accruals,
                ),
            ),
        )

    def _build_feedback_order_list_request(
        self,
        args: argparse.Namespace,
    ) -> FeedbackOrderListRequest:
        return FeedbackOrderListRequest(
            association_id=args.association_id,
            payload=load_payload(
                args,
                {},
            ),
        )

    def _build_debtor_notification_request(
        self,
        args: argparse.Namespace,
    ) -> DebtorNotificationRequest:
        return DebtorNotificationRequest(
            association_id=args.association_id,
            date=args.date,
            debt_filter_accruals=args.debt_filter_accruals,
            min_debt=args.min_debt,
            limit=args.limit,
            apartment_numbers=args.apartment_number,
            confirm_apartment_numbers=args.confirm,
            message_template=args.message_template,
            send=args.send,
        )

    def _build_apartment_list_request(
        self,
        args: argparse.Namespace,
    ) -> ApartmentListRequest:
        return ApartmentListRequest(
            association_id=args.association_id,
            page=args.page,
            size=args.size,
            payload=load_payload(args, {}),
        )

    def _build_money_transaction_bank_list_request(
        self,
        args: argparse.Namespace,
    ) -> MoneyTransactionBankListRequest:
        payload = {"direction": args.direction}
        if args.from_date:
            payload["from"] = args.from_date
        return MoneyTransactionBankListRequest(
            association_id=args.association_id,
            page=args.page,
            size=args.size,
            payload=load_payload(args, payload),
        )

    def _build_messenger_group_messages_request(
        self,
        args: argparse.Namespace,
    ) -> MessengerGroupMessagesRequest:
        if not args.group_id:
            raise SystemExit(MISSING_MESSENGER_GROUP_ID_MESSAGE)
        return MessengerGroupMessagesRequest(
            group_id=args.group_id,
            page=args.page,
            size=args.size,
            payload=load_payload(args, {}),
        )

    def _build_messenger_groups_page_request(
        self,
        args: argparse.Namespace,
    ) -> MessengerGroupsPageRequest:
        return MessengerGroupsPageRequest(
            page=args.page,
            size=args.size,
            payload=load_payload(
                args,
                {},
            ),
        )

    def _build_messenger_message_request(
        self,
        args: argparse.Namespace,
        client: DahApiClient,
    ) -> MessengerMessageRequest:
        group_id = args.group_id or ""
        if args.interlocutor_id:
            group_id = PersonalGroupResolver(client).resolve(args.interlocutor_id)
        elif not group_id:
            group_id = MessengerGroupResolver(client).resolve(args.chat_name)

        kwargs: dict[str, Any] = {}
        if args.create_time is not None:
            kwargs["create_time"] = args.create_time

        return MessengerMessageRequest(
            group_id=group_id,
            payload=args.message,
            message_type=args.message_type,
            **kwargs,
        )


@dataclass(slots=True)
class MessengerGroupResolver:
    client: DahApiClient

    def resolve(self, chat_name: str) -> str:
        expected_name = chat_name.strip().casefold()
        matches = [
            group
            for group in self.iter_groups()
            if str(group.get("name", "")).strip().casefold() == expected_name
        ]
        return self.select_single_id(matches, chat_name)

    def select_single_id(
        self,
        matches: list[dict[str, Any]],
        chat_name: str,
    ) -> str:
        if not matches:
            raise SystemExit(f"Chat not found by exact name: {chat_name}")
        if len(matches) > 1:
            ids = self.format_group_ids(matches)
            raise SystemExit(
                f"Multiple chats found by exact name '{chat_name}'. "
                f"Use --group-id. Matches: {ids}",
            )

        group_id = matches[0].get("id")
        if not isinstance(group_id, str) or not group_id:
            raise SystemExit(f"Chat '{chat_name}' has no usable id.")
        return group_id

    def iter_groups(self) -> Iterable[dict[str, Any]]:
        page = 0
        size = 50

        while True:
            response_data = self.client.list_messenger_groups(
                MessengerGroupsPageRequest(page=page, size=size),
            )
            groups = self.extract_groups(response_data)
            yield from groups
            if response_data.get("last") is True:
                break
            total_pages = response_data.get("totalPages")
            page += 1
            if isinstance(total_pages, int) and page >= total_pages:
                break

    @staticmethod
    def extract_groups(response_data: Any) -> list[dict[str, Any]]:
        if not isinstance(response_data, dict):
            raise SystemExit("Unable to resolve chat name: unexpected groups response.")

        groups = response_data.get("content", [])
        if not isinstance(groups, list):
            raise SystemExit("Unable to resolve chat name: missing groups content.")
        return [group for group in groups if isinstance(group, dict)]

    @staticmethod
    def format_group_ids(matches: list[dict[str, Any]]) -> str:
        return ", ".join(str(match.get("id", "")) for match in matches)


@dataclass(slots=True)
class PersonalGroupResolver:
    client: DahApiClient

    def resolve(self, interlocutor_id: str) -> str:
        group = self.client.get_messenger_personal_group(
            MessengerPersonalGroupRequest(interlocutor_id)
        )
        self.validate_group(group, interlocutor_id)
        return self.extract_group_id(group)

    @staticmethod
    def validate_group(group: Any, interlocutor_id: str) -> None:
        if not isinstance(group, dict):
            raise SystemExit("Unable to resolve personal chat: unexpected response.")
        if group.get("interlocutorId") != interlocutor_id:
            raise SystemExit("Unable to resolve personal chat: interlocutor mismatch.")
        if group.get("type") != "PERSONAL":
            raise SystemExit("Unable to resolve personal chat: group is not PERSONAL.")
        if group.get("canWriteMessage") is not True:
            raise SystemExit("Unable to resolve personal chat: cannot write message.")

    @staticmethod
    def extract_group_id(group: dict[str, Any]) -> str:
        group_id = group.get("id")
        if not isinstance(group_id, str) or not group_id:
            raise SystemExit("Unable to resolve personal chat: missing group id.")
        return group_id


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


def add_save_env_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--save-env-local",
        action="store_true",
        help="Save returned auth tokens to .env.local without printing them.",
    )


def load_payload(
    args: argparse.Namespace,
    default_payload: dict[str, Any],
) -> dict[str, Any]:
    raw_body = args.body
    if args.body_file:
        raw_body = read_body_file(args.body_file)
    if raw_body is None:
        return default_payload
    try:
        return json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON body: {exc}") from exc


def read_body_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except OSError as exc:
        raise SystemExit(f"Unable to read body file: {exc}") from exc


def main() -> int:
    return DahCli().run()


if __name__ == "__main__":
    raise SystemExit(main())
