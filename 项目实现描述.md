# VerbalVis 项目完整实现描述

---

## 一、项目目标

实现一个全双工语音驱动的可视分析系统，让分析师通过语音与AI协同分析Olist巴西电商数据集。系统的核心特性是支持barge-in打断——用户可以在AI说话过程中随时插话修正分析方向，AI立即停止当前输出并重新规划。最终需要跑通一个包含三次打断的Running Example，作为论文Case Study的素材。

---

## 二、技术栈

```
前端：Vue 3 + Pinia + Vega-Lite + Vite
后端：FastAPI + DuckDB + websockets
语音：OpenAI Realtime API（gpt-realtime-2）
数据：Olist CSV → DuckDB宽表
```

---

## 三、数据层

### 3.1 数据准备

后端启动时，DuckDB读取Olist的多个CSV文件，执行一次JOIN生成一张宽表main_table，包含以下字段：

```
order_id            VARCHAR
order_month         VARCHAR    ← YYYY-MM，从purchase_timestamp截取
review_score        INTEGER    ← 1-5
customer_state      VARCHAR    ← 巴西州代码，如SP、RJ
product_category    VARCHAR    ← 品类名称
delivery_days       INTEGER    ← actual_delivery - purchase，整数
revenue             FLOAT      ← payment_value
```

JOIN逻辑：orders LEFT JOIN order_items ON order_id，LEFT JOIN order_reviews ON order_id，LEFT JOIN customers ON customer_id，LEFT JOIN products ON product_id。宽表大约10万行，DuckDB查询毫秒级。

### 3.2 查询函数

db.py暴露两类函数：

第一类是聚合查询，给定WHERE子句、GROUP BY字段、聚合指标，返回分组后的数据数组，直接喂给前端Vega-Lite渲染。

第二类是统计查询，给定WHERE子句和目标字段，返回row_count、mean、median、max、min等统计值，用于构建dashboard_context里的statistics。

WHERE子句由当前active_filters列表动态构造。每个filter是一个字典，包含field、operator、value三个字段，转成SQL条件拼接。

---

## 四、Tool层

### 4.1 三个Tool（模型调用）

**filter_data**

参数：field、operator、value、append、reason

执行逻辑：如果append=true，把新条件追加到active_filters列表；如果append=false，替换整个列表；如果field=null，清空列表。然后触发全局数据刷新——对所有视图重新执行聚合查询和统计查询，把新data推给前端，把新dashboard_context注入给Realtime。reason字段不影响执行逻辑，仅写入实验日志。

**append_visual**

参数：chart_type、x、y、title、color、analysis_goal

执行逻辑：根据chart_type和字段名生成Vega-Lite spec。用当前active_filters构造WHERE子句查询数据。生成递增的view_id（workspace-1、workspace-2……）。把spec + data + view_id推给前端，前端往views数组push新对象，网格自动重排。把view_id作为工具执行结果返回给Realtime，这样模型后续可以引用这个ID。analysis_goal字段仅写入实验日志。

**highlight_visual**

参数：view_id、highlight_element、dim_others

执行逻辑：不查数据库。把高亮指令推给前端——前端设置目标视图opacity=1.0，其余视图opacity=0.4。如果有highlight_element，前端在Vega-Lite里对应数据点加高亮标记。更新dashboard_context里的highlighted_view字段。

### 4.2 自动机制（不是Tool）

**aggregate_data**

不是模型调用的工具。filter_data执行后自动触发。对每个视图根据其x_field和y_field重新执行聚合查询，更新数据。

**layout_reflow**

不是模型调用的工具。append_visual执行后，前端CSS Grid自动重排，不需要后端介入。

### 4.3 Tool Schema

每个Tool用helper函数生成统一格式：

```python
{
    "type": "function",
    "name": "...",
    "description": "...",
    "parameters": {...}
}
```

description只描述工具做什么，不包含调用时机的指令。调用时机的规则统一写在SYSTEM_PROMPT里。

view_id参数加enum约束，防止模型编造不存在的ID。append_visual新增的视图ID需要在工具执行后动态更新可用的enum范围，通过dashboard_context告知模型。

### 4.4 SYSTEM_PROMPT

