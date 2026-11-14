"""SecretStore 契约: keyring 优先、文件回退、路由、补偿与脱敏。

测试全部注入假 keyring / 临时目录, 不触碰真实系统钥匙串。
"""

import json
import stat
import sys
import uuid
from pathlib import Path

import pytest
from profile_fixtures import FakeKeyring, make_secret_ref, new_profile_id

from app.core.errors import AppError
from app.repositories.secrets import (
    KEYRING_SERVICE_NAME,
    FileSecretStore,
    KeyringSecretStore,
    build_secret_store,
    rollback_secret,
)
from app.schemas.profile import SecretRef, SecretStoreStatus

SECRET = "sk-ant-fixture-1234567890abcdef"
OTHER_SECRET = "sk-ant-fixture-fedcba0987654321"


def make_file_ref(profile_id: str) -> SecretRef:
    return SecretRef(id=str(uuid.uuid4()), backend="file", locator=profile_id)


def test_keyring_store_roundtrip_uses_service_and_profile_locator() -> None:
    fake = FakeKeyring()
    store = KeyringSecretStore(fake)
    profile_id = new_profile_id()

    ref = store.put(profile_id, SECRET)

    assert ref.backend == "keyring"
    assert ref.locator == profile_id
    assert fake.values == {(KEYRING_SERVICE_NAME, profile_id): SECRET}
    assert store.get(ref) == SECRET

    store.delete(ref)
    store.delete(ref)
    assert fake.values == {}


def test_keyring_store_get_missing_returns_none() -> None:
    store = KeyringSecretStore(FakeKeyring())

    assert store.get(make_secret_ref(new_profile_id())) is None


def test_keyring_read_failure_is_readable_and_hides_secret() -> None:
    fake = FakeKeyring()
    store = KeyringSecretStore(fake)
    ref = store.put(new_profile_id(), SECRET)
    fake.fail_get = True

    with pytest.raises(AppError) as excinfo:
        store.get(ref)

    assert excinfo.value.code == "SECRET_STORE_ERROR"
    assert SECRET not in excinfo.value.message
    assert SECRET not in str(excinfo.value)


def test_keyring_write_failure_is_readable_and_hides_secret() -> None:
    fake = FakeKeyring()
    fake.fail_set = True
    store = KeyringSecretStore(fake)

    with pytest.raises(AppError) as excinfo:
        store.put(new_profile_id(), SECRET)

    assert excinfo.value.code == "SECRET_STORE_ERROR"
    assert SECRET not in excinfo.value.message


def test_keyring_unavailable_rejects_operations_without_fallback() -> None:
    fake = FakeKeyring()
    store = KeyringSecretStore(fake, available=False)

    with pytest.raises(AppError) as excinfo:
        store.put(new_profile_id(), SECRET)

    assert excinfo.value.code == "SECRET_STORE_ERROR"
    assert fake.values == {}


def test_secret_ref_and_status_serialization_never_include_plaintext() -> None:
    fake = FakeKeyring()
    store = KeyringSecretStore(fake)
    ref = store.put(new_profile_id(), SECRET)
    status = SecretStoreStatus(backend="keyring")

    payload = ref.model_dump_json() + status.model_dump_json()

    assert SECRET not in payload
    assert "locator" in payload


def test_file_store_roundtrip_writes_plaintext_json_with_0600(tmp_path: Path) -> None:
    store = FileSecretStore(tmp_path)
    profile_id = new_profile_id()

    ref = store.put(profile_id, SECRET)

    path = tmp_path / "secrets.json"
    assert ref.backend == "file"
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "secrets": {profile_id: SECRET},
    }
    if sys.platform != "win32":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert store.get(ref) == SECRET

    store.delete(ref)
    assert store.get(ref) is None


def test_file_store_missing_file_is_empty_and_delete_does_not_create_it(tmp_path: Path) -> None:
    store = FileSecretStore(tmp_path)
    ref = make_file_ref(new_profile_id())

    assert store.get(ref) is None
    store.delete(ref)

    assert not (tmp_path / "secrets.json").exists()


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        json.dumps({"schema_version": 2, "secrets": {}}),
        json.dumps({"schema_version": 1, "secrets": []}),
        json.dumps({"schema_version": 1, "secrets": {"profile": 1}}),
    ],
)
def test_file_store_corrupt_file_reports_error_and_keeps_bytes(
    tmp_path: Path,
    payload: str,
) -> None:
    path = tmp_path / "secrets.json"
    path.write_text(payload, encoding="utf-8")
    original = path.read_bytes()

    with pytest.raises(AppError) as excinfo:
        FileSecretStore(tmp_path).get(make_file_ref(new_profile_id()))

    assert excinfo.value.code == "SECRET_STORE_ERROR"
    assert path.read_bytes() == original


