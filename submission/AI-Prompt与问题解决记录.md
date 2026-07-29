# AI Prompt 与问题解决记录

本文是正式提交版记录。Prompt 为开发过程中关键交互的内容摘要，不声称是逐字聊天导出；
所有 AI 建议均经过人工取舍，并以测试、静态检查或可观察行为验证。更完整的阶段日志见
[`../docs/ai-development-log.md`](../docs/ai-development-log.md)。

## 1. 开发范式：Spec 驱动的 Vibe Coding

本项目采用 **Spec-driven Vibe Coding（规格驱动的 AI 协作开发）**。这里的 Vibe Coding
不是“用一句自然语言让 AI 一次性生成整个项目”，而是由候选人确定目标、边界和验收标准，
AI 参与需求拆解、方案比较、代码草案、测试设计和问题排查；每次实现都必须受到已确认的
Spec 约束，并通过自动化测试或可观察行为验收。

### 工作流主 Prompt 摘要

> 采用 Spec 驱动方式完成本项目。先根据原始笔试要求整理 `spec.md`，明确功能需求、非功能
> 需求、不在范围内的内容和验收标准；规格确认后再生成 `plan.md`，说明架构、模块接口、
> 数据结构、交互流程、测试设计和风险；随后将方案拆成 `task.md` 中可独立验证的有序任务，
> 并用 `checklist.md` 建立最终验收映射。实现阶段每次只处理当前任务，不得绕过 Spec 扩张
> 范围；完成后运行对应测试，失败则定位原因并修正实现，不通过删除断言或降低标准伪造成功。

### 五阶段约束链

```text
原始笔试要求
    ↓
spec.md：定义“做什么、为什么做、做到什么程度”
    ↓
plan.md：定义“采用什么架构和技术方案实现”
    ↓
task.md：定义“按什么顺序完成哪些可验证任务”
    ↓
实现 → 测试 → 问题修复 → 回归
    ↓
checklist.md：逐项确认是否满足 Spec 和提交要求
```

四份核心文档的职责如下：

| 文档 | 本项目中的作用 | 防止的问题 |
| --- | --- | --- |
| `spec.md` | 固化 F1–F14 功能需求、非功能要求、范围边界和验收标准 | AI 自行扩张范围或遗漏硬性要求 |
| `plan.md` | 固化分层架构、数据模型、模块交互、异常模型、测试策略和需求覆盖映射 | 边写边改导致架构失控 |
| `task.md` | 将方案拆成 T1–T20 有依赖顺序且带验证方式的实现任务 | 一次生成大量代码、难以定位问题 |
| `checklist.md` | 从环境、功能、集成、异常、安全、测试到提交材料逐项验收 | 代码能运行但不能证明满足笔试要求 |

### 单个任务的 Vibe Coding 闭环

每个任务都遵循同一循环：

1. AI 读取当前 Spec、Plan 和任务边界，先说明准备修改的模块和验收方式。
2. 候选人确认关键技术取舍，AI 再生成或修改最小范围代码。
3. 运行单元测试、集成测试、Ruff、mypy 或端到端场景，收集实际结果。
4. 若失败，依据错误信息回到实现定位根因，不通过跳过测试或放宽断言掩盖问题。
5. 当前任务验证通过后再进入下一任务，最终由 Checklist 和完整回归统一验收。

因此，本项目虽然充分使用自然语言与 AI 加速开发，但最终实现不是由聊天“感觉正确”来
决定，而是由 Spec、任务边界、测试结果和验收清单共同决定。这是本项目中
“Spec-driven”与普通无约束 Vibe Coding 的核心区别。

## 2. 需求拆解与范围控制

### Prompt 摘要

> 根据笔试要求设计一个 framework-free 的最小 Agent Runtime。必须接入真实 LLM，支持
> 结构化工具调用、多 Session、Context 管理、基础 Memory 压缩、异常处理、Trace、Web/CLI
> 入口和自动化测试。先输出可确认的 `spec.md`，拆解需求、边界和验收标准；规格确认前不要
> 直接实现代码，也不依赖现成 Agent 框架替代核心循环。

### 采纳结果

- 使用 Python、FastAPI、Pydantic、HTTPX、SQLite 和原生网页。
- 明确核心 Agent Loop 自研，FastAPI 只作为入口层。
- 形成 `spec.md`、`plan.md`、`task.md` 和 `checklist.md`，将要求转成可验证条目。
- 不实现多 Agent、RAG、向量数据库和浏览器控制，避免超出笔试范围。
- 后续架构和代码 Prompt 均引用这些约束文档，而不是脱离上下文重新生成方案。

## 3. 分层架构与依赖方向

### Prompt 摘要

> 设计 Web、CLI、Application、Runtime、Protocol 和 Adapter 的边界，使核心 Runtime 不依赖
> FastAPI、SQLite 的具体实现或某一家 LLM SDK，并说明怎样通过依赖注入支持测试替身。

