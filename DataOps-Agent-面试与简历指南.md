# DataOps Agent：面试与简历指南

> 面向 GitHub 公开项目与面试准备的说明书。本文只把当前仓库中已经实现、可由代码或测试验证的能力写成“已实现”；Redis、Elasticsearch、模型服务和 VerbalVis 接入等外部或后续能力会明确标为“适配接口 / 待上线验证”。
>
> **发布前原则：** 不要把“单元测试通过”写成“线上高并发稳定运行”，不要把“可插拔接口”写成“已在生产部署”，不要填写任何没有实验记录支撑的吞吐、P95、成本或成功率数字。文中所有 `【待实测】` 必须替换为本次发布对应的命令、日期、机器配置和原始报告链接。

## 1. 项目定位

**项目名：DataOps Agent Runtime —— 面向多源数据质量审计的可观测工具运行时**

这是一个将确定性数据处理能力包装为结构化工具的独立 Python 服务。它的目标不是把所有问题都交给大模型，而是让不同类型的信息请求走到合适的确定性系统：结构化事实由 DuckDB/SQL 计算，文档与规则由检索层提供，任务与运行时状态由队列和状态存储接口协调。FastAPI 暴露 JSON/CSV 导入、质量审计、任务进度、受限 SQL、知识检索和请求路由端点。

当前可在本地代码与测试中核实的核心能力包括：

- JSON 与 UTF-8 CSV 导入、按 `batch_id` 的重复批次跳过、坏记录隔离，以及 DuckDB 持久化；
- 已完成批次的 `schema_valid_rate` 与 `duplicate_rate` 质量报告；
- 只允许 `SELECT` / `WITH` 的 SQL 接口，限定表、函数和数据源，并在隔离的内存 DuckDB 副本中执行；
- 默认将 SQL 响应限制为 1,000 行，并将查询 deadline 明确留在应用或部署边界；
- DuckDB 持久化审计任务状态、本地 FIFO 队列，以及可选 Redis Streams 队列适配器；
- Markdown 分块、元数据过滤、精确标识符优先、RRF 融合和可插拔重排接口；可选 Elasticsearch 适配器可在提供向量函数时组合 lexical 与 KNN 检索；
- 工具描述、上下文裁剪、内存/Redis 状态存储和 JSONL 脱敏追踪等 Runtime 基础构件。
- 可选的 stdio MCP Server，已通过 SDK 内存客户端验证五个只读工具的发现与调用；它不承载写入操作，也没有接入 FastAPI 的模型规划链。

它**没有**在当前提交中把 LLM 规划器、Redis StateStore、ContextManager 或 MCP host session 全部接入 FastAPI 的每一条请求链；MCP Server 目前只提供只读 stdio tool discovery，未提供认证、会话路由或变更型工具。它也没有改动 VerbalVis 的单会话实验行为。面试时要主动说明：这是“可验证的 Runtime 基础设施 + 明确的接入边界”，而不是虚构的生产平台。

## 2. 一句话与技术责任图

**一句话介绍：** 我把数据导入、质量审计和 SQL 分析做成确定性工具，再为它们补齐任务状态、检索知识与可观测性边界；核心原则是“事实走 SQL、解释走检索、运行态走状态存储”。

| 负载 / 问题 | 首选组件 | 为什么 | 当前仓库边界 |
| --- | --- | --- | --- |
| 记录、批次、质量指标、精确聚合 | DuckDB + 受限 SQL | 结果可复算、可审计，适合聚合、过滤和版本化事实 | 已实现并由本地测试覆盖 |
| 文档、规则、Runbook、历史案例 | `HybridRetriever` / 可选 Elasticsearch | 非结构化说明不应混入事实表；精确 ID 先直查，再做检索 | 本地检索已实现；ES 为可选适配器 |
| 会话 ownership、幂等键、异步队列、缓存 | `StateStore` / Redis Streams 接口 | 运行态需要低延迟、跨进程共享和显式 ACK，不应成为事实唯一来源 | 内存实现可测；Redis 适配器可配置，尚需真实集群演练 |
| 质量审计任务的最终结果 | DuckDB TaskStore | 任务进度、结果和错误需要持久可查，队列消息不能是唯一真相 | 已实现 |
| LLM / MCP 编排 | ToolSpec、Router、只读 stdio MCP Server | 先规范工具 schema 与确定性边界，再换模型或协议 | 已实现 5 个只读 MCP 工具；未接入 LLM、认证、会话路由或变更型工具 |

```text
JSON / CSV
    │
    ▼
ETL：校验、去重、隔离坏记录 ──────────────► DuckDB（records / batches / audit tasks）
    │                                              │
    ├──────────────────────────────────────────────┤
    ▼                                              ▼
质量规则 / 审计任务                         受限只读 SQL
    │                                              │
    ▼                                              ▼
本地队列 或 Redis Streams 适配器             精确事实、指标与明细
    │
    ▼
任务进度 / JSONL Trace

文档、质量规则、Runbook ──► 分块 + 元数据 ──► Hybrid Retrieval / 可选 Elasticsearch
                                                │
                                                ▼
                                     供 Agent 的“解释性知识”工具使用
```

## 3. 中文简历 Item（请按岗位选择其一）

### Agent 开发 / AI 应用工程版本

**DataOps Agent Runtime｜Python、FastAPI、DuckDB、Redis Streams、Elasticsearch（可选）**

- 构建面向数据质量审计的 Agent 工具运行时，将 JSON/CSV 导入、质量审计、受限 SQL 与知识检索封装为 FastAPI 工具；按“结构化事实走 SQL、非结构化解释走检索、运行态走状态存储”解耦数据与 Agent 能力。
- 设计批次幂等、坏记录隔离与 DuckDB 持久化任务状态；实现本地队列及 Redis Streams 适配接口，任务仅在持久化为终态后 ACK，支持通过进度端点查询审计结果。
- 实现 ToolSpec、response ownership / 幂等 StateStore、字符预算 ContextManager 与脱敏 JSONL Trace 基础构件；提供精确标识符优先、RRF 融合、可插拔 reranker 与 Elasticsearch hybrid retrieval 适配边界，并开放 5 个只读 stdio MCP 工具。
- 以 pytest 覆盖 ETL、SQL 安全、任务状态、检索、路由和端到端 API 合约；发布前补充并附上【待实测：版本、环境、测试数、耗时】证据，不以未测性能替代工程事实。

### 数据工程 / 数据分析工程版本

**多源数据导入与质量审计平台（DataOps Agent）｜Python、DuckDB、SQL、FastAPI**

- 建立 JSON/CSV → 字段校验 → 去重 → quarantine → DuckDB 的可重复 ETL 链路，以 `batch_id` 实现批次级幂等；对无 `record_id` 或非对象输入保留原始内容与失败原因，避免静默丢数。
- 基于完成批次计算 `schema_valid_rate`、`duplicate_rate`，并以持久化审计任务输出可查询的质量结果；将耗时审计从同步 HTTP 路径抽离为队列任务与进度查询。
- 实现受限分析 SQL：仅开放允许表、允许函数和单条 `SELECT/WITH`，在隔离内存副本中执行，从接口层阻断 DDL/DML、外部文件读取和源库宏的副作用。
- 将文档规则与事实数据分层管理：指标和明细由 SQL 精确计算，字段定义、审计规则与 Runbook 由带 metadata filter 的检索层提供，为后续智能分析保留可审计的数据底座。

### 简历数字使用规则

可填的数字必须能被仓库中的报告复现，例如：`覆盖 X 条测试`、`以 N 条合成记录在 M 配置下完成导入`、`P95 为 Y ms`。不要写“百万级”“高并发”“生产可用”“节省 80% 成本”等没有基准、压测脚本、原始日志和实验条件支撑的结论。可暂时写成：`完成 10K/100K/1M 合成数据基准对比（报告链接）`，再在发布前替换占位。

