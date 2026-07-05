#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
同时处理 10 个 VerbalVis formative-study 日志，并生成一个汇总 TXT 报告。

无需命令行参数。使用方法：
1. pip install -U openai
2. PowerShell:
   $env:DASHSCOPE_API_KEY="你的百炼 API Key"
3. 直接运行：
   C:\Users\admin\miniconda3\envs\VerbalVis\python.exe `
     "F:\VerbalVis2\backend\formative study log\formative intent\run_10_logs_qwen37_report.py"

输出：
- formative_intent_revision_report.txt：完整总报告
- formative_intent_revision_results.json：结构化结果，便于审计

注意：
Qwen 结果是候选编码，不是未经复核的最终真值。
论文使用前必须人工核验每条用户原话、上下文和分类。
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from openai import OpenAI


# ============================================================
# 1. 只需根据你的电脑情况修改这一小段
# ============================================================

BASE_DIR = Path(
    r"F:\VerbalVis2\backend\formative study log\formative intent log"
)

MODEL = "qwen3.7-plus"
BASE_URL = os.getenv(
    "QWEN_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)
API_KEY_ENV = "sk-ws-H.RXMLMMI.snlW.MEUCIHx-oKToa5niaSK3UzFw7HWJ0qRyXUAq2ffZTJ2EG-TUAiEA9vkcFxME3EUdzH_a9QW95WJuasZxrFSDLVJ0o8cOfQ4"

# 同时处理的日志数量。为避免 API 限流，默认并发 3 个。
MAX_WORKERS = 3

# 单次请求的近似最大字符数；超长日志会自动分块。
MAX_CHARS_PER_CHUNK = 42_000
OVERLAP_EVENTS = 14
MAX_RETRIES = 4

REPORT_PATH = BASE_DIR / "formative_intent_revision_report.txt"
JSON_PATH = BASE_DIR / "formative_intent_revision_results.json"


# ============================================================
# 2. 提交给 Qwen3.7-Plus 的完整 Prompt
# ============================================================

SYSTEM_PROMPT = r"""
你是一名严谨的定性编码助手。请分析一份 VerbalVis 对话式可视分析日志，
识别真正的 analytical intent revision（分析意图修订）。

【输入格式】
输入是同一个日志文件中的 JSONL 事件，每条事件包含：
- line：原始日志行号
- ts：时间戳
- session_id：会话编号
- role："You" 表示用户，"AI" 表示系统
- text：原始话语

【判定原则】
一个 intent revision 必须同时具备：
1. 修订前存在一个仍然有效的 analytical commitment；
2. 用户的新话语取代、重定向、限定或实质性修改了该 commitment。

不得仅因为用户继续追问、换图、纠错、打断系统、执行下一步，或 AI 后来声称
“发生了目标转换/假设修正/范围变化”，就判定 revision。
分类必须由用户真实原话和当时上下文共同支持。

【三类 revision】

1. analytical_goal_shift
用户取代或实质性重定向主要分析问题、分析目的或希望获得的知识结果。
例如，从“分析订单量”转向“寻找低评分商品”。

不包括：
- 同一目标下新增图表、排序、比较或指标；
- 仅筛选到某个州；
- 仅纠正系统理解。

2. working_hypothesis_revision
用户拒绝、替换、限定、削弱、加强或实质性修改此前已存在的暂定解释、
因果猜测、预期或解释框架。

不包括：
- 第一次提出 hypothesis；
- 请求更多证据验证同一 hypothesis；
- AI 自己总结出旧 hypothesis，但用户从未表达或采纳；
- 只描述观察，没有修改解释。

3. analytical_scope_refinement
在较高层目标大体保持不变时，用户改变分析所适用的数据范围或约束，
包括地区、时间、品类、群体、变量、粒度、纳入/排除条件。
可以是缩小、扩大、替换范围或改变粒度。

不包括：
- 临时筛选但未改变后续 intended scope；
- 当前计划本来就要求顺序检查多个州，而用户只是执行下一步；
- 删除、恢复、排序或换图表。

【复合 revision】
同一 episode 可以包含多个类型。
必须选择一个 primary_type，并将其他类型放入 secondary_types。
类型计数采用多标签计数。

【必须排除】
以下通常不是 revision：
- method_or_representation_change：换图、排序、删除、恢复、布局调整；
- request_for_additional_evidence：继续索要证据；
- asr_or_entity_correction：纠正识别、州名、年份或品类；
- conversational_repair_or_clarification：纠正系统理解或图表错误；
- ordinary_follow_up：沿当前方向继续；
- non_analytical_barge_in：好的、嗯、停一下、说短一点；
- first_time_hypothesis：首次提出解释；
- experiment_logistics_or_off_task：实验时长、研究者交流、设备讨论；
- meta_level_summary_request：要求按“目标转换、假设修正、范围变化”总结；
- ambiguous_or_insufficient_context：上下文不足。

这些内容不要放入 revision_episodes。

【用户话语合并】
连续的多个 role="You" 事件可以属于同一个 utterance，条件是：
- 时间接近；
- 后一句是在补全或修复同一次请求；
- 中间没有实质性 AI 回应，或 AI 只有“好的/明白/是的”等短回应。

输出时不要把多条日志伪造成一条直接引语。
必须在 user_evidence 中逐条保留真实 text、line 和 ts。

【证据要求】
- 只能使用输入日志；
- user_evidence.text 必须逐字复制用户真实原话；
- 不得编造时间戳、用户动机、工具状态或旧 hypothesis；
- 每个 revision 必须给出非空 reason；
- reason 必须明确说明：
  1. 修订前的 active commitment 是什么；
  2. 用户的新话语改变了什么；
  3. 为什么这不是普通追问、换图、纠错或首次 hypothesis；
- confidence 为 0.00–1.00；
- 有疑问时 requires_human_review=true；
- timing 只能使用：
  - during_assistant_speech
  - after_speech_before_tool_completion
  - during_tool_execution
  - after_dashboard_commitment
  - ordinary_turn_boundary
  - unknown
- 仅凭相邻时间戳不能证明 mid-speech barge-in。

【输出】
只返回一个可被 json.loads() 解析的 JSON 对象，不要 Markdown，不要额外说明：

{
  "session_id": "session id",
  "revision_episodes": [
    {
      "line_start": 1,
      "line_end": 2,
      "timestamp_start": "原时间戳或 null",
      "timestamp_end": "原时间戳或 null",
      "user_evidence": [
        {
          "line": 1,
          "ts": "原时间戳或 null",
          "text": "逐字复制的用户原话"
        }
      ],
      "prior_active_commitment": "修订前的目标、解释或范围",
      "revised_commitment": "修订后的目标、解释或范围",
      "primary_type": "analytical_goal_shift",
      "secondary_types": [
        "analytical_scope_refinement"
      ],
      "revision_relation": "supersedes/redirects/qualifies/narrows/broadens/substitutes/changes_granularity/mixed",
      "reason": "必须非空，简洁说明旧 commitment、新变化以及边界区分",
      "timing": "unknown",
      "confidence": 0.90,
      "requires_human_review": false
    }
  ],
  "notes": "数据质量或上下文不足说明；没有则为空字符串"
}

约束：
- primary_type 只允许：
  - analytical_goal_shift
  - working_hypothesis_revision
  - analytical_scope_refinement
- secondary_types 只能包含上述三类，且不得重复 primary_type；
- 没有 revision 时 revision_episodes 必须为 []；
- 不要输出普通回合或非 revision；
- 每个 revision 的 reason 不得为空。
""".strip()


REVISION_TYPES = {
    "analytical_goal_shift",
    "working_hypothesis_revision",
    "analytical_scope_refinement",
}

TIMING_VALUES = {
    "during_assistant_speech",
    "after_speech_before_tool_completion",
    "during_tool_execution",
    "after_dashboard_commitment",
    "ordinary_turn_boundary",
    "unknown",
}

RELATION_VALUES = {
    "supersedes",
    "redirects",
    "qualifies",
    "narrows",
    "broadens",
    "substitutes",
    "changes_granularity",
    "mixed",
}


@dataclass(frozen=True)
class Event:
    line: int
    ts: str | None
    session_id: str
    role: str
    text: str


@dataclass(frozen=True)
class Chunk:
    index: int
    events: tuple[Event, ...]


def candidate_names(index: int) -> list[str]:
    """兼容全角/半角括号和几种常见命名方式。"""
    number = f"{index:02d}"
    return [
        f"conversation.jsonl（{number}）",
        f"conversation.jsonl({number})",
        f"conversation（{number}）.jsonl",
        f"conversation({number}).jsonl",
        f"conversation_{number}.jsonl",
        f"conversation-{number}.jsonl",
        f"conversation {number}.jsonl",
    ]


def resolve_log_files() -> tuple[list[Path], list[str]]:
    found: list[Path] = []
    warnings: list[str] = []
    used: set[Path] = set()

    all_files = [path for path in BASE_DIR.iterdir() if path.is_file()]

    for index in range(1, 11):
        selected: Path | None = None

        for name in candidate_names(index):
            candidate = BASE_DIR / name
            if candidate.is_file():
                selected = candidate
                break

        if selected is None:
            number = f"{index:02d}"
            # 宽松匹配：文件名中同时包含 conversation 和两位序号。
            matches = [
                path for path in all_files
                if "conversation" in path.name.lower()
                and re.search(rf"(?<!\d){number}(?!\d)", path.name)
                and path not in used
            ]
            if len(matches) == 1:
                selected = matches[0]
            elif len(matches) > 1:
                matches.sort(key=lambda p: len(p.name))
                selected = matches[0]
                warnings.append(
                    f"序号 {number} 匹配到多个文件，自动选择：{selected.name}"
                )

        if selected is None:
            warnings.append(f"未找到第 {index:02d} 个日志")
        else:
            found.append(selected)
            used.add(selected)

    return found, warnings


def read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "utf-16"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeError:
            continue
    raise RuntimeError(f"无法解码文件：{path}")


def parse_events(path: Path) -> tuple[list[Event], list[str]]:
    events: list[Event] = []
    warnings: list[str] = []

    for line_number, raw_line in enumerate(read_text(path).splitlines(), start=1):
        if not raw_line.strip():
            continue

        try:
            obj = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            warnings.append(
                f"{path.name}:{line_number} JSON 格式错误，已跳过：{exc.msg}"
            )
            continue

        if not isinstance(obj, dict):
            warnings.append(f"{path.name}:{line_number} 不是 JSON object，已跳过")
            continue

        role = obj.get("role")
        text = obj.get("text")
        if not isinstance(role, str) or not isinstance(text, str):
            warnings.append(
                f"{path.name}:{line_number} 缺少 role 或 text，已跳过"
            )
            continue

        events.append(
            Event(
                line=line_number,
                ts=str(obj["ts"]) if obj.get("ts") is not None else None,
                session_id=str(obj.get("session_id") or "unknown-session"),
                role=role,
                text=text,
            )
        )

    return events, warnings


def serialize_event(event: Event) -> str:
    return json.dumps(
        {
            "line": event.line,
            "ts": event.ts,
            "session_id": event.session_id,
            "role": event.role,
            "text": event.text,
        },
        ensure_ascii=False,
    )


def make_chunks(events: list[Event]) -> list[Chunk]:
    if not events:
        return []

    chunks: list[Chunk] = []
    start = 0
    index = 1

    while start < len(events):
        end = start
        chars = 0

        while end < len(events):
            size = len(serialize_event(events[end])) + 1
            if end > start and chars + size > MAX_CHARS_PER_CHUNK:
                break
            chars += size
            end += 1

        chunks.append(Chunk(index=index, events=tuple(events[start:end])))

        if end >= len(events):
            break

        start = max(start + 1, end - OVERLAP_EVENTS)
        index += 1

    return chunks


def strip_fence(text: str) -> str:
    value = text.strip()
    value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s*```$", "", value)
    return value.strip()


