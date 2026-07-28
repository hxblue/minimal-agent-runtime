# AI 辅助开发与问题解决记录

## 使用原则

- AI 用于需求拆解、方案比较、代码起草、测试构造和问题排查。
- 关键范围、技术取舍与验收标准由候选人确认。
- 每个实现阶段必须通过命令或可观察行为验证，不把 AI 输出直接视为正确结果。
- 不向日志写入 API Key、私人数据或模型隐藏思维链。

## 需求与规格阶段

### 输入背景

根据笔试截图整理了以下硬性要求：自研 Agent Loop、真实 LLM、至少三个带参数
Schema 的工具、多 Session、Context 管理与基础压缩、异常处理、Trace、自动化测试、
README、录屏以及 AI Prompt/问题解决记录。

### AI 建议与人工决策

- 建议使用 Python、SQLite、FastAPI、Pydantic、HTTPX 与原生网页。
- 确认不使用 LangGraph、OpenHands、OpenClaw 等 Agent 框架。
- 确认三个工具为安全计算器、稳定 Mock Search 和 Session 级 Todo。
- 确认 Memory 采用 Session 摘要与消息水位，而不是向量数据库。
- 确认 Trace 记录结构化运行事件，不收集或伪造隐藏思维链。

### 形成的约束文档

- `spec.md`：行为需求与验收标准。
- `plan.md`：架构、接口、数据结构与技术决策。
- `task.md`：20 个有序实现任务及验证命令。
- `checklist.md`：74 个可观察验收检查项。

## 实现阶段日志

### T1–T4：骨架、契约、SQLite 与 Trace

- AI 起草了 Pydantic 领域模型、Protocol、SQLite 表结构和 Trace 脱敏策略。
- 人工确认 SQLite 适合无需外部数据库服务的笔试交付，并保留 Repository 抽象以便未来替换。
- 首次安装在网络沙箱中失败；在获得联网授权后正常安装 FastAPI、pytest-asyncio 与 Uvicorn。
- 首轮 Ruff 发现一处超长行和两处联合类型写法，修复后验证通过。
- 验证：11 个阶段测试通过，Ruff 与 mypy 通过。

### T5–T8：工具层

- AI 建议三个工具统一经过 Registry，而不是为演示 Prompt 硬编码调用路径。
- Calculator 最初采用 `operator` 映射，mypy 无法证明函数类型。人工选择改为显式 AST 运算分支，使允许的行为更容易审计和讲解。
- Todo 的 Session ID 只来自 ToolContext；Schema 额外字段禁止，避免模型越权指定作用域。
- 验证：24 个工具测试通过，Ruff 与 mypy 通过。

### T9–T11：LLM、Memory 与 Context

- 根据 Context7 当前文档使用 HTTPX 应用级 AsyncClient、独立超时与 MockTransport；
  使用 Pydantic v2 `model_json_schema` 和 `model_validate_json`。
- LLM Adapter 只实现 Chat Completions 协议，不承担 Agent 决策。
- Memory 使用 Session 摘要与 through_message_id 水位；LLM 摘要失败时确定性降级。
- 工具调用 assistant 消息与 tool result 作为同一对话轮原子保留。
- 验证：18 个阶段测试通过，Ruff 与 mypy 通过。

### T12–T13：Agent Runtime 与 Application

- 实现直接回答、一个或多个工具调用、结果回填、多轮继续、最大轮次与失败 Run。
- Application 为每个 Session 管理 asyncio.Lock，同 Session 串行、不同 Session 并发。
- 首轮静态检查发现 LLM Protocol 类型收窄与 Literal 状态问题，改用显式
  `resolved_llm` 后解决。
- 验证：13 个核心集成测试通过，Ruff 与 mypy 通过。

### T14–T16：API、CLI 与 Runtime Workbench

- FastAPI 使用 lifespan 管理 SQLite 与 HTTPX 生命周期；Web/CLI 共用 AgentApplication。
- 首版 TestClient 在当前 FastAPI/Starlette 中产生弃用警告，改为 HTTPX
  ASGITransport 并显式进入 lifespan，消除兼容警告。
- 前端设计采用 Session 台账、对话工作区和 Trace 飞行记录器三栏布局，唯一视觉重点为
  `INPUT → MODEL → TOOL → CONTINUE` 循环轨道。
- 使用本机 Edge 无头截图进行 1440×1000 视觉检查，布局、中文、工具列表和响应式边界正常。
- 验证：6 个入口层测试通过；完整离线回归 74 个测试通过；Ruff、mypy、compileall 通过。

### T17–T20：回归、边界修复与提交准备

- 最终回归发现低 Context 预算下，必要系统消息、Memory 和当前输入可能已经超过预算。
  人工决定在调用模型前显式拒绝该请求，避免把超预算 Context 发送给上游；API 返回 422，
  CLI 输出受控错误，同时保留压缩失败的确定性降级路径。
- 新增 Context 超预算单元测试和 API 超长输入集成测试；完整离线测试由 72 个增至 74 个。
- 执行禁止框架扫描与密钥模式扫描，`app/`、依赖清单和待提交材料中均未发现匹配项。
- 初始化本地 Git 仓库用于提交前文件检查；未创建提交，也未配置或上传远程仓库。
- 最终证据：`pytest -q -m "not live"` 为 74 passed；`ruff check .`、`mypy app`、
  `python -m compileall app` 均为退出码 0。

### T18：LongCat-2.0 真实端到端验证

- `.env` 被程序正确识别为 `LongCat-2.0` 与 `https://api.longcat.chat/openai/v1`；
  检查过程只输出配置状态、模型名和 Base URL，没有输出 API Key。
- 首次沙箱内运行因网络隔离快速进入受控失败；获得真实网络授权后，pytest 默认临时目录
  又触发 Windows 权限冲突。人工选择使用独立临时目录并关闭 pytest 缓存后重试，没有修改
  Runtime 逻辑或降低测试断言。
- 最终真实结果：普通回答、Calculator 工具闭环和 Todo 多轮工具闭环全部通过，
  `3 passed in 52.17s`。
- 该结果确认 LongCat-2.0 的实际端点能够处理本项目发送的 OpenAI-compatible
  `tools`、`tool_choice`、`tool_calls` 和 tool result 消息，尽管公开聊天接口页面未完整列出这些字段。

### 当前待验证事项

- 操作录屏已由候选人完成，正式提交前需要上传并填写面试官可访问的链接。
- 创建可供面试官访问的远程代码仓库链接。

### T21：提交材料整理

- 将 GitHub 首页 README、AI Prompt/问题解决记录、验收证据、上传指南和检查清单统一整理。
- 将当前已注册的确定性 Mock Weather 工具补充到 README，确保文档与代码一致。
- API 集成测试原先只断言三个工具；同步 Mock Weather 后更新为四工具预期，并重新完成
  `74 passed, 3 deselected`、Ruff、mypy（26 个源码文件）和 compileall 检查。
- 扩充 `.gitignore`，排除 IDE 配置、虚拟环境、API Key、SQLite 数据库和常见录屏文件。
- 保留真实 LLM 端到端测试的既有证据；提交准备阶段不重复消耗真实 API，也不读取或输出密钥。
