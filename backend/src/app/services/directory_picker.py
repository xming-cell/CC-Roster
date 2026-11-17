"""系统原生文件夹选择器: 仅由本机后端在用户点击时调用。

命令参数一律以列表传递, 不拼 shell 字符串; 输出只返回绝对路径, 不读取目录内容。
"""

from __future__ import annotations

import json
import posixpath
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Never, Protocol

from app.core.errors import AppError
from app.schemas.directory_picker import DirectoryPickResponse

DEFAULT_TIMEOUT_SECONDS = 120


class CommandRunner(Protocol):
    def __call__(
        self, command: Sequence[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]: ...


class DirectoryPickerService:
    def __init__(
        self,
        *,
        platform: str | None = None,
        which: Callable[[str], str | None] = shutil.which,
        runner: CommandRunner | None = None,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._platform = sys.platform if platform is None else platform
        self._which = which
        self._runner = subprocess.run if runner is None else runner
        self._timeout = timeout

    def pick(self) -> DirectoryPickResponse:
        if self._platform == "win32":
            return self._pick_windows()
        if self._platform == "darwin":
            return self._pick_macos()
        if self._platform.startswith("linux"):
            return self._pick_linux()
        raise AppError(
            "DIRECTORY_PICKER_UNAVAILABLE",
            "当前平台不支持系统目录选择, 请手动输入路径",
            501,
        )

    def _pick_windows(self) -> DirectoryPickResponse:
        powershell = self._which("powershell.exe") or self._which("powershell")
        if powershell is None:
            self._unavailable()
        script = (
            "$ErrorActionPreference='Stop'; "
            "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); "
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$d=New-Object System.Windows.Forms.FolderBrowserDialog; "
            "$d.Description='选择项目目录'; "
            "$d.ShowNewFolderButton=$true; "
            "$r=$d.ShowDialog(); "
            "if($r -eq [System.Windows.Forms.DialogResult]::OK){"
            "@{path=$d.SelectedPath;cancelled=$false}|ConvertTo-Json -Compress"
            "}else{@{path=$null;cancelled=$true}|ConvertTo-Json -Compress}"
        )
        completed = self._run([powershell, "-NoProfile", "-STA", "-Command", script])
        if completed.returncode != 0:
            self._failed(completed.stderr)
        try:
            payload = json.loads(completed.stdout.strip())
        except json.JSONDecodeError as exc:
            raise AppError(
                "DIRECTORY_PICKER_FAILED", "目录选择器返回了无法解析的结果", 502
            ) from exc
        if bool(payload.get("cancelled")):
            return DirectoryPickResponse(cancelled=True)
        path = payload.get("path")
        if not isinstance(path, str) or not path.strip():
            self._failed("empty path")
        return DirectoryPickResponse(path=self._normalize(path))

    def _pick_macos(self) -> DirectoryPickResponse:
        osascript = self._which("osascript")
        if osascript is None:
            self._unavailable()
        script = (
            'set chosenFolder to choose folder with prompt "选择项目目录"\n'
            "return POSIX path of chosenFolder"
        )
        completed = self._run([osascript, "-e", script])
        if completed.returncode == 1:
            return DirectoryPickResponse(cancelled=True)
        if completed.returncode != 0:
            self._failed(completed.stderr)
        path = completed.stdout.strip()
        if not path:
            self._failed("empty path")
        return DirectoryPickResponse(path=self._normalize(path))

    def _pick_linux(self) -> DirectoryPickResponse:
        zenity = self._which("zenity")
        if zenity is not None:
            completed = self._run(
                [
                    zenity,
                    "--file-selection",
                    "--directory",
                    "--title=选择项目目录",
                ]
            )
        else:
            kdialog = self._which("kdialog")
            if kdialog is None:
                self._unavailable()
            completed = self._run([kdialog, "--getexistingdirectory", str(Path.home())])
        if completed.returncode == 1:
            return DirectoryPickResponse(cancelled=True)
        if completed.returncode != 0:
            self._failed(completed.stderr)
        path = completed.stdout.strip()
        if not path:
            self._failed("empty path")
        return DirectoryPickResponse(path=self._normalize(path))

    def _run(self, command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        try:
            return self._runner(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self._timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise AppError(
                "DIRECTORY_PICKER_TIMEOUT", "目录选择器等待超时, 请手动输入路径", 504
            ) from exc
        except OSError as exc:
            raise AppError("DIRECTORY_PICKER_UNAVAILABLE", "无法启动系统目录选择器", 501) from exc

    def _normalize(self, raw: str) -> str:
        if self._platform != "win32":
            return posixpath.normpath(raw)
        try:
            return str(Path(raw).expanduser().resolve())
        except OSError as exc:
            raise AppError("DIRECTORY_PICKER_FAILED", "目录选择器返回的路径无效", 502) from exc

    @staticmethod
    def _unavailable() -> Never:
        raise AppError(
            "DIRECTORY_PICKER_UNAVAILABLE",
            "当前平台没有可用的系统目录选择器, 请手动输入路径",
            501,
        )

    @staticmethod
    def _failed(detail: str) -> None:
        message = "目录选择器调用失败"
        if detail.strip():
            message += ": " + detail.strip()[:200]
        raise AppError("DIRECTORY_PICKER_FAILED", message, 502)
