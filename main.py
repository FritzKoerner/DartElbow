"""Dart throw elbow angle detection pipeline.

Detects colored tape markers on shoulder/elbow/wrist, tracks them across
video frames, and reports the elbow angle at the moment of dart release.

Supports single-video and batch mode (--batch <folder> → CSV output).
"""

import argparse
import csv
import os
import sys

import cv2
import numpy as np
import yaml
from scipy.signal import savgol_filter

from detection import detect_markers
from tracking import initial_assignment, track_frame, interpolate_gaps
from angle import compute_elbow_angle
from release import detect_release
from visualization import draw_overlay, create_video_writer

VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}


def load_config(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Detect elbow angle at dart release from side-view video."
    )
    parser.add_argument("--video", help="Path to input video (overrides config)")
    parser.add_argument(
        "--batch",
        help="Process all videos in a folder and output a CSV with results",
    )
    parser.add_argument(
        "--batch-config",
        default="batch_config.yaml",
        help="Per-video HSV overrides for batch mode (default: batch_config.yaml)",
    )
    parser.add_argument(
        "--output-csv",
        default="results.csv",
        help="CSV output path for batch mode (default: results.csv)",
    )
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument(
        "--no-preview", action="store_true", help="Disable live preview window"
    )
    return parser.parse_args()


def smooth_positions(raw_positions, window, polyorder):
    """Smooth a list of (x, y) or None values with Savitzky-Golay filter.

    Returns smoothed list of (x, y) with None gaps preserved.
    """
    n = len(raw_positions)
    xs = np.full(n, np.nan)
    ys = np.full(n, np.nan)

    for i, pos in enumerate(raw_positions):
        if pos is not None:
            xs[i], ys[i] = pos

    valid = ~np.isnan(xs)
    if valid.sum() < window:
        return raw_positions

    indices = np.arange(n)
    valid_idx = indices[valid]

    xs_interp = np.interp(indices, valid_idx, xs[valid])
    ys_interp = np.interp(indices, valid_idx, ys[valid])

    xs_smooth = savgol_filter(xs_interp, window, polyorder)
    ys_smooth = savgol_filter(ys_interp, window, polyorder)

    result = []
    for i in range(n):
        if valid[i] or (i > valid_idx[0] and i < valid_idx[-1]):
            result.append((float(xs_smooth[i]), float(ys_smooth[i])))
        else:
            result.append(None)
    return result