def parse_json_response(text: str) -> dict[str, Any]:
    cleaned = strip_fence(text)

    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError:
        first = cleaned.find("{")
        last = cleaned.rfind("}")
        if first < 0 or last <= first:
            raise
        obj = json.loads(cleaned[first:last + 1])

    if not isinstance(obj, dict):
        raise ValueError("模型返回内容不是 JSON object")
    return obj


def make_user_message(file_name: str, chunk: Chunk) -> str:
    body = "\n".join(serialize_event(event) for event in chunk.events)
    sessions = sorted({event.session_id for event in chunk.events})

    return (
        f"日志文件：{file_name}\n"
        f"chunk_index：{chunk.index}\n"
        f"session_id：{', '.join(sessions)}\n"
        f"line_range：{chunk.events[0].line}-{chunk.events[-1].line}\n\n"
        "----- BEGIN LOG -----\n"
        f"{body}\n"
        "----- END LOG -----\n\n"
        "请只输出符合 system prompt schema 的 JSON。"
    )


def call_qwen(
    client: OpenAI,
    file_name: str,
    chunk: Chunk,
) -> dict[str, Any]:
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": make_user_message(file_name, chunk),
                    },
                ],
                temperature=0,
                max_tokens=8_000,
                response_format={"type": "json_object"},
                extra_body={"enable_thinking": False},
            )

            content = response.choices[0].message.content
            if not content:
                raise RuntimeError("模型返回空内容")
            return parse_json_response(content)

        except Exception as exc:
            last_error = exc
            if attempt == MAX_RETRIES:
                break
            time.sleep(min(2 ** (attempt - 1), 8))

    raise RuntimeError(
        f"{file_name} chunk {chunk.index} 调用失败：{last_error}"
    )


