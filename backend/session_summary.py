"""Deterministic per-session phase summaries for realtime relays."""

from __future__ import annotations

import datetime
import json
import re
from pathlib import Path
from typing import Any


_ACTION_RE = re.compile(
    r"(添加|生成|绘制|画|筛选|过滤|删除|移除|高亮|展示|显示|修改|更改|改成|换成|排序|"
    r"add|create|draw|show|display|filter|remove|delete|highlight|update|sort)",
    re.IGNORECASE,
)
_TOP_N_RE = re.compile(r"(?:前\s*(\d+|N)|top\s*(\d+|n))", re.IGNORECASE)
_EXPLICIT_CORRECTION_RES = (
    re.compile(r"不是(?P<wrong>[^，。,.；;]{1,20})[，,]?(?:是|要)(?P<right>[^，。,.；;]{1,20})"),
    re.compile(r"(?:把|将)?(?P<wrong>[^，。,.；;]{1,20})(?:改成|改为|换成)(?P<right>[^，。,.；;]{1,20})"),
)


class SessionSummaryTracker:
    """Accumulates completed realtime turns and emits compact phase summaries.

    The tracker is intentionally deterministic: it only uses counters, the
    stored session events, and simple string rules for likely ASR confusions.
    """

    def __init__(
        self,
        session_id: str,
        provider: str,
        *,
        user_phase_size: int = 3,
        tool_phase_size: int = 2,
        log_dir: Path | None = None,
    ) -> None:
        self.session_id = session_id
        self.provider = provider
        self.user_phase_size = user_phase_size
        self.tool_phase_size = tool_phase_size
        self._log_dir = log_dir

        self.turns: list[dict[str, Any]] = []
        self.tool_calls: list[dict[str, Any]] = []
        self._pending_tool_calls: dict[str, dict[str, Any]] = {}
        self._next_turn_id = 1
        self._phase_index = 0
        self._last_summary_turn_id = 0
        self._user_since_summary = 0
        self._successful_tools_since_summary = 0

    def set_log_dir(self, log_dir: Path | None) -> None:
        self._log_dir = log_dir

    def record_user_transcript(self, text: str) -> dict[str, Any] | None:
        clean = _clean_text(text)
        if not clean:
            return None
        self._append_turn({"kind": "user_transcript", "role": "user", "text": clean})
        self._user_since_summary += 1
        return self._maybe_emit_summary("user_threshold")

    def record_assistant_transcript(
        self,
        text: str,
        *,
        suppressed: bool = False,
    ) -> dict[str, Any] | None:
        clean = _clean_text(text)
        if not clean:
            return None
        self._append_turn({
            "kind": "assistant_transcript",
            "role": "assistant",
            "text": clean,
            "suppressed": suppressed,
        })
        return None

    def record_tool_call(
        self,
        *,
        name: str,
        arguments: Any,
        response_id: str | None = None,
        call_id: str | None = None,
    ) -> dict[str, Any] | None:
        entry = self._append_turn({
            "kind": "tool_call",
            "name": name or "",
            "arguments": _compact_value(arguments),
            "response_id": response_id,
            "call_id": call_id,
        })
        self.tool_calls.append(entry)
        self._pending_tool_calls[_tool_key(response_id, call_id, name)] = entry
        return None

    def record_tool_result(
        self,
        *,
        name: str,
        arguments: Any,
        result: dict[str, Any],
        response_id: str | None = None,
        call_id: str | None = None,
        duration_ms: float | None = None,
    ) -> dict[str, Any] | None:
        success = bool(result.get("success"))
        key = _tool_key(response_id, call_id, name)
        pending = self._pending_tool_calls.pop(key, None)
        if pending is not None:
            pending["result_seen"] = True
            pending["success"] = success
        self._append_turn({
            "kind": "tool_result",
            "name": name or "",
            "arguments": _compact_value(arguments),
            "response_id": response_id,
            "call_id": call_id,
            "success": success,
            "duration_ms": duration_ms,
            "result": _compact_tool_result(result),
        })
        if success:
            self._successful_tools_since_summary += 1
        return self._maybe_emit_summary("tool_threshold")

    def _append_turn(self, entry: dict[str, Any]) -> dict[str, Any]:
        now = _utc_now()
        entry = {
            "turn_id": self._next_turn_id,
            "ts": now,
            **entry,
        }
        self._next_turn_id += 1
        self.turns.append(entry)
        return entry

    def _maybe_emit_summary(self, trigger: str) -> dict[str, Any] | None:
        user_ready = self._user_since_summary >= self.user_phase_size
        tool_ready = self._successful_tools_since_summary >= self.tool_phase_size
        if not user_ready and not tool_ready:
            return None

        covered = [turn for turn in self.turns if turn["turn_id"] > self._last_summary_turn_id]
        if not covered:
            self._user_since_summary = 0
            self._successful_tools_since_summary = 0
            return None

        self._phase_index += 1
        timestamp = _utc_now()
        summary = _build_summary(
            session_id=self.session_id,
            provider=self.provider,
            phase_index=self._phase_index,
            trigger=trigger,
            timestamp=timestamp,
            turns=covered,
        )
        self._last_summary_turn_id = covered[-1]["turn_id"]
        self._user_since_summary = 0
        self._successful_tools_since_summary = 0
        self._write_summary(summary)
        return summary

    def _write_summary(self, summary: dict[str, Any]) -> None:
        if not self._log_dir:
            return
        path = self._log_dir / "session_summary.jsonl"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(summary, ensure_ascii=False) + "\n")


