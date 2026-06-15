# Gold Label Schema

RGA-001 evaluates detected `reward_moment` events against hand labels stored as
JSON under `data/annotations/`. Every label must refer to first-party,
self-recorded, customer-authorized, partner-authorized, or synthetic test
footage under `data/recordings/`.

Do not label scraped Twitch, YouTube, or other public VOD footage for training,
evaluation, or customer delivery.

## File Shape

Use one JSON file per recording:

```json
{
  "schema_version": "rga.gold_labels.v1",
  "video": {
    "path": "data/recordings/slay_spire_clip_001.mp4",
    "game": "slay-the-spire",
    "source_rights": "first_party_self_recorded",
    "recording_id": "slay_spire_clip_001"
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
        "frame_index": 3702,
        "details": {
          "screen_context": "victory_reward",
          "boundary_confidence": "medium",
          "semantic_confidence": "high",
          "success_contingent": true
        }
      },
      "notes": "Victory screen transitions into the card reward choice."
    }
  ]
}
```

## Top-Level Fields

`schema_version`: Required. Use `rga.gold_labels.v1`.

`video.path`: Required. Must point under `data/recordings/`.

`video.game`: Required. Use the game key from config, for example
`slay-the-spire`.

`video.source_rights`: Required. Allowed values are
`first_party_self_recorded`, `customer_uploaded_authorized`,
`partner_authorized`, and `synthetic_test`.

`events`: Required array of temporal labels.

## Event Fields

`id`: Required stable label id, unique within the file. Use `rm_0001`,
`rm_0002`, and so on.

`type`: Required. RGA-001 scoring reads only `reward_moment`.

`t_start` and `t_end`: Required seconds from video start. Mark the interval
where the reward becomes player-visible or player-audible. `t_end` must be
greater than or equal to `t_start`.

`label`: Required semantic tag. Recommended initial tags include
`card_choice`, `relic_gain`, `currency_gain`, `victory_reward`,
`boss_reward`, `shop_reward`, `unlock_reward`, and `run_end_summary`.

`obvious`: Optional boolean, defaulting to `true` for RGA-001 evaluation.
Set `false` when the moment is ambiguous or requires domain interpretation.

`confidence`: Optional annotator confidence: `high`, `medium`, or `low`.

`evidence_ref`: Optional pointer to the frame, timestamp, ROI, detector note,
or other inspectable evidence. It follows `contracts.EvidenceRef`.

`notes`: Optional short human note for boundary or semantic ambiguity.

## Labeling Rules

Label the player-perceived reward moment, not every individual item inside it.
Item-level splitting belongs to later `reward_items` work.

Merge reward items into one `reward_moment` when they are perceived as one
screen or payout beat, for example a victory screen that presents cards and a
relic together.

Split events when the player perceives separate reward beats, for example a
combat victory payout followed later by a shop purchase.

Start the interval when the reward is unambiguous to the player: the reward
screen appears, the payout number lands, the unlock modal appears, or the
success-contingent audio/visual cue fires.

End the interval when the immediate reward beat stabilizes or leaves the
screen. For choice screens, end after the choice UI is fully visible, not after
the player eventually makes a selection.

Do not label preview-only information as a reward unless it is clearly framed
as a successful payout or new option granted to the player.

## Evaluation Defaults

`src/rga/eval.py` loads labels from `data/annotations/`, keeps only
`type == "reward_moment"`, and by default scores only labels where `obvious` is
missing or `true`.

Matching is one-to-one by nearest reward-moment midpoint within `2.0` seconds.
The reported timestamp error is the median absolute midpoint error for matched
events.

If no labels or recordings exist yet, the evaluator prints a pending metrics
table and exits with status 0.
