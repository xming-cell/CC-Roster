from pathlib import Path

import pytest

from app.adapters.base import ToolCapabilities, ToolDetection, ToolReadResult
from app.adapters.registry import (
    AdapterContext,
    AdapterRegistration,
    ToolRegistry,
    build_registry,
    default_context,
)
from app.core.errors import AppError


class StubAdapter:
    def __init__(self, adapter_id: str) -> None:
        self.id = adapter_id
        self.display_name = adapter_id
        self.capabilities = ToolCapabilities()
        self.managed_paths: tuple[Path, ...] = ()

    def detect(self) -> ToolDetection:
        return ToolDetection(installed=True, configured=False)

    def read(self) -> ToolReadResult:
        return ToolReadResult()


def make_context() -> AdapterContext:
    def which(_name: str) -> str | None:
        return None

    return AdapterContext(environ={}, home=Path("/home/test"), which=which)


def test_registry_preserves_explicit_registration_order() -> None:
    first = StubAdapter("first")
    second = StubAdapter("second")

    registry = ToolRegistry([first, second])

    assert [adapter.id for adapter in registry.adapters] == ["first", "second"]
    assert registry.get("second") is second


def test_registry_skips_duplicate_ids_with_warning() -> None:
    first = StubAdapter("same")
    duplicate = StubAdapter("same")

    registry = ToolRegistry([first, duplicate])

    assert registry.adapters == (first,)
    assert len(registry.warnings) == 1
    assert registry.warnings[0].code == "ADAPTER_ERROR"
    assert "same" in registry.warnings[0].message


def test_registry_get_unknown_id_raises_tool_not_found() -> None:
    registry = ToolRegistry([])

    with pytest.raises(AppError) as excinfo:
        registry.get("missing")

    assert excinfo.value.code == "TOOL_NOT_FOUND"
    assert excinfo.value.status_code == 404


def test_default_context_accepts_injected_environ_home_and_which() -> None:
    environ = {"PROBE_HOME": "/tmp/probe"}
    home = Path("/tmp/home")

    def which(_name: str) -> str | None:
        return "/usr/local/bin/probe"

    context = default_context(environ=environ, home=home, which=which)

    assert context.environ is environ
    assert context.home == home
    assert context.which is which


def test_build_registry_passes_injected_context_to_factories() -> None:
    seen: list[AdapterContext] = []

    def factory(context: AdapterContext) -> StubAdapter:
        seen.append(context)
        return StubAdapter("probe")

    context = make_context()

    registry = build_registry(
        context=context,
        registrations=[AdapterRegistration("probe", factory)],
    )

    assert seen == [context]
    assert registry.get("probe").id == "probe"
    assert registry.warnings == ()


def test_build_registry_isolates_failing_factory() -> None:
    def broken(_context: AdapterContext) -> StubAdapter:
        raise RuntimeError("boom")

    registry = build_registry(
        context=make_context(),
        registrations=[
            AdapterRegistration("broken", broken),
            AdapterRegistration("healthy", lambda _context: StubAdapter("healthy")),
        ],
    )

    assert [adapter.id for adapter in registry.adapters] == ["healthy"]
    assert len(registry.warnings) == 1
    assert registry.warnings[0].code == "ADAPTER_ERROR"
    assert "broken" in registry.warnings[0].message
    assert "boom" not in registry.warnings[0].message


def test_build_registry_skips_adapter_with_mismatched_id() -> None:
    registry = build_registry(
        context=make_context(),
        registrations=[AdapterRegistration("expected", lambda _context: StubAdapter("actual"))],
    )

    assert registry.adapters == ()
    assert len(registry.warnings) == 1
    assert registry.warnings[0].code == "ADAPTER_ERROR"
    assert "expected" in registry.warnings[0].message


def test_default_registry_registers_claude_and_codex_in_order(tmp_path: Path) -> None:
    def which(_name: str) -> str | None:
        return None

    context = AdapterContext(
        environ={
            "CLAUDE_CONFIG_DIR": str(tmp_path / "claude"),
            "CODEX_HOME": str(tmp_path / "codex"),
        },
        home=tmp_path / "home",
        which=which,
    )

    registry = build_registry(context=context)

    assert [adapter.id for adapter in registry.adapters] == [
        "claude-code",
        "codex-cli",
        "gemini-cli",
        "opencode",
    ]
    assert registry.warnings == ()
