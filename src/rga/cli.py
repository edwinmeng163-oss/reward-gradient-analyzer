"""Command line runner for the RGA specialist spike."""

from __future__ import annotations

import argparse
import binascii
import json
import sys
import zlib
from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from struct import pack
from typing import Any, cast

from .contracts import AudioExtract, CandidateEvent, FrameSample, GameConfig, JsonValue, RewardMoment


_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_CONFIG = _REPO_ROOT / "configs" / "slay-the-spire.json"
_DEFAULT_RECORDINGS_DIR = _REPO_ROOT / "data" / "recordings"
_DEFAULT_OUTPUT_ROOT = _REPO_ROOT / "data" / "outputs"
_VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}


class _CliError(Exception):
    """User-facing CLI error without a traceback."""


def main(argv: list[str] | None = None) -> int:
    """Run the RGA CLI and return a process exit code."""

    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "analyze":
        return _analyze(args)
    parser.print_help()
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m rga.cli",
        description="Analyze first-party gameplay footage into reward moments and reward density.",
    )
    subparsers = parser.add_subparsers(dest="command")
    analyze = subparsers.add_parser("analyze", help="run the specialist reward-moment pipeline")
    analyze.add_argument(
        "video",
        nargs="?",
        help="first-party/self-recorded gameplay clip under data/recordings/",
    )
    analyze.add_argument(
        "--config",
        default=str(_DEFAULT_CONFIG),
        help="game config JSON path (default: configs/slay-the-spire.json)",
    )
    analyze.add_argument(
        "--output-dir",
        help="directory for timeline JSON, reward density PNG, report.md, and intermediate artifacts",
    )
    return parser


def _analyze(args: argparse.Namespace) -> int:
    try:
        video_path = _video_path(args.video)
        if video_path is None:
            print(
                "No first-party gameplay clip found. Place a recording under "
                f"{_relative(_DEFAULT_RECORDINGS_DIR)}/ or pass a video path under data/.",
                file=sys.stderr,
            )
            return 0

        config_path = _resolve_existing_path(Path(args.config), "config")
        config = _load_config(config_path)
        output_dir = _output_dir(args.output_dir, video_path)
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"Analyzing {_relative(video_path)}")
        print(f"Using config {_relative(config_path)}")
        print(f"Writing outputs to {_relative(output_dir)}")

        result = _run_pipeline(video_path=video_path, output_dir=output_dir, config=config)
        timeline_path = output_dir / "reward_moment_timeline.json"
        density_path = output_dir / "reward_density.png"
        report_path = output_dir / "report.md"

        _write_timeline(
            path=timeline_path,
            video_path=video_path,
            config_path=config_path,
            config=config,
            result=result,
        )
        _write_density_png(density_path, result["density"])
        _write_report(
            path=report_path,
            video_path=video_path,
            config_path=config_path,
            result=result,
            timeline_path=timeline_path,
            density_path=density_path,
        )
    except _CliError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - keeps CLI failures readable.
        print(f"Analysis failed: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {_relative(timeline_path)}")
    print(f"Wrote {_relative(density_path)}")
    print(f"Wrote {_relative(report_path)}")
    return 0


def _run_pipeline(
    *,
    video_path: Path,
    output_dir: Path,
    config: GameConfig,
) -> dict[str, Any]:
    from . import audio, fuse, ingest, ocr, screens

    frames = ingest.sample_frames(video_path, output_dir, config)
    audio_extract = ingest.extract_audio(video_path, output_dir, config)
    ocr_candidates = ocr.read_rois(frames, config)
    screen_candidates = screens.classify(frames, ocr_candidates, config)
    audio_candidates = audio.detect_cues(audio_extract, config)
    candidates = [*ocr_candidates, *screen_candidates, *audio_candidates]
    moments = fuse.to_reward_moments(candidates, config)
    density = fuse.compute_reward_density(moments, config, duration_s=audio_extract.duration_s)
    return {
        "frames": frames,
        "audio": audio_extract,
        "ocr_candidates": ocr_candidates,
        "screen_candidates": screen_candidates,
        "audio_candidates": audio_candidates,
        "candidates": candidates,
        "moments": moments,
        "density": density,
    }


