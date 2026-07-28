# 最小可用 Agent Runtime 任务清单

## 1. 文件清单

| 操作 | 文件 | 职责 |
| --- | --- | --- |
| 创建 | `pyproject.toml` | 依赖、包信息、pytest、Ruff 和 mypy 配置 |
| 创建 | `.env.example` | 无密钥的 LLM 与 Runtime 配置模板 |
| 创建 | `.gitignore` | 忽略密钥、数据库、缓存、日志和构建产物 |
| 创建 | `app/__init__.py` | 应用包及版本信息 |
| 创建 | `app/config.py` | 环境配置加载与边界校验 |
| 创建 | `app/errors.py` | 内部稳定异常类型 |
| 创建 | `app/models.py` | Message、Tool、Session、Run、Trace 等共享模型 |
| 创建 | `app/protocols.py` | LLM、Repository、Memory 等抽象契约 |
| 创建 | `app/runtime.py` | 自研 Agent Loop |
| 创建 | `app/context.py` | Context 预算、选择和构建 |
| 创建 | `app/memory.py` | LLM 摘要压缩和确定性降级策略 |
| 创建 | `app/tracing.py` | Trace 事件、脱敏和持久化协调 |
| 创建 | `app/application.py` | 用例编排和 Session 级并发控制 |
| 创建 | `app/bootstrap.py` | Repository、LLM、Tools 和 Runtime 依赖组合 |
| 创建 | `app/cli.py` | CLI 聊天及 Session/Trace 控制命令 |
| 创建 | `app/llm/__init__.py` | LLM 适配器包 |
| 创建 | `app/llm/openai_compatible.py` | HTTPX Chat Completions 调用和响应解析 |
| 创建 | `app/tools/__init__.py` | 内置工具注册入口 |
| 创建 | `app/tools/base.py` | ToolDefinition、ToolRegistry 和执行器 |
| 创建 | `app/tools/calculator.py` | 安全算术工具 |
| 创建 | `app/tools/mock_search.py` | 稳定模拟搜索工具 |
| 创建 | `app/tools/todo.py` | Session 级待办工具 |
| 创建 | `app/storage/__init__.py` | 存储适配器包 |
| 创建 | `app/storage/sqlite.py` | SQLite 表初始化及 Repository 实现 |
| 创建 | `app/api/__init__.py` | API 包 |
| 创建 | `app/api/app.py` | FastAPI 工厂、lifespan 和静态资源挂载 |
| 创建 | `app/api/schemas.py` | HTTP 请求与响应 Schema |
| 创建 | `app/api/routes.py` | Session、Run、Trace、Tools 和 Health 路由 |
| 创建 | `app/web/index.html` | 网页演示结构 |
| 创建 | `app/web/styles.css` | 聊天、工具事件和 Trace 样式 |
| 创建 | `app/web/app.js` | Session 切换、消息发送和 Trace 渲染 |
| 创建 | `tests/conftest.py` | 临时数据库、应用和公共测试夹具 |
| 创建 | `tests/fakes.py` | 可脚本化 Fake LLM 与故障注入 |
| 创建 | `tests/unit/test_models.py` | 核心模型和不变量测试 |
| 创建 | `tests/unit/test_tool_registry.py` | 工具注册、Schema、参数和错误测试 |
| 创建 | `tests/unit/test_calculator.py` | 计算器安全与边界测试 |
| 创建 | `tests/unit/test_mock_search.py` | 搜索稳定性和边界测试 |
| 创建 | `tests/unit/test_todo.py` | Todo 行为和 Session 作用域测试 |
| 创建 | `tests/unit/test_context.py` | Context 预算和消息选择测试 |
| 创建 | `tests/unit/test_memory.py` | 摘要合并和降级测试 |
| 创建 | `tests/unit/test_llm_parser.py` | 请求转换、响应解析和 HTTP 错误测试 |
| 创建 | `tests/unit/test_tracing.py` | Trace 顺序、字段和脱敏测试 |
| 创建 | `tests/integration/test_repository.py` | SQLite 持久化和事务测试 |
| 创建 | `tests/integration/test_agent_loop.py` | 直接回答、工具循环和最大轮次测试 |
| 创建 | `tests/integration/test_sessions.py` | 多 Session、追问、Memory 和并发隔离测试 |
| 创建 | `tests/integration/test_error_paths.py` | LLM、工具、压缩和恢复能力测试 |
| 创建 | `tests/integration/test_api.py` | HTTP API 用例和状态码测试 |
| 创建 | `tests/integration/test_cli.py` | CLI 控制命令和共享 Runtime 测试 |
| 创建 | `tests/integration/test_web.py` | 静态页面和 API 集成测试 |
| 创建 | `tests/e2e/test_live_llm.py` | 显式启用的真实 LLM 端到端测试 |
| 创建 | `README.md` | 运行、设计、Memory、测试和提交说明 |
| 创建 | `docs/ai-development-log.md` | AI Prompt、设计决策、问题与解决过程 |
| 创建 | `docs/demo-script.md` | 录屏脚本和演示检查点 |

