# 笔试提交包

本目录集中放置除录屏文件之外的正式提交材料。代码、测试和项目首页说明位于仓库根目录；
录屏已由候选人完成，不应把大体积视频或任何包含凭据的文件提交到 Git 仓库。

## 可直接填写到提交页面的内容

### 真实 LLM API

项目已接入 OpenAI-compatible Chat Completions API，支持结构化 `tool_calls`。真实端到端
验证使用 LongCat-2.0，覆盖普通回答、Calculator 工具闭环和 Todo 多轮工具闭环，结果为
`3 passed in 52.17s`。API Key 仅从本地 `.env` 读取并写入 Authorization Header，未进入
源码、日志、Trace 或提交材料。

### 代码链接

```text
待创建 GitHub 远程仓库后填写，例如：
https://github.com/<你的用户名>/minimal-agent-runtime
```

建议创建空的 GitHub 仓库，再按照 [GitHub上传指南.md](GitHub上传指南.md) 推送当前本地仓库。

### 终端或网页操作录屏

```text
录屏已完成；请在正式提交前粘贴面试官可访问的分享链接。
```

建议使用网盘、视频平台或招聘方指定渠道，并以无痕窗口验证链接无需候选人账号即可访问。

### README

项目根目录 [`README.md`](../README.md) 已包含：

- 安装、真实模型配置、Web/CLI 运行方式；
- 系统架构、Agent Loop、工具注册与错误处理；
- Session、SQLite、Trace 与并发设计；
- Memory 压缩触发时机、存储位置和召回顺序；
- 自动化测试、真实 LLM 测试和已知边界。

### AI Prompt 与问题解决记录

- 提交版：[`AI-Prompt与问题解决记录.md`](AI-Prompt与问题解决记录.md)
- 完整开发日志：[`../docs/ai-development-log.md`](../docs/ai-development-log.md)
- 验收证据：[`../docs/acceptance-report.md`](../docs/acceptance-report.md)

## 项目简介

本项目从零实现一个不依赖 LangGraph、OpenHands、OpenClaw 等 Agent 框架的最小 Agent
Runtime。核心流程由项目自行控制：构建 Context、调用真实 LLM、解析工具请求、校验并执行
工具、回填工具结果、继续多轮循环，直到生成最终回答或触发安全停止条件。

项目提供 FastAPI Web 页面和 CLI 两个入口，二者复用同一个 `AgentApplication` 与
`AgentRuntime`。状态使用 SQLite 持久化，支持多 Session 隔离、基础 Memory 压缩、结构化
Trace、受控错误结果和自动化测试。

## 正式提交前仍需人工完成

1. 在 GitHub 创建空仓库并推送本地代码。
2. 将生成的 GitHub 仓库 URL 填入上面的“代码链接”。
3. 上传已经完成的录屏并填写分享 URL。
4. 用无痕窗口验证代码仓库和录屏链接均可访问。
5. 最后核对 [`提交前检查清单.md`](提交前检查清单.md)。
