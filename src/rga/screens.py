"""Screen-state/template interface stub.

Inputs:
- FrameSample records from ingest.sample_frames
- OCR CandidateEvent records from ocr.read_rois
- loaded GameConfig containing screen states and template definitions

Output:
- CandidateEvent records with modality=Modality.SCREEN

Implementation is intentionally deferred to the screen-state worker.
"""

from __future__ import annotations

from .contracts import CandidateEvent, FrameSample, GameConfig


def classify(
    frames: list[FrameSample],
    ocr_candidates: list[CandidateEvent],
    config: GameConfig,
) -> list[CandidateEvent]:
    """Classify reward/shop/victory/combat/map screens from frames and OCR evidence."""

    raise NotImplementedError("screens.classify is a contract stub for the screen-state worker")
