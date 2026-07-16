#!/usr/bin/env node
/**
 * 验证 applyStreamEvent 累积行为（不依赖 React/JSX）。
 * 跑法：node web/scripts/test_stream_accumulate.mjs
 *
 * 这是 ChatWindow 的纯函数 applyStreamEvent 的等价实现 + 4 个测试 case。
 * 如果未来引入了 vitest，可以把这个脚本改成 vitest spec。
 */
import assert from "node:assert/strict";

// 复刻 applyStreamEvent（保持与 ChatWindow.tsx 一致；改时两边同步）
function applyStreamEvent(events, event) {
  if (event.type === "text") {
    const delta = event.data?.delta ?? "";
    if (!delta) return events;
    const last = events[events.length - 1];
    if (last && last.kind === "text") {
      const updated = [...events];
      updated[updated.length - 1] = { ...last, content: last.content + delta };
      return updated;
    }
    return [...events, { kind: "text", content: delta }];
  }
  if (event.type === "tool_start") {
    return [
      ...events,
      {
        kind: "tool",
        tc: {
          id: event.data.id,
          name: event.data.name,
          args: event.data.args || {},
          status: "calling",
        },
      },
    ];
  }
  if (event.type === "tool_end") {
    return events.map((e) =>
      e.kind === "tool" && e.tc.id === event.data.id
        ? {
            ...e,
            tc: {
              ...e.tc,
              result: event.data.result,
              ok: event.data.ok,
              status: event.data.ok ? "done" : "error",
            },
          }
        : e
    );
  }
  return events;
}

// ===== 测试 =====

let events = [];

// 1) 多个连续 text 事件合并到同一个 text 段
events = applyStreamEvent(events, { type: "text", data: { delta: "我先" } });
events = applyStreamEvent(events, { type: "text", data: { delta: "看下项目" } });
assert.deepEqual(events, [
  { kind: "text", content: "我先看下项目" },
]);

// 2) tool_start append 新 tool 事件
events = applyStreamEvent(events, {
  type: "tool_start",
  data: { id: "tool-1", name: "list_projects", args: {} },
});
assert.equal(events.length, 2);
assert.equal(events[1].kind, "tool");
assert.equal(events[1].tc.status, "calling");
assert.equal(events[1].tc.id, "tool-1");

// 3) text 在 tool 之后 → 新 text 段（不合并到 tool 之前那个 text）
events = applyStreamEvent(events, { type: "text", data: { delta: "找到了" } });
assert.equal(events.length, 3);
assert.equal(events[1].kind, "tool");
assert.equal(events[2].kind, "text");
assert.equal(events[2].content, "找到了");

// 4) tool_end 找对应 tool 更新 status + result
events = applyStreamEvent(events, {
  type: "tool_end",
  data: { id: "tool-1", result: '{"ok":true}', ok: true },
});
assert.equal(events.length, 3);
assert.equal(events[1].tc.status, "done");
assert.equal(events[1].tc.result, '{"ok":true}');
assert.equal(events[1].tc.ok, true);

// 5) 完整 LLM 流：text → tool → text → tool → text（交错）
events = [];
events = applyStreamEvent(events, { type: "text", data: { delta: "先" } });
events = applyStreamEvent(events, { type: "text", data: { delta: "查" } });
events = applyStreamEvent(events, {
  type: "tool_start",
  data: { id: "a", name: "list_projects", args: {} },
});
events = applyStreamEvent(events, {
  type: "tool_end",
  data: { id: "a", result: "[]", ok: true },
});
events = applyStreamEvent(events, { type: "text", data: { delta: "再建任务" } });
events = applyStreamEvent(events, {
  type: "tool_start",
  data: { id: "b", name: "add_task", args: { title: "x" } },
});
events = applyStreamEvent(events, {
  type: "tool_end",
  data: { id: "b", result: "{}", ok: true },
});
events = applyStreamEvent(events, { type: "text", data: { delta: "完成" } });
assert.equal(events.length, 5);
assert.deepEqual(
  events.map((e) => (e.kind === "text" ? `text:"${e.content}"` : `tool:${e.tc.name}/${e.tc.status}`)),
  ["text:\"先查\"", "tool:list_projects/done", "text:\"再建任务\"", "tool:add_task/done", "text:\"完成\""]
);

console.log("✓ 5 个测试全过 — applyStreamEvent 行为正确");
