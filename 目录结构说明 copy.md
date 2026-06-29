# VerbalVis 项目目录结构说明

VerbalVis 是一个**语音优先的可视化数据分析助手**，针对 Olist 巴西电商数据集（订单、评价、地理、品类、配送、营收）。用户通过语音与系统对话，由 OpenAI Realtime API 驱动模型理解意图，并调用后端工具来过滤数据、高亮视图、新增/删除图表，前端仪表盘随之实时更新。

整体架构是 **Python(FastAPI) 后端 + Vue3 前端**，两者通过 WebSocket 通信；后端再与 OpenAI Realtime API 建立第二条 WebSocket，充当桥接层。

> 说明：本文档不涉及 `记录.md`、`项目实现描述.md`、`zzz的baseline和摘要，introduce.txt`、`frontend/main.tex` 四个文件。

---

## 顶层目录

```
VerbalVis2/
├── .gitignore                  Git 忽略规则
├── .vscode/                    VS Code 工作区配置
│   └── settings.json
├── backend/                    Python 后端（FastAPI + DuckDB + Realtime 桥接）
├── frontend/                   Vue3 前端（语音交互 + Vega-Lite 仪表盘）
└── image/                      文档/记录用的截图素材（非代码）
```

### `.gitignore`
Git 忽略规则。排除操作系统/编辑器临时文件、Python 缓存与虚拟环境、后端密钥与日志（`backend/.env`、`backend/logs/`）、以及 Node 依赖与前端构建产物（`node_modules/`、`dist/`）。

### `.vscode/settings.json`
VS Code 工作区设置，指定 Python 环境与包管理器使用 conda（`ms-python.python:conda`），统一团队开发环境。

---

## backend/ —— 后端

后端职责：加载数据、维护仪表盘状态、向模型暴露工具、桥接前端与 OpenAI Realtime API。

```
backend/
├── .env                请求密钥/配置（被 .gitignore 忽略，不入库）
├── requirements.txt    Python 依赖清单
├── main.py             FastAPI 入口，WebSocket 端点
├── realtime.py         Realtime API 桥接核心（最大模块）
├── tools.py            工具层：schema、执行、仪表盘状态
├── db.py               DuckDB 数据层
├── prompts.py          系统提示词
├── data/               原始数据集
└── logs/               运行期生成的会话日志（被忽略，不入库）
```

### `backend/main.py`（约 56 行）
FastAPI 应用入口。创建 app、配置 CORS（允许所有来源便于本地开发）；在 `startup` 事件中调用 `initialize_db()` 加载 DuckDB；暴露 `/health` 健康检查；核心是 `/ws` WebSocket 端点——每个客户端连接生成一个 `session-xxxx` 会话 ID，实例化 `RealtimeSession` 并启动，处理断连与异常。

### `backend/realtime.py`（约 800 行，核心模块）
前端 WebSocket 与 OpenAI Realtime WebSocket 之间的桥接管理器（`RealtimeSession`）。负责：
- 建立并维护到 OpenAI Realtime API 的连接，下发 `session.update`（注入系统提示词与工具 schema）。
- 双向转发：把前端的麦克风音频上行给模型，把模型返回的语音、转写文字下行给前端。
- 工具调用编排：接收模型的 function call，调用 `execute_tool` 执行，回传结果并注入最新仪表盘上下文；在工具为 `filter_data` / `append_visual` / `delete_visual` 时推送 `views_update` 让前端刷新。
- 打断（barge-in）与"陈旧调用"处理：用户中途说话时取消过期的响应/工具结果，避免错乱。
- 结构化事件日志：按会话写入 `logs/` 下带时间戳的目录，终端只打印关键事件。

### `backend/tools.py`（约 760 行）
工具层，定义模型可调用的能力并维护仪表盘运行期状态（`active_filters`、`views`、`highlighted_view` 等）。包含：
- **基础视图定义** `BASE_VIEWS_DEFS`：4 个初始图表（月度订单趋势、评分分布、各州订单、品类营收 Top15）及 `init_views()` 初始化。
- **工具 schema** `TOOL_SCHEMAS`：
  - `filter_data` — 对全局数据集加/清过滤条件，所有视图联动更新。
  - `highlight_visual` — 高亮某个视图、可选淡化其余视图。
  - `append_visual` — 新建图表并追加到仪表盘。
  - `delete_visual` — 按 `view_id` 删除指定视图。
