# 最小可用 Agent Runtime 技术方案

## 1. 架构概览

项目采用“核心 Runtime + 基础设施适配器 + 多入口”的分层结构。Agent 主循环、工具调度、Session/Context/Memory 管理全部自行实现；FastAPI、Pydantic、HTTPX 等库只承担 Web、数据校验和 HTTP 通信等通用能力，不代理 Agent 决策。

```text
Browser UI ─┐
            ├─> Application Service ─> Agent Runtime ─> LLM Client
CLI ────────┘                           │      │
                                       │      └─> Tool Registry ─> Tools
                                       │
                                       ├─> Context Manager ─> Memory Compressor
                                       ├─> Session Repository
                                       └─> Trace Recorder

Persistent state: SQLite
LLM transport: OpenAI-compatible Chat Completions over HTTP
```

依赖方向保持单向：

```text
Web / CLI
   ↓
Application composition
   ↓
Agent Runtime
   ↓
Protocols + Context + Tools + Repository interfaces
   ↓
HTTPX LLM adapter + SQLite repositories
```

核心 Runtime 不导入 FastAPI，也不依赖网页状态，因此可以通过 CLI、测试或未来其他入口复用。

## 2. 技术栈

| 层级 | 选择 | 用途 |
| --- | --- | --- |
| 语言 | Python 3.11+ | 主实现语言，使用现代类型标注和异步 I/O |
| API | FastAPI | JSON API、静态网页托管、生命周期管理 |
| Schema | Pydantic v2 | API 数据、LLM 输出和工具参数的边界校验及 JSON Schema 生成 |
| LLM HTTP | HTTPX AsyncClient | OpenAI-compatible API 调用、超时和连接池 |
| 持久化 | SQLite（标准库驱动） | Session、Message、Memory、Todo、Run 和 Trace 持久化 |
| CLI | argparse + asyncio | 无额外 CLI 框架的交互入口 |
| Web | 原生 HTML/CSS/JavaScript | 无 Node 构建步骤的轻量演示界面 |
| 测试 | pytest + pytest-asyncio + HTTPX transport | 单元、集成和可选真实 LLM 测试 |
| 质量 | Ruff + mypy | 格式、静态检查和类型检查 |

## 3. 核心数据结构

以下签名描述模块契约，具体字段校验在实现阶段完成。

### 3.1 Message

```python
class Message(BaseModel):
    id: str
    session_id: str
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None
    tool_calls: list[ToolCall]
    tool_call_id: str | None
    created_at: datetime
```

`assistant` 消息可以携带一个或多个结构化工具调用；`tool` 消息必须通过 `tool_call_id` 与原调用关联。工具调用消息和对应结果在 Context 中作为不可拆分单元处理。

### 3.2 ToolDefinition 与 ToolCall

```python
ToolHandler = Callable[[BaseModel, ToolContext], Awaitable[ToolResult]]

class ToolDefinition:
    name: str
    description: str
    arguments_model: type[BaseModel]
    handler: ToolHandler

class ToolCall(BaseModel):
    id: str
    name: str
    arguments_json: str

class ToolContext(BaseModel):
    session_id: str
    run_id: str

class ToolResult(BaseModel):
    call_id: str
    tool_name: str
    ok: bool
    content: str
    error_type: str | None
```

`arguments_model.model_json_schema()` 生成提供给 LLM 的参数 Schema；LLM 返回的参数使用 `model_validate_json()` 校验。Handler 只能接收校验后的对象。

### 3.3 LLMMessage 与 LLMResponse

```python
class LLMToolSpec(TypedDict):
    name: str
    description: str
    parameters: dict[str, Any]

class LLMResponse(BaseModel):
    final_text: str | None
    tool_calls: list[ToolCall]
    finish_reason: str | None
    usage: TokenUsage | None

class LLMClient(Protocol):
    async def complete(
        self,
        messages: Sequence[Message],
        tools: Sequence[LLMToolSpec],
        *,
        allow_tools: bool = True,
    ) -> LLMResponse: ...
```

`LLMResponse` 必须满足“存在非空最终文本”或“存在至少一个工具调用”之一；两者均为空时视为协议错误。

### 3.4 Session、Memory 与 Todo

```python
class Session(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime

class SessionMemory(BaseModel):
    session_id: str
    summary: str
    through_message_id: str | None
    updated_at: datetime

class TodoItem(BaseModel):
    id: str
    session_id: str
    content: str
    completed: bool
    created_at: datetime
```

