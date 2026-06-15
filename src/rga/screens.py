"""Screen-state/template classifier for the specialist pipeline.

Inputs:
- FrameSample records from ingest.sample_frames
- OCR CandidateEvent records from ocr.read_rois
- loaded GameConfig containing screen states and template definitions

Output:
- CandidateEvent records with modality=Modality.SCREEN

The detector is deliberately conservative for reward-bearing states. OCR and
template evidence can emit high-confidence labels; color/layout probes mostly
support those decisions and only emit neutral states when the visual signature
is strong.
"""

from __future__ import annotations

import math
import re
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import cv2
    import numpy as np
except ModuleNotFoundError:
    cv2 = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]

from .contracts import CandidateEvent, EvidenceRef, FrameSample, GameConfig, JsonValue, Modality, Phase


_CANONICAL_LABELS = ("combat", "explore", "reward_screen", "shop", "victory", "death", "map", "menu")
_LABEL_ALIASES = {
    "exploration": "explore",
    "explore": "explore",
    "reward": "reward_screen",
    "reward_screen": "reward_screen",
    "rewards": "reward_screen",
}
_GENERIC_REWARD_KEYWORDS = {"take", "skip", "proceed"}
_HIGH_RISK_LABELS = {"reward_screen", "shop", "victory", "death"}
_DEFAULT_MIN_CONFIDENCE = {
    "reward_screen": 0.65,
    "shop": 0.70,
    "victory": 0.65,
    "death": 0.78,
    "menu": 0.72,
    "combat": 0.70,
    "map": 0.70,
    "explore": 0.55,
}
_BUILTIN_KEYWORDS = {
    "reward_screen": ("choose a card", "reward", "rewards", "relic", "take", "skip"),
    "shop": ("shop", "merchant", "purge", "remove a card", "sale"),
    "victory": ("victory", "proceed"),
    "death": ("you died", "death", "defeat", "defeated", "game over", "slain"),
    "menu": ("settings", "options", "resume", "abandon run", "save and quit", "main menu", "return"),
    "map": ("map", "choose next", "next room"),
    "combat": (),
    "explore": (),
}
_STATE_PRIORITY = {
    "victory": 0,
    "death": 1,
    "reward_screen": 2,
    "shop": 3,
    "menu": 4,
    "map": 5,
    "combat": 6,
    "explore": 7,
}


@dataclass(frozen=True)
class _StateSpec:
    key: str
    label: str
    positive_keywords: tuple[str, ...]
    template_ids: tuple[str, ...]
    positive_rois: tuple[str, ...]
    min_confidence: float


@dataclass(frozen=True)
class _TemplateSpec:
    id: str
    path: Path
    roi_id: str | None
    label: str
    threshold: float


@dataclass(frozen=True)
class _TemplateMatch:
    template_id: str
    score: float
    threshold: float
    roi_id: str | None
    path: str
    available: bool


@dataclass(frozen=True)
class _RoiFeatures:
    roi_id: str
    mean_h: float
    mean_s: float
    mean_v: float
    std_v: float
    edge_density: float
    dark_ratio: float
    bright_ratio: float
    tan_ratio: float
    green_ratio: float
    red_ratio: float
    blue_ratio: float


@dataclass(frozen=True)
class _OcrEvidence:
    text: str
    confidence: float
    roi_id: str | None
    timestamp: float
    label: str


@dataclass(frozen=True)
class _FrameWindow:
    frame: FrameSample
    t_start: float
    t_end: float


@dataclass(frozen=True)
class _StateScore:
    state_key: str
    label: str
    confidence: float
    keyword_score: float
    color_score: float
    template_score: float
    matched_keywords: tuple[str, ...]
    matched_template: _TemplateMatch | None
    min_confidence: float
    details: dict[str, JsonValue] = field(default_factory=dict)


@dataclass(frozen=True)
class _FrameDecision:
    window: _FrameWindow
    score: _StateScore
    low_confidence_fallback: bool = False


