"""Shared contracts for the RGA-001 specialist pipeline.

This file is the integration surface for parallel implementation work. Module
workers should keep these types and signatures stable unless the PM changes the
ticket contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import NotRequired, Protocol, TypedDict


JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


class Phase(str, Enum):
    """Pipeline phase that produced an artifact or evidence record."""

    INGEST = "ingest"
    OCR = "ocr"
    SCREEN = "screen"
    AUDIO = "audio"
    FUSION = "fusion"
    EVAL = "eval"


class Modality(str, Enum):
    """Specialist signal source for candidate events."""

    FRAME = "frame"
    OCR = "ocr"
    SCREEN = "screen"
    AUDIO = "audio"
    FUSED = "fused"


class EvidenceRef(TypedDict, total=False):
    """Pointer to inspectable evidence backing a candidate or fused event."""

    phase: Phase
    frame_index: int
    timestamp: float
    path: str
    roi_id: str
    template_id: str
    detector: str
    details: dict[str, JsonValue]


class RoiSpec(TypedDict):
    """Normalized ROI in 0..1 coordinates relative to analysis resolution."""

    x: float
    y: float
    w: float
    h: float


class GameConfig(TypedDict, total=False):
    """Loaded per-game JSON config."""

    schema_version: str
    game: str
    ingest: dict[str, JsonValue]
    rois: dict[str, RoiSpec]
    templates: list[dict[str, JsonValue]]
    ocr: dict[str, JsonValue]
    screen_states: dict[str, JsonValue]
    audio: dict[str, JsonValue]
    fusion: dict[str, JsonValue]
    eval: dict[str, JsonValue]


class GoldLabel(TypedDict):
    """One hand label for evaluation."""

    id: str
    type: str
    t_start: float
    t_end: float
    label: str
    obvious: NotRequired[bool]
    confidence: NotRequired[str]
    evidence_ref: NotRequired[EvidenceRef]
    notes: NotRequired[str]


@dataclass(frozen=True)
class FrameSample:
    """A sampled video frame ready for specialist detectors."""

    frame_index: int
    timestamp: float
    path: Path
    width: int
    height: int
    source_fps: float
    evidence_ref: EvidenceRef = field(default_factory=dict)


@dataclass(frozen=True)
class AudioExtract:
    """Extracted mono audio artifact."""

    path: Path
    sample_rate: int
    duration_s: float
    evidence_ref: EvidenceRef = field(default_factory=dict)


@dataclass(frozen=True)
class CandidateEvent:
    """Specialist candidate before fusion."""

    t_start: float
    t_end: float
    modality: Modality
    label: str
    value: JsonValue
    confidence: float
    evidence_ref: EvidenceRef


@dataclass(frozen=True)
class RewardItem:
    """Stub for later item-level splitting inside a reward moment."""

    label: str
    value: JsonValue = None
    confidence: float = 0.0
    evidence_ref: EvidenceRef = field(default_factory=dict)


@dataclass(frozen=True)
class RewardMoment:
    """Fused player-perceived reward moment."""

    t_start: float
    t_end: float
    label: str
    confidence: float
    evidence_ref: EvidenceRef
    candidates: list[CandidateEvent] = field(default_factory=list)
    reward_items: list[RewardItem] = field(default_factory=list)


@dataclass(frozen=True)
class EvalScore:
    """Precision/recall summary against hand labels."""

    precision: float
    recall: float
    median_abs_error_s: float | None
    true_positive: int
    false_positive: int
    false_negative: int
    label_count: int
    prediction_count: int


class IngestContract(Protocol):
    def sample_frames(self, video_path: Path, output_dir: Path, config: GameConfig) -> list[FrameSample]:
        """Sample baseline and densified frames from a recording."""

    def extract_audio(self, video_path: Path, output_dir: Path, config: GameConfig) -> AudioExtract:
        """Extract mono 16 kHz audio from a recording."""


class OcrContract(Protocol):
    def read_rois(self, frames: list[FrameSample], config: GameConfig) -> list[CandidateEvent]:
        """Read configured OCR ROIs and return OCR candidate events."""


class ScreensContract(Protocol):
    def classify(
        self,
        frames: list[FrameSample],
        ocr_candidates: list[CandidateEvent],
        config: GameConfig,
    ) -> list[CandidateEvent]:
        """Classify screen states and return visual candidate events."""


class AudioContract(Protocol):
    def detect_cues(self, audio: AudioExtract, config: GameConfig) -> list[CandidateEvent]:
        """Detect audio cues for later confidence boosting."""


class FuseContract(Protocol):
    def to_reward_moments(
        self,
        candidates: list[CandidateEvent],
        config: GameConfig,
    ) -> list[RewardMoment]:
        """Fuse specialist candidates into reward moments."""


class EvalContract(Protocol):
    def score(
        self,
        predictions: list[RewardMoment],
        labels: list[GoldLabel],
        tolerance_s: float = 2.0,
    ) -> EvalScore:
        """Score fused reward moments against hand labels."""
