# 最小可用 Agent Runtime 验收清单

> 所有项目必须通过运行命令或观察实际行为验证。不得仅凭代码存在或主观判断勾选。真实 LLM 项目需要使用支持结构化 tool calls 的有效 OpenAI-compatible API 配置。

## 1. 环境与启动

- [ ] **ENV-01 新环境安装成功。**（验证：在新的 Python 3.11+ 虚拟环境运行 `python -m pip install -e ".[dev]"`，期望无依赖冲突并成功安装项目。）
- [ ] **ENV-02 无密钥也能检查应用状态。**（验证：不设置 `LLM_API_KEY` 启动应用并访问 `/api/health`，期望服务正常响应且明确显示 LLM 未配置，不泄漏环境变量内容。）
- [ ] **ENV-03 配置真实 LLM 后服务就绪。**（验证：通过环境变量提供 Base URL、Model 和 Key，访问 `/api/health`，期望显示 LLM 已配置，但响应中不出现 Key。）
- [ ] **ENV-04 数据库自动初始化。**（验证：删除测试用临时数据库后启动一次应用，期望自动生成 SQLite 文件并能创建 Session，无需手工执行 SQL。）
- [ ] **ENV-05 Web 与 CLI 均可启动。**（验证：运行 `uvicorn app.api.app:create_app --factory` 后首页可打开；另开终端运行 `python -m app.cli --help`，期望显示 CLI 帮助。）

## 2. 实现完整性

- [ ] **IMP-01 自研 Agent Loop 可独立运行。**（验证：运行 `pytest tests/integration/test_agent_loop.py -q`，期望直接回答、工具回填、继续循环和最大轮次用例全部通过。）
- [ ] **IMP-02 未使用禁止的 Agent 框架。**（验证：检查依赖清单和 `rg "langgraph|openhands|openclaw" -i app pyproject.toml`，期望没有匹配项。）
- [ ] **IMP-03 LLM 响应能区分回答与工具调用。**（验证：运行 `pytest tests/unit/test_llm_parser.py -q`，期望普通文本、单工具、多工具、空响应和畸形响应场景全部通过。）
- [ ] **IMP-04 工具注册信息完整。**（验证：访问 `GET /api/tools`，期望至少返回 calculator、search、todo；每个条目均包含名称、描述和非空参数 Schema。）
- [ ] **IMP-05 工具参数在执行前校验。**（验证：运行 `pytest tests/unit/test_tool_registry.py -q`，期望未知工具、无效 JSON、字段缺失、字段类型错误均产生受控 ToolResult，Handler 不被错误调用。）
- [ ] **IMP-06 Calculator 安全可用。**（验证：运行 `pytest tests/unit/test_calculator.py -q`，期望正常算术通过，名称访问、函数调用、属性访问、除零和超限表达式被拒绝。）
- [ ] **IMP-07 Mock Search 稳定可复现。**（验证：运行 `pytest tests/unit/test_mock_search.py -q`，期望相同查询多次结果一致，limit 和空查询边界受控，测试期间无外部网络请求。）
- [ ] **IMP-08 Todo 支持添加和查看。**（验证：运行 `pytest tests/unit/test_todo.py -q`，期望 add/list、空内容拒绝和 Session 隔离用例全部通过。）
- [ ] **IMP-09 Session 历史持久化。**（验证：运行 `pytest tests/integration/test_repository.py -q`，期望关闭并重新打开 Repository 后 Session、Message、Memory、Todo、Run 和 Trace 仍可读取。）
- [ ] **IMP-10 Context 预算有效。**（验证：运行 `pytest tests/unit/test_context.py -q`，期望系统指令、工具 Schema、回复空间和消息均计入预算，构建结果不超过安全上限。）
- [ ] **IMP-11 Memory 压缩与召回有效。**（验证：运行 `pytest tests/unit/test_memory.py tests/unit/test_context.py -q`，期望产生摘要与水位，后续 Context 包含摘要和水位后的近期消息。）
- [ ] **IMP-12 Trace 信息完整且有序。**（验证：运行 `pytest tests/unit/test_tracing.py -q`，并查询一次含工具调用 Run 的 Trace，期望包含 run/session 标识、轮次、模型和工具状态、耗时及结束事件。）
- [ ] **IMP-13 网页区分三类内容。**（验证：在网页完成一次工具调用，期望用户消息、Agent 最终回答、工具调用/结果使用不同视觉样式，Trace 可展开查看。）
- [ ] **IMP-14 CLI 支持全部控制命令。**（验证：运行 `pytest tests/integration/test_cli.py -q`，期望 `/new`、`/sessions`、`/use`、`/trace`、`/tools` 和 `/quit` 均按预期工作。）