def clamp_confidence(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, number))


def clean_episode(
    raw: Any,
    file_path: Path,
    event_by_line: dict[int, Event],
) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None

    primary = raw.get("primary_type")
    if primary not in REVISION_TYPES:
        return None

    evidence_raw = raw.get("user_evidence")
    if not isinstance(evidence_raw, list):
        return None

    evidence: list[dict[str, Any]] = []

    for item in evidence_raw:
        if not isinstance(item, dict):
            continue

        try:
            line = int(item.get("line"))
        except (TypeError, ValueError):
            continue

        source = event_by_line.get(line)
        if source is None or source.role != "You":
            continue

        # 用户真实原话必须与日志逐字相同。
        if item.get("text") != source.text:
            continue

        evidence.append(
            {
                "line": line,
                "ts": source.ts,
                "text": source.text,
            }
        )

    if not evidence:
        return None

    evidence.sort(key=lambda item: item["line"])
    line_start = evidence[0]["line"]
    line_end = evidence[-1]["line"]

    secondary_raw = raw.get("secondary_types")
    if not isinstance(secondary_raw, list):
        secondary_raw = []

    secondary = [
        item for item in secondary_raw
        if item in REVISION_TYPES and item != primary
    ]
    secondary = list(dict.fromkeys(secondary))

    relation = raw.get("revision_relation")
    if relation not in RELATION_VALUES:
        relation = "mixed"

    timing = raw.get("timing")
    if timing not in TIMING_VALUES:
        timing = "unknown"

    reason = raw.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        reason = (
            "模型未提供完整判定原因；该条必须人工复核后方可用于研究报告。"
        )
        requires_review = True
    else:
        reason = reason.strip()
        requires_review = bool(raw.get("requires_human_review", False))

    session_ids = {
        event_by_line[item["line"]].session_id for item in evidence
    }

    return {
        "file": file_path.name,
        "file_path": str(file_path),
        "session_id": (
            next(iter(session_ids))
            if len(session_ids) == 1
            else ", ".join(sorted(session_ids))
        ),
        "line_start": line_start,
        "line_end": line_end,
        "timestamp_start": evidence[0]["ts"],
        "timestamp_end": evidence[-1]["ts"],
        "user_evidence": evidence,
        "prior_active_commitment": raw.get("prior_active_commitment"),
        "revised_commitment": raw.get("revised_commitment"),
        "primary_type": primary,
        "secondary_types": secondary,
        "revision_relation": relation,
        "reason": reason,
        "timing": timing,
        "confidence": clamp_confidence(raw.get("confidence")),
        "requires_human_review": requires_review,
    }


