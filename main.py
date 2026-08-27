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

from auth_session import (
    auth_env_updates,
    auth_status,
    sanitize_auth_response,
    save_auth_env,
)
from cli_parser import build_parser
from dah_api import (
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
    TenantNotificationRequest,
    default_bill_debt_analytics_payload,
    load_env_file,
)
from debtor_notifications import (
    DebtorNotificationRequest,
    DebtorNotificationService,
    NotificationLedger,
    format_debtor_notification_report,
)
from debtor_reports import (
    DebtorAuditRequest,
    DebtorNextRequest,
    DebtorReportService,
    DebtorStructureRequest,
    DebtSnapshotRequest,
)

MISSING_MESSENGER_GROUP_ID_MESSAGE = "Missing messenger group id. Pass --group-id."
NO_TOKEN_COMMANDS = {
    "auth-status",
    "authentication-relogin",
    "authentication-web-login",
    "ledger-add-contact",
}
NO_BEARER_COMMANDS = {
    "authentication-relogin",
    "authentication-web-login",
    "ledger-add-contact",
}
READ_ONLY_COMMANDS = {
    "access",
    "auth-status",
    "publications-search",
    "publication-get",
    "bill-debt-analytics",
    "debtors-by-entrance",
    "debtors-next",
    "debtor-audit",
    "debt-snapshot",
    "feedback-order-list",
    "apartment-list",
    "money-transaction-bank-list",
    "messenger-group-messages",
    "messenger-groups-page",
    "messenger-personal-group-get",
}
DRY_RUN_READ_ONLY_COMMANDS = {
    "feedback-order-status",
    "messenger-send-message",
    "publication-save",
}
SEND_FLAG_READ_ONLY_COMMANDS = {
    "debtors-notify",
    "tenant-notification-send",
}


