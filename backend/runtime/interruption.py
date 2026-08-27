"""Deterministic policy for completed overlap transcripts."""

from __future__ import annotations

from enum import Enum


class InterruptionDecision(str, Enum):
    BACKCHANNEL = "BACKCHANNEL"
    RECOGNITION_REPAIR = "RECOGNITION_REPAIR"
    STOP_ONLY = "STOP_ONLY"
    ANALYTICAL_REVISION = "ANALYTICAL_REVISION"


def classify_completed_utterance(text: str) -> InterruptionDecision:
    """Classify a final user utterance without relying on model state."""
    normalized = " ".join(text.lower().split()).strip(".,!?;:")
    if normalized in {
        "yes",
        "yes, continue",
        "yeah",
        "yep",
        "okay",
        "ok",
        "continue",
        "go on",
    }:
        return InterruptionDecision.BACKCHANNEL
    if normalized.startswith(("sorry, i mean", "i mean", "correction")):
        return InterruptionDecision.RECOGNITION_REPAIR
    if normalized in {"stop", "stop it", "cancel", "never mind", "nevermind"}:
        return InterruptionDecision.STOP_ONLY
    return InterruptionDecision.ANALYTICAL_REVISION
