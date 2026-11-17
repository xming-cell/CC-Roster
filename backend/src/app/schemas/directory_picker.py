"""原生目录选择响应; 只返回路径, 不读取目录内容。"""

from pydantic import BaseModel, ConfigDict, model_validator


class DirectoryPickResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str | None = None
    cancelled: bool = False

    @model_validator(mode="after")
    def _check_path(self) -> "DirectoryPickResponse":
        if self.cancelled and self.path is not None:
            raise ValueError("取消选择时不能返回路径")
        if not self.cancelled and (self.path is None or not self.path.strip()):
            raise ValueError("未取消时必须返回目录路径")
        return self
