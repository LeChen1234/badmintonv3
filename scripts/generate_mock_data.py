"""Generate mock test data for the annotation platform.

Creates synthetic video frames (colored placeholders) and mock annotations.
"""

import os
import sys
import json
import random
import argparse
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ml-backend"))
from pose_estimator import estimate_keypoints, KEYPOINT_NAMES
from action_recognizer import recognize_action, ACTION_TYPES

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def generate_mock_frames(
    output_dir: str,
    count: int = 100,
    width: int = 640,
    height: int = 480,
):
    """Generate placeholder frame images."""
    os.makedirs(output_dir, exist_ok=True)

    if not HAS_PIL:
        print("  Pillow not installed, creating empty placeholder files")
        for i in range(count):
            path = os.path.join(output_dir, f"frame_{i:05d}.jpg")
            with open(path, "wb") as f:
                f.write(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
        return

    for i in range(count):
        bg_color = (
            random.randint(20, 60),
            random.randint(80, 140),
            random.randint(20, 60),
        )
        img = Image.new("RGB", (width, height), bg_color)
        draw = ImageDraw.Draw(img)

        draw.text((width // 2 - 60, height // 2 - 10), f"Frame {i:05d}", fill=(255, 255, 255))

        cx, cy = width // 2 + random.randint(-50, 50), height // 2 + random.randint(-50, 50)
        draw.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=(255, 0, 0))

        path = os.path.join(output_dir, f"frame_{i:05d}.jpg")
        img.save(path, "JPEG", quality=85)

    print(f"  Generated {count} mock frames in {output_dir}")


def generate_mock_annotations(count: int = 100) -> list[dict]:
    """Generate mock annotation data in Label Studio export format."""
    annotations = []
    for i in range(count):
        keypoints = estimate_keypoints()
        for kp in keypoints:
            kp["from_name"] = "keypoints"
            kp["to_name"] = "image"
            kp["type"] = "keypointlabels"

        actions = recognize_action()
        result = keypoints + actions

        annotations.append({
            "id": i + 1,
            "data": {"image": f"frame_{i:05d}.jpg"},
            "annotations": [{
                "id": i + 1,
                "result": result,
                "completed_by": 1,
            }],
        })

    return annotations


def main():
    parser = argparse.ArgumentParser(description="Generate mock data for testing")
    parser.add_argument("--frames", type=int, default=100, help="Number of frames to generate")
    parser.add_argument("--output-dir", type=str, default=os.path.join(DATA_DIR, "mock_frames"))
    parser.add_argument("--annotations-out", type=str, default=os.path.join(DATA_DIR, "mock_annotations.json"))
    args = parser.parse_args()

    print("=== Generating Mock Frames ===")
    generate_mock_frames(args.output_dir, args.frames)

    print("\n=== Generating Mock Annotations ===")
    annotations = generate_mock_annotations(args.frames)
    os.makedirs(os.path.dirname(args.annotations_out), exist_ok=True)
    with open(args.annotations_out, "w", encoding="utf-8") as f:
        json.dump(annotations, f, ensure_ascii=False, indent=2)
    print(f"  Generated {len(annotations)} mock annotations -> {args.annotations_out}")

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
