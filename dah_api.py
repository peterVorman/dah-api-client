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
from typing import Any, Callable


DEFAULT_BASE_URL = "https://api.dah-online.com"
DEFAULT_ORIGIN = "https://cabinet.dah-online.com"
DEFAULT_REFERER = f"{DEFAULT_ORIGIN}/"
DEFAULT_ASSOCIATION_ID = "251b4ef9-e0ed-49bd-80a0-3b6cbe322b05"
DEFAULT_MESSENGER_GROUP_ID = "65664e74-cf14-4076-b793-931f1921ae8e"
DEFAULT_BEARER_TOKEN = (
    "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJ1c2VyX25hbWUiOiIrMzgwOTk0NjA0MTY0Iiwic2Vzc2lvbiI6eyJzZXNzaW9uVHMi"
    "OjE3NzU1MDg4ODI2NDksInVzZXJJZCI6ImRjYzBiY2I5LTFmZjUtNGU2Yy05ZTlmLTBk"
    "ZjA4Mzc0ZDBjNSIsImRldmljZUlkIjoiMjgyODA4ZGUtNzcxMS00Njc3LWFlYjAtY2Iz"
    "ZjhhMGQ0M2Y4IiwiY2xpZW50VHlwZSI6IldFQiIsImNsaWVudElkIjoiREFIX0NMSUVO"
    "VF9XRUIifSwicGVybWlzc2lvbnMiOnsiMDAwMDAwMDAwMDAwMDAwMEUwRkZGRkZGRkZG"
    "RkZGRkZGRkZGRkZGRjAzIjpbeyJ0IjoiMjUxYjRlZjktZTBlZC00OWJkLTgwYTAtM2I2"
    "Y2JlMzIyYjA1In1dfSwic2NvcGUiOlsiVVNFUiJdLCJwZXJtQyI6e30sImV4cCI6MTc3"
    "NTUxMjQ4MiwiY2xpZW50X2lkIjoiREFIX0NMSUVOVF9XRUIifQ."
    "LPniuR_qGCHGuBN4Xx8XELJGuH_0L6fqMBlru_iletX3tmlJhDXN9nobBCMjUa78yHLO1"
    "dKJkRixz3xWrtFRS9Z7Nve-bShzmDvAXYTzRrwdMP-PNkl5mNZjlDYspnB04MkYPM56nfu"
    "lW3sImtnMbChztuqEmmJirCg48nA47J1NSI0m-P-YF-LY05nKp_FY_jFTpz4AqcFVGEZu"
    "U_mTi6Ow94phTYv-KGiHq0NxNaNPFrbXacwWH__u_z97yCFkDZwI1LLOPfPB52szprdoG"
    "KpAuSuKS5hgePa6IO65Y4NglM1eWkCWLuUPv-l7s4GHi9F95YjwvK_fNo008RRyXg"
)
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.0.0 Safari/537.36"
)
ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


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

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = _strip_env_value(value.strip())
        if not ENV_KEY_RE.match(key):
            continue
        if override or key not in os.environ:
            os.environ[key] = value


def _strip_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def default_publications_payload() -> dict[str, Any]:
    return {
        "associationId": DEFAULT_ASSOCIATION_ID,
        "statuses": ["PUBLISHED"],
    }


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


def default_messenger_group_messages_payload() -> dict[str, Any]:
    return {}


def default_messenger_groups_page_payload() -> dict[str, Any]:
    return {}


