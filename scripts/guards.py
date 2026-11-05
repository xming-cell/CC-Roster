"""硬门禁：把 AGENTS.md 里"零例外"的规则变成可执行断言。

两个检查：
  scope      改动是否越出当前任务卡 `specs/<CURRENT>/spec.md` 的 scope 块
  forbidden  源码里是否有被禁写法（type: ignore / as any / .skip ...）

用法：
  python scripts/guards.py all
  python scripts/guards.py scope
  python scripts/guards.py scope --base origin/main
  python scripts/guards.py forbidden

注意：屏幕输出一律用 ASCII，避免 Windows 控制台代码页（cp936）把中文打成乱码，
中文解释放在 specs/ 与 rules/ 里。
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPECS_DIR = ROOT / "specs"
CURRENT_POINTER = SPECS_DIR / "CURRENT"

# 任务簿记永远放行，否则每张卡都要重复列一遍
ALWAYS_ALLOWED: tuple[str, ...] = ("PROGRESS.md", "specs/**")

# 只扫这些目录：既覆盖源码，又不会把 .venv / node_modules 扫进来
SCAN_ROOTS: tuple[str, ...] = ("backend/src", "backend/tests", "frontend/src")
SCAN_SUFFIXES = {".py", ".ts", ".vue"}

# (路径 glob, 正则, 给人看的名字)
BANNED: tuple[tuple[str, str, str], ...] = (
    ("backend/**/*.py", r"#\s*type:\s*ignore", "# type: ignore"),
    ("backend/**/*.py", r"@pytest\.mark\.skip", "@pytest.mark.skip"),
    ("frontend/**/*.ts", r"//\s*@ts-ignore", "@ts-ignore"),
    ("frontend/**/*.ts", r"//\s*@ts-expect-error", "@ts-expect-error"),
    ("frontend/**/*.vue", r"//\s*@ts-ignore", "@ts-ignore"),
    ("frontend/**/*.vue", r"//\s*@ts-expect-error", "@ts-expect-error"),
    ("frontend/**/*.ts", r"\bas\s+any\b", "as any"),
    ("frontend/**/*.vue", r"\bas\s+any\b", "as any"),
    ("frontend/**/*.ts", r"\b(?:it|test|describe)\.(?:skip|only)\b", ".skip / .only"),
    ("frontend/**/*.vue", r"\b(?:it|test|describe)\.(?:skip|only)\b", ".skip / .only"),
)

_SCOPE_OPEN = re.compile(r"^\s*```+\s*scope\s*$")
_FENCE_CLOSE = re.compile(r"^\s*```+\s*$")


def use_utf8_stdout() -> None:
    """Windows 控制台默认 cp936，直接 print 源码片段会抛 UnicodeEncodeError。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """把 glob 转成正则：`**/` 可跨零到多级目录，`*` 不跨 `/`，`?` 单字符。"""
    out: list[str] = ["^"]
    i = 0
    while i < len(pattern):
        chunk = pattern[i : i + 3]
        if chunk == "**/":
            out.append("(?:.*/)?")
            i += 3
            continue
        if chunk.startswith("**"):
            out.append(".*")
            i += 2
            continue
        ch = pattern[i]
        if ch == "*":
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(ch))
        i += 1
    out.append("$")
    return re.compile("".join(out))


def parse_scope(text: str) -> list[str]:
    """取出 markdown 里 ```scope 围栏中的 glob 清单（`#` 起头为注释）。"""
    patterns: list[str] = []
    inside = False
    for line in text.splitlines():
        if not inside:
            if _SCOPE_OPEN.match(line):
                inside = True
            continue
        if _FENCE_CLOSE.match(line):
            break
        item = line.split("#", 1)[0].strip().lstrip("-").strip()
        if item:
            patterns.append(item)
    return patterns


