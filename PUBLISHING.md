# DataOps Agent 发布检查清单

这份清单的目标是让仓库能经得起面试官、开源使用者和未来维护者的复查。它不把本地单元测试、Docker 配置和生产部署混为一谈；每一项都应保留可复现的证据。

## 0. 发布边界

- 当前仓库的可发布单元是 `dataops_agent/`：数据摄取、DuckDB 质量审计、受限 SQL、任务进度、可选 Redis Streams 传输、知识检索适配器、MCP 只读工具和安全 Trace。
- 原生 DuckDB 由 API 进程持有；内存队列通过同一进程的 FastAPI `BackgroundTasks` 消费，Redis Streams 则由同进程生命周期 worker 消费并恢复 `pending_publish` outbox。Redis Streams 可以作为可选传输层，但本仓库不把它发布成原生 DuckDB 的独立、多进程 Worker 拓扑。
- 所有变更状态的接口（`/ingest`、`/ingestion`、`/ingest/csv`、`/audit`）都要求非空 `Idempotency-Key`。同一键与同一请求重放先前响应；同一键配不同请求必须返回 `409`。默认 file-backed 配置会持久化请求 fingerprint 与首个响应，审计任务也有独立的持久幂等记录。
- CI 只运行 `tests/dataops`，使用内存 DuckDB 与 fake Redis/Elasticsearch 客户端；因此 CI 通过证明的是接口契约和回归测试，而不是远端 Redis、Elasticsearch 或 Docker 已在某个环境部署成功。
- 任何性能数字、成功率或“生产可用”结论，应当来自带日期、数据规模、硬件配置和命令的基准记录。没有证据时，不在 README 或简历中填写具体数值。

## 1. 本地发布前必须完成

在仓库根目录执行。PowerShell 示例：

```powershell
python --version
python -m pip install -r requirements-dataops.txt
python -m pytest tests/dataops -q
python -m compileall -q dataops_agent
git status --short
git diff --check
```

验收标准：

- `pytest` 退出码为 0；若有 warning，要确认不是新引入的弃用、安全或资源泄漏问题。
- `compileall` 和 `git diff --check` 均无输出、退出码为 0。
- 工作区中不应包含 `.dataops/`、trace JSONL、DuckDB 文件、`.env`、访问令牌或本地导出的样本数据。
- 运行一次 API 演示，并把实际使用的命令、日期和结果写入发布说明或 GitHub Release Notes；不要凭记忆声称演示已成功。

最小的幂等性冒烟验证应包含一次重放和一次冲突请求：

```powershell
$headers = @{ "Idempotency-Key" = "release-smoke-ingest-001" }
$body = '{"batch_id":"release-smoke","records":[{"record_id":"r-1","source":"smoke","value":1}]}'
Invoke-RestMethod http://127.0.0.1:8000/ingest -Method Post -Headers $headers -ContentType application/json -Body $body
Invoke-RestMethod http://127.0.0.1:8000/ingest -Method Post -Headers $headers -ContentType application/json -Body $body
# 该请求必须失败并返回 HTTP 409：同一键不可绑定到不同请求。
Invoke-RestMethod http://127.0.0.1:8000/ingest -Method Post -Headers $headers -ContentType application/json -Body '{"batch_id":"release-smoke","records":[{"record_id":"r-2","source":"smoke","value":2}]}'
```

## 2. 可选集成验证（强烈建议）

单元测试不会启动外部服务。要证明实际集成可用，另行执行：

```powershell
docker compose -f docker-compose.dataops.yml up --build
```

然后在另一个终端完成 `/health`、JSON/CSV 摄取、`/audit`、`/tasks/{task_id}/progress`、`/sql`、`/knowledge` 和 trace 文件检查。记录：Docker/Compose 版本、镜像 tag、环境变量（删除敏感值后）、时间戳、请求和响应摘要。