## 2. 有序任务

### T1：建立项目骨架与安全配置

**文件：** `pyproject.toml`、`.env.example`、`.gitignore`、`app/__init__.py`、`app/config.py`、`docs/ai-development-log.md`

**依赖：** 无

**步骤：**

1. 声明 Python 3.11+、运行依赖和开发依赖，并配置 pytest、Ruff 与 mypy。
2. 实现从环境读取数据库路径、LLM 地址、模型、密钥、超时、最大轮次和 Context 预算的配置对象。
3. 区分“可启动但 LLM 未配置”和“执行真实 Run 必须配置 LLM”，使 Health 页面能给出明确状态。
4. 提供不包含真实凭据的 `.env.example`，忽略 `.env`、数据库、缓存、日志和测试产物。
5. 创建 AI 开发日志，记录目前的需求分析、spec/plan 决策和后续追加规则。

**验证：** 运行 `python -m pip install -e ".[dev]"`，期望安装成功；运行 `python -c "from app.config import Settings; print(Settings.from_env().database_path)"`，期望输出默认数据库路径且不泄漏密钥。

### T2：定义共享模型、协议与异常

**文件：** `app/models.py`、`app/protocols.py`、`app/errors.py`、`tests/fakes.py`、`tests/unit/test_models.py`

**依赖：** T1

**步骤：**

1. 按 `plan.md` 定义 Message、ToolCall、ToolResult、Session、SessionMemory、TodoItem、AgentRun、TraceEvent、LLMResponse 和 RunResult。
2. 为 LLM、Session Repository 和 Memory Compressor 定义 Protocol，保持 Runtime 与基础设施解耦。
3. 定义 Configuration、Session、LLM、Tool 和 MaxRounds 内部异常层级。
4. 实现可按顺序返回回答、工具调用或异常的 Fake LLM。
5. 测试模型不变量：角色与 tool_call 关联、LLMResponse 至少有回答或调用、状态枚举和字段边界。

**验证：** 运行 `pytest tests/unit/test_models.py -q`，期望全部通过；运行 `python -m compileall app`，期望无语法错误。

### T3：实现 SQLite 持久化 Repository

**文件：** `app/storage/__init__.py`、`app/storage/sqlite.py`、`tests/conftest.py`、`tests/integration/test_repository.py`

**依赖：** T2

**步骤：**

1. 幂等创建 sessions、messages、session_memories、todos、agent_runs 和 trace_events 表及必要索引。
2. 使用参数化 SQL 实现 Session、Message、Memory、Todo、Run 和 Trace 的增查改接口。
3. 对复合写操作使用显式事务，正确序列化和反序列化 JSON 字段。
4. 为测试创建独立临时数据库夹具，确保测试之间无状态泄漏。
5. 验证关闭并重新打开 Repository 后数据仍存在，以及 Session 过滤不会串数据。