- **执行函数** `execute_tool()` 及各 `_exec_*` 实现，含字段/算子校验、SQL 聚合推断（`_infer_agg`、`_decide_table`）、散点采样（`_scatter_data`）。
- **状态/上下文**：`_refresh_all_views`、`_compute_view_stats`（每个视图的摘要统计）、`rebuild_context` / `context_text`（注入给模型的紧凑上下文）、`get_views_for_frontend`（前端渲染数据）。
- **实验日志** `log_tool_call`：把每次工具调用与仪表盘快照写入 jsonl。

### `backend/db.py`（约 334 行）
DuckDB 数据层。把 Olist 的多张 CSV 读入内存数据库，构建两张事实表：`fact_order`（每个已交付订单一行，用于订单粒度视图）与 `fact_item`（每个订单条目一行，用于品类/商品粒度视图，正确计算 item 级营收）。对外提供 `get_connection`、`initialize_db`，以及供工具层调用的查询辅助：`build_where`（过滤条件转 SQL）、`resolve_column`（字段名映射到物理列）、`aggregate_query`、`stats_query`、`total_rows`，并声明可过滤字段集 `FIELDS` 与算子集 `OPERATORS`。

### `backend/prompts.py`（约 118 行）
系统提示词模块。定义 VerbalVis 的角色设定（语音优先的数据分析助手）、语音成本控制规则（回答尽量 1–2 句、不复述内部推理）、工具使用纪律（用工具改动仪表盘而非凭空描述）。提供 `build_system_prompt` 供 `realtime.py` 在会话初始化时组装最终提示词。提示词刻意保持精简，以提升长会话中的 prompt-cache 命中率、降低重复输入成本。

### `backend/requirements.txt`
Python 依赖清单：`fastapi`、`uvicorn[standard]`、`websockets`、`duckdb`、`python-dotenv`。

### `backend/.env`
环境变量文件，存放 OpenAI API Key 等密钥（已被 `.gitignore` 忽略，不会提交到仓库）。

### `backend/data/`
原始数据集，包含 Olist 巴西电商公开数据集的 9 个 CSV 文件与品类名翻译表，以及绘制地图用的 `brazil-states.geojson`：

```
data/
├── brazil-states.geojson                     巴西各州地理边界
└── olist/
    ├── olist_customers_dataset.csv           客户
    ├── olist_geolocation_dataset.csv         地理位置
    ├── olist_order_items_dataset.csv         订单条目
    ├── olist_order_payments_dataset.csv      支付
    ├── olist_order_reviews_dataset.csv       评价
    ├── olist_orders_dataset.csv              订单
    ├── olist_products_dataset.csv            商品
    ├── olist_sellers_dataset.csv             卖家
    └── product_category_name_translation.csv 品类名（葡→英）翻译
```

### `backend/logs/`
运行时由 `realtime.py` / `tools.py` 生成的会话日志目录（按会话分目录、jsonl 工具调用记录），用于实验分析。被 `.gitignore` 忽略，不入库。

---

## frontend/ —— 前端

Vue 3 + Vite + Pinia + Vega-Lite 的单页应用。负责采集麦克风音频、播放模型语音、通过 WebSocket 与后端通信，并把仪表盘视图渲染为 Vega-Lite 图表。

```
frontend/
├── index.html              HTML 入口
├── package.json            依赖与脚本
├── package-lock.json       依赖锁定文件
├── vite.config.js          Vite 配置（含 WS 代理）
└── src/
    ├── main.js             应用启动入口
    ├── App.vue             根组件
    ├── specFactory.js      Vega-Lite 图表 spec 工厂
    ├── components/
    │   ├── Dashboard.vue    仪表盘主界面
    │   └── ChartSlot.vue    单个图表卡片
    ├── composables/
    │   ├── useWebSocket.js  WebSocket 通信
    │   └── useAudio.js      音频采集与播放
    └── stores/
        └── dashboard.js     Pinia 全局状态
```

### `frontend/index.html`
HTML 入口模板，提供 `#app` 挂载点并加载 `/src/main.js`。

