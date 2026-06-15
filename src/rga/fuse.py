"""Fuse specialist candidates into conservative reward moments.

Fusion intentionally stays rule-based for this spike. OCR and screen-state
candidates can create a reward moment; audio is boost-only evidence and never
emits by itself. The output remains two-level: this module emits
``reward_moment`` events now and leaves ``reward_items`` empty for later
item-level splitting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import CandidateEvent, EvidenceRef, GameConfig, JsonValue, Modality, Phase, RewardMoment


_DEFAULT_REWARD_STATES = {"reward_screen", "victory"}
_DEFAULT_REWARD_KEYWORDS = {"choose a card", "reward", "rewards", "victory", "relic"}
_GENERIC_KEYWORDS = {"take", "skip", "proceed"}
_LABEL_ALIASES = {
    "reward": "reward_screen",
    "rewards": "reward_screen",
    "reward_screen": "reward_screen",
    "card_reward": "reward_screen",
    "combat_reward": "reward_screen",
    "victory_reward": "victory",
    "victory": "victory",
}


@dataclass(frozen=True)
class _FusionSettings:
    target_label: str
    reward_states: set[str]
    reward_keywords: set[str]
    cluster_gap_s: float
    emit_threshold: float
    ocr_emit_threshold: float
    audio_boost_window_s: float
    audio_boost_max: float
    density_window_s: float
    density_step_s: float


@dataclass(frozen=True)
class _ScoredCandidate:
    candidate: CandidateEvent
    score: float
    reason: str


@dataclass(frozen=True)
class _Cluster:
    core: list[_ScoredCandidate]
    audio: list[CandidateEvent]

    @property
    def t_start(self) -> float:
        return min(item.candidate.t_start for item in self.core)

    @property
    def t_end(self) -> float:
        return max(item.candidate.t_end for item in self.core)


def to_reward_moments(candidates: list[CandidateEvent], config: GameConfig) -> list[RewardMoment]:
    """Cluster OCR/screen candidates into fused ``reward_moment`` events.

    Audio candidates are attached only when they are near a non-audio reward
    cluster. This keeps the pipeline precise: a jingle or peak without visual
    or OCR reward evidence is not enough to emit a reward event.
    """

    settings = _settings(config)
    if not candidates:
        return []

    core_candidates = [
        scored
        for candidate in candidates
        if (scored := _reward_score(candidate, settings)) is not None
    ]
    if not core_candidates:
        return []

    audio_candidates = [
        candidate
        for candidate in candidates
        if candidate.modality == Modality.AUDIO
    ]
    clusters = _attach_audio(_clusters(core_candidates, settings.cluster_gap_s), audio_candidates, settings)

    moments: list[RewardMoment] = []
    for cluster in clusters:
        moment = _reward_moment(cluster, settings)
        if moment.confidence >= settings.emit_threshold:
            moments.append(moment)

    return sorted(moments, key=lambda item: (item.t_start, item.t_end, -item.confidence))


def compute_reward_density(
    moments: list[RewardMoment],
    config: GameConfig,
    duration_s: float | None = None,
) -> list[dict[str, JsonValue]]:
    """Compute reward density windows using ``fusion`` config defaults."""

    settings = _settings(config)
    return reward_density(
        moments,
        duration_s=duration_s,
        window_s=settings.density_window_s,
        step_s=settings.density_step_s,
    )


def reward_density(
    moments: list[RewardMoment],
    duration_s: float | None = None,
    window_s: float = 60.0,
    step_s: float = 5.0,
) -> list[dict[str, JsonValue]]:
    """Return rolling reward-density windows.

    The spike does not have a full reward-strength model yet, so confidence is
    used as the current reward-score proxy. Density is reward-score sum divided
    by window duration.
    """

    window_s = _positive_float(window_s, 60.0)
    step_s = _positive_float(step_s, 5.0)
    duration = _duration_from_moments(moments, duration_s)
    if duration <= 0:
        return []

    starts = _window_starts(duration, window_s, step_s)
    windows: list[dict[str, JsonValue]] = []
    for start in starts:
        end = min(duration, start + window_s)
        if end <= start:
            continue
        included = [
            moment
            for moment in moments
            if start <= _event_time(moment) < end or _overlaps(moment.t_start, moment.t_end, start, end)
        ]
        reward_sum = sum(_confidence(moment.confidence) for moment in included)
        window_duration = end - start
        windows.append(
            {
                "window_start": round(start, 4),
                "window_end": round(end, 4),
                "window_duration_s": round(window_duration, 4),
                "reward_count": len(included),
                "reward_sum": round(reward_sum, 4),
                "reward_density": round(reward_sum / window_duration, 6),
            }
        )
    return windows


def _settings(config: GameConfig) -> _FusionSettings:
    fusion = _dict_value(config.get("fusion"))
    reward_states = {
        _canonical_label(value)
        for value in _string_values(fusion.get("reward_states"))
    } or set(_DEFAULT_REWARD_STATES)
    reward_keywords = {
        _normalize_text(value)
        for value in _string_values(fusion.get("reward_keywords"))
        if _normalize_text(value)
    } or set(_DEFAULT_REWARD_KEYWORDS)
    emit_threshold = _bounded_float(fusion.get("emit_threshold"), 0.80, 0.0, 0.99)
    return _FusionSettings(
        target_label=str(fusion.get("target_label", "reward_moment")),
        reward_states=reward_states,
        reward_keywords=reward_keywords,
        cluster_gap_s=_positive_float(fusion.get("cluster_gap_s"), 2.5),
        emit_threshold=emit_threshold,
        ocr_emit_threshold=_bounded_float(fusion.get("ocr_emit_threshold"), max(0.78, emit_threshold - 0.05), 0.0, 0.99),
        audio_boost_window_s=_positive_float(fusion.get("audio_boost_window_s"), 1.25),
        audio_boost_max=_bounded_float(fusion.get("audio_boost_max"), 0.10, 0.0, 0.25),
        density_window_s=_positive_float(fusion.get("density_window_s"), 60.0),
        density_step_s=_positive_float(fusion.get("density_step_s"), 5.0),
    )


def _reward_score(candidate: CandidateEvent, settings: _FusionSettings) -> _ScoredCandidate | None:
    if candidate.modality == Modality.AUDIO:
        return None

    confidence = _confidence(candidate.confidence)
    labels = _candidate_labels(candidate)
    if candidate.modality == Modality.SCREEN:
        matched_states = labels & settings.reward_states
        if not matched_states:
            return None
        return _ScoredCandidate(
            candidate=candidate,
            score=confidence,
            reason=f"screen_state:{sorted(matched_states)[0]}",
        )

    if candidate.modality == Modality.OCR:
        matched_keywords = _candidate_keywords(candidate) & settings.reward_keywords
        if not matched_keywords or confidence < settings.ocr_emit_threshold:
            return None
        specificity = max(_keyword_specificity(keyword) for keyword in matched_keywords)
        score = confidence * specificity
        if score < settings.emit_threshold - 0.10:
            return None
        return _ScoredCandidate(
            candidate=candidate,
            score=_clamp(score, 0.0, 0.97),
            reason=f"ocr_keyword:{','.join(sorted(matched_keywords))}",
        )

    return None


def _clusters(scored_candidates: list[_ScoredCandidate], cluster_gap_s: float) -> list[_Cluster]:
    groups: list[list[_ScoredCandidate]] = []
    for scored in sorted(
        scored_candidates,
        key=lambda item: (item.candidate.t_start, item.candidate.t_end, item.candidate.label),
    ):
        if not groups:
            groups.append([scored])
            continue
        previous_end = max(item.candidate.t_end for item in groups[-1])
        if scored.candidate.t_start <= previous_end + cluster_gap_s:
            groups[-1].append(scored)
        else:
            groups.append([scored])
    return [_Cluster(core=group, audio=[]) for group in groups]


def _attach_audio(
    clusters: list[_Cluster],
    audio_candidates: list[CandidateEvent],
    settings: _FusionSettings,
) -> list[_Cluster]:
    if not audio_candidates:
        return clusters

    attached: list[_Cluster] = []
    for cluster in clusters:
        start = cluster.t_start - settings.audio_boost_window_s
        end = cluster.t_end + settings.audio_boost_window_s
        audio = [
            candidate
            for candidate in audio_candidates
            if _overlaps(candidate.t_start, candidate.t_end, start, end)
            or start <= _event_time(candidate) <= end
        ]
        attached.append(_Cluster(core=cluster.core, audio=audio))
    return attached


def _reward_moment(cluster: _Cluster, settings: _FusionSettings) -> RewardMoment:
    core_candidates = [item.candidate for item in cluster.core]
    all_candidates = _dedupe_candidates([*core_candidates, *cluster.audio])
    base_confidence = _combined_core_confidence(cluster.core)
    source_bonus = _source_bonus(core_candidates)
    audio_boost = _audio_boost(cluster.audio, settings.audio_boost_max)
    confidence = _clamp(base_confidence + source_bonus + audio_boost, 0.0, 0.99)
    primary = _primary_candidate(core_candidates)
    t_start = min(candidate.t_start for candidate in core_candidates)
    t_end = max(candidate.t_end for candidate in core_candidates)
    if t_end <= t_start:
        t_end = t_start + 0.001

    evidence_ref = _merged_evidence(
        primary=primary,
        t_start=t_start,
        t_end=t_end,
        confidence=confidence,
        cluster=cluster,
        settings=settings,
        base_confidence=base_confidence,
        source_bonus=source_bonus,
        audio_boost=audio_boost,
    )
    return RewardMoment(
        t_start=round(t_start, 4),
        t_end=round(t_end, 4),
        label=settings.target_label,
        confidence=round(confidence, 4),
        evidence_ref=evidence_ref,
        candidates=all_candidates,
        reward_items=[],
    )


def _combined_core_confidence(scored_candidates: list[_ScoredCandidate]) -> float:
    inverse = 1.0
    for scored in scored_candidates:
        inverse *= 1.0 - _clamp(scored.score, 0.0, 0.98)
    return _clamp(1.0 - inverse, 0.0, 0.98)


def _source_bonus(candidates: list[CandidateEvent]) -> float:
    modalities = {candidate.modality for candidate in candidates}
    if Modality.SCREEN in modalities and Modality.OCR in modalities:
        return 0.04
    return 0.0


def _audio_boost(candidates: list[CandidateEvent], max_boost: float) -> float:
    if not candidates or max_boost <= 0:
        return 0.0
    best_audio = max(_confidence(candidate.confidence) for candidate in candidates)
    return min(max_boost, best_audio * max_boost)


def _primary_candidate(candidates: list[CandidateEvent]) -> CandidateEvent:
    return max(
        candidates,
        key=lambda candidate: (
            candidate.confidence,
            1 if candidate.modality == Modality.SCREEN else 0,
            -candidate.t_start,
        ),
    )


def _merged_evidence(
    *,
    primary: CandidateEvent,
    t_start: float,
    t_end: float,
    confidence: float,
    cluster: _Cluster,
    settings: _FusionSettings,
    base_confidence: float,
    source_bonus: float,
    audio_boost: float,
) -> EvidenceRef:
    primary_ref = primary.evidence_ref
    timestamp = _event_time(primary)
    evidence_refs = [candidate.evidence_ref for candidate in _dedupe_candidates([item.candidate for item in cluster.core] + cluster.audio)]
    details: dict[str, JsonValue] = {
        "type": settings.target_label,
        "window": {"t_start": round(t_start, 4), "t_end": round(t_end, 4)},
        "confidence": round(confidence, 4),
        "confidence_parts": {
            "core_noisy_or": round(base_confidence, 4),
            "source_bonus": round(source_bonus, 4),
            "audio_boost": round(audio_boost, 4),
            "emit_threshold": round(settings.emit_threshold, 4),
        },
        "core_reasons": [item.reason for item in cluster.core],
        "candidate_labels": [candidate.label for candidate in _dedupe_candidates([item.candidate for item in cluster.core] + cluster.audio)],
        "modalities": sorted({candidate.modality.value for candidate in _dedupe_candidates([item.candidate for item in cluster.core] + cluster.audio)}),
        "audio_policy": "boost_only_never_emit_audio_alone",
        "reward_items_policy": "stub_empty_for_this_ticket",
        "primary_evidence_ref": primary_ref,
        "evidence_refs": evidence_refs,
    }
    evidence: EvidenceRef = {
        "phase": Phase.FUSION,
        "timestamp": timestamp,
        "detector": "fuse.to_reward_moments",
        "details": details,
    }
    if isinstance(primary_ref.get("frame_index"), int):
        evidence["frame_index"] = primary_ref["frame_index"]
    if isinstance(primary_ref.get("path"), str):
        evidence["path"] = primary_ref["path"]
    if isinstance(primary_ref.get("roi_id"), str):
        evidence["roi_id"] = primary_ref["roi_id"]
    if isinstance(primary_ref.get("template_id"), str):
        evidence["template_id"] = primary_ref["template_id"]
    return evidence


def _dedupe_candidates(candidates: list[CandidateEvent]) -> list[CandidateEvent]:
    deduped: list[CandidateEvent] = []
    seen: set[tuple[float, float, str, str]] = set()
    for candidate in sorted(
        candidates,
        key=lambda item: (item.t_start, item.t_end, item.modality.value, item.label, -item.confidence),
    ):
        key = (
            round(candidate.t_start, 4),
            round(candidate.t_end, 4),
            candidate.modality.value,
            candidate.label,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _candidate_labels(candidate: CandidateEvent) -> set[str]:
    labels = {_canonical_label(candidate.label)}
    _collect_label_values(candidate.value, labels)
    details = candidate.evidence_ref.get("details")
    if isinstance(details, dict):
        _collect_label_values(details, labels)
    return {label for label in labels if label}


def _collect_label_values(value: Any, labels: set[str]) -> None:
    if isinstance(value, str):
        labels.add(_canonical_label(value))
        return
    if isinstance(value, int | float | bool) or value is None:
        return
    if isinstance(value, list | tuple):
        for item in value:
            _collect_label_values(item, labels)
        return
    if isinstance(value, dict):
        for key in ("label", "screen", "phase", "state_key", "aliases", "state_keys_in_window"):
            if key in value:
                _collect_label_values(value[key], labels)


def _candidate_keywords(candidate: CandidateEvent) -> set[str]:
    keywords: set[str] = set()
    _collect_keyword_values(candidate.value, keywords)
    details = candidate.evidence_ref.get("details")
    if isinstance(details, dict):
        _collect_keyword_values(details, keywords)
    if not keywords:
        _collect_text_keywords(candidate.value, keywords)
    return {keyword for keyword in keywords if keyword}


def _collect_keyword_values(value: Any, keywords: set[str]) -> None:
    if isinstance(value, str):
        return
    if isinstance(value, int | float | bool) or value is None:
        return
    if isinstance(value, list | tuple):
        for item in value:
            if isinstance(item, str):
                keywords.add(_normalize_text(item))
            else:
                _collect_keyword_values(item, keywords)
        return
    if isinstance(value, dict):
        for key in ("matched_keywords", "keywords"):
            if key in value:
                _collect_keyword_values(value[key], keywords)
        for key in ("text", "raw_text", "normalized_text"):
            text = value.get(key)
            if isinstance(text, str):
                _collect_text_keywords(text, keywords)


def _collect_text_keywords(value: Any, keywords: set[str]) -> None:
    if not isinstance(value, str):
        return
    text = f" {_normalize_text(value)} "
    for keyword in [*_DEFAULT_REWARD_KEYWORDS, *_GENERIC_KEYWORDS]:
        normalized = _normalize_text(keyword)
        if not normalized:
            continue
        if " " in normalized:
            if normalized in text:
                keywords.add(normalized)
        elif f" {normalized} " in text:
            keywords.add(normalized)


def _keyword_specificity(keyword: str) -> float:
    if keyword in _GENERIC_KEYWORDS:
        return 0.58
    if " " in keyword:
        return 1.0
    if len(keyword) >= 7:
        return 0.94
    return 0.86


def _window_starts(duration_s: float, window_s: float, step_s: float) -> list[float]:
    if duration_s <= window_s:
        return [0.0]
    starts: list[float] = []
    current = 0.0
    final_start = max(0.0, duration_s - window_s)
    while current < final_start:
        starts.append(round(current, 6))
        current += step_s
    if not starts or starts[-1] < final_start:
        starts.append(round(final_start, 6))
    return starts


def _duration_from_moments(moments: list[RewardMoment], duration_s: float | None) -> float:
    if duration_s is not None:
        return max(0.0, float(duration_s))
    if not moments:
        return 0.0
    return max(max(moment.t_end, moment.t_start) for moment in moments)


def _event_time(event: CandidateEvent | RewardMoment) -> float:
    return (event.t_start + event.t_end) / 2.0


def _overlaps(start_a: float, end_a: float, start_b: float, end_b: float) -> bool:
    return max(start_a, start_b) <= min(end_a, end_b)


def _canonical_label(value: str) -> str:
    normalized = _normalize_text(value).replace(" ", "_")
    if normalized.startswith("ocr_"):
        normalized = normalized.removeprefix("ocr_")
    if normalized.startswith("audio_"):
        normalized = normalized.removeprefix("audio_")
    return _LABEL_ALIASES.get(normalized, normalized)


def _normalize_text(value: str) -> str:
    return " ".join(value.casefold().replace("_", " ").replace("-", " ").split())


def _dict_value(value: JsonValue | None) -> dict[str, JsonValue]:
    return value if isinstance(value, dict) else {}


def _string_values(value: JsonValue | None) -> list[str]:
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _confidence(value: float) -> float:
    return _clamp(float(value), 0.0, 1.0)


def _positive_float(value: Any, default: float) -> float:
    number = _as_float(value, default)
    return number if number > 0 else default


def _bounded_float(value: Any, default: float, low: float, high: float) -> float:
    return _clamp(_as_float(value, default), low, high)


def _as_float(value: Any, default: float) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, int | float | str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))