def classify(
    frames: list[FrameSample],
    ocr_candidates: list[CandidateEvent],
    config: GameConfig,
) -> list[CandidateEvent]:
    """Classify screen states from frames, templates, layout/color, and OCR.

    The returned candidates are grouped into contiguous same-label windows.
    Reward-bearing labels require configured threshold confidence; ambiguous
    visual-only reward/shop/victory/death hints are left un-emitted.
    """

    if not frames:
        return []

    state_specs = _state_specs(config)
    template_specs = _template_specs(config)
    frame_windows = _frame_windows(sorted(frames, key=lambda frame: (frame.timestamp, frame.frame_index)))
    ocr_evidence = [_ocr_evidence(candidate) for candidate in ocr_candidates]
    ocr_evidence = [item for item in ocr_evidence if item is not None]

    decisions: list[_FrameDecision] = []
    for window in frame_windows:
        image = _read_image(window.frame.path)
        roi_features = _roi_features(image, window.frame, config) if image is not None else {}
        template_matches = _match_templates(image, window.frame, config, template_specs) if image is not None else {}
        nearby_ocr = _ocr_for_window(ocr_evidence, window.t_start, window.t_end)
        decision = _classify_window(window, state_specs, roi_features, template_matches, nearby_ocr)
        if decision is not None:
            decisions.append(decision)

    return _merge_decisions(decisions)


def _classify_window(
    window: _FrameWindow,
    state_specs: list[_StateSpec],
    roi_features: dict[str, _RoiFeatures],
    template_matches: dict[str, _TemplateMatch],
    ocr_evidence: list[_OcrEvidence],
) -> _FrameDecision | None:
    scores = [
        _score_state(spec, roi_features, template_matches, ocr_evidence)
        for spec in state_specs
    ]
    scores = [score for score in scores if score.confidence > 0.0]
    if not scores:
        return None

    scores.sort(key=lambda score: (-score.confidence, _STATE_PRIORITY.get(score.label, 99), score.label))
    best = scores[0]
    if best.confidence >= best.min_confidence:
        return _FrameDecision(window=window, score=best)

    fallback = _neutral_fallback(window, scores, roi_features)
    if fallback is None:
        return None
    return fallback


def _score_state(
    spec: _StateSpec,
    roi_features: dict[str, _RoiFeatures],
    template_matches: dict[str, _TemplateMatch],
    ocr_evidence: list[_OcrEvidence],
) -> _StateScore:
    keyword_score, matched_keywords = _keyword_score(spec, ocr_evidence)
    color_score = _color_score(spec.label, roi_features)
    matched_template = _best_template_match(spec, template_matches)
    template_score = 0.0
    if matched_template is not None and matched_template.available:
        template_score = matched_template.score

    confidence = 0.0
    sources: list[str] = []
    if keyword_score > 0.0:
        confidence = max(confidence, 0.62 + (0.27 * keyword_score))
        sources.append("ocr")
    if matched_template is not None and matched_template.available:
        if matched_template.score >= matched_template.threshold:
            normalized = _safe_ratio(
                matched_template.score - matched_template.threshold,
                max(1.0 - matched_template.threshold, 1e-6),
            )
            confidence = max(confidence, 0.72 + (0.23 * min(1.0, normalized)))
            sources.append("template")
        else:
            confidence = max(confidence, min(0.50, matched_template.score * 0.45))
    if color_score > 0.0:
        if spec.label in {"combat", "map"}:
            confidence = max(confidence, color_score)
            if color_score >= 0.55:
                sources.append("color_layout")
        elif spec.label in _HIGH_RISK_LABELS:
            confidence = max(confidence, min(color_score, spec.min_confidence - 0.02))
        else:
            confidence = max(confidence, min(color_score, 0.68))
            if color_score >= 0.55:
                sources.append("color_layout")

    if keyword_score > 0.0 and matched_template is not None and matched_template.score >= matched_template.threshold:
        confidence += 0.08
    if keyword_score >= 0.45 and color_score >= 0.45:
        confidence += 0.04
    if matched_template is not None and matched_template.score >= matched_template.threshold and color_score >= 0.45:
        confidence += 0.03

    if spec.label == "reward_screen" and set(matched_keywords).issubset(_GENERIC_REWARD_KEYWORDS):
        if matched_template is None or matched_template.score < matched_template.threshold:
            confidence = min(confidence, spec.min_confidence - 0.01)

    confidence = _clamp(confidence, 0.0, 0.99)
    details: dict[str, JsonValue] = {
        "sources": sources,
        "keyword_score": round(keyword_score, 4),
        "color_score": round(color_score, 4),
        "template_score": round(template_score, 4),
        "min_confidence": spec.min_confidence,
    }
    return _StateScore(
        state_key=spec.key,
        label=spec.label,
        confidence=confidence,
        keyword_score=keyword_score,
        color_score=color_score,
        template_score=template_score,
        matched_keywords=matched_keywords,
        matched_template=matched_template,
        min_confidence=spec.min_confidence,
        details=details,
    )