def git(*args: str) -> list[str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def has_head() -> bool:
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode == 0


def changed_paths(base: str | None) -> list[str]:
    """待提交的改动：工作区（含暂存）+ 未跟踪文件，可选叠加 base...HEAD 区间。"""
    paths: set[str] = set()
    if has_head():
        paths.update(git("diff", "--name-only", "--no-renames", "HEAD"))
    else:
        paths.update(git("diff", "--name-only", "--no-renames", "--cached"))
    paths.update(git("ls-files", "--others", "--exclude-standard"))
    if base:
        paths.update(git("diff", "--name-only", "--no-renames", f"{base}...HEAD"))
    return sorted(p.replace("\\", "/") for p in paths)


def current_task_dir() -> Path | None:
    if not CURRENT_POINTER.is_file():
        return None
    raw = CURRENT_POINTER.read_text(encoding="utf-8")
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    if not lines:
        return None
    wanted = lines[0]
    if wanted.lower() in {"none", "null", "-", "无"}:
        return None
    matches = sorted(p for p in SPECS_DIR.glob(f"{wanted}*") if p.is_dir())
    if not matches:
        raise RuntimeError(
            f"specs/CURRENT = '{wanted}' but no matching dir; expected specs/{wanted}-<slug>/"
        )
    return matches[0]


def check_scope(base: str | None) -> bool:
    print("\n=== guard: scope ===", flush=True)
    try:
        task_dir = current_task_dir()
    except RuntimeError as exc:
        print(f"[FAIL] {exc}", flush=True)
        return False
    if task_dir is None:
        print("[skip] specs/CURRENT points to no task card; scope check skipped", flush=True)
        return True

    spec_file = task_dir / "spec.md"
    rel_task = task_dir.relative_to(ROOT).as_posix()
    if not spec_file.is_file():
        print(f"[FAIL] {rel_task}/spec.md not found", flush=True)
        return False

    patterns = parse_scope(spec_file.read_text(encoding="utf-8"))
    if not patterns:
        print(f"[FAIL] {rel_task}/spec.md has no ```scope block (or it is empty)", flush=True)
        return False

    allowed = [glob_to_regex(p) for p in (*ALWAYS_ALLOWED, *patterns)]
    print(f"task card: {rel_task} ({len(patterns)} path rules)", flush=True)

    try:
        changed = changed_paths(base)
    except RuntimeError as exc:
        print(f"[FAIL] {exc}", flush=True)
        return False

    outside = [p for p in changed if not any(r.match(p) for r in allowed)]
    if outside:
        print(f"[FAIL] {len(outside)} changed file(s) outside the task card scope:", flush=True)
        for path in outside:
            print(f"  - {path}", flush=True)
        print(f"hint: revert them, or add the path to {rel_task}/spec.md scope block", flush=True)
        print("      and note why in PROGRESS.md.", flush=True)
        return False

    print(f"[ok] {len(changed)} changed file(s), all within scope", flush=True)
    return True


def check_forbidden() -> bool:
    print("\n=== guard: forbidden ===", flush=True)
    rules = [(glob_to_regex(g), re.compile(p), label) for g, p, label in BANNED]
    hits: list[str] = []

    for rel_root in SCAN_ROOTS:
        root = ROOT / rel_root
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix not in SCAN_SUFFIXES:
                continue
            rel = path.relative_to(ROOT).as_posix()
            applicable = [item for item in rules if item[0].match(rel)]
            if not applicable:
                continue
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            for lineno, line in enumerate(text.splitlines(), start=1):
                for _, pattern, label in applicable:
                    if pattern.search(line):
                        hits.append(f"{rel}:{lineno}  {label}  |  {line.strip()[:90]}")

    if hits:
        print(f"[FAIL] {len(hits)} banned pattern hit(s):", flush=True)
        for hit in hits:
            print(f"  - {hit}", flush=True)
        print("\nhint: zero-exception rule -> fix the code, do not add an escape hatch.", flush=True)
        return False

    print("[ok] no banned patterns in source", flush=True)
    return True


def main(argv: list[str]) -> int:
    use_utf8_stdout()
    known = {"all", "scope", "forbidden"}
    command = argv[0] if argv and not argv[0].startswith("-") else "all"
    if command not in known:
        print(f"unknown command: {command} (use: {', '.join(sorted(known))})", flush=True)
        return 2

    base: str | None = None
    if "--base" in argv:
        idx = argv.index("--base")
        if idx + 1 >= len(argv):
            print("--base requires a git ref", flush=True)
            return 2
        base = argv[idx + 1]

    ok = True
    if command in {"all", "scope"}:
        ok = check_scope(base) and ok
    if command in {"all", "forbidden"}:
        ok = check_forbidden() and ok

    print("\n[guard] PASS" if ok else "\n[guard] FAIL", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))