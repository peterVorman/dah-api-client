#!/usr/bin/env python3
"""CLI wrapper for the DAH API client."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Iterable
from typing import Any

from dah_api import (
    DEFAULT_BASE_URL,
    DEFAULT_ORIGIN,
    DEFAULT_REFERER,
    DEFAULT_USER_AGENT,
    MISSING_BEARER_TOKEN_MESSAGE,
    MISSING_MESSENGER_GROUP_ID_MESSAGE,
    BillDebtAnalyticsRequest,
    DahApiClient,
    DahApiConfig,
    DahHttpError,
    DahRequestError,
    FeedbackOrderListRequest,
    MessengerGroupMessagesRequest,
    MessengerGroupsPageRequest,
    MessengerMessageRequest,
    MoneyTransactionBankListRequest,
    PublicationsSearchRequest,
    default_bill_debt_analytics_payload,
    default_feedback_order_list_payload,
    default_messenger_group_messages_payload,
    default_messenger_groups_page_payload,
    default_money_transaction_bank_list_payload,
    default_publications_payload,
    load_env_file,
)


class DahCli:
    def __init__(self) -> None:
        load_env_file()
        self.parser = self._build_parser()

    def run(self, argv: list[str] | None = None) -> int:
        args = self.parser.parse_args(argv)
        client = DahApiClient(self._build_config(args))

        try:
            response_data = self._dispatch_command(args, client)
        except DahHttpError as exc:
            print(f"HTTP {exc.status_code} {exc.reason}", file=sys.stderr)
            if exc.body:
                print(exc.body, file=sys.stderr)
            return 1
        except DahRequestError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        self._print_response(response_data, compact=args.compact)
        return 0

    def _dispatch_command(
        self,
        args: argparse.Namespace,
        client: DahApiClient,
    ) -> Any:
        handlers: dict[str, Callable[[], Any]] = {
            "access": client.get_access,
            "publications-search": lambda: client.search_publications(
                self._build_publications_request(args)
            ),
            "bill-debt-analytics": lambda: client.get_bill_debt_analytics(
                self._build_bill_debt_analytics_request(args)
            ),
            "feedback-order-list": lambda: client.list_feedback_orders(
                self._build_feedback_order_list_request(args)
            ),
            "money-transaction-bank-list": lambda: client.list_money_transaction_bank(
                self._build_money_transaction_bank_list_request(args)
            ),
            "messenger-group-messages": lambda: client.list_messenger_group_messages(
                self._build_messenger_group_messages_request(args)
            ),
            "messenger-groups-page": lambda: client.list_messenger_groups(
                self._build_messenger_groups_page_request(args)
            ),
            "messenger-send-message": lambda: self._send_or_preview_message(
                args, client
            ),
        }
        return handlers[args.command]()

    def _send_or_preview_message(
        self,
        args: argparse.Namespace,
        client: DahApiClient,
    ) -> Any:
        message_request = self._build_messenger_message_request(args, client)
        if args.dry_run:
            return message_request.to_payload()
        return client.send_messenger_message(message_request)

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

        publications_parser = subparsers.add_parser(
            "publications-search",
            help="POST /publications/search",
            description="Search publications.",
        )
        publications_parser.add_argument(
            "--page",
            type=int,
            default=0,
            help="0-based page number.",
        )
        publications_parser.add_argument(
            "--size",
            type=int,
            default=5,
            help="Page size.",
        )
        body_group = publications_parser.add_mutually_exclusive_group()
        body_group.add_argument(
            "--body",
            help="Inline JSON body to send to the endpoint.",
        )
        body_group.add_argument(
            "--body-file",
            help="Path to a JSON file containing the request body.",
        )

        debt_analytics_parser = subparsers.add_parser(
            "bill-debt-analytics",
            help="POST /accounting/v1/report/bill/{associationId}/debt/analytics",
            description="Fetch bill debt analytics.",
        )
        debt_analytics_parser.add_argument(
            "--association-id",
            default=os.getenv("DAH_ASSOCIATION_ID"),
            help=(
                "Association id path parameter. Defaults to DAH_ASSOCIATION_ID "
                "or a single id resolved from get_access."
            ),
        )
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
        debt_body_group = debt_analytics_parser.add_mutually_exclusive_group()
        debt_body_group.add_argument(
            "--body",
            help="Inline JSON body to send to the endpoint.",
        )
        debt_body_group.add_argument(
            "--body-file",
            help="Path to a JSON file containing the request body.",
        )

        feedback_order_parser = subparsers.add_parser(
            "feedback-order-list",
            help="POST /feedback/order/list/{associationId}",
            description="Fetch feedback order list.",
        )
        feedback_order_parser.add_argument(
            "--association-id",
            default=os.getenv("DAH_ASSOCIATION_ID"),
            help=(
                "Association id path parameter. Defaults to DAH_ASSOCIATION_ID "
                "or a single id resolved from get_access."
            ),
        )
        feedback_body_group = feedback_order_parser.add_mutually_exclusive_group()
        feedback_body_group.add_argument(
            "--body",
            help="Inline JSON body to send to the endpoint.",
        )
        feedback_body_group.add_argument(
            "--body-file",
            help="Path to a JSON file containing the request body.",
        )

        money_transaction_parser = subparsers.add_parser(
            "money-transaction-bank-list",
            help="POST /accounting/v1/money/transaction/{associationId}/list/bank",
            description="Fetch bank money transactions.",
        )
        money_transaction_parser.add_argument(
            "--association-id",
            default=os.getenv("DAH_ASSOCIATION_ID"),
            help=(
                "Association id path parameter. Defaults to DAH_ASSOCIATION_ID "
                "or a single id resolved from get_access."
            ),
        )
        money_transaction_parser.add_argument(
            "--page",
            type=int,
            default=0,
            help="0-based page number.",
        )
        money_transaction_parser.add_argument(
            "--size",
            type=int,
            default=50,
            help="Page size.",
        )
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
        money_transaction_body_group = (
            money_transaction_parser.add_mutually_exclusive_group()
        )
        money_transaction_body_group.add_argument(
            "--body",
            help="Inline JSON body to send to the endpoint.",
        )
        money_transaction_body_group.add_argument(
            "--body-file",
            help="Path to a JSON file containing the request body.",
        )

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
        messenger_parser.add_argument(
            "--page",
            type=int,
            default=0,
            help="0-based page number.",
        )
        messenger_parser.add_argument(
            "--size",
            type=int,
            default=50,
            help="Page size.",
        )
        messenger_body_group = messenger_parser.add_mutually_exclusive_group()
        messenger_body_group.add_argument(
            "--body",
            help="Inline JSON body to send to the endpoint.",
        )
        messenger_body_group.add_argument(
            "--body-file",
            help="Path to a JSON file containing the request body.",
        )

        messenger_groups_parser = subparsers.add_parser(
            "messenger-groups-page",
            help="POST /messenger/groups/page",
            description="Fetch messenger groups page.",
        )
        messenger_groups_parser.add_argument(
            "--page",
            type=int,
            default=0,
            help="0-based page number.",
        )
        messenger_groups_parser.add_argument(
            "--size",
            type=int,
            default=50,
            help="Page size.",
        )
        messenger_groups_body_group = (
            messenger_groups_parser.add_mutually_exclusive_group()
        )
        messenger_groups_body_group.add_argument(
            "--body",
            help="Inline JSON body to send to the endpoint.",
        )
        messenger_groups_body_group.add_argument(
            "--body-file",
            help="Path to a JSON file containing the request body.",
        )

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

        return parser

    def _build_config(self, args: argparse.Namespace) -> DahApiConfig:
        token = os.getenv("DAH_BEARER_TOKEN")
        if not token:
            raise SystemExit(MISSING_BEARER_TOKEN_MESSAGE)
        return DahApiConfig(
            token=token,
            base_url=args.base_url,
            tab_id=args.tab_id,
            origin=args.origin,
            referer=args.referer,
            user_agent=args.user_agent,
            timeout=args.timeout,
        )

    def _build_publications_request(
        self,
        args: argparse.Namespace,
    ) -> PublicationsSearchRequest:
        return PublicationsSearchRequest(
            page=args.page,
            size=args.size,
            payload=self._load_payload(
                args,
                default_publications_payload(os.getenv("DAH_ASSOCIATION_ID")),
            ),
        )

    def _build_bill_debt_analytics_request(
        self,
        args: argparse.Namespace,
    ) -> BillDebtAnalyticsRequest:
        return BillDebtAnalyticsRequest(
            association_id=args.association_id,
            payload=self._load_payload(
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
            payload=self._load_payload(args, default_feedback_order_list_payload()),
        )

    def _build_money_transaction_bank_list_request(
        self,
        args: argparse.Namespace,
    ) -> MoneyTransactionBankListRequest:
        return MoneyTransactionBankListRequest(
            association_id=args.association_id,
            page=args.page,
            size=args.size,
            payload=self._load_payload(
                args,
                default_money_transaction_bank_list_payload(
                    direction=args.direction,
                    from_date=args.from_date,
                ),
            ),
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
            payload=self._load_payload(
                args, default_messenger_group_messages_payload()
            ),
        )

    def _build_messenger_groups_page_request(
        self,
        args: argparse.Namespace,
    ) -> MessengerGroupsPageRequest:
        return MessengerGroupsPageRequest(
            page=args.page,
            size=args.size,
            payload=self._load_payload(args, default_messenger_groups_page_payload()),
        )

    def _build_messenger_message_request(
        self,
        args: argparse.Namespace,
        client: DahApiClient,
    ) -> MessengerMessageRequest:
        group_id = args.group_id
        if group_id is None:
            group_id = self._resolve_messenger_group_id(client, args.chat_name)

        kwargs: dict[str, Any] = {}
        if args.create_time is not None:
            kwargs["create_time"] = args.create_time

        return MessengerMessageRequest(
            group_id=group_id,
            payload=args.message,
            message_type=args.message_type,
            **kwargs,
        )

    def _resolve_messenger_group_id(
        self,
        client: DahApiClient,
        chat_name: str,
    ) -> str:
        expected_name = self._normalize_chat_name(chat_name)
        matches = self._find_messenger_group_matches(client, expected_name)
        return self._select_single_group_id(matches, chat_name)

    def _find_messenger_group_matches(
        self,
        client: DahApiClient,
        expected_name: str,
    ) -> list[dict[str, Any]]:
        matches: list[dict[str, Any]] = []
        for group in self._iter_messenger_groups(client):
            if self._normalize_chat_name(group.get("name", "")) == expected_name:
                matches.append(group)
        return matches

    def _iter_messenger_groups(
        self,
        client: DahApiClient,
    ) -> Iterable[dict[str, Any]]:
        page = 0
        size = 50

        while True:
            response_data = client.list_messenger_groups(
                MessengerGroupsPageRequest(page=page, size=size),
            )
            groups = self._extract_messenger_groups(response_data)
            yield from groups
            if response_data.get("last") is True:
                break
            total_pages = response_data.get("totalPages")
            page += 1
            if isinstance(total_pages, int) and page >= total_pages:
                break

    def _extract_messenger_groups(self, response_data: Any) -> list[dict[str, Any]]:
        if not isinstance(response_data, dict):
            raise SystemExit("Unable to resolve chat name: unexpected groups response.")

        groups = response_data.get("content", [])
        if not isinstance(groups, list):
            raise SystemExit("Unable to resolve chat name: missing groups content.")
        return [group for group in groups if isinstance(group, dict)]

    def _select_single_group_id(
        self,
        matches: list[dict[str, Any]],
        chat_name: str,
    ) -> str:
        self._ensure_group_match_count(matches, chat_name)
        return self._extract_group_id(matches[0], chat_name)

    def _ensure_group_match_count(
        self,
        matches: list[dict[str, Any]],
        chat_name: str,
    ) -> None:
        if not matches:
            raise SystemExit(f"Chat not found by exact name: {chat_name}")
        if len(matches) > 1:
            ids = self._format_group_ids(matches)
            raise SystemExit(
                f"Multiple chats found by exact name '{chat_name}'. "
                f"Use --group-id. Matches: {ids}",
            )

    @staticmethod
    def _format_group_ids(matches: list[dict[str, Any]]) -> str:
        return ", ".join(str(match.get("id", "")) for match in matches)

    @staticmethod
    def _extract_group_id(group: dict[str, Any], chat_name: str) -> str:
        group_id = group.get("id")
        if not isinstance(group_id, str) or not group_id:
            raise SystemExit(f"Chat '{chat_name}' has no usable id.")
        return group_id

    @staticmethod
    def _normalize_chat_name(name: str) -> str:
        return name.strip().casefold()

    def _load_payload(
        self,
        args: argparse.Namespace,
        default_payload: dict[str, Any],
    ) -> dict[str, Any]:
        raw_body = self._load_raw_body(args)
        if raw_body is None:
            return default_payload
        return self._parse_json_body(raw_body)

    def _load_raw_body(self, args: argparse.Namespace) -> str | None:
        if args.body_file:
            return self._read_body_file(args.body_file)
        return args.body

    @staticmethod
    def _read_body_file(path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return handle.read()
        except OSError as exc:
            raise SystemExit(f"Unable to read body file: {exc}") from exc

    @staticmethod
    def _parse_json_body(raw_body: str) -> dict[str, Any]:
        try:
            return json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSON body: {exc}") from exc

    @staticmethod
    def _print_response(data: Any, *, compact: bool) -> None:
        if compact:
            print(json.dumps(data, ensure_ascii=False))
        else:
            print(json.dumps(data, ensure_ascii=False, indent=2))


def main() -> int:
    return DahCli().run()


if __name__ == "__main__":
    raise SystemExit(main())
