"""Audio cue detector.

Audio candidates are intentionally conservative boost-only evidence. They help
fusion raise confidence around visual/OCR reward evidence, but must never be
treated as sufficient reward evidence on their own.
"""

from __future__ import annotations

import math
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import numpy as np
from scipy.signal import fftconvolve, find_peaks, resample_poly

from .contracts import (
    AudioExtract,
    CandidateEvent,
    EvidenceRef,
    GameConfig,
    JsonValue,
    Modality,
    Phase,
)

try:
    import soundfile as sf
except ImportError:  # pragma: no cover - dependency is declared, fallback keeps the module usable.
    sf = None  # type: ignore[assignment]


_EPS = 1e-12
_BOOST_POLICY = "boost_only_never_emit_audio_alone"
_SEMANTIC_LABELS = {"coin", "coin_pickup", "level_up", "victory", "victory_jingle", "reward_jingle"}


@dataclass(frozen=True)
class _FrameSeries:
    timestamps: np.ndarray
    rms: np.ndarray
    energy_z: np.ndarray
    onset_z: np.ndarray
    hop_s: float
    window_s: float


@dataclass(frozen=True)
class _LocalFeatures:
    duration_s: float
    centroid_hz: float
    high_freq_ratio: float
    low_freq_ratio: float
    spectral_peakiness: float
    envelope_peak_count: int


@dataclass(frozen=True)
class _CueTemplate:
    cue_id: str
    label: str
    path: Path
    min_similarity: float
    min_gap_s: float
    confidence_floor: float
    confidence_ceiling: float


def detect_cues(audio: AudioExtract, config: GameConfig) -> list[CandidateEvent]:
    """Detect onset/energy/template audio cues for confidence boosting."""

    audio_config = _dict_value(config.get("audio"))
    sample_rate = _positive_int(audio_config.get("sample_rate"), audio.sample_rate, "audio.sample_rate")
    samples, sample_rate = _load_audio(audio.path, sample_rate)
    if samples.size == 0 or audio.duration_s <= 0:
        return []

    duration_s = min(audio.duration_s, samples.size / sample_rate)
    window_s = _positive_float(audio_config.get("window_s"), 0.2, "audio.window_s")
    hop_s = _positive_float(audio_config.get("hop_s"), 0.05, "audio.hop_s")
    min_gap_s = _positive_float(audio_config.get("min_gap_s"), 1.25, "audio.min_gap_s")
    threshold_sigma = _positive_float(audio_config.get("threshold_sigma"), 2.75, "audio.threshold_sigma")
    min_rms = _bounded_float(audio_config.get("min_rms"), 0.006, 0.0, 1.0)
    max_events = _positive_int(audio_config.get("max_events"), 96, "audio.max_events")

    series = _frame_series(samples, sample_rate, window_s, hop_s)
    semantic_events = [
        *_configured_semantic_events(audio, audio_config, duration_s),
        *_template_events(samples, sample_rate, audio, audio_config, min_gap_s),
    ]
    generic_events = _generic_peak_events(
        samples=samples,
        sample_rate=sample_rate,
        audio=audio,
        series=series,
        duration_s=duration_s,
        threshold_sigma=threshold_sigma,
        min_rms=min_rms,
        min_gap_s=min_gap_s,
        semantic_events=semantic_events,
    )

    events = _dedupe_events([*semantic_events, *generic_events], merge_window_s=0.18)
    events.sort(key=lambda event: (event.t_start, -event.confidence, event.label))
    if len(events) <= max_events:
        return events

    highest_confidence = sorted(events, key=lambda event: event.confidence, reverse=True)[:max_events]
    return sorted(highest_confidence, key=lambda event: (event.t_start, -event.confidence, event.label))