def _neutral_fallback(
    window: _FrameWindow,
    scores: list[_StateScore],
    roi_features: dict[str, _RoiFeatures],
) -> _FrameDecision | None:
    if not roi_features:
        return None

    best = scores[0]
    if best.label in _HIGH_RISK_LABELS and best.confidence >= 0.55:
        return None

    for label in ("combat", "map", "menu", "explore"):
        score = next((item for item in scores if item.label == label), None)
        if score is not None and score.confidence >= 0.48:
            fallback_score = _replace_confidence(score, min(score.confidence, 0.54))
            return _FrameDecision(window=window, score=fallback_score, low_confidence_fallback=True)

    explore = _StateScore(
        state_key="explore",
        label="explore",
        confidence=0.30,
        keyword_score=0.0,
        color_score=0.30,
        template_score=0.0,
        matched_keywords=(),
        matched_template=None,
        min_confidence=_DEFAULT_MIN_CONFIDENCE["explore"],
        details={"sources": ["low_confidence_visual_fallback"], "min_confidence": _DEFAULT_MIN_CONFIDENCE["explore"]},
    )
    return _FrameDecision(window=window, score=explore, low_confidence_fallback=True)


def _replace_confidence(score: _StateScore, confidence: float) -> _StateScore:
    details = dict(score.details)
    sources = details.get("sources")
    if isinstance(sources, list):
        details["sources"] = [*sources, "low_confidence_fallback"]
    else:
        details["sources"] = ["low_confidence_fallback"]
    return _StateScore(
        state_key=score.state_key,
        label=score.label,
        confidence=confidence,
        keyword_score=score.keyword_score,
        color_score=score.color_score,
        template_score=score.template_score,
        matched_keywords=score.matched_keywords,
        matched_template=score.matched_template,
        min_confidence=score.min_confidence,
        details=details,
    )


def _merge_decisions(decisions: list[_FrameDecision]) -> list[CandidateEvent]:
    if not decisions:
        return []

    sorted_decisions = sorted(
        decisions,
        key=lambda decision: (decision.window.t_start, decision.window.frame.frame_index, decision.score.label),
    )
    median_gap = _median_gap([decision.window.frame.timestamp for decision in sorted_decisions])
    merge_gap_s = max(1.25, median_gap * 1.75)

    groups: list[list[_FrameDecision]] = []
    for decision in sorted_decisions:
        if not groups:
            groups.append([decision])
            continue
        previous = groups[-1][-1]
        same_label = previous.score.label == decision.score.label
        close = decision.window.t_start <= previous.window.t_end + merge_gap_s
        if same_label and close:
            groups[-1].append(decision)
        else:
            groups.append([decision])

    return [_event_from_group(group) for group in groups]


