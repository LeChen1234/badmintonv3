import argparse
import csv
import json
import math
from itertools import permutations
from pathlib import Path
from statistics import mean, median


def geometry_of_person(person: dict) -> tuple[float, float, float] | None:
    skeleton = person.get("skeleton", {})
    if not skeleton:
        return None
    xs = []
    ys = []
    for pt in skeleton.values():
        x = pt.get("x")
        y = pt.get("y")
        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            xs.append(float(x))
            ys.append(float(y))
    if not xs:
        return None
    scale = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
    if scale <= 1e-9:
        return None
    return sum(xs) / len(xs), sum(ys) / len(ys), scale


def match_people(previous: list[dict], current: list[dict]) -> list[tuple[dict, dict]]:
    """Minimum-cost one-to-one matching based on scale-normalized centroids."""
    if not previous or not current:
        return []
    if len(previous) <= len(current):
        left, right, swapped = previous, current, False
    else:
        left, right, swapped = current, previous, True

    def cost(a: dict, b: dict) -> float:
        ga, gb = geometry_of_person(a), geometry_of_person(b)
        if ga is None or gb is None:
            return float("inf")
        return math.hypot(ga[0] - gb[0], ga[1] - gb[1]) / ((ga[2] + gb[2]) / 2)

    if len(right) > 6:
        candidates = sorted(
            (cost(a, b), i, j)
            for i, a in enumerate(left)
            for j, b in enumerate(right)
        )
        used_left, used_right, pairs = set(), set(), []
        for candidate_cost, i, j in candidates:
            if not math.isfinite(candidate_cost):
                continue
            if i not in used_left and j not in used_right:
                pairs.append((left[i], right[j]))
                used_left.add(i)
                used_right.add(j)
        return [(b, a) for a, b in pairs] if swapped else pairs

    best = None
    for candidate in permutations(range(len(right)), len(left)):
        candidate_cost = sum(cost(left[i], right[j]) for i, j in enumerate(candidate))
        if math.isfinite(candidate_cost) and (best is None or candidate_cost < best[0]):
            best = candidate_cost, candidate
    if best is None:
        return []
    pairs = [(left[i], right[j]) for i, j in enumerate(best[1])]
    return [(b, a) for a, b in pairs] if swapped else pairs


def distance_sum_between_people(prev_person: dict, curr_person: dict) -> tuple[float, int]:
    prev_skeleton = prev_person.get("skeleton", {})
    curr_skeleton = curr_person.get("skeleton", {})
    if not prev_skeleton or not curr_skeleton:
        return 0.0, 0

    prev_geometry = geometry_of_person(prev_person)
    curr_geometry = geometry_of_person(curr_person)
    if prev_geometry is None or curr_geometry is None:
        return 0.0, 0
    scale = (prev_geometry[2] + curr_geometry[2]) / 2
    shared_keys = set(prev_skeleton.keys()) & set(curr_skeleton.keys())
    total = 0.0
    used = 0
    for key in shared_keys:
        p0 = prev_skeleton.get(key, {})
        p1 = curr_skeleton.get(key, {})
        x0, y0 = p0.get("x"), p0.get("y")
        x1, y1 = p1.get("x"), p1.get("y")
        if not all(isinstance(v, (int, float)) for v in (x0, y0, x1, y1)):
            continue
        total += math.hypot(float(x1) - float(x0), float(y1) - float(y0)) / scale
        used += 1
    return total, used


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    if q <= 0:
        return min(values)
    if q >= 100:
        return max(values)
    sorted_vals = sorted(values)
    pos = (len(sorted_vals) - 1) * (q / 100.0)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_vals[lo]
    w = pos - lo
    return sorted_vals[lo] * (1 - w) + sorted_vals[hi] * w


