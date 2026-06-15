"""Fusion interface stub.

Inputs:
- CandidateEvent records from OCR, screen-state, and audio modules
- loaded GameConfig containing clustering and confidence thresholds

Output:
- RewardMoment records; RewardItem remains a stub for later work

Audio candidates are boost-only and must not be sole sources for emitted reward
moments. Implementation is intentionally deferred to the fusion worker.
"""

from __future__ import annotations

from .contracts import CandidateEvent, GameConfig, RewardMoment


def to_reward_moments(candidates: list[CandidateEvent], config: GameConfig) -> list[RewardMoment]:
    """Cluster specialist candidates into fused reward_moment events."""

    raise NotImplementedError("fuse.to_reward_moments is a contract stub for the fusion worker")