**验证：** 运行 `pytest tests/integration/test_repository.py -q`，期望建表幂等、重启恢复、事务和 Session 过滤用例全部通过。

### T4：实现 Trace、计时与敏感信息脱敏

**文件：** `app/tracing.py`、`tests/unit/test_tracing.py`

**依赖：** T2、T3

**步骤：**

1. 实现 Run 级 TraceEvent 创建、持久化和时间顺序查询。
2. 支持计划中的事件类型、轮次、状态和 duration 字段。
3. 实现 Payload 白名单、递归敏感键脱敏和字符串长度限制。
4. 确保 API Key、Authorization、Token、Cookie 和隐藏推理内容不会进入事件。
5. 测试事件顺序、Run/Session 关联、耗时与嵌套字段脱敏。

**验证：** 运行 `pytest tests/unit/test_tracing.py -q`，期望事件与脱敏用例全部通过，并确认测试输出中不存在测试密钥原文。

### T5：实现工具注册与统一执行器

**文件：** `app/tools/__init__.py`、`app/tools/base.py`、`tests/unit/test_tool_registry.py`

**依赖：** T2

**步骤：**

1. 实现 ToolDefinition 和 ToolRegistry 的注册、重名保护及查询。
2. 使用参数模型生成 OpenAI-compatible Function Tool Schema。
3. 实现未知工具、无效 JSON、Schema 校验失败、Handler 异常和结果截断。
4. 确保 Handler 只接收校验后的参数和 Runtime 注入的 ToolContext。
5. 测试成功执行及所有失败路径产生稳定 ToolResult。

**验证：** 运行 `pytest tests/unit/test_tool_registry.py -q`，期望注册、Schema、校验、异常和截断测试全部通过。

### T6：实现安全计算器工具

**文件：** `app/tools/calculator.py`、`tests/unit/test_calculator.py`

**依赖：** T5

**步骤：**

1. 定义 CalculatorArgs 和工具描述。
2. 用受限 AST 支持数字、括号及 `+ - * / % **`，禁止名称、属性、调用和其他节点。
3. 限制表达式长度、AST 深度、指数和结果规模，处理除零。
4. 注册为标准 ToolDefinition，不加入问题关键词硬编码。

**验证：** 运行 `pytest tests/unit/test_calculator.py -q`，期望正常计算、优先级、恶意表达式、除零和资源上限测试全部通过。

### T7：实现稳定 Mock Search 工具

**文件：** `app/tools/mock_search.py`、`tests/unit/test_mock_search.py`

**依赖：** T5

**步骤：**

1. 定义 SearchArgs、limit 边界和清晰工具描述。
2. 建立与 Agent/公司笔试演示相关的小型固定语料集。
3. 实现大小写不敏感的确定性关键词评分、稳定排序和无匹配回退。
4. 返回结构一致的标题、摘要和模拟 URL，不发起外部网络请求。

**验证：** 运行 `pytest tests/unit/test_mock_search.py -q`，同一查询多次结果必须一致，limit、空查询和无匹配测试全部通过。

### T8：实现 Session 级 Todo 工具

**文件：** `app/tools/todo.py`、`tests/unit/test_todo.py`

**依赖：** T3、T5

**步骤：**

1. 定义 add/list 操作及条件参数校验。
2. 从 ToolContext 获取 session_id，模型参数不得指定或覆盖 Session。
3. 通过 Repository 添加和列出 Todo，并返回适合模型理解的结果。
4. 测试空内容、正常添加、列表顺序和两个 Session 隔离。

**验证：** 运行 `pytest tests/unit/test_todo.py -q`，期望 add/list、参数错误和 Session 隔离用例全部通过。

### T9：实现真实 LLM HTTP 适配器与解析器