包含以下内容：你是VerbalVis的数据分析助手，当前Dashboard有哪些视图（从dashboard_context读取），当用户表达分析意图时立即调用工具，用户可能在你说话过程中打断，打断时重新评估意图并生成新的工具调用，基于dashboard_context中的facts和statistics进行分析解释，不要预设结论，让分析方向由用户和AI共同形成。

---

## 五、dashboard_context

### 5.1 结构

```python
{
    "active_filters": [
        {"field": "review_score", "operator": "lte", "value": 2}
    ],
    "highlighted_view": "view-review",
    "views": [
        {
            "id": "view-trend",
            "chart_type": "line",
            "title": "Monthly Orders Trend",
            "x_field": "order_month",
            "y_field": "order_count",
            "row_count": 1834,
            "statistics": {
                "peak_month": "2017-11",
                "peak_value": 342,
                "avg_monthly": 76
            }
        },
        ...
    ]
}
```

### 5.2 两层信息

Level 1是结构信息：chart_type、encoding、filters、row_count。告诉模型当前每个视图长什么样。

Level 2是统计事实：mean、median、peak、ratio等。告诉模型当前数据的客观特征。

不提供Level 3（Interpretation）。不存hypothesis、不存insight。让Realtime自己基于Level 1 + Level 2形成解释，这样不同用户面对同一张图可以走向不同的分析路径。

### 5.3 更新时机

每次任何Tool执行完，都调用rebuild_context函数。这个函数对每个视图执行聚合SQL拿新data、执行统计SQL拿新statistics，组装成完整的context字典。然后做两件事：data推给前端渲染，context通过conversation.item.create注入给Realtime。

### 5.4 statistics怎么算

每个视图的statistics通过DuckDB SQL计算，都是简单的聚合函数：

view-trend：peak_month（订单最多的月份）、peak_value、avg_monthly

view-review：mean（平均评分）、median、low_score_ratio（score≤2的比例）、dominant_bin（最多的评分档）

view-map：top_state（订单最多的州）、top_state_ratio（该州占比）、state_count

view-category：top_category（销售额最高的品类）、top_revenue、category_count

append_visual动态创建的视图：根据chart_type自动选择合适的统计指标，比如scatter类型算correlation、mean_x、mean_y。

---

## 六、后端架构

### 6.1 连接模型

一个FastAPI进程，维护两个WebSocket连接：

```
前端浏览器 ←WebSocket→ FastAPI ←WebSocket→ OpenAI Realtime API
```

前端连上后端时，后端同时建立与OpenAI的连接。前端断开时，后端也关闭与OpenAI的连接。

### 6.2 与OpenAI Realtime API的交互

连接建立后发送session.update，包含SYSTEM_PROMPT和TOOL_SCHEMAS。

运行时监听OpenAI返回的事件流：

response.audio.delta → 直接转发给前端播放

response.function_call_arguments.done → 解析工具名和参数，执行本地逻辑，rebuild_context，把data推给前端，把tool result + context通过conversation.item.create返回给OpenAI，然后response.create让Realtime继续推理

input_audio_buffer.speech_started → Realtime自带的VAD检测到用户开口，Realtime自动处理打断，后端不需要手动调response.cancel

### 6.3 消息格式

前端→后端：

```json
{"type": "audio", "data": "<base64 PCM>"}
```

后端→前端：

```json
{"type": "audio", "data": "<base64 PCM>"}
{"type": "tool_result", "tool": "filter_data", "views_data": {...}}
{"type": "tool_result", "tool": "append_visual", "view": {...}}
{"type": "tool_result", "tool": "highlight_visual", "view_id": "...", "dim_others": true}
{"type": "audio_stop"}
```

### 6.4 文件结构

```
backend/
├── main.py        # FastAPI入口 + WebSocket endpoint
├── db.py          # DuckDB初始化 + 查询函数
├── tools.py       # Tool Schema + 执行函数 + rebuild_context
├── realtime.py    # OpenAI Realtime API连接管理 + 事件处理
└── data/olist/    # CSV文件
```

---

## 七、前端架构

### 7.1 Pinia Store

dashboard store维护：

views数组：初始4个，每个包含id、spec、data、highlighted。append_visual追加新元素。

active_filters：当前筛选条件列表，同步后端状态。

applyToolResult方法：根据tool_result消息类型更新对应状态。

### 7.2 WebSocket连接

useWebSocket.js composable管理与后端的连接。onmessage根据type分发：audio给播放器，tool_result给store，audio_stop清空播放队列。提供sendAudio方法发送麦克风数据。

