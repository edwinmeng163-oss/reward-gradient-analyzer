"""ffmpeg-backed ingestion for first-party gameplay recordings.

Inputs:
- first-party gameplay recording under data/recordings/
- output directory for sampled frames/audio
- loaded GameConfig from configs/slay-the-spire.json

Outputs:
- FrameSample records for baseline and trigger-densified frames
- AudioExtract for mono 16 kHz audio
"""

from __future__ import annotations

import json
import math
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contracts import AudioExtract, FrameSample, GameConfig, JsonValue, Phase


_PTS_TIME_RE = re.compile(r"pts_time:(?P<timestamp>-?\d+(?:\.\d+)?)")


@dataclass(frozen=True)
class _VideoProbe:
    width: int
    height: int
    fps: float
    duration_s: float
    has_audio: bool


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    """Run an ffmpeg-family command and surface stderr on failure."""

    try:
        return subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Required executable not found: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip()
        stdout = exc.stdout.strip()
        details = stderr or stdout or f"exit code {exc.returncode}"
        raise RuntimeError(f"{command[0]} failed: {details}") from exc


def _probe_video(video_path: Path) -> _VideoProbe:
    result = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_entries",
            "format=duration:stream=index,codec_type,width,height,avg_frame_rate,r_frame_rate,duration",
            str(video_path),
        ]
    )
    payload = json.loads(result.stdout)
    streams = payload.get("streams", [])
    video_stream = next(
        (stream for stream in streams if stream.get("codec_type") == "video"),
        None,
    )
    if video_stream is None:
        raise ValueError(f"No video stream found in {video_path}")

    duration = _as_float(video_stream.get("duration"), 0.0) or _as_float(
        payload.get("format", {}).get("duration"), 0.0
    )
    if duration <= 0:
        raise ValueError(f"Could not determine positive video duration for {video_path}")

    fps = _parse_fraction(video_stream.get("avg_frame_rate")) or _parse_fraction(
        video_stream.get("r_frame_rate")
    )
    if fps <= 0:
        fps = 30.0

    return _VideoProbe(
        width=int(video_stream["width"]),
        height=int(video_stream["height"]),
        fps=fps,
        duration_s=duration,
        has_audio=any(stream.get("codec_type") == "audio" for stream in streams),
    )


def _probe_dimensions(media_path: Path) -> tuple[int, int]:
    result = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            str(media_path),
        ]
    )
    payload = json.loads(result.stdout)
    streams = payload.get("streams", [])
    if not streams:
        raise ValueError(f"Could not probe frame dimensions for {media_path}")
    stream = streams[0]
    return int(stream["width"]), int(stream["height"])


def _probe_duration(media_path: Path, fallback_s: float) -> float:
    result = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_entries",
            "format=duration",
            str(media_path),
        ]
    )
    payload = json.loads(result.stdout)
    duration = _as_float(payload.get("format", {}).get("duration"), fallback_s)
    return duration if duration > 0 else fallback_s


def _parse_fraction(value: Any) -> float:
    if not isinstance(value, str) or value in {"", "0/0"}:
        return 0.0
    if "/" not in value:
        return _as_float(value, 0.0)
    numerator, denominator = value.split("/", 1)
    denominator_value = _as_float(denominator, 0.0)
    if denominator_value == 0:
        return 0.0
    return _as_float(numerator, 0.0) / denominator_value