def _video_path(raw_video: str | None) -> Path | None:
    if raw_video is None:
        return _first_recording()

    raw_path = Path(raw_video).expanduser()
    candidate = raw_path if raw_path.is_absolute() else _REPO_ROOT / raw_path
    if not candidate.exists():
        print(
            f"No video found at {raw_video!r}. Place a first-party clip under data/recordings/.",
            file=sys.stderr,
        )
        return None
    if not candidate.is_file():
        raise _CliError(f"Video path is not a file: {raw_video}")
    video_path = candidate.resolve()
    data_root = (_REPO_ROOT / "data").resolve()
    if not _is_relative_to(video_path, data_root):
        raise _CliError(
            "Refusing to analyze footage outside data/. Copy first-party/self-recorded footage "
            "to data/recordings/ and rerun the command."
        )
    if video_path.suffix.casefold() not in _VIDEO_EXTENSIONS:
        raise _CliError(f"Unsupported video extension for {video_path.name!r}")
    return video_path


def _first_recording() -> Path | None:
    if not _DEFAULT_RECORDINGS_DIR.exists():
        return None
    videos = [
        path.resolve()
        for path in sorted(_DEFAULT_RECORDINGS_DIR.iterdir())
        if path.is_file() and path.suffix.casefold() in _VIDEO_EXTENSIONS
    ]
    return videos[0] if videos else None


def _load_config(config_path: Path) -> GameConfig:
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise _CliError(f"Config is not valid JSON: {config_path}") from exc
    if not isinstance(payload, dict):
        raise _CliError(f"Config must be a JSON object: {config_path}")
    return cast(GameConfig, payload)


def _resolve_existing_path(path: Path, label: str) -> Path:
    candidate = path.expanduser()
    if not candidate.is_absolute():
        candidate = _REPO_ROOT / candidate
    if not candidate.exists():
        raise _CliError(f"{label.capitalize()} path does not exist: {path}")
    if not candidate.is_file():
        raise _CliError(f"{label.capitalize()} path is not a file: {path}")
    return candidate.resolve()


def _output_dir(raw_output_dir: str | None, video_path: Path) -> Path:
    if raw_output_dir is not None:
        candidate = Path(raw_output_dir).expanduser()
        return (candidate if candidate.is_absolute() else _REPO_ROOT / candidate).resolve()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return (_DEFAULT_OUTPUT_ROOT / f"{video_path.stem}-{stamp}").resolve()


