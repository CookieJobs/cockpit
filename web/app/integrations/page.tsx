"use client";

/**
 * /integrations — 接入中心 (2026-08-02 v0.5a.1 立)
 *
 * 哲学: 让用户**一键**把 cockpit MCP server 注册到 Claude Code / Cursor /
 *       Trae / Cline / Continue / WorkBuddy, 不用手改 JSON。
 *
 * 两种安装方式 (后端按 type 区分):
 *   - json  (Claude Code / Cursor / Trae / Cline / Continue)
 *     → 后端读现有 config → 只改 mcpServers.cockpit 段 → 写回
 *     → 前端点 [安装] 按钮直接调 POST /api/integrations/install
 *   - command (WorkBuddy)
 *     → 后端不写 config, 返 install_command 让用户复制到 WorkBuddy 对话框
 *
 * 状态显示:
 *   - 后端 GET /supported 拿每个 agent 的 is_installed (json 类型读文件判断, command 类型恒 false)
 *   - 操作后本地乐观更新 + 重新 fetch 保证准确
 */
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import {
  ArrowLeft,
  Plug,
  Check,
  Copy,
  Download,
  Terminal,
  FolderOpen,
  RefreshCw,
  ExternalLink,
  Loader2,
} from "lucide-react";
import { api, type IntegrationAgent, type IntegrationsResponse } from "@/lib/api";
import { useToast } from "@/components/Toast";

