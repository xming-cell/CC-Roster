"""`profiles.json` 仓储的持久化契约。

覆盖空库、坏文件、未知版本、并发写入、锁超时、读只读性, 以及删除 SQLite 后
档案仍然可读。全部走真实文件系统 + `tmp_path`, 只替换写入边界模拟磁盘失败。
"""

import hashlib
import json
import shutil
import threading
from collections.abc import Callable
from pathlib import Path

import pytest
from profile_fixtures import make_binding, make_profile
from pydantic import ValidationError

from app.core.db import bootstrap_database
from app.core.errors import AppError
from app.core.locks import FileLock
from app.core.paths import ensure_data_dirs
from app.repositories.profiles import ProfileRepository
from app.schemas.profile import ModelEntry, Profile, ProfileStore

PROFILES_FILE = "profiles.json"


def make_repository(data_dir: Path, *, lock_timeout: float = 5.0) -> ProfileRepository:
    return ProfileRepository(data_dir, lock_timeout=lock_timeout)


def write_raw(data_dir: Path, payload: object) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / PROFILES_FILE
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def add_profile(profile: Profile) -> Callable[[ProfileStore], None]:
    def change(store: ProfileStore) -> None:
        store.profiles.append(profile)

    return change


def test_missing_file_is_empty_store_and_read_creates_nothing(tmp_path: Path) -> None:
    data_dir = tmp_path / "CC-Roster"
    repo = make_repository(data_dir)

    assert repo.list_profiles() == []
    assert repo.list_bindings() == []
    assert not data_dir.exists()


def test_missing_file_inside_existing_data_dir_creates_nothing(tmp_path: Path) -> None:
    repo = make_repository(tmp_path)

    assert repo.load().profiles == []
    assert list(tmp_path.iterdir()) == []


def test_mutate_persists_schema_version_and_roundtrips_models(tmp_path: Path) -> None:
    repo = make_repository(tmp_path)
    model = ModelEntry(id="  claude-sonnet-4  ", display_name="   ")
    profile = make_profile(" Anthropic 主力 ", models=[model])

    created = repo.mutate(add_profile(profile))

    assert created is None
    raw = json.loads((tmp_path / PROFILES_FILE).read_text(encoding="utf-8"))
    assert raw["schema_version"] == 1
    assert raw["bindings"] == []
    assert raw["profiles"][0]["name"] == "Anthropic 主力"
    assert raw["profiles"][0]["models"] == [{"id": "claude-sonnet-4", "display_name": None}]
    assert raw["profiles"][0]["created_at"].endswith(("Z", "+00:00"))

    loaded = repo.get_profile(profile.id)
    assert loaded == profile
    assert loaded is not None
    assert loaded.created_at.utcoffset() is not None


def test_bindings_roundtrip_and_lookup(tmp_path: Path) -> None:
    repo = make_repository(tmp_path)
    profile = make_profile()
    binding = make_binding(profile.id, "codex-cli")

    def change(store: ProfileStore) -> None:
        store.profiles.append(profile)
        store.bindings.append(binding)

    repo.mutate(change)

    assert repo.list_bindings() == [binding]
    assert repo.get_binding("codex-cli") == binding
    assert repo.get_binding("unknown-tool") is None


def test_reads_are_idempotent_and_never_modify_existing_file(tmp_path: Path) -> None:
    repo = make_repository(tmp_path)
    profile = make_profile()
    repo.mutate(add_profile(profile))
    path = tmp_path / PROFILES_FILE
    before_hash = file_hash(path)
    before_mtime = path.stat().st_mtime_ns

    for _ in range(3):
        assert repo.list_profiles() == [profile]
        assert repo.get_profile(profile.id) == profile
        assert repo.list_bindings() == []

    assert file_hash(path) == before_hash
    assert path.stat().st_mtime_ns == before_mtime


def test_corrupt_json_reports_unreadable_and_never_overwrites(tmp_path: Path) -> None:
    path = tmp_path / PROFILES_FILE
    original = '{"schema_version": 1, "profiles": ['
    path.write_text(original, encoding="utf-8")
    repo = make_repository(tmp_path)

    with pytest.raises(AppError) as read_error:
        repo.list_profiles()
    assert read_error.value.code == "PROFILE_STORE_UNREADABLE"

    with pytest.raises(AppError) as write_error:
        repo.mutate(add_profile(make_profile()))
    assert write_error.value.code == "PROFILE_STORE_UNREADABLE"

    assert path.read_text(encoding="utf-8") == original
    assert list(tmp_path.glob("*.tmp")) == []


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"profiles": [], "bindings": []},
        {"schema_version": "1", "profiles": [], "bindings": []},
        {"schema_version": True, "profiles": [], "bindings": []},
        {"schema_version": 1, "profiles": {}, "bindings": []},
        {"schema_version": 1, "profiles": [], "bindings": {}},
        {"schema_version": 1, "profiles": [{"id": "missing-fields"}], "bindings": []},
    ],
)
def test_invalid_structure_reports_unreadable_and_keeps_file(
    tmp_path: Path,
    payload: object,
) -> None:
    path = write_raw(tmp_path, payload)
    original_hash = file_hash(path)
    repo = make_repository(tmp_path)

    with pytest.raises(AppError) as excinfo:
        repo.load()

    assert excinfo.value.code == "PROFILE_STORE_UNREADABLE"
    assert file_hash(path) == original_hash


