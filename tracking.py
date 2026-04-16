"""Joint identity assignment and frame-to-frame tracking.

Assigns detected marker centroids to shoulder/elbow/wrist labels and
maintains identity across frames using the Hungarian algorithm.
"""

import numpy as np
from scipy.optimize import linear_sum_assignment


JOINTS = ["shoulder", "elbow", "wrist"]


def initial_assignment(centroids, faces_right=True):
    """Assign 3 centroids to shoulder/elbow/wrist on the first valid frame.

    Heuristic for side-view: shoulder is topmost (smallest y), wrist is
    furthest forward (largest x if facing right, smallest x if facing left),
    elbow is the remaining point.

    Args:
        centroids: List of exactly 3 (x, y) tuples.
        faces_right: True if the thrower faces right in the video.

    Returns:
        Dict {"shoulder": (x,y), "elbow": (x,y), "wrist": (x,y)}.
    """
    assert len(centroids) == 3, f"Expected 3 centroids, got {len(centroids)}"

    points = sorted(centroids, key=lambda p: p[1])  # sort by y ascending (top first)
    shoulder = points[0]  # topmost point

    remaining = points[1:]
    if faces_right:
        # Wrist is further right (larger x)
        remaining.sort(key=lambda p: p[0])
        elbow, wrist = remaining[0], remaining[1]
    else:
        # Wrist is further left (smaller x)
        remaining.sort(key=lambda p: p[0])
        wrist, elbow = remaining[0], remaining[1]

    return {"shoulder": shoulder, "elbow": elbow, "wrist": wrist}


def track_frame(prev_positions, current_centroids, max_jump):
    """Assign current detections to joints using Hungarian algorithm.

    Args:
        prev_positions: Dict {"shoulder": (x,y), "elbow": (x,y), "wrist": (x,y)}.
        current_centroids: List of (x, y) tuples (may have fewer or more than 3).
        max_jump: Maximum allowed pixel distance for a valid assignment.

    Returns:
        Dict {"shoulder": (x,y) or None, "elbow": ..., "wrist": ...}.
    """
    result = {j: None for j in JOINTS}

    if not current_centroids:
        return result

    prev_points = [prev_positions[j] for j in JOINTS]
    n_prev = len(prev_points)
    n_curr = len(current_centroids)

    # Build cost matrix (Euclidean distances)
    cost = np.zeros((n_prev, n_curr))
    for i, pp in enumerate(prev_points):
        for j, cp in enumerate(current_centroids):
            cost[i, j] = np.hypot(pp[0] - cp[0], pp[1] - cp[1])

    # Hungarian algorithm for optimal assignment
    row_idx, col_idx = linear_sum_assignment(cost)

    for r, c in zip(row_idx, col_idx):
        if cost[r, c] <= max_jump:
            result[JOINTS[r]] = current_centroids[c]

    return result


def interpolate_gaps(positions, max_gap=5):
    """Fill short gaps in a position track via linear interpolation.

    Args:
        positions: List of (x, y) or None for each frame.
        max_gap: Maximum number of consecutive None frames to interpolate.

    Returns:
        New list with short gaps filled.
    """
    result = list(positions)
    n = len(result)
    i = 0

    while i < n:
        if result[i] is None:
            # Find the gap extent
            gap_start = i
            while i < n and result[i] is None:
                i += 1
            gap_end = i  # first non-None after the gap (or n)
            gap_len = gap_end - gap_start

            # Interpolate only if gap is short and we have points on both sides
            if gap_len <= max_gap and gap_start > 0 and gap_end < n:
                x0, y0 = result[gap_start - 1]
                x1, y1 = result[gap_end]
                for k in range(gap_len):
                    t = (k + 1) / (gap_len + 1)
                    result[gap_start + k] = (
                        x0 + t * (x1 - x0),
                        y0 + t * (y1 - y0),
                    )
        else:
            i += 1

    return result