## 3. 模块集成

- [ ] **INT-01 普通回答不误调用工具。**（验证：Fake LLM 返回 final_text 时运行一次 Agent，期望只有一轮模型调用、无 `tool_started` 事件并持久化最终回答。）
- [ ] **INT-02 完成工具闭环。**（验证：Fake LLM 先返回 calculator 调用、再返回最终回答，期望消息顺序为 user → assistant tool_call → tool result → assistant final，Trace 顺序一致。）
- [ ] **INT-03 支持同轮多个工具。**（验证：Fake LLM 在一次响应中返回两个工具调用，期望两个调用按顺序执行、结果分别关联正确 call_id，并在下一轮一并提供给模型。）
- [ ] **INT-04 工具错误可由模型修正。**（验证：Fake LLM 第一次给出无效参数、第二次给出有效参数，期望首个错误回填 Context，第二次执行成功，Run 最终完成。）
- [ ] **INT-05 Session 历史相互隔离。**（验证：运行 `pytest tests/integration/test_sessions.py -q`，创建 Session A/B 并写入不同消息，期望任何按 Session 查询均不返回另一 Session 内容。）
- [ ] **INT-06 Todo 与 Memory 相互隔离。**（验证：在 Session A 添加 Todo 并触发摘要，在 Session B 分别 list Todo 和构建 Context，期望看不到 A 的 Todo 与摘要。）
- [ ] **INT-07 连续对话能够追问。**（验证：在同一 Session 先提供一个姓名或偏好，再追问该信息，期望第二次模型请求包含所需历史且回答正确。）
- [ ] **INT-08 带工具结果的追问有效。**（验证：先执行 Mock Search，再询问“第二条结果是什么”，期望 Agent 能利用先前工具结果回答或合理再次选择工具。）
- [ ] **INT-09 工具调用和结果保持原子关系。**（验证：触发 Context 预算裁剪，期望测试断言中不会出现孤立 assistant tool_call 或缺少其对应 tool result 的 Context。）
- [ ] **INT-10 同 Session 并发顺序稳定。**（验证：同时向同一 Session 发起两个测试 Run，期望它们串行完成且历史不交错；同时向不同 Session 发起请求时两者可独立推进。）
- [ ] **INT-11 Web 和 CLI 共享持久状态。**（验证：CLI 创建 Session 并写入一条消息，随后启动 Web 并打开同一数据库，期望网页能够列出该 Session 及其历史。）
- [ ] **INT-12 应用重启后可继续会话。**（验证：创建 Session、添加 Todo、关闭并重启应用，再次进入原 Session，期望历史和 Todo 均存在且可继续对话。）

## 4. 异常与边界

- [ ] **ERR-01 最大轮次可靠终止。**（验证：设置较小 `max_rounds` 并让 Fake LLM 持续请求工具，期望调用次数不超过上限，Run 状态为 `max_rounds` 且用户收到明确终止信息。）
- [ ] **ERR-02 LLM 超时受控。**（验证：让 Fake/MockTransport 抛出 read timeout，期望 Run 状态为 failed、Trace 包含 `LLMTimeoutError`，下一次请求仍可成功。）
- [ ] **ERR-03 LLM HTTP 错误受控。**（验证：模拟 401、429 和 500，期望返回稳定错误类型，不把上游响应、Authorization 或 API Key 暴露给用户。）
- [ ] **ERR-04 LLM 协议错误受控。**（验证：模拟空 choices、空内容且无 tool_calls、畸形 arguments，期望产生 `LLMProtocolError` 或可回填参数错误，进程不退出。）
- [ ] **ERR-05 工具异常不会击穿服务。**（验证：注册一个主动抛异常的测试工具，期望生成失败 ToolResult 和 Trace；随后普通 Run 仍可完成。）
- [ ] **ERR-06 压缩失败有降级方案。**（验证：让摘要 LLM 调用失败，期望使用确定性降级摘要、Context 仍受预算约束，并出现 `compression_fallback` 事件。）
- [ ] **ERR-07 无效 Session 返回明确错误。**（验证：请求不存在的 Session API，期望 404；CLI `/use` 不存在 ID 时显示提示且继续运行。）
- [ ] **ERR-08 非法用户请求在边界被拒绝。**（验证：提交空白消息、超长消息和非法 JSON，期望 API 返回稳定 4xx 或受控错误，不创建不完整 Run。）