Memory 是对已压缩历史的 Session 级摘要，不是跨 Session 的用户画像。Todo 数据也严格绑定 Session。

### 3.5 Run 与 TraceEvent

```python
RunStatus = Literal["running", "completed", "max_rounds", "failed"]

class AgentRun(BaseModel):
    id: str
    session_id: str
    status: RunStatus
    rounds: int
    started_at: datetime
    finished_at: datetime | None
    error_type: str | None

class TraceEvent(BaseModel):
    id: str
    run_id: str
    session_id: str
    round: int | None
    event_type: str
    status: Literal["started", "succeeded", "failed", "info"]
    payload: dict[str, Any]
    duration_ms: int | None
    created_at: datetime
```

事件类型至少包括：`run_started`、`context_built`、`compression_started`、`compression_completed`、`model_started`、`model_completed`、`tool_started`、`tool_completed`、`round_completed`、`run_completed`、`max_rounds_reached` 和 `run_failed`。

### 3.6 RunResult

```python
class RunResult(BaseModel):
    run_id: str
    session_id: str
    status: RunStatus
    final_answer: str
    rounds: int
    events: list[TraceEvent]
```

Web 和 CLI 都消费同一 `RunResult`，避免在入口层重新解释 Runtime 状态。

## 4. 模块设计

### 4.1 Agent Runtime

**职责：** 执行自研 Agent Loop，控制轮次、协调 LLM、工具、Context、持久化与 Trace。

**公共接口：**

```python
class AgentRuntime:
    async def run(
        self,
        session_id: str,
        user_input: str,
        *,
        max_rounds: int | None = None,
    ) -> RunResult: ...
```

**循环算法：**

1. 校验 Session 和用户输入，创建 Run 并持久化用户消息。
2. 获取当前 Session 锁；不同 Session 可并发，同一 Session 的 Run 按顺序执行。
3. 通过 Context Manager 构建请求上下文，必要时先压缩历史。
4. 向 LLM 发送消息和工具 Schema。
5. 若返回最终文本，持久化回答并完成 Run。
6. 若返回工具调用，先持久化 assistant 工具调用消息，再逐个经 Tool Registry 校验并执行。
7. 把每个 ToolResult 作为 `tool` 消息持久化，重新构建上下文并进入下一轮。
8. 若达到最大轮次，生成明确的终止回答，保存 `max_rounds` 状态。
9. 无论成功失败均结束 Trace；异常转换为稳定错误结果，不使进程退出。

单个模型响应允许多个工具调用。MVP 中同一响应内的工具按顺序执行，保证 Trace 和持久化顺序确定，便于测试与讲解。

### 4.2 LLM Adapter

**职责：** 把内部消息和工具定义转换成 OpenAI-compatible Chat Completions 请求，通过 HTTPX 调用真实模型，再把供应商响应规范化为 `LLMResponse`。

**公共接口：** 实现 `LLMClient.complete()`。

**配置：**

- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL`
- `LLM_CONNECT_TIMEOUT_SECONDS`
- `LLM_READ_TIMEOUT_SECONDS`
- `LLM_TEMPERATURE`

客户端由应用生命周期统一创建和关闭，复用连接池。请求对 connect、read、write、pool 设置明确超时；HTTP 错误、超时、JSON 错误和响应协议错误转换为项目内部异常。

密钥只进入 Authorization Header，不写入 Trace。日志不保存完整原始响应，只保存状态、用量、finish reason 和必要的截断摘要。

### 4.3 Tool Registry 与 Executor

**职责：** 注册工具、检测重名、生成 LLM Tool Schema、验证 LLM 参数、执行 Handler 并规范化结果。

**公共接口：**

```python
class ToolRegistry:
    def register(self, definition: ToolDefinition) -> None: ...
    def list_specs(self) -> list[LLMToolSpec]: ...
    async def execute(self, call: ToolCall, context: ToolContext) -> ToolResult: ...
```

执行流程：

1. 按名称查找工具；未知名称返回可回填的 `unknown_tool` 结果。
2. 解析 JSON 参数；解析失败返回 `invalid_json`。
3. 使用工具的 Pydantic 模型严格校验；失败返回精简的 `validation_error`。
4. 执行 Handler，捕获异常并返回 `tool_execution_error`。
5. 对结果做长度限制和安全序列化，再回填 LLM。

工具失败通常不直接终止 Run，而是作为工具结果交给模型修正参数或向用户说明；只有 Runtime/存储等不可恢复错误才终止 Run。

### 4.4 三个内置工具

#### Calculator

```python
class CalculatorArgs(BaseModel):
    expression: str
