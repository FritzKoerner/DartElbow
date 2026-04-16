"""Interactive HSV range tuner for colored tape markers.

Opens a video frame and provides trackbars to adjust HSV thresholds
in real-time. Press 's' to print values, 'b' to save to batch config,
'q' to quit.

Usage:
    python calibrate.py <video_path> [--frame N]
    python calibrate.py <video_path> --save-to batch_config.yaml
"""

import argparse
import os
import sys

import cv2
import numpy as np
import yaml


def nothing(_):
    """Trackbar callback (required by OpenCV, does nothing)."""
    pass


def save_to_batch_config(path, video_name, hsv_lower, hsv_upper):
    """Append or update HSV values for a video in the batch config file."""
    data = {}
    if os.path.isfile(path):
        with open(path, "r") as f:
            loaded = yaml.safe_load(f)
            if isinstance(loaded, dict):
                data = loaded

    data[video_name] = {
        "hsv_lower": hsv_lower,
        "hsv_upper": hsv_upper,
    }

    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=None, sort_keys=False)

    print(f"Saved HSV values for '{video_name}' to {path}")


def main():
    parser = argparse.ArgumentParser(description="Tune HSV ranges for marker detection")
    parser.add_argument("video", help="Path to video file")
    parser.add_argument(
        "--frame", type=int, default=0, help="Frame number to use (default: 0)"
    )
    parser.add_argument(
        "--save-to",
        default="batch_config.yaml",
        help="Batch config file to save to with 'b' key (default: batch_config.yaml)",
    )
    args = parser.parse_args()

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"Error: Cannot open video: {args.video}")
        sys.exit(1)

    # Seek to requested frame
    if args.frame > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, args.frame)

    ret, frame = cap.read()
    cap.release()

    if not ret:
        print(f"Error: Cannot read frame {args.frame}")
        sys.exit(1)

    video_name = os.path.basename(args.video)

    # Create windows
    cv2.namedWindow("Trackbars", cv2.WINDOW_NORMAL)
    cv2.namedWindow("Result", cv2.WINDOW_NORMAL)

    # Create trackbars with default values for green tape
    cv2.createTrackbar("H Low", "Trackbars", 35, 179, nothing)
    cv2.createTrackbar("S Low", "Trackbars", 100, 255, nothing)
    cv2.createTrackbar("V Low", "Trackbars", 100, 255, nothing)
    cv2.createTrackbar("H High", "Trackbars", 85, 179, nothing)
    cv2.createTrackbar("S High", "Trackbars", 255, 255, nothing)
    cv2.createTrackbar("V High", "Trackbars", 255, 255, nothing)

    print("Adjust trackbars until exactly 3 marker blobs are visible.")
    print("Press 's' to print values, 'b' to save to batch config, 'q' to quit.")
    print()

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    while True:
        h_lo = cv2.getTrackbarPos("H Low", "Trackbars")
        s_lo = cv2.getTrackbarPos("S Low", "Trackbars")
        v_lo = cv2.getTrackbarPos("V Low", "Trackbars")
        h_hi = cv2.getTrackbarPos("H High", "Trackbars")
        s_hi = cv2.getTrackbarPos("S High", "Trackbars")
        v_hi = cv2.getTrackbarPos("V High", "Trackbars")

        lower = np.array([h_lo, s_lo, v_lo], dtype=np.uint8)
        upper = np.array([h_hi, s_hi, v_hi], dtype=np.uint8)

        mask = cv2.inRange(hsv, lower, upper)

        # Find and count contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        # Filter by area (minimum 50 pixels to avoid noise)
        valid = [c for c in contours if cv2.contourArea(c) >= 50]

        # Show mask and original side by side with contour overlay
        frame_display = frame.copy()
        cv2.drawContours(frame_display, valid, -1, (0, 255, 0), 2)

        # Draw centroids
        for c in valid:
            M = cv2.moments(c)
            if M["m00"] > 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                cv2.circle(frame_display, (cx, cy), 5, (0, 0, 255), -1)

        mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        combined = np.hstack([frame_display, mask_bgr])

        # Add text showing contour count
        color = (0, 255, 0) if len(valid) == 3 else (0, 0, 255)
        cv2.putText(
            combined,
            f"Markers found: {len(valid)}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            color,
            2,
        )

        cv2.imshow("Result", combined)

        key = cv2.waitKey(30) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("s"):
            print("# Paste into config.yaml:")
            print(f"hsv_lower: [{h_lo}, {s_lo}, {v_lo}]")
            print(f"hsv_upper: [{h_hi}, {s_hi}, {v_hi}]")
            print()
        elif key == ord("b"):
            save_to_batch_config(
                args.save_to,
                video_name,
                [h_lo, s_lo, v_lo],
                [h_hi, s_hi, v_hi],
            )

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
