# 03 — FastAPI / 工具链 Lessons

> 三个都是"看着该跑却没跑起来"类的坑。生产环境常见的 silent failure。

## #3. `/api/tasks/{tid}/complete` simple type 参数 body 丢失（修于 2026-07-16）

- **症状**：前端 CompleteTaskModal POST 4 字段 (outcome/cv/reflection/cv_status) 给后端，任务**确实完成了**, achievement **也入库了**, 但**所有 4 字段值都是空字符串**。
- **根因**：路由端点签名是 `complete_task(tid, outcome: str = "", reflection: str = "", cv: str = "", cv_status: str = "ready")`。FastAPI 看到 `str` 这种 simple type 参数会**默认当 query 解析** — 整个 JSON body 被忽略，所有字段走默认值空串。
- **教训**：
  - **FastAPI 端点接 JSON body 必须用 Pydantic BaseModel**，不要用 simple type 参数（这是 memory 里 `python-web-backend-gotchas` 第 3 条，但 storage 层 pytest 测不到这个 — 端点级才暴露）
  - **测试要打到端点级**：storage 层测试全过不代表 API 行为正确。要加 `TestClient` 走 HTTP 真实路径的回归测试。
  - 这次 bug 潜伏了至少一个迭代期 — `add_task` 用了 `TaskCreate` Pydantic model 没事，但 `complete_task` 用了 simple type 就翻车
- **修法位置**：
  - 后端：`app/api/tasks.py` — 加 `CompleteTaskRequest` BaseModel 接 body
  - 测试：`app/tests/test_api_complete_task.py`（新文件，4 个端点级 regression test 锁住）

## #7. `make setup` 引导歧义：以为装完就能访问（修于 2026-07-17）

- **症状**：用户跑完 `make setup`，直接打开 `http://localhost:3000` → "localhost 拒绝了我们的连接请求"。必须再跑 `make all` 才能访问
- **根因**：
  - `make setup` 的语义是**环境准备**（venv + pip + .env + npm install），**没有启动任何服务**
  - 但 `scripts/setup.sh` 末尾输出是"下一步：make dev / make web / make all" + "访问 http://localhost:3000"
  - 用户的第一反应是"环境准备好 = 装好了 = 能直接打开"，**没说清楚还要再跑一条启动命令**
  - "访问 localhost:3000" 出现在 setup 输出里，但端口上根本没服务在跑
- **修法**：
  - 加醒目警告："服务还没启动，需要再跑一条启动命令"
  - 把"一终端 `make all`"放第一位（多数新用户的最简路径）
  - "访问 localhost:3000" 挪到"启动后"标题下 — 语义上"启动 → 访问"的顺序才对
  - "下一步" 改成 "启动服务（任选其一）" — 强调这是个**必须执行**的步骤
- **教训**：
  - **环境准备类脚本的末尾输出要明确"服务状态"** — 准备完了 ≠ 启动了
  - 引导重心应该是"用户下一步必须做什么"，不是"哪个方便"
  - "访问 URL" 一定要跟"启动服务"绑在同一个上下文里出现，不能孤立
- **没改但同样有歧义**（待办）：
  - `Makefile` help target 文案"日常：'make dev'+'make web' / 嫌麻烦：'make all'" 也偏引导"哪个方便"，没强调"必须启动才能访问"
  - 想统一改的话，把 help 也对齐成"启动服务（任选其一）"的格式
- **修法位置**：`scripts/setup.sh` 末尾 echo 块（~25 行）

## #8. Python 3.11 + 隐式依赖 greenlet：后端起不来的双重坑（修于 2026-07-19）

- **症状**：`make all` 之后后端端口没监听，进程"在跑"但 curl 永远超时。手动前台跑 uvicorn 才发现有错
- **两个独立根因**（连着栽两次）：
  1. **`app/api/tasks.py` NameError** — `complete_task` 函数（line 65）参数类型 `CompleteTaskRequest`，但 class 定义在 line 95（函数之后）。Python 3.11 默认 PEP 526 行为，**函数注解立即求值**，import 阶段就爆
     - 720b67e 加 `CompleteTaskRequest` 时能跑，是因为 Python 3.12+ 默认 PEP 649 lazy 注解
     - 切到 3.11.7 立刻爆。**Python 3.11 没 `from __future__ import annotations` = 注解不 lazy**
  2. **`greenlet` 隐式依赖漏装** — SQLAlchemy 2.x async 强制需要 `greenlet`，但 `sqlalchemy` 包没把它列为硬依赖。`make setup` 走 `pip install -e .[dev]` 时漏装，lifespan 启动时报：
     ```
     File ".../sqlalchemy/util/concurrency.py", line 81, in _not_implemented
         raise ValueError("the greenlet library is required to use this function. No module named 'greenlet'")
     ```
     - 错误栈看起来很恐怖（FastAPI merged_lifespan 反复 await 同一失败操作，栈深度 6+ 层），但**根因就是底层这一个 ValueError**