def episode_key(episode: dict[str, Any]) -> tuple[Any, ...]:
    evidence_key = tuple(
        (item["line"], item["text"])
        for item in episode["user_evidence"]
    )
    all_types = tuple(
        sorted([episode["primary_type"], *episode["secondary_types"]])
    )
    return (
        episode["file"],
        episode["session_id"],
        evidence_key,
        all_types,
    )


def deduplicate(episodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[tuple[Any, ...], dict[str, Any]] = {}

    for episode in episodes:
        key = episode_key(episode)
        previous = best.get(key)

        if previous is None:
            best[key] = episode
        elif episode["confidence"] > previous["confidence"]:
            best[key] = episode

    return sorted(
        best.values(),
        key=lambda item: (
            item["file"],
            item["line_start"],
            item["line_end"],
        ),
    )


def process_one_file(
    file_path: Path,
    api_key: str,
) -> dict[str, Any]:
    events, warnings = parse_events(file_path)

    if not events:
        return {
            "file": file_path.name,
            "status": "failed",
            "error": "没有可处理的有效日志事件",
            "warnings": warnings,
            "episodes": [],
            "notes": [],
        }

    client = OpenAI(api_key=api_key, base_url=BASE_URL)
    chunks = make_chunks(events)
    all_episodes: list[dict[str, Any]] = []
    notes: list[str] = []

    for chunk in chunks:
        result = call_qwen(client, file_path.name, chunk)

        note = result.get("notes")
        if isinstance(note, str) and note.strip():
            notes.append(f"chunk {chunk.index}: {note.strip()}")

        event_by_line = {event.line: event for event in chunk.events}
        raw_episodes = result.get("revision_episodes", [])

        if isinstance(raw_episodes, list):
            for raw in raw_episodes:
                cleaned = clean_episode(
                    raw=raw,
                    file_path=file_path,
                    event_by_line=event_by_line,
                )
                if cleaned is not None:
                    all_episodes.append(cleaned)

    episodes = deduplicate(all_episodes)

    return {
        "file": file_path.name,
        "file_path": str(file_path),
        "status": "ok",
        "error": None,
        "warnings": warnings,
        "notes": notes,
        "event_count": len(events),
        "chunk_count": len(chunks),
        "episodes": episodes,
    }


def count_types(episodes: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()

    for episode in episodes:
        counts[episode["primary_type"]] += 1
        counts.update(episode["secondary_types"])

    return counts


def safe(value: Any) -> str:
    if value is None or value == "":
        return "N/A"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "N/A"
    return str(value)


def create_report(
    results: list[dict[str, Any]],
    discovery_warnings: list[str],
) -> str:
    successful = [result for result in results if result["status"] == "ok"]
    failed = [result for result in results if result["status"] != "ok"]

    all_episodes = deduplicate(
        [
            episode
            for result in successful
            for episode in result["episodes"]
        ]
    )

    overall_counts = count_types(all_episodes)
    compound_count = sum(
        1 for episode in all_episodes if episode["secondary_types"]
    )
    review_count = sum(
        1 for episode in all_episodes
        if episode["requires_human_review"]
    )

    lines: list[str] = [
        "FORMATIVE STUDY — ANALYTICAL INTENT REVISION REPORT",
        "=" * 88,
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        f"Model: {MODEL}",
        f"Input directory: {BASE_DIR}",
        "",
        "IMPORTANT",
        "-" * 88,
        "本报告中的结果是 Qwen3.7-Plus 生成的候选编码。",
        "用于论文前，研究者必须逐条核验用户原话、上下文、类型和判定原因。",
        "",
        "1. OVERALL STATISTICS",
        "-" * 88,
        f"Expected log files: 10",
        f"Successfully processed: {len(successful)}",
        f"Failed or missing: {10 - len(successful)}",
        f"Total unique intent-revision episodes: {len(all_episodes)}",
        (
            "Analytical Goal Shift: "
            f"{overall_counts['analytical_goal_shift']}"
        ),
        (
            "Working-Hypothesis Revision: "
            f"{overall_counts['working_hypothesis_revision']}"
        ),
        (
            "Analytical Scope Refinement: "
            f"{overall_counts['analytical_scope_refinement']}"
        ),
        f"Compound revision episodes: {compound_count}",
        f"Episodes requiring human review: {review_count}",
        "",
        "Counting note:",
        "三类数量采用多标签计数。因此，一个复合 revision 可以同时计入两个或三个类别，",
        "三类数量之和可能大于总 revision episode 数。",
        "",
        "2. PER-LOG STATISTICS",
        "-" * 88,
    ]

    for result in sorted(results, key=lambda item: item["file"]):
        if result["status"] != "ok":
            lines.append(
                f"{result['file']}: FAILED — {safe(result.get('error'))}"
            )
            continue

        episodes = result["episodes"]
        counts = count_types(episodes)
        compounds = sum(1 for ep in episodes if ep["secondary_types"])

        lines.append(
            f"{result['file']}: "
            f"total={len(episodes)}, "
            f"goal={counts['analytical_goal_shift']}, "
            f"hypothesis={counts['working_hypothesis_revision']}, "
            f"scope={counts['analytical_scope_refinement']}, "
            f"compound={compounds}"
        )

    lines.extend(["", "3. DETAILED REVISION EPISODES", "=" * 88, ""])

    global_index = 1

    for result in sorted(successful, key=lambda item: item["file"]):
        episodes = result["episodes"]

        lines.extend(
            [
                f"LOG: {result['file']}",
                "#" * 88,
                f"Path: {result['file_path']}",
                f"Valid events: {result.get('event_count', 0)}",
                f"Chunks: {result.get('chunk_count', 0)}",
                f"Revision episodes: {len(episodes)}",
                "",
            ]
        )

        if not episodes:
            lines.extend(["No revision candidate was identified.", ""])
            continue

        for episode in episodes:
            all_types = [
                episode["primary_type"],
                *episode["secondary_types"],
            ]

            lines.extend(
                [
                    f"REVISION {global_index:03d}",
                    "-" * 88,
                    f"Session: {episode['session_id']}",
                    f"Lines: {episode['line_start']}-{episode['line_end']}",
                    (
                        f"Time: {safe(episode['timestamp_start'])} "
                        f"-> {safe(episode['timestamp_end'])}"
                    ),
                    "User's exact utterance(s):",
                ]
            )

            for quote in episode["user_evidence"]:
                lines.append(
                    f"  [{quote['line']}] {safe(quote['ts'])} | "
                    f"{quote['text']}"
                )

            lines.extend(
                [
                    f"Primary type: {episode['primary_type']}",
                    f"Secondary types: {safe(episode['secondary_types'])}",
                    f"All counted types: {', '.join(all_types)}",
                    f"Revision relation: {episode['revision_relation']}",
                    (
                        "Prior active commitment: "
                        f"{safe(episode['prior_active_commitment'])}"
                    ),
                    (
                        "Revised commitment: "
                        f"{safe(episode['revised_commitment'])}"
                    ),
                    f"Reason: {episode['reason']}",
                    f"Timing: {episode['timing']}",
                    f"Confidence: {episode['confidence']:.2f}",
                    (
                        "Requires human review: "
                        f"{episode['requires_human_review']}"
                    ),
                    "",
                ]
            )

            global_index += 1

    all_warnings = list(discovery_warnings)

    for result in results:
        for warning in result.get("warnings", []):
            all_warnings.append(warning)
        for note in result.get("notes", []):
            all_warnings.append(f"{result['file']}: {note}")
        if result["status"] != "ok" and result.get("error"):
            all_warnings.append(
                f"{result['file']}: {result['error']}"
            )

    if all_warnings:
        lines.extend(["4. WARNINGS AND NOTES", "=" * 88, ""])
        lines.extend(f"- {item}" for item in all_warnings)
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    api_key = "sk-ws-H.RXMLMMI.snlW.MEUCIHx-oKToa5niaSK3UzFw7HWJ0qRyXUAq2ffZTJ2EG-TUAiEA9vkcFxME3EUdzH_a9QW95WJuasZxrFSDLVJ0o8cOfQ4"
    if not api_key:
        print(
            f"ERROR: 请先设置环境变量 {API_KEY_ENV}。",
            file=sys.stderr,
        )
        print(
            'PowerShell 示例：$env:DASHSCOPE_API_KEY="你的 API Key"',
            file=sys.stderr,
        )
        return 2

    if not BASE_DIR.is_dir():
        print(f"ERROR: 日志目录不存在：{BASE_DIR}", file=sys.stderr)
        return 2

    log_files, discovery_warnings = resolve_log_files()

    if not log_files:
        print("ERROR: 没有找到任何日志文件。", file=sys.stderr)
        return 2

    print(f"找到 {len(log_files)} 个日志，开始并行处理……")
    for path in log_files:
        print(f"  - {path.name}")

    results: list[dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_path = {
            executor.submit(process_one_file, path, api_key): path
            for path in log_files
        }

        completed = 0

        for future in as_completed(future_to_path):
            path = future_to_path[future]
            completed += 1

            try:
                result = future.result()
            except Exception as exc:
                result = {
                    "file": path.name,
                    "file_path": str(path),
                    "status": "failed",
                    "error": str(exc),
                    "warnings": [],
                    "notes": [],
                    "episodes": [],
                }

            results.append(result)

            if result["status"] == "ok":
                print(
                    f"[{completed}/{len(log_files)}] 完成 {path.name}: "
                    f"{len(result['episodes'])} revisions"
                )
            else:
                print(
                    f"[{completed}/{len(log_files)}] 失败 {path.name}: "
                    f"{result.get('error')}"
                )

    # 把缺失文件也加入结果，保证报告明确显示是否处理满 10 个。
    discovered_names = {path.name for path in log_files}
    for warning in discovery_warnings:
        match = re.search(r"第 (\d{2}) 个日志", warning)
        missing_name = (
            f"conversation log {match.group(1)}"
            if match else "missing log"
        )
        results.append(
            {
                "file": missing_name,
                "status": "failed",
                "error": warning,
                "warnings": [],
                "notes": [],
                "episodes": [],
            }
        )

    report_text = create_report(results, discovery_warnings)

    REPORT_PATH.write_text(report_text, encoding="utf-8")
    JSON_PATH.write_text(
        json.dumps(
            {
                "model": MODEL,
                "input_directory": str(BASE_DIR),
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    successful_episodes = [
        episode
        for result in results
        if result["status"] == "ok"
        for episode in result["episodes"]
    ]
    successful_episodes = deduplicate(successful_episodes)
    counts = count_types(successful_episodes)

    print("")
    print("处理完成。")
    print(f"总 revision 数：{len(successful_episodes)}")
    print(
        "Goal Shift："
        f"{counts['analytical_goal_shift']}"
    )
    print(
        "Working-Hypothesis Revision："
        f"{counts['working_hypothesis_revision']}"
    )
    print(
        "Analytical Scope Refinement："
        f"{counts['analytical_scope_refinement']}"
    )
    print(f"TXT 总报告：{REPORT_PATH}")
    print(f"JSON 审计结果：{JSON_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