def test_file_store_write_failure_keeps_original_and_hides_secret(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FileSecretStore(tmp_path)
    store.put(new_profile_id(), SECRET)
    path = tmp_path / "secrets.json"
    original = path.read_bytes()

    def fail_write(_path: Path, _data: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("app.repositories.secrets.write_json_atomic", fail_write)

    with pytest.raises(AppError) as excinfo:
        store.put(new_profile_id(), OTHER_SECRET)

    assert excinfo.value.code == "SECRET_STORE_ERROR"
    assert path.read_bytes() == original
    assert OTHER_SECRET not in excinfo.value.message


def test_auto_prefers_keyring_when_available(tmp_path: Path) -> None:
    fake = FakeKeyring()
    store = build_secret_store(tmp_path, keyring_store=KeyringSecretStore(fake))

    status = store.status()

    assert status.backend == "keyring"
    assert status.fallback is False
    assert status.message is None

    ref = store.put(new_profile_id(), SECRET)
    assert ref.backend == "keyring"
    assert store.get(ref) == SECRET
    assert not (tmp_path / "secrets.json").exists()


def test_auto_falls_back_to_file_and_reports_banner(tmp_path: Path) -> None:
    fake = FakeKeyring()
    store = build_secret_store(
        tmp_path,
        keyring_store=KeyringSecretStore(fake, available=False),
    )

    status = store.status()

    assert status.backend == "file"
    assert status.fallback is True
    assert status.message is not None
    assert "secrets.json" in status.message

    profile_id = new_profile_id()
    ref = store.put(profile_id, SECRET)
    assert ref.backend == "file"
    assert fake.values == {}
    assert store.get(ref) == SECRET


def test_explicit_file_mode_uses_file_even_when_keyring_available(tmp_path: Path) -> None:
    fake = FakeKeyring()
    store = build_secret_store(
        tmp_path,
        mode="file",
        keyring_store=KeyringSecretStore(fake),
    )

    status = store.status()

    assert status.backend == "file"
    assert status.fallback is True
    assert status.message is not None
    assert "CC_ROSTER_SECRET_BACKEND=file" in status.message

    ref = store.put(new_profile_id(), SECRET)
    assert ref.backend == "file"
    assert fake.values == {}


def test_explicit_keyring_unavailable_refuses_writes_without_silent_fallback(
    tmp_path: Path,
) -> None:
    fake = FakeKeyring()
    store = build_secret_store(
        tmp_path,
        mode="keyring",
        keyring_store=KeyringSecretStore(fake, available=False),
    )

    status = store.status()
    assert status.backend == "unavailable"
    assert status.fallback is False

    with pytest.raises(AppError) as excinfo:
        store.put(new_profile_id(), SECRET)

    assert excinfo.value.code == "SECRET_STORE_ERROR"
    assert not (tmp_path / "secrets.json").exists()


def test_both_backends_unavailable_reports_unavailable(tmp_path: Path) -> None:
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory", encoding="utf-8")
    store = build_secret_store(
        blocked,
        keyring_store=KeyringSecretStore(FakeKeyring(), available=False),
        file_store=FileSecretStore(blocked),
    )

    status = store.status()

    assert status.backend == "unavailable"
    with pytest.raises(AppError) as excinfo:
        store.put(new_profile_id(), SECRET)
    assert excinfo.value.code == "SECRET_STORE_ERROR"


def test_get_and_delete_route_by_ref_backend(tmp_path: Path) -> None:
    fake = FakeKeyring()
    keyring_store = KeyringSecretStore(fake)
    file_store = FileSecretStore(tmp_path)
    profile_id = new_profile_id()
    keyring_ref = keyring_store.put(profile_id, SECRET)
    file_ref = file_store.put(profile_id, OTHER_SECRET)

    keyring_mode = build_secret_store(
        tmp_path,
        mode="keyring",
        keyring_store=keyring_store,
        file_store=file_store,
    )
    assert keyring_mode.get(keyring_ref) == SECRET
    assert keyring_mode.get(file_ref) == OTHER_SECRET

    file_mode = build_secret_store(
        tmp_path,
        mode="file",
        keyring_store=keyring_store,
        file_store=file_store,
    )
    assert file_mode.get(keyring_ref) == SECRET

    file_mode.delete(file_ref)
    assert file_store.get(file_ref) is None
    file_mode.delete(keyring_ref)
    assert keyring_store.get(keyring_ref) is None


def test_rollback_secret_restores_previous_value_or_deletes_new_one(tmp_path: Path) -> None:
    fake = FakeKeyring()
    store = build_secret_store(tmp_path, keyring_store=KeyringSecretStore(fake))
    profile_id = new_profile_id()
    old_ref = store.put(profile_id, SECRET)
    new_ref = store.put(profile_id, OTHER_SECRET)

    rollback_secret(store, new_ref, SECRET)
    assert store.get(old_ref) == SECRET

    rollback_secret(store, new_ref, None)
    assert store.get(new_ref) is None
