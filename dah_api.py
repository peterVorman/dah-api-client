"""Object-oriented client for the DAH cabinet API."""

from __future__ import annotations

import gzip
import json
import os
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from time import time
from typing import Any

import certifi

DEFAULT_BASE_URL = "https://api.dah-online.com"
ALLOWED_API_HOST = "api.dah-online.com"
DEFAULT_ORIGIN = "https://cabinet.dah-online.com"
DEFAULT_REFERER = f"{DEFAULT_ORIGIN}/"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.0.0 Safari/537.36"
)
ENV_ASSIGNMENT_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")
MISSING_BEARER_TOKEN_MESSAGE = "Missing bearer token. Set DAH_BEARER_TOKEN."  # nosec B105
MISSING_ASSOCIATION_ID_MESSAGE = (
    "Unable to resolve a single association id from get_access. "
    "Set DAH_ASSOCIATION_ID or pass --association-id."
)


def default_ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context(
        cafile=os.getenv("SSL_CERT_FILE") or certifi.where()
    )


def load_env_file(
    path: str | os.PathLike[str] = ".env.local",
) -> None:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
    except FileNotFoundError:
        return

    for key, value in filter(None, map(_parse_env_assignment, lines)):
        if key not in os.environ:
            os.environ[key] = value


def _parse_env_assignment(raw_line: str) -> tuple[str, str] | None:
    match = ENV_ASSIGNMENT_RE.match(raw_line)
    if not match:
        return None

    return match.group(1), match.group(2).strip()


def default_bill_debt_analytics_payload(
    *,
    date: str | None = None,
    debt_filter_accruals: int = 1,
) -> dict[str, Any]:
    return {
        "pan": False,
        "sort": "BALANCE_ASC",
        "order": ["APARTMENT"],
        "owner": False,
        "debtFilterType": "ACCRUALS",
        "apartmentFilter": {},
        "debtFilterMonths": 0,
        "debtFilterAccruals": debt_filter_accruals,
        "splitApartmentName": False,
        "accrualTypesExclude": False,
        "flowItemsFilterExclude": False,
        "flowItemCategoriesExclude": False,
        "date": date or datetime.now().strftime("%Y-%m-%dT%H:%M"),
        "accrualTypes": [],
    }