```

使用受限语法树计算数字、括号和基础算术运算。禁止 `eval`，限制表达式长度、嵌套深度、指数大小和除零错误。

#### Mock Search

```python
class SearchArgs(BaseModel):
    query: str
    limit: int = 3
```

在项目内置小型数据集中按关键词匹配，输出标题、摘要和模拟 URL。结果稳定且不访问互联网，便于自动化测试和录屏复现。

#### Todo

```python
class TodoArgs(BaseModel):
    action: Literal["add", "list"]
    content: str | None = None
```

`add` 要求非空 content，`list` 忽略 content。Handler 从 `ToolContext.session_id` 获取作用域，只读写当前 Session 的 Todo。

### 4.5 Session Repository

**职责：** 管理 Session、消息、摘要记忆和 Todo 的持久化，提供事务边界。

**公共接口：**

```python
class SessionRepository(Protocol):
    async def create_session(self, title: str | None = None) -> Session: ...
    async def list_sessions(self) -> list[Session]: ...
    async def get_session(self, session_id: str) -> Session | None: ...
    async def append_message(self, message: Message) -> None: ...
    async def list_active_messages(self, session_id: str) -> list[Message]: ...
    async def get_memory(self, session_id: str) -> SessionMemory | None: ...
    async def save_memory(self, memory: SessionMemory) -> None: ...
    async def add_todo(self, session_id: str, content: str) -> TodoItem: ...
    async def list_todos(self, session_id: str) -> list[TodoItem]: ...
```

SQLite 使用以下表：

- `sessions`
- `messages`
- `session_memories`
- `todos`
- `agent_runs`
- `trace_events`

列表、JSON 对象等使用 JSON 文本存储。写入使用参数化 SQL 和显式事务。每次启动执行幂等建表；本题不引入完整迁移框架。

### 4.6 Context Manager 与 Memory Compressor

**职责：** 估算上下文使用量、选择进入模型的消息、触发压缩并召回 Session 摘要。

**公共接口：**

```python
class ContextManager:
    async def build(
        self,
        session_id: str,
        tool_specs: Sequence[LLMToolSpec],
    ) -> ContextWindow: ...

class MemoryCompressor(Protocol):
    async def compress(
        self,
        previous_summary: str | None,
        messages: Sequence[Message],
    ) -> str: ...
```

Context 顺序：

1. 系统指令。
2. 当前 Session 的 Memory 摘要（若存在，并明确标识为历史摘要而非用户新指令）。
3. 摘要水位之后的近期完整消息。
4. 当前用户输入始终保留在末尾。

选择规则：

- 工具调用 assistant 消息与相应 tool 结果必须成组保留或成组压缩。
- 至少保留最近若干完整对话轮次及当前输入。
- 工具 Schema、系统指令和预留回复空间计入预算。
- MVP 使用保守字符估算器并增加安全余量，不宣称供应商级精确 token 计数。
- 达到预算阈值时压缩较旧消息；压缩请求禁用工具，避免递归进入 Agent Loop。

摘要格式固定包含：重要用户事实、已完成决定、未完成事项、仍有用的工具结果。新摘要合并旧摘要并记录 `through_message_id`，后续只召回摘要水位之后的原始消息。

若 LLM 摘要请求失败，使用确定性的截断式降级摘要，保证 Context 仍受预算约束，并记录 `compression_fallback` Trace。

### 4.7 Trace Recorder

**职责：** 生成 Run 级事件、计算耗时、持久化并向 Web/CLI 返回安全事件视图。

**公共接口：**

```python
class TraceRecorder:
    async def emit(
        self,
        run_id: str,
        event_type: str,
        status: str,
        *,
        round: int | None = None,
        payload: Mapping[str, Any] | None = None,
        duration_ms: int | None = None,
    ) -> TraceEvent: ...

    async def list_events(self, run_id: str) -> list[TraceEvent]: ...
```

Trace Payload 使用字段白名单、长度上限和敏感键过滤。工具参数在满足题目可观察性前提下记录安全投影；`authorization`、`api_key`、`token`、Cookie 等字段统一替换为 `[REDACTED]`。不记录隐藏思维链。

### 4.8 Application Service 与并发控制

**职责：** 为 API/CLI 提供稳定用例，组合 Runtime 和 Repository，并管理每个 Session 的异步锁。

```python
class AgentApplication:
    async def create_session(self, title: str | None) -> Session: ...
    async def list_sessions(self) -> list[Session]: ...
    async def get_history(self, session_id: str) -> list[Message]: ...
    async def run_agent(self, session_id: str, text: str) -> RunResult: ...
    async def get_trace(self, run_id: str) -> list[TraceEvent]: ...
    def list_tools(self) -> list[LLMToolSpec]: ...