### 采纳结果

- `AgentApplication` 统一 Web/CLI 用例并提供 Session 级并发锁。
- `AgentRuntime` 只负责编排 Context、LLM、Tool、Repository 和 Trace。
- `LLMClient`、`SessionRepository`、`MemoryCompressor` 使用 Python `Protocol` 定义契约。
- `SQLiteRepository` 与 `OpenAICompatibleClient` 作为基础设施适配器注入核心层。

## 4. 工具注册与安全执行

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

## 5. Agent Loop

### Prompt 摘要

> 实现一个支持直接回答、单个或多个工具调用、工具结果回填、多轮继续、参数自我修正、最大
> 轮数停止和失败 Run 的异步 Agent Loop，并保证 assistant tool_call 与 tool result 的关联正确。

### 采纳结果

- 每轮重新构建 Context，再调用 LLM。
- 模型返回 `tool_calls` 时，先保存 assistant 工具调用消息，再依次执行工具并保存 tool 消息。
- 工具失败被包装成 `ToolResult(ok=False)`，让模型有机会在下一轮修正参数。
- 模型没有工具调用时保存最终回答并结束 Run。
- `max_rounds` 防止无限工具循环。

## 6. Context 与 Memory 压缩

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

## 7. Trace、错误处理与隐私

### Prompt 摘要

> 设计能够展示 Agent Loop 的结构化 Trace，但不得收集隐藏思维链或泄露 API Key。请覆盖
> LLM 超时、HTTP 错误、协议错误、工具错误、Context 超预算和最大轮数。

### 采纳结果

- Trace 记录 run、context、model、tool、compression 和完成/失败事件及耗时。
- Payload 递归过滤 authorization、api_key、token、cookie、password、secret 和 reasoning
  类字段，并限制字符串长度。
- 预期错误转换成稳定领域异常；失败 Run 留下 Trace，但不终止整个服务。
- `.env`、数据库、日志、虚拟环境、IDE 配置和录屏文件不进入 Git。

## 8. 自动化测试与真实 LLM 验证

### Prompt 摘要

> 为直接回答、工具闭环、多工具顺序、参数修正、最大轮数、Session 隔离、SQLite 恢复、
> Memory 压缩、Trace 脱敏、API、CLI 和真实 LLM 设计可重复测试；离线测试不得访问网络。

### 采纳结果

- 使用 `FakeLLMClient` 和 HTTPX `MockTransport` 隔离外部服务。
- 离线测试、Ruff、mypy 和 compileall 作为提交前固定检查。
- Live 测试必须显式设置 `RUN_LIVE_LLM_TESTS=1` 才运行。
- LongCat-2.0 真实测试验证直接回答、Calculator 和 Todo 多轮工具闭环，结果为
  `3 passed in 52.17s`。

## 9. 关键问题解决记录

| 问题 | 判断与处理 | 验证方式 |
| --- | --- | --- |
| Calculator 的 `operator` 映射让 mypy 无法证明函数签名 | 改为显式 AST 节点分支，使允许行为更容易审计 | 工具测试、Ruff、mypy |
| LLM Protocol 的联合类型无法稳定收窄 | 在 Bootstrap 中增加显式类型的 `resolved_llm` | mypy 通过 |
| FastAPI/Starlette `TestClient` 出现弃用警告 | 改用 HTTPX `ASGITransport` 并显式管理 lifespan | API 集成测试无弃用警告 |
| 低 Context 预算下必要消息仍可能超限 | 模型调用前再次检查预算并受控拒绝，不向上游发送超限请求 | Context 单元测试、API 422 测试 |
| LLM 摘要服务可能失败 | 增加确定性摘要降级，保留较新内容并写入 fallback Trace | Memory 压缩与失败路径测试 |
| Live 测试遇到网络隔离和 Windows 临时目录权限冲突 | 获得网络授权后使用独立临时目录并关闭 pytest 缓存，不降低断言 | 真实 LLM 测试 3 passed |

这些问题的处理同样遵循 Spec 闭环：先判断失败影响哪项需求或验收标准，再修改最小必要
实现并执行相应测试，最后运行完整回归；没有为了让结果“变绿”而删除功能、跳过关键测试
或改变既定验收口径。

## 10. 人工责任边界

- AI 用于需求拆解、备选方案、代码草案、测试设计和问题定位。
- 架构范围、安全边界、工具行为和最终验收由候选人确认。
- `spec.md`、`plan.md`、`task.md` 和 `checklist.md` 是 AI 协作的约束输入，不是完成开发后
  为包装结果而补写的说明材料。
- 不把 AI 输出直接视为正确结论，所有关键路径都通过测试或人工演示验证。
- 不提交私人 Prompt、API Key、Authorization Header 或模型隐藏推理内容。
