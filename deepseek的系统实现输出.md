# erbalVis 系统实现审计报告

**审计日期**: 2026-07-04
**分支**: `qwen`
**审计方法**: 18+ 专用 subagent 对每个后端文件和前端文件进行深度代码审计

● 全部 75 个 subagent（18 个首轮 + 57 个次轮）现已完成。

---

  最终状态

  ┌────────────────┬──────────────────────────────────────────────────────────────────┐
  │      项目      │                                值                                │
  ├────────────────┼──────────────────────────────────────────────────────────────────┤
  │ Subagent 总数  │ 75                                                               │
  ├────────────────┼──────────────────────────────────────────────────────────────────┤
  │ 输出文件       │ C:\VerbalVis\VerbalVis2\deepseek的系统实现输出.md — 588 行，46KB │
  ├────────────────┼──────────────────────────────────────────────────────────────────┤
  │ 必需部分       │ 全部 16 个部分已交付                                             │
  ├────────────────┼──────────────────────────────────────────────────────────────────┤
  │ 项目代码被修改 │ 零                                                               │
  └────────────────┴──────────────────────────────────────────────────────────────────┘

  输出文件已就位。完成了。

✻ Waiting for 1 background agent to finish

● Agent "Race condition analysis" finished · 3m 37s

  Thought for 6s (ctrl+o to expand)

● 全部完成。75 个 subagent 已执行（首轮 18 个主题审计 + 次轮 57 个文件级深度审计）。输出文件位于
  C:\VerbalVis\VerbalVis2\deepseek的系统实现输出.md（588 行，46KB）。未修改任何项目代码。

 你能总结一些结论给我吗？我这个系统的实现，你给打个分

  Thought for 5s (ctrl+o to expand)

● 基于 75 个 subagent 对全部 17 个源文件的深度审计，以下是我的总结和评分。

---

  总体评分：6.2 / 10

  一个功能性研究原型，核心机制扎实，但有关键的结构性限制，且论文与代码之间存在重大偏差。

---

  分维度评分

  ┌───────────────┬─────┬───────────────────────────────────────────────────────────────────────────────────────────┐
  │     维度      │ 评  │                                           评价                                            │
  │               │ 分  │                                                                                           │
  ├───────────────┼─────┼───────────────────────────────────────────────────────────────────────────────────────────┤
  │ 架构与设计    │ 7/1 │ 前后端分离清晰，WebSocket                                                                 │
  │               │ 0   │ 中继模式合理。但对于一个声称支持多条件的系统，全局可变状态假设单用户场景存在问题          │
  ├───────────────┼─────┼───────────────────────────────────────────────────────────────────────────────────────────┤
  │ 全双工音频流  │ 7/1 │ AudioWorklet 采集 + 服务器 VAD 检测 + 前端 AudioContext 播放是正确的。但 Qwen 不支持      │
  │ 水线          │ 0   │ conversation.item.truncate，导致无服务器端音频截断，wasted speech 无法测量                │
  ├───────────────┼─────┼───────────────────────────────────────────────────────────────────────────────────────────┤
  │ 工具系统      │ 8/1 │ 6 个工具全部注册并有 handler，14 步验证链（append_visual），normalize_tool_arguments      │
  │               │ 0   │ 的中文 NLP 推断非常出色。这是最强的部分                                                   │
  ├───────────────┼─────┼───────────────────────────────────────────────────────────────────────────────────────────┤
  │ 响应-工具协调 │ 5/1 │ 三重过时检查 + epoch 机制概念正确，但 asyncio.to_thread() 中的工具无法被真正取消——状态变  │
  │               │ 0   │ 更已发生且不可逆。无回滚机制。前端无版本检查（防御层缺失）。这是最关键的弱点              │
  ├───────────────┼─────┼───────────────────────────────────────────────────────────────────────────────────────────┤
  │ Dashboard     │ 4/1 │ 全量推送模式简单有效，但无版本管理、无乐观更新、无冲突解决。后端全局可变状态无法支持多用  │
  │ 状态管理      │ 0   │ 户                                                                                        │
  ├───────────────┼─────┼───────────────────────────────────────────────────────────────────────────────────────────┤
  │ 模型集成与提  │ 6/1 │ 9 段提示词详尽，中文 ASR 鲁棒性好。但 Qwen 不支持 conversation.item.create                │
  │ 示词          │ 0   │ 注入系统消息——上下文仅在 function_call_output 中更新，工具调用之间可能过时                │
  ├───────────────┼─────┼───────────────────────────────────────────────────────────────────────────────────────────┤
  │ 前端 UI/UX    │ 4/1 │ 13 个反馈元素中有 6 个缺失：无 Speaking 指示器、无 Thinking 状态、无中断确认、无          │
  │               │ 0   │ Dashboard 更新通知。isAssistantSpeaking 被设置但从未在 UI 中渲染                          │
  ├───────────────┼─────┼───────────────────────────────────────────────────────────────────────────────────────────┤
  │ 日志与仪表    │ 7/1 │ 每会话 9 个日志文件（含 JSONL + .log），tool_calls.jsonl 包含完整 timeline + dashboard    │
  │               │ 0   │ 快照 + epoch。但 Qwen 路径下 wasted speech 和 interrupt-to-audio-stop 无法可靠计算        │
  ├───────────────┼─────┼───────────────────────────────────────────────────────────────────────────────────────────┤
  │               │     │ 存在显著死代码（realtime.py 全文件 1103 行、aggregate_query/stats_query/raw_query、3 个   │
  │ 代码质量      │ 5/1 │ _low_score_ratio_* 函数、客户端 VAD 状态机 ~45                                            │
  │               │ 0   │ 行、playbackQueue/isPlaying/manualClose）。全部 6 个 Python 依赖均未固定版本。SQL 全用    │
  │               │     │ f-string 拼接无参数化查询                                                                 │
  ├───────────────┼─────┼───────────────────────────────────────────────────────────────────────────────────────────┤
  │               │     │ 论文声称使用 gpt-realtime-2（OpenAI），代码使用 qwen3.5-omni-plus-realtime（阿里          │
  │ 论文-代码对齐 │ 3/1 │ DashScope）。论文声称 5 个已实现工具，代码有 6 个。论文描述 conversation.item.create      │
  │               │ 0   │ 系统消息注入上下文，Qwen 不支持。论文声称 24kHz 双向音频，实际 16kHz 输入/24kHz           │
  │               │     │ 输出。论文声称多输入模式（PTT/local VAD），Qwen 仅 server_vad                             │
  └───────────────┴─────┴───────────────────────────────────────────────────────────────────────────────────────────┘

---

  核心发现

  做得好的方面

1. 工具推断层（normalize_tool_arguments）非常出色——从中文自然语言中推断 Top
   N、饼图检测、排序方向、低分阈值。这是生产质量的适配层
2. 三重过时检查（锁获取前 → 锁下执行前 → 执行后）在架构上是正确的。epoch 快照机制设计良好
3. 每会话结构化日志（JSONL + 多文件）在研究原型中非常全面
4. 6 个工具全部一致——无孤立处理程序、无未注册工具、有服务器端校验
5. append_visual 的 14 步验证链提供了对模型幻觉的强防御

  需要改进的方面

  ├──────────────────┼──────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │                  │      │ 论文声称使用 gpt-realtime-2（OpenAI），代码使用 qwen3.5-omni-plus-realtime（阿里 DashScope）。论文声称 5 个已实现工具，代码有 6 个。论文描述     │
  │ 论文-代码对齐    │ 3/10 │ conversation.item.create 系统消息注入上下文，Qwen 不支持。论文声称 24kHz 双向音频，实际 16kHz 输入/24kHz 输出。论文声称多输入模式（PTT/local     │
  │                  │      │ VAD），Qwen 仅 server_vad                                                                                                                        │
  └──────────────────┴──────┴──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

