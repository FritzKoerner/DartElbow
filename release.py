"""Dart release moment detection via wrist velocity analysis.

Finds the frame where the dart is released by detecting the peak
in the wrist velocity profile.
"""

import numpy as np
from scipy.signal import savgol_filter, find_peaks


def compute_velocity(positions, fps, component="speed"):
    """Compute per-frame velocity from a position track.

    Args:
        positions: List of (x, y) or None for each frame.
        fps: Video frames per second.
        component: "speed" (euclidean), "x", or "y".

    Returns:
        Numpy array of velocity values (NaN where positions are missing).
    """
    n = len(positions)
    vel = np.full(n, np.nan)

    for i in range(1, n):
        if positions[i] is not None and positions[i - 1] is not None:
            dx = positions[i][0] - positions[i - 1][0]
            dy = positions[i][1] - positions[i - 1][1]

            if component == "speed":
                vel[i] = np.hypot(dx, dy) * fps
            elif component == "x":
                vel[i] = abs(dx) * fps
            elif component == "y":
                vel[i] = abs(dy) * fps

    return vel


def detect_release(
    wrist_positions, fps, smooth_window, smooth_polyorder,
    peak_prominence, frames_after_peak, velocity_component="speed"
):
    """Detect the dart release frame from wrist velocity.

    Args:
        wrist_positions: List of (x, y) or None per frame.
        fps: Frames per second.
        smooth_window: Savitzky-Golay filter window.
        smooth_polyorder: Savitzky-Golay polynomial order.
        peak_prominence: Minimum peak prominence for detection.
        frames_after_peak: Offset from velocity peak to release frame.
        velocity_component: "speed", "x", or "y".

    Returns:
        Frame index of detected release, or None if not found.
    """
    vel = compute_velocity(wrist_positions, fps, velocity_component)

    # Replace NaN with 0 for smoothing
    vel_clean = np.nan_to_num(vel, nan=0.0)

    if len(vel_clean) < smooth_window:
        return None

    vel_smooth = savgol_filter(vel_clean, smooth_window, smooth_polyorder)
    vel_smooth = np.maximum(vel_smooth, 0)  # velocity can't be negative

    peaks, properties = find_peaks(vel_smooth, prominence=peak_prominence)

    if len(peaks) == 0:
        return None

    # Select the most prominent peak
    best_idx = np.argmax(properties["prominences"])
    peak_frame = peaks[best_idx]

    release_frame = peak_frame + frames_after_peak
    release_frame = min(release_frame, len(wrist_positions) - 1)

    return int(release_frame)