**文件：** `app/llm/__init__.py`、`app/llm/openai_compatible.py`、`tests/unit/test_llm_parser.py`

**依赖：** T2

**步骤：**

1. 把内部 Message 和 Tool Schema 转换为 OpenAI-compatible Chat Completions 请求。
2. 使用应用级 HTTPX AsyncClient、独立超时和 Authorization Header 调用真实 API。
3. 解析普通回答、单个/多个 tool_calls、finish reason 和 usage。
4. 对空响应、畸形 JSON、HTTP 错误和超时抛出内部稳定异常。
5. 使用 HTTPX MockTransport 验证请求结构和响应解析，不执行真实网络请求。

**验证：** 运行 `pytest tests/unit/test_llm_parser.py -q`，期望普通回答、工具调用、多个调用、超时、HTTP 错误和协议错误测试全部通过。

### T10：实现 Memory 摘要与降级压缩

**文件：** `app/memory.py`、`tests/unit/test_memory.py`

**依赖：** T2、T3

**步骤：**

1. 实现禁用工具的摘要请求，固定输出重要事实、决定、未完成事项和工具结果。
2. 合并旧摘要与新压缩消息，生成新的摘要水位。
3. 实现 LLM 摘要失败时的确定性截断式降级策略。
4. 限制摘要长度并防止历史摘要被解释为用户新指令。
5. 测试首次摘要、增量摘要、水位更新、失败降级和 Session 绑定。

**验证：** 运行 `pytest tests/unit/test_memory.py -q`，期望摘要合并、降级、长度和 Session 作用域测试全部通过。

### T11：实现 Context 预算与消息选择

**文件：** `app/context.py`、`tests/unit/test_context.py`

**依赖：** T3、T10

**步骤：**

1. 实现保守字符预算估算，并计入系统指令、工具 Schema 和回复预留空间。
2. 按“系统指令—Session Memory—近期消息—当前输入”构建上下文。
3. 把 assistant tool_calls 与对应 tool 结果作为原子组选择。
4. 超过阈值时选择旧完整轮次压缩，并召回摘要水位后的消息。
5. 确保当前输入和最低近期轮次始终保留，最终 Context 不超过安全预算。

**验证：** 运行 `pytest tests/unit/test_context.py -q`，期望预算、顺序、工具原子组、压缩触发、当前输入保留和跨 Session 防泄漏测试全部通过。

### T12：实现自研 Agent Runtime 主循环

**文件：** `app/runtime.py`、`tests/integration/test_agent_loop.py`

**依赖：** T4、T6、T7、T8、T9、T11

**步骤：**

1. 实现 Run 创建、用户消息持久化、Context 构建和模型调用。
2. 处理普通最终回答，以及一个或多个工具调用的顺序执行和结果回填。
3. 每轮重建 Context，并持续循环到最终回答、不可恢复错误或最大轮次。
4. 在所有阶段发出计划中的 Trace，持久化 assistant/tool 消息和 Run 状态。
5. 工具可恢复错误回填模型；LLM/Repository 不可恢复错误转换为受控失败结果。
6. 使用 Fake LLM 测试直接回答、单工具、多工具、多轮修正和最大轮次。

**验证：** 运行 `pytest tests/integration/test_agent_loop.py -q`，期望基本 Loop、工具回填、多个工具、错误修正、Trace 顺序和最大轮次用例全部通过。

### T13：实现 Application Service、依赖组合与 Session 锁

**文件：** `app/application.py`、`app/bootstrap.py`、`tests/integration/test_sessions.py`、`tests/integration/test_error_paths.py`

**依赖：** T12

**步骤：**

1. 实现创建/列出 Session、读取历史、运行 Agent、读取 Trace 和列出工具用例。
2. 为每个 Session 管理独立 asyncio.Lock；相同 Session 串行，不同 Session 可并发。
3. 在 bootstrap 中注册三个工具并组合 Repository、Trace、Context、LLM 和 Runtime。
4. 统一处理配置缺失、Session 不存在、LLM 失败和服务恢复。
5. 测试对话、Memory、Todo、并发和异常在两个 Session 间不串扰。

