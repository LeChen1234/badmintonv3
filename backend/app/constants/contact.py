"""Contact-centric annotation vocabulary (monocular training video).

Geometry is defined in the image / face-parameter chart, not SE(3) world coords.
"""

from typing import Dict, List, Optional, Tuple

# Discrete contact zone on the projected racket face (parameter domain F).
CONTACT_ZONES: Tuple[str, ...] = (
    "sweet",       # central sweet-spot band
    "top",         # toward tip of head
    "bottom",      # toward throat / near handle
    "head_side",   # lateral (toe/heel of face in image)
    "throat",      # near shaft–head junction
    "unknown",
)

CONTACT_ZONE_LABELS: Dict[str, str] = {
    "sweet": "甜区",
    "top": "拍头远端",
    "bottom": "近柄侧",
    "head_side": "拍面侧缘",
    "throat": "拍颈附近",
    "unknown": "未知/不可见",
}

# Ordinal face attitude at contact (proxy for open/closed face; not full SO(3)).
FACE_ATTITUDES: Tuple[str, ...] = ("open", "square", "closed", "unknown")

FACE_ATTITUDE_LABELS: Dict[str, str] = {
    "open": "开放拍面",
    "square": "正面/中性",
    "closed": "关闭拍面",
    "unknown": "未知",
}

SUPPORT_FEET: Tuple[str, ...] = ("left", "right", "both", "unknown")

SUPPORT_FOOT_LABELS: Dict[str, str] = {
    "left": "左脚支撑",
    "right": "右脚支撑",
    "both": "双脚",
    "unknown": "未知",
}

# Sparse face corners for contact frames only (orthogonal to RacketVision dense pose).
FACE_CORNER_NAMES: Tuple[str, ...] = (
    "face_top",
    "face_bottom",
    "face_left",
    "face_right",
)

FACE_CORNER_LABELS: Dict[str, str] = {
    "face_top": "拍面上沿",
    "face_bottom": "拍面下沿",
    "face_left": "拍面左缘",
    "face_right": "拍面右缘",
}

# Technical error attributes attachable at contact (multi-label).
ERROR_ATTRIBUTES: Tuple[str, ...] = (
    "off_center_contact",
    "open_face",
    "closed_face",
    "late_timing",
    "early_timing",
    "unstable_base",
    "poor_grip",
    "other",
)

ERROR_ATTRIBUTE_LABELS: Dict[str, str] = {
    "off_center_contact": "击球点偏离甜区",
    "open_face": "拍面过于开放",
    "closed_face": "拍面过于关闭",
    "late_timing": "击球偏晚",
    "early_timing": "击球偏早",
    "unstable_base": "支撑不稳",
    "poor_grip": "握拍问题",
    "other": "其他",
}

# Research-aligned ordinal quality (preferred for contact events).
CONTACT_QUALITY_RATINGS: Tuple[str, ...] = (
    "standard",
    "acceptable",
    "needs_correction",
)

CONTACT_QUALITY_LABELS: Dict[str, str] = {
    "standard": "标准",
    "acceptable": "可接受",
    "needs_correction": "需纠正",
}


def empty_contact_payload() -> dict:
    """Default contact JSON stored on FrameAnnotation.contact."""
    return {
        "tolerance_flag": False,
        "shuttle": {"x": None, "y": None, "visibility": 0},
        "face_corners": [
            {"name": n, "x": 0.0, "y": 0.0, "visibility": 0} for n in FACE_CORNER_NAMES
        ],
        "contact_point": {"x": None, "y": None, "visibility": 0},
        "contact_uv": {"u": None, "v": None},
        "contact_zone": None,
        "face_attitude": None,
        "support_foot": None,
        "error_attributes": [],
    }


def bilinear_uv(
    face_corners: List[dict],
    px: float,
    py: float,
) -> Optional[Tuple[float, float]]:
    """Approximate (u,v) in [0,1]^2 from image point vs face quad.

    Chart: top-left≈(0,0), top-right≈(1,0), bottom-left≈(0,1), bottom-right≈(1,1)
    using corners ordered as face_top, face_bottom, face_left, face_right approximated
    via bilinear solve on a reconstructed quad:
      TL = average(top, left), TR = average(top, right), ...
    Falls back to None if corners incomplete.
    """
    by_name = {c.get("name"): c for c in face_corners if c.get("visibility", 0) > 0}
    need = ("face_top", "face_bottom", "face_left", "face_right")
    if not all(n in by_name for n in need):
        return None

    top, bottom, left, right = (by_name[n] for n in need)
    tl = ((top["x"] + left["x"]) / 2.0, (top["y"] + left["y"]) / 2.0)
    tr = ((top["x"] + right["x"]) / 2.0, (top["y"] + right["y"]) / 2.0)
    bl = ((bottom["x"] + left["x"]) / 2.0, (bottom["y"] + left["y"]) / 2.0)
    br = ((bottom["x"] + right["x"]) / 2.0, (bottom["y"] + right["y"]) / 2.0)

    # Inverse bilinear (Hitachi / Hormann style iterative) — 8 steps enough for UI.
    u, v = 0.5, 0.5
    for _ in range(8):
        x = (
            (1 - u) * (1 - v) * tl[0]
            + u * (1 - v) * tr[0]
            + (1 - u) * v * bl[0]
            + u * v * br[0]
        )
        y = (
            (1 - u) * (1 - v) * tl[1]
            + u * (1 - v) * tr[1]
            + (1 - u) * v * bl[1]
            + u * v * br[1]
        )
        # Jacobians
        dxdu = (1 - v) * (tr[0] - tl[0]) + v * (br[0] - bl[0])
        dxdv = (1 - u) * (bl[0] - tl[0]) + u * (br[0] - tr[0])
        dydu = (1 - v) * (tr[1] - tl[1]) + v * (br[1] - bl[1])
        dydv = (1 - u) * (bl[1] - tl[1]) + u * (br[1] - tr[1])
        det = dxdu * dydv - dxdv * dydu
        if abs(det) < 1e-8:
            break
        rx, ry = x - px, y - py
        u -= (dydv * rx - dxdv * ry) / det
        v -= (-dydu * rx + dxdu * ry) / det
        u = max(0.0, min(1.0, u))
        v = max(0.0, min(1.0, v))
    return round(u, 4), round(v, 4)
