"""021 新手引导状态机: 安装 → 凭证 → 首条消息。"""

from __future__ import annotations

from app.adapters.registry import ToolRegistry
from app.core.errors import AppError
from app.repositories.chat import ChatRepository
from app.repositories.onboarding import OnboardingRepository
from app.repositories.profiles import ProfileRepository
from app.repositories.secrets import SecretStore
from app.schemas.onboarding import (
    OnboardingState,
    OnboardingUpdate,
    OnboardingView,
    StepState,
)

INSTALL_HINTS: dict[str, str] = {
    "claude-code": "安装 Claude Code: npm install -g @anthropic-ai/claude-code",
    "codex-cli": "安装 Codex CLI: npm install -g @openai/codex",
    "gemini-cli": "安装 Gemini CLI: npm install -g @google/gemini-cli",
    "opencode": "安装 OpenCode: 参考 https://opencode.ai 的官方安装说明",
}

COMPLIANCE_NOTE = (
    "本引导不代注册、不代购、不共享账号; 只使用你已有的官方工具与凭证。"
    "第三方中转的可用性与计费由对应服务商负责。"
)


class OnboardingService:
    def __init__(
        self,
        repository: OnboardingRepository,
        registry: ToolRegistry,
        profiles: ProfileRepository,
        secrets: SecretStore,
        chats: ChatRepository,
    ) -> None:
        self._repository = repository
        self._registry = registry
        self._profiles = profiles
        self._secrets = secrets
        self._chats = chats

    def get(self) -> OnboardingView:
        return _view(self._repository.load())

    def update(self, payload: OnboardingUpdate) -> OnboardingView:
        def change(state: OnboardingState) -> None:
            if payload.reset:
                state.current_step = "install"
                state.install = StepState()
                state.credentials = StepState()
                state.first_message = StepState()
                state.tool_id = None
                state.profile_id = None
                state.project_dir = None
                return
            if payload.tool_id is not None:
                if payload.tool_id != state.tool_id:
                    state.install = StepState()
                    state.credentials = StepState()
                    state.first_message = StepState()
                state.tool_id = payload.tool_id or None
            if payload.profile_id is not None:
                if payload.profile_id != state.profile_id:
                    state.credentials = StepState()
                    state.first_message = StepState()
                state.profile_id = payload.profile_id or None
            if payload.project_dir is not None:
                if payload.project_dir != state.project_dir:
                    state.first_message = StepState()
                state.project_dir = payload.project_dir or None
            _recompute_step(state)

        self._repository.mutate(change)
        return self.get()

    def check_install(self, payload: OnboardingUpdate) -> OnboardingView:
        self.update(payload)

        def change(current: OnboardingState) -> None:
            if current.tool_id is None:
                current.install = StepState(status="failed", message="先选择一个工具")
            else:
                try:
                    adapter = self._registry.get(current.tool_id)
                    detection = adapter.detect()
                except AppError as exc:
                    current.install = StepState(status="failed", message=exc.message)
                except Exception as exc:
                    current.install = StepState(
                        status="failed",
                        message=f"工具检测失败: {type(exc).__name__}",
                    )
                else:
                    if detection.installed:
                        current.install = StepState(
                            status="done",
                            message=f"已找到 {adapter.display_name}",
                        )
                    else:
                        hint = INSTALL_HINTS.get(current.tool_id, "请查看该工具的官方安装说明")
                        current.install = StepState(
                            status="failed", message=f"没有检测到工具; {hint}"
                        )
            _recompute_step(current)

        self._repository.mutate(change)
        return self.get()

    def check_credentials(self, payload: OnboardingUpdate) -> OnboardingView:
        self.update(payload)

        def change(current: OnboardingState) -> None:
            if current.profile_id is None:
                current.credentials = StepState(status="failed", message="先登记一份供应商档案")
            else:
                profile = self._profiles.get_profile(current.profile_id)
                if profile is None:
                    current.credentials = StepState(status="failed", message="档案不存在")
                elif not profile.models:
                    current.credentials = StepState(status="failed", message="档案没有模型清单")
                elif profile.secret_ref is None:
                    current.credentials = StepState(status="failed", message="档案没有可用密钥")
                else:
                    try:
                        secret = self._secrets.get(profile.secret_ref)
                    except AppError as exc:
                        secret = None
                        message = exc.message
                    else:
                        message = "密钥读取失败"
                    if not secret:
                        current.credentials = StepState(status="failed", message=message)
                    else:
                        current.credentials = StepState(
                            status="done",
                            message="凭证已就绪; 可在档案页主动体检, 本引导不会发起计费请求",
                        )
            _recompute_step(current)

        self._repository.mutate(change)
        return self.get()

    def check_first_message(self, payload: OnboardingUpdate) -> OnboardingView:
        self.update(payload)

        def change(current: OnboardingState) -> None:
            if current.tool_id is None or current.profile_id is None or current.project_dir is None:
                current.first_message = StepState(
                    status="failed",
                    message="先填写工具、档案与项目目录",
                )
            else:
                found = any(
                    session.tool_id == current.tool_id
                    and session.profile_id == current.profile_id
                    and session.project_dir == current.project_dir
                    and any(message.role == "user" for message in session.messages)
                    and any(message.role == "assistant" for message in session.messages)
                    for session in self._chats.load().sessions
                )
                if found:
                    current.first_message = StepState(
                        status="done",
                        message="已完成一次真实对话",
                    )
                else:
                    current.first_message = StepState(
                        status="failed",
                        message="还没有完成一次对话; 请到 /chat 发送第一条消息后再检查",
                    )
            _recompute_step(current)

        self._repository.mutate(change)
        return self.get()


def _recompute_step(state: OnboardingState) -> None:
    if (
        state.install.status == "done"
        and state.credentials.status == "done"
        and state.first_message.status == "done"
    ):
        state.current_step = "complete"
    elif state.install.status == "done" and state.credentials.status == "done":
        state.current_step = "first_message"
    elif state.install.status == "done":
        state.current_step = "credentials"
    else:
        state.current_step = "install"


def _view(state: OnboardingState) -> OnboardingView:
    return OnboardingView(
        current_step=state.current_step,
        install=state.install,
        credentials=state.credentials,
        first_message=state.first_message,
        tool_id=state.tool_id,
        profile_id=state.profile_id,
        project_dir=state.project_dir,
        updated_at=state.updated_at,
        chat_url="/chat",
        compliance_note=COMPLIANCE_NOTE,
    )