## 4. 两分钟演示与发布证据清单

建议在 GitHub README 或 Release 中附上以下证据，而不是只放架构图：

所有写入端点（`/ingest`、`/ingestion`、`/ingest/csv`、`/audit`）必须带非空 `Idempotency-Key` 请求头；相同 key 与相同请求会重放结果，相同 key 与不同请求返回 `409`。

1. 运行 `python -m pytest tests/dataops -q`，保存终端输出与 commit SHA；
2. 使用 `/ingest` 导入 JSON、使用 `/ingest/csv?batch_id=...` 导入 UTF-8 CSV，展示一条有效记录与一条 quarantined 记录；
3. 触发 `/audit`，轮询 `/tasks/{task_id}/progress` 至终态；
4. 调用 `/sql` 展示合法聚合，并展示危险 SQL 被拒绝；
5. 调用 `/knowledge` 展示 metadata filter 与标识符查询；
6. 读取 JSONL trace，确认 `Authorization`、Bearer token 等敏感内容已被替换；
7. 若声明 Redis / Elasticsearch 可用，额外提供真实容器启动日志、健康检查、至少一次 Streams 消费与 ES 检索的集成测试结果；
8. 发布前执行依赖扫描、密钥扫描、许可证确认、CI 检查和 `git diff --check`。外部服务未实测时应明确写“适配器已测，真实服务 E2E 待验证”。

## 5. 面试问答使用方法

- **P0：必须讲透。** 这类问题决定面试官是否相信你理解项目边界与工程取舍。
- **P1：高频追问。** 这类问题用于证明你不仅会搭框架，也能解释失败路径、测试与安全。
- **P2：加分与反问。** 这类问题用于展示演进思路；未实现的内容必须用“下一步会……”表达，不能伪装成现状。

以下 100 题按重要性降序排列。回答并非逐字背诵稿；每题均给出建议的应答结构。真实面试时先给结论，再给实现细节、取舍和证据。

## P0｜核心项目叙事与架构（1–30）

### 01. 这个项目解决什么问题？为什么值得做？

它解决的是数据任务从“脚本能跑”到“服务可解释、结果可追溯”的断层。很多分析型 Agent 直接把自然语言交给模型，事实计算、规则解释、任务状态和聊天上下文混在一起，结果难复现也难排错。我的做法是先把导入、校验、SQL 统计和审计做成确定性工具，再让 Agent Runtime 负责选择和编排。这样既能服务数据质量场景，也能回答 Agent 工程岗位最关心的 tool use、state、trace 与失败恢复问题。

### 02. 用一句话向面试官介绍它？

我会说：**“这是一个把多源数据导入、质量审计和 SQL 分析封装成可追溯工具的 DataOps Runtime；结构化事实用 DuckDB 精确计算，规则和说明由检索层提供，异步任务和运行态通过队列/状态接口协调。”** 接着补一句边界：当前版本的核心处理路径可本地验证，Redis、Elasticsearch 和 VerbalVis 的连接是可替换接口或单独的后续集成，而不是虚构的线上部署。

### 03. 为什么不再做一个普通 RAG 问答项目？

普通“文档切块—向量检索—回答”很难证明数据工程能力，也会把应由 SQL 回答的问题变成近似检索。例如“某批次重复率是多少”必须由确定性聚合得出，不能由 embedding 猜。这个项目把 RAG 降为知识工具：它解释字段定义、审计规则、Runbook 和历史案例；而记录数、质量率、任务进度等事实仍由 DuckDB 和 TaskStore 给出。这样架构更符合真实系统的职责边界。

### 04. 为什么要同时有 DuckDB、Redis 和 Elasticsearch？一个库不够吗？

它们处理的是三种不同负载。DuckDB 是结构化事实和精确计算的持久层；Redis 的角色是低延迟运行态、幂等键与 Streams 消息协调，不应成为审计结果唯一真相；Elasticsearch 是可选的非结构化知识检索适配器，适合 lexical、向量和 metadata filter。把三者硬塞进一个库会导致 SQL 统计、临时会话和文档检索相互牵制。当前仓库的 DuckDB 路径是主证据，Redis/ES 需要在真实服务环境继续验收。

### 05. 系统从用户请求到结果的主链路是什么？

导入请求先经 FastAPI 接收 JSON 或原始 CSV，再进入 ETL：校验对象与 `record_id`、判重、写入记录或 quarantine，并记录完成批次。审计请求只创建并持久化任务，由本地队列或 Redis Streams 适配器消费，质量规则生成结果后更新任务终态。事实类问题走只读 SQL；规则或文档类问题走检索；两类请求都会在配置 tracer 时写入经脱敏处理的 JSONL 事件。关键是每一步都有明确的责任方，而不是让模型同时承担数据库、队列和解释器。

### 06. 为什么选择 DuckDB，而不是一开始就上 PostgreSQL 或 Spark？

当前目标是可公开、可复现、低运维的面试项目：DuckDB 嵌入 Python、SQL 完整、列式分析友好，适合单机批处理与本地 demo，也减少了启动额外数据库的门槛。它不是对 PostgreSQL/Spark 的替代：多用户事务、服务端并发写入、权限治理或分布式大数据会改用 PostgreSQL、对象存储与 Spark/Flink。面试时应强调选择由当前 workload 决定，不能把 DuckDB 包装成生产 OLTP 数据库。

### 07. 为什么把“数据事实”和“知识解释”分开？

事实应可精确、可审计、可复算，例如某批次的重复率、某条记录是否隔离、某任务是否完成；这些来自 SQL 或持久化状态。知识解释具有文本性和上下文性，例如字段含义、质量规则的业务原因、故障 Runbook，适合检索后供模型组织语言。将两者分开可以避免 RAG 幻觉污染指标，也避免把所有文档硬编码到 SQL 表中。面试时我会拿“当前任务进度不能用向量检索”作为具体例子。

### 08. 这个项目里的“Agent”体现在哪里？它是不是只是 API 集合？

当前提交刻意先完成 Agent 的可验证底座，而不是伪造一个黑盒 LLM demo：工具有名称、描述、输入 schema 与是否变更状态的声明；路由区分 SQL、知识、审计和多步计划；Runtime 具备 state、context、trace 的独立构件。真正的 LLM planner 或 MCP transport 可以在这些确定性边界上接入。这样做的价值是模型可替换，数据处理与安全控制不会随 prompt 漂移；同时我会明确承认当前 API 尚未内置一个真实模型调用链。

### 09. 为什么先做 DataOps MVP，再补知识和 Runtime？

因为没有可信数据底座，Agent 只会把不可靠输入包装得更像答案。第一阶段先验证导入、隔离、幂等、质量指标、SQL 和任务进度，建立可以重复执行的事实层；第二阶段才在其上增加检索、状态、工具声明和 trace。这个顺序也便于测试：即使 Redis、ES 或模型服务不可用，核心 ETL 与审计仍可在本地运行，避免外部依赖掩盖业务错误。

### 10. 如何向数据岗和 Agent 岗分别讲这个项目？

投数据岗时，我主讲 ETL、数据契约、quarantine、批次幂等、DuckDB/SQL、质量指标和异步审计，强调 Python 负责解析与规则，SQL 负责精确聚合。投 Agent 岗时，我主讲 ToolSpec、路由、运行态、幂等、队列 ACK、trace、上下文预算和 RAG 的职责边界。两份叙事共享同一事实基础，只是把“可靠工具”与“自主编排”分别放在前面，避免为两个方向虚构两个割裂项目。

### 11. ETL 的 Extract、Transform、Load 分别是什么？

