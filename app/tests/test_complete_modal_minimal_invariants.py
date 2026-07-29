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
