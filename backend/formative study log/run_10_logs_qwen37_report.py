#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
Run Qwen3.7-Plus intent-revision coding for .log files only.

This script is intentionally located inside:
F:\VerbalVis2\backend\formative study log\formative intent log

Rules:
- Only direct *.log files in this same directory are processed.
- .jsonl files are never discovered or processed.
- One complete .log file = one Qwen request.
- Up to 32 requests are sent concurrently by default.
- The TXT report and JSON audit file are written to this same directory.

PowerShell:
  $env:DASHSCOPE_API_KEY="your DashScope API key"
  C:\Users\admin\miniconda3\python.exe `
    "F:\VerbalVis2\backend\formative study log\formative intent log\run_10_logs_qwen37_report.py"

Useful check:
  C:\Users\admin\miniconda3\python.exe `
    "F:\VerbalVis2\backend\formative study log\formative intent log\run_10_logs_qwen37_report.py" --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore[assignment]


SCRIPT_DIR = Path(__file__).resolve().parent
LOG_DIR = SCRIPT_DIR
PROMPT_PATH = SCRIPT_DIR / "qwen37_intent_revision_prompt_final.txt"

MODEL = os.getenv("QWEN_MODEL", "qwen3.7-plus")
BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
API_KEY_ENV_NAMES = ("DASHSCOPE_API_KEY", "QWEN_API_KEY")

LOG_PATTERN = "*.log"
MAX_WORKERS = int(os.getenv("QWEN_MAX_WORKERS", "32"))
MAX_RETRIES = 4
MAX_TOKENS = int(os.getenv("QWEN_MAX_TOKENS", "12000"))

REPORT_NAME = "formative_intent_log_revision_report.txt"
JSON_NAME = "formative_intent_log_revision_results.json"

TURN_RE = re.compile(r"^(\d{1,2}:\d{2}:\d{2}(?:\.\d{1,6})?)\s+(AI|You):\s?(.*)$")

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
    line_end: int
    ts: str | None
    role: str
    text: str


def read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "utf-16"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeError:
            continue
    raise RuntimeError(f"Cannot decode file: {path}")


def load_prompt() -> str:
    if not PROMPT_PATH.is_file():
        raise FileNotFoundError(f"Prompt file not found: {PROMPT_PATH}")
    prompt = PROMPT_PATH.read_text(encoding="utf-8").strip()
    if not prompt:
        raise ValueError(f"Prompt file is empty: {PROMPT_PATH}")
    return prompt


def get_api_key() -> str | None:
    for name in API_KEY_ENV_NAMES:
        value = os.getenv(name)
        if value:
            return value
    return None


def discover_logs(log_dir: Path, pattern: str) -> list[Path]:
    return sorted(
        (path for path in log_dir.glob(pattern) if path.is_file() and path.suffix.lower() == ".log"),
        key=lambda path: path.name.lower(),
    )


def parse_events(path: Path) -> tuple[list[Event], list[str]]:
    events: list[Event] = []
    warnings: list[str] = []
    current: dict[str, Any] | None = None

    def flush_current() -> None:
        nonlocal current
        if current is None:
            return

        text = "\n".join(current["parts"]).strip()
        events.append(
            Event(
                line=current["line"],
                line_end=current["line_end"],
                ts=current["ts"],
                role=current["role"],
                text=text,
            )
        )
        current = None

    for line_number, raw_line in enumerate(read_text(path).splitlines(), start=1):
        match = TURN_RE.match(raw_line)
        if match:
            flush_current()
            current = {
                "line": line_number,
                "line_end": line_number,
                "ts": match.group(1),
                "role": match.group(2),
                "parts": [match.group(3)],
            }
            continue

        if current is not None:
            current["parts"].append(raw_line)
            current["line_end"] = line_number
        elif raw_line.strip():
            warnings.append(f"{path.name}:{line_number} skipped non-turn line")

    flush_current()
    return events, warnings


def serialize_event(event: Event) -> str:
    return json.dumps(
        {
            "line": event.line,
            "line_end": event.line_end,
            "ts": event.ts,
            "role": event.role,
            "text": event.text,
        },
        ensure_ascii=False,
    )