Extract 接收 JSON records 或 UTF-8 `text/csv` 原始请求体；Transform 对输入是否为对象、是否存在非空 `record_id` 做校验，标准化 `source`，并区分重复和无效记录；Load 将有效记录写入 DuckDB、将坏记录及原因写入 quarantine、写入批次统计并标记完成。这个链路的重点不是“清洗得多复杂”，而是输入失败可定位、重放不会重复写、批次结果可追溯。

### 12. 如何实现批次幂等？为什么用 `batch_id`？

导入以调用方提供的 `batch_id` 为自然幂等键。在一个批次锁和事务中先 claim 批次；若同一完成批次再次提交，返回 `skipped` 而不重复插入。`batch_id` 能把一次业务导入作为整体管理，适合重试与审计。它也有前提：调用方必须稳定地产生 ID，并明确“同 ID 是同一份不可变输入”；若允许同 ID 更新内容，就应改成版本号、内容 hash 或显式 upsert 语义。

### 13. 为什么坏记录要 quarantine，而不是直接丢弃或让整批失败？

直接丢弃会造成不可见的数据损失，整批失败又会让少量脏数据阻塞大批可用数据。quarantine 保存原始记录与失败原因，因此既能继续服务正常记录，也能把修复责任和数据质量问题暴露出来。对于强一致金融结算等场景，策略可能改为整批阻断；项目选择隔离是为了演示可观测的数据质量治理，而不是声称所有业务都应容错导入。

### 14. 当前质量规则和指标有哪些？如何解释？

当前质量报告聚合已完成导入批次，输出 `schema_valid_rate` 与 `duplicate_rate`。前者以被接受或判为重复的记录占接收数的比例衡量最基本的结构有效性，后者是接收记录中被判为重复的比例；其意义是用最小而可验证的指标搭出质量框架。面试时不要冒充已经有完整 Great Expectations 规则库；下一步可按业务加入完整率、引用完整性、值域、时效性与跨表一致性规则。

### 15. 重复记录是怎样识别和处理的？

当前以 `record_id` 的已有记录为准判重。重复记录不重复写入事实表，但被计入批次 `duplicates`，从而影响质量指标并保留批次层面的可见性。这体现了“数据去重”与“调用幂等”的差异：前者是记录键级别，后者是批次请求级别。若真实业务允许同一 ID 的版本演进，应改用复合键或 SCD/version 表，而不是沿用这一简化策略。

### 16. 受限 SQL 为什么不能只靠检查是否以 `SELECT` 开头？

因为 `SELECT` 可以隐藏危险能力，例如访问外部文件、系统表、扩展函数、序列函数或自定义宏，也可能通过多语句拼接绕过。当前实现不仅要求单条 `SELECT/WITH`，还限制来源表、关系操作和函数名，并在一个新建的内存 DuckDB sandbox 中只复制允许表的数据再执行。这样即使源库存在宏、序列或扩展，也不会在查询接口执行它们；这比简单关键字黑名单更接近安全边界。

### 17. SQL sandbox 的代价和局限是什么？

每次受限 SQL 都要把允许表 materialize 到内存 sandbox，安全隔离更强，但大表复制会增加延迟和内存消耗。当前默认最多返回 1,000 行，超限会拒绝响应；这控制了结果传输与 `fetchall` 风险，但不等于执行时间上限。它适合 demo、管理分析和小中型受控查询，不适合作为无限制 BI 查询服务。生产上可进一步引入只读数据库账号、资源组、应用层 deadline、SQL parser/AST 校验、预计算指标表和查询缓存。面试时主动说明这个取舍比声称“绝对安全且高性能”更可信。

### 18. 为什么允许表和函数都要 allow-list？

表 allow-list 限制数据边界，防止用户借 SQL 枚举内部元数据或读取无授权关系；函数 allow-list 限制执行能力，防止看似只读的 `nextval`、sleep、外部读取函数等产生副作用、拖垮 worker 或越权。两者缺一不可。对函数的控制还要防止同名宏覆盖，因此最终在隔离连接执行，而不是只在源连接按名字放行。

### 19. 审计任务为什么要持久化到 DuckDB，而不只放 Redis Streams？

Redis Streams 解决消息分发、consumer group 和 ACK，不是审计结果的长期事实库。任务的状态、完成量、质量报告和错误需要能被 API 稳定查询，也要在队列重启或消息被 ACK 后继续保留，因此 TaskStore 以 DuckDB 为最终事实。这里遵循一个原则：消息队列协调工作，数据库保存业务结果；否则一次 ACK 或过期策略就可能让用户失去任务结论。

### 20. 任务状态机是怎样设计的？

任务包含 `pending_publish`、`queued`、`running`、`completed`、`failed` 和 `skipped` 等状态。`pending_publish` 表示已写入 TaskStore、但尚未成功发到外部队列；`queued` 表示可消费；worker 开始后进入 `running`，只有质量报告或错误被持久化后进入终态。状态转换由 store 校验允许来源，避免任意覆盖。具体状态可随业务简化，但“持久化终态在 ACK 前”是不可省略的因果约束。

### 21. 为什么 Redis Streams 比 Pub/Sub 更适合批量审计？

Pub/Sub 适合瞬时通知，消费者离线就会错过消息，也没有待处理列表与显式确认；批量审计需要消费组分摊、pending message、重新领取和 ACK。Streams 提供这些语义，因此适合把 API 提交与耗时处理解耦。不过当前 DuckDB 拓扑只支持由 API 所在进程后台 drain；若要多进程 consumer，必须先迁移 TaskStore 到 PostgreSQL 等共享写入存储，或实现严格单写入者架构，再演练 consumer 异常、死信队列、lease/heartbeat、积压报警和公平性。

### 22. 什么时候 ACK Redis Stream 消息？为什么？

原则是：**只有 TaskStore 已经确认任务处于持久化终态后才 ACK。** 若先 ACK、后写结果失败，消息已经消失而任务永远停在 running 或 queued，造成不可恢复的“幽灵任务”。当前 worker 会在处理后检查任务是否为终态再确认；如果持久化失败，不应 ACK，以便后续恢复或人工诊断。这里可以顺带说明 at-least-once 的现实：重复投递必须由幂等与状态机承担。

### 23. `pending_publish` 解决了什么问题？它是否等于事务性消息？

它处理的是“任务先持久化，但 `XADD` 发布失败”的窗口：任务先处于 `pending_publish`，同一幂等键再次提交时可沿用原任务而不是创建第二个任务。当前 API 所在进程的生命周期 worker 会扫描并重投这些 durable outbox 记录，因此客户端不必再次发送请求；它仍不等于完整事务性消息系统，因为数据库提交和 Redis 发布不能原子完成。生产继续需要发布尝试记录、退避、告警、死信与幂等消费。

### 24. 当前的幂等机制覆盖哪些操作？

ETL 导入以 `batch_id` 做批次幂等；审计任务模型支持 `idempotency_key`，TaskStore 为该键建立唯一约束。当前 API 的所有 mutation 都强制非空 `Idempotency-Key`：同 key、同请求重放首个结果，同 key、不同请求返回 `409`；默认 file-backed 配置会持久化请求 fingerprint 与首个响应，覆盖 API 重启后的重试。Runtime 的 StateStore 还定义了原子 claim 幂等键的接口。生产仍需规定 key 的 TTL、跨进程部署策略和 fingerprint 演进策略。

### 25. 什么是 response ownership？为什么 DataOps 里也要考虑它？

在交互式 Agent 中，一个 session 可能先后产生多个 response；较早 response 的工具结果晚到时，不能覆盖用户当前意图。StateStore 通过 session 的 response ID 与递增 epoch，让工具在执行前确认自己仍拥有 admission 权。DataOps 的独立服务先把这项能力实现为可测接口，VerbalVis 仍保留原有本地协调器；未来接入时必须采用“双重准入”，不能用 Redis 状态替换当前中断语义。

### 26. ContextManager 目前做了什么？不能做什么？