def analyze_motion(
    json_path: Path,
    min_people: int,
    min_shared_joints: int,
) -> list[dict]:
    with json_path.open("r", encoding="utf-8") as f:
        frames = json.load(f)

    results = []
    prev_valid_frame = None

    for frame in frames:
        frame_index = frame.get("frame_index")
        timestamp_sec = frame.get("timestamp_sec")
        people = frame.get("people", [])

        if not isinstance(people, list) or len(people) < min_people:
            # Avoid mixing different temporal gaps into one score distribution.
            prev_valid_frame = None
            continue

        if prev_valid_frame is None:
            prev_valid_frame = {
                "frame_index": frame_index,
                "timestamp_sec": timestamp_sec,
                "people": people,
            }
            continue

        prev_people = prev_valid_frame["people"]
        curr_people = people

        motion_score = 0.0
        shared_joint_count = 0

        for prev_person, curr_person in match_people(prev_people, curr_people):
            d, used = distance_sum_between_people(prev_person, curr_person)
            motion_score += d
            shared_joint_count += used

        if shared_joint_count >= min_shared_joints:
            results.append(
                {
                    "frame_index": frame_index,
                    "timestamp_sec": timestamp_sec,
                    "prev_frame_index": prev_valid_frame["frame_index"],
                    "motion_score": round(motion_score / shared_joint_count, 6),
                    "shared_joint_count": shared_joint_count,
                    "people_count": len(people),
                }
            )

        prev_valid_frame = {
            "frame_index": frame_index,
            "timestamp_sec": timestamp_sec,
            "people": people,
        }

    return results


def save_csv(rows: list[dict], csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "frame_index",
                "timestamp_sec",
                "prev_frame_index",
                "motion_score",
                "shared_joint_count",
                "people_count",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def save_plot(rows: list[dict], plot_path: Path) -> bool:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return False

    plot_path.parent.mkdir(parents=True, exist_ok=True)
    x = [r["frame_index"] for r in rows]
    y = [r["motion_score"] for r in rows]

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(x, y, linewidth=1.2)
    ax.set_title("Frame-to-frame motion score on valid frames")
    ax.set_xlabel("Frame index")
    ax.set_ylabel("Motion score (mean body-scale-normalized joint displacement)")
    ax.grid(True, linestyle="--", alpha=0.35)

    p70 = percentile(y, 70)
    p80 = percentile(y, 80)
    p90 = percentile(y, 90)
    for val, name, color in [
        (p70, "P70", "#d97706"),
        (p80, "P80", "#2563eb"),
        (p90, "P90", "#dc2626"),
    ]:
        ax.axhline(y=val, linestyle="--", linewidth=1.0, color=color, label=f"{name}={val:.2f}")

    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze frame-to-frame motion score from skeleton JSON."
    )
    parser.add_argument(
        "--input",
        default="badminton_skeleton_data.json",
        help="Path to input skeleton JSON",
    )
    parser.add_argument(
        "--output-csv",
        default="data/exports/frame_motion_scores.csv",
        help="Path to output CSV",
    )
    parser.add_argument(
        "--output-plot",
        default="data/exports/frame_motion_scores.png",
        help="Path to output line chart PNG",
    )
    parser.add_argument(
        "--min-people",
        type=int,
        default=2,
        help="Only frames with at least this number of people are considered valid",
    )
    parser.add_argument(
        "--min-shared-joints",
        type=int,
        default=8,
        help="Minimal shared joints between adjacent valid frames",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_csv = Path(args.output_csv)
    output_plot = Path(args.output_plot)

    if not input_path.exists():
        raise FileNotFoundError(f"Input JSON not found: {input_path}")

    rows = analyze_motion(
        json_path=input_path,
        min_people=args.min_people,
        min_shared_joints=args.min_shared_joints,
    )

    if not rows:
        print("No valid adjacent-frame motion records found under current filters.")
        return

    save_csv(rows, output_csv)
    plot_ok = save_plot(rows, output_plot)

    scores = [r["motion_score"] for r in rows]
    p70 = percentile(scores, 70)
    p80 = percentile(scores, 80)
    p90 = percentile(scores, 90)
    p95 = percentile(scores, 95)

    print(f"Valid adjacent-frame records: {len(rows)}")
    print(f"mean={mean(scores):.3f}, median={median(scores):.3f}")
    print(f"p70={p70:.3f}, p80={p80:.3f}, p90={p90:.3f}, p95={p95:.3f}")
    print(f"CSV saved to: {output_csv}")
    if plot_ok:
        print(f"Plot saved to: {output_plot}")
    else:
        print("matplotlib is not installed, plot generation skipped.")


if __name__ == "__main__":
    main()