def make_user_message(file_path: Path, events: list[Event]) -> str:
    body = "\n".join(serialize_event(event) for event in events) or "(no parseable AI/You turns)"
    user_turns = sum(1 for event in events if event.role == "You")
    ai_turns = sum(1 for event in events if event.role == "AI")

    return (
        f"Log file: {file_path.name}\n"
        f"Original path: {file_path}\n"
        f"Normalized events: {len(events)}\n"
        f"User events: {user_turns}\n"
        f"AI events: {ai_turns}\n\n"
        "Each JSON line below is one normalized event from the same complete .log file.\n"
        "The line and line_end fields are original raw log line numbers.\n"
        "For each candidate user utterance, classify only from context before that utterance.\n"
        "Do not use later AI summaries or later user reactions to infer an earlier label.\n\n"
        "----- BEGIN COMPLETE LOG -----\n"
        f"{body}\n"
        "----- END COMPLETE LOG -----\n\n"
        "Return only one JSON object matching the required schema."
    )


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
        obj = json.loads(cleaned[first : last + 1])

    if not isinstance(obj, dict):
        raise ValueError("Model response is not a JSON object")
    return obj


def call_qwen(client: Any, system_prompt: str, file_path: Path, events: list[Event]) -> dict[str, Any]:
    user_message = make_user_message(file_path, events)
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0,
                max_tokens=MAX_TOKENS,
                response_format={"type": "json_object"},
                extra_body={"enable_thinking": False},
            )
            content = response.choices[0].message.content
            if not content:
                raise RuntimeError("Model returned empty content")
            return parse_json_response(content)
        except Exception as exc:
            last_error = exc
            if attempt == MAX_RETRIES:
                break
            time.sleep(min(2 ** (attempt - 1), 8))

    raise RuntimeError(f"{file_path.name} Qwen call failed: {last_error}")


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
    validation_notes: list[str],
) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        validation_notes.append(f"{file_path.name}: dropped non-object episode")
        return None

    primary = raw.get("primary_type")
    if primary not in REVISION_TYPES:
        validation_notes.append(f"{file_path.name}: dropped invalid primary_type={primary!r}")
        return None

    evidence_raw = raw.get("user_evidence")
    if not isinstance(evidence_raw, list):
        validation_notes.append(f"{file_path.name}: dropped episode without user_evidence list")
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
        if source is None:
            validation_notes.append(f"{file_path.name}: evidence line {line} not found")
            continue
        if source.role != "You":
            validation_notes.append(f"{file_path.name}: evidence line {line} is not a user turn")
            continue
        if item.get("text") != source.text:
            validation_notes.append(f"{file_path.name}: evidence text mismatch at line {line}")
            continue

        evidence.append({"line": line, "ts": source.ts, "text": source.text})

    if not evidence:
        validation_notes.append(f"{file_path.name}: dropped episode because exact user evidence did not validate")
        return None

    evidence.sort(key=lambda item: item["line"])

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
    requires_review = bool(raw.get("requires_human_review", False))
    if not isinstance(reason, str) or not reason.strip():
        reason = "Model did not provide a non-empty reason; human review is required."
        requires_review = True
    else:
        reason = reason.strip()

    prior = raw.get("prior_active_commitment")
    revised = raw.get("revised_commitment")
    if not isinstance(prior, str) or not prior.strip():
        prior = ""
        requires_review = True
    if not isinstance(revised, str) or not revised.strip():
        revised = ""
        requires_review = True

    return {
        "file": file_path.name,
        "file_path": str(file_path),
        "line_start": evidence[0]["line"],
        "line_end": evidence[-1]["line"],
        "timestamp_start": evidence[0]["ts"],
        "timestamp_end": evidence[-1]["ts"],
        "user_evidence": evidence,
        "prior_active_commitment": prior,
        "revised_commitment": revised,
        "primary_type": primary,
        "secondary_types": secondary,
        "revision_relation": relation,
        "reason": reason,
        "timing": timing,
        "confidence": clamp_confidence(raw.get("confidence")),
        "requires_human_review": requires_review,
    }


def episode_key(episode: dict[str, Any]) -> tuple[Any, ...]:
    evidence_key = tuple((item["line"], item["text"]) for item in episode["user_evidence"])
    types_key = tuple(sorted([episode["primary_type"], *episode["secondary_types"]]))
    return episode["file"], evidence_key, types_key