def _generic_peak_events(
    *,
    samples: np.ndarray,
    sample_rate: int,
    audio: AudioExtract,
    series: _FrameSeries,
    duration_s: float,
    threshold_sigma: float,
    min_rms: float,
    min_gap_s: float,
    semantic_events: list[CandidateEvent],
) -> list[CandidateEvent]:
    if series.timestamps.size == 0:
        return []

    peak_indices = _peak_indices(series, threshold_sigma, min_gap_s)
    events: list[CandidateEvent] = []
    for index in peak_indices:
        timestamp = float(series.timestamps[index])
        if _near_event(timestamp, semantic_events, window_s=0.35):
            continue

        energy_z = float(series.energy_z[index])
        onset_z = float(series.onset_z[index])
        rms = float(series.rms[index])
        peak_score = max(energy_z, onset_z)
        if peak_score < threshold_sigma or rms < min_rms:
            continue

        features = _local_features(samples, sample_rate, timestamp)
        label, detector, confidence = _classify_peak(energy_z, onset_z, threshold_sigma, features)
        t_start = max(0.0, timestamp - min(0.12, series.window_s / 2.0))
        t_end = min(duration_s, max(t_start + 0.08, timestamp + min(max(features.duration_s, 0.18), 1.75)))
        details: dict[str, JsonValue] = {
            "boost_policy": _BOOST_POLICY,
            "peak_kind": "onset" if onset_z >= energy_z else "energy",
            "energy_z": _round(energy_z),
            "onset_z": _round(onset_z),
            "threshold_sigma": _round(threshold_sigma),
            "rms": _round(rms, digits=6),
            "min_rms": _round(min_rms, digits=6),
            "window_s": _round(series.window_s),
            "hop_s": _round(series.hop_s),
            "duration_s": _round(features.duration_s),
            "centroid_hz": _round(features.centroid_hz),
            "high_freq_ratio": _round(features.high_freq_ratio),
            "low_freq_ratio": _round(features.low_freq_ratio),
            "spectral_peakiness": _round(features.spectral_peakiness),
            "envelope_peak_count": features.envelope_peak_count,
        }
        events.append(
            _event(
                audio=audio,
                t_start=t_start,
                t_end=t_end,
                label=label,
                confidence=confidence,
                detector=detector,
                value={
                    "cue_family": label.removeprefix("audio_"),
                    "boost_only": True,
                    "peak_score": _round(peak_score),
                },
                details=details,
            )
        )
    return events


def _peak_indices(series: _FrameSeries, threshold_sigma: float, min_gap_s: float) -> list[int]:
    distance = max(1, int(round(min_gap_s / series.hop_s)))
    combined = np.maximum(series.energy_z, series.onset_z)
    peaks: set[int] = set()

    for scores in (series.energy_z, series.onset_z, combined):
        found, _ = find_peaks(scores, height=threshold_sigma, distance=distance)
        peaks.update(int(index) for index in found)

    if combined.size and float(combined[0]) >= threshold_sigma:
        peaks.add(0)
    if combined.size > 1 and float(combined[-1]) >= threshold_sigma:
        peaks.add(combined.size - 1)

    selected: list[int] = []
    for index in sorted(peaks, key=lambda item: float(series.timestamps[item])):
        if not selected:
            selected.append(index)
            continue
        previous = selected[-1]
        if float(series.timestamps[index] - series.timestamps[previous]) >= min_gap_s:
            selected.append(index)
            continue
        if float(combined[index]) > float(combined[previous]):
            selected[-1] = index
    return selected