@dataclass(slots=True)
class DahApiConfig:
    token: str = ""
    base_url: str = DEFAULT_BASE_URL
    tab_id: str | None = None
    origin: str = DEFAULT_ORIGIN
    referer: str = DEFAULT_REFERER
    user_agent: str = DEFAULT_USER_AGENT
    timeout: float = 30
    require_token: bool = True
    ssl_context: ssl.SSLContext = field(
        default_factory=default_ssl_context,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        if self.require_token and not self.token:
            raise ValueError(MISSING_BEARER_TOKEN_MESSAGE)
        parsed_url = urllib.parse.urlparse(self.base_url)
        if parsed_url.scheme != "https" or parsed_url.hostname != ALLOWED_API_HOST:
            raise ValueError(f"DAH base URL must be https://{ALLOWED_API_HOST}.")

    @classmethod
    def from_env(cls) -> "DahApiConfig":
        load_env_file()
        token = os.getenv("DAH_BEARER_TOKEN")
        if not token:
            raise ValueError(MISSING_BEARER_TOKEN_MESSAGE)
        return cls(
            token=token,
            base_url=os.getenv("DAH_BASE_URL", DEFAULT_BASE_URL),
            tab_id=os.getenv("DAH_TAB_ID"),
            origin=os.getenv("DAH_ORIGIN", DEFAULT_ORIGIN),
            referer=os.getenv("DAH_REFERER", DEFAULT_REFERER),
            user_agent=os.getenv("DAH_USER_AGENT", DEFAULT_USER_AGENT),
        )


@dataclass(slots=True)
class PublicationsSearchRequest:
    page: int = 0
    size: int = 5
    payload: dict[str, Any] = field(default_factory=lambda: {"statuses": ["PUBLISHED"]})


@dataclass(slots=True)
class AuthenticationWebLoginRequest:
    login: str = ""
    password: str = ""
    client_id: str = "DAH_CLIENT_WEB"

    def to_payload(self) -> dict[str, Any]:
        return {
            "clientId": self.client_id,
            "login": self.login,
            "password": self.password,
        }


@dataclass(slots=True)
class AuthenticationReloginRequest:
    refresh_token: str = ""
    device_id: str | None = None
    client_id: str = "DAH_CLIENT_WEB"
    client_type: str = "WEB"

    def to_payload(self) -> dict[str, Any]:
        payload = {
            "clientId": self.client_id,
            "clientType": self.client_type,
            "refreshToken": self.refresh_token,
        }
        if self.device_id:
            payload["deviceId"] = self.device_id
        return payload


@dataclass(slots=True)
class PublicationSaveRequest:
    payload: dict[str, Any]

    def to_payload(self, association_id: str) -> dict[str, Any]:
        if self.payload.get("associationId"):
            return self.payload
        return {**self.payload, "associationId": association_id}


@dataclass(slots=True)
class BillDebtAnalyticsRequest:
    association_id: str | None = None
    payload: dict[str, Any] = field(default_factory=default_bill_debt_analytics_payload)


@dataclass(slots=True)
class FeedbackOrderListRequest:
    association_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FeedbackOrderStatusRequest:
    order_id: str
    status: str = "DONE"

    def to_payload(self) -> dict[str, Any]:
        return {"status": self.status}


@dataclass(slots=True)
class MoneyTransactionBankListRequest:
    association_id: str | None = None
    page: int = 0
    size: int = 50
    payload: dict[str, Any] = field(default_factory=lambda: {"direction": "EXPENSE"})


@dataclass(slots=True)
class MessengerGroupMessagesRequest:
    group_id: str
    page: int = 0
    size: int = 50
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MessengerGroupsPageRequest:
    page: int = 0
    size: int = 50
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MessengerMessageRequest:
    group_id: str
    payload: str
    message_type: str = "TEXT"
    create_time: int = field(default_factory=lambda: int(time() * 1000))

    def to_payload(self) -> dict[str, Any]:
        return {
            "createTime": self.create_time,
            "groupId": self.group_id,
            "payload": self.payload,
            "type": self.message_type,
        }


class DahRequestError(RuntimeError):
    """Raised for network and request-layer errors."""


class DahHttpError(RuntimeError):
    def __init__(self, status_code: int, reason: str, body: str = "") -> None:
        super().__init__(f"HTTP {status_code} {reason}")
        self.status_code = status_code
        self.reason = reason
        self.body = body


class DahApiClient:
    def __init__(self, config: DahApiConfig) -> None:
        self.config = config
        self._default_association_id: str | None = None

    def get_access(self, *, tab_id: str | None = None) -> Any:
        return self.request_json(
            method="GET",
            path="/organization/v1/access",
            tab_id=tab_id,
        )

    def authentication_web_login(
        self,
        request: AuthenticationWebLoginRequest | None = None,
        *,
        tab_id: str | None = None,
    ) -> Any:
        login_request = request or AuthenticationWebLoginRequest()
        return self.request_json(
            method="POST",
            path="/authentication/web/login",
            payload=login_request.to_payload(),
            tab_id=tab_id,
        )

    def authentication_relogin(
        self,
        request: AuthenticationReloginRequest | None = None,
        *,
        tab_id: str | None = None,
    ) -> Any:
        relogin_request = request or AuthenticationReloginRequest()
        return self.request_json(
            method="POST",
            path="/authentication/relogin",
            payload=relogin_request.to_payload(),
            tab_id=tab_id,
        )

    def search_publications(
        self,
        request: PublicationsSearchRequest | None = None,
        *,
        tab_id: str | None = None,
    ) -> Any:
        search_request = request or PublicationsSearchRequest()
        payload = search_request.payload
        if not payload.get("associationId"):
            payload = {
                **payload,
                "associationId": self.get_default_association_id(),
            }
        return self.request_json(
            method="POST",
            path="/publications/search",
            query={"page": search_request.page, "size": search_request.size},
            payload=payload,
            tab_id=tab_id,
        )

    def get_publication(
        self,
        publication_id: str,
        *,
        tab_id: str | None = None,
    ) -> Any:
        publication_id = urllib.parse.quote(publication_id, safe="")
        return self.request_json(
            method="GET",
            path=f"/publications/get/{publication_id}",
            tab_id=tab_id,
        )

    def save_publication(
        self,
        request: PublicationSaveRequest,
        *,
        tab_id: str | None = None,
    ) -> Any:
        association_id = (
            request.payload.get("associationId") or self.get_default_association_id()
        )
        payload = request.to_payload(association_id)
        return self.request_json(
            method="PUT" if payload.get("id") else "POST",
            path=(
                "/publications/v2/edit/web"
                if payload.get("id")
                else "/publications/v2/add/web"
            ),
            payload=payload,
            tab_id=tab_id,
        )

    def get_bill_debt_analytics(
        self,
        request: BillDebtAnalyticsRequest | None = None,
        *,
        tab_id: str | None = None,
    ) -> Any:
        report_request = request or BillDebtAnalyticsRequest()
        association_id = urllib.parse.quote(
            report_request.association_id or self.get_default_association_id(),
            safe="",
        )
        return self.request_json(
            method="POST",
            path=f"/accounting/v1/report/bill/{association_id}/debt/analytics",
            payload=report_request.payload,
            tab_id=tab_id,
        )

    def list_feedback_orders(
        self,
        request: FeedbackOrderListRequest | None = None,
        *,
        tab_id: str | None = None,
    ) -> Any:
        list_request = request or FeedbackOrderListRequest()
        association_id = urllib.parse.quote(
            list_request.association_id or self.get_default_association_id(),
            safe="",
        )
        return self.request_json(
            method="POST",
            path=f"/feedback/order/list/{association_id}",
            payload=list_request.payload,
            tab_id=tab_id,
        )

    def update_feedback_order_status(
        self,
        request: FeedbackOrderStatusRequest,
        *,
        tab_id: str | None = None,
    ) -> Any:
        order_id = urllib.parse.quote(request.order_id, safe="")
        return self.request_json(
            method="PUT",
            path=f"/feedback/order/comment/{order_id}",
            payload=request.to_payload(),
            tab_id=tab_id,
        )

    def list_money_transaction_bank(
        self,
        request: MoneyTransactionBankListRequest | None = None,
        *,
        tab_id: str | None = None,
    ) -> Any:
        list_request = request or MoneyTransactionBankListRequest()
        association_id = urllib.parse.quote(
            list_request.association_id or self.get_default_association_id(),
            safe="",
        )
        return self.request_json(
            method="POST",
            path=f"/accounting/v1/money/transaction/{association_id}/list/bank",
            query={"page": list_request.page, "size": list_request.size},
            payload=list_request.payload,
            tab_id=tab_id,
        )

    def list_messenger_group_messages(
        self,
        request: MessengerGroupMessagesRequest,
        *,
        tab_id: str | None = None,
    ) -> Any:
        group_id = urllib.parse.quote(request.group_id, safe="")
        return self.request_json(
            method="POST",
            path=f"/messenger/groups/{group_id}/messages",
            query={"page": request.page, "size": request.size},
            payload=request.payload,
            tab_id=tab_id,
        )

    def list_messenger_groups(
        self,
        request: MessengerGroupsPageRequest | None = None,
        *,
        tab_id: str | None = None,
    ) -> Any:
        groups_request = request or MessengerGroupsPageRequest()
        return self.request_json(
            method="POST",
            path="/messenger/groups/page",
            query={"page": groups_request.page, "size": groups_request.size},
            payload=groups_request.payload,
            tab_id=tab_id,
        )

    def send_messenger_message(
        self,
        request: MessengerMessageRequest,
        *,
        tab_id: str | None = None,
    ) -> Any:
        return self.request_json(
            method="POST",
            path="/messenger/messages",
            payload=request.to_payload(),
            tab_id=tab_id,
        )

    def get_default_association_id(self) -> str:
        if self._default_association_id is None:
            association_ids = self._extract_access_association_ids(self.get_access())
            unique_ids = sorted(set(association_ids))
            if len(unique_ids) != 1:
                raise DahRequestError(MISSING_ASSOCIATION_ID_MESSAGE)
            self._default_association_id = unique_ids[0]
        return self._default_association_id

    @staticmethod
    def _extract_access_association_ids(access_data: Any) -> list[str]:
        if not isinstance(access_data, dict):
            return []

        return [
            item["id"]
            for item in DahApiClient._iter_access_items(access_data)
            if isinstance(item.get("id"), str) and item.get("id")
        ]

    @staticmethod
    def _iter_access_items(access_data: dict[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for access_key in ("managerAccess", "tenantAccess"):
            access_items = access_data.get(access_key, [])
            if isinstance(access_items, list):
                items.extend(item for item in access_items if isinstance(item, dict))
        return items

    def request_json(
        self,
        *,
        method: str,
        path: str,
        query: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
        tab_id: str | None = None,
    ) -> Any:
        request = self._build_request(
            method=method,
            path=path,
            query=query,
            payload=payload,
            tab_id=tab_id,
        )
        try:
            with urllib.request.urlopen(  # nosec B310
                request,
                timeout=self.config.timeout,
                context=self.config.ssl_context,
            ) as response:
                return json.loads(self._read_response_text(response))
        except urllib.error.HTTPError as exc:
            raise DahHttpError(
                exc.code,
                exc.reason,
                self._read_response_text(exc),
            ) from exc
        except urllib.error.URLError as exc:
            raise DahRequestError(f"Request failed: {exc}") from exc

    def _build_request(
        self,
        *,
        method: str,
        path: str,
        query: dict[str, Any] | None,
        payload: dict[str, Any] | None,
        tab_id: str | None,
    ) -> urllib.request.Request:
        url = f"{self.config.base_url.rstrip('/')}{path}"
        if query:
            url = f"{url}?{urllib.parse.urlencode(query)}"

        data = None
        if payload is not None:
            data = json.dumps(payload, separators=(",", ":")).encode("utf-8")

        return urllib.request.Request(
            url=url,
            data=data,
            headers=self._build_headers(
                has_json_body=payload is not None, tab_id=tab_id
            ),
            method=method,
        )

    def _build_headers(
        self, *, has_json_body: bool, tab_id: str | None
    ) -> dict[str, str]:
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Origin": self.config.origin,
            "Referer": self.config.referer,
            "User-Agent": self.config.user_agent,
        }
        if self.config.token:
            headers["Authorization"] = f"Bearer {self.config.token}"
        effective_tab_id = tab_id if tab_id is not None else self.config.tab_id
        if effective_tab_id:
            headers["X-DAH-TabId"] = effective_tab_id
        if has_json_body:
            headers["Content-Type"] = "application/json"
        return headers

    def _read_response_text(self, response: Any) -> str:
        data = response.read()
        if response.headers.get("Content-Encoding", "").lower() == "gzip":
            data = gzip.decompress(data)
        return data.decode("utf-8")
