# Feiyu GitHub 最小治理实验设计

## 1. 目标

在公开仓库 `a444777/feiyu` 中建立一条可验证的 GitHub 协作与交付流水线，并用两个独立 GitHub 账号演练真实开源贡献流程。

- Maintainer：`a444777`
- 首次贡献者：`momobiubiu`
- 上游仓库：`https://github.com/a444777/feiyu`
- 默认分支：`main`
- 仓库可见性：公开

本阶段不实现完整的知识沉淀系统，只构建最小 FastAPI 应用和仓库治理 Harness，以学习 fork、分支、commit、push、PR、审核、CI、CodeQL、Ruleset、合并和 CD。

## 2. 成功标准

实验完成时必须能证明：

1. `momobiubiu` 能从 fork 的功能分支向 `a444777/feiyu:main` 提交 PR。
2. 首次贡献者的 GitHub Actions 在 Maintainer 批准前不运行。
3. CI 或 CodeQL 未完成、失败或报告超过阈值的安全问题时，PR 不能合并。
4. 即使检查通过，没有 `a444777` 的 Code Owner Review 也不能合并。
5. 新提交会使旧审批失效，未解决讨论会阻止合并。
6. PR 以 squash 方式合并后，产生 GHCR 镜像的 `latest` 和 commit SHA 标签。
7. 可从 GHCR 拉取镜像并验证 `/health` 返回成功。
8. 贡献者能将合并后的上游 `main` 同步回自己的 fork。

## 3. 仓库结构

```text
feiyu/
├── app/
│   ├── __init__.py
│   └── main.py
├── tests/
│   └── test_health.py
├── docs/
│   ├── knowledge-precipitation-report-human.md
│   ├── knowledge-precipitation-report-ai.md
│   └── superpowers/specs/2026-08-12-github-governance-lab-design.md
├── .github/
│   ├── CODEOWNERS
│   ├── pull_request_template.md
│   └── workflows/
│       ├── ci.yml
│       ├── codeql.yml
│       └── release.yml
├── .dockerignore
├── .gitignore
├── CONTRIBUTING.md
├── Dockerfile
├── pyproject.toml
└── README.md
```

## 4. 最小应用

- Python 3.12。
- FastAPI 应用提供 `GET /health`。
- pytest 验证健康检查的状态码和响应体。
- Ruff 执行代码质量检查。
- Dockerfile 生成可运行镜像，容器中通过 Uvicorn 启动服务。

完整知识沉淀系统的人读版和 AI 实现参考版文档进入 `docs/`，但其业务实现不属于本次实验。

## 5. GitHub Actions

### 5.1 CI

`ci.yml` 在 `pull_request` 和对 `main` 的 `push` 时运行，执行：

1. Checkout。
2. 安装 Python 3.12。
3. 安装项目与开发依赖。
4. Ruff 检查。
5. pytest。

稳定的 job 名为 `quality`，用于 Ruleset 的 required status check。

### 5.2 CodeQL

`codeql.yml` 在 `pull_request`、对 `main` 的 `push` 和定时任务中扫描 Python，使用 `github/codeql-action/*@v4`。job 名为 `analyze-python`。

fork PR 的 token 仅获得扫描所需的最小权限；工作流不读取 secrets，不使用 `pull_request_target`。

### 5.3 GHCR 发布

`release.yml` 仅在对 `main` 的 `push` 中运行，权限限定为：

```yaml
permissions:
  contents: read
  packages: write
```

工作流构建并发布：

- `ghcr.io/a444777/feiyu:latest`
- `ghcr.io/a444777/feiyu:<commit-sha>`

CD 的边界是发布可部署容器镜像，不包含第三方云平台或公网服务部署。

## 6. Ruleset

在初始 CI 和 CodeQL 至少成功运行一次后，由 `a444777` 创建 Active branch ruleset `main-governance`，Target 为 Default branch。

不配置 bypass actor，并启用：

- Restrict deletions。
- Block force pushes。
- Require a pull request before merging。
- Required approvals = 1。
- Require review from Code Owners。
- Dismiss stale approvals when new commits are pushed。
- Require conversation resolution before merging。
- Require status checks to pass。
- Require branches to be up to date before merging。
- Required checks：从首次真实运行中选择 `quality` 和 `analyze-python` 对应的精确 check name。
- Require code scanning results：CodeQL，安全阈值为 `high` 及以上。

`.github/CODEOWNERS` 将全部路径的 Code Owner 设为 `@a444777`。