### 7.3 音频处理

useAudio.js composable管理麦克风录制和音频播放。

录制：getUserMedia获取麦克风，AudioWorklet把PCM转base64，持续通过WebSocket发送。

播放：AudioContext维护播放队列，收到audio数据解码排入队列，收到audio_stop清空队列立即停止。

不需要前端做VAD，Realtime API自带。

### 7.4 Dashboard组件

Dashboard.vue是CSS Grid容器，v-for渲染views数组：

```css
.dashboard-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
    gap: 16px;
}
```

4个视图自动2×2，追加第5个后自动重排。

ChartSlot.vue接收单个view对象，用vega-embed渲染spec。view.data变化时重新渲染。view.highlighted控制opacity。

### 7.5 Vega-Lite Spec

四个初始视图的spec硬编码。Choropleth需要巴西TopoJSON文件，放在public目录下。append_visual的spec由后端根据参数动态生成。

### 7.6 文件结构

```
frontend/src/
├── App.vue
├── stores/
│   └── dashboard.js
├── composables/
│   ├── useWebSocket.js
│   └── useAudio.js
└── components/
    ├── Dashboard.vue
    └── ChartSlot.vue
```

---

## 八、Barge-in机制

整个打断流程不需要后端手动处理。Realtime API自带VAD，检测到用户开口后自动停止当前AI输出，自动处理新的用户输入，自动产生新的工具调用。

后端唯一需要做的是：收到新的function_call时正常执行，不需要区分这次调用是"正常对话"还是"打断后重新规划"。

前端唯一需要做的是：收到audio_stop时停止播放，收到新的audio时开始播放新内容，收到tool_result时更新Dashboard。

打断的智能全部交给Realtime，不写任何GoalShiftDetector、HypothesisCorrectionDetector、ScopeNarrowingDetector。把三种打断类型的概念写进SYSTEM_PROMPT，让模型自己判断。

---

## 九、Turn-based Baseline

User Study需要一个关闭barge-in的对照版本。实现方式是后端加一个配置开关：

```python
BARGE_IN_ENABLED = True
```

当BARGE_IN_ENABLED=False时，在session.update里设置turn_detection为disabled或调大silence阈值，让Realtime不在AI说话时响应用户输入。用户必须等AI说完才能被处理。其他所有逻辑完全一致。

---

## 十、实验日志

每次工具调用时，后端写一条日志到本地JSON文件：

```json
{
    "timestamp": "2026-06-23T14:32:01",
    "session_id": "user-03-barge-in",
    "tool": "filter_data",
    "params": {
        "field": "customer_state",
        "operator": "eq",
        "value": "SP",
        "append": true,
        "reason": "scope_narrowing"
    },
    "dashboard_context_snapshot": {...},
    "mode": "barge_in"
}
```

filter_data的reason字段和append_visual的analysis_goal字段直接记录在日志里，User Study分析时不需要人工推断意图类型。

---

## 十一、Running Example验证标准

系统跑通的标准是完整执行以下流程：

```
用户："帮我看看这个数据集有什么问题"
  → AI开始说话 + highlight_visual(view-trend)
  → Dashboard趋势图高亮

用户打断："我更关心评分"
  → AI立刻停止
  → highlight_visual(view-review)
  → Dashboard评分图高亮，趋势图变暗
  → AI重新开口解释评分

用户打断："我觉得是物流问题"
  → AI立刻停止
  → filter_data(review_score<=2)
  → append_visual(scatter, delivery_days, review_score)
  → Dashboard新增散点图，网格重排
  → AI解释延迟与评分关系

用户打断："只看圣保罗"
  → AI立刻停止
  → filter_data(customer_state=SP, append=true)
  → highlight_visual(view-map)
  → 所有视图数据更新为SP
  → AI解释SP内部模式
```

这个跑通了，Case Study有素材，User Study有系统，论文的System Design和Evaluation都能写。

---

## 十二、开发顺序

