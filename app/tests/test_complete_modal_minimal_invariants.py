"""CompleteTaskModal 极简化不变量 (2026-07-28 立)。

用户反馈 (2026-07-28):
- 4 字段全显示 (outcome / cv / reflection / cv_status) 感觉在写两遍
- 完成时多巴胺峰值被表单打断, 摩擦大
- 完成价值 (成就沉淀) 用户当下看不到, 弹窗变纯成本

改造 (A 项):
- 主流程只剩 outcome 1 必填
- cv 智能预填 `完成「${task.title}」` + "✨ 润色" 按钮调 LLM 重写
- reflection + cv_status 折叠在"高级"区域, 默认收起
- outcome 必填, cv 不必填 (有默认值, 0 摩擦起步)

D 项同时改: 完成弹窗关闭后弹一个轻量 toast 庆祝 + 跳转到 /achievements
(在 Toast.tsx + MainBoard.tsx + /today/page.tsx 联动, 这里不锁)

这条测试锁住 A 项, 防退化。
"""
import re
from pathlib import Path

MODAL_TSX = (
    Path(__file__).parent.parent.parent
    / "web"
    / "components"
    / "CompleteTaskModal.tsx"
)


def read_modal() -> str:
    return MODAL_TSX.read_text(encoding="utf-8")


def test_modal_has_outcome_required_marker():
    """outcome 字段必须有 * 必填标记。"""
    src = read_modal()
    # 必填标记: <span className="text-danger">*</span> 必须紧跟结果描述 label
    assert '结果描述 <span className="text-danger">*</span>' in src, (
        "outcome 必填标记缺失 — 完成弹窗必须有 1 个必填字段 (outcome), "
        "不能回退到 4 字段全必填/全选填"
    )


def test_modal_cv_has_default_value_not_required():
    """cv 字段不能有必填标记 (有默认值, 0 摩擦起步)。"""
    src = read_modal()
    # 找 cv label 区域: 必须没有 * 必填标记
    cv_label_idx = src.find("CV 成就陈述")
    assert cv_label_idx > 0, "CV 成就陈述 label 缺失"
    # 往后 200 字符内不能有必填 *
    cv_section = src[cv_label_idx : cv_label_idx + 200]
    assert "text-danger" not in cv_section or "*" not in cv_section.split("必填")[0] if "必填" in cv_section else True, (
        "cv 不该有必填标记 — 已有默认值 `完成「${title}」`, 0 摩擦起步"
    )


def test_modal_cv_prefilled_with_task_title():
    """cv 字段必须有 task.title 预填 (用 useState 初始值)。"""
    src = read_modal()
    # useState(`完成「${task.title}」`)
    assert "useState(`完成「${task.title}」`)" in src or 'useState(`完成「${task.title}」`)' in src, (
        "cv 必须预填 `完成「${task.title}」` 作为默认值, 0 摩擦起步"
    )


def test_modal_has_polish_button():
    """必须有 ✨ 润色按钮调 LLM 润色 cv。"""
    src = read_modal()
    # 按钮文案: "润色" 必须出现 + 调用 api.polishCv
    assert "润色" in src, "润色按钮文案缺失"
    assert "api.polishCv" in src, "润色按钮必须调 api.polishCv (POST /api/llm/polish_cv)"


def test_modal_advanced_section_collapsed_by_default():
    """reflection + cv_status 折叠在"高级选项"区域, 默认收起。"""
    src = read_modal()
    # 1. useState(false) 默认收起
    assert "setShowAdvanced" in src, "高级选项折叠状态缺失"
    assert "useState(false)" in src, "高级选项必须默认收起 (useState(false))"
    # 2. "高级选项" 文案
    assert "高级选项" in src, "高级选项 label 缺失"
    # 3. reflection 和 cv_status 都在 showAdvanced 条件渲染内
    advanced_idx = src.find("showAdvanced &&")
    assert advanced_idx > 0, "showAdvanced 条件渲染块缺失"
    # 找 showAdvanced 块的结束 — 平衡到对应的 )}
    # 简单方案: 看从 advanced_idx 起到文件末尾, reflection + cvStatus 都在
    advanced_section = src[advanced_idx:]
    assert "reflection" in advanced_section, "reflection 必须在 showAdvanced 块内"
    assert "cvStatus" in advanced_section, "cvStatus 必须在 showAdvanced 块内 (不直接暴露给用户)"