def test_duplicate_profile_ids_are_treated_as_corruption(tmp_path: Path) -> None:
    profile = make_profile()
    payload = {
        "schema_version": 1,
        "profiles": [
            profile.model_dump(mode="json"),
            profile.model_dump(mode="json"),
        ],
        "bindings": [],
    }
    path = write_raw(tmp_path, payload)
    original_hash = file_hash(path)

    with pytest.raises(AppError) as excinfo:
        make_repository(tmp_path).load()

    assert excinfo.value.code == "PROFILE_STORE_UNREADABLE"
    assert file_hash(path) == original_hash


@pytest.mark.parametrize("version", [0, 2, 99])
def test_unsupported_schema_version_reports_version_error(
    tmp_path: Path,
    version: int,
) -> None:
    payload = {"schema_version": version, "profiles": [], "bindings": []}
    path = write_raw(tmp_path, payload)
    original_hash = file_hash(path)
    repo = make_repository(tmp_path)

    with pytest.raises(AppError) as excinfo:
        repo.load()

    assert excinfo.value.code == "PROFILE_STORE_VERSION_UNSUPPORTED"
    assert file_hash(path) == original_hash


def test_concurrent_mutations_serialize_without_losing_updates(tmp_path: Path) -> None:
    repo = make_repository(tmp_path, lock_timeout=10.0)
    profiles = [make_profile(f"档案 {index}") for index in range(8)]
    errors: list[Exception] = []

    def worker(profile: Profile) -> None:
        try:
            repo.mutate(add_profile(profile))
        except Exception as exc:  # 线程里收集失败原因, 交给主线程断言
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(profile,)) for profile in profiles]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)

    assert not any(thread.is_alive() for thread in threads)
    assert errors == []
    stored_ids = {profile.id for profile in repo.list_profiles()}
    assert stored_ids == {profile.id for profile in profiles}
    json.loads((tmp_path / PROFILES_FILE).read_text(encoding="utf-8"))


def test_lock_timeout_reports_readable_error_without_writing(tmp_path: Path) -> None:
    repo = make_repository(tmp_path, lock_timeout=0.1)
    repo.mutate(add_profile(make_profile()))
    path = tmp_path / PROFILES_FILE
    original_hash = file_hash(path)

    with FileLock(repo.lock_path, timeout=1.0), pytest.raises(AppError) as excinfo:
        repo.mutate(add_profile(make_profile("另一个档案")))

    assert excinfo.value.code == "PROFILE_STORE_LOCK_TIMEOUT"
    assert file_hash(path) == original_hash
    assert len(repo.list_profiles()) == 1


def test_write_failure_keeps_original_file_and_reports_readable_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = make_repository(tmp_path)
    repo.mutate(add_profile(make_profile()))
    path = tmp_path / PROFILES_FILE
    original_hash = file_hash(path)

    def fail_write(_path: Path, _data: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("app.repositories.profiles.write_json_atomic", fail_write)

    with pytest.raises(AppError) as excinfo:
        repo.mutate(add_profile(make_profile("新档案")))

    assert excinfo.value.code == "PROFILE_STORE_WRITE_FAILED"
    assert file_hash(path) == original_hash
    assert list(tmp_path.glob("*.tmp")) == []


def test_profiles_survive_deleting_sqlite_cache_and_logs(tmp_path: Path) -> None:
    data_dir = tmp_path
    ensure_data_dirs(data_dir)
    bootstrap_database(data_dir / "db" / "app.sqlite3").close()
    (data_dir / "cache").mkdir()
    (data_dir / "cache" / "tool-index.json").write_text("{}", encoding="utf-8")
    (data_dir / "logs" / "app.log").write_text("log", encoding="utf-8")

    repo = make_repository(data_dir)
    profile = make_profile()
    repo.mutate(add_profile(profile))

    shutil.rmtree(data_dir / "db")
    shutil.rmtree(data_dir / "cache")
    shutil.rmtree(data_dir / "logs")

    assert repo.list_profiles() == [profile]
    assert (data_dir / PROFILES_FILE).is_file()


def test_mutate_rejects_store_invariant_breach_without_writing(tmp_path: Path) -> None:
    repo = make_repository(tmp_path)
    profile = make_profile()
    repo.mutate(add_profile(profile))
    path = tmp_path / PROFILES_FILE
    original_hash = file_hash(path)

    def duplicate(store: ProfileStore) -> None:
        store.profiles.append(profile)

    with pytest.raises(ValidationError):
        repo.mutate(duplicate)

    assert file_hash(path) == original_hash
    assert repo.list_profiles() == [profile]