当前 ContextManager 是一个明确、轻量的字符预算构件：从最新消息向前保留完整消息，超出预算时停止，不截断半条内容。它适合证明上下文预算应当作为 Runtime 责任，而不是无限堆聊天历史。它尚未接入真实 token 计数、摘要模型、持久记忆或 FastAPI 的 LLM 请求链，因此面试时应把它描述为“可测试的压缩策略基础”，并说明生产要按模型 tokenizer、消息类型和检索引用做分层预算。

### 27. Tool Registry 的价值是什么？

ToolSpec 把工具名称、描述、handler、输入 schema 与是否变更状态集中声明，避免工具散落在业务代码和 prompt 字符串中。统一 registry 后可以在执行前做 schema 验证、权限、timeout、trace、重试和 idempotency 控制，也可以生成 MCP/OpenAI function 的描述。当前仓库已提供独立的只读 stdio MCP Server，但真正的统一 dispatch/hook 链路、认证与变更型工具策略仍是下一步。

### 28. 为什么需要 Trace？目前 Trace 记录了什么？

没有 Trace 时，回答错了只能看用户描述，无法分辨是导入、SQL、检索、队列还是模型路由出错。当前 JSONL tracer 将任意工具输入最小化为类型、字段数、项数等形状统计，并递归脱敏常见密钥、Bearer/Basic、email、SSN 与卡号片段；API 事件已含 `trace_id`、`session_id`、`call_id`、工具名、状态、`elapsed_ms`、`retry_count` 与时间戳。它仍未记录 LLM token/cost、统一错误分类或跨进程 trace 关联，所以不能宣称已经具备完整生产 observability。

### 29. 该怎样设计完整的可观测性事件？

我会为每个请求生成 `trace_id`，为每次工具调用生成 `call_id`，并记录 `session_id`、tool 名称、参数摘要/哈希、结果大小、状态、开始结束时间、耗时、重试数、异常分类和数据版本；LLM 场景再记录模型、输入/输出 token 和成本估算。敏感内容只保留 hash 或长度。这样可以计算成功率、工具 P95、重试率与成本，同时能够关联一次多步任务的所有事件。

### 30. Hybrid RAG 在此项目中的正确位置是什么？

它是**解释性知识工具**，不是事实数据库的替代。对于 `bar_02_q03`、批次 ID、文件路径等确定标识符，系统应先精确查找；对于“show 变体是什么意思”“为什么这个质量规则存在”“类似故障如何处理”，才需要 lexical、向量和 metadata 过滤的检索。当前本地 retriever 提供词法/元数据 RRF 与 reranker 协议；可选 ES adapter 在注入 embedding 函数时可使用 RRF 合并 match 和 KNN。没有真实 embedding 或 reranker 服务时，不能夸大其语义召回效果。

## P1｜工程实现、可靠性与安全（31–70）

### 31. 请求路由器如何区分 SQL、知识、审计和计划？

当前 Router 是狭窄、确定性的规则路由：显式 SQL 或聚合/筛选词优先走 SQL，审计与质量检查词走 AUDIT，文档、定义和 Runbook 词走 KNOWLEDGE，多步工作流词走 PLAN，其余归为 LOOKUP。这样做的好处是可测、可解释、不会把简单事实都交给模型。局限是规则对中文和复杂表达的覆盖有限；生产可以让 LLM 产生受 schema 约束的 route，再由确定性 validator 和策略层做最终裁决。

### 32. 为什么 SQL 路由优先于知识检索？

当用户问数量、均值、过滤结果或版本差异时，需要最新、精确、可复算的结构化事实。若先走知识检索，很可能找到旧文档、样例数据或仅有定义的段落，造成“答案看似合理但数错”的问题。因此 router 对聚合和查询意图优先选 SQL。只有用户同时要求解释原因时，计划才应先 SQL 获取事实，再检索规则或历史案例补充解释。

### 33. 既然没有完整 LLM planner，为什么仍称为 Agent Runtime？

因为 Agent 的难点常常不在 while loop，而在模型之外的工具边界、状态、幂等、任务持久化、上下文预算和可观测性。项目当前实现的是可验证的 runtime primitives，并故意不绑定某个模型供应商。更准确的表述是“Agent Runtime MVP / tool foundation”；下一步才是接入一个结构化 tool-calling 模型并把 route、plan、tool result 放进统一执行循环。名称不能掩盖当前范围，反而应体现工程演进路线。

### 34. 为什么 JSON 和 CSV 都要支持？

JSON 方便服务间调用和保留嵌套 payload，CSV 是数据团队最常见的人工导入与批量交换格式。两种入口最终被归一到 records，因此后续校验、去重、隔离和入库逻辑不会分叉。当前 CSV 接口接收 UTF-8 `text/csv` 原始 body，检查空内容、重复/空 header 和列数不一致；它不是 multipart 文件上传服务，超大文件的流式解析与对象存储暂不在此 MVP 范围。

### 35. 如何处理 CSV 编码和格式错误？

实现接受 UTF-8（含 BOM），无法解码、空 body、无数据行、空/重复 header、行列数不一致或 CSV 语法异常会返回明确的 400 错误。这样把传输格式错误挡在 ETL 之前，避免把整份损坏文本当作数据。对于真实多地区数据，可增加编码探测、列映射、分隔符配置和逐行错误报告，但要避免默默猜错编码导致字段错位。

### 36. 为什么要同时有 batch lock 和数据库事务？

事务保证同一进程/连接中的“claim 批次—写记录—写批次统计”要么一起成功要么回滚；batch lock 用于避免同一批次被并发调用时重复 claim。文件数据库在多进程场景还需跨进程锁与连接生命周期控制，不能误以为一个 Python `Lock` 就足够。面试时可说明：锁保护竞争窗口，事务保护原子性，两者针对的问题不同。

### 37. DuckDB 文件连接为什么是风险点？

嵌入式数据库的连接属于进程内资源。若 ETL 为了释放文件锁而关闭了与 TaskStore 共享的连接，后续审计或 API 查询会在“已关闭连接”上失败；多个连接也会引入写事务竞争。因此代码需要明确谁拥有连接、何时关闭、哪些路径共享连接，并用文件路径集成测试覆盖“导入后立即审计”。这是比纯内存 happy path 更接近真实工程的问题。

### 38. 质量审计为什么做成异步任务，而不是同步 HTTP？

小批次同步执行当然简单，但批次变大或规则变多时会占用 Web worker、易超时且无法报告阶段进度。异步任务把 API 的职责限定为受理与返回 `task_id`，worker 负责执行，TaskStore 提供可轮询的真相。这样也为重试、限流、并发控制和失败治理留出位置；代价是需要设计状态机、幂等和队列恢复，不能只加一个后台线程就声称可靠。

### 39. 任务进度有哪些字段？如何让前端或 Agent 使用？

TaskProgress 至少包含任务 ID、状态、已完成数、总数、百分比、结果与错误。前端可以轮询 `/tasks/{task_id}/progress` 或未来由 SSE/WebSocket 推送；Agent 则读取确定性任务状态，而不是“记忆”它已经做了多少。结果和错误摘要必须保存在持久化 TaskStore，中途 worker 崩溃时才能给用户一个真实的 pending/running/failed 状态，而不是编造完成。

### 40. Redis Streams 的 consumer group 如何工作？

生产上每个 worker 以同一个 group、不同 consumer name 读取 stream 中未交付消息；Redis 把一条消息交给其中一个 consumer，并把它放入 PEL（pending entries list）。worker 在数据库成功写出终态后 `XACK`，否则消息仍可被观察或重新领取。当前适配器使用 `XGROUP CREATE`、`XREADGROUP`、`XAUTOCLAIM` 和 `XACK` 的基本语义；真正部署还需要 consumer 唯一命名、阻塞读取、连接重试和 metrics。

### 41. stale reclaim 会不会造成重复执行？

