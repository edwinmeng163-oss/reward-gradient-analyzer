"""Evaluation interface stub.

Inputs:
- RewardMoment predictions from fuse.to_reward_moments
- GoldLabel records loaded from data/annotations

Output:
- EvalScore precision/recall/timestamp-error summary

Implementation is intentionally deferred to the eval worker.
"""

from __future__ import annotations

from .contracts import EvalScore, GoldLabel, RewardMoment


def score(
    predictions: list[RewardMoment],
    labels: list[GoldLabel],
    tolerance_s: float = 2.0,
) -> EvalScore:
    """Compute precision, recall, and median absolute timestamp error."""

    raise NotImplementedError("eval.score is a contract stub for the eval worker")