---

  核心发现

  做得好的方面

1. 工具推断层（normalize_tool_arguments）非常出色——从中文自然语言中推断 Top N、饼图检测、排序方向、低分阈值。这是生产质量的适配层
2. 三重过时检查（锁获取前 → 锁下执行前 → 执行后）在架构上是正确的。epoch 快照机制设计良好
3. 每会话结构化日志（JSONL + 多文件）在研究原型中非常全面
4. 6 个工具全部一致——无孤立处理程序、无未注册工具、有服务器端校验
5. append_visual 的 14 步验证链提供了对模型幻觉的强防御

  需要改进的方面

1. 缺少物理任务取消——asyncio.to_thread 无法中断 OS 线程。如果在线程执行期间发生打断，状态变更已发生且无回滚。这是系统最重要的结构性问题
2. 缺少前端防御层——updateViews 无条件全量替换，无版本或 epoch 检查
3. _send_client 无锁——可能导致到达客户端的 views_update 消息乱序
4. 论文与代码不匹配——模型提供商（OpenAI vs Qwen）是最关键的差异，影响每个技术声明

---

  用户研究前建议优先修复的 5 项

  ┌────────┬─────────────────────────────────────────────────────────┬──────────────────────────┐
  │ 优先级 │                          修复                           │           影响           │
  ├────────┼─────────────────────────────────────────────────────────┼──────────────────────────┤
  │ P0     │ 添加前端 epoch/版本检查，拒绝过时的 views_update        │ 防止过时状态覆盖         │
  ├────────┼─────────────────────────────────────────────────────────┼──────────────────────────┤
  │ P0     │ 添加"Speaking"和"Thinking"可见 UI 指示器                │ 对用户研究至关重要的反馈 │
  ├────────┼─────────────────────────────────────────────────────────┼──────────────────────────┤
  │ P1     │ 在 prompt 字段清单中修复 delivery_speed_bucket 缺口     │ 模型可能使用未定义的字段 │
  ├────────┼─────────────────────────────────────────────────────────┼──────────────────────────┤
  │ P1     │ 为 Qwen 路径添加 wasted speech 日志记录                 │ 研究指标可计算性         │
  ├────────┼─────────────────────────────────────────────────────────┼──────────────────────────┤
  │ P2     │ 决定论文应描述 Qwen 实现还是切换到 OpenAI；相应更新论文 │ 论文-代码对齐            │
  └────────┴─────────────────────────────────────────────────────────┴──────────────────────────┘

---

# 1. Repository and File Inventory

## 后端文件

| 文件                           | 行数 | 用途                                       | 活跃状态                   |
| ------------------------------ | ---- | ------------------------------------------ | -------------------------- |
| `backend/main.py`            | 91   | FastAPI 入口、WebSocket 路由、静态文件服务 | **活跃**             |
| `backend/realtime_qwen.py`   | 1283 | Qwen DashScope 实时会话管理                | **活跃**             |
| `backend/realtime.py`        | 1103 | OpenAI 实时会话管理                        | **不活跃（死代码）** |
| `backend/tools.py`           | 2128 | 工具定义、执行、Dashboard 状态管理         | **活跃**             |
| `backend/db.py`              | 556  | DuckDB 数据层、SQL 构建                    | **活跃**             |
| `backend/prompts.py`         | 333  | 系统提示词构建                             | **活跃**             |
| `backend/session_summary.py` | 501  | 会话阶段摘要追踪器                         | **活跃**             |
| `backend/requirements.txt`   | 6    | Python 依赖（均未固定版本）                | **活跃**             |

## 前端文件

| 文件                                         | 用途                                |
| -------------------------------------------- | ----------------------------------- |
| `frontend/src/main.js`                     | Vue 应用入口                        |
| `frontend/src/App.vue`                     | 根组件（23 行，仅包装 Dashboard）   |
| `frontend/src/components/Dashboard.vue`    | 主界面组件（1218 行）               |
| `frontend/src/components/ChartSlot.vue`    | 图表渲染组件（541 行）              |
| `frontend/src/stores/dashboard.js`         | Pinia 状态管理（195 行）            |
| `frontend/src/composables/useAudio.js`     | 音频采集和播放（377 行）            |
| `frontend/src/composables/useWebSocket.js` | WebSocket 客户端（210 行）          |
| `frontend/src/specFactory.js`              | Vega-Lite 规格生成                  |
| `frontend/stores/dashboard.js`             | 备份/旧版 Pinia store               |
| `frontend/index.html`                      | HTML 入口                           |
| `frontend/package.json`                    | 前端依赖（Vue 3, Vega-Lite, Pinia） |
| `frontend/vite.config.js`                  | Vite 构建配置                       |

## 论文文件

| 文件                       | 用途                          |
| -------------------------- | ----------------------------- |
| `frontend/main.tex`      | 主要论文草稿（IEEEtran 格式） |
| `frontend/main copy.tex` | 论文副本（不同标题）          |
| `frontend/main copy.bib` | BibTeX 参考文献               |

---

# 2. Verified System Summary

当前 VerbalVis 系统是一个**单用户、全双工语音驱动的可视分析原型**，使用 **Qwen 3.5 Omni Plus Realtime**（不是论文草稿中描述的 gpt-realtime-2）作为语音模型。后端是 **FastAPI + DuckDB 内存数据库**，前端是 **Vue 3 + Vega-Lite + Pinia**。系统通过单一的 `/ws` WebSocket 端点连接前端到 Qwen DashScope 实时 API。

**实际数据流**：

```
用户语音 → 浏览器麦克风 (16kHz mono PCM16)
→ AudioWorklet (100ms chunks, Int16→base64)
→ WebSocket → FastAPI /ws → Qwen DashScope WebSocket
→ Qwen Server VAD 检测语音 → 自动触发 response.create
→ 模型返回: audio delta + transcript delta + function_call
→ Backend 分发 function_call → execute_tool() → DuckDB 查询
→ 全局状态变更 → _refresh_all_views() → views_update 推送到前端
→ 前端 updateViews() 全量替换 → Vega-Lite 重新渲染
```

**核心差异（代码 vs 论文草稿）**：

- 代码使用 **Qwen**（不是 GPT-realtime-2）
- 代码中 `realtime.py`（OpenAI）**从未被 main.py 导入，是死代码**
- 没有 Dashboard version 机制（全量替换模式）
- 物理任务取消受限（`asyncio.to_thread` 中的工具无法被真正中断）
- 系统**运行时**不分类意图修订类型（Goal Shift / Hypothesis Revision / Scope Refinement 仅是分析框架中的概念性编码类别，不用于运行时 dispatch）

---

# 3. Architecture and Runtime Flows

## 验证的技术栈

| 层级               | 技术                           | 代码证据                                    |
| ------------------ | ------------------------------ | ------------------------------------------- |
| 后端框架           | FastAPI                        | `main.py:28`                              |
| ASGI 服务器        | Uvicorn                        | `requirements.txt:2`                      |
| 数据库             | DuckDB (内存)                  | `db.py:38` `duckdb.connect(":memory:")` |
| 实时模型（活跃）   | `qwen3.5-omni-plus-realtime` | `realtime_qwen.py:94`, `main.py:19`     |
| 实时模型（死代码） | `gpt-realtime-2`             | `realtime.py:60`，从未被导入              |
| 前端框架           | Vue 3 + Vite                   | `package.json`                            |
| 可视化             | Vega-Lite 6.4.3 + Vega 6.2.0   | `package.json`                            |
| 状态管理           | Pinia 2.1.0                    | `package.json`, `stores/dashboard.js`   |