def _event_from_group(group: list[_FrameDecision]) -> CandidateEvent:
    best = max(group, key=lambda decision: decision.score.confidence)
    start = min(decision.window.t_start for decision in group)
    end = max(decision.window.t_end for decision in group)
    confidence = max(decision.score.confidence for decision in group)
    labels = sorted({decision.score.state_key for decision in group})
    frame_confidences = [round(decision.score.confidence, 4) for decision in group]

    details: dict[str, JsonValue] = {
        "screen": best.score.label,
        "state_key": best.score.state_key,
        "state_keys_in_window": labels,
        "frame_count": len(group),
        "frame_confidences": frame_confidences,
        "low_confidence_fallback": any(decision.low_confidence_fallback for decision in group),
        "matched_keywords": list(best.score.matched_keywords),
        "score": _score_details(best.score),
    }
    if best.score.matched_template is not None:
        details["template_match"] = _template_details(best.score.matched_template)

    evidence: EvidenceRef = {
        "phase": Phase.SCREEN,
        "frame_index": best.window.frame.frame_index,
        "timestamp": best.window.frame.timestamp,
        "path": str(best.window.frame.path),
        "detector": "screens.classify",
        "details": details,
    }
    if best.score.matched_template is not None:
        evidence["template_id"] = best.score.matched_template.template_id
    if best.score.matched_template is not None and best.score.matched_template.roi_id is not None:
        evidence["roi_id"] = best.score.matched_template.roi_id
    elif best.score.label in {"combat", "reward_screen", "victory", "shop"}:
        evidence["roi_id"] = _primary_roi_for_label(best.score.label)

    value: JsonValue = {
        "screen": best.score.label,
        "phase": best.score.label,
        "state_key": best.score.state_key,
        "aliases": sorted({best.score.label, best.score.state_key}),
        "window": {"t_start": round(start, 4), "t_end": round(end, 4)},
        "frame_count": len(group),
    }
    return CandidateEvent(
        t_start=start,
        t_end=end,
        modality=Modality.SCREEN,
        label=best.score.label,
        value=value,
        confidence=round(confidence, 4),
        evidence_ref=evidence,
    )


def _state_specs(config: GameConfig) -> list[_StateSpec]:
    screen_states = _dict_value(config.get("screen_states"))
    specs: dict[str, _StateSpec] = {}

    for state_key, raw_state in screen_states.items():
        if not isinstance(raw_state, dict):
            continue
        key = str(state_key)
        label = _canonical_label(key)
        keywords = _string_tuple(raw_state.get("positive_keywords"))
        template_ids = _string_tuple(raw_state.get("template_ids"))
        positive_rois = _string_tuple(raw_state.get("positive_rois"))
        min_confidence = _as_float(raw_state.get("min_confidence"), _DEFAULT_MIN_CONFIDENCE.get(label, 0.75))
        specs[label] = _StateSpec(
            key=key,
            label=label,
            positive_keywords=_merge_keywords(label, keywords),
            template_ids=template_ids,
            positive_rois=positive_rois,
            min_confidence=_clamp(min_confidence, 0.0, 0.99),
        )

    for label in _CANONICAL_LABELS:
        if label in specs:
            continue
        specs[label] = _StateSpec(
            key=label,
            label=label,
            positive_keywords=_BUILTIN_KEYWORDS[label],
            template_ids=(),
            positive_rois=(),
            min_confidence=_DEFAULT_MIN_CONFIDENCE[label],
        )

    return sorted(specs.values(), key=lambda spec: _STATE_PRIORITY.get(spec.label, 99))


def _template_specs(config: GameConfig) -> dict[str, _TemplateSpec]:
    specs: dict[str, _TemplateSpec] = {}
    for raw_template in _list_value(config.get("templates")):
        if not isinstance(raw_template, dict):
            continue
        template_id = raw_template.get("id")
        path_value = raw_template.get("path")
        if not isinstance(template_id, str) or not isinstance(path_value, str):
            continue
        label = _canonical_label(str(raw_template.get("label", "")) or template_id)
        roi_id_value = raw_template.get("roi_id")
        specs[template_id] = _TemplateSpec(
            id=template_id,
            path=_resolve_repo_path(path_value),
            roi_id=roi_id_value if isinstance(roi_id_value, str) else None,
            label=label,
            threshold=_as_float(raw_template.get("match_threshold"), 0.82),
        )
    return specs