## 5. 安全与隐私

- [ ] **SEC-01 仓库不包含凭据。**（验证：运行密钥模式扫描并检查 Git 待提交文件，期望无真实 API Key、Authorization Header、`.env` 或包含凭据的日志。）
- [ ] **SEC-02 Trace 自动脱敏。**（验证：向 Trace 测试 Payload 注入 `api_key`、`authorization`、`token` 和 `cookie` 嵌套字段，期望查询结果均为 `[REDACTED]`。）
- [ ] **SEC-03 工具不能由模型越权指定 Session。**（验证：尝试在 Todo 参数中传入另一 Session ID，期望参数被拒绝或忽略，工具只操作 Runtime 注入的当前 Session。）
- [ ] **SEC-04 Calculator 不执行任意代码。**（验证：提交导入、函数调用、属性访问、下标和超深表达式，期望全部拒绝且不产生文件、进程或网络副作用。）
- [ ] **SEC-05 不保存隐藏思维链。**（验证：检查 RunResult、Trace、SQLite 消息及网页输出，只应存在最终回答、结构化工具事件和必要摘要，不存在声称为模型隐藏推理的完整内容。）
- [ ] **SEC-06 工具与日志输出有限长。**（验证：让测试工具返回超长字符串，期望回填内容和 Trace Payload 被截断，后续 Context 仍能构建。）

## 6. 构建与自动化测试

- [ ] **QA-01 源码可编译。**（验证：运行 `python -m compileall app`，期望退出码为 0。）
- [ ] **QA-02 核心模型与协议测试通过。**（验证：运行 `pytest tests/unit/test_models.py -q`，期望全部通过。）
- [ ] **QA-03 工具测试通过。**（验证：运行 `pytest tests/unit/test_tool_registry.py tests/unit/test_calculator.py tests/unit/test_mock_search.py tests/unit/test_todo.py -q`，期望全部通过。）
- [ ] **QA-04 LLM、Context、Memory 与 Trace 测试通过。**（验证：运行 `pytest tests/unit/test_llm_parser.py tests/unit/test_context.py tests/unit/test_memory.py tests/unit/test_tracing.py -q`，期望全部通过。）
- [ ] **QA-05 Repository 与 Runtime 集成测试通过。**（验证：运行 `pytest tests/integration/test_repository.py tests/integration/test_agent_loop.py tests/integration/test_sessions.py tests/integration/test_error_paths.py -q`，期望全部通过。）
- [ ] **QA-06 API、CLI 与 Web 测试通过。**（验证：运行 `pytest tests/integration/test_api.py tests/integration/test_cli.py tests/integration/test_web.py -q`，期望全部通过。）
- [ ] **QA-07 完整离线测试可单命令运行。**（验证：运行 `pytest -q -m "not live"`，期望全部通过、无网络依赖、无测试顺序依赖。）
- [ ] **QA-08 Ruff 通过。**（验证：运行 `ruff check .`，期望退出码为 0。）
- [ ] **QA-09 mypy 通过。**（验证：运行 `mypy app`，期望退出码为 0。）
- [ ] **QA-10 真实 LLM 测试通过。**（验证：安全设置真实凭据后运行 `$env:RUN_LIVE_LLM_TESTS='1'; pytest tests/e2e/test_live_llm.py -q -m live`，期望普通回答、calculator 和 Todo 三个场景通过。）

## 7. 端到端场景