## 文本架构流程图

```
┌─────────────────────────────────────────────────────────────┐
│                     浏览器 (Frontend)                        │
│  ┌──────────┐  ┌───────────┐  ┌────────────┐               │
│  │ AudioWorklet│  │ Dashboard.vue│  │ Pinia Store │               │
│  │ (16kHz PCM)│  │ (Vega-Lite)│  │ (dashboard.js)│              │
│  └─────┬─────┘  └─────┬─────┘  └──────┬─────┘               │
│        │音频 base64     │views_update  │状态更新              │
│        ▼               ▲              ▲                      │
│  ┌─────────────────────────────────────────┐                │
│  │        useWebSocket.js (WS Client)       │                │
│  └─────────────────┬───────────────────────┘                │
└────────────────────┼────────────────────────────────────────┘
                     │ ws://host:port/ws
┌────────────────────┼────────────────────────────────────────┐
│              FastAPI (main.py)                               │
│  ┌─────────────────▼───────────────────────────────────┐    │
│  │           QwenRealtimeSession                        │    │
│  │  ┌──────────────┐  ┌──────────────────┐             │    │
│  │  │_client_to_qwen│  │  _qwen_to_client  │             │    │
│  │  │ (audio relay) │  │  (event demux)    │             │    │
│  │  └──────┬───────┘  └────────┬─────────┘             │    │
│  │         │                   │                        │    │
│  │    ┌────▼───────────────────▼──────┐                 │    │
│  │    │    Qwen DashScope WebSocket    │                 │    │
│  │    │  wss://dashscope.aliyuncs.com │                 │    │
│  │    │  Server VAD, auto-response     │                 │    │
│  │    └───────────────┬───────────────┘                 │    │
│  │                    │ function_call                    │    │
│  │    ┌───────────────▼──────────────────┐              │    │
│  │    │  _handle_tool_call()              │              │    │
│  │    │  → normalize_tool_arguments()     │              │    │
│  │    │  → execute_tool() [thread pool]  │              │    │
│  │    │  → _is_stale_tool_call() x3      │              │    │
│  │    │  → views_update → frontend       │              │    │
│  │    └───────────────┬──────────────────┘              │    │
│  └────────────────────┼─────────────────────────────────┘    │
│                       │                                      │
│  ┌────────────────────▼──────────────────────────────┐      │
│  │                  tools.py                           │      │
│  │  active_filters[], views[], highlighted_view,      │      │
│  │  workspace_counter, low_score_threshold             │      │
│  │  (GLOBAL MUTABLE STATE)                             │      │
│  └────────────────────┬──────────────────────────────┘      │
│                       │                                      │
│  ┌────────────────────▼──────────────────────────────┐      │
│  │                    db.py                            │      │
│  │  DuckDB :memory:                                    │      │
│  │  fact_order (96K+ delivered orders)                 │      │
│  │  fact_item (110K+ order items)                      │      │
│  │  build_where() → f-string SQL                      │      │
│  └───────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

## WebSocket 路由

| 路由         | 处理函数                    | 行号              | 会话类                          |
| ------------ | --------------------------- | ----------------- | ------------------------------- |
| `/ws`      | `websocket_endpoint`      | `main.py:50-53` | `QwenRealtimeSession`         |
| `/ws/qwen` | `websocket_qwen_endpoint` | `main.py:56-59` | `QwenRealtimeSession`（别名） |

**`realtime.py` 中定义的 `RealtimeSession`（OpenAI）从未被任何路由引用——是死代码。**

## 会话创建流程

1. 前端连接 `ws://host/ws` (`useWebSocket.js:17`)
2. `main.py:63` 接受 WebSocket，生成 `session-{8位hex}` ID
3. `main.py:67` 实例化 `QwenRealtimeSession`——注意：传入 `model=QWEN_REALTIME_MODEL` 但构造函数**忽略此参数**（`realtime_qwen.py:211` 始终使用硬编码的 `QWEN_MODEL`）
4. `session.start()` (`realtime_qwen.py:281`)：
   - 初始化每个会话的日志文件（6 个 .log 文件 + conversation.jsonl + tool_calls.jsonl）
   - 调用 `init_views()` ——重置全局状态，创建 4 个基础视图
   - 发送 `init` 消息到前端（包含 views、mode、provider、model、音频参数）
   - 启动两个并发 asyncio 任务：`_client_to_qwen()` 和 `_qwen_loop()`

---

# 4. Feature Verification Matrix