class DahCli:
    def __init__(self) -> None:
        load_env_file()
        self.parser = build_parser()

    def run(self, argv: list[str] | None = None) -> int:
        args = self.parser.parse_args(argv)
        client = DahApiClient(self._build_config(args))

        try:
            response_data = self._dispatch(args, client)
        except DahHttpError as exc:
            if self._should_retry_auth(args, exc):
                return self._run_after_auth_refresh(args)
            return self._print_http_error(exc)
        except DahRequestError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        self._print_response(response_data, args.compact)
        return 0

    def _run_after_auth_refresh(self, args: argparse.Namespace) -> int:
        try:
            self._refresh_auth(args)
            response_data = self._dispatch(args, DahApiClient(self._build_config(args)))
        except DahHttpError as exc:
            return self._print_http_error(exc)
        except DahRequestError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        self._print_response(response_data, args.compact)
        return 0

    def _refresh_auth(self, args: argparse.Namespace) -> None:
        client = DahApiClient(
            DahApiConfig(
                base_url=args.base_url,
                tab_id=args.tab_id,
                origin=args.origin,
                referer=args.referer,
                user_agent=args.user_agent,
                timeout=args.timeout,
                require_token=False,
            )
        )
        response = self._refresh_auth_response(client)
        updates = auth_env_updates(response)
        if not updates.get("DAH_BEARER_TOKEN"):
            raise DahRequestError("DAH auth refresh did not return a bearer token.")
        save_auth_env(response)
        os.environ.update(updates)

    @staticmethod
    def _refresh_auth_response(client: DahApiClient) -> Any:
        refresh_token = os.getenv("DAH_REFRESH_TOKEN")
        if not refresh_token:
            return DahCli._web_login_auth_response(client)
        try:
            return client.authentication_relogin(
                AuthenticationReloginRequest(
                    refresh_token=refresh_token,
                    device_id=os.getenv("DAH_DEVICE_ID"),
                )
            )
        except DahHttpError as exc:
            if exc.status_code != 401:
                raise
            return DahCli._web_login_auth_response(client)

    @staticmethod
    def _web_login_auth_response(client: DahApiClient) -> Any:
        login = os.getenv("DAH_LOGIN", "")
        password = os.getenv("DAH_PASSWORD", "")
        if login and password:
            return client.authentication_web_login(
                AuthenticationWebLoginRequest(login=login, password=password)
            )
        raise DahRequestError(
            "Unable to refresh DAH auth. Set DAH_REFRESH_TOKEN "
            "or DAH_LOGIN/DAH_PASSWORD."
        )

    @staticmethod
    def _should_retry_auth(args: argparse.Namespace, exc: DahHttpError) -> bool:
        return (
            exc.status_code == 401
            and "invalid_access_token" in exc.body
            and command_is_read_only(args)
        )

    def _dispatch(self, args: argparse.Namespace, client: DahApiClient) -> Any:
        handlers = {
            "access": client.get_access,
            "auth-status": lambda: self._auth_status(client),
            "authentication-web-login": lambda: self._login_or_preview(args, client),
            "authentication-relogin": lambda: self._relogin_or_preview(args, client),
            "authentication-exit": client.authentication_exit,
            "publications-search": lambda: client.search_publications(
                self._build_publications_request(args)
            ),
            "publication-get": lambda: client.get_publication(args.publication_id),
            "publication-save": lambda: self._save_or_preview_publication(args, client),
            "bill-debt-analytics": lambda: client.get_bill_debt_analytics(
                self._build_bill_debt_analytics_request(args)
            ),
            "debtors-by-entrance": lambda: DebtorReportService(client).by_entrance(
                self._build_debtor_structure_request(args)
            ),
            "debtors-next": lambda: DebtorReportService(client).next_to_notify(
                self._build_debtor_next_request(args)
            ),
            "debtor-audit": lambda: DebtorReportService(client).audit(
                self._build_debtor_audit_request(args)
            ),
            "debtors-notify": lambda: self._debtors_notify(args, client),
            "feedback-order-list": lambda: client.list_feedback_orders(
                self._build_feedback_order_list_request(args)
            ),
            "feedback-order-status": lambda: self._update_or_preview_order_status(
                args, client
            ),
            "debt-snapshot": lambda: DebtorReportService(client).snapshot(
                self._build_debt_snapshot_request(args)
            ),
            "ledger-add-contact": lambda: self._ledger_add_contact(args),
            "tenant-notification-send": lambda: (
                self._send_or_preview_tenant_notification(args, client)
            ),
            "apartment-list": lambda: client.list_apartments(
                self._build_apartment_list_request(args)
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
            "messenger-personal-group-get": lambda: client.get_messenger_personal_group(
                MessengerPersonalGroupRequest(args.interlocutor_id)
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

    def _update_or_preview_order_status(
        self,
        args: argparse.Namespace,
        client: DahApiClient,
    ) -> Any:
        request = FeedbackOrderStatusRequest(args.order_id, args.status)
        if args.dry_run:
            return request.to_payload()
        return client.update_feedback_order_status(request)

    def _send_or_preview_tenant_notification(
        self,
        args: argparse.Namespace,
        client: DahApiClient,
    ) -> Any:
        request = self._build_tenant_notification_request(args)
        if not args.send:
            return request.to_payload()
        validate_tenant_notification_confirmation(args, request)
        return client.send_tenant_notification(request)

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

    def _build_config(self, args: argparse.Namespace) -> DahApiConfig:
        no_token_command = args.command in NO_TOKEN_COMMANDS
        token = (
            ""
            if args.command in NO_BEARER_COMMANDS
            else os.getenv("DAH_BEARER_TOKEN", "")
        )
        if not token:
            if not no_token_command:
                raise SystemExit(MISSING_BEARER_TOKEN_MESSAGE)
        return DahApiConfig(
            token=token,
            base_url=args.base_url,
            tab_id=args.tab_id,
            origin=args.origin,
            referer=args.referer,
            user_agent=args.user_agent,
            timeout=args.timeout,
            require_token=not no_token_command,
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
            **debtor_request_kwargs(args),
            apartment_numbers=args.apartment_number,
            confirm_apartment_numbers=args.confirm,
            exclude_notified_today=args.exclude_notified_today,
            ledger_path=args.ledger_path,
            write_ledger=not args.no_ledger,
            max_send=debtor_notify_max_send(args),
            message_template=args.message_template,
            notification_method=args.notification_method,
            recipient_scope=args.recipient_scope,
            send=args.send,
        )

    def _build_debtor_next_request(
        self,
        args: argparse.Namespace,
    ) -> DebtorNextRequest:
        return DebtorNextRequest(
            **debtor_request_kwargs(args),
            exclude_notified_today=args.exclude_notified_today,
            ledger_path=args.ledger_path,
            output_format=args.format,
            notification_method=args.notification_method,
            recipient_scope=args.recipient_scope,
        )

    def _build_debtor_structure_request(
        self,
        args: argparse.Namespace,
    ) -> DebtorStructureRequest:
        return DebtorStructureRequest(
            **debtor_request_kwargs(args, include_limit=False),
            area_adjusted=args.area_adjusted,
        )

    def _build_debtor_audit_request(
        self,
        args: argparse.Namespace,
    ) -> DebtorAuditRequest:
        return DebtorAuditRequest(
            apartment_number=args.apartment_number,
            from_date=args.from_date,
            association_id=args.association_id,
            date=args.date,
            debt_filter_accruals=args.debt_filter_accruals,
            kind=args.kind,
            ledger_path=args.ledger_path,
        )

    def _build_debt_snapshot_request(
        self,
        args: argparse.Namespace,
    ) -> DebtSnapshotRequest:
        return DebtSnapshotRequest(
            **debtor_request_kwargs(args, include_limit=False),
            snapshot_path=args.snapshot_path,
            write_snapshot=args.write,
        )

    @staticmethod
    def _ledger_add_contact(args: argparse.Namespace) -> dict[str, Any]:
        return NotificationLedger(args.ledger_path).record_manual_contact(
            apartment_number=args.apartment_number,
            status=args.status,
            debt=args.debt,
            recipient_scope=args.recipient_scope,
            recipients=args.recipients,
            note=args.note,
            kind=args.kind,
            contact_date=args.contact_date,
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

    def _build_tenant_notification_request(
        self,
        args: argparse.Namespace,
    ) -> TenantNotificationRequest:
        payload = load_payload(
            args,
            TenantNotificationRequest(
                association_id=args.association_id,
                tenant_id=args.tenant_id or "",
                text=args.text or "",
                text_html=args.text_html,
            ).to_payload(),
        )
        details = payload.get("details", [])
        if not isinstance(details, list):
            raise SystemExit("Tenant notification details must be a JSON array.")
        request = TenantNotificationRequest(
            association_id=args.association_id,
            tenant_id=str(payload.get("tenantId", "")),
            text=str(payload.get("text", "")),
            text_html=payload.get("textHtml"),
            details=details,
        )
        validate_tenant_notification_request(request)
        return request

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


def debtor_notify_max_send(args: argparse.Namespace) -> int | None:
    return 1 if args.one_by_one else args.max_send


def command_is_read_only(args: argparse.Namespace) -> bool:
    return (
        args.command in READ_ONLY_COMMANDS
        or (args.command in DRY_RUN_READ_ONLY_COMMANDS and bool(args.dry_run))
        or (args.command in SEND_FLAG_READ_ONLY_COMMANDS and not bool(args.send))
    )


def debtor_request_kwargs(
    args: argparse.Namespace,
    *,
    include_limit: bool = True,
) -> dict[str, Any]:
    kwargs = {
        "association_id": args.association_id,
        "date": args.date,
        "debt_filter_accruals": args.debt_filter_accruals,
        "min_debt": args.min_debt,
        "kind": args.kind,
    }
    if include_limit:
        kwargs["limit"] = args.limit
    return kwargs


def validate_tenant_notification_request(request: TenantNotificationRequest) -> None:
    if not request.tenant_id:
        raise SystemExit("Missing tenant id. Pass --tenant-id or body tenantId.")
    if not request.text:
        raise SystemExit("Missing tenant notification text. Pass --text or body text.")


def validate_tenant_notification_confirmation(
    args: argparse.Namespace,
    request: TenantNotificationRequest,
) -> None:
    if args.confirm_tenant_id != request.tenant_id:
        raise SystemExit(
            "Missing --confirm-tenant-id matching tenantId for tenant notification."
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