def _frame_windows(frames: list[FrameSample]) -> list[_FrameWindow]:
    if len(frames) == 1:
        frame = frames[0]
        return [_FrameWindow(frame=frame, t_start=max(0.0, frame.timestamp - 0.5), t_end=frame.timestamp + 0.5)]

    timestamps = [frame.timestamp for frame in frames]
    windows: list[_FrameWindow] = []
    for index, frame in enumerate(frames):
        if index == 0:
            next_gap = max(0.0, timestamps[index + 1] - frame.timestamp)
            start = max(0.0, frame.timestamp - (next_gap / 2.0))
        else:
            start = (timestamps[index - 1] + frame.timestamp) / 2.0

        if index == len(frames) - 1:
            previous_gap = max(0.0, frame.timestamp - timestamps[index - 1])
            end = frame.timestamp + (previous_gap / 2.0)
        else:
            end = (frame.timestamp + timestamps[index + 1]) / 2.0
        if end <= start:
            end = start + 0.001
        windows.append(_FrameWindow(frame=frame, t_start=start, t_end=end))
    return windows


def _read_image(path: Path) -> np.ndarray[Any, np.dtype[np.uint8]] | None:
    if cv2 is None:
        return None
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None or image.size == 0:
        return None
    return image


def _roi_features(
    image: np.ndarray[Any, np.dtype[np.uint8]],
    frame: FrameSample,
    config: GameConfig,
) -> dict[str, _RoiFeatures]:
    features: dict[str, _RoiFeatures] = {}
    for roi_id, raw_roi in _dict_value(config.get("rois")).items():
        if not isinstance(raw_roi, dict):
            continue
        crop = _crop_roi(image, frame, raw_roi)
        if crop is None:
            continue
        features[str(roi_id)] = _features_for_crop(str(roi_id), crop)
    return features


def _features_for_crop(roi_id: str, crop: np.ndarray[Any, np.dtype[np.uint8]]) -> _RoiFeatures:
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    hue = hsv[:, :, 0].astype(np.float32)
    sat = hsv[:, :, 1].astype(np.float32)
    val = hsv[:, :, 2].astype(np.float32)
    edges = cv2.Canny(gray, 80, 160)

    tan_mask = (hue >= 8) & (hue <= 35) & (sat >= 25) & (sat <= 205) & (val >= 70)
    green_mask = (hue >= 35) & (hue <= 95) & (sat >= 55) & (val >= 65)
    red_mask = ((hue <= 8) | (hue >= 168)) & (sat >= 55) & (val >= 45)
    blue_mask = (hue >= 92) & (hue <= 132) & (sat >= 45) & (val >= 50)

    return _RoiFeatures(
        roi_id=roi_id,
        mean_h=float(np.mean(hue) / 179.0),
        mean_s=float(np.mean(sat) / 255.0),
        mean_v=float(np.mean(val) / 255.0),
        std_v=float(np.std(val) / 255.0),
        edge_density=float(np.mean(edges > 0)),
        dark_ratio=float(np.mean(val < 65)),
        bright_ratio=float(np.mean(val > 190)),
        tan_ratio=float(np.mean(tan_mask)),
        green_ratio=float(np.mean(green_mask)),
        red_ratio=float(np.mean(red_mask)),
        blue_ratio=float(np.mean(blue_mask)),
    )


def _match_templates(
    image: np.ndarray[Any, np.dtype[np.uint8]],
    frame: FrameSample,
    config: GameConfig,
    templates: dict[str, _TemplateSpec],
) -> dict[str, _TemplateMatch]:
    matches: dict[str, _TemplateMatch] = {}
    for template in templates.values():
        if not template.path.exists():
            matches[template.id] = _TemplateMatch(
                template_id=template.id,
                score=0.0,
                threshold=template.threshold,
                roi_id=template.roi_id,
                path=str(template.path),
                available=False,
            )
            continue

        source = image
        if template.roi_id is not None:
            raw_roi = _dict_value(config.get("rois")).get(template.roi_id)
            if isinstance(raw_roi, dict):
                crop = _crop_roi(image, frame, raw_roi)
                if crop is not None:
                    source = crop

        template_image = _read_image(template.path)
        score = _template_score(source, template_image) if template_image is not None else 0.0
        matches[template.id] = _TemplateMatch(
            template_id=template.id,
            score=score,
            threshold=template.threshold,
            roi_id=template.roi_id,
            path=str(template.path),
            available=template_image is not None,
        )
    return matches


