"""一键验收。任何一步失败立即以非零码退出，这是 agent 的唯一成功信号。"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
IS_WIN = sys.platform == "win32"


def run(name: str, args: list[str], cwd: Path) -> None:
    print(f"\n=== {name} ===", flush=True)
    if IS_WIN:
        # Windows 上 pnpm 是 .cmd，必须经 shell 才能启动
        result = subprocess.run(subprocess.list2cmdline(args), cwd=cwd, shell=True)
    else:
        result = subprocess.run(args, cwd=cwd)
    if result.returncode != 0:
        print(f"\n[FAIL] {name}", flush=True)
        sys.exit(result.returncode)


def main() -> None:
    run("backend lint", ["uv", "run", "ruff", "check", "."], BACKEND)
    run("backend format", ["uv", "run", "ruff", "format", "--check", "."], BACKEND)
    run("backend types", ["uv", "run", "mypy", "src"], BACKEND)
    run("backend tests", ["uv", "run", "pytest", "-q"], BACKEND)
    run("frontend types", ["pnpm", "run", "type-check"], FRONTEND)
    run("frontend lint", ["pnpm", "run", "lint"], FRONTEND)
    # --run：单次执行，避免 vitest 在终端里进入 watch 模式卡住
    run("frontend tests", ["pnpm", "run", "test:unit", "--run"], FRONTEND)
    print("\nAll checks passed.", flush=True)


if __name__ == "__main__":
    main()