def analyze_video(video_path, cfg, write_video=True, show_preview=False):
    """Run the full analysis pipeline on a single video.

    Returns a dict with results, or None if analysis failed.
    """
    hsv_lower = np.array(cfg["hsv_lower"], dtype=np.uint8)
    hsv_upper = np.array(cfg["hsv_upper"], dtype=np.uint8)
    hsv_lower2 = np.array(cfg["hsv_lower2"], dtype=np.uint8) if cfg.get("hsv_lower2") else None
    hsv_upper2 = np.array(cfg["hsv_upper2"], dtype=np.uint8) if cfg.get("hsv_upper2") else None
    min_area = cfg["min_marker_area"]
    max_area = cfg["max_marker_area"]
    max_jump = cfg["max_jump"]
    faces_right = cfg["thrower_faces_right"]
    smooth_win = cfg["smoothing_window"]
    smooth_poly = cfg["smoothing_polyorder"]
    roi = cfg.get("roi")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"  Error: Cannot open video: {video_path}")
        return {"error": "Cannot open video file"}

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    if fps == 0:
        cap.release()
        print(f"  Error: Invalid video (0 FPS)")
        return {"error": "Invalid video (0 FPS)"}

    print(f"  FPS: {fps:.1f}, Frames: {total_frames}, Duration: {total_frames/fps:.1f}s")

    # --- Pass 1: Detect and track markers ---
    raw_positions = {"shoulder": [], "elbow": [], "wrist": []}
    prev_positions = None
    initialized = False
    detected_count = 0

    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if roi is not None:
            rx, ry, rw, rh = roi
            work_frame = frame[ry : ry + rh, rx : rx + rw]
        else:
            work_frame = frame
            rx, ry = 0, 0

        centroids = detect_markers(work_frame, hsv_lower, hsv_upper, min_area, max_area,
                                   hsv_lower2, hsv_upper2)

        if not initialized:
            if len(centroids) == 3:
                centroids_full = [(c[0] + rx, c[1] + ry) for c in centroids]
                prev_positions = initial_assignment(centroids_full, faces_right)
                initialized = True
                for joint in raw_positions:
                    raw_positions[joint] = [None] * frame_idx
                    raw_positions[joint].append(prev_positions[joint])
                detected_count += 1
            else:
                for joint in raw_positions:
                    raw_positions[joint].append(None)
        else:
            centroids_full = [(c[0] + rx, c[1] + ry) for c in centroids]
            current = track_frame(prev_positions, centroids_full, max_jump)
            for joint in raw_positions:
                raw_positions[joint].append(current.get(joint))
            for joint, pos in current.items():
                if pos is not None:
                    prev_positions[joint] = pos
            if all(v is not None for v in current.values()):
                detected_count += 1

        frame_idx += 1

    cap.release()

    if not initialized:
        print("  Error: Could not detect 3 markers in any frame.")
        return {"error": "Could not detect 3 markers in any frame"}

    detection_rate = 100 * detected_count / frame_idx
    print(f"  Markers detected in {detected_count}/{frame_idx} frames ({detection_rate:.1f}%)")

    # --- Post-pass: Smooth, compute angles, detect release ---
    for joint in raw_positions:
        raw_positions[joint] = interpolate_gaps(raw_positions[joint], max_gap=5)

    smoothed = {}
    for joint in raw_positions:
        smoothed[joint] = smooth_positions(raw_positions[joint], smooth_win, smooth_poly)

    angles = []
    for i in range(frame_idx):
        s = smoothed["shoulder"][i]
        e = smoothed["elbow"][i]
        w = smoothed["wrist"][i]
        if s is not None and e is not None and w is not None:
            angles.append(compute_elbow_angle(s, e, w))
        else:
            angles.append(None)

    release_frame = detect_release(
        smoothed["wrist"],
        fps,
        smooth_win,
        smooth_poly,
        cfg["velocity_peak_prominence"],
        cfg["frames_after_peak"],
        cfg["velocity_component"],
    )

    # Build result
    result = {
        "video": video_path,
        "fps": fps,
        "total_frames": total_frames,
        "detection_rate": detection_rate,
        "release_frame": None,
        "release_time": None,
        "release_angle": None,
        "angle_min": None,
        "angle_max": None,
    }

    valid_angles = [a for a in angles if a is not None]
    if valid_angles:
        result["angle_min"] = min(valid_angles)
        result["angle_max"] = max(valid_angles)

    if release_frame is not None and release_frame < len(angles):
        result["release_frame"] = release_frame
        result["release_time"] = release_frame / fps
        result["release_angle"] = angles[release_frame]
        print(f"  Release at frame {release_frame} (t = {result['release_time']:.3f}s)")
        if result["release_angle"] is not None:
            print(f"  Elbow angle at release: {result['release_angle']:.1f} degrees")
        else:
            print("  Warning: Could not compute angle at release frame")
    else:
        print("  Warning: Could not detect release moment")

    # --- Pass 2: Write annotated video ---
    output_path = cfg.get("output_video") if write_video else None
    if output_path or show_preview:
        if output_path:
            # In batch mode, put annotated videos in output/ named after the source
            base = os.path.splitext(os.path.basename(video_path))[0]
            out_dir = os.path.dirname(output_path) or "output"
            os.makedirs(out_dir, exist_ok=True)
            output_path = os.path.join(out_dir, f"{base}_annotated.mp4")

        cap = cv2.VideoCapture(video_path)
        writer = None
        if output_path:
            writer = create_video_writer(output_path, fps, (width, height))

        fi = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            positions = {joint: smoothed[joint][fi] for joint in smoothed}
            angle = angles[fi]
            is_release = fi == release_frame
            draw_overlay(frame, positions, angle, is_release)
            if writer is not None:
                writer.write(frame)
            if show_preview:
                cv2.imshow("Dart Throw Analysis", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
            fi += 1

        cap.release()
        if writer is not None:
            writer.release()
            print(f"  Annotated video: {output_path}")
        if show_preview:
            cv2.destroyAllWindows()

    return result


def run_single(args, cfg):
    """Run pipeline on a single video."""
    video_path = args.video or cfg["video_path"]
    if not os.path.isfile(video_path):
        print(f"Error: Video file not found: {video_path}")
        sys.exit(1)

    show_preview = cfg["show_preview"] and not args.no_preview
    print(f"Video: {video_path}")
    result = analyze_video(video_path, cfg, write_video=True, show_preview=show_preview)

    if "error" in result:
        print(f"\nAnalysis failed: {result['error']}")
        print("Run: python calibrate.py <video_path>")
        sys.exit(1)

    if result["angle_min"] is not None:
        print(f"  Angle range: {result['angle_min']:.1f} - {result['angle_max']:.1f} degrees")
    print("\nDone.")


def load_batch_config(path):
    """Load per-video overrides from batch config file.

    Returns a dict mapping video filename to override dict, or empty dict.
    """
    if not os.path.isfile(path):
        return {}
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def merge_config(base_cfg, overrides):
    """Return a copy of base_cfg with overrides applied."""
    merged = dict(base_cfg)
    merged.update(overrides)
    return merged


def run_batch(args, cfg):
    """Process all videos in a folder and write results to CSV."""
    folder = args.batch
    if not os.path.isdir(folder):
        print(f"Error: Folder not found: {folder}")
        sys.exit(1)

    video_files = sorted(
        f for f in os.listdir(folder)
        if os.path.splitext(f)[1].lower() in VIDEO_EXTENSIONS
    )

    if not video_files:
        print(f"Error: No video files found in {folder}")
        print(f"  Supported formats: {', '.join(VIDEO_EXTENSIONS)}")
        sys.exit(1)

    batch_overrides = load_batch_config(args.batch_config)
    has_overrides = bool(batch_overrides)

    print(f"Batch mode: {len(video_files)} videos in {folder}")
    if has_overrides:
        matched = [f for f in video_files if f in batch_overrides]
        print(f"Batch config: {args.batch_config} ({len(matched)}/{len(video_files)} videos with custom HSV)")
    print(f"Output CSV: {args.output_csv}")
    print()

    results = []
    for i, filename in enumerate(video_files, 1):
        video_path = os.path.join(folder, filename)
        video_cfg = merge_config(cfg, batch_overrides.get(filename, {}))
        if filename in batch_overrides:
            print(f"[{i}/{len(video_files)}] {filename} (custom HSV)")
        else:
            print(f"[{i}/{len(video_files)}] {filename}")
        result = analyze_video(video_path, video_cfg, write_video=False, show_preview=False)
        if "error" in result:
            results.append({
                "video": filename,
                "error": result["error"],
                "release_angle": None,
                "release_frame": None,
                "release_time": None,
                "angle_min": None,
                "angle_max": None,
                "detection_rate": None,
                "fps": None,
                "total_frames": None,
            })
        else:
            result["video"] = filename
            result["error"] = ""
            results.append(result)
        print()

    # Write CSV
    fieldnames = [
        "video",
        "release_angle",
        "release_frame",
        "release_time",
        "angle_min",
        "angle_max",
        "detection_rate",
        "fps",
        "total_frames",
        "error",
    ]
    with open(args.output_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            row = {}
            for key in fieldnames:
                val = r.get(key)
                if isinstance(val, float):
                    row[key] = f"{val:.2f}"
                else:
                    row[key] = val if val is not None else ""
            writer.writerow(row)

    print(f"Results written to {args.output_csv}")

    # Print summary table
    errors = [r for r in results if r.get("error")]
    successful = [r for r in results if r["release_angle"] is not None]
    no_release = [r for r in results if not r.get("error") and r["release_angle"] is None]
    print(f"\nSummary: {len(successful)}/{len(results)} videos analyzed successfully", end="")
    if errors:
        print(f" ({len(errors)} failed)")
        for r in errors:
            print(f"  - {r['video']}: {r['error']}")
    else:
        print()
    if no_release:
        print(f"  {len(no_release)} video(s) analyzed but no release detected")

    if successful:
        angles = [r["release_angle"] for r in successful]
        print(f"  Release angle mean: {np.mean(angles):.1f} degrees")
        print(f"  Release angle std:  {np.std(angles):.1f} degrees")
        print(f"  Release angle range: {min(angles):.1f} - {max(angles):.1f} degrees")

    print("\nDone.")


def main():
    args = parse_args()
    cfg = load_config(args.config)

    if args.batch:
        run_batch(args, cfg)
    else:
        run_single(args, cfg)


if __name__ == "__main__":
    main()