若启用 Redis Streams，请验证 API 所属进程中的入队、`pending_publish` 自动重投、消费、ACK 与异常恢复，不要把同一个原生 DuckDB 文件交给外部独立 Worker 并发消费；若接入真实 Elasticsearch，请验证索引 mapping、权限、HTTPS 和备份策略。未做这些验证时，发布说明应写“可选适配器已覆盖契约测试”，而不是“已部署 Redis/Elasticsearch 集群”。

默认 Compose 演示只证明 Elasticsearch mapping/bootstrap 与词法检索种子。Hybrid KNN/vector 检索必须有应用注入的 embedder；没有该依赖时，不能在 Release Notes 中宣称已运行语义向量检索。

## 3. 安全与配置检查

- 不提交 `.env`、API key、Redis 口令、Elasticsearch 用户名/密码、生产 URL、真实用户数据或 trace 原文。
- 为生产 Redis/Elasticsearch 使用 TLS、最小权限账号、网络隔离和密钥管理服务；Docker 演示中的禁用安全配置只适用于本地开发。
- 对 `DATAOPS_DATABASE_PATH`、`DATAOPS_TRACE_PATH` 使用受控目录和最小文件权限；Trace 必须继续最小化任意工具输入为结构统计、脱敏凭据/常见 PII，且避免记录原始敏感字段。
- 审查允许的 SQL 表和函数白名单、输入大小限制、默认 1,000 行结果上限、CSV 编码/格式错误处理、幂等键策略、任务失败/重试策略与审计日志保留期限；长查询仍需在应用或基础设施层设置请求 deadline。
- 若公开 MCP，确认 `python -m dataops_agent.mcp_server` 仍只通过 stdio 暴露五个只读工具；不要把它描述为自带 LLM、自动模型接入或写入权限的服务。
- 在公开 issue、截图、README 和简历中，使用合成数据或经过脱敏的数据；不要展示 token、内部路径或客户标识。

## 4. GitHub 远端发布步骤

以下步骤需要拥有目标 GitHub 仓库的写权限，不能由本地测试替代：

1. 确认当前分支、目标仓库和待提交文件；只暂存本次发布相关路径，避免把其他人的未提交修改带入提交。
2. 创建清晰的提交，例如 `feat(dataops): harden runtime and add release assets`；推送到非默认分支，并以 Draft PR 发起评审。
3. 在 PR 中确认 `DataOps CI` 对 Python 3.11 与 3.12 都通过；失败时先修复并重新运行，不要绕过 required check。
4. 请求至少一次人工审阅，重点复核安全、公开接口、文档中是否有未经证实的效果描述，以及 Redis/Elasticsearch 的开发配置是否被误用于生产。
5. 合并前补齐仓库 About、topics、可复现的 Quick Start，并复核现有 MIT `LICENSE` 的权利人、版本和兼容性是否符合仓库所有者的发布意图。README 必须保留 Docker 未在本次环境实跑的声明，以及 KNN 依赖 embedder、MCP 仅 stdio 只读工具的边界。
6. 创建带语义化版本号的 Git tag 与 GitHub Release，Release Notes 至少列出功能、破坏性变更、验证命令、已知限制和安全配置说明。

## 5. 面试与开源表述校验

发布前逐条检查 README、简历和演示稿：

- 用“实现 / 提供 / 覆盖了契约测试”描述已验证能力。
- 用“可选适配器 / 待部署验证”描述未做真实服务联调的能力。
- 数据事实由 DuckDB/SQL 获取；非结构化说明由检索组件获取；会话、缓存和异步协调由 Redis 承担。不要把其中任一项泛化成所有数据的唯一来源。
- 遇到吞吐、P95、成本、准确率等数字，能立即给出数据集、基线、命令和测量日期；否则删掉数字。

## 6. 发布后观察

- 关注 GitHub Actions、Dependabot/依赖告警、issue 与安全通报。
- 对每次接口、schema、质量规则或检索策略变更补充测试和迁移说明。
- 对外部服务故障、任务堆积、trace 脱敏失败和 SQL 拒绝日志建立可查询的告警与复盘记录。