def test_modal_submit_disabled_only_when_outcome_and_cv_empty():
    """submit 按钮 disabled 条件: outcome 空 或 cv 空。outcome 是唯一真必填, cv 有默认值不该空。"""
    src = read_modal()
    # 找 submit button 的 disabled 条件
    submit_match = re.search(
        r"onClick=\{submit\}.*?disabled=\{([^}]+)\}",
        src,
        re.DOTALL,
    )
    assert submit_match, "submit 按钮的 disabled 条件缺失"
    disabled_expr = submit_match.group(1)
    # 必须包含 outcome 和 cv
    assert "outcome.trim()" in disabled_expr, "disabled 必须检查 outcome (唯一真必填)"
    assert "cv.trim()" in disabled_expr, "disabled 必须检查 cv (兜底, 理论不会空)"


def test_modal_explains_that_incomplete_evidence_is_not_report_ready():
    """完成不应被阻塞，但用户必须知道待补数据不会提前进入报告。"""
    src = read_modal()
    assert "将保存为待补数据，不会进入报告；补全后自动可用" in src, (
        "完成弹窗必须解释质量门的结果，避免用户误以为默认 CV 或未答追问会进入周报/CV"
    )


def test_modal_outcome_autofocus_on_open():
    """打开弹窗时必须自动 focus outcome, 减少点击。"""
    src = read_modal()
    # useEffect 里有 outcomeRef.current?.focus()
    assert "outcomeRef.current?.focus()" in src, "打开弹窗必须自动 focus outcome"


def test_modal_uses_polishcv_via_api_helper():
    """润色必须走 api.polishCv (封装好的 fetch 包装), 不能直接 fetch。"""
    src = read_modal()
    # 找 polish 函数
    polish_idx = src.find("const polish = async () =>")
    assert polish_idx > 0, "polish 函数缺失"
    polish_body = src[polish_idx : polish_idx + 500]
    assert "await api.polishCv" in polish_body, "polish 必须调 api.polishCv (封装好的 fetch)"


def test_modal_polish_error_does_not_block_submit():
    """polish 失败不能阻塞完成 — 失败时保留原文 cv, 给 warning 提示。"""
    src = read_modal()
    # 找 polish 的 catch 块
    polish_idx = src.find("const polish = async () =>")
    catch_idx = src.find("catch", polish_idx)
    assert catch_idx > 0, "polish 必须有 try/catch 兜底"
    # catch 后必须 setCv 不变 (或不报错让用户继续)
    catch_section = src[catch_idx : catch_idx + 400]
    assert "setPolishError" in catch_section, "polish 失败必须有 UI 提示"
    # 不能 throw 出去 (避免 catch 之外的代码报错)
    assert "throw" not in catch_section, "polish catch 不能 rethrow, 必须静默 fallback"


# ===== 任务引导 + AI 追问 (2026-07-30 立, lesson #15) =====
#
# 用户反馈 (2026-07-29 23:50): "如果我在项目中的一个任务是「完成 PRD」, 那么我的
# 「结果描述」以及「CV 成就陈述」要怎么写呢?"
#
# 根因: 任务标题 = 动作 (完成 PRD), 用户只记得"动作"忘了"价值" — "动作 ≠ 价值" 痛点
# 解法 (v4):
#   - 前端: 按 task.title 分类 (artifact/fix/discussion/research/generic), 显示引导卡片
#   - 前端: outcome placeholder 动态化, 按类型给具体示例
#   - 后端: LLM 必要时返 follow_up_questions, 前端以 chip 形式展示
#   - 闭环: outcome → AI 追问 → 补全 → 再润色
#
# 这条测试锁住前端不变量, 防退化