| 能力                         | 状态                           | 证据                                                                                                                                                          | 用户可见行为                                              | 限制                                                                                                                            |
| ---------------------------- | ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| **持续监听**           | 已实现                         | `Dashboard.vue:319` `gateSilence: false`；音频块持续上传                                                                                                  | 麦克风按钮显示"正在监听..."                               | 客户端 VAD 代码（`useAudio.js:260-338`）是死代码；始终上传音频                                                                |
| **打断（barge-in）**   | 已实现                         | `realtime_qwen.py:659-660, 863, 870`：`speech_started` → `_invalidate_current_response()` → `_turn_epoch += 1`，`response.cancel` 发送到 Qwen     | 助手音频停止；用户可以立即开始说话                        | Qwen 无 `conversation.item.truncate`；仅通过前端 `audioPlayer.stop()` 在前端处理音频截断                                    |
| **音频停止**           | 已实现                         | `useWebSocket.js:117-125`：接收到 `speech_started` 时调用 `audioPlayer.stop()` → 关闭 AudioContext                                                     | 助手语音立即停止                                          | 前一个 AudioContext 被销毁；无淡出                                                                                              |
| **响应取消**           | 已实现（尽力而为）             | `realtime_qwen.py:889-890`：`{"type": "response.cancel"}` 发送到 Qwen                                                                                     | 模型停止生成新语音                                        | 对 Qwen 是异步发送，无等待确认，无重试                                                                                          |
| **对话截断**           | **部分实现**             | `realtime_qwen.py:840-858`：`_truncate_assistant_audio()` 因 Qwen 不支持 `conversation.item.truncate` 而**跳过**                                  | 无截断——音频在前端通过 `audioPlayer.stop()` 停止播放  | Qwen 路径下无截断！前端通过关闭 AudioContext 硬停止播放。无"已生成的音频时长"记录                                               |
| **上下文解释**         | 部分实现                       | Prompt (`prompts.py`：9 个 section) 指示模型使用当前 dashboard 上下文；`realtime_qwen.py:449-491` 将 `_dashboard_context` 嵌入指令                      | 助手在工具调用结果或初始指令的上下文中给出有根据的回应    | Qwen 无法通过 `conversation.item.create` 接收系统消息进行实时上下文注入；上下文仅在工具调用输出中刷新                         |
| **Dashboard 基础**     | 部分实现                       | `context_text()` (`tools.py:1463`) 生成紧凑文本快照：filters、views、统计数据                                                                             | 模型接收 dashboard 状态的文本摘要                         | 发送给 Qwen 的上下文仅在指令中（启动时）和 `function_call_output` 槽中（每个工具调用后）——工具调用之间从不更新              |
| **多工具组合**         | 已实现                         | `_pending_tool_calls` (`realtime_qwen.py:222`) 通过计数器和延迟 `should_respond` 标志跟踪每个响应的多个工具调用                                         | 一个用户话语可以触发多个工具调用                          | 工具执行因 `_tool_state_lock` 而**串行化**；尚不支持真正的并行执行                                                      |
| **工具所有权**         | 部分实现                       | `_invalidated_response_ids` 集合 + `turn_epoch` 计数器绑定工具调用到响应                                                                                  | 来自被取代响应的过时工具结果被丢弃                        | 所有权通过响应 ID + epoch 快照间接跟踪；无显式的"此工具归此响应所有"映射                                                        |
| **Epoch**              | 已实现                         | `realtime_qwen.py:220` `_turn_epoch: int = 0`；在 `_invalidate_current_response` 的 line 870 递增；在派遣工具调用时捕获（line 715）                     | 不可见——内部机制                                        | 仅一个 epoch；无独立的工具 epoch。工具调用通过值捕获快照 epoch                                                                  |
| **任务取消**           | **部分实现（关键限制）** | `task.cancel()` 在 `_tool_tasks` 中被调用（line 886），但 `execute_tool()` 在 `asyncio.to_thread()` 中运行（line 944）——无法被 CancelledError 中断  | 已排队（尚未执行）的工具被取消；正在执行的工具继续完成    | **已在 OS 线程中执行的任务无法被取消**。工具完成其状态变更，然后 CancelledError 在 await 边界引发。状态变更已发生且不可逆 |
| **过时结果拒绝**       | 部分实现                       | 三重检查（`realtime_qwen.py:918, 936, 946`）：锁获取前、锁下执行前、执行后                                                                                  | 保留当前 dashboard 状态（未添加过时结果）                 | **关键缺陷**：在检查点 #3（执行后），工具已经变更了内存状态。丢弃的是结果的**传达**，而非**状态变更**         |
| **Dashboard 版本管理** | **未实现**               | 后端和前端均不存在版本字段。前端的 `updateViews()` (`dashboard.js:43`) 无条件全量替换                                                                     | 无版本检测——总是信任最新消息                            | 无防御层（如果过时消息绕过丢弃，会覆盖更新状态）                                                                                |
| **前端过时更新拒绝**   | **未实现**               | 无版本比较、无序列号、无 epoch 检查                                                                                                                           | 无保护——任何 `views_update` 消息被无条件接受          | 完全依赖后端侧丢弃；前端无防御措施                                                                                              |
| **交互反馈**           | 部分实现                       | 可见：Listening、Tool chips、Transcript（仅最终）、Filters。**不可见**：Speaking、Thinking、Interruption/Cancelled、Dashboard Updated、Your Turn 指示器 | 用户在中断、静默状态变更或 dashboard 刷新方面收到极少反馈 | 13 项中有 6 项缺失或仅为"状态仅存"（无可见 UI）                                                                                 |
| **日志记录**           | 已实现                         | 每个会话创建 6 个 .log + conversation.jsonl + tool_calls.jsonl。`tool_calls.jsonl` 包含 epoch、timeline、dashboard 快照                                     | 不可见——仅开发者                                        | Qwen 路径无法可靠计算 wasted speech 和 interrupt-to-audio-stop（无 truncation 事件日志）                                        |
| **轮次制条件**         | 已实现                         | `VERBALVIS_BARGE_IN_ENABLED` 环境变量控制 `session.update` 中的 `interrupt_response`（line 515）和前端麦克风按钮（`Dashboard.vue:191`）               | 在 turn_based 模式下，麦克风在助手说话时变灰并禁用        | 模式通过环境变量在服务器启动时设置——无运行时用户切换功能                                                                      |

---

# 5. Tool Inventory

| 工具                        | 已注册                | 后端已实现                                   | 前端已处理                                                | 必需参数                                              | 状态效果                                                                         | 限制                                                                                                         |
| --------------------------- | --------------------- | -------------------------------------------- | --------------------------------------------------------- | ----------------------------------------------------- | -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `filter_data`             | 是 (`tools.py:183`) | `_exec_filter_data` (`:527`)             | `handleToolResult` + `views_update`                   | `field` (必需), `operator`, `value`, `append` | 修改 `active_filters[]`；刷新所有非冻结视图                                    | `None` 字段值变为 `col = None`（非 ISO SQL 标准的 `IS NULL`）                                          |
| `remove_filter`           | 是 (`tools.py:233`) | `_exec_remove_filter` (`:578`)           | `handleToolResult` + `views_update`                   | `field` (必需)                                      | 移除一个字段的过滤器；保留其余                                                   | —                                                                                                           |
| `highlight_visual`        | 是 (`tools.py:211`) | `_exec_highlight_visual` (`:636`)        | `handleToolResult` (仅此)                               | `view_id` (必需)                                    | 设置 `highlighted_view`；**不触发** `views_update`                     | `highlight_element` 参数未被 specFactory.js 或 ChartSlot.vue 使用                                          |
| `append_visual`           | 是 (`tools.py:248`) | `_exec_append_visual` (`:665`)           | `views_update`（**不**通过 `handleToolResult`） | `chart_type, x, y, title`                           | 递增 `workspace_counter`；追加到 `views[]`                                   | `handleToolResult` 忽略 `append_visual` 结果；仅依赖 `views_update`。表图表仅支持 state×category 格式 |
| `set_low_score_threshold` | 是 (`tools.py:376`) | `_exec_set_low_score_threshold` (`:608`) | `views_update`（**不**通过 `handleToolResult`） | `threshold` (1-5)                                   | 设置 `low_score_threshold`；刷新所有比率视图                                   | `handleToolResult` 忽略工具的 `tool_result` 负载                                                         |
| `delete_visual`           | 是 (`tools.py:394`) | `_exec_delete_visual` (`:929`)           | `views_update`（**不**通过 `handleToolResult`） | `view_id` (必需)                                    | 从 `views[]` 中移除；如果被删除的视图是突出显示的，则清除 `highlighted_view` | 仅删除——不支持替换、移动、重排序或撤销                                                                     |

**全部 6 个已注册工具** = `TOOL_SCHEMAS` (`tools.py:182-409`) 中的 6 个条目 = `execute_tool()` (`tools.py:416-435`) 通过 if/elif 链分派的 6 个处理程序。无孤立工具、无孤立处理程序。

**前端 `handleToolResult` 仅处理 3/6 个工具**：`filter_data`、`remove_filter`、`highlight_visual`。其余 3 个仅依赖 `views_update` 进行前端状态更新。`appendView` store 操作（`dashboard.js:58`）是**死代码**——从未被调用。

---

# 6. Dashboard-State Inventory

## 后端状态（`tools.py` 中的全局变量）

| 变量                    | 类型           | 行 | 初始值   | 突变位置                                                                                      |
| ----------------------- | -------------- | -- | -------- | --------------------------------------------------------------------------------------------- |
| `active_filters`      | `list[dict]` | 81 | `[]`   | `filter_data` (:532/553/555), `remove_filter` (:590), `init_views` (:158)               |
| `workspace_counter`   | `int`        | 82 | `0`    | `_exec_append_visual` (:816 +=1), `init_views` (:159)                                     |
| `views`               | `list[dict]` | 83 | `[]`   | `init_views` (:158/162-165), `_exec_append_visual` (:894), `_exec_delete_visual` (:942) |
| `highlighted_view`    | `str\|None`   | 84 | `None` | `_exec_highlight_visual` (:650), `_exec_delete_visual` (:945-946), `init_views` (:160)  |
| `low_score_threshold` | `int`        | 85 | `2`    | `_exec_set_low_score_threshold` (:619), `init_views` (:161)                               |

