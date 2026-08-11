# 2026-08-11 — 核心闭环收敛

## 决定

将职业输出收敛到本地、确定性的 Composer：周报、月度总结、述职和 CV 只从 `ready` 成就读取。`pending` 和 `needs_data` 留在补证据路径，不再被任何正式输出混入。

同步提供版本化 `cockpit-career-memory` 导出、预览导入和导入前备份；密钥与 settings 永不进入归档，冲突 ID 不合并、不覆盖。确认反馈按 trace/action 去重，避免重试被误计为多次采用。

## 推翻关系

- 推翻独立浏览器模板拼装与单独 `/cv` 产品入口；`/cv` 仅保留至 `/report?type=cv&range=all` 的兼容跳转。
- 推翻以质量分数、强动词、标签和 PR 产物为核心的日常产品面；保留事实、证据和用户确认。

## 验证

- 后端全量：457 passed, 2 skipped。
- 前端：`npx tsc --noEmit`；输出中心脚本通过。
- 真实两周 dogfooding 是后续证据门，不由合成数据替代。