### `frontend/package.json`
前端依赖与脚本声明。脚本：`dev`（启动 Vite 开发服务器）、`build`（生产构建）、`preview`。依赖：`vue`、`pinia`（状态管理）、`vega`/`vega-lite`/`vega-embed`（图表渲染）；开发依赖 `vite` 与 `@vitejs/plugin-vue`。

### `frontend/package-lock.json`
npm 依赖版本锁定文件，保证安装可复现（由 npm 自动生成）。

### `frontend/vite.config.js`
Vite 构建/开发配置。启用 Vue 插件，开发服务器监听 5173 端口，并把 `/ws`（WebSocket）代理到 `ws://localhost:8000`、把 `/upload-recording` 代理到后端，避免本地跨域问题。

### `frontend/src/main.js`（7 行）
应用启动入口。创建 Vue 应用、注册 Pinia，并把根组件 `App` 挂载到 `#app`。

### `frontend/src/App.vue`
根组件。仅渲染 `Dashboard` 组件，并定义全局基础样式（盒模型重置、页面背景）。

### `frontend/src/components/Dashboard.vue`（约 286 行）
仪表盘主界面。包含顶栏（标题、连接状态指示灯）、控制区（"按住说话"录音按钮，支持空格键/麦克风 push-to-talk）、过滤条件展示、转写文字区，以及由多个 `ChartSlot` 组成的图表网格。它把 `useWebSocket`、`useAudio` 与 Pinia store 串联起来，驱动整体交互。

### `frontend/src/components/ChartSlot.vue`（约 113 行）
单个图表卡片组件。根据传入的 `view` 元数据调用 `specFactory` 生成 Vega-Lite spec，用 `vega-embed` 渲染到容器；监听高亮状态，对被高亮视图加边框、对其余视图做淡化（dimmed）处理；数据变化时重新渲染。

### `frontend/src/specFactory.js`（约 146 行）
Vega-Lite 图表 spec 工厂。`createSpec(view)` 按视图 ID 分派：4 个基础视图（趋势线、评分柱状、各州柱状、品类营收）各有专用 spec；其余动态视图（`append_visual` 新建的）由 `dynamicSpec` 按 `chart_type`（scatter/bar/line/histogram）与字段生成。数据通过 vega-embed 单独注入，spec 只描述图表结构。

### `frontend/src/composables/useWebSocket.js`（约 150 行）
WebSocket 通信组合式函数。连接后端 `/ws`，按消息类型分发：`init`/`views_update` 更新视图、`audio` 入队播放、`transcript` 累积转写、`tool_result` 交给 store 处理高亮/过滤、`response_done`/`speech_started` 控制播放与打断等。同时负责把前端音频/控制消息发送给后端。

### `frontend/src/composables/useAudio.js`（约 206 行）
音频组合式函数。基于 Web Audio API（24kHz PCM16，与 Realtime API 对齐）：采集麦克风音频并以 base64 PCM 回调上行；接收后端下行音频块入队、按时间线顺序播放；管理录音/播放状态、设备就绪与打断停止。

### `frontend/src/stores/dashboard.js`（约 90 行）
Pinia 全局状态仓库。集中保存 `views`（视图列表）、`activeFilters`、`highlightedViewId`、转写记录、连接状态等，并提供 actions：`initViews`、`updateViews`（整列表替换，自动移除被删视图并清理失效高亮）、`appendView`、`highlightView`、`handleToolResult`（按工具结果更新高亮/过滤）、`addTranscript`。是前端各组件共享数据的单一真实来源。

---

## image/
存放文档与记录中引用的截图等图片素材，不参与程序运行。

---

## 一次典型交互的数据流

1. 用户在 `Dashboard.vue` 按住录音 → `useAudio.js` 采集 PCM 音频。
2. `useWebSocket.js` 经 `/ws` 把音频上行给后端。
3. `realtime.py` 转发给 OpenAI Realtime API；模型理解后发起工具调用。
4. `tools.py` 执行工具（过滤/高亮/新增/删除），更新 `db.py` 查询出的视图数据与状态。
5. `realtime.py` 把工具结果与 `views_update` 下行给前端，并把模型语音回传。
6. 前端 store 更新 → `ChartSlot.vue` 用 `specFactory.js` 重新渲染图表，`useAudio.js` 播放语音回答。