def deduplicate(episodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[tuple[Any, ...], dict[str, Any]] = {}
    for episode in episodes:
        key = episode_key(episode)
        previous = best.get(key)
        if previous is None or episode["confidence"] > previous["confidence"]:
            best[key] = episode
    return sorted(best.values(), key=lambda item: (item["file"], item["line_start"], item["line_end"]))


def process_one_file(file_path: Path, api_key: str, system_prompt: str) -> dict[str, Any]:
    events, warnings = parse_events(file_path)

    if OpenAI is None:
        raise RuntimeError("The openai package is not installed. Run: pip install -U openai")

    client = OpenAI(api_key=api_key, base_url=BASE_URL)
    result = call_qwen(client, system_prompt, file_path, events)

    notes: list[str] = []
    model_notes = result.get("notes")
    if isinstance(model_notes, str) and model_notes.strip():
        notes.append(model_notes.strip())

    raw_episodes = result.get("revision_episodes", [])
    if not isinstance(raw_episodes, list):
        raw_episodes = []
        notes.append("revision_episodes was not a list")

    event_by_line = {event.line: event for event in events}
    episodes: list[dict[str, Any]] = []
    for raw in raw_episodes:
        cleaned = clean_episode(raw, file_path, event_by_line, notes)
        if cleaned is not None:
            episodes.append(cleaned)

    return {
        "file": file_path.name,
        "file_path": str(file_path),
        "status": "ok",
        "error": None,
        "warnings": warnings,
        "notes": notes,
        "event_count": len(events),
        "user_event_count": sum(1 for event in events if event.role == "You"),
        "ai_event_count": sum(1 for event in events if event.role == "AI"),
        "episodes": deduplicate(episodes),
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


def create_report(results: list[dict[str, Any]], log_dir: Path, max_workers: int) -> str:
    ok_results = [result for result in results if result["status"] == "ok"]
    failed_results = [result for result in results if result["status"] != "ok"]
    all_episodes = deduplicate([episode for result in ok_results for episode in result["episodes"]])

    counts = count_types(all_episodes)
    compound_count = sum(1 for episode in all_episodes if episode["secondary_types"])
    review_count = sum(1 for episode in all_episodes if episode["requires_human_review"])

    lines: list[str] = [
        "FORMATIVE STUDY - ANALYTICAL INTENT REVISION REPORT",
        "=" * 88,
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        f"Model: {MODEL}",
        f"Input directory: {log_dir}",
        f"Processed file pattern: {LOG_PATTERN}",
        f"Prompt: {PROMPT_PATH}",
        f"Max concurrent requests: {max_workers}",
        "",
        "IMPORTANT",
        "-" * 88,
        "本报告中的结果是 Qwen 生成的候选编码。",
        "用于论文或正式分析前，请逐条人工核验用户原话、上下文、类型和判定理由。",
        "",
        "1. OVERALL STATISTICS",
        "-" * 88,
        f"Discovered .log files: {len(results)}",
        f"Successfully processed: {len(ok_results)}",
        f"Failed: {len(failed_results)}",
        f"Total unique intent-revision episodes: {len(all_episodes)}",
        f"Analytical Goal Shift: {counts['analytical_goal_shift']}",
        f"Working-Hypothesis Revision: {counts['working_hypothesis_revision']}",
        f"Analytical Scope Refinement: {counts['analytical_scope_refinement']}",
        f"Compound revision episodes: {compound_count}",
        f"Episodes requiring human review: {review_count}",
        "",
        "Counting note:",
        "三类数量采用多标签计数。一个 compound revision 可能同时计入两个或三个类型。",
        "",
        "2. PER-LOG STATISTICS",
        "-" * 88,
    ]

    for result in sorted(results, key=lambda item: item["file"].lower()):
        if result["status"] != "ok":
            lines.append(f"{result['file']}: FAILED - {safe(result.get('error'))}")
            continue

        episodes = result["episodes"]
        local_counts = count_types(episodes)
        compounds = sum(1 for episode in episodes if episode["secondary_types"])
        lines.append(
            f"{result['file']}: total={len(episodes)}, "
            f"goal={local_counts['analytical_goal_shift']}, "
            f"hypothesis={local_counts['working_hypothesis_revision']}, "
            f"scope={local_counts['analytical_scope_refinement']}, "
            f"compound={compounds}, "
            f"events={result.get('event_count', 0)}, "
            f"user_events={result.get('user_event_count', 0)}"
        )

    lines.extend(["", "3. DETAILED REVISION EPISODES", "=" * 88, ""])
    global_index = 1

    for result in sorted(ok_results, key=lambda item: item["file"].lower()):
        episodes = result["episodes"]
        lines.extend(
            [
                f"LOG: {result['file']}",
                "#" * 88,
                f"Path: {result['file_path']}",
                f"Valid events: {result.get('event_count', 0)}",
                f"Revision episodes: {len(episodes)}",
                "",
            ]
        )

        if not episodes:
            lines.extend(["No revision candidate was identified.", ""])
            continue

        for episode in episodes:
            all_types = [episode["primary_type"], *episode["secondary_types"]]
            lines.extend(
                [
                    f"REVISION {global_index:03d}",
                    "-" * 88,
                    f"Lines: {episode['line_start']}-{episode['line_end']}",
                    f"Time: {safe(episode['timestamp_start'])} -> {safe(episode['timestamp_end'])}",
                    "User exact utterance(s):",
                ]
            )

            for quote in episode["user_evidence"]:
                lines.append(f"  [{quote['line']}] {safe(quote['ts'])} | {quote['text']}")

            lines.extend(
                [
                    f"Primary type: {episode['primary_type']}",
                    f"Secondary types: {safe(episode['secondary_types'])}",
                    f"All counted types: {', '.join(all_types)}",
                    f"Revision relation: {episode['revision_relation']}",
                    f"Prior active commitment: {safe(episode['prior_active_commitment'])}",
                    f"Revised commitment: {safe(episode['revised_commitment'])}",
                    f"Reason: {episode['reason']}",
                    f"Timing: {episode['timing']}",
                    f"Confidence: {episode['confidence']:.2f}",
                    f"Requires human review: {episode['requires_human_review']}",
                    "",
                ]
            )
            global_index += 1

    warnings: list[str] = []
    for result in sorted(results, key=lambda item: item["file"].lower()):
        warnings.extend(result.get("warnings", []))
        warnings.extend(f"{result['file']}: {note}" for note in result.get("notes", []))
        if result["status"] != "ok" and result.get("error"):
            warnings.append(f"{result['file']}: {result['error']}")

    if warnings:
        lines.extend(["4. WARNINGS AND NOTES", "=" * 88, ""])
        lines.extend(f"- {warning}" for warning in warnings)
        lines.append("")

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Qwen intent-revision coding on .log files only.")
    parser.add_argument("--max-workers", type=int, default=MAX_WORKERS)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    max_workers = max(1, args.max_workers)

    log_files = discover_logs(LOG_DIR, LOG_PATTERN)
    if args.limit is not None:
        log_files = log_files[: args.limit]

    if not log_files:
        print(f"ERROR: no .log files matched {LOG_PATTERN!r} under {LOG_DIR}", file=sys.stderr)
        return 2

    print(f"Found {len(log_files)} .log files under {LOG_DIR}")
    print(f"Max concurrent requests: {max_workers}")
    print("Only .log files are processed. .jsonl files are ignored.")
    for path in log_files:
        print(f"  - {path.name} ({path.stat().st_size} bytes)")

    if args.dry_run:
        print("Dry run only. No Qwen requests were sent.")
        return 0

    api_key = get_api_key()
    if not api_key:
        env_names = " or ".join(API_KEY_ENV_NAMES)
        print(f"ERROR: please set {env_names} before running Qwen calls.", file=sys.stderr)
        return 2

    system_prompt = load_prompt()

    print(f"Starting Qwen calls. This will send up to {max_workers} requests concurrently.")
    results: list[dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_path = {
            executor.submit(process_one_file, path, api_key, system_prompt): path
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
                    "event_count": 0,
                    "user_event_count": 0,
                    "ai_event_count": 0,
                    "episodes": [],
                }

            results.append(result)
            if result["status"] == "ok":
                print(f"[{completed}/{len(log_files)}] OK {path.name}: {len(result['episodes'])} revisions")
            else:
                print(f"[{completed}/{len(log_files)}] FAILED {path.name}: {result.get('error')}")

    results = sorted(results, key=lambda item: item["file"].lower())
    report_path = LOG_DIR / REPORT_NAME
    json_path = LOG_DIR / JSON_NAME

    report_path.write_text(create_report(results, LOG_DIR, max_workers), encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "model": MODEL,
                "base_url": BASE_URL,
                "input_directory": str(LOG_DIR),
                "processed_pattern": LOG_PATTERN,
                "max_workers": max_workers,
                "prompt_path": str(PROMPT_PATH),
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    all_episodes = deduplicate([episode for result in results for episode in result["episodes"]])
    counts = count_types(all_episodes)

    print("")
    print("Processing complete.")
    print(f"Total revisions: {len(all_episodes)}")
    print(f"Goal Shift: {counts['analytical_goal_shift']}")
    print(f"Working-Hypothesis Revision: {counts['working_hypothesis_revision']}")
    print(f"Analytical Scope Refinement: {counts['analytical_scope_refinement']}")
    print(f"TXT report: {report_path}")
    print(f"JSON audit: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
