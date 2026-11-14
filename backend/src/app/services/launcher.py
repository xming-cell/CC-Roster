"""启动器用例: 只看计划, 再显式启动; 不写任何工具配置。"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.adapters.registry import ToolRegistry
from app.core.errors import AppError
from app.repositories.profiles import ProfileRepository
from app.repositories.secrets import SecretStore
from app.schemas.launcher import (
    LaunchBlocker,
    LaunchBlockerCode,
    LaunchPreview,
    LaunchRequest,
    LaunchResponse,
)
from app.schemas.profile import Profile


class TerminalSpawner(Protocol):
    def spawn(self, command: Sequence[str], cwd: Path, env: Mapping[str, str]) -> int: ...


class SubprocessTerminalSpawner:
    """Windows 用新控制台; macOS / Linux 交给常见终端模拟器。"""

    def __init__(self, platform: str | None = None) -> None:
        self._platform = sys.platform if platform is None else platform

    def spawn(self, command: Sequence[str], cwd: Path, env: Mapping[str, str]) -> int:
        merged_env = dict(env)
        if self._platform == "win32":
            process = subprocess.Popen(
                list(command),
                cwd=str(cwd),
                env=merged_env,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
            return process.pid
        if self._platform == "darwin":
            script = f"cd {shlex.quote(str(cwd))} && exec {shlex.join(command)}"
            process = subprocess.Popen(
                [
                    "osascript",
                    "-e",
                    f'tell application "Terminal" to do script "{_osa_escape(script)}"',
                ],
                env=merged_env,
            )
            return process.pid
        if self._platform.startswith("linux"):
            script = f"cd {shlex.quote(str(cwd))} && exec {shlex.join(command)}"
            process = subprocess.Popen(
                ["x-terminal-emulator", "-e", "sh", "-c", script],
                env=merged_env,
            )
            return process.pid
        raise OSError(f"unsupported platform: {self._platform}")


@dataclass(frozen=True, slots=True)
class _ToolLaunchSpec:
    executable: str
    protocol: str
    env_names: tuple[str, str, str]
    command_args: tuple[str, ...] = ()


_SPECS: dict[str, _ToolLaunchSpec] = {
    "claude-code": _ToolLaunchSpec(
        executable="claude",
        protocol="anthropic",
        env_names=("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_MODEL"),
    ),
    "codex-cli": _ToolLaunchSpec(
        executable="codex",
        protocol="openai",
        env_names=("OPENAI_BASE_URL", "OPENAI_API_KEY", "CODEX_MODEL"),
    ),
    "gemini-cli": _ToolLaunchSpec(
        executable="gemini",
        protocol="openai",
        env_names=("GOOGLE_GEMINI_BASE_URL", "GEMINI_API_KEY", "GEMINI_MODEL"),
    ),
    "opencode": _ToolLaunchSpec(
        executable="opencode",
        protocol="openai",
        env_names=("OPENAI_BASE_URL", "OPENCODE_API_KEY", "OPENCODE_MODEL"),
    ),
}


class LaunchService:
    def __init__(
        self,
        registry: ToolRegistry,
        profiles: ProfileRepository,
        secrets: SecretStore,
        *,
        which: Callable[[str], str | None] | None,
        spawner: TerminalSpawner,
        platform: str,
    ) -> None:
        self._registry = registry
        self._profiles = profiles
        self._secrets = secrets
        self._which = which
        self._spawner = spawner
        self._platform = platform

    def preview(self, request: LaunchRequest) -> LaunchPreview:
        profile = self._profile(request.profile_id)
        spec = _SPECS.get(request.tool_id)
        blockers: list[LaunchBlocker] = []
        if spec is None:
            raise AppError("TOOL_NOT_FOUND", f"未知工具: {request.tool_id}", 404)
        adapter = self._registry.get(request.tool_id)
        if request.tool_id not in _SPECS or not adapter.capabilities.launch:
            blockers.append(_blocker("PLATFORM_UNSUPPORTED", "这个工具暂不支持从应用内启动"))
        executable = self._resolve_executable(spec.executable)
        if executable is None:
            blockers.append(
                _blocker("TOOL_NOT_INSTALLED", f"没有找到 {spec.executable} 命令, 请先安装该工具")
            )
        if profile.protocol != spec.protocol:
            blockers.append(
                _blocker(
                    "PROTOCOL_MISMATCH",
                    f"{adapter.display_name} 需要 {spec.protocol} 档案, "
                    f"当前档案是 {profile.protocol}",
                )
            )
        secret = self._read_secret(profile)
        if secret is None:
            blockers.append(_blocker("SECRET_MISSING", "档案没有可用密钥, 无法启动"))
        project = Path(request.project_dir)
        if not project.exists():
            blockers.append(
                _blocker("PROJECT_DIR_NOT_FOUND", f"项目目录不存在: {request.project_dir}")
            )
        elif not project.is_dir():
            blockers.append(
                _blocker("PROJECT_DIR_NOT_DIRECTORY", f"项目路径不是目录: {request.project_dir}")
            )
        model = request.model or (profile.models[0].id if profile.models else None)
        if model is None:
            blockers.append(_blocker("MODEL_MISSING", "档案没有模型清单, 请先添加模型"))
        if self._platform not in {"win32", "darwin"} and not self._platform.startswith("linux"):
            blockers.append(
                _blocker("PLATFORM_UNSUPPORTED", f"当前平台不支持启动终端: {self._platform}")
            )

        command = [executable or spec.executable, *spec.command_args]
        if request.tool_id == "codex-cli" and model is not None:
            command.extend(["--model", model])
        return LaunchPreview(
            tool_id=request.tool_id,
            profile_id=profile.id,
            model=model,
            project_dir=request.project_dir,
            executable=executable,
            command=command,
            environment_keys=list(spec.env_names),
            blockers=blockers,
            can_launch=not blockers,
        )

    def environment(self, request: LaunchRequest) -> dict[str, str]:
        """按档案生成子进程环境; 密钥只存在于内存中的 env, 不进入响应。"""
        profile = self._profile(request.profile_id)
        spec = _SPECS.get(request.tool_id)
        if spec is None:
            raise AppError("TOOL_NOT_FOUND", f"未知工具: {request.tool_id}", 404)
        secret = self._read_secret(profile)
        if secret is None:
            raise AppError("SECRET_MISSING", "档案没有可用密钥", 400)
        model = request.model or (profile.models[0].id if profile.models else "")
        return {
            spec.env_names[0]: profile.base_url,
            spec.env_names[1]: secret,
            spec.env_names[2]: model,
        }

    def launch(self, request: LaunchRequest) -> LaunchResponse:
        preview = self.preview(request)
        if not preview.can_launch:
            message = "; ".join(blocker.message for blocker in preview.blockers)
            raise AppError("LAUNCH_BLOCKED", message or "启动条件不满足", 409)
        profile = self._profile(request.profile_id)
        spec = _SPECS[request.tool_id]
        secret = self._read_secret(profile)
        if secret is None:
            raise AppError("LAUNCH_BLOCKED", "档案没有可用密钥, 无法启动", 409)
        env = {
            spec.env_names[0]: profile.base_url,
            spec.env_names[1]: secret,
            spec.env_names[2]: preview.model or "",
        }
        try:
            pid = self._spawner.spawn(preview.command, Path(request.project_dir), env)
        except OSError as exc:
            raise AppError("LAUNCH_FAILED", f"终端启动失败: {type(exc).__name__}", 500) from exc
        return LaunchResponse(
            tool_id=request.tool_id,
            profile_id=profile.id,
            project_dir=request.project_dir,
            launched=True,
            pid=pid,
            message="已在所选目录打开终端; 若工具已在运行, 请在新窗口中确认它读取的是本次档案。",
        )

    def _profile(self, profile_id: str) -> Profile:
        profile = self._profiles.get_profile(profile_id)
        if profile is None:
            raise AppError("PROFILE_NOT_FOUND", "档案不存在", 404)
        return profile

    def _read_secret(self, profile: Profile) -> str | None:
        if profile.secret_ref is None:
            return None
        try:
            return self._secrets.get(profile.secret_ref)
        except AppError:
            return None

    def _resolve_executable(self, name: str) -> str | None:
        if self._which is None:
            return None
        result = self._which(name)
        return result if result else None


def _blocker(code: LaunchBlockerCode, message: str) -> LaunchBlocker:
    return LaunchBlocker(code=code, message=message)


def _osa_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def terminal_argv(command: Sequence[str], platform: str, cwd: Path) -> list[str]:
    """把工具命令包装成平台终端命令; 用户输入不以未经引用的形式拼进 shell。"""
    if platform == "win32":
        executable = command[0].lower() if command else ""
        if executable.endswith((".cmd", ".bat")):
            return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", *command]
        return list(command)
    script = f"cd {shlex.quote(str(cwd))} && exec {shlex.join(command)}"
    if platform == "darwin":
        osa = f'tell application "Terminal" to do script "{_osa_escape(script)}"'
        return ["osascript", "-e", osa]
    if platform.startswith("linux"):
        return ["x-terminal-emulator", "-e", "sh", "-c", script]
    raise OSError(f"unsupported platform: {platform}")
