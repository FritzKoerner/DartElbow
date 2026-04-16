"""Visualization overlay for annotated video output.

Draws joint markers, arm skeleton, angle arc, and release frame indicator.
"""

import cv2
import numpy as np


# Colors (BGR)
COLOR_SHOULDER = (0, 0, 255)    # red
COLOR_ELBOW = (0, 255, 0)       # green
COLOR_WRIST = (255, 0, 0)       # blue
COLOR_SKELETON = (255, 255, 255) # white
COLOR_ANGLE = (0, 255, 255)     # yellow
COLOR_RELEASE = (0, 165, 255)   # orange

JOINT_COLORS = {
    "shoulder": COLOR_SHOULDER,
    "elbow": COLOR_ELBOW,
    "wrist": COLOR_WRIST,
}


def draw_overlay(frame, positions, angle, is_release):
    """Draw tracking overlay on a video frame.

    Args:
        frame: BGR image (modified in-place).
        positions: Dict {"shoulder": (x,y) or None, ...}.
        angle: Elbow angle in degrees, or None.
        is_release: True if this is the detected release frame.
    """
    pts = {}
    for joint, pos in positions.items():
        if pos is not None:
            pt = (int(round(pos[0])), int(round(pos[1])))
            pts[joint] = pt
            cv2.circle(frame, pt, 6, JOINT_COLORS[joint], -1)
            cv2.circle(frame, pt, 8, JOINT_COLORS[joint], 2)

    # Draw skeleton lines
    if "shoulder" in pts and "elbow" in pts:
        cv2.line(frame, pts["shoulder"], pts["elbow"], COLOR_SKELETON, 2)
    if "elbow" in pts and "wrist" in pts:
        cv2.line(frame, pts["elbow"], pts["wrist"], COLOR_SKELETON, 2)

    # Draw angle arc and text at elbow
    if angle is not None and "shoulder" in pts and "elbow" in pts and "wrist" in pts:
        _draw_angle_arc(frame, pts["shoulder"], pts["elbow"], pts["wrist"], angle)

    # Release frame indicator
    if is_release:
        h, w = frame.shape[:2]
        cv2.rectangle(frame, (0, 0), (w - 1, h - 1), COLOR_RELEASE, 4)
        cv2.putText(
            frame, "RELEASE",
            (w // 2 - 80, 40),
            cv2.FONT_HERSHEY_SIMPLEX, 1.2, COLOR_RELEASE, 3,
        )
        if angle is not None:
            cv2.putText(
                frame, f"Elbow: {angle:.1f} deg",
                (w // 2 - 100, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, COLOR_RELEASE, 2,
            )


def _draw_angle_arc(frame, shoulder, elbow, wrist, angle):
    """Draw an arc at the elbow showing the angle."""
    # Compute angles of the two arm segments relative to horizontal
    angle_upper = np.degrees(np.arctan2(
        -(shoulder[1] - elbow[1]), shoulder[0] - elbow[0]
    ))
    angle_lower = np.degrees(np.arctan2(
        -(wrist[1] - elbow[1]), wrist[0] - elbow[0]
    ))

    # Ensure we draw the arc on the correct side (interior angle)
    start_angle = min(angle_upper, angle_lower)
    end_angle = max(angle_upper, angle_lower)

    # If the arc would span more than 180 degrees, flip it
    if end_angle - start_angle > 180:
        start_angle, end_angle = end_angle, start_angle + 360

    arc_radius = 30
    cv2.ellipse(
        frame, elbow, (arc_radius, arc_radius),
        0, -end_angle, -start_angle,  # negate because OpenCV y-axis is flipped
        COLOR_ANGLE, 2,
    )

    # Angle text near the arc
    mid_angle = np.radians((angle_upper + angle_lower) / 2)
    text_x = int(elbow[0] + (arc_radius + 15) * np.cos(mid_angle))
    text_y = int(elbow[1] - (arc_radius + 15) * np.sin(mid_angle))
    cv2.putText(
        frame, f"{angle:.0f}",
        (text_x - 15, text_y + 5),
        cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLOR_ANGLE, 2,
    )


def create_video_writer(path, fps, frame_size):
    """Create an OpenCV VideoWriter for MP4 output.

    Args:
        path: Output file path.
        fps: Frames per second.
        frame_size: (width, height) tuple.

    Returns:
        cv2.VideoWriter instance.
    """
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    return cv2.VideoWriter(path, fourcc, fps, frame_size)
