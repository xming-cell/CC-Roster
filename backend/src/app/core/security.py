"""本地安全边界: 请求体大小限制。

监听地址由 `settings.host` 与启动命令保证仅 loopback; 这里拦截超大请求体,
统一返回 `{code: "PAYLOAD_TOO_LARGE", message}`, 避免本地接口被误用撑爆内存。
"""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import ErrorResponse

PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
_TOO_LARGE_MESSAGE = "请求体超过大小上限"


class RequestBodyLimitMiddleware:
    """纯 ASGI 中间件: 进入路由前读完请求体并校验大小。

    本地应用只处理小型 JSON 请求, 预读上限内的字节再回放, 比在流式读取中途
    中断响应更可控; Content-Length 与 chunked 两种传输方式都会被覆盖。
    """

    def __init__(self, app: ASGIApp, max_body_bytes: int) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declared = _declared_content_length(scope)
        if declared is not None and declared > self.max_body_bytes:
            await _send_too_large(send)
            return

        body, exceeded = await _read_body(receive, self.max_body_bytes)
        if exceeded:
            await _send_too_large(send)
            return
        if body is None:
            return

        replayed = False

        async def replay() -> Message:
            nonlocal replayed
            if replayed:
                return await receive()
            replayed = True
            return {"type": "http.request", "body": body, "more_body": False}

        await self.app(scope, replay, send)


def _declared_content_length(scope: Scope) -> int | None:
    for key, value in scope.get("headers", []):
        if key.lower() == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


async def _read_body(receive: Receive, limit: int) -> tuple[bytes | None, bool]:
    """读到请求体结束; 超限时返回 `(None, True)`, 客户端断开返回 `(None, False)`。"""
    body = bytearray()
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            return None, False
        body.extend(message.get("body", b""))
        if len(body) > limit:
            return None, True
        if not message.get("more_body", False):
            return bytes(body), False


async def _send_too_large(send: Send) -> None:
    payload = ErrorResponse(
        code=PAYLOAD_TOO_LARGE,
        message=_TOO_LARGE_MESSAGE,
    ).model_dump_json(exclude_none=True)
    body = payload.encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