def _classify_peak(
    energy_z: float,
    onset_z: float,
    threshold_sigma: float,
    features: _LocalFeatures,
) -> tuple[str, str, float]:
    peak_score = max(energy_z, onset_z)
    base_confidence = _confidence_from_score(peak_score, threshold_sigma, floor=0.34, ceiling=0.58)
    strong_onset = onset_z >= threshold_sigma + 0.7

    if (
        strong_onset
        and features.duration_s <= 0.85
        and features.centroid_hz >= 1800.0
        and features.high_freq_ratio >= 0.22
        and features.low_freq_ratio <= 0.38
    ):
        confidence = max(base_confidence, _confidence_from_score(peak_score, threshold_sigma, 0.52, 0.68))
        return "audio_coin_like", "rms_onset_coin_heuristic", confidence

    if (
        peak_score >= threshold_sigma + 1.0
        and 0.45 <= features.duration_s <= 2.25
        and features.envelope_peak_count >= 2
        and features.spectral_peakiness >= 5.0
        and features.low_freq_ratio <= 0.55
    ):
        confidence = max(base_confidence, _confidence_from_score(peak_score, threshold_sigma, 0.48, 0.64))
        return "audio_level_up_like", "rms_onset_level_up_heuristic", confidence

    if (
        peak_score >= threshold_sigma + 1.25
        and features.duration_s >= 1.1
        and features.envelope_peak_count >= 3
        and features.spectral_peakiness >= 4.5
        and features.low_freq_ratio <= 0.6
    ):
        confidence = max(base_confidence, _confidence_from_score(peak_score, threshold_sigma, 0.46, 0.62))
        return "audio_victory_jingle_like", "rms_energy_victory_heuristic", confidence

    if onset_z >= energy_z:
        return "audio_onset_peak", "rms_onset_peak", base_confidence
    return "audio_energy_peak", "rms_energy_peak", base_confidence


def _configured_semantic_events(
    audio: AudioExtract,
    audio_config: dict[str, JsonValue],
    duration_s: float,
) -> list[CandidateEvent]:
    """Accept cached CLAP-like detections supplied by a first-party upstream step."""

    min_confidence = _positive_float(audio_config.get("clap_min_confidence"), 0.65, "audio.clap_min_confidence")
    cue_values = [*_list_value(audio_config.get("clap_cues")), *_list_value(audio_config.get("semantic_cues"))]
    events: list[CandidateEvent] = []
    for raw in cue_values:
        if not isinstance(raw, dict):
            continue
        cue = cast(dict[str, JsonValue], raw)
        timestamp = _as_float(cue.get("timestamp_s", cue.get("timestamp", cue.get("t"))), -1.0)
        confidence = _as_float(cue.get("confidence"), 0.0)
        if not (0.0 <= timestamp <= duration_s and confidence >= min_confidence):
            continue
        cue_label = _safe_label(str(cue.get("label", cue.get("id", "semantic_cue"))))
        if cue_label in _SEMANTIC_LABELS:
            label = f"audio_clap_{cue_label}"
        else:
            label = "audio_clap_semantic_cue"
        half_window = _positive_float(cue.get("window_s"), 0.25, "audio.clap_cues.window_s") / 2.0
        details: dict[str, JsonValue] = {
            "boost_policy": _BOOST_POLICY,
            "source": "configured_clap_or_semantic_cue",
            "cue_label": cue_label,
            "min_confidence": _round(min_confidence),
        }
        events.append(
            _event(
                audio=audio,
                t_start=max(0.0, timestamp - half_window),
                t_end=min(duration_s, timestamp + half_window),
                label=label,
                confidence=min(0.9, max(0.0, confidence)),
                detector="configured_clap_cue",
                value={
                    "cue_family": cue_label,
                    "boost_only": True,
                    "semantic_model": str(cue.get("model", "configured")),
                },
                details=details,
            )
        )
    return events


