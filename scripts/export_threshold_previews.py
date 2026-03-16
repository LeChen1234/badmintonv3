import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path

import cv2


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    if q <= 0:
        return min(values)
    if q >= 100:
        return max(values)
    arr = sorted(values)
    pos = (len(arr) - 1) * (q / 100.0)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return arr[lo]
    w = pos - lo
    return arr[lo] * (1 - w) + arr[hi] * w


def parse_percentiles(text: str) -> list[int]:
    vals = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        v = int(part)
        if 0 <= v <= 100:
            vals.append(v)
    vals = sorted(set(vals))
    if not vals:
        raise ValueError("No valid percentiles found")
    return vals


def load_motion_csv(csv_path: Path) -> list[dict]:
    rows = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                frame_index = int(row.get("frame_index", "-1"))
                motion_score = float(row.get("motion_score", "0"))
            except ValueError:
                continue
            if frame_index < 0:
                continue
            rows.append({"frame_index": frame_index, "motion_score": motion_score})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export frame folders and preview videos for multiple percentile thresholds"
    )
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
        "--percentiles",
        default="25,30,35,40,45,50,55,60,65,70,75,80,85,90,95",
        help="Comma-separated percentile list, e.g. 25,50,75,90",
    )
    parser.add_argument(
        "--output-root",
        default="data/exports/threshold_previews",
        help="Output root directory",
    )
    parser.add_argument(
        "--preview-fps",
        type=float,
        default=12.0,
        help="FPS for preview videos",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv)
    video_path = Path(args.video)
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    rows = load_motion_csv(csv_path)
    if not rows:
        raise RuntimeError("No valid rows in motion CSV")

    scores = [r["motion_score"] for r in rows]
    frame_score = {r["frame_index"]: r["motion_score"] for r in rows}
    percentiles = parse_percentiles(args.percentiles)

    threshold_info = []
    for p in percentiles:
        th = percentile(scores, p)
        selected = sorted(r["frame_index"] for r in rows if r["motion_score"] >= th)
        tag = f"P{p:02d}_ge_{th:.2f}".replace(".", "_")
        frames_dir = output_root / f"{tag}_frames"
        video_file = output_root / f"{tag}.mp4"
        frames_dir.mkdir(parents=True, exist_ok=True)
        threshold_info.append(
            {
                "p": p,
                "threshold": th,
                "selected": selected,
                "selected_set": set(selected),
                "tag": tag,
                "frames_dir": frames_dir,
                "video_file": video_file,
                "writer": None,
                "written": 0,
            }
        )

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")

    for info in threshold_info:
        info["writer"] = cv2.VideoWriter(
            str(info["video_file"]), fourcc, args.preview_fps, (width, height)
        )

    targets_by_frame = defaultdict(list)
    for i, info in enumerate(threshold_info):
        for idx in info["selected"]:
            targets_by_frame[idx].append(i)

    current_idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break

        target_list = targets_by_frame.get(current_idx)
        if target_list:
            for ti in target_list:
                info = threshold_info[ti]
                img_path = info["frames_dir"] / f"frame_{current_idx:08d}.jpg"
                cv2.imwrite(str(img_path), frame)

                preview = frame.copy()
                score = frame_score.get(current_idx, 0.0)
                text1 = f"{info['tag']}"
                text2 = f"frame={current_idx} score={score:.2f}"
                cv2.putText(
                    preview,
                    text1,
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.9,
                    (0, 255, 255),
                    2,
                    cv2.LINE_AA,
                )
                cv2.putText(
                    preview,
                    text2,
                    (20, 78),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (255, 255, 255),
                    2,
                    cv2.LINE_AA,
                )
                info["writer"].write(preview)
                info["written"] += 1

        current_idx += 1

    cap.release()
    for info in threshold_info:
        info["writer"].release()

    summary_csv = output_root / "threshold_summary.csv"
    with summary_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "percentile",
                "threshold",
                "selected_frames",
                "exported_frames",
                "frames_dir",
                "video_file",
            ],
        )
        writer.writeheader()
        for info in threshold_info:
            writer.writerow(
                {
                    "percentile": info["p"],
                    "threshold": f"{info['threshold']:.6f}",
                    "selected_frames": len(info["selected"]),
                    "exported_frames": info["written"],
                    "frames_dir": str(info["frames_dir"]),
                    "video_file": str(info["video_file"]),
                }
            )

    print(f"Done. summary={summary_csv}")
    for info in threshold_info:
        print(
            f"P{info['p']:02d} threshold={info['threshold']:.2f} "
            f"selected={len(info['selected'])} exported={info['written']}"
        )


if __name__ == "__main__":
    main()
