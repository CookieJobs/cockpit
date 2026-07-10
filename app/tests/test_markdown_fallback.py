"""Markdown tool call fallback 测试。

适用场景：某些模型（如 MiniMax abab6.5s-chat）在拿到 tool_result 后
倾向于输出 `functions.xxx(args)` markdown code block 而不是真的调 tool_use。
chat_engine 检测到这种 markdown 伪调用会自动解析执行。
"""
from app.llm.chat_engine import _parse_markdown_tool_calls


def test_basic():
    """基本匹配。"""
    text = '```typescript\nfunctions.add_project({"name": "测试"})\n```'
    calls = _parse_markdown_tool_calls(text)
    assert len(calls) == 1
    assert calls[0].name == "add_project"
    assert calls[0].args == {"name": "测试"}


def test_multiple_calls():
    """匹配多个调用。"""
    text = (
        'functions.add_project({"name": "X"})\n'
        'functions.add_task({"project": "proj_1", "title": "任务1"})\n'
        'functions.add_task({"project": "proj_1", "title": "任务2"})\n'
    )
    calls = _parse_markdown_tool_calls(text)
    assert len(calls) == 3
    assert calls[0].name == "add_project"
    assert calls[1].name == "add_task"
    assert calls[1].args["title"] == "任务1"
    assert calls[2].args["title"] == "任务2"


def test_whitelist_blocks_unknown():
    """非白名单工具不解析。"""
    text = 'functions.dangerous_thing({"x": 1})'
    calls = _parse_markdown_tool_calls(text)
    assert len(calls) == 0


def test_dedup_same_args():
    """相同参数重复调用去重。"""
    text = (
        'functions.add_task({"project": "p1", "title": "X"})\n'
        'functions.add_task({"project": "p1", "title": "X"})\n'
    )
    calls = _parse_markdown_tool_calls(text)
    assert len(calls) == 1


def test_empty_text():
    """空文本返回空列表。"""
    assert _parse_markdown_tool_calls("") == []
    assert _parse_markdown_tool_calls(None) == []


def test_bare_string_arg():
    """裸字符串参数解析。"""
    text = 'functions.add_project("项目交接")'
    calls = _parse_markdown_tool_calls(text)
    assert len(calls) == 1
    assert calls[0].args == {"name": "项目交接"}


def test_multiline_json_arg():
    """多行 JSON 参数。"""
    text = """functions.add_task({
        "project": "proj_1",
        "title": "复杂任务",
        "priority": "高"
    })"""
    calls = _parse_markdown_tool_calls(text)
    assert len(calls) == 1
    assert calls[0].name == "add_task"
    assert calls[0].args["title"] == "复杂任务"
    assert calls[0].args["priority"] == "高"


def test_unrelated_text_ignored():
    """无关文本不解析。"""
    text = "这是普通文字，没有 functions 调用。"
    assert _parse_markdown_tool_calls(text) == []


def test_id_format():
    """fallback 生成的 ID 应该有 md- 前缀。"""
    calls = _parse_markdown_tool_calls('functions.list_projects()')
    assert len(calls) == 1
    assert calls[0].id.startswith("md-")