会，这正是 at-least-once 队列的常态：worker A 处理很慢或崩溃，worker B 重新领取同一消息时必须假设 handler 可能已执行过。因此业务侧必须有 task 状态机和幂等：已终态任务只确认不重复做，正在运行的任务要结合 lease/heartbeat、尝试次数和安全重试策略决定等待、转失败或重跑。当前实现覆盖基本 reclaim/ACK 行为；“长时间 running 的自动恢复”仍应作为发布后的高优先级强化项，而非假装已经完全解决。

### 42. 如何设计可靠的任务重试？

我会先按错误分类：网络瞬时错误可指数退避重试，参数/规则错误直接失败，非幂等写入在开始后不自动重试。每次尝试记录 attempt、开始时间、lease、错误类型和下次可执行时间；超过阈值进入死信队列或人工处置。重试 key 与原任务 ID 绑定，结果写入采用 compare-and-set。这样避免“同一质量审计被无限重复”以及“重试覆盖了第一次的真实错误”。

### 43. Redis StateStore 和 TaskStore 分别保存什么？

StateStore 用于短生命周期运行态，例如某 session 当前 response、epoch 和幂等 claim；它追求原子性和低延迟。TaskStore 保存需要长期查询与审计的任务结果、进度和错误；它是业务真相。两者混在一起会有风险：把任务结果只存 Redis 会受 TTL/故障影响；把每次 response ownership 都写数据库则增加延迟和锁竞争。当前仓库分别提供两类接口，但 API 尚未把 Redis StateStore 作为必选依赖。

### 44. `claim_response` 为什么需要 epoch？只比较 response_id 不行吗？

epoch 是单调递增的版本号。只比较 response_id 虽然通常可用，但一旦出现重放、重复 ID、异步晚到或 session 状态被重置，版本信息能更清楚地表达“这是第几次所有权切换”。工具开始前带着 `(session_id, response_id, epoch)` 做 admission，只有与当前三元组一致才执行。Redis 版用 Lua 将递增与写入合成原子操作，避免两个 worker 在读改写之间竞争。

### 45. 为什么 VerbalVis 不能直接换成 Redis StateStore？

VerbalVis 当前的 ResponseCoordinator 还承载单会话、打断、音频和工具输出的本地时序语义。直接替换成远端存储可能让网络延迟、读写失败或状态不一致改变已有实验行为。正确做法是先加 adapter：保留本地 coordinator 的准入，再增加 StateStore 的第二道准入，只有二者都允许才执行工具。当前仓库有这份未来集成边界文档，但未改动实验版行为，面试时应把“未接入”说清楚。

### 46. Redis 的幂等键应该设置 TTL 吗？

应该，除非业务明确要求永久去重。无限期保存会导致键空间增长，也会让合法的新请求永远被判为旧请求；过短 TTL 又可能在客户端重试窗口结束前失效。TTL 应来自业务重试窗口、任务最长执行时间、消息保留策略和风险等级，并把首次请求的 payload hash 与响应摘要一起保存。当前 StateStore 接口只体现原子 `SET NX` 思路，TTL 和请求指纹比对是生产化时必须补充的契约。

### 47. 为什么检索要 metadata filter？

数据质量知识通常有版本、数据集、团队、规则类型和来源边界。例如同样叫“schema validity”的规则在不同版本或业务域含义可能不同；只靠语义相似会召回错误范围的文档。metadata filter 先用结构化条件缩小候选，再做匹配/向量排序，既提高准确性也便于权限隔离。当前本地 retriever 和 ES adapter 都支持等值 metadata filter。

### 48. RRF 是什么？为什么用它融合检索结果？

RRF（Reciprocal Rank Fusion）对每个候选按 `1 / (k + rank)` 计分，再合并多条召回列表。它不要求 lexical 分数和向量分数在同一量纲，工程上比直接相加稳健。项目中本地实现用词法和 metadata-token 排名做确定性 RRF；ES adapter 在提供 embedding 时可用 ES 的 RRF 合并 match 与 KNN。`k`、候选窗口和检索数仍需用离线标注集调参，不能凭直觉宣称最佳。

### 49. 为什么标识符查询要优先 exact lookup？

像 `bar_02_q03`、`AUDIT-SCHEMA-001` 或文档路径是结构化 ID；用户输入它时期待唯一、稳定的结果。向量相似可能把相近编号、相似段落排到前面，既慢也不可靠。因此项目对看起来像标识符的查询先查 document ID / metadata identifier / aliases，再补 hybrid 结果。这个原则可以概括为：能确定性定位，就不要为了展示 RAG 而使用近似检索。

### 50. 当前 reranker 到底实现到了哪里？

本地 HybridRetriever 定义了一个可插拔 `Reranker` 协议：它接收 RRF 后的候选并返回重排序结果，测试用确定性实现验证调用顺序。它不是已经接入的 Cross-Encoder，也没有在 ES adapter 中配置一个在线 rerank 模型。因此简历只能写“提供 reranker 接口和两阶段检索边界”，不能写“已部署 cross-encoder 使准确率提升 X%”。若要补齐，应选择模型、记录候选数/耗时并做 Recall@K、MRR、nDCG 对比。

### 51. Elasticsearch 的 mapping 为什么要显式声明向量维度和 keyword 字段？

向量字段的维度、索引和相似度必须与 embedding 模型一致，否则 KNN 查询会失败或结果失真；而 identifier、aliases 和常用 metadata 应是 keyword，才能做精确 term filter。项目的 bootstrap 会创建或检查 mapping，并写入一条确定性示例规则。这避免“搜索时临时建索引”的隐式副作用。前提是发布者真的运行过容器或 ES 集成测试；否则只能说请求结构和 bootstrap 合约已被 fake client 测试。

### 52. 如何给知识库做 chunking？

当前 Markdown chunker 按标题层级和段落切分，保留 `document_id`、`section_path` 和来源 metadata；超过字符预算再拆分。相比盲目定长切块，它能让检索结果保留“规则属于哪个章节”的语义，也便于引用源文档。仍需根据真实文档实验 chunk 长度、overlap、表格/代码块处理和多语言 tokenization，不能把 1,000 characters 当作通用最优值。

### 53. 怎样评估 RAG，而不是只看回答感觉？

先做带标准答案的 query–relevant chunk 集，分别测 exact-ID 命中率、Recall@K、MRR、nDCG、filter 正确率和无答案时的拒答率；再测端到端答案引用正确性、事实一致性、延迟和成本。对比 lexical、vector、hybrid、hybrid+rerank 四种配置，保留失败样本做 error taxonomy。当前项目提供可测检索原语，但未附带真实标注集与性能结论，因此这是发布时最值得追加的 evidence。

### 54. MCP 在这个项目里已经做到哪一步？

当前仓库已提供 `python -m dataops_agent.mcp_server` 启动的可选 stdio MCP Server，SDK 内存客户端测试了 `inspect_schema`、`quality_report`、`execute_readonly_sql`、`deterministic_lookup` 与 `route_request` 的发现和调用；五个工具都标为只读，SQL 仍复用隔离 sandbox。它没有接入 FastAPI 的 LLM 主链，也没有认证、host 会话路由、变更型工具或真实 MCP host E2E，因此正确说法是“已实现受限只读 MCP 接入”，而不是“完整企业 MCP 平台”。

### 55. 为什么工具需要 `mutates` 标记？

读工具的失败与重试通常风险较低，变更型工具会写数据、创建任务或影响外部系统，必须要求更严格的 permission、idempotency、审计和重试策略。一个 `mutates=True` 标记让 runtime 在不读取具体业务代码的情况下决定是否需要幂等键、是否允许自动重试、如何记录审计。它不是完整授权系统，生产还应加入用户身份、资源范围、审批和 allow-list policy。

### 56. 如何防止 Agent 生成危险 SQL？