def _as_float(value: Any, default: float) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, int | float | str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _as_int(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return default
    return default


def _dict_value(value: JsonValue | None) -> dict[str, JsonValue]:
    return value if isinstance(value, dict) else {}


def _list_value(value: JsonValue | None) -> list[JsonValue]:
    return value if isinstance(value, list) else []


def _positive_float(value: Any, default: float, name: str) -> float:
    number = _as_float(value, default)
    if number <= 0:
        raise ValueError(f"{name} must be positive, got {value!r}")
    return number


def _positive_int(value: Any, default: int, name: str) -> int:
    number = _as_int(value, default)
    if number <= 0:
        raise ValueError(f"{name} must be positive, got {value!r}")
    return number


def _rate_text(rate: float) -> str:
    if math.isclose(rate, round(rate)):
        return str(int(round(rate)))
    return f"{rate:.6f}".rstrip("0").rstrip(".")


def _ensure_video_path(video_path: Path) -> Path:
    resolved = video_path.expanduser()
    if not resolved.exists():
        raise FileNotFoundError(f"Video path does not exist: {video_path}")
    if not resolved.is_file():
        raise ValueError(f"Video path is not a file: {video_path}")
    return resolved


def _prepare_output_dir(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _clear_prefixed_files(directory: Path, prefixes: tuple[str, ...]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for path in directory.iterdir():
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".wav"}:
            if any(path.name.startswith(prefix) for prefix in prefixes):
                path.unlink()


def _analysis_height(config: GameConfig, source_height: int) -> int:
    ingest = _dict_value(config.get("ingest"))
    coordinate_space = _dict_value(config.get("coordinate_space"))  # type: ignore[typeddict-item]
    height = _as_int(
        ingest.get("analysis_height"),
        _as_int(coordinate_space.get("analysis_height"), min(source_height, 720)),
    )
    if height <= 0:
        raise ValueError(f"analysis_height must be positive, got {height!r}")
    return min(height, source_height)


def _scene_trigger_timestamps(video_path: Path, threshold: float, max_windows: int) -> list[float]:
    if threshold <= 0 or max_windows <= 0:
        return []

    command = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-i",
        str(video_path),
        "-vf",
        f"select='gt(scene,{threshold:.6f})',showinfo",
        "-an",
        "-f",
        "null",
        "-",
    ]
    result = _run(command)
    timestamps: list[float] = []
    seen: set[int] = set()
    for match in _PTS_TIME_RE.finditer(result.stderr):
        timestamp = float(match.group("timestamp"))
        key = int(round(timestamp * 1000))
        if key in seen:
            continue
        seen.add(key)
        timestamps.append(timestamp)
        if len(timestamps) >= max_windows:
            break
    return timestamps


def _configured_trigger_timestamps(ingest: dict[str, JsonValue]) -> list[float]:
    densify = _dict_value(ingest.get("densify"))
    values: list[JsonValue] = []
    for key in ("trigger_timestamps_s", "audio_peak_timestamps_s", "timestamps_s"):
        values.extend(_list_value(ingest.get(key)))
        values.extend(_list_value(densify.get(key)))

    timestamps: list[float] = []
    for value in values:
        timestamp = _as_float(value, -1.0)
        if timestamp >= 0:
            timestamps.append(timestamp)
    return timestamps


def _configured_windows(ingest: dict[str, JsonValue], duration_s: float) -> list[tuple[float, float]]:
    densify = _dict_value(ingest.get("densify"))
    values = [*_list_value(ingest.get("densify_windows")), *_list_value(densify.get("windows"))]
    windows: list[tuple[float, float]] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        start = _as_float(value.get("start_s", value.get("start")), -1.0)
        end = _as_float(value.get("end_s", value.get("end")), -1.0)
        if start < 0 or end <= start:
            continue
        windows.append((max(0.0, start), min(duration_s, end)))
    return windows


def _merge_windows(windows: list[tuple[float, float]], max_windows: int) -> list[tuple[float, float]]:
    if not windows:
        return []
    merged: list[tuple[float, float]] = []
    for start, end in sorted(windows):
        if end <= start:
            continue
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            previous_start, previous_end = merged[-1]
            merged[-1] = (previous_start, max(previous_end, end))
    return merged[:max_windows]


def _dense_windows(video_path: Path, config: GameConfig, probe: _VideoProbe) -> list[tuple[float, float]]:
    ingest = _dict_value(config.get("ingest"))
    densify = _dict_value(ingest.get("densify"))
    max_windows = _positive_int(densify.get("max_windows"), 240, "ingest.densify.max_windows")
    pre_s = max(0.0, _as_float(densify.get("pre_s"), 1.0))
    post_s = max(0.0, _as_float(densify.get("post_s"), 2.0))

    triggers = _configured_trigger_timestamps(ingest)
    scene_threshold = _as_float(ingest.get("scene_threshold"), -1.0)
    if scene_threshold > 0:
        triggers.extend(_scene_trigger_timestamps(video_path, scene_threshold, max_windows))

    windows = _configured_windows(ingest, probe.duration_s)
    for timestamp in sorted(set(round(trigger, 3) for trigger in triggers if trigger >= 0)):
        start = max(0.0, timestamp - pre_s)
        end = min(probe.duration_s, timestamp + post_s)
        if end > start:
            windows.append((start, end))
    return _merge_windows(windows, max_windows)


def _frame_record(
    path: Path,
    timestamp: float,
    width: int,
    height: int,
    source_fps: float,
    sample_kind: str,
    sample_rate: float,
) -> FrameSample:
    frame_index = max(0, int(round(timestamp * source_fps)))
    details: dict[str, JsonValue] = {
        "sample_kind": sample_kind,
        "sample_rate_fps": sample_rate,
        "source_fps": source_fps,
    }
    return FrameSample(
        frame_index=frame_index,
        timestamp=timestamp,
        path=path,
        width=width,
        height=height,
        source_fps=source_fps,
        evidence_ref={
            "phase": Phase.INGEST,
            "frame_index": frame_index,
            "timestamp": timestamp,
            "path": str(path),
            "detector": "ffmpeg",
            "details": details,
        },
    )


def sample_frames(video_path: Path, output_dir: Path, config: GameConfig) -> list[FrameSample]:
    """Sample 1 fps baseline frames plus trigger-densified frames into output_dir."""

    video_path = _ensure_video_path(video_path)
    output_dir = _prepare_output_dir(output_dir)
    frames_dir = output_dir / "frames"
    _clear_prefixed_files(frames_dir, ("baseline_", "dense_"))

    probe = _probe_video(video_path)
    ingest = _dict_value(config.get("ingest"))
    baseline_fps = _positive_float(ingest.get("baseline_fps"), 1.0, "ingest.baseline_fps")
    dense_fps = _positive_float(ingest.get("dense_fps"), 6.0, "ingest.dense_fps")
    analysis_height = _analysis_height(config, probe.height)

    baseline_pattern = frames_dir / "baseline_%06d.jpg"
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video_path),
            "-vf",
            f"fps={_rate_text(baseline_fps)},scale=-2:{analysis_height}",
            "-q:v",
            "2",
            str(baseline_pattern),
        ]
    )

    windows = _dense_windows(video_path, config, probe)
    for index, (start, end) in enumerate(windows, start=1):
        dense_pattern = frames_dir / f"dense_{index:04d}_%06d.jpg"
        _run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                f"{start:.3f}",
                "-i",
                str(video_path),
                "-t",
                f"{end - start:.3f}",
                "-vf",
                f"fps={_rate_text(dense_fps)},scale=-2:{analysis_height}",
                "-q:v",
                "2",
                str(dense_pattern),
            ]
        )

    frame_paths = [*sorted(frames_dir.glob("baseline_*.jpg")), *sorted(frames_dir.glob("dense_*.jpg"))]
    if not frame_paths:
        raise RuntimeError(f"ffmpeg produced no sampled frames for {video_path}")
    frame_width, frame_height = _probe_dimensions(frame_paths[0])

    records: list[FrameSample] = []
    seen_timestamps: set[int] = set()

    for index, path in enumerate(sorted(frames_dir.glob("baseline_*.jpg")), start=1):
        timestamp = (index - 1) / baseline_fps
        if timestamp > probe.duration_s + (0.5 / baseline_fps):
            continue
        key = int(round(timestamp * 1000))
        if key in seen_timestamps:
            continue
        seen_timestamps.add(key)
        records.append(
            _frame_record(
                path=path,
                timestamp=timestamp,
                width=frame_width,
                height=frame_height,
                source_fps=probe.fps,
                sample_kind="baseline",
                sample_rate=baseline_fps,
            )
        )

    for window_index, (start, _end) in enumerate(windows, start=1):
        dense_paths = sorted(frames_dir.glob(f"dense_{window_index:04d}_*.jpg"))
        for frame_index, path in enumerate(dense_paths, start=1):
            timestamp = start + ((frame_index - 1) / dense_fps)
            if timestamp > probe.duration_s + (0.5 / dense_fps):
                continue
            key = int(round(timestamp * 1000))
            if key in seen_timestamps:
                continue
            seen_timestamps.add(key)
            records.append(
                _frame_record(
                    path=path,
                    timestamp=timestamp,
                    width=frame_width,
                    height=frame_height,
                    source_fps=probe.fps,
                    sample_kind="dense",
                    sample_rate=dense_fps,
                )
            )

    return sorted(records, key=lambda frame: (frame.timestamp, frame.path.name))


