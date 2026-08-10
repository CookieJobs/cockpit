"""成就库项目层级不变量 (2026-07-28 立, v2 改造)。

用户原话 (2026-07-28): "成就库里面是不是没有采用项目和任务的层级？是不是只有任务这一层?"

调查发现:
- 后端 Achievement 表有 project_id + project 名称快照 (app/core/models.py:280-288)
- 旧前端 web/app/achievements/page.tsx 只按 date 分组, project 仅作徽章
- 用户想看"我在哪些项目上有沉淀" — 需要项目级聚合

改造 (v2):
- 一级 = project card (按项目聚合所有成就)
- 二级 = date (项目下按日期分组)
- 项目排序: ready 数 desc
- 折叠状态: localStorage 持久化, 默认展开
- 跟 /today 项目卡片的"已沉淀 N" 子区风格一致

这条测试锁住, 防退化到"只按日期分组" 的旧版。
"""
import re
from pathlib import Path

ACHV_PAGE = (
    Path(__file__).parent.parent.parent / "web" / "app" / "achievements" / "page.tsx"
)


def read_achv() -> str:
    return ACHV_PAGE.read_text(encoding="utf-8")


# ===== 一级 = project 分组 =====


def test_uses_project_level_grouping_not_only_date():
    """必须有项目级聚合 (projectGroups / projectGroups.map), 不能只按 date 分组。"""
    src = read_achv()
    assert "projectGroups" in src, "必须有项目级聚合状态 (projectGroups), 不能只有 date 分组"
    # 必须按 project 聚合 (不是按 date)
    assert "a.project" in src or "item.project" in src, "聚合 key 必须用 project 字段"
    # 必须有项目卡片的 map 渲染
    assert re.search(r"projectGroups\.map", src), "必须有 projectGroups.map 渲染项目卡片"


def test_project_card_shows_name_and_emoji():
    """项目卡片必须有 emoji + 项目名, 跟 /today 风格一致 (复用 projectEmoji)。"""
    src = read_achv()
    assert "projectEmoji" in src, "项目卡片必须用 projectEmoji (跟 /today 共享)"
    # 项目名显示
    assert "g.project" in src, "项目卡片必须显示项目名"


def test_project_card_shows_status_counts():
    """项目卡片必须有 ready / pending / needs_data 三态计数。"""
    src = read_achv()
    # ready 计数 (绿色 ✅)
    assert "g.ready" in src and "✅" in src, "项目卡片必须显示 ready 数 (✅)"
    # pending 计数
    assert "g.pending" in src and "⏳" in src, "项目卡片必须显示 pending 数 (⏳)"
    # needs_data 计数
    assert "g.needs_data" in src and "📊" in src, "项目卡片必须显示 needs_data 数 (📊)"


def test_project_groups_sorted_by_ready_desc():
    """项目分组必须按 ready 数 desc 排序 (最近沉淀最多的项目最显眼)。"""
    src = read_achv()
    # 找排序逻辑
    assert "b.ready - a.ready" in src or "b.ready !== a.ready" in src, (
        "项目必须按 ready 数 desc 排序, 让最近沉淀最多的项目最显眼"
    )


# ===== 二级 = date 分组 (项目卡片内) =====


def test_inside_project_still_groups_by_date():
    """项目卡片内部仍按日期分组, 不能直接把成就全平铺。"""
    src = read_achv()
    # 找二级 date 分组
    assert "dateGroups" in src or "a.date" in src, "项目卡片内部必须按 date 二级分组"
    # 找二级排序
    assert re.search(r"localeCompare", src), "二级 date 必须排序 (最新在上)"


# ===== 折叠状态 =====


def test_project_collapse_persisted_in_localstorage():
    """项目折叠状态必须 localStorage 持久化 (用户跨刷新保留偏好)。"""
    src = read_achv()
    assert "localStorage" in src, "项目折叠状态必须 localStorage 持久化"
    assert "COLLAPSED_KEY" in src, "必须有 localStorage key 常量 (避免 typo)"
    assert "cockpit_achievements_collapsed_projects" in src, "localStorage key 必须是 cockpit_achievements_collapsed_projects"


def test_each_project_card_has_toggle_button():
    """每个项目卡片必须有展开/收起按钮 (默认展开)。"""
    src = read_achv()
    # onClick={onToggle} 绑定到按钮
    assert re.search(r"onClick=\{onToggle\}", src), "项目卡片 header 必须是 button + onClick={onToggle}"
    # ChevronDown 指示器
    assert "ChevronDown" in src, "项目卡片必须有 ChevronDown 指示器"


# ===== Achievement Item (二级列表内) =====


def test_achievement_item_keeps_all_4_fields():
    """成就条目必须保留 cv / outcome / reflection / cv_status 4 个字段 (不能因为层级改造砍掉)。"""
    src = read_achv()
    # cv
    assert "a.cv" in src, "成就条目必须显示 cv 字段"
    # outcome
    assert "a.outcome" in src, "成就条目必须显示 outcome 字段"
    # reflection
    assert "a.reflection" in src, "成就条目必须显示 reflection 字段"
    # cv_status 状态指示器
    assert "a.cv_status" in src, "成就条目必须显示 cv_status 状态指示器"


def test_achievement_edit_and_undo_still_works():
    """编辑 CV + 升级 + 撤销 三个动作必须保留。"""
    src = read_achv()
    assert "updateAchievement" in src, "编辑 CV 必须调 updateAchievement"
    assert "undoAchievement" in src, "撤销必须调 undoAchievement"
    # needs_data → ready 的升级入口
    assert "/achievements/follow-up" in src, "needs_data 必须有补全证据的入口"
    assert 'cv_status: "ready"' not in src, "成就库不能绕过质量门直接升 ready"


# ===== 顶层 UI =====


def test_status_filter_still_present():
    """状态过滤 (all / needs_data / pending / ready) 必须保留。"""
    src = read_achv()
    assert "StatusFilter" in src, "StatusFilter type 必须保留"
    # 4 个 filter 选项
    for k in ["all", "needs_data", "pending", "ready"]:
        assert f'k: "{k}"' in src or f"k: '{k}'" in src, f"状态过滤必须包含 {k}"


def test_empty_state_preserved():
    """空状态 (0 成就) 文案必须保留。"""
    src = read_achv()
    assert "还没有成就" in src, "空状态文案必须保留"


# ===== 防退化: 旧版"只按 date 分组" 的代码不能复活 =====


def test_no_top_level_date_only_grouping():
    """顶层不能再用 Object.entries(groups).map(...) 按 date 渲染 (那是 v1 旧版)。"""
    src = read_achv()
    # 旧版签名: `Object.entries(groups).sort(...).map(([date, list])` 这种结构
    # 新版顶层用 projectGroups.map
    # 简单判断: 顶层 JSX 不能直接 entries(groups).map 作为渲染
    # 找顶层 div 内的 map
    # 由于 v2 内部 ProjectSection 还有 entries(dateGroups).map (二级), 这里只检查顶层
    # 顶层渲染应该是 projectGroups.map
    # 用更严格的方式: 找顶层 "return ( ... {projectGroups.map" 或类似结构
    assert re.search(r"projectGroups\.map\(\(g\)|projectGroups\.map\(\(.*?\)", src), (
        "顶层必须用 projectGroups.map 渲染, 不能用 Object.entries(groups).map 按 date"
    )
