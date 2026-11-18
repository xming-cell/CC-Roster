"""Gemini CLI 适配器: `~/.gemini/settings.json` 的 model / baseUrl 托管字段。"""

from collections.abc import Mapping
from pathlib import Path

from app.adapters.simple_json import SimpleJsonAdapter


def resolve_gemini_config_dir(*, environ: Mapping[str, str], home: Path) -> Path:
    raw = environ.get("GEMINI_CONFIG_DIR", "").strip()
    if raw:
        candidate = Path(raw)
        return candidate if candidate.is_absolute() else home / candidate
    return home / ".gemini"


class GeminiCliAdapter(SimpleJsonAdapter):
    id = "gemini-cli"
    display_name = "Gemini CLI"
    provider_name = "Google"
    executable = "gemini"
    config_file_name = "settings.json"
    env_key_names = ("GEMINI_API_KEY",)
    model_path = ("model",)
    base_url_path = ("baseUrl",)
