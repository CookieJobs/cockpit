// 简单 Markdown 解析（v1.0 轻量级，LLM 接入后可替换为 react-markdown）
// 支持：**bold** *italic* `code` 标题 # ## ### 列表 - 1.

import React from "react";

export function renderMarkdown(text: string): React.ReactNode[] {
  const lines = text.split("\n");
  const nodes: React.ReactNode[] = [];
  let listBuffer: string[] = [];
  let key = 0;

  const flushList = () => {
    if (listBuffer.length > 0) {
      nodes.push(
        <ul key={key++} className="my-1">
          {listBuffer.map((item, i) => (
            <li key={i} className="ml-4">
              {renderInline(item)}
            </li>
          ))}
        </ul>
      );
      listBuffer = [];
    }
  };

  for (const line of lines) {
    if (line.match(/^###\s+/)) {
      flushList();
      nodes.push(
        <h3 key={key++} className="text-base font-semibold mt-2 mb-1">
          {line.replace(/^###\s+/, "")}
        </h3>
      );
    } else if (line.match(/^##\s+/)) {
      flushList();
      nodes.push(
        <h2 key={key++} className="text-lg font-semibold mt-3 mb-1">
          {line.replace(/^##\s+/, "")}
        </h2>
      );
    } else if (line.match(/^#\s+/)) {
      flushList();
      nodes.push(
        <h1 key={key++} className="text-xl font-semibold mt-3 mb-2">
          {line.replace(/^#\s+/, "")}
        </h1>
      );
    } else if (line.match(/^[-*]\s+/)) {
      listBuffer.push(line.replace(/^[-*]\s+/, ""));
    } else if (line.trim() === "") {
      flushList();
    } else {
      flushList();
      nodes.push(
        <p key={key++} className="my-1">
          {renderInline(line)}
        </p>
      );
    }
  }
  flushList();
  return nodes;
}

function renderInline(text: string): React.ReactNode {
  // 解析 **bold** `code` *italic*
  const parts: React.ReactNode[] = [];
  let remaining = text;
  let key = 0;

  const patterns: Array<[RegExp, (match: string) => React.ReactNode]> = [
    [/\*\*([^*]+)\*\*/g, (m) => <strong key={key++} className="text-accent font-semibold">{m.slice(2, -2)}</strong>],
    [/`([^`]+)`/g, (m) => <code key={key++} className="bg-bg-tertiary px-1 py-0.5 rounded text-sm">{m.slice(1, -1)}</code>],
  ];

  // 简化处理：按 ** 分割
  const segments = text.split(/(\*\*[^*]+\*\*)/g);
  return segments.map((seg, i) => {
    if (seg.match(/^\*\*[^*]+\*\*$/)) {
      return (
        <strong key={i} className="text-accent font-semibold">
          {seg.slice(2, -2)}
        </strong>
      );
    }
    // 处理 `code`
    const codeParts = seg.split(/(`[^`]+`)/g);
    return codeParts.map((cp, j) => {
      if (cp.match(/^`[^`]+`$/)) {
        return (
          <code key={`${i}-${j}`} className="bg-bg-tertiary px-1 py-0.5 rounded text-sm">
            {cp.slice(1, -1)}
          </code>
        );
      }
      return cp;
    });
  });
}
