import json
from pathlib import Path

from adapter_contract import AdapterContract
from probe_adapter import ProbeAdapter

from app.adapters.base import ToolAdapter


class TestProbeAdapterContract(AdapterContract):
    """用测试替身跑通契约骨架; T2 / T3 用真实适配器继承同一组断言。"""

    def make_adapter(self, config_dir: Path) -> ToolAdapter:
        return ProbeAdapter(config_dir)

    def seed_configured(self, config_dir: Path) -> None:
        (config_dir / "settings.json").write_text(
            json.dumps(
                {
                    "provider": "probe",
                    "base_url": "https://api.example.test",
                    "model": "probe-1",
                    "secret": "sk-probe-1234567890abcdef",
                }
            ),
            encoding="utf-8",
        )

    def seed_unknown_structure(self, config_dir: Path) -> None:
        (config_dir / "settings.json").write_text(
            json.dumps({"future": {"nested": True}}),
            encoding="utf-8",
        )