**未找到**：`version`、`latest_request`、`recent_actions`、`fixed_views`、`appended_views`——这些在代码中都不存在。

## 前端状态（Pinia Store，`frontend/stores/dashboard.js` 和 `frontend/src/stores/dashboard.js`）

| 字段                    | 类型                                  | 默认值              |
| ----------------------- | ------------------------------------- | ------------------- |
| `views`               | `ref([])`                           | `[]`              |
| `activeFilters`       | `ref([])`                           | `[]`              |
| `highlightedViewId`   | `ref(null)`                         | `null`            |
| `highlightElement`    | `ref(null)`                         | `null`            |
| `transcripts`         | `ref([])`                           | `[]`              |
| `sessionSummaries`    | `ref([])`                           | `[]`              |
| `isAssistantSpeaking` | `ref(false)`                        | `false`           |
| `connectionStatus`    | `ref("disconnected")`               | `"disconnected"`  |
| `sessionReady`        | `ref(false)`                        | `false`           |
| `sessionMode`         | `ref("barge_in")`                   | `"barge_in"`      |
| `inputMode`           | `ref("server_vad")`                 | `"server_vad"`    |
| `provider`            | `ref("qwen")`                       | `"qwen"`          |
| `model`               | `ref("qwen3.5-omni-plus-realtime")` | 硬编码              |
| `recentToolCalls`     | `ref([])`                           | `[]`（最多 3 个） |

## 真实来源

**后端是唯一的真实来源**。Dashboard 数据（views、data、active_filters、highlighted_view）来自后端。前端 `updateViews()` 执行无条件全量替换——无 diff、无版本比较、无冲突解决。

## 版本管理

**不存在**。系统中不存在 `version` 字段。前端 `updateViews` 无条件替换 `views`，无版本检查。

## 重置

- **部分**：`filter_data` 使用 `field="__all__"` → 清除所有过滤器
- **完全**：前端发送 `start_session` → Qwen 路径调用 `_restart_qwen_session()` → 重新调用 `init_views()`
- **无**显式的"重置为默认" UI 按钮

## 4 个基础视图

| 视图 ID           | 标题            | 图表类型 | X                    | Y               | 来源表         |
| ----------------- | --------------- | -------- | -------------------- | --------------- | -------------- |
| `view-trend`    | 月度订单趋势    | 折线图   | `order_month`      | `order_count` | `fact_order` |
| `view-review`   | 评分分布        | 柱状图   | `review_score`     | `order_count` | `fact_order` |
| `view-map`      | 按州订单量      | 柱状图   | `customer_state`   | `order_count` | `fact_order` |
| `view-category` | 类别营收 Top 15 | 柱状图   | `product_category` | `revenue`     | `fact_item`  |

---

# 7. Response–Tool Coordination Audit（最关键部分）

## 已验证的状态变量

| 变量                          | 类型                  | 文件:行                  | 设置位置                                    | 检查位置                                                                     |
| ----------------------------- | --------------------- | ------------------------ | ------------------------------------------- | ---------------------------------------------------------------------------- |
| `current_response_id`       | `str\|None`          | `realtime_qwen.py:213` | `response.created` (:635)                 | `_create_response_if_idle` (:791), `_invalidate_current_response` (:869) |
| `_turn_epoch`               | `int`               | `realtime_qwen.py:220` | `_invalidate_current_response` (:870 +=1) | `_is_stale_tool_call` (:1056)                                              |
| `_invalidated_response_ids` | `set[str]`          | `realtime_qwen.py:219` | `_invalidate_current_response` (:873)     | `_is_stale_tool_call` (:1057)                                              |
| `_tool_tasks`               | `set[asyncio.Task]` | `realtime_qwen.py:218` | `_handle_tool_call` (:719)                | `_invalidate_current_response` (:886-887 cancel)                           |
| `_pending_tool_calls`       | `dict[str,int]`     | `realtime_qwen.py:222` | `_handle_tool_call` (:711-712)            | `_finalize_tool_call` (:1042)                                              |
| `_tool_state_lock`          | `asyncio.Lock`      | `realtime_qwen.py:217` | 使用 `async with` 获取                    | `_handle_tool_call` (:935), `_finalize_tool_call` (:1039)                |

## 正常执行流程（步骤带行号）

1. `input_audio_buffer.speech_stopped` (:662) → 服务器自动创建响应
2. `response.created` (:633) → `self.current_response_id = resp["id"]` (:635)，启动指标
3. `response.function_call_arguments.done` (:683) → `_handle_tool_call()` 作为任务被派遣（:715），使用 `turn_epoch=self._turn_epoch`（按值捕获）
4. 过时检查 #1 (:918)：锁获取前 → 如果过时，返回（未执行工具）
5. 获取 `_tool_state_lock` (:935) → 过时检查 #2 (:936)
6. `execute_tool()` 在 `asyncio.to_thread()` 中运行 (:944) → 变更内存中的工具状态
7. 过时检查 #3 (:946) → `stale_after_execution` 已记录
8. 如果不过时：发送 `tool_result` (:984)、`views_update` (:992-998)、`function_call_output` (:1011-1026)
9. 如果过时（且工具已执行）：返回于 :976——不发送消息，但工具的状态变更已发生

## Barge-In 流程（用户打断）

1. `input_audio_buffer.speech_started` (:659) → `_handle_speech_started()` (:863)
2. `_invalidate_current_response()` (:867)：
   - `self._turn_epoch += 1` (:870)
   - 当前 response_id 添加到 `_invalidated_response_ids` (:873)
   - 取消所有 `_tool_tasks` (:886-887)
   - 发送 `response.cancel` 到 Qwen (:889-890)
   - 发送 `speech_started` 到前端 (:892-895)
3. **前端**（`useWebSocket.js:117-125`）：接收 `speech_started` → `audioPlayer.stop()` → 关闭 AudioContext

## 过时结果流程

```
工具 T1 在 epoch=0 时派遣
→ T1 通过检查 #1 和 #2
→ execute_tool() 在 thread-pool 中开始执行
→ 用户开始说话 → epoch → 1
→ T1 的执行完成（状态已变更！）
→ T1 在检查 #3 处失败（turn_epoch=0 != self._turn_epoch=1）
→ 返回于 :976 : 不向前端发送 tool_result，不向 Qwen 发送 function_call_output
→ 关于 T1 结果的前端和 Qwen 均未得到通知
→ 但 T1 的状态变更存在于内存中，并影响后续操作
```

## 物理取消 vs 逻辑失效

| 机制                                          | 存在？         | 效果                      | 限制                                                                              |
| --------------------------------------------- | -------------- | ------------------------- | --------------------------------------------------------------------------------- |
| **物理取消**（`task.cancel()`）       | 是（:886-887） | 向协程发送 CancelledError | 无法中断 `asyncio.to_thread()` 中的 OS 线程。正在线程中执行的任务完成其状态变更 |
| **逻辑失效**（`_is_stale_tool_call`） | 是（三重检查） | 阻止将结果传达给前端/上游 | 在检查 #3 处，状态变更已发生。仅阻止传达，不阻止变更                              |

**结论**：逻辑失效（而非物理取消）是过时结果被实际上阻止的主要机制。由于无法在线程中取消，系统的有效保证是"我们不会告诉你过时的结果"，而不是"过时的操作不会产生效果"。