**验证：** 运行 `pytest tests/integration/test_sessions.py tests/integration/test_error_paths.py -q`，期望 Session 隔离、连续追问、并发顺序、Memory 召回及故障恢复测试全部通过。

### T14：实现 FastAPI HTTP API

**文件：** `app/api/__init__.py`、`app/api/app.py`、`app/api/schemas.py`、`app/api/routes.py`、`tests/integration/test_api.py`

**依赖：** T13

**步骤：**

1. 使用 lifespan 创建和关闭 SQLite、HTTPX Client 与 AgentApplication。
2. 实现 Health、Session、Messages、Run、Trace 和 Tools 路由。
3. 使用 Pydantic 请求/响应模型和稳定 HTTP 状态码。
4. 确保 LLM 受控失败作为 Run 结果返回，Session 不存在返回 404，非法请求返回 422。
5. 使用测试应用、临时数据库和 Fake LLM 覆盖所有 API。

**验证：** 运行 `pytest tests/integration/test_api.py -q`，期望所有端点、响应 Schema、状态码和错误脱敏测试通过；运行 `python -c "from app.api.app import create_app; print(create_app().title)"`，期望成功创建应用。

### T15：实现 CLI 入口

**文件：** `app/cli.py`、`tests/integration/test_cli.py`

**依赖：** T13

**步骤：**

1. 实现交互式聊天以及 `/new`、`/sessions`、`/use`、`/trace`、`/tools`、`/quit`。
2. CLI 直接调用 AgentApplication，禁止复制 Runtime 或通过 HTTP 回环。
3. 清晰输出 Session、最终回答、工具事件、Trace 和受控错误。
4. 通过注入输入输出流实现可重复的命令测试。

**验证：** 运行 `pytest tests/integration/test_cli.py -q`，期望控制命令和聊天流程通过；运行 `python -m app.cli --help`，期望显示启动参数且不要求真实调用 LLM。

### T16：实现网页聊天与 Trace 界面

**文件：** `app/web/index.html`、`app/web/styles.css`、`app/web/app.js`、`tests/integration/test_web.py`、`app/api/app.py`

**依赖：** T14

**步骤：**

1. 实现 Session 列表、新建/切换、历史恢复、输入和加载状态。
2. 调用 API 提交 Run，并区分渲染用户消息、最终回答和工具事件。
3. 实现可折叠 Trace 时间线、配置缺失、网络错误和受控失败提示。
4. 禁止在前端保存 API Key 或承载 Agent 决策逻辑。
5. 由 FastAPI 托管静态资源，确保 `/api/*` 路由优先且 `/` 可加载。

**验证：** 运行 `pytest tests/integration/test_web.py -q`，期望首页、静态资源和 API 路由测试通过；启动 `uvicorn app.api.app:create_app --factory` 后在浏览器完成创建 Session 和一次 Fake/真实配置下的交互检查。

### T17：执行完整离线回归与质量检查

**文件：** 所有 `app/` 和 `tests/` 文件、`pyproject.toml`

**依赖：** T15、T16

**步骤：**

1. 运行全部非 live 测试，修复顺序依赖、状态泄漏和不稳定断言。
2. 运行 Ruff 和 mypy，修复格式、未使用代码和类型问题。
3. 检查核心 Runtime 不导入 FastAPI，也未引入任何 Agent 框架。
4. 扫描仓库中的密钥模式、数据库和日志误提交。
5. 将重要修复过程追加到 AI 开发日志。

**验证：** 运行 `ruff check .`、`mypy app`、`pytest -q -m "not live"` 和 `python -m compileall app`，期望全部成功；运行 `rg "langgraph|openhands|openclaw|sk-[A-Za-z0-9]" -i .`，期望除规格说明中的框架禁用文字外没有实现依赖或真实密钥。