@dataclass(slots=True)
class DahApiConfig:
    base_url: str = DEFAULT_BASE_URL
    token: str = DEFAULT_BEARER_TOKEN
    tab_id: str | None = None
    origin: str = DEFAULT_ORIGIN
    referer: str = DEFAULT_REFERER
    user_agent: str = DEFAULT_USER_AGENT
    timeout: float = 30
    insecure: bool = False

    @classmethod
    def from_env(cls) -> "DahApiConfig":
        load_env_file()
        return cls(
            base_url=os.getenv("DAH_BASE_URL", DEFAULT_BASE_URL),
            token=os.getenv("DAH_BEARER_TOKEN", DEFAULT_BEARER_TOKEN),
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
    association_id: str = DEFAULT_ASSOCIATION_ID
    payload: dict[str, Any] = field(default_factory=default_bill_debt_analytics_payload)


@dataclass(slots=True)
class FeedbackOrderListRequest:
    association_id: str = DEFAULT_ASSOCIATION_ID
    payload: dict[str, Any] = field(default_factory=default_feedback_order_list_payload)


@dataclass(slots=True)
class MessengerGroupMessagesRequest:
    group_id: str = DEFAULT_MESSENGER_GROUP_ID
    page: int = 0
    size: int = 50
    payload: dict[str, Any] = field(default_factory=default_messenger_group_messages_payload)

    def query_params(self) -> dict[str, int]:
        return {
            "page": self.page,
            "size": self.size,
        }


@dataclass(slots=True)
class MessengerGroupsPageRequest:
    page: int = 0
    size: int = 50
    payload: dict[str, Any] = field(default_factory=default_messenger_groups_page_payload)

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
    """Raised for network and TLS errors."""


class DahHttpError(DahApiError):
    def __init__(self, status_code: int, reason: str, body: str = "") -> None:
        super().__init__(f"HTTP {status_code} {reason}")
        self.status_code = status_code
        self.reason = reason
        self.body = body


class DahApiClient:
    def __init__(
        self,
        config: DahApiConfig,
        notifier: Callable[[str], None] | None = None,
    ) -> None:
        self.config = config
        self.notifier = notifier

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
        return self.request_json(
            method="POST",
            path="/publications/search",
            query=search_request.query_params(),
            payload=search_request.payload,
            tab_id=tab_id,
        )

    def get_bill_debt_analytics(
        self,
        request: BillDebtAnalyticsRequest | None = None,
        *,
        tab_id: str | None = None,
    ) -> Any:
        report_request = request or BillDebtAnalyticsRequest()
        association_id = urllib.parse.quote(report_request.association_id, safe="")
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
        association_id = urllib.parse.quote(list_request.association_id, safe="")
        return self.request_json(
            method="POST",
            path=f"/feedback/order/list/{association_id}",
            payload=list_request.payload,
            tab_id=tab_id,
        )

    def list_messenger_group_messages(
        self,
        request: MessengerGroupMessagesRequest | None = None,
        *,
        tab_id: str | None = None,
    ) -> Any:
        messages_request = request or MessengerGroupMessagesRequest()
        group_id = urllib.parse.quote(messages_request.group_id, safe="")
        return self.request_json(
            method="POST",
            path=f"/messenger/groups/{group_id}/messages",
            query=messages_request.query_params(),
            payload=messages_request.payload,
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
        return self._perform_request(request)

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
            headers=self._build_headers(has_json_body=payload is not None, tab_id=tab_id),
            method=method,
        )

    def _build_headers(self, *, has_json_body: bool, tab_id: str | None) -> dict[str, str]:
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

    def _perform_request(self, request: urllib.request.Request) -> Any:
        verified_context = self._build_ssl_context()
        try:
            return self._request_json(request, verified_context)
        except urllib.error.HTTPError as exc:
            raise self._http_error(exc) from exc
        except (ssl.SSLCertVerificationError, urllib.error.URLError) as exc:
            if not self._is_ssl_verification_error(exc):
                raise DahRequestError(f"Request failed: {exc}") from exc
            if self.config.insecure:
                raise DahRequestError(
                    "TLS verification failed even with --insecure enabled."
                ) from exc
            self._notify("TLS verification failed; retrying once without certificate checks.")
            try:
                return self._request_json(request, ssl._create_unverified_context())
            except urllib.error.HTTPError as retry_exc:
                raise self._http_error(retry_exc) from retry_exc
            except (ssl.SSLCertVerificationError, urllib.error.URLError) as retry_exc:
                raise DahRequestError(f"Request failed: {retry_exc}") from retry_exc

    def _request_json(
        self,
        request: urllib.request.Request,
        context: ssl.SSLContext,
    ) -> Any:
        with urllib.request.urlopen(
            request,
            timeout=self.config.timeout,
            context=context,
        ) as response:
            return json.loads(self._decode_response(response))

    def _build_ssl_context(self) -> ssl.SSLContext:
        if self.config.insecure:
            return ssl._create_unverified_context()
        return ssl.create_default_context()

    def _decode_response(self, response: Any) -> str:
        data = response.read()
        if response.headers.get("Content-Encoding", "").lower() == "gzip":
            data = gzip.decompress(data)
        return data.decode("utf-8")

    def _http_error(self, exc: urllib.error.HTTPError) -> DahHttpError:
        return DahHttpError(exc.code, exc.reason, self._decode_response(exc))

    @staticmethod
    def _is_ssl_verification_error(exc: BaseException) -> bool:
        if isinstance(exc, ssl.SSLCertVerificationError):
            return True
        if isinstance(exc, urllib.error.URLError):
            return isinstance(exc.reason, ssl.SSLCertVerificationError)
        return False

    def _notify(self, message: str) -> None:
        if self.notifier is not None:
            self.notifier(message)