## Commit 条件（实际代码伪代码）

```python
def tool_result_accepted(response_id, captured_epoch):
    if captured_epoch != live_session_epoch:
        return DISCARD  # 自派遣以来发生了打断
    if response_id is not None and response_id in invalidated_response_ids:
        return DISCARD  # 此特定响应已失效
    if not session_is_running:
        return DISCARD  # 会话正在关闭
    return ACCEPT  # 向前端和上游模型传达
```

**注意**：这不是真正的 commit——状态变更无条件进行。这是一个"传达决策"，决定是否将结果告知前端和模型。

## 对 12 个问题的回答

1. **工具调用何时绑定到 response_id？** 在派遣时（:715），`response_id` 在 `_handle_tool_call()` 任务创建时通过闭包捕获
2. **工具调用是否绑定到 epoch？** 是，`turn_epoch=self._turn_epoch` 在派遣时通过值捕获（:715）
3. **用户开始说话时 epoch 是否总是递增？** **对于 Qwen：是**，无条件（:863-870）。对于 OpenAI（`realtime.py`）：仅在 server_vad 模式下（:725-731），非 `MANUAL_COMMIT_MODE`
4. **已排队工具是否被取消？** 是，`_tool_tasks` 中的所有任务接收到 `task.cancel()` (:886-887)。但线程中已执行的任务无法被中断
5. **已运行数据库任务是否被取消？** **否**。线程中执行的任务完成其 DuckDB 查询和状态变更
6. **无法取消时，结果是否被禁止 commit？** 传达被阻止（不发送 messages），但状态变更**已经发生**且不可逆
7. **过时检查在何时执行？** 三处：工具执行前（锁获取前）、锁下执行前、执行后。不在 Dashboard 更新前——没有单独的 Dashboard 更新检查
8. **已 commit 的旧状态是否可以回滚？** **否**。系统中不存在回滚/快照/撤销机制
9. **多个工具是否同时失效？** 是。当 `_turn_epoch` 递增时，所有在旧 epoch 下派遣的进行中工具在下次检查 #1 或 #2 时失效
10. **迟到的前端消息是否会覆盖新状态？** 如果一条过时的 `views_update` 以某种方式绕过后端丢弃（极不可能通过 TCP），前端会无条件接受它（前端无版本检查）
11. **current_response_id 何时清除？** 在 `response.done` 时（:744）和 `_restart_qwen_session` 中（:359）。在 `_invalidate_current_response` 中**不清除**
12. **`response.done` 后工具结果如何处理？** `_create_response_if_idle` 使用 `response.done` 清除的 `current_response_id` 来允许新的 `response.create`。如果此响应仍是最后一个待处理工具，`_finalize_tool_call` 会触发一个新的 `response.create`

---

# 8. Logging Audit

## 每会话日志文件

| 文件                      | 格式                | 内容                                                                                                                                                                     |
| ------------------------- | ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `realtime_events.log`   | 纯文本 HH:MM:SS.mmm | 所有 WS 事件，会话更新，上下文注入                                                                                                                                       |
| `tool_calls.log`        | 纯文本              | TOOL_EVENT, TOOL_CALL, TOOL_START, TOOL_STALE, TOOL_DONE, TOOL_CANCELLED                                                                                                 |
| `dashboard.log`         | 纯文本              | VIEWS_UPDATE                                                                                                                                                             |
| `bargein.log`           | 纯文本              | BARGE_IN, TRUNCATE_SKIPPED_QWEN                                                                                                                                          |
| `connection.log`        | 纯文本              | CONNECTING_QWEN, QWEN_CONNECTED, 会话生命周期                                                                                                                            |
| `conversation.log`      | 纯文本              | "You: ..." / "AI: ..."                                                                                                                                                   |
| `conversation.jsonl`    | JSONL               | ts, session_id, role, text                                                                                                                                               |
| `tool_calls.jsonl`      | JSONL               | timestamp, session_id, tool, params, response_id, call_id, result_success, cancelled, metrics (tool_duration_ms, turn_epoch, timeline), dashboard_context_snapshot, mode |
| `session_summary.jsonl` | JSONL               | 带有 16 个键的完整阶段摘要字典                                                                                                                                           |

## 指标可计算性

| 指标                             | 可计算？                    | 缺失事件                                                                                                                         |
| -------------------------------- | --------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| interrupt-to-audio-stop          | **部分**（仅 OpenAI） | Qwen 路径下无 truncation 事件日志——无法可靠计算。前端 `audioPlayer.stop()` 未被记录                                          |
| redirect-to-first-aligned-action | **可计算**            | `tool_calls.jsonl` timeline 跟踪 `speech_started` → `TOOL_START`                                                          |
| redirect-to-aligned-dashboard    | **可计算**            | 比较 tool_calls.jsonl 中的 `turn_epoch` 值                                                                                     |
| wasted speech                    | **不可用于 Qwen**     | Qwen 路径下无 truncation。`_current_assistant_audio_generated_ms` 在中断时未被记录——仅发送到前端的 `response_done` metrics |
| stale-result handling            | **可计算**            | 完整记录：TOOL_STALE_BEFORE_START, TOOL_STALE_AFTER_LOCK, TOOL_STALE；tool_calls.jsonl 中的 `cancelled` 标志                   |

## 日志缺口

1. **Qwen 会话无 wasted speech**——日志中不记录截断/中断时间
2. **无前端渲染完成**事件——无日志周期结束标记
3. **无 Dashboard 版本**可供记录
4. **无会话级实验条件**日志（条件由 env var 设置但未明确记录在日志中）
5. **`realtime.py` 和 `realtime_qwen.py` 之间日志不一致**——前者使用 `print()` + 文件日志，后者使用仅文件日志

---

# 9. Safe Claims（论文可以安全声称的内容）

1. 系统提供了一个语音驱动的可视分析界面，具有全双工音频能力
2. 当用户开始说话时，服务器端 VAD 检测语音开始并触发响应取消（`response.cancel` 发送到 Qwen）
3. 当检测到用户语音时，前端立即通过 `AudioContext.close()` 停止音频播放
4. 每个工具调用都绑定到一个 `turn_epoch`，该 epoch 在每次打断时递增
5. 来自被取代轮次的工具结果通过三重过时检查被阻止传达给前端和模型
6. 系统维护一个包含 4 个基础视图的 dashboard（通过 DuckDB 查询的 Olist 数据）和动态工作区图表
7. 六个基于模式的工具（filter_data、highlight_visual、remove_filter、append_visual、set_low_score_threshold、delete_visual）已完全实现为注册给模型的函数调用
8. 在每次成功的工具调用后，将 dashboard 上下文（筛选器、视图 ID、统计数据、行数）注入到模型的指令中
9. 工具协调通过 `_tool_state_lock` 处理多工具轮次，使用 `_pending_tool_calls` 来去重 `response.create` 调用
10. 每个会话生成结构化日志（JSONL 格式），包含 tool_calls.jsonl（完整 timeline + dashboard 快照）和 conversation.jsonl

---

# 10. Claims Requiring Weaker Wording

必须使用较弱措辞（如"尝试取消"、"防止提交"、"使用上下文来解释"、"旨在支持"）而非"确保"或"保证"的主张：

