"""Object-oriented client for the DAH cabinet API."""

from __future__ import annotations

import gzip
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from time import time
from typing import Any

DEFAULT_BASE_URL = "https://api.dah-online.com"
ALLOWED_API_HOST = "api.dah-online.com"
DEFAULT_ORIGIN = "https://cabinet.dah-online.com"
DEFAULT_REFERER = f"{DEFAULT_ORIGIN}/"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.0.0 Safari/537.36"
)
ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
MISSING_BEARER_TOKEN_MESSAGE = "Missing bearer token. Set DAH_BEARER_TOKEN."  # nosec B105
MISSING_MESSENGER_GROUP_ID_MESSAGE = (
    "Missing messenger group id. Set DAH_MESSENGER_GROUP_ID or pass --group-id."
)
MISSING_ASSOCIATION_ID_MESSAGE = (
    "Unable to resolve a single association id from get_access. "
    "Set DAH_ASSOCIATION_ID or pass --association-id."
)


def load_env_file(
    path: str | os.PathLike[str] = ".env.local",
    *,
    override: bool = False,
) -> None:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
    except FileNotFoundError:
        return

    for key, value in _EnvFileParser(lines).assignments():
        if override or key not in os.environ:
            os.environ[key] = value


@dataclass(slots=True)
class _EnvFileParser:
    lines: list[str]

    def assignments(self) -> list[tuple[str, str]]:
        assignments: list[tuple[str, str]] = []
        for raw_line in self.lines:
            assignment = self.parse_assignment(raw_line)
            if assignment is not None:
                assignments.append(assignment)
        return assignments

    def parse_assignment(self, raw_line: str) -> tuple[str, str] | None:
        line = self.normalize_line(raw_line)
        if "=" not in line:
            return None

        key, value = line.split("=", 1)
        clean_key = key.strip()
        if not ENV_KEY_RE.match(clean_key):
            return None
        return clean_key, self.strip_value(value)

    @staticmethod
    def normalize_line(raw_line: str) -> str:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            return ""
        if line.startswith("export "):
            return line[len("export ") :].lstrip()
        return line

    @staticmethod
    def strip_value(value: str) -> str:
        clean_value = value.strip()
        if len(clean_value) >= 2 and clean_value[0] == clean_value[-1]:
            if clean_value[0] in {"'", '"'}:
                return clean_value[1:-1]
        return clean_value


def default_publications_payload(
    association_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"statuses": ["PUBLISHED"]}
    if association_id:
        payload["associationId"] = association_id
    return payload


def current_report_date() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M")


def current_epoch_millis() -> int:
    return int(time() * 1000)


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
        "date": date or current_report_date(),
        "accrualTypes": [],
    }


def default_feedback_order_list_payload() -> dict[str, Any]:
    return {}


def default_money_transaction_bank_list_payload(
    *,
    direction: str = "EXPENSE",
    from_date: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "direction": direction,
    }
    if from_date:
        payload["from"] = from_date
    return payload


def default_messenger_group_messages_payload() -> dict[str, Any]:
    return {}


def default_messenger_groups_page_payload() -> dict[str, Any]:
    return {}


@dataclass(slots=True)
class DahApiConfig:
    token: str
    base_url: str = DEFAULT_BASE_URL
    tab_id: str | None = None
    origin: str = DEFAULT_ORIGIN
    referer: str = DEFAULT_REFERER
    user_agent: str = DEFAULT_USER_AGENT
    timeout: float = 30

    def __post_init__(self) -> None:
        if not self.token:
            raise ValueError(MISSING_BEARER_TOKEN_MESSAGE)
        self._validate_base_url()

    def _validate_base_url(self) -> None:
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
    payload: dict[str, Any] = field(default_factory=default_publications_payload)

    def query_params(self) -> dict[str, int]:
        return {
            "page": self.page,
            "size": self.size,
        }


