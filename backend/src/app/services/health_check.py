"""用户主动触发的一次性档案连通性检测。"""

import http.client
import json
import ssl
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import IO, Protocol
from urllib.parse import urlsplit, urlunsplit

from app.core.clock import utc_now
from app.core.errors import AppError
from app.repositories.profiles import ProfileRepository
from app.repositories.secrets import SecretStore
from app.schemas.health_check import HealthCheckRequest, HealthCheckResponse, HealthCheckStatus
from app.schemas.profile import Profile

HEALTH_CHECK_TIMEOUT_SECONDS = 10
MAX_RESPONSE_BYTES = 64 * 1024


class HealthCheckHttpResponse(Protocol):
    status: int
    body: bytes


class HealthCheckTransport(Protocol):
    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes,
        timeout: int,
    ) -> HealthCheckHttpResponse: ...


class _Response:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self.body = body


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        request: urllib.request.Request,
        response: IO[bytes],
        code: int,
        message: str,
        headers: http.client.HTTPMessage,
        new_url: str,
    ) -> urllib.request.Request | None:
        return None


class UrllibHealthCheckTransport:
    """标准库传输实现; 将重定向响应作为普通 HTTP 结果交给服务分类。"""

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes,
        timeout: int,
    ) -> _Response:
        request = urllib.request.Request(
            url,
            data=body,
            headers=dict(headers),
            method="POST",
        )
        opener = urllib.request.build_opener(_NoRedirect())
        try:
            response = opener.open(request, timeout=timeout)
        except urllib.error.HTTPError as error:
            try:
                body = error.read(MAX_RESPONSE_BYTES + 1)[:MAX_RESPONSE_BYTES]
            finally:
                error.close()
            return _Response(error.code, body)
        with response:
            return _Response(
                response.status,
                response.read(MAX_RESPONSE_BYTES + 1)[:MAX_RESPONSE_BYTES],
            )


