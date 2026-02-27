"""Multi-format annotation export service.

Supports COCO keypoint, CSV, and VLM prompt formats.
"""

import json
import csv
import io
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def convert_to_coco(annotations: List[Dict]) -> Dict:
    """Convert Label Studio export to COCO keypoint format."""
    images = []
    coco_annotations = []
    categories = [{
        "id": 1,
        "name": "person",
        "supercategory": "person",
        "keypoints": [
            "head_top", "head_center", "chin", "neck",
            "chest_center", "spine_mid", "pelvis_center",
            "left_shoulder", "left_elbow", "left_wrist", "left_palm",
            "right_shoulder", "right_elbow", "right_wrist", "right_palm",
            "left_hip", "left_knee", "left_ankle", "left_toe",
            "right_hip", "right_knee", "right_ankle", "right_toe",
            "racket_grip", "racket_head",
        ],
        "skeleton": [
            [0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 6],
            [3, 7], [7, 8], [8, 9], [9, 10],
            [3, 11], [11, 12], [12, 13], [13, 14],
            [6, 15], [15, 16], [16, 17], [17, 18],
            [6, 19], [19, 20], [20, 21], [21, 22],
            [13, 23], [23, 24],
        ],
    }]

    ann_id = 1
    for idx, task in enumerate(annotations):
        img_id = idx + 1
        data = task.get("data", {})
        images.append({
            "id": img_id,
            "file_name": data.get("image", f"frame_{img_id}.jpg"),
            "width": 640,
            "height": 480,
        })

        for annotation in task.get("annotations", []):
            keypoints = [0.0] * (25 * 3)
            action_type = None
            action_phase = None
            quality = None

            for result in annotation.get("result", []):
                rtype = result.get("type")
                value = result.get("value", {})

                if rtype == "keypointlabels":
                    labels = value.get("keypointlabels", [])
                    if labels:
                        label = labels[0]
                        kp_names = categories[0]["keypoints"]
                        if label in kp_names:
                            ki = kp_names.index(label)
                            ow = result.get("original_width", 640)
                            oh = result.get("original_height", 480)
                            x = value.get("x", 0) / 100.0 * ow
                            y = value.get("y", 0) / 100.0 * oh
                            keypoints[ki * 3] = round(x, 1)
                            keypoints[ki * 3 + 1] = round(y, 1)
                            keypoints[ki * 3 + 2] = 2

                elif rtype == "choices":
                    from_name = result.get("from_name", "")
                    choices = value.get("choices", [])
                    if choices:
                        if from_name == "action_type":
                            action_type = choices[0]
                        elif from_name == "action_phase":
                            action_phase = choices[0]
                        elif from_name == "quality_rating":
                            quality = choices[0]

            coco_annotations.append({
                "id": ann_id,
                "image_id": img_id,
                "category_id": 1,
                "keypoints": keypoints,
                "num_keypoints": sum(1 for i in range(25) if keypoints[i * 3 + 2] > 0),
                "action_type": action_type,
                "action_phase": action_phase,
                "quality_rating": quality,
            })
            ann_id += 1

    return {
        "images": images,
        "annotations": coco_annotations,
        "categories": categories,
    }


def convert_to_csv(annotations: List[Dict]) -> str:
    """Convert Label Studio export to flat CSV."""
    output = io.StringIO()
    writer = csv.writer(output)

    kp_names = [
        "head_top", "head_center", "chin", "neck",
        "chest_center", "spine_mid", "pelvis_center",
        "left_shoulder", "left_elbow", "left_wrist", "left_palm",
        "right_shoulder", "right_elbow", "right_wrist", "right_palm",
        "left_hip", "left_knee", "left_ankle", "left_toe",
        "right_hip", "right_knee", "right_ankle", "right_toe",
        "racket_grip", "racket_head",
    ]

    header = ["image"]
    for name in kp_names:
        header.extend([f"{name}_x", f"{name}_y", f"{name}_v"])
    header.extend(["action_type", "action_phase", "quality_rating"])
    writer.writerow(header)

    for task in annotations:
        data = task.get("data", {})
        image = data.get("image", "")

        for annotation in task.get("annotations", []):
            row = [image]
            kp_data = {name: (0, 0, 0) for name in kp_names}
            action_type = ""
            action_phase = ""
            quality = ""

            for result in annotation.get("result", []):
                value = result.get("value", {})
                if result.get("type") == "keypointlabels":
                    labels = value.get("keypointlabels", [])
                    if labels and labels[0] in kp_data:
                        kp_data[labels[0]] = (
                            round(value.get("x", 0), 2),
                            round(value.get("y", 0), 2),
                            2,
                        )
                elif result.get("type") == "choices":
                    choices = value.get("choices", [])
                    from_name = result.get("from_name", "")
                    if choices:
                        if from_name == "action_type":
                            action_type = choices[0]
                        elif from_name == "action_phase":
                            action_phase = choices[0]
                        elif from_name == "quality_rating":
                            quality = choices[0]

            for name in kp_names:
                row.extend(kp_data[name])
            row.extend([action_type, action_phase, quality])
            writer.writerow(row)

    return output.getvalue()


def convert_to_vlm(annotations: List[Dict]) -> List[Dict]:
    """Convert annotations to VLM prompt format for training vision-language models."""
    records = []
    for task in annotations:
        data = task.get("data", {})
        image = data.get("image", "")

        for annotation in task.get("annotations", []):
            keypoints = {}
            action_type = None
            action_phase = None
            quality = None

            for result in annotation.get("result", []):
                value = result.get("value", {})
                if result.get("type") == "keypointlabels":
                    labels = value.get("keypointlabels", [])
                    if labels:
                        keypoints[labels[0]] = {
                            "x": round(value.get("x", 0), 2),
                            "y": round(value.get("y", 0), 2),
                        }
                elif result.get("type") == "choices":
                    choices = value.get("choices", [])
                    from_name = result.get("from_name", "")
                    if choices:
                        if from_name == "action_type":
                            action_type = choices[0]
                        elif from_name == "action_phase":
                            action_phase = choices[0]
                        elif from_name == "quality_rating":
                            quality = choices[0]

            prompt = f"分析这张羽毛球训练图片中运动员的动作。"
            response = (
                f"运动员正在执行 {action_type or '未知'} 动作，"
                f"处于 {action_phase or '未知'} 阶段，"
                f"动作质量评级为 {quality or '未知'}。"
                f"检测到 {len(keypoints)} 个关键点。"
            )

            records.append({
                "image": image,
                "prompt": prompt,
                "response": response,
                "keypoints": keypoints,
                "action_type": action_type,
                "action_phase": action_phase,
                "quality_rating": quality,
            })

    return records
