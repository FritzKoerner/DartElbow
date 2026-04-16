"""Dart throw elbow angle detection pipeline.

Detects colored tape markers on shoulder/elbow/wrist, tracks them across
video frames, and reports the elbow angle at the moment of dart release.
"""

import argparse
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


def load_config(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Detect elbow angle at dart release from side-view video."
    )
    parser.add_argument("--video", help="Path to input video (overrides config)")
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
        # Not enough data points to smooth — return as-is
        return raw_positions

    # Interpolate gaps for smoothing, then apply filter
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


def main():
    args = parse_args()
    cfg = load_config(args.config)

    video_path = args.video or cfg["video_path"]
    if not os.path.isfile(video_path):
        print(f"Error: Video file not found: {video_path}")
        sys.exit(1)

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
    show_preview = cfg["show_preview"] and not args.no_preview

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Cannot open video: {video_path}")
        sys.exit(1)

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    print(f"Video: {video_path}")
    print(f"FPS: {fps:.1f}, Frames: {total_frames}, Duration: {total_frames/fps:.1f}s")
    print(f"Resolution: {width}x{height}")
    print()

    # --- Pass 1: Detect and track markers ---
    print("Pass 1: Detecting and tracking markers...")

    raw_positions = {"shoulder": [], "elbow": [], "wrist": []}
    prev_positions = None
    initialized = False
    detected_count = 0

    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Apply ROI crop if configured
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
                # Offset centroids back to full-frame coordinates
                centroids_full = [(c[0] + rx, c[1] + ry) for c in centroids]
                prev_positions = initial_assignment(centroids_full, faces_right)
                initialized = True
                for joint in raw_positions:
                    # Backfill with None for frames before initialization
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
            # Update prev_positions only for joints that were tracked
            for joint, pos in current.items():
                if pos is not None:
                    prev_positions[joint] = pos
            if all(v is not None for v in current.values()):
                detected_count += 1

        frame_idx += 1

    cap.release()

    if not initialized:
        print("Error: Could not detect 3 markers in any frame. Check HSV ranges.")
        print("  Run: python calibrate.py <video_path>")
        sys.exit(1)

    print(
        f"Markers detected in {detected_count}/{frame_idx} frames "
        f"({100 * detected_count / frame_idx:.1f}%)"
    )

    # --- Post-pass: Smooth, compute angles, detect release ---
    print("Smoothing position tracks...")

    # Interpolate short gaps
    for joint in raw_positions:
        raw_positions[joint] = interpolate_gaps(raw_positions[joint], max_gap=5)

    # Smooth
    smoothed = {}
    for joint in raw_positions:
        smoothed[joint] = smooth_positions(raw_positions[joint], smooth_win, smooth_poly)

    # Compute elbow angle per frame
    angles = []
    for i in range(frame_idx):
        s = smoothed["shoulder"][i]
        e = smoothed["elbow"][i]
        w = smoothed["wrist"][i]
        if s is not None and e is not None and w is not None:
            angles.append(compute_elbow_angle(s, e, w))
        else:
            angles.append(None)

    # Detect release
    release_frame = detect_release(
        smoothed["wrist"],
        fps,
        smooth_win,
        smooth_poly,
        cfg["velocity_peak_prominence"],
        cfg["frames_after_peak"],
        cfg["velocity_component"],
    )

    print()
    if release_frame is not None and release_frame < len(angles):
        release_time = release_frame / fps
        release_angle = angles[release_frame]
        print(f"Release detected at frame {release_frame} (t = {release_time:.3f}s)")
        if release_angle is not None:
            print(f"Elbow angle at release: {release_angle:.1f} degrees")
        else:
            print("Warning: Could not compute elbow angle at release frame (missing data)")

        valid_angles = [a for a in angles if a is not None]
        if valid_angles:
            print(
                f"Elbow angle range during video: "
                f"{min(valid_angles):.1f} - {max(valid_angles):.1f} degrees"
            )
    else:
        print("Warning: Could not detect release moment.")
        print("  Try adjusting velocity_peak_prominence in config.yaml")

    # --- Pass 2: Write annotated video ---
    output_path = cfg.get("output_video")
    if output_path or show_preview:
        print()
        print("Pass 2: Writing annotated video...")

        cap = cv2.VideoCapture(video_path)
        writer = None
        if output_path:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            writer = create_video_writer(output_path, fps, (width, height))

        frame_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            positions = {
                joint: smoothed[joint][frame_idx] for joint in smoothed
            }
            angle = angles[frame_idx]
            is_release = frame_idx == release_frame

            draw_overlay(frame, positions, angle, is_release)

            if writer is not None:
                writer.write(frame)

            if show_preview:
                cv2.imshow("Dart Throw Analysis", frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break

            frame_idx += 1

        cap.release()
        if writer is not None:
            writer.release()
            print(f"Annotated video saved to: {output_path}")
        if show_preview:
            cv2.destroyAllWindows()

    print("\nDone.")


if __name__ == "__main__":
    main()