class HealthCheckService:
    def __init__(
        self,
        repository: ProfileRepository,
        secrets: SecretStore,
        transport: HealthCheckTransport,
    ) -> None:
        self._repository = repository
        self._secrets = secrets
        self._transport = transport

    def check(
        self,
        profile_id: str,
        payload: HealthCheckRequest,
    ) -> HealthCheckResponse:
        profile = self._repository.get_profile(profile_id)
        if profile is None:
            raise AppError("PROFILE_NOT_FOUND", f"档案不存在: {profile_id}", 404)

        model = payload.model
        model_ids = {entry.id for entry in profile.models}
        if model is None and profile.models:
            model = profile.models[0].id
        elif model is not None and model not in model_ids:
            raise AppError("VALIDATION_ERROR", "所选模型不在该档案的模型清单中", 422)

        if model is None:
            return _result(
                profile,
                None,
                "MODEL_REQUIRED",
                False,
                None,
                "档案尚未添加模型。请先添加模型后再体检",
            )

        secret: str | None = None
        if profile.secret_ref is not None:
            try:
                secret = self._secrets.get(profile.secret_ref)
            except AppError:
                return _result(
                    profile,
                    model,
                    "SECRET_STORE_ERROR",
                    False,
                    None,
                    "密钥存储暂时不可用。未发起网络请求",
                )
            if secret is None:
                return _result(
                    profile,
                    model,
                    "SECRET_MISSING",
                    False,
                    None,
                    "档案引用的密钥不存在。未发起网络请求",
                )

        request_url, headers, body = _build_probe(profile, model, secret)
        started = time.perf_counter_ns()
        try:
            response = self._transport.post(
                request_url,
                headers=headers,
                body=body,
                timeout=HEALTH_CHECK_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            duration_ms = _elapsed_ms(started)
            return _result(
                profile,
                model,
                "TIMEOUT",
                True,
                duration_ms,
                "请求超时。请检查接口地址或稍后重试",
            )
        except urllib.error.URLError as error:
            duration_ms = _elapsed_ms(started)
            if isinstance(error.reason, TimeoutError):
                return _result(
                    profile,
                    model,
                    "TIMEOUT",
                    True,
                    duration_ms,
                    "请求超时。请检查接口地址或稍后重试",
                )
            return _result(
                profile,
                model,
                "INVALID_ADDRESS",
                True,
                duration_ms,
                "无法连接到该接口地址。请检查地址、网络或 TLS 配置",
            )
        except (ssl.SSLError, OSError, http.client.HTTPException):
            duration_ms = _elapsed_ms(started)
            return _result(
                profile,
                model,
                "INVALID_ADDRESS",
                True,
                duration_ms,
                "无法连接到该接口地址。请检查地址、网络或 TLS 配置",
            )

        duration_ms = _elapsed_ms(started)
        status, message = _classify_response(response)
        return _result(profile, model, status, True, duration_ms, message)


def _result(
    profile: Profile,
    model: str | None,
    status: HealthCheckStatus,
    attempted: bool,
    duration_ms: int | None,
    message: str,
) -> HealthCheckResponse:
    return HealthCheckResponse(
        profile_id=profile.id,
        model=model,
        status=status,
        attempted=attempted,
        duration_ms=duration_ms,
        message=message,
        checked_at=utc_now(),
    )


def _build_probe(
    profile: Profile,
    model: str,
    secret: str | None,
) -> tuple[str, dict[str, str], bytes]:
    parts = urlsplit(profile.base_url)
    path = parts.path.rstrip("/")
    if not path.endswith("/v1"):
        path += "/v1"
    if profile.protocol == "anthropic":
        path += "/messages"
        headers = {"anthropic-version": "2023-06-01"}
        request_body = {
            "model": model,
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "Health check"}],
        }
        if secret is not None:
            headers["x-api-key"] = secret
    else:
        path += "/chat/completions"
        headers = {}
        request_body = {
            "model": model,
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "Health check"}],
            "stream": False,
        }
        if secret is not None:
            headers["Authorization"] = f"Bearer {secret}"
    headers["Content-Type"] = "application/json"
    url = urlunsplit((parts.scheme, parts.netloc, path, parts.query, ""))
    return url, headers, json.dumps(request_body).encode("utf-8")


def _classify_response(
    response: HealthCheckHttpResponse,
) -> tuple[HealthCheckStatus, str]:
    model_error = _is_model_error(response.body)
    if response.status in (401, 403):
        return "INVALID_CREDENTIALS", "认证失败。请检查档案中的密钥"
    if response.status == 429:
        return "RATE_LIMITED", "请求过于频繁。请稍后再试"
    if model_error:
        return "MODEL_NOT_FOUND", "供应商不接受该模型。请确认模型名称是否可用"
    if response.status == 404:
        return "INVALID_ADDRESS", "接口路径不存在。请检查接口地址"
    if 200 <= response.status < 300:
        try:
            payload = json.loads(response.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return "UNKNOWN", "供应商返回了无法识别的响应"
        if not isinstance(payload, dict):
            return "UNKNOWN", "供应商返回了无法识别的响应"
        return "CONNECTED", "连接成功。档案地址、凭证和模型可用"
    if 300 <= response.status < 400:
        return "INVALID_ADDRESS", "接口返回重定向。已为保护密钥而拒绝跟随"
    return "UNKNOWN", "供应商返回了暂时无法识别的错误"


def _is_model_error(body: bytes) -> bool:
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    error = payload.get("error")
    if not isinstance(error, dict):
        return False
    details = " ".join(
        value.lower() for value in error.values() if isinstance(value, str) and len(value) < 2048
    )
    markers = ("model_not_found", "model not found", "unknown model", "model does not exist")
    return any(marker in details for marker in markers) or (
        "model" in details and ("not found" in details or "does not exist" in details)
    )


def _elapsed_ms(started: int) -> int:
    return max(0, (time.perf_counter_ns() - started) // 1_000_000)