第一层是让模型只生成受 schema 限制的工具参数；第二层是服务端把 SQL 当不可信输入，要求单语句 `SELECT/WITH`、允许来源表和函数；第三层是在不含源库宏/扩展的内存 sandbox 执行。还应设置行数、超时、扫描量和审计日志。关键是不能依赖“system prompt 说不要 DELETE”，因为 prompt 不是安全边界；最终权限必须在执行器侧强制。

### 57. 如何处理 SQL 注入？

SQL endpoint 本身允许用户表达查询，因此传统字符串拼接不是唯一问题；更重要是限制 query language 的能力边界。业务写入使用参数化 SQL，用户分析查询经过 admission 和 sandbox；不能把外部字符串直接插到表名、路径或 `COPY` 语句。对于需要过滤器的产品接口，更好的做法是暴露结构化 filter 工具并在服务端参数化生成 SQL，开放文本 SQL 仅给受信任分析角色并增加预算限制。

### 58. Trace 脱敏是怎样做的？还有什么不足？

JsonlTracer 对 `input`、`payload`、`records` 等非受控工具输入只保留类型、字段数或项数，不保留原始值；同时归一化识别 `authorization`、`token`、`password`、`secret` 等键，并替换 Bearer/Basic、email、SSN 和卡号片段。它适合避免开发日志直接泄密，但不是完整 DLP：错误文本、文件路径、未知敏感模式和历史 trace 仍需要规则、访问控制与发布前检查。公开 GitHub 前必须检查 `.dataops`、trace、`.env` 和历史提交。

### 59. 如何处理工具、数据库或外部服务的错误？

先把错误分为客户端输入错误、可重试基础设施错误、不可重试业务规则错误和未知错误。API 对 CSV/SQL 等可预期校验返回明确 4xx；审计 worker 把执行错误持久化为 failed；Redis/ES 适配器应由调用层区分连接失败和空结果。Trace 要记录错误类别和上下文摘要但不记录秘密。当前版本有基础失败持久化与 tracer，完整的退避、熔断和告警属于下一阶段。

### 60. 怎样避免外部服务不可用时整个 demo 无法启动？

核心单元和集成测试使用内存 DuckDB、本地队列和内存 retriever，不依赖 live Redis/ES。默认应用在未配置 ES URL 时使用空的本地 HybridRetriever；Redis URL 未配置时用 InMemoryTaskQueue。这样贡献者能先验证数据底座。Docker Compose 是展示 API+ES 的可选路径，但 README 也应明确“容器配置与 fake-client 请求形状测试”不等于已在所有环境完成真实 E2E。

### 61. 这个项目如何测试？

测试按边界分层：ETL 测幂等、quarantine、事务与文件连接；SQL 测语句、表、函数和 sandbox 绕过；tasks 测状态转换、发布失败、ACK 与 reclaim；runtime 测 ownership、registry、context、trace；knowledge 测 chunk、filter、RRF、exact lookup、mapping；integration 通过 FastAPI 串起导入、审计、SQL、检索和脱敏 trace。发布时请重新运行 `python -m pytest tests/dataops -q`，把实际输出写到 Release，而不是照抄旧文档计数。

### 62. 单元测试、集成测试和真实服务测试有什么区别？

单元测试隔离函数或适配器，定位错误快；集成测试验证模块间合约，例如 API 到 DuckDB 的完整链路；真实服务测试才会覆盖 Redis network、Elasticsearch mapping、Docker DNS、消费者崩溃和权限配置。项目现有测试强项是前两层，并用 fake client 约束外部请求形状。不能把 fake Redis/ES 通过说成容器压测通过；发布说明应分开列出三类证据。

### 63. 如何做数据质量规则的版本管理？

规则应有稳定 ID、版本、适用数据集/字段、严重级别、阈值、作者、启用状态和变更原因；审计结果还要记录“此次执行用的规则版本”。这样同一批数据在规则升级前后的差异可解释。当前项目有质量规则知识示例和基础指标，但未实现完整 rule registry；我会把这作为下一步 schema 设计，而不假装已有企业级数据治理平台。

### 64. 如何做增量导入与版本 diff？

当前批次幂等提供了“同一批不重复写”的最小增量语义。若需要真正版本 diff，应把业务主键、dataset version、ingested_at、payload hash 和有效期显式建模，导入时比较 hash 得到新增/删除/修改，再以 SQL 聚合不同类型。这样可以回答“新版本为什么质量率下降”。不要把当前简单 records 表的重复检测直接称为完整 CDC 或 SCD 实现。

### 65. 如何避免一个慢 SQL 把服务拖死？

当前最重要的防线是 allow-list 与 isolated sandbox，避免外部文件、任意函数和系统对象；但仍应承认它没有完整资源治理。生产上会加查询超时、最大返回行、最大扫描字节、并发 semaphore、取消句柄、缓存和预聚合表，并把重查询放入异步任务。面试时可以说安全与资源隔离是两个维度：没有副作用不代表不会耗尽 CPU/内存。

### 66. Redis Cache 和 Semantic Cache 应该怎么加？

先做确定性缓存：规范化只读 SQL 或工具参数，加入数据版本/规则版本，hash 后缓存结果并设置 TTL；数据导入后按版本自然失效。Semantic cache 只适合低风险的自然语言解释，必须保存 prompt、embedding、答案、适用 metadata 和阈值，且不能缓存当前任务状态或精确指标。当前项目未把 cache 接入主链路，因此只能把它列为演进项，不能作为简历已完成功能。

### 67. 为什么当前状态不能用 RAG 获取？

当前筛选器、当前 response、任务百分比和刚刚提交的批次属于强一致运行态；向量检索可能返回旧状态、相近 session 或过期文档，完全不满足正确性要求。它们应由 StateStore 或 TaskStore 做精确 key lookup。RAG 只回答“规则为什么这么设计”“字段是什么意思”一类允许文本语义的背景知识。这是区分 memory、state 和 retrieval 的关键工程原则。

### 68. 如何实现权限控制？

当前项目的权限主要体现在 SQL 表/函数 allow-list 与未来工具 `mutates` 标记，并不是完整认证授权。生产需在 FastAPI 前加入身份认证，给每个 tenant/user/role 绑定可访问数据集、字段、工具和知识 metadata filter；变更型操作需审计、审批和资源范围检查。不要说“用了 Redis / MCP 就有权限控制”，授权必须由服务端策略明确执行。

### 69. 你如何防止提示注入影响工具调用？

把检索文档与用户输入都看成不可信数据：它们可以提供内容，不能直接改变系统工具权限。模型输出必须满足结构化 schema，服务端再按工具注册表、身份、allow-list、幂等和资源限制执行；文档中的“忽略之前指令”不会自动成为指令。高风险工具可要求二次确认或 human-in-the-loop。当前项目的重点是确定性执行边界，prompt injection benchmark 是后续安全测试项。

### 70. 如何说明项目的效果而不夸大？

我会把效果拆成可验证的“能力结果”与待实验的“数值结果”。能力结果是：无效记录可隔离、重复批次不重复入库、审计任务能查询终态、危险 SQL 被拒绝、日志能脱敏、精确 ID 优先返回。数值结果只能写在真实基准后，例如【待实测：10K/100K/1M 记录导入耗时、内存、查询 P95、任务成功率】；并附机器、版本、数据生成方法和原始 CSV。

## P2｜发布、演进、行为题与加分追问（71–100）

### 71. GitHub 公开前最重要的检查是什么？

我会先确认没有 `.env`、API key、DuckDB 业务样本、trace、缓存和本地数据被提交，再运行测试、格式/静态检查、依赖审查和 `git diff --check`。README 必须写清本地最小运行路径、外部依赖、已验证范围与未验证范围；许可证、贡献方式和安全披露也要明确。最容易失分的是 README 写“生产级 Redis/ES”而 Compose 根本没有 Redis worker 或没有真实部署证据。