```

同一进程内每个 Session 一个 `asyncio.Lock`：同一 Session 请求串行化，不同 Session 可并发。MVP 固定单进程启动；跨进程分布式锁不在本题范围。

### 4.9 HTTP API

FastAPI 在生命周期中创建数据库、HTTPX 客户端、Registry、Runtime 和 Application Service，并在退出时关闭资源。

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| GET | `/api/health` | 检查服务、数据库和 LLM 配置状态，不发起计费调用 |
| POST | `/api/sessions` | 创建 Session |
| GET | `/api/sessions` | 获取 Session 列表 |
| GET | `/api/sessions/{session_id}/messages` | 获取对话历史 |
| POST | `/api/sessions/{session_id}/runs` | 提交用户输入并返回 RunResult |
| GET | `/api/runs/{run_id}/trace` | 获取一次运行的 Trace |
| GET | `/api/tools` | 查看已注册工具 Schema |
| GET | `/` | 返回演示网页 |

所有请求和响应使用 Pydantic 模型。Session 不存在返回 404；请求数据错误返回 422；LLM 外部服务不可用时 Run 返回受控失败信息并保留 Trace，而不是泄漏上游响应或密钥。

MVP 不使用流式协议。`POST /runs` 完成后一次返回最终答案和事件列表，网页即可按时间线展示工具事件；这样减少 SSE/WebSocket 对核心题目的干扰。

### 4.10 网页界面

页面包含：

- Session 列表、新建和切换按钮。
- 当前 Session 对话区。
- 输入框、发送按钮和运行中状态。
- 用户消息、Agent 最终回答、工具调用/结果三类视觉样式。
- 当前 Run 的可折叠 Trace 时间线。
- 配置缺失和运行失败的明确提示。

网页只通过 HTTP API 操作，不直接保存业务状态。刷新页面后从 API 恢复 Session 和消息。

### 4.11 CLI

启动方式为 `python -m app.cli`。CLI 支持普通聊天输入及以下控制命令：

- `/new [title]`
- `/sessions`
- `/use <session_id>`
- `/trace`
- `/tools`
- `/quit`

CLI 调用 `AgentApplication`，不通过 HTTP 回环，也不复制 Agent Loop。

## 5. 异常模型

内部异常按层级转换，不把第三方异常直接暴露给用户：

| 异常 | 来源 | 用户行为 | Trace |
| --- | --- | --- | --- |
| `ConfigurationError` | 缺少模型配置 | 启动/健康检查明确提示 | 记录缺失配置名，不记录值 |
| `SessionNotFoundError` | 无效 Session | API 404 / CLI 提示 | 记录 Session 标识 |
| `LLMTimeoutError` | LLM 超时 | Run 受控失败，可重试 | 记录阶段和耗时 |
| `LLMHTTPError` | 上游非成功状态 | Run 受控失败 | 记录状态码，不记录响应隐私内容 |
| `LLMProtocolError` | 输出无法规范化 | Run 受控失败 | 记录 finish reason 和错误类型 |
| `ToolNotFoundError` | 未知工具 | 结果回填模型 | `tool_completed: failed` |
| `ToolValidationError` | 参数无效 | 结果回填模型 | 记录精简字段错误 |
| `ToolExecutionError` | Handler 异常 | 结果回填模型 | 记录异常类型 |
| `MaxRoundsReached` | 达到轮次限制 | 返回明确终止回答 | `max_rounds_reached` |

## 6. 模块交互

### 6.1 普通回答

```text
UI/CLI -> Application -> Runtime
Runtime -> SessionRepo: append user message
Runtime -> ContextManager: build context
Runtime -> LLMClient: messages + tool schemas
LLMClient -> Runtime: final_text
Runtime -> SessionRepo: append assistant message
Runtime -> TraceRecorder: run_completed
Runtime -> UI/CLI: RunResult
```

### 6.2 工具调用

```text
LLMClient -> Runtime: ToolCall[]
Runtime -> SessionRepo: append assistant tool-call message
Runtime -> ToolRegistry: validate + execute
ToolRegistry -> Tool handler: validated args + ToolContext
Tool handler -> ToolRegistry: ToolResult
Runtime -> SessionRepo: append tool result message
Runtime -> ContextManager: rebuild context
Runtime -> LLMClient: continue next round
LLMClient -> Runtime: final_text or more ToolCall[]
```

### 6.3 Context 压缩

```text
ContextManager -> SessionRepo: history + current memory
ContextManager: estimate budget
ContextManager -> MemoryCompressor: old complete turns
MemoryCompressor -> LLMClient: summary request with tools disabled
ContextManager -> SessionRepo: save merged summary + watermark
ContextManager: system + summary + recent messages + current input
```

### 6.4 Session 隔离

所有 Repository 查询和 ToolContext 必须显式携带 `session_id`。Todo Handler 不能接受模型提供的 Session 标识，只能使用 Runtime 注入的 `ToolContext.session_id`，防止模型参数越权访问其他 Session。

## 7. 文件组织

```text
project/
  spec.md                         # 已批准的行为规格
  plan.md                         # 本技术方案
  task.md                         # 后续任务拆解
  checklist.md                    # 后续验收清单
  README.md                       # 运行、设计、Memory、测试和演示说明
  pyproject.toml                  # Python 依赖、测试和质量工具配置
  .env.example                    # 无密钥的环境变量模板
  .gitignore                      # 密钥、数据库、缓存和构建产物忽略规则
  app/
    __init__.py
    config.py                     # 环境配置及安全校验
    models.py                     # 跨模块共享数据模型
    protocols.py                  # LLM/Repository 等抽象接口
    runtime.py                    # 自研 Agent Loop
    context.py                    # Context 构建、预算和压缩
    memory.py                     # 摘要生成与降级策略
    tracing.py                    # Trace 生成、过滤和记录
    application.py                # 用例编排与 Session 锁
    bootstrap.py                  # 依赖组合与生命周期
    cli.py                        # 终端入口
    llm/
      __init__.py
      openai_compatible.py        # HTTPX LLM 适配器与响应解析
    tools/
      __init__.py
      base.py                     # ToolDefinition、Registry、Executor
      calculator.py               # 安全计算器
      mock_search.py              # 稳定模拟搜索
      todo.py                     # Session 级待办工具
    storage/
      __init__.py
      sqlite.py                   # SQLite 初始化和 Repository 实现
    api/
      __init__.py
      app.py                      # FastAPI 应用工厂与 lifespan
      schemas.py                  # HTTP 请求/响应模型
      routes.py                   # API 路由
    web/
      index.html                  # 演示页面
      styles.css                  # 页面样式
      app.js                      # Session、聊天和 Trace 交互
  tests/
    conftest.py                   # 临时数据库、FakeLLM、测试 Runtime
    fakes.py                      # 可脚本化 LLM 和故障注入
    unit/
      test_tool_registry.py
      test_calculator.py
      test_mock_search.py
      test_todo.py
      test_context.py
      test_memory.py
      test_llm_parser.py
      test_tracing.py
    integration/
      test_agent_loop.py
      test_sessions.py
      test_error_paths.py
      test_api.py
    e2e/
      test_live_llm.py            # 需显式开启的真实 LLM 测试
  docs/
    ai-development-log.md         # Prompt、AI 使用及问题解决记录
    demo-script.md                # 录屏步骤和预期结果