def _template_score(
    source: np.ndarray[Any, np.dtype[np.uint8]],
    template: np.ndarray[Any, np.dtype[np.uint8]],
) -> float:
    if source.size == 0 or template.size == 0:
        return 0.0

    source_gray = cv2.cvtColor(source, cv2.COLOR_BGR2GRAY)
    template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
    source_h, source_w = source_gray.shape[:2]
    template_h, template_w = template_gray.shape[:2]

    if template_h > source_h or template_w > source_w:
        scale = min(source_h / max(template_h, 1), source_w / max(template_w, 1))
        if scale <= 0:
            return 0.0
        new_size = (max(1, int(template_w * scale)), max(1, int(template_h * scale)))
        template_gray = cv2.resize(template_gray, new_size, interpolation=cv2.INTER_AREA)

    if template_gray.shape == source_gray.shape:
        source_norm = source_gray.astype(np.float32)
        template_norm = template_gray.astype(np.float32)
        source_std = float(np.std(source_norm))
        template_std = float(np.std(template_norm))
        if source_std < 1e-6 or template_std < 1e-6:
            return 0.0
        score = float(np.corrcoef(source_norm.ravel(), template_norm.ravel())[0, 1])
        if math.isnan(score):
            return 0.0
        return _clamp((score + 1.0) / 2.0, 0.0, 1.0)

    result = cv2.matchTemplate(source_gray, template_gray, cv2.TM_CCOEFF_NORMED)
    if result.size == 0:
        return 0.0
    score = float(np.max(result))
    if math.isnan(score):
        return 0.0
    return _clamp(score, 0.0, 1.0)


def _crop_roi(
    image: np.ndarray[Any, np.dtype[np.uint8]],
    frame: FrameSample,
    roi: dict[str, JsonValue],
) -> np.ndarray[Any, np.dtype[np.uint8]] | None:
    height, width = image.shape[:2]
    frame_width = frame.width if frame.width > 0 else width
    frame_height = frame.height if frame.height > 0 else height
    scale_x = width / frame_width
    scale_y = height / frame_height

    x = _as_float(roi.get("x"), 0.0)
    y = _as_float(roi.get("y"), 0.0)
    w = _as_float(roi.get("w"), 0.0)
    h = _as_float(roi.get("h"), 0.0)
    if w <= 0.0 or h <= 0.0:
        return None

    left = int(round(_clamp(x, 0.0, 1.0) * frame_width * scale_x))
    top = int(round(_clamp(y, 0.0, 1.0) * frame_height * scale_y))
    right = int(round(_clamp(x + w, 0.0, 1.0) * frame_width * scale_x))
    bottom = int(round(_clamp(y + h, 0.0, 1.0) * frame_height * scale_y))
    left = max(0, min(width - 1, left))
    top = max(0, min(height - 1, top))
    right = max(left + 1, min(width, right))
    bottom = max(top + 1, min(height, bottom))
    crop = image[top:bottom, left:right]
    return crop if crop.size else None


def _keyword_score(spec: _StateSpec, ocr_evidence: list[_OcrEvidence]) -> tuple[float, tuple[str, ...]]:
    if not spec.positive_keywords or not ocr_evidence:
        return 0.0, ()

    scores: list[float] = []
    matched: list[str] = []
    for keyword in spec.positive_keywords:
        normalized = _normalize_text(keyword)
        if not normalized:
            continue
        for evidence in ocr_evidence:
            if _text_contains_keyword(evidence.text, normalized):
                specificity = _keyword_specificity(normalized)
                scores.append(_clamp(evidence.confidence, 0.20, 1.0) * specificity)
                matched.append(normalized)
                break

    if not scores:
        return 0.0, ()

    combined = 1.0
    for score in scores:
        combined *= 1.0 - _clamp(score, 0.0, 0.95)
    return 1.0 - combined, tuple(sorted(set(matched)))


def _text_contains_keyword(text: str, keyword: str) -> bool:
    if " " in keyword:
        return keyword in text
    return re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", text) is not None