def _write_timeline(
    *,
    path: Path,
    video_path: Path,
    config_path: Path,
    config: GameConfig,
    result: dict[str, Any],
) -> None:
    moments = cast(list[RewardMoment], result["moments"])
    audio_extract = cast(AudioExtract, result["audio"])
    candidates = cast(list[CandidateEvent], result["candidates"])
    payload: dict[str, JsonValue] = {
        "schema_version": "rga.reward_timeline.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "video": {
            "path": _relative(video_path),
            "duration_s": round(audio_extract.duration_s, 4),
            "source_rights_policy": "first_party_self_recorded_required",
        },
        "config": {
            "path": _relative(config_path),
            "game": str(config.get("game", "unknown")),
            "schema_version": str(config.get("schema_version", "unknown")),
        },
        "summary": {
            "frame_count": len(cast(list[FrameSample], result["frames"])),
            "candidate_count": len(candidates),
            "candidate_count_by_modality": _candidate_counts(candidates),
            "reward_moment_count": len(moments),
            "reward_density_window_count": len(cast(list[dict[str, JsonValue]], result["density"])),
        },
        "events": [
            _moment_record(moment, index)
            for index, moment in enumerate(moments, start=1)
        ],
        "reward_density": cast(list[dict[str, JsonValue]], result["density"]),
    }
    path.write_text(json.dumps(_json_ready(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_density_png(path: Path, density: list[dict[str, JsonValue]]) -> None:
    centers, values = _density_points(density)

    try:
        import matplotlib
    except ModuleNotFoundError:
        _write_basic_density_png(path, centers, values)
        return

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 4), dpi=140)
    if centers:
        ax.plot(centers, values, color="#1f77b4", linewidth=2.0)
        ax.fill_between(centers, values, color="#1f77b4", alpha=0.18)
    else:
        ax.plot([], [])
    ax.set_title("Reward Density")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Reward score / second")
    ax.grid(True, alpha=0.25)
    ax.set_ylim(bottom=0.0)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _density_points(density: list[dict[str, JsonValue]]) -> tuple[list[float], list[float]]:
    centers = [
        (_as_float(window.get("window_start"), 0.0) + _as_float(window.get("window_end"), 0.0)) / 2.0
        for window in density
    ]
    values = [_as_float(window.get("reward_density"), 0.0) for window in density]
    return centers, values


def _write_basic_density_png(path: Path, centers: list[float], values: list[float]) -> None:
    width, height = 1000, 400
    left, right, top, bottom = 70, 24, 30, 55
    plot_left = left
    plot_right = width - right
    plot_top = top
    plot_bottom = height - bottom
    pixels = bytearray([255] * width * height * 3)

    for x in range(plot_left, plot_right + 1):
        _set_pixel(pixels, width, height, x, plot_bottom, (180, 180, 180))
    for y in range(plot_top, plot_bottom + 1):
        _set_pixel(pixels, width, height, plot_left, y, (180, 180, 180))
    for fraction in (0.25, 0.5, 0.75):
        y = int(plot_bottom - ((plot_bottom - plot_top) * fraction))
        for x in range(plot_left, plot_right + 1):
            if x % 6 in {0, 1}:
                _set_pixel(pixels, width, height, x, y, (225, 225, 225))

    if centers and values:
        min_x = min(centers)
        max_x = max(centers)
        if max_x <= min_x:
            max_x = min_x + 1.0
        max_y = max(max(values), 1e-6)
        points: list[tuple[int, int]] = []
        for center, value in zip(centers, values, strict=False):
            x = plot_left + round(((center - min_x) / (max_x - min_x)) * (plot_right - plot_left))
            y = plot_bottom - round((max(0.0, value) / max_y) * (plot_bottom - plot_top))
            points.append((x, y))
        if len(points) == 1:
            x, y = points[0]
            for dx in range(-3, 4):
                for dy in range(-3, 4):
                    _set_pixel(pixels, width, height, x + dx, y + dy, (31, 119, 180))
        for start, end in zip(points, points[1:], strict=False):
            _draw_line(pixels, width, height, start, end, (31, 119, 180))

    path.write_bytes(_png_bytes(width, height, pixels))


def _draw_line(
    pixels: bytearray,
    width: int,
    height: int,
    start: tuple[int, int],
    end: tuple[int, int],
    color: tuple[int, int, int],
) -> None:
    x0, y0 = start
    x1, y1 = end
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    error = dx + dy
    while True:
        for ox, oy in ((0, 0), (1, 0), (0, 1)):
            _set_pixel(pixels, width, height, x0 + ox, y0 + oy, color)
        if x0 == x1 and y0 == y1:
            break
        doubled = 2 * error
        if doubled >= dy:
            error += dy
            x0 += sx
        if doubled <= dx:
            error += dx
            y0 += sy


def _set_pixel(
    pixels: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    color: tuple[int, int, int],
) -> None:
    if not (0 <= x < width and 0 <= y < height):
        return
    offset = (y * width + x) * 3
    pixels[offset : offset + 3] = bytes(color)


def _png_bytes(width: int, height: int, pixels: bytearray) -> bytes:
    row_size = width * 3
    raw = b"".join(
        b"\x00" + bytes(pixels[y * row_size : (y + 1) * row_size])
        for y in range(height)
    )
    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            _png_chunk(b"IHDR", pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)),
            _png_chunk(b"IDAT", zlib.compress(raw, level=6)),
            _png_chunk(b"IEND", b""),
        ]
    )


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return pack(">I", len(data)) + kind + data + pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)