### 72. 发布 README 应该怎样写，才不像作业？

README 首屏应给出问题、架构图、两分钟 demo 和不变量；随后说明目录、端点、测试命令、外部服务配置、数据安全和已知限制。每个“亮点”都应链接到对应模块或测试，而不是只堆技术 logo。对本项目尤其要保留“DataOps 独立于 VerbalVis，未来 adapter 尚未接入”的说明；诚实的 scope 比过度营销更能获得工程面试官信任。

### 73. 如何设计 CI？

最小 CI 在干净 Python 环境安装 `requirements-dataops.txt`，运行 DataOps pytest、编译检查和可能的 linter；保存失败日志。第二层可用 Docker service 起 Redis/Elasticsearch 做真实 adapter E2E，并设置超时和镜像版本固定；第三层做依赖与 secret 扫描。CI 徽章只能在 workflow 实际存在并持续运行后添加，不能先贴绿色 badge 再补流水线。

### 74. Docker Compose 在项目中扮演什么角色？

它提供可重复的 API + Elasticsearch 演示环境，并在启动前执行知识索引 bootstrap。它降低外部检索层的上手门槛，但不是生产编排方案：当前 Compose 不等于 Kubernetes、没有完整 secret 管理、也不代表 Redis worker 已被同一文件部署。面试时我会强调 Compose 用于本地可复现 demo，生产需要拆分 image、healthcheck、volume、资源限制、配置中心和监控。

### 75. 如何做数据库迁移？

轻量 MVP 可以在初始化时创建表并谨慎做兼容列检查；但当 schema 进入多人协作或生产后，应使用版本化 migration，记录版本号、前置条件、回滚策略和 data backfill。对 DuckDB 也不能把 `ALTER` 当作随便可重复执行的脚本。TaskStore 的幂等键列和索引就是一个例子：迁移需要考虑已有库、唯一约束冲突与部署顺序。

### 76. 如果数据规模从 10K 增长到 1M，先优化哪里？

先通过基准确认瓶颈，而不是凭感觉换技术栈。可能的瓶颈包括 Python 逐行循环、JSON 序列化、每请求 sandbox 全表复制、重复任务扫描和 trace 同步写盘。针对结果可批量插入、用 Arrow/Parquet、按批次分区、预聚合质量指标、限制 SQL 返回、异步化重查询；若并发写入/多租户成为主矛盾，再迁到服务端数据库。每一步要保留相同数据集、同机器、warmup 和 P50/P95 指标。

### 77. 如何设计性能基准，避免“造数据”失真？

使用固定随机种子生成包含正常、重复、缺字段、长 payload 和不同 source 分布的合成数据，并保留生成器与数据概要。分别测试 10K、100K、500K、1M，记录导入吞吐、峰值内存、quarantine 比例、质量审计耗时、SQL P50/P95、并发数和失败率。冷热缓存要分开，运行至少多轮并报告方差。若数据来自真实项目，需脱敏并说明抽样方法，不能泄露原始数据。

### 78. 如何设计数据契约？

数据契约应包含字段名/类型/是否必填、主键、值域、枚举、时间语义、版本、生产者/消费者、变更兼容性和错误处理。ETL 在入口尽可能验证这些不变量，并把无法解析的输入隔离。当前项目只实现了最小的对象和 `record_id` 契约，因此文档应把完整 schema validation 写成演进目标；不要用两个字段校验冒充全量业务 schema。

### 79. 数据质量问题如何反馈给上游？

quarantine 不是终点。每条坏记录都应关联 batch、source、规则 ID、字段路径、错误原因和样例 hash；质量报告按 source/版本/规则聚合，再通过 dashboard、告警或回写工单反馈。阈值需与业务协商，例如 schema valid rate 低于某线阻断下游或只标黄。这样从“发现脏数据”走到“闭环修复”，也是 DataOps 项目比一次性清洗脚本更完整的地方。

### 80. 如何对质量规则做灰度发布？

先将新规则以 observe-only 运行，记录命中但不阻断；和旧版本对比误报、漏报、影响批次与人工抽样，再逐步提升为 warning 或 blocking。每个审计结果必须记录规则版本，否则无法解释指标波动。对于 Agent 自动修复建议，更应先只生成报告、保留人工审批，不能让新规则直接改生产数据。

### 81. 你会怎样设计异常检测？

先区分 deterministic rule 与统计异常。确定性规则处理缺失、唯一性、引用完整性、值域等强约束；统计异常可按 source、日期、字段分桶，使用 z-score、IQR、季节性基线或 Isolation Forest，并将样本、阈值、训练窗口记录下来。异常分数应成为审计结果的一部分，由 SQL 精确聚合和检索规则解释。当前版本未集成统计模型，所以只能说明设计方案与验证计划。

### 82. 如何防止 SQL 结果泄露敏感数据？

在数据层给表、列和行做权限范围；在 SQL allow-list 之外增加 column allow-list、行级 filter、脱敏视图、最大行数和结果字段审计。对 Agent 还应按用户身份强制 metadata/tenant filter，而不是让模型决定。当前 demo 的 records 是简化表，主要展示执行隔离；真实含 PII 的系统必须加认证、审计保留期、加密与访问复核。

### 83. 如何处理多租户？

每条记录、批次、任务、trace 和知识 chunk 都要携带 tenant ID；所有 repository 与 retriever 查询将 tenant predicate 作为不可移除的服务端条件，而不是可选 filter。Redis key/stream 也要 namespace 隔离，缓存 key 包含 tenant 和数据版本。为减少越权风险，工具层从用户身份推导 tenant，模型永远不能自填 tenant ID。当前 demo 未实现租户体系，应明确为生产化差距。

### 84. 如何设计任务取消？

取消需要持久化状态、worker 协作检查点和幂等清理：API 将任务标为 cancel_requested，worker 在每个可中断阶段检查，停止后写 cancelled 终态并决定是否 ACK。已经发生的写操作要么设计为事务回滚，要么补偿，不能假装“取消就像没执行过”。当前审计是短同步质量计算，未实现 cancel；以后在长批任务、外部调用和多步骤 Agent 中才是必要能力。

### 85. 什么情况下应使用 background task，什么情况下应使用独立 worker？

FastAPI BackgroundTasks 适合短、低风险、同进程可完成的工作，便于本地 demo；但应用重启、横向扩容和长时间计算都会使它不可靠。独立 worker + Redis Streams/其他队列适合耗时审计、可恢复任务和多消费者，但当前原生 DuckDB 文件不能由 API 与独立 worker 并发写入。当前本地/Redis queue 都由 API 所在进程后台 drain；上线若要独立 worker，先迁移 TaskStore 到 PostgreSQL 等共享写入存储，或实现严格单写入者架构，再加入健康检查、并发/重试配置和进度监控。

### 86. 如果 Redis 宕机，系统应该怎样降级？

不能无声降级成“任务已完成”。如果 Redis 只用于外部队列，API 可以先把任务持久化为 pending_publish，再返回受理状态并由 outbox publisher 重试；如果 Redis 用于 session state，要定义是拒绝新变更操作、走单机 fallback，还是只允许只读操作。降级策略取决于一致性要求，必须在 API 响应与 trace 中可见。当前本地模式是显式选用 InMemoryTaskQueue，而不是在运行时偷偷切换。

### 87. 如果 Elasticsearch 不可用，知识回答怎么办？

不要把错误文档当作“没有结果”。可以返回明确的 retriever unavailable，让 Agent 继续完成 SQL/审计事实部分并说明背景知识暂不可得；也可在低风险情况下使用本地只读索引/缓存做有限降级。无论哪种都必须标注答案缺少检索证据。当前未配置 ES 时应用使用本地空 retriever，适合开发测试；真实服务需要 health check、超时、熔断和索引版本监控。