def _template_events(
    samples: np.ndarray,
    sample_rate: int,
    audio: AudioExtract,
    audio_config: dict[str, JsonValue],
    default_min_gap_s: float,
) -> list[CandidateEvent]:
    templates = _parse_templates(audio_config, audio.path, default_min_gap_s)
    if not templates:
        return []

    normalized_samples = _normalize(samples)
    events: list[CandidateEvent] = []
    for template in templates:
        template_samples, template_rate = _load_audio(template.path, sample_rate)
        if template_rate != sample_rate:
            template_samples = _resample(template_samples, template_rate, sample_rate)
        template_samples = _normalize(template_samples)
        if template_samples.size < max(16, int(0.035 * sample_rate)) or template_samples.size > samples.size:
            continue

        similarity = _normalized_correlation(normalized_samples, template_samples)
        if similarity.size == 0:
            continue
        distance = max(1, int(round(template.min_gap_s * sample_rate)))
        peaks, properties = find_peaks(similarity, height=template.min_similarity, distance=distance)
        heights = cast(np.ndarray, properties.get("peak_heights", np.array([], dtype=np.float32)))
        for peak, height in zip(peaks, heights, strict=False):
            score = float(height)
            t_start = max(0.0, float(peak) / sample_rate)
            t_end = min(audio.duration_s, t_start + template_samples.size / sample_rate)
            confidence = _confidence_from_similarity(
                score,
                threshold=template.min_similarity,
                floor=template.confidence_floor,
                ceiling=template.confidence_ceiling,
            )
            label = f"audio_template_{_safe_label(template.label)}"
            details: dict[str, JsonValue] = {
                "boost_policy": _BOOST_POLICY,
                "template_id": template.cue_id,
                "template_path": str(template.path),
                "similarity": _round(score),
                "min_similarity": _round(template.min_similarity),
            }
            events.append(
                _event(
                    audio=audio,
                    t_start=t_start,
                    t_end=t_end,
                    label=label,
                    confidence=confidence,
                    detector="normalized_template_match",
                    value={
                        "cue_family": _safe_label(template.label),
                        "boost_only": True,
                        "template_id": template.cue_id,
                        "similarity": _round(score),
                    },
                    details=details,
                    template_id=template.cue_id,
                )
            )
    return events


def _parse_templates(
    audio_config: dict[str, JsonValue],
    audio_path: Path,
    default_min_gap_s: float,
) -> list[_CueTemplate]:
    raw_templates = [*_list_value(audio_config.get("cue_templates")), *_list_value(audio_config.get("templates"))]
    default_threshold = _positive_float(audio_config.get("template_min_similarity"), 0.72, "audio.template_min_similarity")
    templates: list[_CueTemplate] = []
    for index, raw in enumerate(raw_templates):
        if not isinstance(raw, dict):
            continue
        entry = cast(dict[str, JsonValue], raw)
        raw_path = entry.get("path", entry.get("template_path"))
        if not isinstance(raw_path, str) or not raw_path.strip():
            continue
        label = _safe_label(str(entry.get("label", entry.get("id", f"cue_{index}"))))
        cue_id = _safe_label(str(entry.get("id", label)))
        path = _resolve_template_path(raw_path, audio_path)
        if path is None:
            continue
        templates.append(
            _CueTemplate(
                cue_id=cue_id,
                label=label,
                path=path,
                min_similarity=_positive_float(
                    entry.get("min_similarity", entry.get("threshold")),
                    default_threshold,
                    "audio.cue_templates.min_similarity",
                ),
                min_gap_s=_positive_float(entry.get("min_gap_s"), default_min_gap_s, "audio.cue_templates.min_gap_s"),
                confidence_floor=_bounded_float(entry.get("confidence_floor"), 0.62, 0.0, 1.0),
                confidence_ceiling=_bounded_float(entry.get("confidence_ceiling"), 0.88, 0.0, 1.0),
            )
        )
    return templates


def _normalized_correlation(samples: np.ndarray, template: np.ndarray) -> np.ndarray:
    template_energy = float(np.sqrt(np.sum(template * template)))
    if template_energy <= _EPS:
        return np.array([], dtype=np.float32)

    raw = fftconvolve(samples, template[::-1], mode="valid")
    local_energy = fftconvolve(samples * samples, np.ones(template.size, dtype=np.float32), mode="valid")
    denom = np.sqrt(np.maximum(local_energy, 0.0)) * template_energy
    valid = denom > _EPS
    similarity = np.zeros_like(raw, dtype=np.float32)
    similarity[valid] = raw[valid] / denom[valid]
    return np.clip(similarity, -1.0, 1.0)