```

## 8. 测试设计

### 8.1 Fake LLM

测试使用可脚本化 `FakeLLMClient`，按调用顺序返回最终文本、工具调用或异常。它实现与真实适配器相同的 `LLMClient` 协议，使测试能验证 Runtime，而不依赖网络和随机模型行为。

### 8.2 单元测试

- Tool Registry：注册、重名、Schema、未知工具、无效 JSON、参数错误。
- Calculator：正常优先级、括号、非法节点、除零、超限表达式。
- Mock Search：稳定性、limit 边界和无匹配结果。
- Todo：add/list、空内容、Session 隔离。
- Context：消息选择、工具对原子性、预算、摘要水位和当前输入保留。
- Memory：摘要合并、压缩失败降级。
- LLM Parser：最终回答、一个/多个工具调用、空响应、畸形参数。
- Trace：事件顺序、耗时和敏感信息脱敏。

### 8.3 集成测试

- 直接回答闭环。
- 单工具和多轮工具闭环。
- 模型第一次传错参数、收到工具错误后自我修正。
- 两个 Session 的历史、Memory 和 Todo 隔离。
- 达到最大轮次后停止。
- LLM 超时、HTTP 错误、协议错误和工具异常后系统仍可继续处理请求。
- API 创建 Session、运行 Agent、获取历史与 Trace。

### 8.4 真实 LLM 测试

`e2e` 测试默认跳过，仅在设置 `RUN_LIVE_LLM_TESTS=1` 且配置真实密钥时运行。至少验证：

1. 一个无需工具的普通问答。
2. 一个必需调用计算器的问题。
3. 一个添加并查询 Todo 的多轮对话。

真实模型结果不按固定文案断言，而断言 Run 状态、工具事件和非空最终回答。

## 9. 需求覆盖映射

| 规格需求 | 方案落点 |
| --- | --- |
| F1 | Agent Runtime 循环算法 |
| F2 | OpenAI-compatible LLM Adapter、LLMResponse Parser |
| F3 | ToolDefinition、Tool Registry、Pydantic JSON Schema |
| F4 | Calculator、Mock Search、Todo |
| F5 | Tool Executor 参数校验与 ToolResult 回填 |
| F6 | SQLite Session Repository、Session 锁、显式 session_id |
| F7 | Message 持久化与 Context Manager |
| F8 | Runtime max_rounds 与 Context 预算 |
| F9 | Memory Compressor、摘要水位、降级摘要 |
| F10 | 内部异常模型与受控错误结果 |
| F11 | Run、TraceEvent、Trace Recorder 与脱敏 |
| F12 | FastAPI、原生 Web UI、CLI、Application Service |
| F13 | Fake LLM、单元/集成/可选 e2e 测试 |
| F14 | README、AI development log、demo script |

## 10. 技术决策

| 决策 | 选择 | 原因 |
| --- | --- | --- |
| Agent 框架 | 不使用 | 满足题目“核心 Runtime 自行实现”要求 |
| LLM 接入 | 自写 OpenAI-compatible HTTP 适配器 | 同时展示协议理解并兼容多家模型服务，避免 SDK 把核心行为藏起来 |
| API 模式 | 非流式 JSON | MVP 更稳定，Trace 可随 RunResult 一次返回，减少与核心题目无关的流式复杂度 |
| Schema/校验 | Pydantic v2 | 当前 API 提供 `model_json_schema` 与 `model_validate_json`，适合从同一模型生成工具 Schema 并校验不可信 LLM 参数 |
| HTTP 生命周期 | 应用级 HTTPX AsyncClient | 复用连接池并统一控制 connect/read/write/pool 超时；测试可替换 MockTransport |
| FastAPI 初始化 | lifespan | 当前推荐的共享资源创建/关闭方式，适合数据库与 HTTP 客户端生命周期 |
| 持久化 | SQLite | 无外部服务、可演示重启恢复、足够展示 Session 隔离和事务 |
| 数据访问 | 标准库 SQL + Repository | 项目表结构小，减少 ORM 噪音，面试时更容易讲清边界 |
| 前端 | 原生 HTML/CSS/JS | 无 Node 工具链，控制工作量，把重点留给 Runtime |
| Context 估算 | 保守字符估算 + 安全余量 | 兼容不同供应商；明确是基础压缩，不伪装成精确 tokenizer |
| Memory | Session 摘要 + 水位 | 直接回答题目要求的召回时机和放置方式，同时避免复杂向量记忆 |
| 工具执行 | 同轮顺序执行 | 事件顺序确定、数据库一致性简单；并行工具调用不属于 MVP 必需项 |
| 同 Session 并发 | 进程内按 Session 串行 | 防止历史交错；单进程演示足够，分布式锁明确不在范围 |
| 测试 LLM | Protocol + Fake 实现 | 自动化测试稳定、免费、无网络，同时保留真实 LLM e2e 证明 |
| Trace 内容 | 结构化事件而非思维链 | 满足可观察性，又不暴露密钥、私人内容或模型隐藏推理 |

## 11. 实施约束与风险控制

- 运行时固定单进程；README 明确不要使用多个 Web worker，共享锁和 SQLite 行为由此保持确定。
- OpenAI-compatible 服务必须支持结构化 tool calls；不实现基于自然语言正则猜测工具调用的脆弱降级。
- Context 压缩会产生额外 LLM 调用，Trace 和 README 应明确这一点，录屏使用较小预算主动展示一次即可。
- 工具结果和日志均设置长度上限，防止异常输出撑爆 Context 或页面。
- 真实模型具有非确定性；演示 Prompt 应清楚指向工具能力，自动化测试不得依赖模型措辞。
- 项目不提交真实数据库、`.env`、API Key、运行日志或录屏中的敏感信息。