```
Step 1  db.py
        DuckDB读CSV、JOIN宽表、聚合查询、统计查询
        独立测试：Python脚本调用验证查询结果

Step 2  tools.py
        Tool Schema + 执行函数 + rebuild_context
        独立测试：模拟工具调用，检查context输出

Step 3  前端静态渲染
        Pinia store + Dashboard.vue + ChartSlot.vue
        用假data跑通4个视图渲染

Step 4  main.py + realtime.py
        FastAPI WebSocket + OpenAI连接
        串联后端所有模块

Step 5  前端接WebSocket
        useWebSocket.js + useAudio.js
        真实数据替换假数据，音频录制播放

Step 6  联调
        Running Example三次打断端到端跑通

Step 7  Turn-based版本
        加配置开关，关闭barge-in
```

对，你说得对。Realtime能自己纠正的前提是后端返回的错误信息足够详细，让它知道错在哪、怎么改。

---

**后端容错应该做的事：**

**参数校验，返回具体原因：**

```python
# 字段名不存在
{
    "success": false,
    "error": "Unknown field: 'state'. Available fields: customer_state, review_score, product_category, order_month, delivery_days, revenue, order_count"
}

# operator不合法
{
    "success": false,
    "error": "Invalid operator: 'contains'. Supported operators: eq, neq, in, gte, lte, between"
}

# value类型不匹配
{
    "success": false,
    "error": "Field 'review_score' expects integer, got string 'high'"
}

# view_id不存在
{
    "success": false,
    "error": "Unknown view_id: 'review_chart'. Available views: view-trend, view-review, view-map, view-category, workspace-1"
}
```

**SQL执行异常捕获：**

```python
# DuckDB查询出错
{
    "success": false,
    "error": "Query failed: column 'delivery_time' does not exist. Did you mean 'delivery_days'?"
}
```

**空结果提示：**

```python
# 筛选后没有数据
{
    "success": true,
    "warning": "Filter returned 0 rows. Current filters: review_score<=2 AND customer_state='AC'. Consider relaxing filters.",
    "filtered_rows": 0
}
```

---

**核心原则是：每条错误信息都要告诉Realtime三件事：**

```
1. 错在哪（哪个参数有问题）
2. 为什么错（期望什么、实际收到什么）
3. 怎么改（列出合法选项）
```

这样Realtime不是盲目重试，而是有依据地纠正参数后重新调用。

我这个项目这么做，可以吗？

必须修改：不要把 dashboard_context 全量塞回 Realtime

只发：

```
{
   "type":"system",
   "content":"Dashboard updated.

Highlighted view:
view-review

Active filters:
review_score<=2
"
}
```

append_visual 的 enum 不现实

然后Prompt里告诉模型：

```
Current views:

view-trend
view-review
view-map
view-category
workspace-1
workspace-2
```

# 必须修改 ③

## audio_stop 不一定会有

这里最容易踩坑。

你写：

```
{
  "type":"audio_stop"
}
```

---

Realtime API并没有保证：

```
每段语音结束
↓
发audio_stop
```

这种事件。

---

你应该自己维护：

```
current_response_id
```

---

监听：

```
response.done
```

或者：

```
response.output_item.done
```

再通知前端：

```
{
   "type":"assistant_finished"
}
```

---

不要依赖：

```
audio_stop
```

这个概念。

append_visual 不要直接生成 Vega Spec。

Tool返回：

```
{
   "chart_type":"scatter",
   "x":"delivery_days",
   "y":"review_score"
}
```

---

前端：

```
specFactory()
```

生成 Vega。

# 应该修改 ②

## Tool Result 应该统一格式

现在：

```
highlight_visual
```

返回一种格式。

---

```
append_visual
```

另一种格式。

---

建议统一：

```
{
   "tool":"highlight_visual",
   "success":true,
   "payload":{...}
}
```

# 应该修改 ③

## reason 不要让模型生成

这是论文相关。

---

现在：

```
filter_data(
reason="scope_narrowing"
)
```

---

我会删掉。

---

因为：

```
Goal Shift
Hypothesis Correction
Scope Narrowing
```

是你的研究标签。

---

不是Tool参数。

# 所以 VerbalVis 应该怎么改

我现在会改成：

## 固定图

Prompt维护：

```
Base Views

view-trend
view-review
view-map
view-category
```

---

## 动态图

Prompt维护：

```
Current Workspace Views

workspace-1
workspace-2
workspace-3
```

## filter_data

核心职责是收窄全局数据范围，所有视图同步更新。

需要知道筛什么字段、用什么条件、筛什么值。另外需要一个append标志，因为第三次打断是在已有低评分筛选基础上再叠加SP筛选，不能把前面的条件冲掉。还需要支持传null来清空所有筛选，恢复全量数据。