def _frame_series(samples: np.ndarray, sample_rate: int, window_s: float, hop_s: float) -> _FrameSeries:
    window = max(1, int(round(window_s * sample_rate)))
    hop = max(1, int(round(hop_s * sample_rate)))
    if samples.size < window:
        samples = np.pad(samples, (0, window - samples.size))

    starts = np.arange(0, samples.size - window + 1, hop, dtype=np.int64)
    if starts.size == 0:
        starts = np.array([0], dtype=np.int64)

    squared = np.asarray(samples * samples, dtype=np.float64)
    cumulative = np.concatenate([np.array([0.0]), np.cumsum(squared)])
    frame_energy = (cumulative[starts + window] - cumulative[starts]) / window
    rms = np.sqrt(np.maximum(frame_energy, 0.0))
    rms_db = 20.0 * np.log10(rms + 1e-8)
    onset = np.maximum(np.diff(rms_db, prepend=rms_db[0]), 0.0)
    timestamps = (starts + (window / 2.0)) / sample_rate

    return _FrameSeries(
        timestamps=timestamps.astype(np.float64),
        rms=rms.astype(np.float32),
        energy_z=_robust_z(rms_db),
        onset_z=_robust_z(onset),
        hop_s=hop / sample_rate,
        window_s=window / sample_rate,
    )


def _local_features(samples: np.ndarray, sample_rate: int, timestamp: float) -> _LocalFeatures:
    start = max(0, int(round((timestamp - 0.08) * sample_rate)))
    end = min(samples.size, int(round((timestamp + 2.8) * sample_rate)))
    segment = samples[start:end]
    if segment.size < 16:
        return _LocalFeatures(0.0, 0.0, 0.0, 0.0, 0.0, 0)

    envelope = _rms_envelope(segment, sample_rate, window_s=0.025, hop_s=0.01)
    if envelope.size == 0:
        duration_s = min(segment.size / sample_rate, 0.025)
        peak_count = 1
    else:
        baseline = float(np.median(envelope))
        spread = _mad(envelope)
        threshold = max(baseline + 2.0 * spread, float(np.max(envelope)) * 0.22)
        active = np.flatnonzero(envelope >= threshold)
        if active.size:
            duration_s = max(0.025, (int(active[-1]) - int(active[0]) + 1) * 0.01)
        else:
            duration_s = min(segment.size / sample_rate, 0.025)
        peaks, _ = find_peaks(envelope, height=threshold, distance=max(1, int(round(0.08 / 0.01))))
        peak_count = int(peaks.size)

    analysis_len = min(segment.size, max(128, int(round(min(max(duration_s, 0.12), 1.5) * sample_rate))))
    spectrum_segment = segment[:analysis_len]
    if spectrum_segment.size < 16:
        return _LocalFeatures(duration_s, 0.0, 0.0, 0.0, 0.0, peak_count)

    window = np.hanning(spectrum_segment.size)
    spectrum = np.abs(np.fft.rfft(spectrum_segment * window))
    power = spectrum * spectrum
    total_power = float(np.sum(power))
    if total_power <= _EPS:
        return _LocalFeatures(duration_s, 0.0, 0.0, 0.0, 0.0, peak_count)

    freqs = np.fft.rfftfreq(spectrum_segment.size, d=1.0 / sample_rate)
    centroid = float(np.sum(freqs * power) / total_power)
    high_ratio = float(np.sum(power[freqs >= 2500.0]) / total_power)
    low_ratio = float(np.sum(power[freqs <= 500.0]) / total_power)
    peakiness = float(np.max(power) / (np.mean(power) + _EPS))
    return _LocalFeatures(duration_s, centroid, high_ratio, low_ratio, peakiness, peak_count)


