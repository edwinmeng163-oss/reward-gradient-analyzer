"""Evaluation harness for gold-label reward moments.

The evaluator is intentionally footage-agnostic: it can be run before any
first-party recordings or hand labels exist, and will report a pending status
instead of failing. When labels and prediction JSON are present, matching is a
one-to-one nearest-midpoint assignment within the configured tolerance.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any, Iterable, Sequence, cast

from .contracts import EvalScore, EvidenceRef, GoldLabel, RewardMoment


_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_ANNOTATIONS_DIR = Path("data/annotations")
_DEFAULT_RECORDINGS_DIR = Path("data/recordings")
_DEFAULT_PREDICTION_PATHS = (
    Path("data/outputs/reward_moments.json"),
    Path("data/output/reward_moments.json"),
    Path("outputs/reward_moments.json"),
    Path("reward_moments.json"),
    Path("timeline.json"),
)
_RECORDING_EXTENSIONS = {".avi", ".m4v", ".mkv", ".mov", ".mp4", ".webm"}
_ALLOWED_SOURCE_RIGHTS = {
    "first_party_self_recorded",
    "customer_uploaded_authorized",
    "partner_authorized",
    "synthetic_test",
}

JsonObject = dict[str, Any]


def score(
    predictions: list[RewardMoment],
    labels: list[GoldLabel],
    tolerance_s: float = 2.0,
) -> EvalScore:
    """Compute precision, recall, and median absolute timestamp error."""

    if tolerance_s < 0:
        raise ValueError("tolerance_s must be non-negative")

    reward_labels = [label for label in labels if label["type"] == "reward_moment"]
    candidate_pairs: list[tuple[float, int, int]] = []
    for label_index, label in enumerate(reward_labels):
        label_midpoint = _midpoint(label["t_start"], label["t_end"])
        for prediction_index, prediction in enumerate(predictions):
            prediction_midpoint = _midpoint(prediction.t_start, prediction.t_end)
            error_s = abs(prediction_midpoint - label_midpoint)
            if error_s <= tolerance_s:
                candidate_pairs.append((error_s, label_index, prediction_index))

    matched_labels: set[int] = set()
    matched_predictions: set[int] = set()
    errors: list[float] = []
    for error_s, label_index, prediction_index in sorted(candidate_pairs):
        if label_index in matched_labels or prediction_index in matched_predictions:
            continue
        matched_labels.add(label_index)
        matched_predictions.add(prediction_index)
        errors.append(error_s)

    true_positive = len(errors)
    label_count = len(reward_labels)
    prediction_count = len(predictions)
    false_positive = prediction_count - true_positive
    false_negative = label_count - true_positive

    return EvalScore(
        precision=_safe_ratio(true_positive, prediction_count),
        recall=_safe_ratio(true_positive, label_count),
        median_abs_error_s=statistics.median(errors) if errors else None,
        true_positive=true_positive,
        false_positive=false_positive,
        false_negative=false_negative,
        label_count=label_count,
        prediction_count=prediction_count,
    )


def load_gold_labels(annotation_path: Path, *, obvious_only: bool = True) -> list[GoldLabel]:
    """Load gold-label reward moments from one JSON file or a directory tree."""

    labels: list[GoldLabel] = []
    for json_path in _json_paths(annotation_path):
        document = _load_json(json_path)
        _validate_source_rights(document, json_path)
        for index, raw_event in enumerate(_event_records(document, json_path)):
            label = _parse_gold_label(raw_event, json_path, index)
            if label["type"] != "reward_moment":
                continue
            if obvious_only and not label.get("obvious", True):
                continue
            labels.append(label)
    return sorted(labels, key=lambda item: (item["t_start"], item["id"]))


def load_reward_moments(prediction_path: Path) -> list[RewardMoment]:
    """Load detected reward moments from one JSON file or a directory tree."""

    moments: list[RewardMoment] = []
    for json_path in _json_paths(prediction_path):
        document = _load_json(json_path)
        for index, raw_event in enumerate(_prediction_records(document, json_path)):
            moment = _parse_reward_moment(raw_event, json_path, index)
            if moment is not None:
                moments.append(moment)
    return sorted(moments, key=lambda item: (item.t_start, item.t_end, item.label))


def format_metrics_table(eval_score: EvalScore, *, tolerance_s: float, status: str = "ok") -> str:
    """Format an EvalScore as a compact Markdown metrics table."""

    median_error = (
        f"{eval_score.median_abs_error_s:.3f}s"
        if eval_score.median_abs_error_s is not None
        else "n/a"
    )
    rows = (
        ("status", status),
        ("tolerance_s", f"{tolerance_s:.3f}"),
        ("label_count", str(eval_score.label_count)),
        ("prediction_count", str(eval_score.prediction_count)),
        ("true_positive", str(eval_score.true_positive)),
        ("false_positive", str(eval_score.false_positive)),
        ("false_negative", str(eval_score.false_negative)),
        ("precision", f"{eval_score.precision:.3f}"),
        ("recall", f"{eval_score.recall:.3f}"),
        ("timestamp_median_abs_error", median_error),
    )
    return _markdown_table(rows)


def format_pending_table(reason: str, *, annotations: Path, recordings: Path, predictions: Path | None) -> str:
    """Format a pending status table for missing footage, labels, or predictions."""

    rows = [
        ("status", "metrics pending labeled footage"),
        ("reason", reason),
        ("annotations", str(annotations)),
        ("recordings", str(recordings)),
        ("predictions", str(predictions) if predictions is not None else "not provided"),
    ]
    return _markdown_table(rows)


def main(argv: Sequence[str] | None = None) -> int:
    """Run evaluator CLI and print a metrics table."""

    parser = argparse.ArgumentParser(description="Score detected reward_moments against gold labels.")
    parser.add_argument(
        "predictions",
        nargs="?",
        type=Path,
        help="Prediction JSON file or directory. Defaults to common reward_moments paths.",
    )
    parser.add_argument(
        "--annotations",
        type=Path,
        default=_DEFAULT_ANNOTATIONS_DIR,
        help="Gold-label JSON file or directory. Defaults to data/annotations.",
    )
    parser.add_argument(
        "--recordings",
        type=Path,
        default=_DEFAULT_RECORDINGS_DIR,
        help="Recording directory used only for pending-data detection.",
    )
    parser.add_argument(
        "--tolerance-s",
        type=float,
        default=2.0,
        help="Maximum midpoint error in seconds for a prediction/label match.",
    )
    parser.add_argument(
        "--include-non-obvious",
        action="store_true",
        help="Include low-confidence or non-obvious labels in the score.",
    )
    args = parser.parse_args(argv)

    annotations_path = _resolve_user_path(args.annotations)
    recordings_path = _resolve_user_path(args.recordings)
    prediction_path = _resolve_prediction_path(args.predictions)

    labels = load_gold_labels(annotations_path, obvious_only=not args.include_non_obvious)
    has_recordings = _has_recordings(recordings_path)
    if not labels:
        if not has_recordings:
            reason = "no gold labels under data/annotations and no recordings under data/recordings"
        else:
            reason = "no gold-label reward_moment annotations found"
        print(format_pending_table(reason, annotations=annotations_path, recordings=recordings_path, predictions=prediction_path))
        return 0

    if prediction_path is None:
        print(
            format_pending_table(
                "no detected reward_moments JSON found; run the pipeline or pass a prediction file",
                annotations=annotations_path,
                recordings=recordings_path,
                predictions=None,
            )
        )
        return 0

    predictions = load_reward_moments(prediction_path)
    eval_score = score(predictions, labels, tolerance_s=args.tolerance_s)
    print(format_metrics_table(eval_score, tolerance_s=args.tolerance_s))
    return 0


def _json_paths(path: Path) -> list[Path]:
    resolved = _resolve_user_path(path)
    if resolved.is_file():
        return [resolved] if resolved.suffix.lower() == ".json" else []
    if resolved.is_dir():
        return sorted(item for item in resolved.rglob("*.json") if item.is_file())
    return []


def _load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON at line {exc.lineno}, column {exc.colno}") from exc


def _event_records(document: Any, source: Path) -> list[JsonObject]:
    if isinstance(document, list):
        return _ensure_object_list(document, source, "top-level list")
    if isinstance(document, dict):
        events = document.get("events")
        if isinstance(events, list):
            return _ensure_object_list(events, source, "events")
    raise ValueError(f"{source}: expected a gold-label object with an events array")


def _prediction_records(document: Any, source: Path) -> list[JsonObject]:
    if isinstance(document, list):
        return _ensure_object_list(document, source, "top-level list")
    if isinstance(document, dict):
        for key in ("reward_moments", "predictions", "events", "timeline"):
            events = document.get(key)
            if isinstance(events, list):
                return _ensure_object_list(events, source, key)
    raise ValueError(f"{source}: expected prediction JSON with reward_moments, predictions, events, or timeline")


def _ensure_object_list(items: Iterable[Any], source: Path, field: str) -> list[JsonObject]:
    records: list[JsonObject] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"{source}: {field}[{index}] must be an object")
        records.append(item)
    return records


def _parse_gold_label(raw: JsonObject, source: Path, index: int) -> GoldLabel:
    record_id = _required_str(raw, "id", source, index)
    record_type = _required_str(raw, "type", source, index)
    t_start = _required_float(raw, "t_start", source, index)
    t_end = _required_float(raw, "t_end", source, index)
    if t_end < t_start:
        raise ValueError(f"{source}: events[{index}].t_end must be >= t_start")

    label: GoldLabel = {
        "id": record_id,
        "type": record_type,
        "t_start": t_start,
        "t_end": t_end,
        "label": _required_str(raw, "label", source, index),
    }

    if "obvious" in raw:
        label["obvious"] = _required_bool(raw, "obvious", source, index)
    if "confidence" in raw:
        label["confidence"] = _required_str(raw, "confidence", source, index)
    if "evidence_ref" in raw:
        evidence_ref = raw["evidence_ref"]
        if not isinstance(evidence_ref, dict):
            raise ValueError(f"{source}: events[{index}].evidence_ref must be an object")
        label["evidence_ref"] = cast(EvidenceRef, evidence_ref)
    if "notes" in raw:
        label["notes"] = _required_str(raw, "notes", source, index)

    return label


def _parse_reward_moment(raw: JsonObject, source: Path, index: int) -> RewardMoment | None:
    record_type = raw.get("type")
    if isinstance(record_type, str) and record_type != "reward_moment":
        return None

    t_start = _timestamp_or_field(raw, "t_start", source, index)
    t_end = _optional_float(raw, "t_end", source, index, default=t_start)
    if t_end < t_start:
        raise ValueError(f"{source}: prediction[{index}].t_end must be >= t_start")

    evidence_ref = raw.get("evidence_ref", {})
    if not isinstance(evidence_ref, dict):
        raise ValueError(f"{source}: prediction[{index}].evidence_ref must be an object")

    return RewardMoment(
        t_start=t_start,
        t_end=t_end,
        label=str(raw.get("label", "reward_moment")),
        confidence=_optional_float(raw, "confidence", source, index, default=0.0),
        evidence_ref=cast(EvidenceRef, evidence_ref),
    )


def _validate_source_rights(document: Any, source: Path) -> None:
    if not isinstance(document, dict) or "video" not in document:
        return

    video = document["video"]
    if not isinstance(video, dict):
        raise ValueError(f"{source}: video must be an object")

    source_rights = video.get("source_rights")
    if source_rights not in _ALLOWED_SOURCE_RIGHTS:
        allowed = ", ".join(sorted(_ALLOWED_SOURCE_RIGHTS))
        raise ValueError(f"{source}: video.source_rights must be one of: {allowed}")

    video_path = video.get("path")
    if isinstance(video_path, str) and video_path:
        _validate_recording_path(video_path, source)


def _validate_recording_path(video_path: str, source: Path) -> None:
    raw_path = Path(video_path)
    absolute_path = raw_path if raw_path.is_absolute() else _REPO_ROOT / raw_path
    try:
        absolute_path.resolve().relative_to((_REPO_ROOT / _DEFAULT_RECORDINGS_DIR).resolve())
    except ValueError as exc:
        raise ValueError(f"{source}: video.path must point under data/recordings/") from exc


def _required_str(raw: JsonObject, field: str, source: Path, index: int) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{source}: events[{index}].{field} must be a non-empty string")
    return value


def _required_float(raw: JsonObject, field: str, source: Path, index: int) -> float:
    return _numeric(raw.get(field), f"{source}: events[{index}].{field}")


def _optional_float(raw: JsonObject, field: str, source: Path, index: int, *, default: float) -> float:
    if field not in raw:
        return default
    return _numeric(raw.get(field), f"{source}: events[{index}].{field}")


def _timestamp_or_field(raw: JsonObject, field: str, source: Path, index: int) -> float:
    if field in raw:
        return _required_float(raw, field, source, index)
    if "timestamp" in raw:
        return _numeric(raw["timestamp"], f"{source}: prediction[{index}].timestamp")
    raise ValueError(f"{source}: prediction[{index}] must include {field} or timestamp")


def _required_bool(raw: JsonObject, field: str, source: Path, index: int) -> bool:
    value = raw.get(field)
    if not isinstance(value, bool):
        raise ValueError(f"{source}: events[{index}].{field} must be true or false")
    return value


def _numeric(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{label} must be a number")
    return float(value)


def _resolve_prediction_path(path: Path | None) -> Path | None:
    if path is not None:
        return _resolve_user_path(path)
    for candidate in _DEFAULT_PREDICTION_PATHS:
        resolved = _resolve_user_path(candidate)
        if resolved.exists():
            return resolved
    return None


def _resolve_user_path(path: Path) -> Path:
    return path if path.is_absolute() else _REPO_ROOT / path


def _has_recordings(path: Path) -> bool:
    if not path.is_dir():
        return False
    return any(item.is_file() and item.suffix.lower() in _RECORDING_EXTENSIONS for item in path.rglob("*"))


def _midpoint(t_start: float, t_end: float) -> float:
    return (t_start + t_end) / 2.0


def _safe_ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _markdown_table(rows: Sequence[tuple[str, str]]) -> str:
    lines = ["| metric | value |", "| --- | --- |"]
    lines.extend(f"| {metric} | {value} |" for metric, value in rows)
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
