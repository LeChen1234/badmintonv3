import argparse
import csv
from pathlib import Path

import cv2


def load_selected_indices(csv_path: Path, threshold: float) -> list[int]:
    indices = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                score = float(row.get("motion_score", "0"))
                frame_idx = int(row.get("frame_index", "-1"))
            except ValueError:
                continue
            if frame_idx >= 0 and score >= threshold:
                indices.append(frame_idx)
    return sorted(set(indices))


def export_frames(video_path: Path, frame_indices: list[int], output_dir: Path) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    exported = 0
    for frame_idx in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ok, frame = cap.read()
        if not ok:
            continue
        out_path = output_dir / f"frame_{frame_idx:08d}.jpg"
        cv2.imwrite(str(out_path), frame)
        exported += 1

    cap.release()
    return exported


def main() -> None:
    parser = argparse.ArgumentParser(description="Export selected frames by motion threshold")
    parser.add_argument(
        "--csv",
        default="data/exports/frame_motion_scores.csv",
        help="Path to frame motion score CSV",
    )
    parser.add_argument(
        "--video",
        default="video.mp4",
        help="Path to source video",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=693.0,
        help="Motion threshold (>= threshold will be selected)",
    )
    parser.add_argument(
        "--output-dir",
        default="data/exports/selected_frames_p90_693",
        help="Output directory for selected frames",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv)
    video_path = Path(args.video)
    output_dir = Path(args.output_dir)

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    frame_indices = load_selected_indices(csv_path, args.threshold)
    if not frame_indices:
        print("No frames matched the threshold.")
        return

    exported = export_frames(video_path, frame_indices, output_dir)
    print(f"threshold={args.threshold}")
    print(f"selected_frames={len(frame_indices)}")
    print(f"exported_frames={exported}")
    print(f"output_dir={output_dir}")


if __name__ == "__main__":
    main()