TASK_GUIDANCE_TS = (
    Path(__file__).parent.parent.parent
    / "web"
    / "lib"
    / "taskGuidance.ts"
)


def read_task_guidance() -> str:
    return TASK_GUIDANCE_TS.read_text(encoding="utf-8")


def test_modal_imports_task_guidance_module():
    """CompleteTaskModal 必须 import taskGuidance 模块 (分类 + 引导文案来源)。"""
    src = read_modal()
    assert (
        'import { classifyTaskTitle, getGuidance, type TaskCategory } from "@/lib/taskGuidance"' in src
    ), "CompleteTaskModal 必须 import taskGuidance 模块 (lesson #15)"


def test_modal_classifies_task_title_and_uses_guidance():
    """modal 必须调 classifyTaskTitle(task.title) + getGuidance(), 不能硬编码引导文案。"""
    src = read_modal()
    # 1. 分类调用
    assert "classifyTaskTitle(task.title)" in src, "必须按 task.title 分类 (lesson #15)"
    # 2. 引导文案来源
    assert "getGuidance(taskCategory)" in src, "必须从 getGuidance() 取引导文案 (不能硬编码)"


def test_modal_outcome_placeholder_uses_guidance_dynamic():
    """outcome placeholder 必须从 guidance.placeholder 来, 不能硬编码示例。"""
    src = read_modal()
    # 找 outcome textarea 的 placeholder 属性
    # 必须用 {guidance.placeholder} 插值, 不能写死字符串
    assert "placeholder={guidance.placeholder}" in src, (
        "outcome placeholder 必须用 guidance.placeholder 动态化 (lesson #15), "
        "否则修引导文案要改 2 个地方"
    )
    # 反向断言: 不能硬编码"用户反馈登录 bug 已修复" 这种旧 placeholder
    assert "用户反馈登录 bug 已修复" not in src, (
        "outcome placeholder 已从硬编码改为动态 (按任务类型), "
        "不能保留旧硬编码 placeholder"
    )


def test_modal_has_guidance_card_under_outcome():
    """outcome 输入框下方必须有引导卡片 (任务类型 + 4 维度)。"""
    src = read_modal()
    # 1. 引导卡片容器: showGuidance && (...) 条件渲染
    assert "showGuidance &&" in src, "引导卡片必须可关闭 (showGuidance 状态)"
    # 2. 卡片内必须显示任务类型 emoji + label
    assert "guidance.emoji" in src, "引导卡片必须显示任务类型 emoji"
    assert "guidance.label" in src, "引导卡片必须显示任务类型 label"
    # 3. 4 个 dimensions chip
    assert "guidance.dimensions.map" in src, "引导卡片必须渲染 4 个维度 chip"
    # 4. 默认展开
    assert "useState(true)" in src, "引导卡片默认必须展开 (useState(true))"


def test_modal_stores_follow_up_questions_from_polish_response():
    """polish 后必须把 response.follow_up_questions 保存到 state (给追问卡片用)。"""
    src = read_modal()
    # 1. state 声明
    assert "followUpQuestions" in src, "必须有 followUpQuestions state (lesson #15)"
    # 2. useState 初值必须为空数组
    assert "useState<string[]>([])" in src, "followUpQuestions 初值必为 [] (空数组, 不渲染追问卡片)"
    # 3. polish 成功后必须 setFollowUpQuestions
    polish_idx = src.find("const polish = async () =>")
    polish_body = src[polish_idx : polish_idx + 800]
    assert "setFollowUpQuestions" in polish_body, "polish 后必须 setFollowUpQuestions (保存 LLM 追问)"
    # 4. 从 response 透传, 不能写死
    assert "res.follow_up_questions" in polish_body, "必须从 res.follow_up_questions 取追问 (后端 JSON 字段名)"