def _keyword_specificity(keyword: str) -> float:
    if keyword in _GENERIC_REWARD_KEYWORDS:
        return 0.48
    if " " in keyword:
        return 1.0
    if len(keyword) >= 7:
        return 0.90
    return 0.74


def _best_template_match(
    spec: _StateSpec,
    template_matches: dict[str, _TemplateMatch],
) -> _TemplateMatch | None:
    candidate_ids = set(spec.template_ids)
    if not candidate_ids:
        candidate_ids = {
            template_id
            for template_id, match in template_matches.items()
            if _canonical_label(template_id) == spec.label or _canonical_label(match.template_id) == spec.label
        }
    matches = [template_matches[template_id] for template_id in candidate_ids if template_id in template_matches]
    if not matches:
        return None
    return max(matches, key=lambda match: match.score)


def _color_score(label: str, features: dict[str, _RoiFeatures]) -> float:
    full = features.get("full_frame")
    top = features.get("top_banner")
    center = features.get("center_panel")
    energy = features.get("energy_hud")

    if label == "combat" and energy is not None:
        score = 0.32 + (0.30 * energy.mean_s) + (0.30 * _safe_ratio(energy.edge_density, 0.14))
        score += 0.10 * (energy.bright_ratio + energy.dark_ratio)
        return _clamp(score, 0.0, 0.82)

    if label == "map" and full is not None:
        edge_target = 1.0 - min(1.0, abs(full.edge_density - 0.08) / 0.08)
        score = 0.24 + (0.34 * full.tan_ratio) + (0.16 * edge_target) + (0.10 * (1.0 - full.mean_s))
        if energy is not None and energy.mean_s > 0.35 and energy.edge_density > 0.06:
            score -= 0.12
        return _clamp(score, 0.0, 0.76)

    if label == "reward_screen" and center is not None:
        score = 0.22 + (0.18 * _safe_ratio(center.edge_density, 0.16))
        score += 0.12 * _safe_ratio(center.std_v, 0.28)
        score += 0.10 * center.dark_ratio
        return _clamp(score, 0.0, 0.58)

    if label == "victory":
        regions = [region for region in (top, center) if region is not None]
        if not regions:
            return 0.0
        green = max(region.green_ratio for region in regions)
        edge = max(region.edge_density for region in regions)
        bright = max(region.bright_ratio for region in regions)
        return _clamp(0.28 + (0.22 * _safe_ratio(green, 0.20)) + (0.12 * _safe_ratio(edge, 0.14)) + (0.08 * bright), 0.0, 0.62)

    if label == "shop" and center is not None:
        score = 0.20 + (0.18 * _safe_ratio(center.edge_density, 0.14)) + (0.14 * center.tan_ratio)
        return _clamp(score, 0.0, 0.58)

    if label == "death" and full is not None:
        gray_dark = full.dark_ratio * (1.0 - full.mean_s)
        red_hint = min(0.20, full.red_ratio)
        return _clamp(0.20 + (0.32 * gray_dark) + red_hint, 0.0, 0.60)

    if label == "menu":
        regions = [region for region in (center, full) if region is not None]
        if not regions:
            return 0.0
        dark_panel = max(region.dark_ratio for region in regions)
        edge = max(region.edge_density for region in regions)
        return _clamp(0.18 + (0.18 * dark_panel) + (0.18 * _safe_ratio(edge, 0.16)), 0.0, 0.56)

    if label == "explore" and full is not None:
        if energy is not None and energy.mean_s > 0.35 and energy.edge_density > 0.05:
            return 0.0
        return _clamp(0.24 + (0.16 * full.mean_s) + (0.12 * _safe_ratio(full.edge_density, 0.16)), 0.0, 0.48)

    return 0.0


def _ocr_evidence(candidate: CandidateEvent) -> _OcrEvidence | None:
    text = _extract_text(candidate)
    normalized = _normalize_text(text)
    if not normalized:
        return None
    timestamp = candidate.t_start
    if "timestamp" in candidate.evidence_ref and isinstance(candidate.evidence_ref["timestamp"], int | float):
        timestamp = float(candidate.evidence_ref["timestamp"])
    roi_id = candidate.evidence_ref.get("roi_id")
    return _OcrEvidence(
        text=normalized,
        confidence=_clamp(candidate.confidence, 0.0, 1.0),
        roi_id=roi_id if isinstance(roi_id, str) else None,
        timestamp=timestamp,
        label=candidate.label,
    )


