"""全局异常处理器: 所有错误响应统一为 `{code, message}`。

覆盖四类来源: 业务异常、请求校验失败、框架 404 / 405、未知异常。
未知异常只返回通用文案, traceback、路径与异常原文一律留在服务端。
"""

import logging
from collections.abc import Mapping

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import AppError, ErrorDetails, ErrorResponse
from app.core.redaction import redact_text

logger = logging.getLogger(__name__)

_VALIDATION_ERROR = "VALIDATION_ERROR"
_INTERNAL_ERROR = "INTERNAL_ERROR"

_HTTP_ERROR_CODES: dict[int, str] = {
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
}
_HTTP_ERROR_MESSAGES: dict[int, str] = {
    404: "请求的资源不存在",
    405: "请求方法不被允许",
}


def _error_response(
    status_code: int,
    code: str,
    message: str,
    headers: Mapping[str, str] | None = None,
    details: ErrorDetails | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(
            code=code,
            message=redact_text(message),
            details=details,
        ).model_dump(exclude_none=True),
        headers=headers,
    )


def _format_validation_error(exc: RequestValidationError) -> str:
    """只拼字段位置与 Pydantic 的 msg, 不回显原始输入值。"""
    details: list[str] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"])
        message = str(error["msg"])
        details.append(f"{location}: {message}" if location else message)
    return f"请求参数不合法: {'; '.join(details)}" if details else "请求参数不合法"


async def _handle_app_error(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return _error_response(
        exc.status_code,
        exc.code,
        exc.message,
        details=exc.details,
    )


async def _handle_validation_error(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    return _error_response(422, _VALIDATION_ERROR, _format_validation_error(exc))


async def _handle_http_exception(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = _HTTP_ERROR_CODES.get(exc.status_code, "HTTP_ERROR")
    message = _HTTP_ERROR_MESSAGES.get(exc.status_code, str(exc.detail))
    return _error_response(exc.status_code, code, message, headers=exc.headers)


async def _handle_unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled application error (%s)", type(exc).__name__)
    return _error_response(500, _INTERNAL_ERROR, "服务器内部错误")


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(Exception, _handle_unexpected_error)