- [ ] **E2E-01 普通问答。**（验证：在网页输入“用一句话说明什么是 Agent Runtime”，期望无需工具即可得到非空回答，Trace 无 tool 事件。）
- [ ] **E2E-02 Calculator 闭环。**（验证：输入“请计算 (18 + 24) * 3，并说明结果”，期望模型自主调用 calculator，工具结果为 126，最终回答包含正确结果。）
- [ ] **E2E-03 Mock Search 与追问。**（验证：输入一个明确的搜索请求，期望调用 search 并返回稳定列表；随后追问其中某条信息，期望基于历史结果回答。）
- [ ] **E2E-04 Todo 多轮操作。**（验证：要求添加“周五提交笔试”，再询问“我的待办有哪些”，期望模型两次使用或合理使用 todo，列表包含该事项。）
- [ ] **E2E-05 双 Session 隔离。**（验证：Session A 添加待办并讨论周报；Session B 讨论天气/搜索并查询待办，期望 B 看不到 A 内容；切回 A 可继续原话题。）
- [ ] **E2E-06 长对话压缩。**（验证：使用较小 Context 预算输入多轮含重要事实的对话，期望 Trace 出现 compression 事件；压缩后追问该事实仍能回答。）
- [ ] **E2E-07 最大轮次展示。**（验证：在测试/演示配置中触发持续工具请求，期望到达限制后停止并显示明确提示，页面不持续加载。）
- [ ] **E2E-08 错误恢复。**（验证：先使用无效模型配置制造受控 LLM 错误，再恢复正确配置并发送普通问题，期望第二次 Run 正常完成，原错误 Trace 可查询。）
- [ ] **E2E-09 重启恢复。**（验证：完成一段对话和 Todo 后重启应用，刷新网页并选择原 Session，期望历史、Todo、Memory 和 Trace 数据仍可访问。）
- [ ] **E2E-10 Web 完整演示。**（验证：按 `docs/demo-script.md` 从启动到工具调用、追问、Session 切换和 Trace 展开完整执行一次，所有步骤与预期一致。）
- [ ] **E2E-11 CLI 完整演示。**（验证：在 CLI 创建 Session、执行计算器、查看 `/trace`、退出后重新进入该 Session，期望全过程成功。）

## 8. 文档与提交材料

- [ ] **DOC-01 README 运行说明可复现。**（验证：由未参与开发的人或新的虚拟环境严格按 README 安装并启动 Web/CLI，期望无需修改源码即可运行。）
- [ ] **DOC-02 README 系统设计完整。**（验证：检查 README 明确解释 Agent Loop、工具注册/校验、Session、Context、SQLite、Trace 和异常路径。）
- [ ] **DOC-03 README 解释 Memory。**（验证：检查 README 明确写出压缩触发时机、召回时机、在 Context 中的位置、摘要水位及 Session 隔离。）
- [ ] **DOC-04 README 解释限制。**（验证：检查 README 明确说明单进程、Mock Search、非流式响应、基础字符预算和 OpenAI-compatible tool-call 要求。）
- [ ] **DOC-05 AI 开发记录真实完整。**（验证：检查 `docs/ai-development-log.md` 包含需求、spec、plan、实现、调试和验证阶段的 Prompt/摘要、人工判断、遇到的问题及验证证据。）
- [ ] **DOC-06 录屏脚本可执行。**（验证：逐项执行 `docs/demo-script.md`，每一步都有输入、预期结果和需要展示的证据，完整流程时长适合提交。）
- [ ] **DOC-07 代码仓库可访问。**（验证：使用未登录或面试官可用权限打开最终仓库链接，期望代码、README 和文档完整可见，历史中无密钥。）
- [ ] **DOC-08 录屏内容完整。**（验证：最终视频实际展示启动、网页或终端操作、真实 LLM、三个工具、追问、双 Session、Trace 和代表性异常，画面不出现密钥。）

## 9. 验收标准映射

| Spec 验收标准 | 必须通过的检查项 |
| --- | --- |
| AC1：真实 LLM 直接回答及工具闭环 | IMP-01、IMP-03、INT-01、INT-02、QA-10、E2E-01、E2E-02 |
| AC2：三个带 Schema 的工具 | IMP-04、IMP-06、IMP-07、IMP-08、QA-03、E2E-02、E2E-03、E2E-04 |
| AC3：未知工具和无效参数受控 | IMP-05、INT-04、ERR-05 |
| AC4：Session 隔离与恢复 | IMP-09、INT-05、INT-06、INT-12、E2E-05、E2E-09 |
| AC5：纯对话和工具追问 | INT-07、INT-08、E2E-03、E2E-04 |
| AC6：最大轮次终止 | ERR-01、E2E-07 |
| AC7：Context 压缩与 Memory 隔离 | IMP-10、IMP-11、INT-06、INT-09、ERR-06、E2E-06 |
| AC8：错误恢复 | ERR-02、ERR-03、ERR-04、ERR-05、ERR-06、E2E-08 |
| AC9：完整 Trace 且无密钥 | IMP-12、SEC-01、SEC-02、SEC-05、E2E-11 |
| AC10：网页和终端共用 Runtime | ENV-05、IMP-13、IMP-14、INT-11、E2E-10、E2E-11 |
| AC11：自动化和真实 LLM 测试 | QA-01 至 QA-10 |
| AC12：README、AI 记录与录屏 | DOC-01 至 DOC-08 |