def _write_report(
    *,
    path: Path,
    video_path: Path,
    config_path: Path,
    result: dict[str, Any],
    timeline_path: Path,
    density_path: Path,
) -> None:
    audio_extract = cast(AudioExtract, result["audio"])
    moments = cast(list[RewardMoment], result["moments"])
    candidates = cast(list[CandidateEvent], result["candidates"])
    density = cast(list[dict[str, JsonValue]], result["density"])
    gaps = _reward_gaps(moments)
    lines = [
        "# RGA Reward Moment Report",
        "",
        f"- Video: `{_relative(video_path)}`",
        f"- Config: `{_relative(config_path)}`",
        f"- Duration: {audio_extract.duration_s:.2f}s",
        f"- Sampled frames: {len(cast(list[FrameSample], result['frames']))}",
        f"- Candidates: {len(candidates)} ({_counts_text(_candidate_counts(candidates))})",
        f"- Reward moments: {len(moments)}",
        f"- Density windows: {len(density)}",
        f"- Timeline JSON: `{_relative(timeline_path)}`",
        f"- Density PNG: `{_relative(density_path)}`",
        "",
        "Audio cues were used only as confidence boosts; no audio-only reward moments are emitted.",
    ]
    if gaps:
        lines.extend(
            [
                "",
                f"Reward gap p50: {_percentile(gaps, 50):.2f}s",
                f"Reward gap p90: {_percentile(gaps, 90):.2f}s",
            ]
        )
    if moments:
        lines.extend(["", "## Reward Moments", "", "| # | Time | Confidence | Evidence |", "|---|---:|---:|---|"])
        for index, moment in enumerate(moments[:12], start=1):
            evidence = _evidence_text(moment)
            lines.append(
                f"| {index} | {moment.t_start:.2f}-{moment.t_end:.2f}s | {moment.confidence:.2f} | {evidence} |"
            )
        if len(moments) > 12:
            lines.append(f"| ... | ... | ... | {len(moments) - 12} additional moments in JSON |")
    else:
        lines.extend(["", "No reward moments met the configured precision threshold."])

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _moment_record(moment: RewardMoment, index: int) -> dict[str, JsonValue]:
    record = cast(dict[str, JsonValue], _json_ready(moment))
    record["id"] = f"rm_{index:04d}"
    record["type"] = "reward_moment"
    return record


def _candidate_counts(candidates: list[CandidateEvent]) -> dict[str, JsonValue]:
    counts: dict[str, JsonValue] = {}
    for candidate in candidates:
        key = candidate.modality.value
        current = counts.get(key, 0)
        counts[key] = int(current) + 1 if isinstance(current, int) else 1
    return counts


def _counts_text(counts: dict[str, JsonValue]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def _reward_gaps(moments: list[RewardMoment]) -> list[float]:
    times = sorted((moment.t_start + moment.t_end) / 2.0 for moment in moments)
    return [
        times[index] - times[index - 1]
        for index in range(1, len(times))
        if times[index] >= times[index - 1]
    ]


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * (percentile / 100.0)
    lower = int(position)
    upper = min(len(ordered) - 1, lower + 1)
    fraction = position - lower
    return ordered[lower] + ((ordered[upper] - ordered[lower]) * fraction)


def _evidence_text(moment: RewardMoment) -> str:
    timestamp = moment.evidence_ref.get("timestamp")
    path = moment.evidence_ref.get("path")
    frame_index = moment.evidence_ref.get("frame_index")
    parts: list[str] = []
    if isinstance(timestamp, int | float):
        parts.append(f"t={float(timestamp):.2f}s")
    if isinstance(frame_index, int):
        parts.append(f"frame={frame_index}")
    if isinstance(path, str):
        parts.append(Path(path).name)
    return ", ".join(parts) if parts else "see JSON evidence_ref"


def _json_ready(value: Any) -> JsonValue:
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _json_ready(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, set):
        return [_json_ready(item) for item in sorted(value, key=str)]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


def _as_float(value: JsonValue | None, default: float) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, int | float | str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(_REPO_ROOT))
    except ValueError:
        return str(path)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
