"""演示数据播种脚本不变量测试 (2026-07-20 立)。

锁住 seed_demo.py 的关键不变量, 防改脚本时不小心破坏演示效果:

1. 脚本文件必须存在
2. PROJECTS 列表必须含 1 个 archived=True（演示归档 UI）
3. TODAY_TASKS 列表必须含 1 个 blocked=True（focus 里有黄色提示）
4. TODAY_TASKS 必须含 due=TODAY 的（演示 warning 颜色）
5. ACHIEVEMENTS 必须覆盖 3 状态（ready + needs_data + pending）
6. ACHIEVEMENTS 必须有本周/上周/本月 3 个时间范围数据（演示 report workspace）
7. make seed-demo target 必须存在
"""
import re
from datetime import date
from pathlib import Path

SCRIPT = Path(__file__).parent.parent.parent / "scripts" / "seed_demo.py"
MAKEFILE = Path(__file__).parent.parent.parent / "Makefile"


def test_seed_script_exists():
    assert SCRIPT.exists(), f"{SCRIPT} 不存在"


def _extract_list(src: str, name: str) -> str:
    r"""提取 `NAME = [ ... ]` 列表的 body（跨多行, 用 [\s\S] 保险）。"""
    # 用 literal "NAME = [" 开头, 找配对的 "]"
    start = src.find(f"{name} = [")
    assert start >= 0, f"{name} 列表未找到"
    body_start = start + len(f"{name} = [")
    # 配对方括号
    depth = 1
    i = body_start
    while i < len(src) and depth > 0:
        ch = src[i]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        elif ch in ('"', "'"):
            # 跳过字符串字面量, 避免里面的 [] 干扰
            quote = ch
            i += 1
            while i < len(src) and src[i] != quote:
                if src[i] == "\\":
                    i += 1
                i += 1
        i += 1
    assert depth == 0, f"{name} 列表方括号未配对"
    return src[body_start : i - 1]


def test_projects_have_archived_demo():
    """PROJECTS 必须含 archived=True 项目（演示归档 UI）。"""
    src = SCRIPT.read_text(encoding="utf-8")
    block = _extract_list(src, "PROJECTS")
    assert '"archived": True' in block, (
        "PROJECTS 缺 archived=True 项目 — 演示归档 UI 没数据"
    )


def test_today_tasks_have_blocked():
    """TODAY_TASKS 必须含 blocked=True（focus 演示里能看见阻塞提示）。"""
    src = SCRIPT.read_text(encoding="utf-8")
    block = _extract_list(src, "TODAY_TASKS")
    assert '"blocked": True' in block, (
        "TODAY_TASKS 缺 blocked=True 任务 — focus 演示里没黄色阻塞提示"
    )


def test_today_tasks_have_today_due():
    """TODAY_TASKS 必须有 due=TODAY 的（演示 warning 颜色 / 今日 due 标签）。"""
    src = SCRIPT.read_text(encoding="utf-8")
    block = _extract_list(src, "TODAY_TASKS")
    assert '"due": TODAY' in block, (
        "TODAY_TASKS 缺 due=TODAY 任务 — 演示'今天due' 红色/橙色标签没数据"
    )


def test_achievements_cover_three_states():
    """ACHIEVEMENTS 必须有 ready + needs_data + pending 三态, 且 needs_data/pending
    各 >= 2 条, 让成就库 /report 里能看见明显的橙色/灰色徽章（2026-07-20 加）。"""
    src = SCRIPT.read_text(encoding="utf-8")
    block = _extract_list(src, "ACHIEVEMENTS")
    assert "CVStatus.READY" in block, "ACHIEVEMENTS 缺 CVStatus.READY"
    assert "CVStatus.NEEDS_DATA" in block, (
        "ACHIEVEMENTS 缺 CVStatus.NEEDS_DATA — 演示 cvStatus 三态不完整"
    )
    assert "CVStatus.PENDING" in block, (
        "ACHIEVEMENTS 缺 CVStatus.PENDING — 演示 cvStatus 三态不完整"
    )
    # 数量下限, 防止改 seed 时只留 1 条 needs_data 让"升级路径"看不出效果
    needs_count = block.count("CVStatus.NEEDS_DATA")
    pending_count = block.count("CVStatus.PENDING")
    assert needs_count >= 2, (
        f"needs_data 数量={needs_count} 太少, 成就库的'📊 还差数据' 区看不出效果"
    )
    assert pending_count >= 2, (
        f"pending 数量={pending_count} 太少, 成就库的'⏳ 草稿' 区看不出效果"
    )


def test_achievements_span_three_time_ranges():
    """ACHIEVEMENTS 必须跨本周/上周/本月 3 个时间范围（演示 report workspace）。

    提示: 今天周一, 跑 demo 时:
      - days_ago=0 → 本周
      - days_ago=1-4 → 上周 (今天往前跨周末)
      - days_ago=7+ → 上周 / 本月早期
    所以 5 条 ago_d0 是"本周", 4 条 ago_d8-11 是"上周"...
    """
    src = SCRIPT.read_text(encoding="utf-8")
    block = _extract_list(src, "ACHIEVEMENTS")
    # 抓所有 ago_dN 形式的天数
    days_ago_list = [int(x) for x in re.findall(r"ago_d(\d+)", block)]

    # 按时间范围分类 (宽容阈值, 适配周一和周中两种情况)
    this_week = [d for d in days_ago_list if 0 <= d <= 1]  # days_ago=0 一定在本周, =1 在周一也是上周
    last_week = [d for d in days_ago_list if 2 <= d <= 13]
    older = [d for d in days_ago_list if d >= 14]

    assert len(this_week) + len(last_week) >= 8, (
        f"本周({len(this_week)}) + 上周({len(last_week)}) 总数 {len(this_week)+len(last_week)} 太少, "
        "/report 演示不出效果"
    )
    assert len(older) >= 2, (
        f"本月更早成就数={len(older)} 太少, /report 本月范围演示不出效果"
    )


def test_makefile_has_seed_demo_target():
    """Makefile 必须有 seed-demo target（让用户能 make seed-demo 跑脚本）。"""
    src = MAKEFILE.read_text(encoding="utf-8")
    assert "seed-demo:" in src, "Makefile 缺 seed-demo target"
    assert "scripts/seed_demo.py" in src, "Makefile seed-demo 没指向 scripts/seed_demo.py"
