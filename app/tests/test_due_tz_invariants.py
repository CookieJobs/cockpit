"""2026-08-01 立: dueColor / dueLabel 时区 bug 不变量。

lesson #18: 用户报告"今天" 设置后显示成"明天"。
根因: `new Date("YYYY-MM-DD")` 被 JS 规范化为 UTC 午夜,
跟 `new Date()` (本地) 比较时被时区偏移污染,
Math.ceil(0.33天) 进位到 1 → "明天"。

修法: 加 parseLocalDate 工具, 显式按本地时区解析。
本测试锁 2 件事:
  1. **静态**: lib/api.ts 里 dueColor / dueLabel 不能直接 `new Date("YYYY-MM-DD"`。
     必须走 parseLocalDate。
  2. **端到端**: subprocess 调 mjs, 跨 3 个时区 (UTC+8 / UTC+0 / UTC-8) 实跑,
     验证"今天" 永远显示"今天", "明天" 永远显示"明天", 等等。

锁 lesson #2/#15/#17 同源教训: 单测过 ≠ 真实数据过。
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

# 跨平台找 node (venv 激活后 PATH 不一定继承父进程, 用 shutil.which 显式找)
_NODE_BIN = shutil.which("node")
assert _NODE_BIN is not None, (
    "node 不在 PATH 中, lesson #18 端到端测试无法跑。请安装 Node.js 22+ "
    "或在测试环境提供 node 二进制。"
)

# 测试文件位置
REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "web"
LIB_API = WEB_DIR / "lib" / "api.ts"
MJS_SCRIPT = WEB_DIR / "scripts" / "test-due-date-tz.mjs"


# ---------------------------------------------------------------------------
# 静态不变量: 防回退到 `new Date("YYYY-MM-DD")`
# ---------------------------------------------------------------------------
def test_lib_api_does_not_use_new_date_with_iso_string_for_due():
    """dueColor / dueLabel 函数体内不能出现 `new Date("YYYY-MM-DD")` 模式。

    旧 bug:  `const dueDate = new Date(due);` 解析 UTC 午夜, 跟本地 now 比差 8h。
    修法后: 必须 `const dueDate = parseLocalDate(due);` 走本地。
    """
    src = LIB_API.read_text()

    # 抓出 dueColor / dueLabel 两个函数体 (用花括号配对, 简单粗暴)
    def extract_body(name: str) -> str:
        m = re.search(rf"export function {name}\([^)]*\)[^{{]*\{{", src)
        assert m, f"{name} function not found"
        start = m.end() - 1  # '{' 位置
        depth = 0
        i = start
        while i < len(src):
            c = src[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return src[start : i + 1]
            i += 1
        raise AssertionError(f"{name} body not closed")

    for name in ("dueColor", "dueLabel"):
        body = extract_body(name)
        # 锁死: 不能有 `new Date("YYYY...`
        bad = re.search(r'new Date\(["\']\d{4}-\d{2}-\d{2}', body)
        assert bad is None, (
            f"{name} 体内有 `new Date(\"YYYY-MM-DD\")` 模式! "
            f"会触发 lesson #18 时区 bug, 必须改用 parseLocalDate(due)。\n"
            f"匹配: {bad.group() if bad else 'N/A'}"
        )
        # 锁死: 必须用 parseLocalDate
        assert "parseLocalDate(due)" in body or "parseLocalDate" in body, (
            f"{name} 必须用 parseLocalDate 解析 due 字符串 (lesson #18)"
        )


def test_parse_local_date_function_exists():
    """parseLocalDate 必须存在且 export。"""
    src = LIB_API.read_text()
    # 锁 export 签名
    m = re.search(r"export function parseLocalDate\([^)]+\)\s*:\s*Date\s*\{", src)
    assert m, "parseLocalDate(s: string): Date 必须存在"
    # 锁实现: 拆字段构造 (走本地)
    body_start = m.end() - 1
    depth = 0
    i = body_start
    while i < len(src):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    body = src[body_start : i + 1]
    # 必须用 .split("-") 或等价拆字段方式
    assert "split" in body, "parseLocalDate 必须拆分 YYYY-MM-DD 字段构造本地 Date"


def test_now_set_hours_zero_in_due_label_and_due_color():
    """dueColor 跟 dueLabel 都要 now.setHours(0,0,0,0) 归零本地 0 点。

    归零后才能跟 dueDate (本地 0 点) 在同一个粒度上做差, 避免出现 0.33 / 0.67
    这种"半天不到" 的小数值, 触发 Math.ceil 进位到下一天。
    """
    src = LIB_API.read_text()

    def extract_body(name: str) -> str:
        m = re.search(rf"export function {name}\([^)]*\)[^{{]*\{{", src)
        assert m, f"{name} function not found"
        start = m.end() - 1
        depth = 0
        i = start
        while i < len(src):
            c = src[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return src[start : i + 1]
            i += 1
        raise AssertionError(f"{name} body not closed")

    for name in ("dueColor", "dueLabel"):
        body = extract_body(name)
        assert "now.setHours(0, 0, 0, 0)" in body or "now.setHours(0,0,0,0)" in body, (
            f"{name} 必须 now.setHours(0, 0, 0, 0) 归零本地 0 点 (lesson #18)"
        )


# ---------------------------------------------------------------------------
# 端到端: subprocess 调 mjs 跨时区真跑
# ---------------------------------------------------------------------------
def test_mjs_script_exists():
    """mjs 端到端脚本必须存在 (lesson #2 同源教训: 端到端实测是必做的)。"""
    assert MJS_SCRIPT.exists(), f"端到端脚本 {MJS_SCRIPT} 不存在"


def test_mjs_e2e_in_utc_plus_8_shanghai():
    """上海 (UTC+8) — 用户实际时区, 旧 bug 触发点。"""
    result = subprocess.run(
        [
            _NODE_BIN,
            "--experimental-strip-types",
            str(MJS_SCRIPT),
        ],
        cwd=REPO_ROOT,
        env={**os.environ, "TZ": "Asia/Shanghai"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"Asia/Shanghai mjs 端到端失败:\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )
    # 锁住 "今天" 必须显示 "今天" (核心 bug)
    # mjs 脚本 Test 7 的反向证明部分会打印 `新 label="今天"` 和 `旧 label="明天"`
    # 锁这两个不变量:
    assert '新 label="今天"' in result.stdout, (
        f"Shanghai 时区下新实现 dueLabel('今天') 必须返回'今天':\n{result.stdout}"
    )
    # 锁住反向证明: 旧实现必须复现"明天" (证明 bug 真实存在)
    assert '旧 label="明天"' in result.stdout, (
        f"Shanghai 时区下旧实现必须复现'明天' (证明 bug 真实存在):\n{result.stdout}"
    )


def test_mjs_e2e_in_utc():
    """UTC — 旧实现凑巧对的时区, 验证新实现也正确。"""
    result = subprocess.run(
        [
            _NODE_BIN,
            "--experimental-strip-types",
            str(MJS_SCRIPT),
        ],
        cwd=REPO_ROOT,
        env={**os.environ, "TZ": "UTC"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"UTC mjs 端到端失败:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_mjs_e2e_in_utc_minus_8_la():
    """洛杉矶 (UTC-8) — 西半球时区, 验证时区无关性。"""
    result = subprocess.run(
        [
            _NODE_BIN,
            "--experimental-strip-types",
            str(MJS_SCRIPT),
        ],
        cwd=REPO_ROOT,
        env={**os.environ, "TZ": "America/Los_Angeles"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"LA mjs 端到端失败:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
