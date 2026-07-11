"""Compatibility import for older launch scripts.

The non-preemptive tool boundary and immediate interruption behavior now live in
``realtime.QwenRealtimeSession``. New code should import from ``realtime``.
"""

from realtime import QWEN_TURN_DETECTION, QwenRealtimeSession

__all__ = ["QWEN_TURN_DETECTION", "QwenRealtimeSession"]