所以参数是：field（筛哪个字段）、operator（等于/小于等于/大于等于/包含等）、value（筛选值，可以是字符串、数字、数组或null）、append（是否叠加，默认false）。

---

## 

---

## highlight_visual

核心职责是引导用户注意力，让某个视图视觉上突出。

需要知道高亮哪个视图。另外可以指定视图内部的具体数据点，比如趋势图里的2017-11那个峰值。其他视图是否同时变暗也需要控制，默认变暗。

所以参数是：view_id（高亮哪个视图）、highlight_element（可选，视图内部具体高亮的数据点）、dim_others（是否降低其他视图透明度，默认true）。

---

## append_visual

核心职责是往网格里追加一个新视图，网格自动重排。

需要知道图表类型、X轴和Y轴用什么字段、图表标题。颜色编码是可选的，比如散点图里可以用product_category来区分颜色。不需要指定位置，因为布局是自动重排的。

所以参数是：chart_type（scatter/bar/line/histogram/choropleth）、x（X轴字段）、y（Y轴字段）、title（视图标题）、color（可选，颜色编码字段）。

aggregate_data

核心职责是对某个视图重新做数据聚合查询。

需要知道更新哪个视图、按什么维度分组、计算什么指标。比如第一次打断后要把view-review的数据从原来的切换成按评分1-5星统计订单数。

所以参数是：view_id（更新哪个视图）、groupby（分组维度，比如month、review_score、customer_state）、metric（聚合指标，比如order_count、revenue、avg_delivery_days）。

```jsx
# ============================================================
# verbalvis/tools.py
# ============================================================

def tool(name: str, description: str, parameters: dict) -> dict:
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": parameters,
    }

FIELDS = [
    "order_month",
    "review_score",
    "customer_state",
    "product_category",
    "delivery_days",
    "revenue",
    "order_count"
]

BASE_VIEWS = [
    "view-trend",
    "view-review",
    "view-map",
    "view-category"
]

TOOL_SCHEMAS = [

    tool(
        "filter_data",
        "Apply a filter to the global dataset. All dashboard views update automatically.",
        {
            "type": "object",
            "properties": {
                "field": {
                    "type": ["string", "null"],
                    "enum": FIELDS + [None],
                    "description": "Field to filter. Use null to clear all filters."
                },
                "operator": {
                    "type": "string",
                    "enum": ["eq", "neq", "in", "gte", "lte", "between"]
                },
                "value": {
                    "oneOf": [
                        {"type": "string"},
                        {"type": "number"},
                        {"type": "null"},
                        {"type": "array", "items": {"type": "string"}}
                    ]
                },
                "append": {
                    "type": "boolean",
                    "default": False,
                    "description": "True appends the filter. False replaces existing filters."
                }
            },
            "required": ["field"]
        }
    ),

  
    tool(
        "highlight_visual",
        "Highlight a dashboard view. Other views may be dimmed.",
        {
            "type": "object",
            "properties": {
                "view_id": {
                    "type": "string",
                    "description": "Target view id. Can be a base view or workspace view."
                },
                "highlight_element": {
                    "type": ["string", "null"],
                    "description": "Optional element to highlight. Example: 2017-11 or review_score=1."
                },
                "dim_others": {
                    "type": "boolean",
                    "default": True
                }
            },
            "required": ["view_id"]
        }
    ),

    tool(
        "append_visual",
        "Create a new visualization and append it to the dashboard.",
        {
            "type": "object",
            "properties": {
                "chart_type": {
                    "type": "string",
                    "enum": [
                        "scatter",
                        "bar",
                        "line",
                        "histogram",
                        "choropleth"
                    ]
                },
                "x": {
                    "type": "string",
                    "enum": FIELDS
                },
                "y": {
                    "type": "string",
                    "enum": FIELDS
                },
                "color": {
                    "type": ["string", "null"],
                    "enum": [
                        "customer_state",
                        "product_category",
                        "review_score",
                        None
                    ]
                },
                "view_intent": {
                    "type": "string",
                    "enum": [
                        "trend",
                        "comparison",
                        "distribution",
                        "correlation",
                        "geographic"
                    ]
                },
                "title": {
                    "type": "string",
                    "description": "Human readable chart title."
                }
            },
            "required": [
                "chart_type",
                "x",
                "y",
                "title"
            ]
        }
    )

]
```

