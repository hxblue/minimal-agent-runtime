# GitHub 上传指南

## 1. 在 GitHub 创建空仓库

1. 登录 GitHub，点击右上角 `+`，选择 `New repository`。
2. Repository name 建议填写 `minimal-agent-runtime`。
3. Description 可填写：

   ```text
   Framework-free minimal Agent Runtime with tool calling, multi-session memory, tracing, Web UI and CLI.
   ```

4. 按招聘方要求选择 Public；如必须 Private，需要单独邀请面试官账号。
5. 不要勾选 `Add a README file`、`.gitignore` 或 License，创建一个完全空的远程仓库。
6. 点击 `Create repository`，复制 HTTPS 地址，例如：

   ```text
   https://github.com/<你的用户名>/minimal-agent-runtime.git
   ```

## 2. 推送已经准备好的本地仓库

在本项目根目录打开 PowerShell。若 Codex 已经完成本地首个提交，只需要执行：

```powershell
git remote add origin https://github.com/<你的用户名>/minimal-agent-runtime.git
git push -u origin main
```

如果执行 `git remote -v` 已经存在名为 `origin` 的地址，则改用：

```powershell
git remote set-url origin https://github.com/<你的用户名>/minimal-agent-runtime.git
git push -u origin main
```

GitHub 不再接受账户密码作为 Git HTTPS 密码。根据终端提示使用浏览器登录、Git
Credential Manager 或 Personal Access Token；不要把 Token 写入项目文件。

## 3. 推送后检查

```powershell
git remote -v
git status
```

浏览器打开：

```text
https://github.com/<你的用户名>/minimal-agent-runtime
```

确认：

- 首页显示根目录 README；
- `app/`、`tests/`、`docs/`、`submission/` 可见；
- `.env`、`.venv/`、`venv/`、`data/agent.db`、`.idea/` 和录屏文件不可见；
- `submission/README.md` 和 AI Prompt 记录可以正常打开；
- 仓库权限允许面试官访问。

## 4. 后续修改后再次上传

```powershell
git add -A
git commit -m "Update submission materials"
git push
```

正式提交的代码链接不需要以 `.git` 结尾，应填写浏览器页面地址：

```text
https://github.com/<你的用户名>/minimal-agent-runtime
```