1. **任务取消**：系统 *尝试取消* 进行中的工具任务，但通过 `asyncio.to_thread()` 在线程中执行的任务继续运行至完成。应使用"attempts to cancel in-flight tool tasks via asyncio task cancellation"。
2. **防止过时结果**：系统 *防止提交* 来自被取代响应的结果到前端，但已执行的工具所进行的数据库状态变更无法被阻止。使用"prevents stale tool results from being relayed to the frontend"而非"prevents stale mutations"。
3. **上下文解释**：系统 *使用上下文来解释* 当前 dashboard 状态——上下文在每次工具调用后作为 `function_call_output` 的一部分注入，但工具调用之间不会更新。使用"provides model with dashboard context that is refreshed after each tool call"。
4. **Dashboard 同步**：系统 *旨在支持* dashboard 同步。无版本或渲染完成反馈。使用"designed to keep the dashboard synchronized with tool results"。
5. **打断处理**：系统 *处理打断*——但无"thinking"指示器、无取消确认反馈、无 barge-in 和 speech-correction 之间的区分。使用"treats user speech onset during assistant output as a potential redirection signal"。

---

# 11. Missing or Incomplete Mechanisms（按重要性排序）

1. **[高] 真正的物理任务取消**：`asyncio.to_thread()` 无法被 CancelledError 中断。如果在检查点 #2 和 #3 之间发生打断，工具的状态变更已发生且不可逆。
2. **[高] 无可回滚**：无快照/保存点/撤销机制用于恢复被过时工具变更损坏的状态。
3. **[中] Qwen 无 `conversation.item.truncate`**：音频截断仅在前端处理（AudioContext 硬停止）。无法测量 wasted speech。
4. **[中] Qwen 无 `conversation.item.create` 用于上下文**：Dashboard 上下文仅在指令中（启动时）和工具调用输出中注入。工具调用之间不更新。
5. **[中] 无 Dashboard 版本管理**：前端无条件全量替换 `views`。无防御层对抗过时消息。
6. **[中] 前端 UI 反馈缺口**：无"Speaking"指示器、无"Thinking"状态、无中断/取消确认、无 Dashboard 更新通知。
7. **[中] `_tool_state_lock` 使工具执行串行化**：多工具并行被锁阻止。
8. **[低] `realtime.py`（OpenAI 路径）是死代码**——存在于仓库中但从未被导入。
9. **[低] 无自动 WebSocket 重连**（Qwen 路径）。`QWEN_RECONNECT_ATTEMPTS` 已声明但从未被引用。
10. **[低] 所有 Python 依赖均未固定版本**——破坏可复现性。

---

# 12. Chapter 4 Detailed Paragraph Plan（设计章节）

## 12.1 Interaction Overview

- **核心论点**：在全双工对话式可视分析中引入了持续的"观察→语音→分析→可视化→新观察"循环
- **系统事实**：系统以全双工方式运行，默认启用打断；用户可以在助手说话时发言；操作通过工具调用变为对 dashboard 的具体更改
- **交互示例**：用户说"显示低评分订单"→ 助手调用 `filter_data(review_score, lte, 2)` → dashboard 刷新为仅显示低评分订单 → 用户观察并说出后续请求
- **DR**：DR1（上下文解释基础）
- **formations**：形成性研究发现用户频繁打断以根据视觉观察修正方向
- **仅限第 5 章**：PCM 格式、WebSocket 事件名称、`_turn_epoch`

## 12.2 Context-Grounded Interpretation

- **核心论点**：助手结合用户话语与当前 dashboard 状态（筛选器、突出显示的视图、可用视图）来解释意图
- **系统事实**：上下文文本包括活跃筛选器、已筛选行数、突出显示的视图、视图 ID/标题/类型、每个视图的统计数据
- **交互示例**：用户说"高亮第二个"——助手知道 `view-review` 是"第二个视图"并调用 `highlight_visual(view-review)`
- **DR**：DR1
- **仅限第 5 章**：`context_text()` 函数、确切的文本格式、注入时机

## 12.3 Composable Analytical Actions

- **核心论点**：一个话语可以触发多个工具调用（筛选→高亮→追加），而不是将每个话语映射到单个操作
- **系统事实**：系统支持单轮次响应中的多个工具调用，使用待处理计数器进行协调
- **交互示例**："过滤到电子产品并显示交付时间与评分的散点图"→ 两个工具调用
- **DR**：DR2
- **仅限第 5 章**：`_pending_tool_calls` 协调机制、`_tool_state_lock` 串行化

## 12.4 Interpreting Overlapping Speech

- **核心论点**：并非每次打断都是分析性修订——系统将服务器 VAD 视为信号，但不尝试在运行时分类打断类型
- **系统事实**：当服务器 VAD 检测到语音开始时，系统取消当前响应并处理新话语。不区分目标转变、假设修正、ASR 修正和澄清
- **交互示例**：用户说"我是说视图，不是试图"（ASR 修正）vs "改为按评分筛选"（目标转变）——两者通过同一管道处理
- **DR**：DR3
- **仅限第 5 章**：VAD 参数（threshold=0.5、silence=800ms）、音频截断的缺失
- **避免声称**：系统从不声称识别或分类哪些打断是"真实"分析性修订

## 12.5 Coordinated Redirection and State Preservation

- **核心论点**：当用户改变方向时，系统停止当前的语音+工具工作，防止过时结果破坏 dashboard，并从最新的已提交状态继续
- **系统事实**：音频停止（客户端）、响应取消（发送到模型）、过时工具结果在传达到前端之前被丢弃、最新上下文重新注入
- **交互示例**：[论文草稿案例研究场景]
- **DR**：DR4
- **仅限第 5 章**：epoch 跟踪的具体细节、check-then-act 竞态条件、thread-pool 取消限制
- **避免声称**：不要声称"事务一致性"或"保证状态一致性"。使用"prevents stale results from updating the dashboard"而非"ensures consistent state"

## 12.6 Visualization as a Persistent Analytical Workspace

- **核心论点**：Dashboard 是一个持久工作空间，在交互过程中保持视觉状态（筛选器、图表、突出显示），使用户能够跨轮次构建和比较证据
- **系统事实**：4 个基础视图 + 动态追加的工作区图表。筛选器全局应用（除非图表声明为独立）。图表可以冻结以供比较。已删除的视图会清除突出显示
- **交互示例**：用户筛选 SP → 追加交付散点图 → 冻结以供比较 → 移除 SP 筛选器 → 两个图表并排显示
- **DR**：DR1、DR2
- **仅限第 5 章**：`freeze`/`inherit_global_filters` 的实现细节、有效筛选器的计算方式
- **避免声称**：不要声称"无限工作空间"或"完整分析历史"——无撤销、无分支、无重排序

## 12.7 Interaction Feedback

- **核心论点**：系统通过麦克风按钮、筛选器徽章、转录和工具芯片提供轻量级状态反馈——但故意避免用持续的视觉提示压垮用户
- **系统事实**：可见：Listening 状态、转录（仅最终）、筛选器徽章、工具芯片（最近 3 个）、连接状态。不可见：Speaking、Thinking、Dashboard 已更新、中断已确认
- **DR**：DR1、DR3
- **避免声称**：不要声称"全面的反馈系统"——当前实现中有 6/13 的反馈元素缺失或仅为"状态仅存"

---

# 13. Chapter 5 Detailed Paragraph Plan（实现章节）

## 13.1 System Architecture

- **关键事实**：Vue 3 + Vega-Lite 前端，FastAPI + DuckDB 后端，Qwen DashScope WebSocket 中继，通过 env var 实现双条件（barge_in/turn_based）
- **推荐图表**：架构图（在提示词文档中已部分提供）
- **表格**：技术栈摘要，WebSocket 路由表
- **揭示**：`realtime.py`（OpenAI）作为参考实现存在但未被连接