def _rms_envelope(samples: np.ndarray, sample_rate: int, window_s: float, hop_s: float) -> np.ndarray:
    window = max(1, int(round(window_s * sample_rate)))
    hop = max(1, int(round(hop_s * sample_rate)))
    if samples.size < window:
        samples = np.pad(samples, (0, window - samples.size))
    starts = np.arange(0, samples.size - window + 1, hop, dtype=np.int64)
    if starts.size == 0:
        return np.array([], dtype=np.float32)
    squared = np.asarray(samples * samples, dtype=np.float64)
    cumulative = np.concatenate([np.array([0.0]), np.cumsum(squared)])
    energy = (cumulative[starts + window] - cumulative[starts]) / window
    return np.sqrt(np.maximum(energy, 0.0)).astype(np.float32)


def _load_audio(path: Path, target_sample_rate: int) -> tuple[np.ndarray, int]:
    if not path.exists():
        raise FileNotFoundError(f"Audio artifact not found: {path}")

    if sf is not None:
        data, sample_rate = sf.read(path, always_2d=False, dtype="float32")
        samples = np.asarray(data, dtype=np.float32)
        if samples.ndim == 2:
            samples = np.mean(samples, axis=1, dtype=np.float32)
    else:
        samples, sample_rate = _read_wave_pcm(path)

    if samples.size == 0:
        return np.array([], dtype=np.float32), target_sample_rate

    samples = np.nan_to_num(samples, copy=False)
    if sample_rate != target_sample_rate:
        samples = _resample(samples, sample_rate, target_sample_rate)
        sample_rate = target_sample_rate

    samples = samples.astype(np.float32, copy=False)
    samples -= float(np.mean(samples))
    peak = float(np.max(np.abs(samples))) if samples.size else 0.0
    if peak > 1.5:
        samples /= peak
    return samples, sample_rate


def _read_wave_pcm(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        frames = wav_file.readframes(wav_file.getnframes())

    if sample_width == 1:
        data = (np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    elif sample_width == 2:
        data = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    elif sample_width == 3:
        raw = np.frombuffer(frames, dtype=np.uint8).reshape(-1, 3)
        signed = raw[:, 0].astype(np.int32) | (raw[:, 1].astype(np.int32) << 8) | (raw[:, 2].astype(np.int32) << 16)
        signed = np.where(signed & 0x800000, signed | ~0xFFFFFF, signed)
        data = signed.astype(np.float32) / 8388608.0
    elif sample_width == 4:
        data = np.frombuffer(frames, dtype="<i4").astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"Unsupported WAV sample width: {sample_width}")

    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1, dtype=np.float32)
    return data.astype(np.float32), sample_rate