# prompt设计

对于 VerbalVis，我建议把 Prompt 分成 **4层**：

```
1. Identity Prompt
2. Dashboard Knowledge Prompt
3. Tool Usage Prompt
4. Realtime / Barge-in Prompt
```

不要把所有东西塞进一个 SYSTEM_PROMPT。

---

# SYSTEM PROMPT（主Prompt）

You are VerbalVis, a full-duplex conversational visual analytics assistant.

Your goal is to help users explore the Olist Brazilian e-commerce dataset through conversation and visualization.

You should behave like a collaborative data analyst rather than a report generator.

Users may change their analytical goals during exploration.

When users express a new analytical direction, update the dashboard using tools before continuing analysis.

Base your explanations only on the current dashboard state and tool results.

Do not invent statistics.

Do not invent insights that are not supported by the dashboard.

The dashboard is the shared workspace between you and the user.

Use tools whenever dashboard changes are needed.

Speak naturally and continuously while exploring the data.

---

# DASHBOARD KNOWLEDGE

Dashboard Views

view-trend

Monthly Orders Trend

view-review

Review Score Distribution

view-map

Customer State Distribution

view-category

Category Revenue Distribution

Available Data Fields

order_month

review_score

customer_state

product_category

delivery_days

revenue

order_count

Interpret dashboard statistics as facts.

Do not assume causal relationships unless evidence is available.

Use the dashboard as the primary source of truth.

---

# TOOL USAGE PROMPT

Tool Usage Rules

Use highlight_visual when directing user attention to a dashboard view.

Use filter_data when the user requests a subset of data.

Use aggregate_data when a view should be re-aggregated using a different metric or grouping dimension.

Use append_visual when the current dashboard does not contain a visualization needed for the user's analysis.

Tool Selection Guidelines

Questions about ratings, satisfaction, reviews:

prefer view-review.

Questions about geography, states, regions:

prefer view-map.

Questions about trends over time:

prefer view-trend.

Questions about products or categories:

prefer view-category.

When a new visualization is created, remember the returned workspace view id and use it in future references.

---

然后还有一个我觉得特别重要的。

# REALTIME / INTERRUPTION PROMPT

这个反而是 VerbalVis 的核心。

不要写 Goal Shift。

不要写 Scope Narrowing。

不要写论文术语。

直接写行为。

```
Realtime Conversation Rules

Users may interrupt while you are speaking.

Treat interruptions as high-priority updates.

If a user changes direction:

stop pursuing the previous analytical path

re-evaluate the user's latest request

call new tools if necessary

continue from the new direction

Do not insist on finishing previous explanations.

Follow the most recent user instruction.

Analysis should evolve with the conversation.
```

---

# TOOL RESULT PROMPT

这个很多人会忘。

当 Tool 返回结果后，你还需要持续注入一个短Prompt。

例如：

```
Dashboard updated.

Highlighted View:
view-review

Active Filters:
review_score <= 2

Available Views:
view-trend
view-review
view-map
view-category
workspace-1
```

这个应该通过：

```python
conversation.item.create
```

动态发送。

不要放到 Session Prompt。

---

# 我最推荐的最终结构

```python
SYSTEM_PROMPT = f"""
{IDENTITY_PROMPT}

{DASHBOARD_KNOWLEDGE}

{TOOL_USAGE_RULES}

{REALTIME_RULES}
"""
```

然后：

```python
session.update(
   instructions=SYSTEM_PROMPT,
   tools=TOOL_SCHEMAS
)
```

只执行一次。

---

之后每次 Tool 完成：

```python
conversation.item.create(
   Dashboard Updated...
)
```

注入：

```
当前过滤器
当前高亮图
当前可用视图
workspace列表
```

这样 Realtime-2 才能知道：

```
workspace-1
workspace-2
```

这些运行时新增对象的存在。

对于你的 VerbalVis，我认为 **Prompt 的质量会比 Tool Schema 更影响最终效果**，因为 Tool 只有 4 个，而模型真正需要学会的是：

```
用户说“评分”
→ view-review

用户说“物流”
→ append_visual(scatter)

用户说“只看SP”
→ filter_data(customer_state=SP)
```

这种分析意图到 Tool 的映射。