"""OCR-on-ROI detector for configured game HUD regions.

The detector reads only configured ROIs from sampled frames. It emits OCR
candidate evidence for later screen-state and fusion stages; it does not try to
infer final reward moments by itself.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from .contracts import CandidateEvent, FrameSample, GameConfig, JsonValue, Modality, Phase, RoiSpec


_OCR_ENGINE_CACHE: dict[tuple[str, str, str], Any] = {}
_NON_WORD_RE = re.compile(r"[^0-9a-z]+")
_SPACE_RE = re.compile(r"\s+")
_NUMBER_RE = re.compile(r"\d+(?:\s*/\s*\d+)?")


@dataclass(frozen=True)
class _OcrLine:
    text: str
    confidence: float


@dataclass(frozen=True)
class _Crop:
    image: Any
    bounds_xyxy: tuple[int, int, int, int]


def read_rois(frames: list[FrameSample], config: GameConfig) -> list[CandidateEvent]:
    """Run PaddleOCR on configured ROIs and return OCR candidate events."""

    if not frames:
        return []

    ocr_config = _dict_value(config.get("ocr"))
    backend = str(ocr_config.get("backend", "paddleocr")).casefold()
    if backend != "paddleocr":
        raise ValueError(f"Unsupported OCR backend: {backend!r}")

    rois = _roi_specs(config)
    roi_ids = _configured_roi_ids(ocr_config, rois)
    if not roi_ids:
        return []

    lang = str(ocr_config.get("lang", "en"))
    model = str(ocr_config.get("model", "PP-OCRv5"))
    keywords = _keyword_list(ocr_config.get("keywords"))
    thresholds = _thresholds(ocr_config)
    engine = _paddle_engine(lang=lang, model=model)

    candidates: list[CandidateEvent] = []
    for frame in frames:
        for roi_id in roi_ids:
            roi = rois[roi_id]
            crop = _crop_frame(frame, roi)
            lines = _read_crop(engine, crop.image)
            if not lines:
                continue

            text = _joined_text(lines)
            confidence = _aggregate_confidence(lines)
            matched_keywords = _matched_keywords(text, keywords)
            numbers = _numbers(text)
            kind = _candidate_kind(roi_id, matched_keywords, numbers)
            if not _passes_threshold(kind, confidence, thresholds):
                continue

            value = _candidate_value(
                roi_id=roi_id,
                kind=kind,
                text=text,
                lines=lines,
                matched_keywords=matched_keywords,
                numbers=numbers,
                backend=backend,
                model=model,
                lang=lang,
            )
            candidates.append(
                CandidateEvent(
                    t_start=frame.timestamp,
                    t_end=frame.timestamp,
                    modality=Modality.OCR,
                    label=f"ocr_{kind}",
                    value=value,
                    confidence=confidence,
                    evidence_ref={
                        "phase": Phase.OCR,
                        "frame_index": frame.frame_index,
                        "timestamp": frame.timestamp,
                        "path": str(frame.path),
                        "roi_id": roi_id,
                        "detector": f"paddleocr:{model}",
                        "details": {
                            "crop_xyxy": list(crop.bounds_xyxy),
                            "frame_width": frame.width,
                            "frame_height": frame.height,
                            "matched_keywords": matched_keywords,
                            "text": text,
                        },
                    },
                )
            )
    return candidates


def _dict_value(value: JsonValue | None) -> dict[str, JsonValue]:
    return value if isinstance(value, dict) else {}


def _list_value(value: JsonValue | None) -> list[JsonValue]:
    return value if isinstance(value, list) else []


def _as_float(value: Any, default: float) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, int | float | str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _roi_specs(config: GameConfig) -> dict[str, RoiSpec]:
    raw_rois = config.get("rois")
    if not isinstance(raw_rois, dict):
        return {}

    rois: dict[str, RoiSpec] = {}
    for roi_id, raw_roi in raw_rois.items():
        if not isinstance(raw_roi, dict):
            continue
        x = _as_float(raw_roi.get("x"), -1.0)
        y = _as_float(raw_roi.get("y"), -1.0)
        w = _as_float(raw_roi.get("w"), -1.0)
        h = _as_float(raw_roi.get("h"), -1.0)
        if x < 0 or y < 0 or w <= 0 or h <= 0:
            continue
        if x > 1 or y > 1:
            continue
        rois[str(roi_id)] = {"x": x, "y": y, "w": min(w, 1.0 - x), "h": min(h, 1.0 - y)}
    return rois


def _configured_roi_ids(ocr_config: dict[str, JsonValue], rois: dict[str, RoiSpec]) -> list[str]:
    configured = [str(value) for value in _list_value(ocr_config.get("roi_ids")) if isinstance(value, str)]
    roi_ids = configured or list(rois)
    return [roi_id for roi_id in roi_ids if roi_id in rois]


def _keyword_list(value: JsonValue | None) -> list[str]:
    keywords: list[str] = []
    for item in _list_value(value):
        if not isinstance(item, str):
            continue
        normalized = _normalize_text(item)
        if normalized and normalized not in keywords:
            keywords.append(normalized)
    return keywords


def _thresholds(ocr_config: dict[str, JsonValue]) -> dict[str, float]:
    return {
        "keyword": _as_float(ocr_config.get("keyword_min_confidence"), 0.60),
        "numeric": _as_float(ocr_config.get("numeric_min_confidence"), 0.65),
        "text": _as_float(ocr_config.get("text_min_confidence"), 0.75),
    }


def _paddle_engine(lang: str, model: str) -> Any:
    cache_key = (lang, model, "paddleocr")
    cached = _OCR_ENGINE_CACHE.get(cache_key)
    if cached is not None:
        return cached

    try:
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise RuntimeError("paddleocr is required for rga.ocr.read_rois") from exc

    attempts: list[dict[str, Any]] = [
        {
            "lang": lang,
            "ocr_version": model,
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
            "use_textline_orientation": False,
        },
        {"lang": lang, "ocr_version": model, "use_angle_cls": False},
        {"lang": lang, "use_angle_cls": False},
        {"lang": lang},
    ]
    last_error: TypeError | ValueError | None = None
    for kwargs in attempts:
        try:
            engine = PaddleOCR(**kwargs)
            _OCR_ENGINE_CACHE[cache_key] = engine
            return engine
        except (TypeError, ValueError) as exc:
            last_error = exc

    if last_error is not None:
        raise RuntimeError(f"Could not initialize PaddleOCR for lang={lang!r}, model={model!r}") from last_error
    raise RuntimeError(f"Could not initialize PaddleOCR for lang={lang!r}, model={model!r}")


def _crop_frame(frame: FrameSample, roi: RoiSpec) -> _Crop:
    image = _load_image(frame.path)
    height, width = image.shape[:2]
    x0 = _clamp_int(round(roi["x"] * width), 0, width - 1)
    y0 = _clamp_int(round(roi["y"] * height), 0, height - 1)
    x1 = _clamp_int(round((roi["x"] + roi["w"]) * width), x0 + 1, width)
    y1 = _clamp_int(round((roi["y"] + roi["h"]) * height), y0 + 1, height)
    return _Crop(image=image[y0:y1, x0:x1], bounds_xyxy=(x0, y0, x1, y1))


def _load_image(path: Path) -> Any:
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("opencv-python is required for rga.ocr.read_rois") from exc

    image = cv2.imread(str(path))
    if image is None:
        raise ValueError(f"Could not read frame image: {path}")
    return image


def _clamp_int(value: int, low: int, high: int) -> int:
    return max(low, min(value, high))


def _read_crop(engine: Any, image: Any) -> list[_OcrLine]:
    result: Any | None = None
    if hasattr(engine, "predict"):
        try:
            result = engine.predict(input=image)
        except TypeError:
            result = engine.predict(image)
    lines = _extract_lines(result)
    if not lines and hasattr(engine, "ocr"):
        try:
            result = engine.ocr(image, cls=False)
        except TypeError:
            result = engine.ocr(image)
        lines = _extract_lines(result)
    return _dedupe_lines(lines)


def _extract_lines(result: Any) -> list[_OcrLine]:
    lines: list[_OcrLine] = []
    _collect_lines(result, lines)
    return lines


def _collect_lines(value: Any, lines: list[_OcrLine]) -> None:
    if value is None or isinstance(value, str):
        return

    data = _json_like(value)
    if data is not value:
        _collect_lines(data, lines)
        return

    if isinstance(value, dict):
        extracted = _lines_from_mapping(value)
        if extracted:
            lines.extend(extracted)
            return
        for child in value.values():
            _collect_lines(child, lines)
        return

    if isinstance(value, tuple):
        line = _line_from_pair(value)
        if line is not None:
            lines.append(line)
            return

    if isinstance(value, list):
        line = _line_from_detection_item(value)
        if line is not None:
            lines.append(line)
            return
        for child in value:
            _collect_lines(child, lines)


def _json_like(value: Any) -> Any:
    json_attr = getattr(value, "json", None)
    if json_attr is None:
        return value

    payload = json_attr() if callable(json_attr) else json_attr
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return value
    if isinstance(payload, dict | list):
        return payload
    return value


def _lines_from_mapping(value: dict[Any, Any]) -> list[_OcrLine]:
    texts = _sequence_value(value, ("rec_texts", "texts", "text", "labels"))
    scores = _sequence_value(value, ("rec_scores", "scores", "confidence", "confidences"))
    if not texts:
        return []

    lines: list[_OcrLine] = []
    for index, text_value in enumerate(texts):
        if not isinstance(text_value, str):
            continue
        score_value = scores[index] if index < len(scores) else 1.0
        line = _line(text_value, score_value)
        if line is not None:
            lines.append(line)
    return lines


def _sequence_value(value: dict[Any, Any], keys: tuple[str, ...]) -> list[Any]:
    for key in keys:
        item = value.get(key)
        if item is None:
            continue
        if isinstance(item, str):
            return [item]
        if isinstance(item, list | tuple):
            return list(item)
        return [item]
    return []


def _line_from_detection_item(value: list[Any]) -> _OcrLine | None:
    if len(value) >= 2:
        line = _line_from_pair(value[1])
        if line is not None:
            return line
    return _line_from_pair(value)


def _line_from_pair(value: Any) -> _OcrLine | None:
    if not isinstance(value, list | tuple) or len(value) < 2:
        return None
    text_value = value[0]
    score_value = value[1]
    if isinstance(text_value, str):
        return _line(text_value, score_value)
    return None


def _line(text: str, score: Any) -> _OcrLine | None:
    cleaned = _SPACE_RE.sub(" ", text).strip()
    if not cleaned:
        return None
    confidence = _as_float(score, 0.0)
    if confidence > 1.0:
        confidence = confidence / 100.0
    confidence = max(0.0, min(confidence, 1.0))
    return _OcrLine(text=cleaned, confidence=confidence)


def _dedupe_lines(lines: list[_OcrLine]) -> list[_OcrLine]:
    deduped: list[_OcrLine] = []
    seen: set[str] = set()
    for line in sorted(lines, key=lambda item: item.confidence, reverse=True):
        key = _normalize_text(line.text)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(line)
    return deduped


def _joined_text(lines: list[_OcrLine]) -> str:
    return _SPACE_RE.sub(" ", " ".join(line.text for line in lines)).strip()


def _aggregate_confidence(lines: list[_OcrLine]) -> float:
    if not lines:
        return 0.0
    return min(line.confidence for line in lines)


def _normalize_text(text: str) -> str:
    normalized = _NON_WORD_RE.sub(" ", text.casefold())
    return _SPACE_RE.sub(" ", normalized).strip()


def _matched_keywords(text: str, keywords: list[str]) -> list[str]:
    normalized = _normalize_text(text)
    if not normalized:
        return []

    tokens = normalized.split()
    token_set = set(tokens)
    padded = f" {normalized} "
    squashed = normalized.replace(" ", "")
    matches: list[str] = []
    for keyword in keywords:
        keyword_tokens = keyword.split()
        if len(keyword_tokens) == 1:
            if keyword in token_set:
                matches.append(keyword)
            continue
        if f" {keyword} " in padded or keyword.replace(" ", "") in squashed:
            matches.append(keyword)
    return matches


def _numbers(text: str) -> list[dict[str, JsonValue]]:
    numbers: list[dict[str, JsonValue]] = []
    for match in _NUMBER_RE.finditer(text):
        raw = _SPACE_RE.sub("", match.group(0))
        if "/" in raw:
            left, right = raw.split("/", 1)
            numbers.append({"raw": raw, "current": int(left), "maximum": int(right)})
        else:
            numbers.append({"raw": raw, "value": int(raw)})
    return numbers


def _candidate_kind(roi_id: str, matched_keywords: list[str], numbers: list[dict[str, JsonValue]]) -> str:
    if matched_keywords:
        return "keyword"
    if numbers and ("hud" in roi_id or "gold" in roi_id or "energy" in roi_id):
        return "numeric"
    return "text"


def _passes_threshold(kind: str, confidence: float, thresholds: dict[str, float]) -> bool:
    return confidence >= thresholds.get(kind, thresholds["text"])


def _candidate_value(
    *,
    roi_id: str,
    kind: str,
    text: str,
    lines: list[_OcrLine],
    matched_keywords: list[str],
    numbers: list[dict[str, JsonValue]],
    backend: str,
    model: str,
    lang: str,
) -> dict[str, JsonValue]:
    value: dict[str, JsonValue] = {
        "kind": kind,
        "roi_id": roi_id,
        "text": text,
        "lines": [
            {"text": line.text, "confidence": line.confidence}
            for line in lines
        ],
        "matched_keywords": matched_keywords,
        "numbers": cast(list[JsonValue], numbers),
        "backend": backend,
        "model": model,
        "lang": lang,
    }

    if numbers:
        first = numbers[0]
        if "value" in first:
            value["numeric_value"] = first["value"]
        if "current" in first and "maximum" in first:
            value["numeric_current"] = first["current"]
            value["numeric_maximum"] = first["maximum"]
    return value
