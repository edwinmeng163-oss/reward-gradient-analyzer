"""Audio cue interface stub.

Inputs:
- AudioExtract from ingest.extract_audio
- loaded GameConfig containing cue thresholds/templates

Output:
- CandidateEvent records with modality=Modality.AUDIO

Audio cues are boost-only evidence; fusion must not emit reward moments from
audio alone. Implementation is intentionally deferred to the audio worker.
"""

from __future__ import annotations

from .contracts import AudioExtract, CandidateEvent, GameConfig


def detect_cues(audio: AudioExtract, config: GameConfig) -> list[CandidateEvent]:
    """Detect onset/energy/template audio cues for confidence boosting."""

    raise NotImplementedError("audio.detect_cues is a contract stub for the audio worker")
