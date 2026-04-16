"""Elbow angle computation from three joint positions."""

import numpy as np


def compute_elbow_angle(shoulder, elbow, wrist):
    """Compute the interior angle at the elbow joint.

    The angle is formed by vectors elbow->shoulder and elbow->wrist.
    A fully extended arm gives ~180 degrees, a tightly bent elbow ~30-60.

    Args:
        shoulder: (x, y) position of the shoulder marker.
        elbow: (x, y) position of the elbow marker.
        wrist: (x, y) position of the wrist marker.

    Returns:
        Angle in degrees (0-180).
    """
    s = np.array(shoulder)
    e = np.array(elbow)
    w = np.array(wrist)

    vec_upper = s - e  # elbow -> shoulder
    vec_lower = w - e  # elbow -> wrist

    norm_upper = np.linalg.norm(vec_upper)
    norm_lower = np.linalg.norm(vec_lower)

    if norm_upper < 1e-8 or norm_lower < 1e-8:
        return 0.0

    cos_angle = np.dot(vec_upper, vec_lower) / (norm_upper * norm_lower)
    cos_angle = np.clip(cos_angle, -1.0, 1.0)

    return float(np.degrees(np.arccos(cos_angle)))
