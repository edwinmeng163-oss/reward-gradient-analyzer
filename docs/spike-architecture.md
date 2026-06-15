# RGA-001 Spike Architecture

This spike is a specialist pipeline for Slay the Spire gameplay recordings. It
does not use an end-to-end VLM reader. A VLM may only be added later as an
optional reviewer for low-confidence candidate frames.

## Data Flow

1. `ingest.sample_frames(video_path, output_dir, config) -> list[FrameSample]`
   extracts 1 fps baseline frames and trigger-densified local frames.
2. `ingest.extract_audio(video_path, output_dir, config) -> AudioExtract`
   extracts mono 16 kHz audio.
3. `ocr.read_rois(frames, config) -> list[CandidateEvent]`
   runs OCR on configured ROIs and emits OCR candidates.
4. `screens.classify(frames, ocr_candidates, config) -> list[CandidateEvent]`
   classifies reward/shop/victory/combat/map screen states using templates,
   layout, color, and OCR evidence.
5. `audio.detect_cues(audio, config) -> list[CandidateEvent]`
   detects audio onset/energy/template cues. These are boost-only signals.
6. `fuse.to_reward_moments(candidates, config) -> list[RewardMoment]`
   clusters specialist candidates into `reward_moment` events. It must not emit
   a reward moment from audio-only evidence.
7. `eval.score(predictions, labels, tolerance_s=2.0) -> EvalScore`
   computes precision, recall, and median absolute timestamp error.

## Shared Contract Types

All modules use `src/rga/contracts.py`.

- `CandidateEvent`: `t_start`, `t_end`, `modality`, `label`, `value`,
  `confidence`, `evidence_ref`.
- `RewardMoment`: fused event with `t_start`, `t_end`, `label`, `confidence`,
  `evidence_ref`, contributing `candidates`, and stub `reward_items`.
- `RewardItem`: reserved for later item-level splitting.
- `Phase`: `ingest`, `ocr`, `screen`, `audio`, `fusion`, `eval`.
- `Modality`: `frame`, `ocr`, `screen`, `audio`, `fused`.

## Gold-Label JSON Schema

Labels live under `data/annotations/` and must refer only to first-party or
self-recorded footage under `data/recordings/`.

```json
{
  "schema_version": "rga.gold_labels.v1",
  "video": {
    "path": "data/recordings/slay_spire_clip.mp4",
    "game": "slay-the-spire",
    "source_rights": "first_party_self_recorded"
  },
  "events": [
    {
      "id": "rm_0001",
      "type": "reward_moment",
      "t_start": 122.8,
      "t_end": 124.2,
      "label": "victory_reward",
      "obvious": true,
      "confidence": "high",
      "evidence_ref": {
        "timestamp": 123.4,
        "details": {
          "screen_context": "victory_reward",
          "boundary_confidence": "medium"
        }
      },
      "notes": "Victory screen transitions into card/relic reward."
    }
  ]
}
```

Evaluation should default to `obvious: true` labels and a 2.0 second matching
tolerance. Precision is prioritized over recall.