def extract_audio(video_path: Path, output_dir: Path, config: GameConfig) -> AudioExtract:
    """Extract mono 16 kHz audio from video_path into output_dir."""

    video_path = _ensure_video_path(video_path)
    output_dir = _prepare_output_dir(output_dir)
    audio_dir = output_dir / "audio"
    _clear_prefixed_files(audio_dir, ("audio_",))

    probe = _probe_video(video_path)
    audio = _dict_value(config.get("audio"))
    sample_rate = _positive_int(audio.get("sample_rate"), 16000, "audio.sample_rate")
    audio_path = audio_dir / "audio_mono_16khz.wav"

    if probe.has_audio:
        _run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(video_path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                str(sample_rate),
                "-c:a",
                "pcm_s16le",
                str(audio_path),
            ]
        )
        source = "extracted_audio_stream"
    else:
        _run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"anullsrc=channel_layout=mono:sample_rate={sample_rate}",
                "-t",
                f"{probe.duration_s:.3f}",
                "-c:a",
                "pcm_s16le",
                str(audio_path),
            ]
        )
        source = "generated_silence_no_audio_stream"

    duration_s = _probe_duration(audio_path, probe.duration_s)
    details: dict[str, JsonValue] = {
        "source": source,
        "channels": 1,
        "source_video_duration_s": probe.duration_s,
    }
    return AudioExtract(
        path=audio_path,
        sample_rate=sample_rate,
        duration_s=duration_s,
        evidence_ref={
            "phase": Phase.INGEST,
            "timestamp": 0.0,
            "path": str(audio_path),
            "detector": "ffmpeg",
            "details": details,
        },
    )