## 13.2 Full-Duplex Audio Pipeline

- **关键事实**：AudioWorklet 处理器，16kHz 输入/24kHz 输出 PCM16，每个块 100ms，base64 编码。服务器 VAD（threshold=0.5，silence=800ms）。无客户端 VAD（`gateSilence: false`）。播放通过 `AudioContext` 和 `nextPlayTime` 锚定进行无间断调度
- **已确认**：Qwen 不支持 `conversation.item.truncate`——音频在前端通过 AudioContext.close() 硬停止

## 13.3 Prompting and Dashboard-State Grounding

- **关键事实**：9 段提示词，2 种模型构建器（`build_system_prompt()` 用于 Qwen，通过 `_build_instructions()` 附加上下文 + Qwen 特定规则）。上下文包括筛选器、阈值、行数、突出显示的视图、每个视图元数据和统计数据
- **限制**：Qwen 路径无法进行实时上下文注入（无 `conversation.item.create` 用于系统消息）——上下文仅在指令中（启动时）和工具调用输出中。工具调用之间不更新

## 13.4 Schema-Grounded Analytical Tools

- **关键事实**：6 个已注册工具（不是论文草稿中声称的 5 个——`set_low_score_threshold` 已注册并完全实现）。每个工具：模式验证 + `normalize_tool_arguments()` NLP 推断 + 服务器端检查 + `execute_tool()` dispatch。`append_visual` 有 14 项验证检查串联
- **关键细节**：`normalize_tool_arguments` 从中文文本推断缺失参数（Top N、饼图 vs 柱状图、排序方向、配送速度桶）
- **限制**：前端 `handleToolResult` 仅处理 6 个工具结果中的 3 个

## 13.5 Data and Visualization State

- **关键事实**：DuckDB 内存数据库，2 个事实表（`fact_order`：每个已交付订单一行，`fact_item`：每个订单商品一行）。所有 SQL 通过 f-string 构建，字段名在 tools.py 中与白名单比对
- **4 个基础视图** + 单体递增计数器生成的动态 `workspace{N}` ID
- **限制**：无参数化查询。2 个 CSV 存在于磁盘但从未加载（geolocation、sellers）。3 个函数（`aggregate_query`、`stats_query`、`raw_query`）已导入但从未调用

## 13.6 Response–Tool Coordination

- **关键事实**：`_turn_epoch` 单调计数器，三重过时检查，`_pending_tool_calls` 协调，锁串行化。`_is_stale_tool_call()` 谓词：epoch 不匹配 OR 响应已失效 OR 会话未运行
- **关键限制**：`asyncio.to_thread()` 无法被取消。在检查点 #3 处完成的工具已经变更了内存状态。无回滚机制
- **推荐**：显示正常执行和 barge-in 场景的序列图，提交条件伪代码

## 13.7 Logging and Instrumentation

- **关键事实**：每会话 6 个 .log 文件 + conversation.jsonl + tool_calls.jsonl（结构化 JSONL，包含完整 timeline + dashboard 快照 + epoch）。`SessionSummaryTracker` 使用正则表达式规则确定性检测 ASR 混淆
- **缺口**：Qwen 路径下无 wasted speech 记录（无 truncation 事件）。无前端渲染完成事件。日志之间不一致

---

# 14. Recommended Figures, Tables, and Algorithms

| 章节             | 推荐的图表                                                   |
| ---------------- | ------------------------------------------------------------ |
| §5.2 系统架构   | 带标注的架构图（前后端 + Qwen + DuckDB）                     |
| §5.2 音频流水线 | 从 AudioWorklet 到 Qwen 到 AudioContext 的序列图             |
| §5.4 工具       | 工具清单表（工具名称、参数、枚举、状态效果、限制）           |
| §5.5 数据       | 包含 `fact_order` 和 `fact_item` 列的数据库模式表        |
| §5.6 协调       | 正常执行和 barge-in 场景的序列图；提交条件伪代码             |
| §5.6 协调       | 已验证状态变量表（名称、类型、定义位置、突变位置、检查位置） |
| §5.7 日志       | 事件到指标表（显示哪些指标可以从日志中计算）                 |

---

# 15. Open Questions Requiring Author Confirmation

1. **Qwen vs GPT 差异**：论文草稿始终引用 `gpt-realtime-2`。是需要更新论文以反映实际的 Qwen 实现，还是计划在用户研究前切换到 OpenAI？
2. **消失的 `realtime.py`**：OpenAI 路径（1103 行）存在于仓库中但从未被连接。是打算作为后备还是参考实现？论文是否应描述一个与提供商无关的架构？
3. **`set_low_score_threshold`**：已注册并完全实现（6 个工具），但论文草稿列出 5 个已实现工具。需要包含此工具还是降级？
4. **物理取消限制**：系统能否有效缓解 thread-pool 取消问题（例如，在 `execute_tool` 内部添加检查点），还是论文应仅依赖于逻辑失效？
5. **Dashboard 上下文及时性**：Qwen 无法通过 `conversation.item.create` 进行实时上下文注入——这是一个需要在论文中记录的已知限制，还是有意为之的设计？
6. **用户研究条件**：用户研究将如何管理条件（FullDuplex vs NoBarge）而不在代码中进行随机化？是通过实验者手动重启服务器并更改 `VERBALVIS_BARGE_IN_ENABLED` 环境变量吗？
7. **前端反馈缺口**：六个 UI 反馈元素仅为"状态仅存"或未实现——这些是在用户研究前需要修复的，还是在论文中作为未来工作进行充分记录？
8. **`delivery_speed_bucket` 提示词缺口**：此字段在提示词中（`prompts.py:186`）被引用但从未在字段清单中定义。是提示词需要修复，还是代码缺失此字段？
9. **版本固定**：所有 6 个 Python 依赖均未固定版本——是否应为可复现性固定版本？
10. **未使用的 CSV**：geolocation 和 sellers CSVs 存在于磁盘但从未被加载。是打算在未来的数据源中使用，还是可以移除？

---

# 16. Prioritized Implementation Fixes Before the User Study

| 优先级       | 问题                                                                                        | 影响       |
| ------------ | ------------------------------------------------------------------------------------------- | ---------- |
| **P0** | 在前端添加 epoch/版本检查，防止过时消息覆盖更新状态                                         | 防御层     |
| **P0** | 添加"Speaking"视觉指示器（`isAssistantSpeaking` 被设置但从未在 UI 中渲染）                | 用户体验   |
| **P1** | 在"Thinking"期间添加可见反馈（语音停止和助手响应开始之间的间隙）                            | 用户体验   |
| **P1** | 添加中断/取消确认（转录中的 toast 或注释）                                                  | 用户体验   |
| **P1** | 记录前端 `audioPlayer.stop()` 时机，以便在 Qwen 路径下计算 wasted speech                  | 研究指标   |
| **P1** | 固定 requirements.txt 中的 Python 依赖版本                                                  | 可复现性   |
| **P2** | 移除死代码或连接 `realtime.py`（OpenAI 路径）                                             | 代码整洁度 |
| **P2** | 修复 `delivery_speed_bucket` 提示词缺口（在 `prompts.py` 的字段清单中添加或删除使用处） | 模型准确性 |
| **P2** | 添加 Dashboard 更新通知（动画或指示器）                                                     | 用户体验   |
| **P3** | 为活动会话添加会话级"条件"日志条目                                                          | 研究分析   |
| **P3** | 实现工具调用去重（通过 `call_id`）                                                        | 稳健性     |
