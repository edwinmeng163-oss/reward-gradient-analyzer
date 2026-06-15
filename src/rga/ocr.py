"""OCR-on-ROI interface stub.

Inputs:
- FrameSample records from ingest.sample_frames
- loaded GameConfig containing named ROIs and OCR keywords

Output:
- CandidateEvent records with modality=Modality.OCR

Implementation is intentionally deferred to the OCR worker.
"""

from __future__ import annotations

from .contracts import CandidateEvent, FrameSample, GameConfig


def read_rois(frames: list[FrameSample], config: GameConfig) -> list[CandidateEvent]:
    """Run OCR on configured ROIs and return OCR candidate events."""

    raise NotImplementedError("ocr.read_rois is a contract stub for the OCR worker")