### T18：执行真实 LLM 端到端验证

**文件：** `tests/e2e/test_live_llm.py`、`docs/ai-development-log.md`

**依赖：** T17

**步骤：**

1. 实现默认跳过、显式开关控制的 live 测试。
2. 使用真实 OpenAI-compatible 模型验证普通回答、计算器调用和 Todo 多轮对话。
3. 断言 Run 状态、工具事件和非空最终回答，不依赖固定措辞。
4. 若真实服务存在兼容差异，修正适配器并记录实际请求/响应差异，但不记录密钥和私人内容。
5. 验证完成后立即检查日志、测试输出和仓库中没有凭据。

**验证：** 在安全配置真实凭据后运行 `$env:RUN_LIVE_LLM_TESTS='1'; pytest tests/e2e/test_live_llm.py -q -m live`，期望三个真实模型场景通过并产生正确工具 Trace。

### T19：完成 README、AI 记录与录屏脚本

**文件：** `README.md`、`docs/ai-development-log.md`、`docs/demo-script.md`、`.env.example`

**依赖：** T17

**步骤：**

1. README 写明安装、配置、Web/CLI 启动、测试、单进程限制和故障排查。
2. 用图和文字说明自研 Agent Loop、工具 Schema、Session/Context/Trace 设计。
3. 专门说明 Memory 的压缩触发时机、召回时机、Context 放置位置和 Session 水位。
4. 整理 AI Prompt 与问题解决记录，区分 AI 建议、人工决策和验证证据。
5. 编写录屏脚本，依次展示启动、工具列表、普通回答、三种工具、追问、双 Session 隔离、压缩、Trace 和受控异常。

**验证：** 按 README 在新的虚拟环境执行安装、测试、Web 与 CLI 启动步骤；逐项走读 `docs/demo-script.md`，每个场景都应有明确输入、预期界面和证据位置。

### T20：最终验收准备与提交前清理

**文件：** 全项目；必要时更新 `README.md`、`docs/ai-development-log.md`、`docs/demo-script.md`

**依赖：** T18、T19

**步骤：**

1. 按 `checklist.md` 执行全部可观察验收项并记录证据。
2. 使用真实模型按录屏脚本完整走一遍，修复只在真实交互中出现的问题。
3. 重新运行离线测试、live 测试、Ruff、mypy 和密钥扫描。
4. 检查仓库只包含源代码和必要文档，不包含 `.env`、SQLite 数据库、缓存、日志或录屏中的密钥。
5. 完成正式录屏，确认代码仓库链接可访问，并核对题目要求的所有提交材料。

**验证：** `ruff check .`、`mypy app`、`pytest -q -m "not live"` 和显式 live 测试全部通过；`git status --short` 仅显示预期源代码/文档；从 README 的空环境步骤可复现网页和 CLI 演示。

## 3. 执行顺序

```text
T1 -> T2 -> T3 -> T4
          ├────> T5 -> T6 ─┐
          │          T7 ───┤
          │          T8 ───┤
          └────> T9        │
                 T10 -> T11┤
                            ↓
                           T12 -> T13 -> T14 -> T16 ─┐
                                      └────> T15 ────┤
                                                     ↓
                                                    T17 -> T18 ─┐
                                                       └-> T19 ─┤
                                                                 ↓
                                                                T20
```

更精确的依赖集合：

```text
T1
T2(T1)
T3(T2)
T4(T2,T3)
T5(T2)
T6(T5)
T7(T5)
T8(T3,T5)
T9(T2)
T10(T2,T3)
T11(T3,T10)
T12(T4,T6,T7,T8,T9,T11)
T13(T12)
T14(T13)
T15(T13)
T16(T14)
T17(T15,T16)
T18(T17)
T19(T17)
T20(T18,T19)
```

