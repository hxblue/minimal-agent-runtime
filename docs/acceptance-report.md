# 最小可用 Agent Runtime 验收报告

验收日期：2026-07-28

## 结论

核心实现、离线自动化测试、静态检查、安全扫描、界面静态验收和真实 LLM
端到端验证均已完成。项目既可在未配置密钥时启动并查看健康状态，也已使用
LongCat-2.0 验证 OpenAI-compatible 结构化工具闭环。

## 已通过的自动化验证

| 验证项 | 命令 | 结果 |
| --- | --- | --- |
| 完整离线测试 | `pytest -q -m "not live"` | 74 passed，3 deselected |
| 完整测试默认行为 | `pytest -q` | 74 passed，3 live skipped |
| 代码规范 | `ruff check .` | 通过 |
| 类型检查 | `mypy app` | 26 个源码文件通过 |
| Python 编译 | `python -m compileall app` | 通过 |
| CLI 入口 | `python -m app.cli --help` | 正常显示帮助 |
| FastAPI 工厂 | `python -c "from app.api.app import create_app; print(create_app().title)"` | `Minimal Agent Runtime` |
| 禁止框架扫描 | 扫描 `app/` 与 `pyproject.toml` | 无匹配 |
| 凭据模式扫描 | 扫描源码、测试和交付文档 | 无匹配 |
| 真实 LLM 测试 | `pytest tests/e2e/test_live_llm.py -q -m live -vv` | 3 passed，52.17 秒 |

离线测试已覆盖：直接回答、单/多工具闭环、参数修正、最大轮次、LLM 超时与 HTTP
错误、工具异常、Session 隔离与并发、SQLite 重启恢复、Memory 压缩与降级、Context
预算、Trace 脱敏、API、CLI 和 Web 静态资源。

## 人工检查

- 以 1440×1000 浏览器视口检查 Runtime Workbench：Session 台账、聊天区、工具结果、
  Trace 飞行记录器和 Loop 状态轨道均正常显示。
- 页面、CLI 和 Runtime 共用同一 `AgentApplication` 与 SQLite Repository，没有复制
  Agent 决策逻辑。
- 本地 Git 仓库已初始化，提交材料已整理并通过提交前检查；远程仓库由候选人创建后绑定。
- 操作录屏已由候选人完成；正式提交前只需上传到面试官可访问的位置并填写链接。
- Mock Weather 注册后，API 工具列表测试仍保留旧的三工具预期；已同步为四工具预期并完成
  全量回归，最终结果为 `74 passed, 3 deselected`。

## 真实模型验证

使用 `LongCat-2.0` 和 `https://api.longcat.chat/openai/v1` 完成以下场景：

1. 普通回答：通过，模型直接返回非空答案且没有工具事件。
2. Calculator：通过，模型自主发起结构化工具调用，工具结果为 126，随后生成最终答案。
3. Todo 多轮：通过，模型完成 add/list 两次工具调用并在后续回答中使用持久化结果。

执行期间未打印或写入 API Key。测试还确认 LongCat-2.0 的实际 OpenAI 兼容端点能够
接受本项目使用的 `tools`、`tool_choice`、`tool_calls` 和 tool result 消息闭环。

## 尚待正式提交

1. 创建面试官可访问的远程代码仓库并核对仓库链接权限。
2. 上传已经完成的操作录屏，填写可访问链接并检查权限。

需要重新运行真实验证时执行：

```powershell
$env:RUN_LIVE_LLM_TESTS='1'
pytest tests/e2e/test_live_llm.py -q -m live
```

不要把 `.env`、SQLite 数据库、录屏中的凭据或 Authorization Header 加入提交。
