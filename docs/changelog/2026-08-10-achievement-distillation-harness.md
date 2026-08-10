# 2026-08-10 — Achievement Distillation Harness v1

- 建立 Capability Contract、30 条版本化评测集、L1 硬约束、离线 runner、JSON report 和 release gate。
- 增加严格 JSON 的可替换 LLM Judge 接口；缺少语义评分时 gate 默认阻断。
- `polish_cv` 加入运行时 P0 防护：拦截无依据数字、实体与归属升级，并安全回退为待补充。
- 新增 append-only trace、任务完成与 trace 关联、以及用户 CV 编辑反馈记录。
- 当前仓库未配置 CI workflow；统一本地入口为 `make harness`，后续 CI 应复用该命令。
