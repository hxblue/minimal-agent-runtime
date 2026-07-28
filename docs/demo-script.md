# 笔试录屏脚本

建议时长：6–9 分钟。录屏前关闭包含 `.env` 或 API Key 的编辑器/终端历史。

## 1. 录制前准备

1. 使用支持结构化 tool calls 的真实模型配置 `.env`。
2. 为了演示压缩，可临时设置：

   ```dotenv
   AGENT_CONTEXT_BUDGET=4000
   AGENT_COMPRESSION_THRESHOLD=0.65
   AGENT_RECENT_TURNS=2
   ```

3. 运行离线测试并保留通过画面：

   ```powershell
   pytest -q -m "not live"
   ```

4. 启动单进程网页：

   ```powershell
   uvicorn app.api.app:create_app --factory --host 127.0.0.1 --port 8000
   ```

## 2. 开场：解释系统（约 45 秒）

- 展示 README 架构图。
- 说明核心 Agent Runtime 自研，FastAPI/网页只是入口。
- 指出页面顶部 `INPUT → MODEL → TOOL → CONTINUE` 循环轨道。
- 展示左下角三个已注册工具和右侧 Trace 飞行记录器。

## 3. 普通回答（约 30 秒）

输入：

```text
不要调用工具，用一句话说明什么是 Agent Runtime。
```

预期：

- 返回非空直接回答。
- Trace 中出现 model 事件，但没有 tool 事件。

## 4. Calculator 闭环（约 45 秒）

输入：

```text
请使用 calculator 工具计算 (18 + 24) * 3，再告诉我结果。
```

预期：

- 页面出现 TOOL REQUEST 和 TOOL RESULT。
- 结果为 126。
- Trace 展示 `model_started → tool_started → tool_completed → model_started → run_completed`。

## 5. Mock Search 与工具追问（约 60 秒）

输入：

```text
请使用 search 工具查找 Session 隔离相关资料，返回两条。
```

随后追问：

```text
第一条资料的核心结论是什么？
```

预期：

- 搜索结果稳定且 URL 使用 `mock://`。
- 追问能够利用之前工具结果。

## 6. Todo 与双 Session 隔离（约 90 秒）

在 Session A 输入：

```text
请用 todo 工具添加：周五提交 Agent 笔试。
```

新建 Session B，输入：

```text
请用 todo 工具列出我的待办。
```

预期 B 为空。切回 A，再输入相同查询，预期看到“周五提交 Agent 笔试”。强调 Todo
不能接受模型指定的 Session ID，只使用 Runtime 注入的作用域。

## 7. Context 压缩与 Memory（约 90 秒）

在同一 Session 连续提供 4–5 轮较长但可辨识的信息，例如：

```text
请记住项目代号是 Blue Finch，并解释你会怎样安排第一阶段工作。
```

继续补充若干背景后追问：

```text
最开始告诉你的项目代号是什么？
```

预期：

- Trace 出现 `compression_completed`；若摘要服务临时失败，则出现
  `compression_fallback`。
- 仍能回答 `Blue Finch`。
- 说明 Memory 在 SQLite 中按 Session 保存，并放在 System Prompt 之后、近期消息之前。

## 8. 错误处理与测试证据（约 45 秒）

回到终端运行：

```powershell
pytest tests/integration/test_error_paths.py -q
```

说明这些测试覆盖 LLM 超时、协议错误、未配置模型和未知 Session；失败 Run 会留下
`run_failed` Trace，下一次请求仍能成功。

## 9. CLI 复用同一 Runtime（约 45 秒）

运行：

```powershell
python -m app.cli
```

展示 `/tools`、一次计算、`/trace` 和 `/sessions`。说明 CLI 直接调用 Application
Service，不复制 Agent Loop。

## 10. 收尾（约 30 秒）

- 展示 `pytest -q -m "not live"`、`ruff check .` 和 `mypy app` 通过结果。
- 展示 README 的限制说明与 AI 开发记录。
- 确认录屏画面未出现密钥、`.env` 内容或私人信息。