- **修法**：
  1. `app/api/tasks.py` 顶部加 `from __future__ import annotations`，所有注解变 lazy 字符串
  2. `pyproject.toml` 显式声明 `"greenlet>=3.0"` 在 dependencies 里（与 sqlalchemy 并列）
- **教训**：
  - **Python 版本敏感度** — 3.11 vs 3.12 在注解语义上行为不同，跨版本时这种坑容易爆。**所有定义在文件下方的 Pydantic model 都建议加 `from __future__ import annotations`** 防一手
  - **"装上 sqlalchemy + aiosqlite ≠ 能跑 async"** — SQLAlchemy async 还有个隐藏的 greenlet 依赖。**显式声明 + 文档标注**比依赖 pip 隐式解析稳
  - **错误栈"看起来很复杂"≠ 根因复杂** — FastAPI/Starlette 嵌套 lifespan 会让单个 ValueError 栈深度翻 6 倍，**找最深一行的 `raise` 才是真因**
  - **`make setup` 跑完 ≠ 服务能起** — 装依赖 + 起服务是两件事，setup 引导文案修了（见 #7），但**依赖完整性也得靠 setup 测出来**——可以把 `uvicorn app.main:app --port 7842 &` + sleep 3 + curl 加进 setup.sh 末尾做 smoke test
- **可参考的运行时探针**：
  ```bash
  # 看 uvicorn 进程是否真在监听
  lsof -nP -iTCP:7842 -sTCP:LISTEN
  # CLOSED 状态 = 进程在但端口没绑 = 启动失败
  ```
- **修法位置**：`app/api/tasks.py:1`、`pyproject.toml:38`

## #10. `build_snapshot` 漏传 description 字段 → 前端永远看不到（修于 2026-07-21）

- **症状**：项目在数据库里有 description 字段，LLM 工具 `list_projects` 能正确返回（"description": "提升产品中的AI含量及token消耗量"），但**前端 MainBoard 项目卡片无论展开/收起都不显示任何 description 文字**。用户以为前端没做这个功能。
- **根因**（两个地方同时漏）：
  1. **`app/core/storage.py:927-928` `build_snapshot()` 构造 `ProjectSnapshot` 时显式 kwarg 传字段，漏了 description**：
     ```python
     projects_grouped.append(ProjectSnapshot(
         id=p.id, name=p.name, tasks=p_tasks   # ← 缺 description=p.description
     ))
     ```
     ORM `p.description` 是有的，但没塞进 snapshot 里。`/api/snapshot` 出去的 JSON 整链路就丢了。
  2. **`web/lib/api.ts` `ProjectSnapshot.description?: string` 是 optional** — 前端类型上没说必填，TS 不报错，运行时 `project.description` 是 `undefined`，`{project.description && <div>...}` 短路求值不渲染，**完全静默**
- **为什么测试没拦住**：
  - `test_build_snapshot_groups_by_project` 只验项目名/任务数，没验 description
  - 测的是另一条路径 `list_projects` 走的是 `projects.py` 接口（直接 dump ORM 全字段），所以测试看到 description 是有的
  - 同一份数据，两个接口行为不一致 —— 一个工具用 list_projects 看得到，dashboard 用 snapshot 看不到，用户对比之下更迷惑
- **修法**（3 个文件 + 1 测试）：
  1. `app/core/storage.py:928` 加 `description=p.description`
  2. `app/core/models.py:296` `ProjectSnapshot.description: str = ""`（必填 + 默认空串）
  3. `web/lib/api.ts:103` `description: string` 必填，TS 编译期就能发现使用方
  4. `app/tests/test_storage.py` 新增 `test_build_snapshot_includes_project_description`，直接断言 snapshot.projects[].description 等于建项目时传入的值
