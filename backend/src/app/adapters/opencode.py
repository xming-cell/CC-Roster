"""OpenCode 适配器: opencode.json 的 model / provider.openai.options.baseURL。"""

import sys
from collections.abc import Mapping
from pathlib import Path

from app.adapters.simple_json import SimpleJsonAdapter


def resolve_opencode_config_dir(*, environ: Mapping[str, str], home: Path) -> Path:
    raw = environ.get("OPENCODE_CONFIG_DIR", "").strip()
    if raw:
        candidate = Path(raw)
        return candidate if candidate.is_absolute() else home / candidate
    if sys.platform == "win32":
        appdata = environ.get("APPDATA")
        base = Path(appdata) if appdata else home / "AppData" / "Roaming"
        return base / "opencode"
    xdg = environ.get("XDG_CONFIG_HOME", "").strip()
    base = Path(xdg) if xdg else home / ".config"
    return base / "opencode"


class OpenCodeAdapter(SimpleJsonAdapter):
    id = "opencode"
    display_name = "OpenCode"
    provider_name = "OpenCode"
    executable = "opencode"
    config_file_name = "opencode.json"
    env_key_names = ("OPENCODE_API_KEY", "OPENAI_API_KEY")
    model_path = ("model",)
    base_url_path = ("provider", "openai", "options", "baseURL")