def _build_summary(
    *,
    session_id: str,
    provider: str,
    phase_index: int,
    trigger: str,
    timestamp: str,
    turns: list[dict[str, Any]],
) -> dict[str, Any]:
    counts = _turn_counts(turns)
    first_id = turns[0]["turn_id"]
    last_id = turns[-1]["turn_id"]
    current_focus = _current_focus(turns)
    bullets = _build_bullets(turns)
    actions = _build_actions(turns)
    possible_mishearings, corrected_phrases = _detect_speech_confusions(turns)
    title = _title_for_phase(phase_index, current_focus, actions)

    return {
        "type": "session_summary",
        "session_id": session_id,
        "provider": provider,
        "phase_index": phase_index,
        "covered_turns": {
            "from": first_id,
            "to": last_id,
            "count": len(turns),
            **counts,
        },
        "title": title,
        "bullets": bullets,
        "actions": actions,
        "current_focus": current_focus,
        "possible_mishearings": possible_mishearings,
        "corrected_phrases": corrected_phrases,
        "timestamp": timestamp,
        "ts": timestamp,
        "trigger": trigger,
    }


def _turn_counts(turns: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "user_transcripts": sum(1 for turn in turns if turn.get("kind") == "user_transcript"),
        "assistant_transcripts": sum(1 for turn in turns if turn.get("kind") == "assistant_transcript"),
        "tool_calls": sum(1 for turn in turns if turn.get("kind") == "tool_call"),
        "tool_results": sum(1 for turn in turns if turn.get("kind") == "tool_result"),
        "successful_tool_turns": sum(
            1 for turn in turns
            if turn.get("kind") == "tool_result" and bool(turn.get("success"))
        ),
    }


def _build_bullets(turns: list[dict[str, Any]]) -> list[str]:
    bullets: list[str] = []
    for turn in turns:
        kind = turn.get("kind")
        if kind == "user_transcript":
            bullets.append(f"User asked: {_clip(turn.get('text', ''))}")
        elif kind == "assistant_transcript":
            if turn.get("suppressed"):
                bullets.append(f"Assistant prepared a tool turn: {_clip(turn.get('text', ''))}")
            else:
                bullets.append(f"Assistant replied: {_clip(turn.get('text', ''))}")
        elif kind == "tool_call":
            bullets.append(f"Tool requested: {turn.get('name', '')}({_args_hint(turn.get('arguments'))})")
        elif kind == "tool_result":
            status = "succeeded" if turn.get("success") else "failed"
            bullets.append(f"Tool {status}: {turn.get('name', '')}{_result_hint(turn.get('result'))}")
        if len(bullets) >= 6:
            break
    return bullets


