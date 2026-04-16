"""Marker detection via HSV color thresholding.

Detects colored tape markers in a video frame and returns their centroids.
"""

import cv2
import numpy as np


def detect_markers(frame, hsv_lower, hsv_upper, min_area, max_area,
                   hsv_lower2=None, hsv_upper2=None):
    """Detect colored markers in a BGR frame.

    Args:
        frame: BGR image (numpy array).
        hsv_lower: Lower HSV bound as numpy array [H, S, V].
        hsv_upper: Upper HSV bound as numpy array [H, S, V].
        min_area: Minimum contour area in pixels.
        max_area: Maximum contour area in pixels.
        hsv_lower2: Optional second lower HSV bound (for red hue wrapping).
        hsv_upper2: Optional second upper HSV bound (for red hue wrapping).

    Returns:
        List of (x, y) centroid tuples for detected markers.
    """
    blurred = cv2.GaussianBlur(frame, (5, 5), 0)
    hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, hsv_lower, hsv_upper)

    # Support dual HSV ranges for colors that wrap around hue 0/180 (e.g. red)
    if hsv_lower2 is not None and hsv_upper2 is not None:
        mask2 = cv2.inRange(hsv, hsv_lower2, hsv_upper2)
        mask = cv2.bitwise_or(mask, mask2)

    # Morphological cleanup: remove noise, fill small gaps
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    centroids = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if min_area <= area <= max_area:
            M = cv2.moments(contour)
            if M["m00"] > 0:
                cx = M["m10"] / M["m00"]
                cy = M["m01"] / M["m00"]
                centroids.append((cx, cy))

    return centroids