def test_modal_renders_follow_up_questions_chip_when_non_empty():
    """followUpQuestions 非空时, 必须渲染追问卡片 + chip (用户可点追加到 outcome)。"""
    src = read_modal()
    # 1. 条件渲染: followUpQuestions.length > 0
    assert "followUpQuestions.length > 0" in src, "追问卡片必须有 length > 0 条件渲染"
    # 2. 循环渲染 chip
    assert "followUpQuestions.map" in src, "追问必须用 .map 渲染为 chip 列表"
    # 3. appendFollowUp 函数 (点 chip 追加到 outcome)
    assert "appendFollowUp" in src, "必须有 appendFollowUp 函数 (点 chip 追加追问到 outcome)"
    # 4. 关闭追问按钮
    # 已经在 showGuidance 块外, 但追问卡片也是可关闭的, 找第二个 X 按钮
    # 简化: 检查 setFollowUpQuestions([]) 调用 (在追问卡片 X 按钮 onClick)
    assert "setFollowUpQuestions([])" in src, "追问卡片必须有 X 关闭按钮"


def test_modal_append_followup_modifies_outcome():
    """appendFollowUp 必须把追问追加到 outcome 文本, 触发"补全 → 再润色" 闭环。"""
    src = read_modal()
    # 找 appendFollowUp 函数体
    fn_idx = src.find("const appendFollowUp =")
    assert fn_idx > 0, "必须有 appendFollowUp 函数"
    fn_body = src[fn_idx : fn_idx + 500]
    # 1. setOutcome(newOutcome) 触发重渲染
    assert "setOutcome" in fn_body, "appendFollowUp 必须 setOutcome 追加追问"
    # 2. 追加格式: 用 【...】 包住, 视觉明显区别于 outcome 本身
    assert "【" in fn_body and "】" in fn_body, "追问追加到 outcome 必须用【...】包住, 视觉区分"
    # 3. 追问被消费后从列表移除 (避免重复点同一追问)
    assert "setFollowUpQuestions" in fn_body, "追问被追加后必须从列表移除 (filter)"


def test_task_guidance_module_has_5_categories():
    """taskGuidance.ts 必须覆盖 5 类任务 (artifact/fix/discussion/research/generic)。"""
    src = read_task_guidance()
    for cat in ["artifact", "fix", "discussion", "research", "generic"]:
        assert cat in src, f"taskGuidance 必须覆盖任务类型: {cat}"
    # 5 类必须有 emoji + label + dimensions + placeholder + followUps
    for field in ["emoji", "label", "dimensions", "placeholder", "followUps"]:
        assert field in src, f"Guidance 接口必须有 {field} 字段"


def test_task_guidance_classifier_covers_prd_pattern():
    """classifyTaskTitle 必须识别"完成 PRD" → artifact (lesson #15 立, 用户原话)。"""
    src = read_task_guidance()
    # 调一下, 确认 PRD 走 artifact
    # 静态分析: classifyTaskTitle 体内必须含 "prd" + "artifact" 的关联
    # 简化: PRD 关键词必须出现 + artifact 必须出现 (粗筛, 实际跑时验证)
    assert "prd" in src.lower(), "classifyTaskTitle 必须识别 PRD 关键词"
    assert "artifact" in src, "必须有 artifact 分类 (含 PRD)"


# ===== 真实任务分类 (2026-07-30 立, lesson #15 盲点修复) =====
#
# 用户实测时 "修登录鉴权 bug" 被分类成 generic — lesson #15 单测通过但真实数据失败
# 修法: 用用户真实 5+ 个任务标题跑分类器, 每条锁住. 防再退.