def _build_actions(turns: list[dict[str, Any]]) -> list[str]:
    actions: list[str] = []
    seen: set[str] = set()
    for turn in turns:
        kind = turn.get("kind")
        action = ""
        if kind == "tool_result":
            status = "completed" if turn.get("success") else "failed"
            action = f"{turn.get('name', '')} {status}"
        elif kind == "tool_call":
            action = f"{turn.get('name', '')} requested"
        elif kind == "user_transcript" and _ACTION_RE.search(turn.get("text", "")):
            action = f"User requested: {_clip(turn.get('text', ''), 80)}"
        if action and action not in seen:
            seen.add(action)
            actions.append(action)
        if len(actions) >= 5:
            break
    return actions


def _current_focus(turns: list[dict[str, Any]]) -> str:
    for turn in reversed(turns):
        if turn.get("kind") == "user_transcript":
            return _clip(turn.get("text", ""), 120)
    for turn in reversed(turns):
        if turn.get("kind") == "tool_result":
            name = turn.get("name", "")
            status = "succeeded" if turn.get("success") else "failed"
            return f"{name} {status}".strip()
    for turn in reversed(turns):
        if turn.get("kind") == "assistant_transcript":
            return _clip(turn.get("text", ""), 120)
    return "Session activity"


def _title_for_phase(phase_index: int, current_focus: str, actions: list[str]) -> str:
    if actions:
        focus = actions[-1]
    else:
        focus = current_focus or "Session activity"
    return f"Phase {phase_index}: {_clip(focus, 48)}"