def _extract_text(candidate: CandidateEvent) -> str:
    fragments: list[str] = []
    _collect_text(candidate.value, fragments)
    _collect_text(candidate.label, fragments)
    details = candidate.evidence_ref.get("details")
    if isinstance(details, dict):
        _collect_text(details, fragments)
    return " ".join(fragments)


def _collect_text(value: Any, fragments: list[str]) -> None:
    if isinstance(value, str):
        fragments.append(value)
        return
    if isinstance(value, int | float | bool) or value is None:
        return
    if isinstance(value, list):
        for item in value:
            _collect_text(item, fragments)
        return
    if isinstance(value, dict):
        for key in ("text", "raw_text", "normalized_text", "line", "word", "words", "lines", "tokens", "value"):
            if key in value:
                _collect_text(value[key], fragments)


def _ocr_for_window(
    ocr_evidence: list[_OcrEvidence],
    start: float,
    end: float,
) -> list[_OcrEvidence]:
    slack = max(0.35, min(1.0, (end - start) * 0.75))
    return [
        item
        for item in ocr_evidence
        if start - slack <= item.timestamp <= end + slack
    ]


def _score_details(score: _StateScore) -> dict[str, JsonValue]:
    details = dict(score.details)
    details.update(
        {
            "state_key": score.state_key,
            "label": score.label,
            "confidence": round(score.confidence, 4),
            "matched_keywords": list(score.matched_keywords),
        }
    )
    return details


def _template_details(match: _TemplateMatch) -> dict[str, JsonValue]:
    return {
        "template_id": match.template_id,
        "score": round(match.score, 4),
        "threshold": match.threshold,
        "roi_id": match.roi_id,
        "path": match.path,
        "available": match.available,
    }


def _primary_roi_for_label(label: str) -> str:
    if label == "combat":
        return "energy_hud"
    if label == "victory":
        return "top_banner"
    if label in {"reward_screen", "shop"}:
        return "center_panel"
    return "full_frame"


def _merge_keywords(label: str, configured: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    merged: list[str] = []
    for keyword in (*configured, *_BUILTIN_KEYWORDS.get(label, ())):
        normalized = _normalize_text(keyword)
        if normalized and normalized not in seen:
            seen.add(normalized)
            merged.append(normalized)
    return tuple(merged)


def _canonical_label(value: str) -> str:
    normalized = _normalize_text(value).replace("-", "_")
    if normalized in _LABEL_ALIASES:
        return _LABEL_ALIASES[normalized]
    if "reward" in normalized:
        return "reward_screen"
    for label in _CANONICAL_LABELS:
        if label in normalized:
            return label
    return normalized


def _resolve_repo_path(path_value: str) -> Path:
    path = Path(path_value).expanduser()
    if path.is_absolute():
        return path
    repo_root = Path(__file__).resolve().parents[2]
    for base in (Path.cwd(), repo_root):
        candidate = base / path
        if candidate.exists():
            return candidate
    return repo_root / path


def _median_gap(timestamps: list[float]) -> float:
    if len(timestamps) < 2:
        return 1.0
    gaps = [
        later - earlier
        for earlier, later in zip(sorted(timestamps), sorted(timestamps)[1:])
        if later > earlier
    ]
    if not gaps:
        return 1.0
    return float(statistics.median(gaps))


def _dict_value(value: JsonValue | None) -> dict[str, JsonValue]:
    return value if isinstance(value, dict) else {}


def _list_value(value: JsonValue | None) -> list[JsonValue]:
    return value if isinstance(value, list) else []


def _string_tuple(value: JsonValue | None) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if isinstance(item, str))


def _as_float(value: Any, default: float) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, int | float | str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _safe_ratio(value: float, denominator: float) -> float:
    if denominator <= 0.0:
        return 0.0
    return _clamp(value / denominator, 0.0, 1.0)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(maximum, max(minimum, value))