export default function IntegrationsPage() {
  const { data, isLoading, mutate } = useSWR<IntegrationsResponse>(
    "/api/integrations/supported",
    () => api.listSupportedIntegrations(),
  );
  const toast = useToast();

  // 操作中的 agent_id (防双击)
  const [busyId, setBusyId] = useState<string | null>(null);
  // 复制的 command 内容 (用于"已复制"反馈)
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  // 复制到剪贴板 + 1.5s 反馈
  const handleCopy = useCallback(async (text: string, key: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedKey(key);
      toast.success("已复制到剪贴板");
      setTimeout(() => setCopiedKey(null), 1500);
    } catch (e) {
      toast.info("复制失败,请手动选择文本");
      console.error(e);
    }
  }, [toast]);

  // 一键安装 (json 类型)
  const handleInstall = useCallback(async (agent: IntegrationAgent) => {
    if (agent.type !== "json") return;
    setBusyId(agent.id);
    try {
      const res = await api.installIntegration(agent.id);
      toast.success(`${agent.name} 已接入 ✨ · ${res.post_install}`);
      await mutate();
    } catch (e: any) {
      toast.info(`安装失败: ${e?.message ?? "未知错误"}`);
    } finally {
      setBusyId(null);
    }
  }, [mutate, toast]);

  // 卸载 (json 类型)
  const handleUninstall = useCallback(async (agent: IntegrationAgent) => {
    if (agent.type !== "json") return;
    if (!confirm(`确认从 ${agent.name} 卸载 cockpit MCP?`)) return;
    setBusyId(agent.id);
    try {
      const res = await api.uninstallIntegration(agent.id);
      toast.success(
        res.removed
          ? `${agent.name} 已卸载`
          : `${agent.name} 原本就没接入,无需操作`,
      );
      await mutate();
    } catch (e: any) {
      toast.info(`卸载失败: ${e?.message ?? "未知错误"}`);
    } finally {
      setBusyId(null);
    }
  }, [mutate, toast]);

  // 安装: 复制 install_command (command 类型 — WorkBuddy)
  const handleCopyCommand = useCallback((agent: IntegrationAgent) => {
    if (agent.type !== "command" || !agent.install_command) return;
    handleCopy(agent.install_command, `cmd-${agent.id}`);
  }, [handleCopy]);

  // 复制手动配置 (command 类型的 manual_command 包含完整步骤)
  const handleCopyManual = useCallback((agent: IntegrationAgent) => {
    if (agent.type !== "command" || !agent.manual_command) return;
    handleCopy(agent.manual_command, `manual-${agent.id}`);
  }, [handleCopy]);

  // 复制 config 路径 (json 类型 — 给高级用户自己查看/编辑)
  const handleCopyPath = useCallback((agent: IntegrationAgent) => {
    if (!agent.current_os_path) return;
    handleCopy(agent.current_os_path, `path-${agent.id}`);
  }, [handleCopy]);

  return (
    <div className="min-h-screen bg-bg text-fg">
      {/* 顶栏 */}
      <div className="border-b border-border bg-bg-secondary/40 sticky top-0 z-10 backdrop-blur">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="text-fg-secondary hover:text-fg transition p-1.5 rounded hover:bg-bg-tertiary"
              title="回主页"
            >
              <ArrowLeft size={16} />
            </Link>
            <div>
              <h1 className="text-[18px] font-semibold tracking-tight flex items-center gap-2">
                <Plug size={16} className="text-accent" />
                集成中心
              </h1>
              <p className="text-[12px] text-fg-muted mt-0.5">
                一键把 cockpit MCP 注册到 Claude Code / Cursor / 其他 agent
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3 text-[12px] text-fg-muted">
            {data && (
              <>
                <span className="hidden sm:flex items-center gap-1.5">
                  <FolderOpen size={11} />
                  <code className="font-mono text-[11px] text-fg-secondary">
                    {data.cockpit_path}
                  </code>
                </span>
                <span className="px-2 py-0.5 rounded-full bg-bg-tertiary text-fg-secondary font-medium">
                  {data.current_os}
                </span>
                <button
                  onClick={() => mutate()}
                  className="p-1.5 rounded hover:bg-bg-tertiary text-fg-muted hover:text-fg transition"
                  title="刷新状态"
                >
                  <RefreshCw size={12} />
                </button>
              </>
            )}
          </div>
        </div>
      </div>

      {/* 主内容 */}
      <div className="max-w-5xl mx-auto px-6 py-8">
        {isLoading && (
          <div className="text-center py-12 text-fg-muted flex items-center justify-center gap-2">
            <Loader2 size={14} className="animate-spin" />
            加载中...
          </div>
        )}

        {data && (
          <>
            {/* 总览条 */}
            <div className="mb-6 p-4 rounded-lg border border-border bg-bg-secondary/30 flex items-center justify-between">
              <div className="text-[13px] text-fg-secondary">
                已接入{" "}
                <strong className="text-accent font-semibold tabular-nums">
                  {data.agents.filter((a) => a.is_installed).length}
                </strong>{" "}
                / {data.agents.length} 个 agent
              </div>
              <div className="text-[11px] text-fg-muted">
                不用 JSON · 不破坏现有 config · 只改 mcpServers.cockpit 段
              </div>
            </div>

            {/* 6 张卡片 */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {data.agents.map((agent) => (
                <IntegrationCard
                  key={agent.id}
                  agent={agent}
                  busy={busyId === agent.id}
                  copiedKey={copiedKey}
                  onInstall={() => handleInstall(agent)}
                  onUninstall={() => handleUninstall(agent)}
                  onCopyCommand={() => handleCopyCommand(agent)}
                  onCopyManual={() => handleCopyManual(agent)}
                  onCopyPath={() => handleCopyPath(agent)}
                />
              ))}
            </div>

            {/* 底部说明 */}
            <div className="mt-10 p-5 rounded-lg border border-border bg-bg-secondary/20 text-[12px] text-fg-muted space-y-2">
              <div className="text-fg-secondary font-medium text-[13px]">
                设计说明
              </div>
              <ul className="space-y-1.5 pl-1">
                <li className="flex gap-2">
                  <span className="text-accent">·</span>
                  <span>
                    <strong className="text-fg-secondary">json 类型</strong>:
                    后端读现有配置文件 → 只改
                    <code className="mx-1 px-1.5 py-0.5 rounded bg-bg-tertiary text-[11px] font-mono">
                      mcpServers.cockpit
                    </code>
                    段 → 写回(临时文件 + rename, 不会半写状态)。其他 server 全部保留。
                  </span>
                </li>
                <li className="flex gap-2">
                  <span className="text-accent">·</span>
                  <span>
                    <strong className="text-fg-secondary">command 类型</strong>:
                    WorkBuddy 不写 JSON,走对话命令安装(WorkBuddy 体验最好的一部分)。
                    点 [复制安装命令] 把
                    <code className="mx-1 px-1.5 py-0.5 rounded bg-bg-tertiary text-[11px] font-mono">
                      workbuddy mcp install cockpit
                    </code>
                    粘到 WorkBuddy 对话框。
                  </span>
                </li>
                <li className="flex gap-2">
                  <span className="text-accent">·</span>
                  <span>
                    <strong className="text-fg-secondary">Trae 特殊</strong>:
                    Trae 不支持 user-level,只在项目根目录写
                    <code className="mx-1 px-1.5 py-0.5 rounded bg-bg-tertiary text-[11px] font-mono">
                      .trae/mcp.json
                    </code>
                    。所以你必须在 cockpit 项目目录跑这一页,才能装到 Trae。
                  </span>
                </li>
                <li className="flex gap-2">
                  <span className="text-accent">·</span>
                  <span>
                    想看 5 个 MCP 工具的清单?读
                    <Link href="/" className="ml-1 text-accent hover:underline">
                      SKILL.md
                    </Link>
                    或在 Claude Code / Cursor 输入 "列 cockpit 项目" 测试接入。
                  </span>
                </li>
              </ul>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// 单个 agent 卡片
// ============================================================================

function IntegrationCard({
  agent,
  busy,
  copiedKey,
  onInstall,
  onUninstall,
  onCopyCommand,
  onCopyManual,
  onCopyPath,
}: {
  agent: IntegrationAgent;
  busy: boolean;
  copiedKey: string | null;
  onInstall: () => void;
  onUninstall: () => void;
  onCopyCommand: () => void;
  onCopyManual: () => void;
  onCopyPath: () => void;
}) {
  const isJson = agent.type === "json";
  const isInstalled = agent.is_installed;

  return (
    <div
      className={`p-4 rounded-lg border transition ${
        isInstalled
          ? "border-accent/40 bg-accent/5"
          : "border-border bg-bg-secondary/30 hover:border-fg-muted"
      }`}
    >
      {/* 头部: 名字 + 状态 badge */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-[14px] font-semibold text-fg">
              {agent.name}
            </h3>
            {agent.scope && (
              <span
                className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                  agent.scope === "user"
                    ? "bg-bg-tertiary text-fg-secondary"
                    : "bg-warning/5 text-warning"
                }`}
                title={agent.scope === "user" ? "全机器生效" : "只在当前项目生效"}
              >
                {agent.scope === "user" ? "全局" : "项目级"}
              </span>
            )}
          </div>
          <p className="text-[11px] text-fg-muted mt-0.5">
            {isJson ? "JSON 配置文件" : "对话命令安装"}
          </p>
        </div>

        <StatusBadge installed={isInstalled} type={agent.type} />
      </div>

      {/* 描述 */}
      <p className="text-[12px] text-fg-secondary mb-3 leading-relaxed">
        {agent.note}
      </p>

      {/* json 类型: 当前 OS 路径 */}
      {isJson && agent.current_os_path && (
        <div className="mb-3 flex items-center gap-1.5 group">
          <FolderOpen size={11} className="text-fg-muted flex-shrink-0" />
          <code className="font-mono text-[10.5px] text-fg-muted truncate flex-1 min-w-0">
            {agent.current_os_path}
          </code>
          <button
            onClick={onCopyPath}
            className="opacity-0 group-hover:opacity-100 transition p-1 rounded hover:bg-bg-tertiary text-fg-muted hover:text-fg"
            title="复制路径"
          >
            {copiedKey === `path-${agent.id}` ? (
              <Check size={10} className="text-success" />
            ) : (
              <Copy size={10} />
            )}
          </button>
        </div>
      )}

      {/* command 类型: install_command */}
      {!isJson && agent.install_command && (
        <div className="mb-3 p-2 rounded bg-bg-tertiary/50 border border-border">
          <div className="flex items-center gap-1.5 mb-1 text-[10px] text-fg-muted">
            <Terminal size={10} />
            <span>在 WorkBuddy 对话框输入:</span>
          </div>
          <code className="font-mono text-[11.5px] text-fg block break-all">
            {agent.install_command}
          </code>
        </div>
      )}

      {/* 操作按钮区 */}
      <div className="flex items-center gap-2 mb-2">
        {isJson ? (
          <>
            {isInstalled ? (
              <button
                onClick={onUninstall}
                disabled={busy}
                className="flex-1 text-[12px] font-medium px-3 py-1.5 rounded
                  border border-border bg-bg-secondary hover:bg-bg-tertiary
                  text-fg-secondary hover:text-fg transition
                  disabled:opacity-50 disabled:cursor-not-allowed
                  flex items-center justify-center gap-1.5"
              >
                {busy ? (
                  <Loader2 size={11} className="animate-spin" />
                ) : (
                  <Download size={11} />
                )}
                卸载
              </button>
            ) : (
              <button
                onClick={onInstall}
                disabled={busy}
                className="flex-1 text-[12px] font-medium px-3 py-1.5 rounded
                  bg-accent text-bg hover:bg-accent/90 transition
                  disabled:opacity-50 disabled:cursor-not-allowed
                  flex items-center justify-center gap-1.5"
              >
                {busy ? (
                  <Loader2 size={11} className="animate-spin" />
                ) : (
                  <Download size={11} />
                )}
                一键安装
              </button>
            )}
          </>
        ) : (
          <>
            <button
              onClick={onCopyCommand}
              className="flex-1 text-[12px] font-medium px-3 py-1.5 rounded
                bg-accent text-bg hover:bg-accent/90 transition
                flex items-center justify-center gap-1.5"
            >
              {copiedKey === `cmd-${agent.id}` ? (
                <>
                  <Check size={11} />
                  已复制
                </>
              ) : (
                <>
                  <Copy size={11} />
                  复制安装命令
                </>
              )}
            </button>
            <button
              onClick={onCopyManual}
              className="text-[12px] font-medium px-2.5 py-1.5 rounded
                border border-border bg-bg-secondary hover:bg-bg-tertiary
                text-fg-secondary hover:text-fg transition flex items-center gap-1"
              title="复制完整步骤(包含手动配置)"
            >
              {copiedKey === `manual-${agent.id}` ? (
                <Check size={11} className="text-success" />
              ) : (
                <Copy size={11} />
              )}
              详细
            </button>
          </>
        )}
      </div>

      {/* post_install 提示 + docs link */}
      <div className="pt-2 border-t border-border/50 flex items-center justify-between gap-2">
        <span className="text-[10.5px] text-fg-muted leading-relaxed flex-1">
          安装后: {agent.post_install}
        </span>
        {agent.docs_url && (
          <a
            href={agent.docs_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-fg-muted hover:text-accent transition flex-shrink-0"
            title="官方文档"
          >
            <ExternalLink size={10} />
          </a>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// 状态徽章
// ============================================================================

function StatusBadge({
  installed,
  type,
}: {
  installed: boolean;
  type: "json" | "command";
}) {
  if (installed) {
    return (
      <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold bg-success/15 text-success border border-success/30 flex items-center gap-1 flex-shrink-0">
        <Check size={9} strokeWidth={3} />
        已接入
      </span>
    );
  }
  if (type === "command") {
    return (
      <span className="text-[10px] px-2 py-0.5 rounded-full font-medium bg-bg-tertiary text-fg-muted border border-border flex-shrink-0">
        待手动安装
      </span>
    );
  }
  return (
    <span className="text-[10px] px-2 py-0.5 rounded-full font-medium bg-fg-muted/10 text-fg-muted border border-border flex-shrink-0">
      未接入
    </span>
  );
}
