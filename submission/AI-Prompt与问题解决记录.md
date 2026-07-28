# AI Prompt 与问题解决记录

本文是正式提交版记录。Prompt 为开发过程中关键交互的内容摘要，不声称是逐字聊天导出；
所有 AI 建议均经过人工取舍，并以测试、静态检查或可观察行为验证。更完整的阶段日志见
[`../docs/ai-development-log.md`](../docs/ai-development-log.md)。

## 1. 需求拆解与范围控制

### Prompt 摘要

> 根据笔试要求设计一个 framework-free 的最小 Agent Runtime。必须接入真实 LLM，支持
> 结构化工具调用、多 Session、Context 管理、基础 Memory 压缩、异常处理、Trace、Web/CLI
> 入口和自动化测试。请先拆解需求、边界和验收标准，不直接依赖现成 Agent 框架。

### 采纳结果

- 使用 Python、FastAPI、Pydantic、HTTPX、SQLite 和原生网页。
- 明确核心 Agent Loop 自研，FastAPI 只作为入口层。
- 形成 `spec.md`、`plan.md`、`task.md` 和 `checklist.md`，将要求转成可验证条目。
- 不实现多 Agent、RAG、向量数据库和浏览器控制，避免超出笔试范围。

## 2. 分层架构与依赖方向

### Prompt 摘要

> 设计 Web、CLI、Application、Runtime、Protocol 和 Adapter 的边界，使核心 Runtime 不依赖
> FastAPI、SQLite 的具体实现或某一家 LLM SDK，并说明怎样通过依赖注入支持测试替身。

### 采纳结果

- `AgentApplication` 统一 Web/CLI 用例并提供 Session 级并发锁。
- `AgentRuntime` 只负责编排 Context、LLM、Tool、Repository 和 Trace。
- `LLMClient`、`SessionRepository`、`MemoryCompressor` 使用 Python `Protocol` 定义契约。
- `SQLiteRepository` 与 `OpenAICompatibleClient` 作为基础设施适配器注入核心层。

## 3. 工具注册与安全执行

### Prompt 摘要

> 设计统一 ToolRegistry：工具参数由 Pydantic 模型描述并导出 JSON Schema；模型返回的参数
> 必须在执行前严格校验；未知工具、参数错误和 Handler 异常应转换成可回填给模型的稳定结果。

### 采纳结果

- 工具统一通过 `ToolDefinition` 注册，禁止在 Prompt 中硬编码调用分支。
- 使用 `model_json_schema()` 向 LLM 暴露参数结构，使用
  `model_validate_json(..., strict=True)` 校验调用参数。
- Calculator 使用受限 AST，不使用 `eval`。
- Todo 的 Session ID 只来自 Runtime 注入的 `ToolContext`，避免模型越权指定作用域。
- 当前注册 Calculator、Mock Search、Todo 和确定性 Mock Weather 四个工具。

## 4. Agent Loop

### Prompt 摘要

> 实现一个支持直接回答、单个或多个工具调用、工具结果回填、多轮继续、参数自我修正、最大
> 轮数停止和失败 Run 的异步 Agent Loop，并保证 assistant tool_call 与 tool result 的关联正确。

### 采纳结果

- 每轮重新构建 Context，再调用 LLM。
- 模型返回 `tool_calls` 时，先保存 assistant 工具调用消息，再依次执行工具并保存 tool 消息。
- 工具失败被包装成 `ToolResult(ok=False)`，让模型有机会在下一轮修正参数。
- 模型没有工具调用时保存最终回答并结束 Run。
- `max_rounds` 防止无限工具循环。

## 5. Context 与 Memory 压缩

### Prompt 摘要

> 在不依赖向量数据库的前提下实现基础上下文压缩。保留最近完整对话轮，将较老消息与已有
> 摘要合并，记录压缩水位；说明压缩触发时机、存储位置、召回顺序和失败降级方式。

### 采纳结果

- `ContextManager` 估算系统提示、工具 Schema、消息和回复预留空间的总字符大小。
- 超过 `context_budget × compression_threshold` 时压缩较老轮次，保留最近
  `recent_turns` 轮原文。
- `LLMMemoryCompressor` 使用同一个 LLM 生成摘要，但设置 `allow_tools=False`。
- 摘要按 Session 写入 SQLite `session_memories` 表，并保存 `through_message_id` 水位。
- 下一次 Context 顺序为系统提示、历史摘要、水位之后的近期完整消息和当前输入。
- 摘要 LLM 失败时使用确定性的拼接与截断方案，并记录 `compression_fallback`。

## 6. Trace、错误处理与隐私

### Prompt 摘要

> 设计能够展示 Agent Loop 的结构化 Trace，但不得收集隐藏思维链或泄露 API Key。请覆盖
> LLM 超时、HTTP 错误、协议错误、工具错误、Context 超预算和最大轮数。

### 采纳结果

- Trace 记录 run、context、model、tool、compression 和完成/失败事件及耗时。
- Payload 递归过滤 authorization、api_key、token、cookie、password、secret 和 reasoning
  类字段，并限制字符串长度。
- 预期错误转换成稳定领域异常；失败 Run 留下 Trace，但不终止整个服务。
- `.env`、数据库、日志、虚拟环境、IDE 配置和录屏文件不进入 Git。

## 7. 自动化测试与真实 LLM 验证

### Prompt 摘要

> 为直接回答、工具闭环、多工具顺序、参数修正、最大轮数、Session 隔离、SQLite 恢复、
> Memory 压缩、Trace 脱敏、API、CLI 和真实 LLM 设计可重复测试；离线测试不得访问网络。

### 采纳结果

- 使用 `FakeLLMClient` 和 HTTPX `MockTransport` 隔离外部服务。
- 离线测试、Ruff、mypy 和 compileall 作为提交前固定检查。
- Live 测试必须显式设置 `RUN_LIVE_LLM_TESTS=1` 才运行。
- LongCat-2.0 真实测试验证直接回答、Calculator 和 Todo 多轮工具闭环，结果为
  `3 passed in 52.17s`。

## 8. 关键问题解决记录

| 问题 | 判断与处理 | 验证方式 |
| --- | --- | --- |
| Calculator 的 `operator` 映射让 mypy 无法证明函数签名 | 改为显式 AST 节点分支，使允许行为更容易审计 | 工具测试、Ruff、mypy |
| LLM Protocol 的联合类型无法稳定收窄 | 在 Bootstrap 中增加显式类型的 `resolved_llm` | mypy 通过 |
| FastAPI/Starlette `TestClient` 出现弃用警告 | 改用 HTTPX `ASGITransport` 并显式管理 lifespan | API 集成测试无弃用警告 |
| 低 Context 预算下必要消息仍可能超限 | 模型调用前再次检查预算并受控拒绝，不向上游发送超限请求 | Context 单元测试、API 422 测试 |
| LLM 摘要服务可能失败 | 增加确定性摘要降级，保留较新内容并写入 fallback Trace | Memory 压缩与失败路径测试 |
| Live 测试遇到网络隔离和 Windows 临时目录权限冲突 | 获得网络授权后使用独立临时目录并关闭 pytest 缓存，不降低断言 | 真实 LLM 测试 3 passed |

## 9. 人工责任边界

- AI 用于需求拆解、备选方案、代码草案、测试设计和问题定位。
- 架构范围、安全边界、工具行为和最终验收由候选人确认。
- 不把 AI 输出直接视为正确结论，所有关键路径都通过测试或人工演示验证。
- 不提交私人 Prompt、API Key、Authorization Header 或模型隐藏推理内容。