### 88. 如何做成本控制？

先从确定性路径减少不必要的 LLM 调用：数值问题直走 SQL，任务进度直读 store，精确 ID 直查，只有解释性问题进入检索/模型。再控制检索候选、上下文预算、模型路由、缓存与重试次数。每次调用记录 token、延迟、成本估算和结果质量，按工具/用户/任务聚合。当前项目没有模型调用和 token telemetry，因此只能说明成本控制设计，不能报告节省比例。

### 89. 如何评价 Agent 的成功率？

不能只看用户是否满意。应定义任务级成功：选对工具、参数有效、执行完成、结果与 SQL ground truth 一致、引用规则相关、未越权、在预算内完成。分开统计 route accuracy、tool-call validity、SQL correctness、retrieval Recall、任务完成率、重试率、P95、成本和人工接管率。测试集应覆盖正常、模糊、恶意和失败服务场景。当前 MVP 的强项是确定性工具单测，不应声称已有端到端 LLM benchmark。

### 90. 如何写一个有效的 Agent evaluation 集？

从真实任务/故障中匿名化采样，给每个样例标注意图、允许工具、预期 SQL/结果、应引用的知识、禁止动作和成功判定。至少覆盖结构化事实、定义解释、多步审计、无结果、权限拒绝、超时和注入攻击。数据集按版本管理，防止 prompt 或规则变化后不知回归在哪里。每次模型、schema、retriever 或路由改动都跑同一套集，并分析失败类别而不是只报总分。

### 91. 如何处理模型幻觉？

把模型放在“解释和编排”层，而不是事实源。要求它引用 SQL 工具结果或检索 chunk，找不到证据就回答“不确定/需运行工具”；服务端禁止模型直接写数据库或绕过审批。对最终答案可做事实验证：数字必须来自结果对象，文档引用必须在检索集合内。项目尚无模型链路，但它的 SQL、TaskStore 与 retrieval 边界正是为减少幻觉可造成的实际伤害。

### 92. 如果要加入自动修复（repair pipeline），如何控制风险？

第一阶段只生成修复建议和受影响行清单；第二阶段让用户确认后生成可审查的 patch 或 staging 表；第三阶段再由带权限的 worker 执行可回滚变更。每次修复绑定 rule version、输入 batch、前后 hash、操作者与 trace，并可重跑验证。绝不让模型直接在事实表上执行任意 UPDATE。当前项目不实现自动修复，因此可把这道题作为安全设计能力展示。

### 93. 如何选择 LLM provider 或模型？

基于任务而非品牌：工具调用 JSON 稳定性、上下文窗口、中文理解、延迟、价格、数据合规、可观测性与私有部署要求。用固定 eval 集比较 route/tool 参数正确率、复杂计划完成率、P95 和单任务成本；低风险简单分类可用小模型，复杂解释才升级。Runtime 要把 provider client 放在 adapter 后，避免业务代码耦合某个 SDK。当前项目没有 provider 绑定，正是为了保留这个选择空间。

### 94. 你会如何设计多 Agent？为什么现在不急着做？

只有当单 Agent 的上下文、权限或并行工作确实成为瓶颈时才拆分，例如一个 data inspector、一个 SQL analyst、一个 knowledge researcher，由 coordinator 控制共享 state 和最终输出。每个 agent 要有明确输入输出 schema、资源预算、权限和 trace，否则多 Agent 只会放大循环调用与调试难度。当前项目优先打磨单一工具 runtime，是因为可靠队列、状态与评估比增加 agent 数量更基础。

### 95. 你会如何回答“这个项目最大的技术难点是什么”？

我会选择“在保持确定性数据处理的前提下补齐异步与安全边界”。具体包含批次幂等与记录去重的区分、持久化任务终态与 Streams ACK 的顺序、受限 SQL 防绕过、以及不把当前状态交给 RAG。回答时给出一个 bug/测试例子，例如源库宏伪装成允许函数时，只有在隔离 sandbox 执行才能避免副作用；再说明我如何用回归测试固定这个不变量。

### 96. 项目中有哪些失败或不足？

我会主动列三类：第一，核心质量规则目前只有最小指标，尚未覆盖完整业务契约；第二，Redis/ES 适配器的真实集群 E2E、lease/死信/监控需要继续验证，且多进程 worker 前必须调整 DuckDB 拓扑；第三，Runtime 原语尚未接入真实 LLM 或 VerbalVis 主链路。MCP 已有只读 stdio server，但没有认证、会话和变更工具。然后说明补齐顺序：先做真实服务与恢复测试，再统一 trace/权限/资源治理，最后接入模型和评估。能准确说出边界，反而体现工程判断。

### 97. 你从这个项目学到了什么？

最重要的认识是：Agent 项目的可靠性来自系统边界，不来自 prompt 的复杂度。结构化事实、任务状态、知识检索、模型上下文和副作用操作有不同的一致性要求；强行统一到向量库或聊天记录一定会出错。其次是测试要覆盖失败时序，例如发布失败、连接关闭、晚到消息和 SQL 绕过，而不只是正常 API 返回 200。

### 98. 如果给你两周继续做，你会怎样排优先级？

第 1 周先让现有声明可被真实环境证据支撑：做 Redis/ES E2E、崩溃恢复、lease/死信和 CI；若要独立 Redis worker，先把 TaskStore 迁移至 PostgreSQL 等共享写入存储，或落地严格单写入者架构，不能直接让两个进程写同一 DuckDB 文件。随后补 LLM token/cost、资源预算和跨进程 trace。第 2 周接入一个结构化 tool-calling 模型、实现统一 dispatcher/permission、建立小型 evaluation 集和基准报告。不会先做 GraphRAG 或多 Agent，因为它们无法弥补队列可靠性、权限和评估缺口。

### 99. 如果面试官要求现场 demo，你如何安排？

我会用一份固定、可公开的样例：先导入包含一条有效、一条重复和一条坏记录的 JSON/CSV；展示 batch retry 不重复；创建审计任务并查看进度与质量报告；运行安全的聚合 SQL，再故意提交危险 SQL 看拒绝；最后检索一条规则并展示 trace 脱敏。若现场没有 Docker/网络，就运行本地测试路径并明确 ES/Redis 是可选演示，不把无法启动的外部服务藏起来。

### 100. 你会如何收尾并真正发布这个项目？

我会将发布当作一次可复现验收：冻结依赖、运行全部测试、保存 commit SHA 与输出；在干净环境走两分钟 demo；真实启动 Redis/ES 后再跑 E2E；补基准报告和架构决策记录，并复核已提供的 MIT LICENSE、SECURITY、贡献指南与 CI。发布说明分为“已验证”“可选适配器”“下一步”三栏，中文/英文 README 都避免无证据数字。只有在远端仓库、默认分支保护和 CI 都确认后才 push/tag；GitHub 发布不是复制代码，而是把可复现证据一起交付。

## 6. 发布前最终替换清单

在把这份文档用于简历或 GitHub 前，逐项替换或核验：

- `【待实测】` 的性能、通过数、日期、机器配置和 commit SHA；
- Redis Streams、Elasticsearch 与 Docker Compose 是否在真实服务中完成 E2E；若要独立 worker，是否已先迁移 TaskStore 或实现单写入者架构；
- 只读 MCP Server 是否仍可启动和发现五个工具；LLM planner、Redis StateStore、ContextManager 若未接入请求执行链，仍保留“接口 / 后续”措辞；
- 数据样例、trace、数据库文件、环境变量和历史 Git 提交是否不含敏感信息；
- 许可证与作者署名是否符合你的发布意图；
- README 的启动命令是否在全新 clone 的机器上复现。

这份项目最有说服力的地方不是技术名词数量，而是你能清楚解释：**哪些事实已经由测试和代码证明，哪些是有明确接口的下一步，以及为什么不能把它们混为一谈。**