def _resample(samples: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    if source_rate <= 0 or target_rate <= 0:
        raise ValueError("Sample rates must be positive")
    divisor = math.gcd(source_rate, target_rate)
    return resample_poly(samples, target_rate // divisor, source_rate // divisor).astype(np.float32)


def _normalize(samples: np.ndarray) -> np.ndarray:
    samples = np.asarray(samples, dtype=np.float32)
    if samples.size == 0:
        return samples
    centered = samples - float(np.mean(samples))
    scale = float(np.sqrt(np.mean(centered * centered)))
    if scale <= _EPS:
        return np.zeros_like(centered, dtype=np.float32)
    return (centered / scale).astype(np.float32)


def _robust_z(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    if values.size == 0:
        return values.astype(np.float32)
    center = float(np.median(values))
    scale = 1.4826 * _mad(values)
    if scale <= 1e-9:
        scale = float(np.std(values))
    if scale <= 1e-9:
        return np.zeros_like(values, dtype=np.float32)
    return ((values - center) / scale).astype(np.float32)


def _mad(values: np.ndarray) -> float:
    if values.size == 0:
        return 0.0
    median = float(np.median(values))
    return float(np.median(np.abs(values - median)))


def _event(
    *,
    audio: AudioExtract,
    t_start: float,
    t_end: float,
    label: str,
    confidence: float,
    detector: str,
    value: dict[str, JsonValue],
    details: dict[str, JsonValue],
    template_id: str | None = None,
) -> CandidateEvent:
    timestamp = max(0.0, (t_start + t_end) / 2.0)
    evidence_ref: EvidenceRef = {
        "phase": Phase.AUDIO,
        "timestamp": timestamp,
        "path": str(audio.path),
        "detector": detector,
        "details": details,
    }
    if template_id is not None:
        evidence_ref["template_id"] = template_id
    return CandidateEvent(
        t_start=max(0.0, t_start),
        t_end=max(t_start, t_end),
        modality=Modality.AUDIO,
        label=label,
        value=value,
        confidence=min(1.0, max(0.0, confidence)),
        evidence_ref=evidence_ref,
    )


def _dedupe_events(events: list[CandidateEvent], merge_window_s: float) -> list[CandidateEvent]:
    selected: list[CandidateEvent] = []
    for event in sorted(events, key=lambda item: (-item.confidence, item.t_start, item.label)):
        center = (event.t_start + event.t_end) / 2.0
        if any(abs(center - ((kept.t_start + kept.t_end) / 2.0)) <= merge_window_s for kept in selected):
            continue
        selected.append(event)
    return selected


def _near_event(timestamp: float, events: list[CandidateEvent], window_s: float) -> bool:
    for event in events:
        center = (event.t_start + event.t_end) / 2.0
        if abs(timestamp - center) <= window_s:
            return True
    return False


def _resolve_template_path(raw_path: str, audio_path: Path) -> Path | None:
    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        return candidate if candidate.exists() else None

    search_roots = [Path.cwd(), audio_path.parent, audio_path.parent.parent]
    for root in search_roots:
        resolved = (root / candidate).resolve()
        if resolved.exists():
            return resolved
    return None


def _confidence_from_score(score: float, threshold: float, floor: float, ceiling: float) -> float:
    if ceiling <= floor:
        return floor
    if score <= threshold:
        return floor
    extra = min(1.0, (score - threshold) / max(threshold, 1.0))
    return floor + (ceiling - floor) * extra


def _confidence_from_similarity(score: float, threshold: float, floor: float, ceiling: float) -> float:
    if ceiling <= floor:
        return floor
    if score <= threshold:
        return floor
    extra = min(1.0, (score - threshold) / max(1.0 - threshold, 1e-6))
    return floor + (ceiling - floor) * extra


def _dict_value(value: object) -> dict[str, JsonValue]:
    if isinstance(value, dict):
        return cast(dict[str, JsonValue], value)
    return {}


def _list_value(value: object) -> list[JsonValue]:
    if isinstance(value, list):
        return cast(list[JsonValue], value)
    return []


def _as_float(value: object, default: float) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        result = float(value)
        return result if math.isfinite(result) else default
    if isinstance(value, str):
        try:
            result = float(value)
        except ValueError:
            return default
        return result if math.isfinite(result) else default
    return default


def _positive_float(value: object, default: float, name: str) -> float:
    result = _as_float(value, default)
    if result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


def _positive_int(value: object, default: int, name: str) -> int:
    result = int(round(_as_float(value, float(default))))
    if result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


def _bounded_float(value: object, default: float, lower: float, upper: float) -> float:
    return min(upper, max(lower, _as_float(value, default)))


def _safe_label(value: str) -> str:
    cleaned = "".join(character.lower() if character.isalnum() else "_" for character in value.strip())
    return "_".join(part for part in cleaned.split("_") if part) or "cue"


def _round(value: float, digits: int = 4) -> float:
    return round(float(value), digits)