仓库只保留 Squash merging，关闭 merge commit 和 rebase merge，合并后自动删除贡献分支。

## 7. 首次贡献者审批

Actions 设置为：

```text
Approval for running fork pull request workflows
→ Require approval for first-time contributors
```

`momobiubiu` 首次从 fork 提交 PR 后：

1. Actions 等待 `a444777` 批准。
2. `a444777` 必须先检查 Files changed，尤其是 `.github/workflows/`。
3. 确认可安全运行后，点击 `Approve workflows to run`。
4. 工作流批准只允许 Runner 执行，不替代 PR Review。
5. 所有检查通过后，`a444777` 还必须单独提交 Approve review。

## 8. 本地双账号模型

为两个账号使用独立 SSH key 和 host alias：

- `github-a444777`
- `github-momobiubiu`

使用两个独立工作目录：

- `feiyu-maintainer/`
- `feiyu-contributor/`

贡献者仓库的 remote：

```text
origin   git@github-momobiubiu:momobiubiu/feiyu.git
upstream https://github.com/a444777/feiyu.git
```

每个本地仓库必须设置对应账号的 repo-local `user.name` 和 `user.email`，避免提交归属错账号。

## 9. 实验剧本

### 9.1 Maintainer 初始化

1. 创建最小应用、测试、文档和三条工作流。
2. 在本地验证 Ruff、pytest 和 Docker build。
3. 推送初始 `main`。
4. 验证 CI、CodeQL 和 GHCR 发布。
5. 创建并激活 `main-governance` Ruleset。

### 9.2 故意失败的首次 PR

1. `momobiubiu` fork 上游仓库。
2. clone 个人 fork，添加 upstream remote。
3. 创建 `feature/expression-preview`。
4. 提交一个明确的命令注入风险演示：将外部输入传给 `subprocess` 的 `shell=True`。
5. push 到 `momobiubiu/feiyu` 并向上游 `main` 创建 PR。
6. 观察工作流等待批准与 Merge 按钮禁用。
7. `a444777` 审查后允许工作流运行。
8. 观察 CodeQL 安全告警和 Ruleset 阻塞。

该危险代码不得合并到 `main`。

### 9.3 在同一 PR 中修复

1. 删除 shell 执行，改为确定性操作白名单。
2. 补充对应测试并 push 到同一 feature branch。
3. 观察 PR 自动更新、检查重跑和旧审批失效。
4. 解决全部 Review conversation。
5. `a444777` 提交新的 Approve review。
6. 只有全部门禁满足后才执行 Squash merge。

### 9.4 交付与同步

1. 验证 Release workflow 只在合并后运行。
2. 验证 GHCR 的 `latest` 和 SHA 标签。
3. 拉取镜像，启动容器并请求 `/health`。
4. 删除已合并分支。
5. `momobiubiu` 从 upstream fetch 并将本地与 fork 的 `main` 同步到上游状态。

## 10. 失败处理

- 首次 CodeQL 检查名称与预期不同：不手写猜测，从 Ruleset 界面选择真实 check。
- Required check 永久 Pending：检查 workflow trigger 是否覆盖 fork PR，以及 check name 是否唯一。
- CodeQL 未识别演示漏洞：不降低门禁，先查看 SARIF 与扫描日志，再换用 CodeQL Python 支持且能稳定重现的最小演示。
- fork workflow 没有等待批准：检查 Actions 的 fork PR 批准策略与账号是否真的从未贡献。
- GHCR 发布失败：检查 workflow 的 `packages: write`、包所有权和仓库 Actions 权限。
- 双账号凭证串号：停止 push，用 `ssh -T` 确认 host alias 对应的 GitHub 身份，再检查 repo-local Git 身份。

## 11. 范围边界

本次包含：

- Git/GitHub 双账号与 fork 协作。
- FastAPI 最小应用。
- CI、CodeQL、Ruleset、Code Review、GHCR CD。
- 门禁成功与失败路径验证。

本次不包含：

- 完整知识沉淀业务。
- 数据库、LLM、文档解析和 OKF 实现。
- 第三方云平台或生产群集部署。
- 自动绕过人工审核或代替用户点击 GitHub 高风险审批。

## 12. 实施停止点

每个阶段都在实际结果符合预期后再继续。遇到下列情况必须暂停：

- 当前 GitHub 身份与预期账号不符。
- 要求为 fork PR 暴露 secrets 或提高 token 权限。
- 危险演示代码有可能被合并、发布或对外部系统执行。
- 需要删除远程数据、改写历史或做其他不可逆操作。