def _detect_speech_confusions(
    turns: list[dict[str, Any]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    texts = [
        turn.get("text", "")
        for turn in turns
        if turn.get("kind") in {"user_transcript", "assistant_transcript"}
    ]
    for turn in turns:
        if turn.get("kind") == "tool_call":
            texts.append(json.dumps(turn.get("arguments", {}), ensure_ascii=False))

    possible: list[dict[str, str]] = []
    corrected: list[dict[str, str]] = []

    for text in texts:
        if not text:
            continue
        _extract_explicit_corrections(text, corrected)
        if any(marker in text for marker in ("同音字", "误解", "听错")):
            _append_unique(possible, {
                "heard": "speech correction mentioned",
                "possibly_meant": "review nearby corrected phrase",
                "reason": "speaker explicitly mentioned 同音字/误解/听错",
            })
        if "试图" in text:
            _append_unique(possible, {
                "heard": "试图",
                "possibly_meant": "视图",
                "reason": "common ASR confusion for dashboard view wording",
            })
            _append_unique(corrected, {
                "from": "试图",
                "to": "视图",
                "reason": "dashboard view terminology",
            })
        if "视图" in text and "图" in text:
            _append_unique(possible, {
                "heard": "图/视图",
                "possibly_meant": "chart or dashboard view",
                "reason": "图 and 视图 can both appear in visualization commands",
            })
        elif "图" in text and _ACTION_RE.search(text):
            _append_unique(possible, {
                "heard": "图",
                "possibly_meant": "视图",
                "reason": "single-character 图 can mean chart or dashboard view",
            })
        if any(ch in text for ch in ("州", "洲", "周")):
            _append_unique(possible, {
                "heard": "州/洲/周",
                "possibly_meant": "region, continent, or week depending on field",
                "reason": "same-pronunciation domain terms",
            })
        if re.search(r"(低于|小于)\s*(三|3)\s*分|(?:三|3)\s*分以下", text):
            _append_unique(possible, {
                "heard": "低于三分",
                "possibly_meant": "三分及以下",
                "reason": "exclusive vs inclusive score threshold",
            })
            _append_unique(corrected, {
                "from": "低于三分",
                "to": "三分及以下",
                "reason": "include score 3 when requested",
            })
        if re.search(r"(?:三|3)\s*分及以下|<=\s*3", text):
            _append_unique(possible, {
                "heard": "三分及以下",
                "possibly_meant": "低于三分",
                "reason": "confirm inclusive threshold behavior",
            })
        if "品类" in text or "类别" in text:
            _append_unique(possible, {
                "heard": "品类/类别",
                "possibly_meant": "category field",
                "reason": "category synonyms can map to different dataset columns",
            })
        for match in _TOP_N_RE.finditer(text):
            value = match.group(1) or match.group(2) or "N"
            _append_unique(possible, {
                "heard": match.group(0),
                "possibly_meant": f"Top {value}",
                "reason": "前N and Top N should preserve the requested limit",
            })
            _append_unique(corrected, {
                "from": match.group(0),
                "to": f"Top {value}",
                "reason": "normalize ranking phrase",
            })
        if "折线" in text or "多系列" in text:
            _append_unique(possible, {
                "heard": "折线/多系列",
                "possibly_meant": "single-series or multi-series line chart",
                "reason": "line chart requests need series intent preserved",
            })
        if "表格" in text or "列表" in text:
            _append_unique(possible, {
                "heard": "表格/列表",
                "possibly_meant": "table view or list view",
                "reason": "display type ambiguity",
            })

    return possible[:8], corrected[:8]


def _extract_explicit_corrections(text: str, corrected: list[dict[str, str]]) -> None:
    for pattern in _EXPLICIT_CORRECTION_RES:
        for match in pattern.finditer(text):
            wrong = _clean_text(match.group("wrong"))
            right = _clean_text(match.group("right"))
            if wrong and right and wrong != right:
                _append_unique(corrected, {
                    "from": wrong,
                    "to": right,
                    "reason": "explicit correction phrase",
                })


def _append_unique(items: list[dict[str, str]], item: dict[str, str]) -> None:
    marker = tuple(sorted(item.items()))
    for existing in items:
        if tuple(sorted(existing.items())) == marker:
            return
    items.append(item)


def _args_hint(arguments: Any) -> str:
    if not isinstance(arguments, dict):
        return _clip(str(arguments), 80)
    hints: list[str] = []
    for key in ("chart_type", "title", "x", "y", "group_by", "limit", "series_limit", "field", "value"):
        value = arguments.get(key)
        if value not in (None, "", [], {}):
            hints.append(f"{key}={_clip(str(value), 24)}")
    if hints:
        return ", ".join(hints[:4])
    return "args"


def _result_hint(result: Any) -> str:
    if not isinstance(result, dict):
        return ""
    error = result.get("error")
    warning = result.get("warning")
    if error:
        return f": {_clip(str(error), 90)}"
    if warning:
        return f": {_clip(str(warning), 90)}"
    return ""


def _compact_tool_result(result: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {
        "success": bool(result.get("success")),
        "tool": result.get("tool"),
    }
    for key in ("error", "warning", "message", "view_id", "title", "chart_type"):
        value = result.get(key)
        if value not in (None, "", [], {}):
            compact[key] = _compact_value(value)
    if isinstance(result.get("views"), list):
        compact["views_count"] = len(result["views"])
    if isinstance(result.get("data"), list):
        compact["data_points"] = len(result["data"])
    return compact


def _compact_value(value: Any) -> Any:
    if isinstance(value, dict):
        compact: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 20:
                compact["..."] = "truncated"
                break
            compact[str(key)] = _compact_value(item)
        return compact
    if isinstance(value, list):
        if len(value) > 10:
            return [_compact_value(item) for item in value[:10]] + [{"...": f"{len(value) - 10} more"}]
        return [_compact_value(item) for item in value]
    if isinstance(value, str):
        return _clip(value, 240)
    return value


def _tool_key(response_id: str | None, call_id: str | None, name: str | None) -> str:
    if call_id:
        return f"call:{call_id}"
    return f"response:{response_id or ''}:name:{name or ''}"


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _clip(text: str, limit: int = 120) -> str:
    clean = _clean_text(str(text))
    if len(clean) <= limit:
        return clean
    return f"{clean[: max(0, limit - 1)]}..."


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()
