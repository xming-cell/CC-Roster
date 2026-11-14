"""档案领域模型的校验契约。

只断言模型能 / 不能表达什么, 不测仓储与 API。
"""

from datetime import datetime

import pytest
from profile_fixtures import make_binding, make_profile, make_secret_ref, new_profile_id
from pydantic import ValidationError

from app.schemas.profile import ModelEntry, ProfileStore


def test_model_entry_strips_id_and_normalizes_blank_display_name() -> None:
    entry = ModelEntry(id="  gpt-5-codex  ", display_name="   ")

    assert entry.id == "gpt-5-codex"
    assert entry.display_name is None


def test_model_entry_keeps_trimmed_display_name() -> None:
    entry = ModelEntry(id="gpt-5", display_name=" GPT-5 ")

    assert entry.display_name == "GPT-5"


@pytest.mark.parametrize("model_id", ["", "   ", "x" * 121])
def test_model_entry_rejects_blank_or_overlong_id(model_id: str) -> None:
    with pytest.raises(ValidationError):
        ModelEntry(id=model_id)


def test_profile_requires_uuid4_id() -> None:
    with pytest.raises(ValidationError):
        make_profile(profile_id="not-a-uuid")


def test_profile_requires_timezone_aware_timestamps() -> None:
    with pytest.raises(ValidationError):
        make_profile(created_at=datetime(2026, 11, 10, 12, 0))


def test_profile_rejects_blank_name() -> None:
    with pytest.raises(ValidationError):
        make_profile("   ")


def test_profile_requires_secret_locator_to_match_its_id() -> None:
    with pytest.raises(ValidationError):
        make_profile(secret_ref=make_secret_ref(new_profile_id()))


def test_profile_store_defaults_to_schema_version_one_and_empty_lists() -> None:
    store = ProfileStore()

    assert store.schema_version == 1
    assert store.profiles == []
    assert store.bindings == []


def test_profile_store_rejects_duplicate_profile_ids() -> None:
    profile = make_profile("甲")
    duplicate = make_profile("乙", profile_id=profile.id)

    with pytest.raises(ValidationError):
        ProfileStore(profiles=[profile, duplicate])


def test_profile_store_rejects_duplicate_tool_bindings() -> None:
    profile = make_profile()
    first = make_binding(profile.id, "claude-code")
    second = make_binding(profile.id, "claude-code")

    with pytest.raises(ValidationError):
        ProfileStore(profiles=[profile], bindings=[first, second])


def test_profile_store_rejects_binding_to_unknown_profile() -> None:
    with pytest.raises(ValidationError):
        ProfileStore(bindings=[make_binding(new_profile_id())])
