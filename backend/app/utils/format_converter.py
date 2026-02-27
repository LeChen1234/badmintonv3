"""Annotation format converter utilities."""

from typing import Dict, List, Tuple


def ls_keypoints_to_dict(
    results: List[Dict],
) -> Dict[str, Tuple[float, float]]:
    """Convert Label Studio keypoint results to {name: (x, y)} dict."""
    keypoints = {}
    for r in results:
        if r.get("type") != "keypointlabels":
            continue
        value = r.get("value", {})
        labels = value.get("keypointlabels", [])
        if labels:
            keypoints[labels[0]] = (value.get("x", 0.0), value.get("y", 0.0))
    return keypoints


def dict_to_ls_keypoints(
    keypoints: Dict[str, Tuple[float, float]],
    original_width: int = 640,
    original_height: int = 480,
) -> List[Dict]:
    """Convert {name: (x, y)} dict back to Label Studio keypoint results."""
    results = []
    for name, (x, y) in keypoints.items():
        results.append({
            "from_name": "keypoints",
            "to_name": "image",
            "type": "keypointlabels",
            "original_width": original_width,
            "original_height": original_height,
            "image_rotation": 0,
            "value": {
                "x": round(x, 2),
                "y": round(y, 2),
                "width": 1.0,
                "keypointlabels": [name],
            },
        })
    return results
