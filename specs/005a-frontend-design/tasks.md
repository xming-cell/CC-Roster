# 005a 任务清单

状态图例：`[ ]` 待做 · `[x]` 完成并已跑过 check.py · `[~]` 做了但有前提未满足

- [x] T1 梳理当前产品需求、已拍板决策与后端能力边界，形成信息架构示例。
- [~] T2 跑一键验收并记录结果；单独记录当前 GitHub Actions 失败位置。验收被已有的后端 CI / 测试问题阻塞。

## 验收记录

命令：`uv run python scripts/check.py`

```text
=== guard scope ===

=== guard: scope ===
task card: specs/005a-frontend-design (1 path rules)
[ok] 4 changed file(s), all within scope

[guard] PASS

=== guard forbidden ===

=== guard: forbidden ===
[ok] no banned patterns in source

[guard] PASS

=== backend lint ===
All checks passed!

=== backend format ===
152 files already formatted

=== backend types ===
Success: no issues found in 92 source files

=== backend tests ===
........................................................................ [ 11%]
........................................................................ [ 22%]
........................................................................ [ 33%]
........................................................................ [ 45%]
........................................................................ [ 56%]
....................................F................................... [ 67%]
........................................................................ [ 78%]
........................................................................ [ 90%]
................................................................         [100%]
================================== FAILURES ===================================
_______________ test_ci_runs_the_same_check_on_three_platforms ________________

    def test_ci_runs_the_same_check_on_three_platforms() -> None:
        root = Path(__file__).resolve().parents[2]
        workflow = (root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

        assert "ubuntu-latest" in workflow
>       assert "macos-latest" in workflow
E       assert 'macos-latest' in 'name: ci\n"on": [push, pull_request]\n\njobs:\n  backend:\n    runs-on: ubuntu-latest\n    defaults:\n      run:\n   ...rozen-lockfile\n      - run: pnpm run type-check\n      - run: pnpm run lint\n      - run: pnpm run test:unit -- --run'

tests\test_release_baseline.py:72: AssertionError
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\我的文件夹\项目3\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/test_release_baseline.py::test_ci_runs_the_same_check_on_three_platforms
1 failed, 639 passed, 1 warning in 27.58s

[FAIL] backend tests
```