- **教训**：
  - **"Pydantic model + 显式 kwarg 构造" 是 silent failure 高发区** — 加新字段时如果忘了在调用点加 kwarg，model 默认值会兜住（这里 `description: str = ""` 兜成空串），数据静默丢失。**改用 `ProjectSnapshot.model_validate({**all_orm_fields})` 或者从 ORM 直接 dump** 能消除这种漏传
  - **"类型 optional = 允许 undefined"** = 前端另一道 silent failure。**字段在数据库有、在 LLM 工具返回里有，唯独 snapshot 里没有** —— 这种情况如果前端类型是 optional 就完全感知不到。**后端实际会送出的字段，前端类型就应该标必填**（即便兜底是空串）。optional 只给真正"可能没这个字段"的场景
  - **同一份数据两条对外路径必须做一致性测试** — `list_projects` 和 `build_snapshot` 都暴露 project 全量信息，但走的是不同代码路径。如果只测一条，另一条就完全没保护
  - **数据流可视化清单**很有用 — LLM 工具看到的有 / snapshot 看到的没有 / 前端展示 — 三层如果对不齐就一定有 bug
- **修法位置**：`app/core/storage.py:928`、`app/core/models.py:296`、`web/lib/api.ts:103`、`app/tests/test_storage.py::test_build_snapshot_includes_project_description`

## #9. `NEXT_PUBLIC_API_BASE` 没设 → 前端 fetch 静默打错端口（修于 2026-07-20）

- **症状**：用户 `make setup` + `make all` 之后访问 `http://localhost:3000`，控制台报
  `404: <!DOCTYPE html>...next-error-h1...`。**响应是 next dev 自己的 404 HTML 页面**，不是后端 JSON
- **三个独立根因叠加**（每个都不致命，合起来每个新用户必踩）：
  1. **`web/lib/api.ts` 默认值 `""` 太宽容** — `const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "";`
     - 空字符串 + `fetch(\`${API_BASE}${path}\`)` 相对路径 = 打 next dev 自己 :3000
     - 而 next 没有自己的 `/api/*` route（全部在后端 :7842），所以 next 返回 404 HTML
     - **没有警告、没有错误**——纯静默
  2. **`scripts/setup.sh` 没建 `web/.env.local`** — 后端有 `cp .env.example .env` 步骤，但前端**没有对应 `web/.env.example` 模板**，setup 流程也没创建
  3. **`api.ts` 错误信息没用** — `throw new Error(\`${res.status}: ${err}\`)` 把 next 的 100KB HTML 整个塞错误信息里，用户抓瞎
- **修法**（3 个文件）：
  1. 新建 `web/.env.example` — 列出 `NEXT_PUBLIC_API_BASE=http://127.0.0.1:7842` 默认值
  2. `scripts/setup.sh` 加 `[5/5]` 步骤 — 若 `web/.env.local` 不存在则从 `.env.example` 复制
  3. `web/lib/api.ts`:
     - 默认值 `""` → `"http://127.0.0.1:7842"`（宁可打错端口也不要静默 fallback 到相对路径）
     - `request()` 错误处理：检测响应是 HTML 时截短到 200 字符 + 加 hint "（响应是 HTML 不是 JSON —— 通常是 NEXT_PUBLIC_API_BASE 没指向后端...）"
- **教训**：
  - **"默认值兜底" 反模式** — API_BASE/DB_URL/API_KEY 这种**必须配**的变量，**别用 `||` 兜底成空字符串**。要么必填（启动时报清晰错误），要么给一个 dev 友好的默认值（"宁可打错端口也不要静默错"）
  - **错误信息检测内容类型** — `res.text()` 拿到 HTML 还是 JSON 是**重要诊断信号**。检测到 HTML 应该截短 + 提示"是不是打错端口了"，而不是整个塞错误信息
  - **"前端用相对路径" 的隐患** — `fetch("/api/x")` 在 next dev 里**不会自动代理到后端**，也不会报错。如果你想让前端代码"零配置"工作，要么配 `API_BASE` 默认值，要么在 next.config.js 里写 `rewrites()` 代理
- **修法位置**：`web/lib/api.ts:5`（默认值）、`web/lib/api.ts:15`（HTML 检测）、`web/.env.example`（新）、`scripts/setup.sh` `[5/5]` 步骤
