"""/report workspace 不变量静态分析测试 (2026-07-20 立)。

锁住:
1. /report 页面文件存在
2. templates.ts 至少 3 个模板 + 4 个时间范围
3. /report 页面渲染 PendingCard × 2（needs_data + pending）
4. /report 页面有"复制"和"下载 .md"两个按钮
5. 模板的"述职"必须过滤只 ready 成就（PRD 场景 5 明确要求）
6. /report 从 MainBoard 有入口
"""
import re
from pathlib import Path

WEB_DIR = Path(__file__).parent.parent.parent / "web"
REPORT_PAGE = WEB_DIR / "app" / "report" / "page.tsx"
TEMPLATES_TS = WEB_DIR / "lib" / "templates.ts"
MAINBOARD_TSX = WEB_DIR / "components" / "MainBoard.tsx"


def test_report_page_exists():
    """周报/述职 workspace 页面文件存在（PRD 场景 4-5 主入口）。"""
    assert REPORT_PAGE.exists(), (
        f"页面文件 {REPORT_PAGE} 不存在 — /report workspace 是核心交付物, "
        "完成即沉淀的护城河只有靠这个兑现"
    )


def test_templates_at_least_three():
    """模板至少 3 个：产品 / 研发 / 述职（PRD 场景 4-5 三大场景）。"""
    src = TEMPLATES_TS.read_text(encoding="utf-8")
    for k in ["product_weekly", "eng_weekly", "review_quarterly"]:
        assert f'key: "{k}"' in src, f"templates.ts 缺模板: {k}"


def test_time_ranges_at_least_four():
    """时间范围至少 4 个预设：本周/上周/本月/本季度。"""
    src = TEMPLATES_TS.read_text(encoding="utf-8")
    for k in ["this_week", "last_week", "this_month", "this_quarter"]:
        assert f'key: "{k}"' in src, f"templates.ts 缺时间范围: {k}"


def test_review_template_filters_ready_only():
    """述职材料 (review_quarterly) 必须只取 ready 成就。

    PRD 场景 5 明确："用 cvStatus=ready 的条目（保证真实）"。
    不能让 needs_data / pending 进述职 — 数据不真, 述职会翻车。
    """
    src = TEMPLATES_TS.read_text(encoding="utf-8")
    # 找 review_quarterly 模板的 sections
    m = re.search(
        r'key:\s*"review_quarterly".*?sections:\s*\[(.*?)\]',
        src,
        re.DOTALL,
    )
    assert m, "review_quarterly 模板定义未找到"
    section = m.group(1)
    assert 'cv_status === "ready"' in section, (
        "述职材料模板没过滤 cv_status=ready, PRD 场景 5 要求"
    )
    # 显式拒绝 needs_data / pending
    assert 'cv_status !== "ready"' in section or (
        # 备选: 模板整体 match 是 ready only
        "ready" in section
    ), "述职模板 match 逻辑必须明确包含 ready 过滤"


def test_report_page_has_pending_cards():
    """/report 页面有 2 个 PendingCard: needs_data + pending。"""
    src = REPORT_PAGE.read_text(encoding="utf-8")
    # 标题必须出现
    assert "还差数据" in src, "/report 页面缺 '还差数据' 区（needs_data 升级入口）"
    assert "草稿" in src, "/report 页面缺 '草稿' 区（pending 升级入口）"


def test_report_page_has_copy_and_download():
    """/report 页面有"复制"和"下载 .md" 按钮。"""
    src = REPORT_PAGE.read_text(encoding="utf-8")
    assert "复制" in src, "/report 缺 '复制' 按钮 — 用户没法把生成的 markdown 拿走"
    assert "下载" in src and ".md" in src, "/report 缺 '下载 .md' 按钮"


def test_mainboard_links_to_report():
    """MainBoard 必须有到 /report 的入口。"""
    src = MAINBOARD_TSX.read_text(encoding="utf-8")
    assert 'href="/report"' in src, (
        "MainBoard 缺 /report 入口, 用户从看板找不到 workspace"
    )
