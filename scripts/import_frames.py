"""Import video frames into Label Studio tasks.

Scans a directory for image files and creates LS tasks for each frame.
"""

import os
import sys
import argparse
import json
from pathlib import Path

import httpx

LS_HOST = os.getenv("LABEL_STUDIO_HOST", "http://localhost:8080")
LS_API_KEY = os.getenv("LABEL_STUDIO_API_KEY", "")

HEADERS = {
    "Authorization": f"Token {LS_API_KEY}",
    "Content-Type": "application/json",
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def scan_frames(directory: str) -> list[str]:
    """Find all image files in a directory, sorted by name."""
    frames = []
    for f in sorted(Path(directory).iterdir()):
        if f.suffix.lower() in IMAGE_EXTENSIONS:
            frames.append(str(f))
    return frames


def create_tasks_from_frames(
    client: httpx.Client,
    project_id: int,
    frames: list[str],
    base_url: str = "",
    batch_size: int = 50,
) -> int:
    """Import frames as tasks into a Label Studio project."""
    total_imported = 0

    for i in range(0, len(frames), batch_size):
        batch = frames[i:i + batch_size]
        tasks = []
        for frame_path in batch:
            filename = os.path.basename(frame_path)
            if base_url:
                image_url = f"{base_url}/{filename}"
            else:
                image_url = f"/data/local-files/?d={frame_path}"

            tasks.append({"data": {"image": image_url}})

        resp = client.post(
            f"{LS_HOST}/api/projects/{project_id}/import",
            headers=HEADERS,
            json=tasks,
        )
        resp.raise_for_status()
        total_imported += len(batch)
        print(f"  Imported {total_imported}/{len(frames)} frames...")

    return total_imported


def main():
    parser = argparse.ArgumentParser(description="Import video frames to Label Studio")
    parser.add_argument("--project-id", type=int, required=True, help="Label Studio project ID")
    parser.add_argument("--frames-dir", type=str, required=True, help="Directory containing frame images")
    parser.add_argument("--base-url", type=str, default="", help="Base URL for images (if served externally)")
    parser.add_argument("--batch-size", type=int, default=50, help="Import batch size")
    args = parser.parse_args()

    if not os.path.isdir(args.frames_dir):
        print(f"Error: directory not found: {args.frames_dir}")
        sys.exit(1)

    frames = scan_frames(args.frames_dir)
    if not frames:
        print(f"No image files found in {args.frames_dir}")
        sys.exit(1)

    print(f"Found {len(frames)} frames in {args.frames_dir}")
    print(f"Importing to project {args.project_id}...")

    client = httpx.Client(timeout=60)
    try:
        total = create_tasks_from_frames(
            client, args.project_id, frames,
            base_url=args.base_url, batch_size=args.batch_size,
        )
        print(f"\nDone! Imported {total} frames.")
    except httpx.HTTPStatusError as e:
        print(f"Error: {e.response.text}")
        sys.exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    main()
