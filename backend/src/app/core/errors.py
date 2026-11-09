"""统一错误模型。

业务代码只抛 `AppError`, 由 `app.api.error_handlers` 转成固定形状 `{code, message}`;
错误码是前端可判断的稳定契约, message 是给人看的说明。
"""

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    code: str
    message: str


class AppError(Exception):
    """可预期的业务错误。未知异常不允许伪装成 AppError。"""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
