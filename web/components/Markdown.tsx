"use client";

/**
 * Markdown 渲染组件 (2026-07-22 升级 v2)
 *
 * v1.0 是手写极简解析器，只支持 # 标题 / 无序列表 / **bold** / `code`，
 * LLM 常用的有序列表 / 任务清单 / 引用 / 表格 / 多行代码块 / 链接 / 分割线
 * 全不识别 → Agent 拆任务时的 "1. **xxx**" 退化成裸文本段落。
 *
 * v2 升级到 react-markdown + remark-gfm (GFM) + rehype-highlight：
 * - 完整 CommonMark + GFM (表格 / 任务清单 / 删除线 / autolink)
 * - 代码块语法高亮 (highlight.js github-dark 主题)
 * - 链接默认 target="_blank" rel="noopener noreferrer"，避免切走对话
 *
 * 流式期间也跑 markdown (用户 2026-07-22 拍板) — 代价是增量解析时
 * block 结构变化 (比如 "1. " 后接数字变成 <ol>) 会小闪烁，可接受。
 */
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github-dark.css";

export function MarkdownView({ content }: { content: string }) {
  return (
    <div className="markdown text-sm">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          // 链接新窗口打开，避免切走对话
          a: ({ node: _node, ...props }) => (
            <a {...props} target="_blank" rel="noopener noreferrer" />
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