@dataclass(slots=True)
class BillDebtAnalyticsRequest:
    association_id: str | None = None
    payload: dict[str, Any] = field(default_factory=default_bill_debt_analytics_payload)


@dataclass(slots=True)
class FeedbackOrderListRequest:
    association_id: str | None = None
    payload: dict[str, Any] = field(default_factory=default_feedback_order_list_payload)


@dataclass(slots=True)
class MoneyTransactionBankListRequest:
    association_id: str | None = None
    page: int = 0
    size: int = 50
    payload: dict[str, Any] = field(
        default_factory=default_money_transaction_bank_list_payload
    )

    def query_params(self) -> dict[str, int]:
        return {
            "page": self.page,
            "size": self.size,
        }


@dataclass(slots=True)
class MessengerGroupMessagesRequest:
    group_id: str
    page: int = 0
    size: int = 50
    payload: dict[str, Any] = field(
        default_factory=default_messenger_group_messages_payload
    )

    def query_params(self) -> dict[str, int]:
        return {
            "page": self.page,
            "size": self.size,
        }


@dataclass(slots=True)
class MessengerGroupsPageRequest:
    page: int = 0
    size: int = 50
    payload: dict[str, Any] = field(
        default_factory=default_messenger_groups_page_payload
    )

    def query_params(self) -> dict[str, int]:
        return {
            "page": self.page,
            "size": self.size,
        }


@dataclass(slots=True)
class MessengerMessageRequest:
    group_id: str
    payload: str
    message_type: str = "TEXT"
    create_time: int = field(default_factory=current_epoch_millis)

    def to_payload(self) -> dict[str, Any]:
        return {
            "createTime": self.create_time,
            "groupId": self.group_id,
            "payload": self.payload,
            "type": self.message_type,
        }


class DahApiError(RuntimeError):
    """Base error for DAH API failures."""


class DahRequestError(DahApiError):
    """Raised for network and request-layer errors."""


class DahHttpError(DahApiError):
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

    def search_publications(
        self,
        request: PublicationsSearchRequest | None = None,
        *,
        tab_id: str | None = None,
    ) -> Any:
        search_request = request or PublicationsSearchRequest()
        payload = self._payload_with_association_id(search_request.payload)
        return self.request_json(
            method="POST",
            path="/publications/search",
            query=search_request.query_params(),
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
            query=list_request.query_params(),
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
            query=request.query_params(),
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
            query=groups_request.query_params(),
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
            self._default_association_id = self._resolve_default_association_id(
                self.get_access(),
            )
        return self._default_association_id

    def _payload_with_association_id(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("associationId"):
            return payload
        return {
            **payload,
            "associationId": self.get_default_association_id(),
        }

    @classmethod
    def _resolve_default_association_id(cls, access_data: Any) -> str:
        association_ids = cls._extract_access_association_ids(access_data)
        unique_ids = sorted(set(association_ids))
        if len(unique_ids) != 1:
            raise DahRequestError(MISSING_ASSOCIATION_ID_MESSAGE)
        return unique_ids[0]

    @staticmethod
    def _extract_access_association_ids(access_data: Any) -> list[str]:
        if not isinstance(access_data, dict):
            return []

        return [
            association_id
            for item in DahApiClient._iter_access_items(access_data)
            if (association_id := DahApiClient._extract_access_item_id(item))
            is not None
        ]

    @staticmethod
    def _iter_access_items(access_data: dict[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for access_key in ("managerAccess", "tenantAccess"):
            access_items = access_data.get(access_key, [])
            if isinstance(access_items, list):
                items.extend(item for item in access_items if isinstance(item, dict))
        return items

    @staticmethod
    def _extract_access_item_id(item: dict[str, Any]) -> str | None:
        association_id = item.get("id")
        if isinstance(association_id, str) and association_id:
            return association_id
        return None

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
            "Authorization": f"Bearer {self.config.token}",
            "Origin": self.config.origin,
            "Referer": self.config.referer,
            "User-Agent": self.config.user_agent,
        }
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