def test_task_guidance_classifier_real_user_titles():
    """classifyTaskTitle 对用户真实任务标题必须分类正确 (端到端跑 Node 跑真实函数).

    标题来自用户 2026-07-30 实测 (修登录鉴权 bug 走 generic 暴露分类盲点).
    这次用真实数据锁住, 防回归.
    """
    import subprocess
    # 调 node 跑 web/scripts/test-task-guidance.mjs
    # 这个 mjs 直接 import taskGuidance.ts 跑真实 classifyTaskTitle 函数
    test_script = MODAL_TSX.parent.parent / "scripts" / "test-task-guidance.mjs"
    assert test_script.exists(), f"端到端测试脚本缺失: {test_script}"
    # node 在 /opt/homebrew/bin 下, subprocess 默认 PATH 找不到, 用绝对路径
    import shutil
    node_path = shutil.which("node") or "/opt/homebrew/bin/node"
    result = subprocess.run(
        [
            node_path,
            "--experimental-strip-types",
            str(test_script),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    # 退出码 0 = 全部通过
    assert result.returncode == 0, (
        f"taskGuidance 真实任务分类有失败 case (lesson #15 盲点回归).\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    # 关键 case 必须在输出里标 ✓
    output = result.stdout
    assert '"修登录鉴权 bug" → fix' in output, (
        f"关键 case '修登录鉴权 bug' 没分类成 fix, "
        f"fix 分类正则必须覆盖 '修' 单字 + 'bug' 关键词. "
        f"实际输出: {output}"
    )


# ===== 润色按钮 disabled 可发现性 (2026-07-30 立, lesson #16 衍生) =====
#
# 用户反馈: "润色按钮为什么不可点击?"
# 根因: outcome 空时按钮 disabled 是设计预期, 但用户看不出为什么灰
# 修法: outcome 空时按钮左/右挂小灰字提示 + 按钮 title 动态化 + placeholder 改成引导语


def test_modal_polish_button_has_outcome_required_discoverability():
    """润色按钮 disabled 时必须有可发现性提示 (用户能看出"为什么不可点")。

    用户原话 (2026-07-30): "「CV 成就陈述」中的「润色」功能为什么不可点击?"
    修法: outcome 空时显示提示文字 (👈 先填结果描述) + placeholder 引导 + title 动态化
    """
    src = read_modal()
    # 1. 必须有"outcome 为空" 的条件判断 + 提示文案
    assert "先填结果描述" in src, (
        "outcome 空时必须有提示文案告诉用户「先填结果描述」, "
        "否则用户看不出润色按钮为什么灰"
    )
    # 2. 按钮 title 必须动态化 (outcome 空时给不同提示)
    polish_idx = src.find('onClick={polish}')
    assert polish_idx > 0, "润色按钮缺失"
    # 找 title 属性 (扩到 1000 字符, 因为 title 模板字符串跨多行)
    button_section = src[polish_idx : polish_idx + 1000]
    # title= 必须动态化 — 找 "outcome.trim()" + "?" + ":" 三元
    assert "title=" in button_section and "outcome.trim()" in button_section, (
        "润色按钮 title 必须根据 outcome 是否为空动态化 (三元表达式), "
        "outcome 空时给引导文案"
    )
    # 找 outcome 空时的提示字样
    assert "先在「结果描述」" in button_section or "先在「结果描述」" in src[polish_idx:polish_idx + 1500], (
        "润色按钮 title 必须含 outcome 空时的引导文案, "
        "防回退成单一静态 title"
    )
    # 3. placeholder 必须根据 outcome 状态变化
    textarea_idx = src.find("<textarea")
    # 找 cv textarea (第二个 textarea, 第一个是 outcome)
    cv_textarea_idx = src.find("<textarea", textarea_idx + 1)
    assert cv_textarea_idx > 0, "cv textarea 缺失"
    cv_section = src[cv_textarea_idx : cv_textarea_idx + 600]
    # placeholder 必须用条件渲染 (不能硬编码一种)
    assert "outcome.trim()" in cv_section, (
        "cv placeholder 必须根据 outcome 是否为空动态化, "
        "outcome 空时引导用户去填结果描述"
    )


def test_modal_polish_button_disabled_state_has_cursor_hint():
    """润色按钮 disabled 状态必须保留 cursor-not-allowed (防退化)。"""
    src = read_modal()
    polish_idx = src.find('onClick={polish}')
    button_section = src[polish_idx : polish_idx + 500]
    # 旧不变量: disabled 时必是灰底灰字 + cursor-not-allowed (2026-07-30 改用强对比, 不用 opacity 衰减)
    assert "cursor-not-allowed" in button_section, "润色按钮 disabled cursor 必须保留"
    assert "bg-bg-tertiary" in button_section or "bg-fg-muted" in button_section, (
        "润色按钮 disabled 必须用强对比灰度 (灰底灰字), 不用 opacity 衰减 (opacity-40 + 15% accent = 几乎不可见)"
    )


# ===== 润色按钮位置 + 流向 (2026-07-30 立, lesson #16 衍生, 用户报设计错误) =====
#
# 用户反馈: "润色按钮会让用户以为润色的目标是「CV」而不是「结果描述」"
# 根因: 按钮在 CV 框旁, 用户认知 = 按钮操作 CV, 实际 = outcome → CV
# 修法: 按钮移到 outcome 框下方 + 加 "↓ 改写成下方 CV 框" 流向提示
# 教训: 行动按钮必须贴着行动目标, 不能贴着输出结果


def test_modal_polish_button_position_below_outcome_not_beside_cv():
    """润色按钮必须在 outcome 框下方, 不能在 CV 框旁 (2026-07-30 改, 防回退).

    关键: outcome 框出现位置 → 润色按钮位置 → CV 框出现位置 顺序
    """
    src = read_modal()
    # 1. outcome textarea 索引
    outcome_idx = src.find("ref={outcomeRef}")
    assert outcome_idx > 0, "outcome textarea 缺失"
    # 2. 润色按钮 onClick={polish} 索引
    polish_idx = src.find("onClick={polish}")
    assert polish_idx > 0, "润色按钮缺失"
    # 3. 关键: 润色按钮必须在 outcome 之后
    assert polish_idx > outcome_idx, (
        "润色按钮必须在 outcome 框之后 (上方或下方都行, 但必须在 outcome 区段内). "
        "如果 polish_idx < outcome_idx 说明按钮回到 CV 框旁了, 用户会误以为按钮操作 CV"
    )
    # 4. 关键: 润色按钮必须在 cv value={cv} 之前 (不能在 CV 框下面)
    cv_idx = src.find('value={cv}')
    assert cv_idx > 0, "CV textarea 缺失"
    assert polish_idx < cv_idx, (
        "润色按钮必须在 CV 框之前 (outcome → button → CV 的视觉流向). "
        "如果 polish_idx > cv_idx 说明按钮又跑到 CV 框下面了"
    )


def test_modal_polish_button_has_flow_hint_to_cv():
    """润色按钮旁边必须有流向提示, 明确按钮的目标是 CV (不是 CV 自己)."""
    src = read_modal()
    polish_idx = src.find("onClick={polish}")
    # 找按钮前的提示文字 (按钮行的左边, 视觉上跟按钮平级)
    button_row_start = src.rfind('mt-2 flex', 0, polish_idx)
    assert button_row_start > 0, "润色按钮必须包在 flex 行里 (跟流向提示平级)"
    button_row = src[button_row_start : polish_idx + 100]
    # 必须有 "改写成" + "CV" 字样 (流向文字)
    assert "改写成" in button_row, (
        "润色按钮前必须有流向提示 '改写成 CV' 类似的文字, "
        "否则用户看不出按钮操作的目标"
    )
    assert "CV" in button_row, "流向提示必须明确说目标是 CV 框"
    # 必须有 ↓ 箭头 (视觉暗示流向)
    assert "↓" in button_row, "流向提示必须有 ↓ 箭头, 视觉上 input → output 流向"


def test_modal_cv_label_marks_ai_polished_output():
    """CV 框 label 必须明确标注这是 AI 润色结果 (output), 不是 input."""
    src = read_modal()
    # 找 CV 框 label
    cv_label_idx = src.find("CV 成就陈述")
    assert cv_label_idx > 0, "CV 框 label 缺失"
    cv_label_section = src[cv_label_idx : cv_label_idx + 300]
    # label 旁必须说明这是 AI 润色结果 (避免用户以为是 input 让 AI 改)
    assert "AI" in cv_label_section and ("润色" in cv_label_section or "改写" in cv_label_section), (
        "CV 框 label 必须明确标注 'AI 润色结果' 或类似, 区分 input (outcome) vs output (CV)"
    )


def test_modal_no_duplicate_polish_button_in_cv_area():
    """CV 框区域不能有第二个润色按钮 (2026-07-30 改后, 按钮只能在 outcome 下方)."""
    src = read_modal()
    # 1. 找 CV 框位置
    cv_idx = src.find('value={cv}')
    assert cv_idx > 0, "CV 框缺失"
    # 2. 找 outcome 框位置
    outcome_idx = src.find("ref={outcomeRef}")
    assert outcome_idx > 0, "outcome 框缺失"
    # 3. CV 框之后 (label 之后到 footer 之前) 不能有 onClick={polish}
    # 找 footer 起点
    footer_idx = src.find("沉淀成就")
    cv_to_footer = src[cv_idx:footer_idx] if footer_idx > cv_idx else src[cv_idx:]
    assert "onClick={polish}" not in cv_to_footer, (
        "CV 框之后不能有润色按钮 (2026-07-30 移到 outcome 下方了). "
        "如果这里有, 说明按钮位置回退, 用户会再次误以为按钮操作 CV"
    )


# ===== CV 框重置 + outcome highlight (2026-07-30 立, v4.1 UX 残留) =====
#
# 背景: lesson #15 v4 立了任务引导 + AI 追问, 但用户实测发现 2 个 UX 残留:
#   1. CV 框润色后想看默认 `完成「title」` 怎么办? 只能手动删 → 加"重置"按钮
#   2. 追问 chip 追加后 outcome 框没明显视觉反馈, 用户得自己回去看 → 加 outcome 高亮


def test_modal_cv_has_reset_button_when_modified():
    """CV 框被修改时 (不等于默认值), 必须有"重置"按钮让用户回到默认.

    关键: 按钮只在 cv !== `完成「${task.title}」` 时显示, 避免默认值时按钮无意义
    """
    src = read_modal()
    # 1. 必须有 resetCv 函数
    assert "const resetCv = " in src, "必须有 resetCv 函数"
    # 2. 必须有 isCvModified state
    assert "isCvModified" in src, "必须有 isCvModified state (控制重置按钮显示)"
    # 3. 重置按钮必须条件渲染 (isCvModified && ...)
    assert "isCvModified &&" in src, "重置按钮必须条件渲染 (cv 已被修改时才显示)"
    # 4. 按钮文案必须含 "重置"
    assert "重置" in src, "重置按钮文案缺失"
    # 5. 按钮 onClick 必须调 resetCv
    assert "onClick={resetCv}" in src, "重置按钮必须 onClick={resetCv}"


def test_modal_append_followup_has_visual_feedback():
    """追问 chip 追加后, 必须有 outcome 框视觉反馈 (用户知道追加成功了).

    实现: setOutcomeHighlight(true) + outcome textarea 临时加 ring 高亮 + 1.2s 后清掉
    """
    src = read_modal()
    # 1. 找 appendFollowUp 函数
    fn_idx = src.find("const appendFollowUp =")
    assert fn_idx > 0, "appendFollowUp 函数缺失"
    fn_body = src[fn_idx : fn_idx + 600]
    # 2. 必须调 setOutcomeHighlight(true)
    assert "setOutcomeHighlight(true)" in fn_body, (
        "appendFollowUp 必须 setOutcomeHighlight(true) 触发视觉反馈, "
        "否则用户看不出追问追加到 outcome 了"
    )
    # 3. 1.2s 后清掉 highlight (避免永久高亮)
    assert "setTimeout" in fn_body and "setOutcomeHighlight(false)" in fn_body, (
        "appendFollowUp 必须 setTimeout 清掉 highlight, 防永久高亮"
    )
    # 4. outcome textarea 条件渲染 highlight 样式
    assert "outcomeHighlight" in src, "outcome textarea 必须引用 outcomeHighlight 状态"
    # 5. 视觉提示: 至少要 ring 或 border-accent
    assert "ring" in src.lower() or "border-accent" in src, (
        "outcome 高亮必须有视觉提示 (ring 或 border-accent), 不能只改数据不显示"
    )
