"""Runtime-loaded annotation taxonomy with structural validation."""

import json
from pathlib import Path
from typing import Any, Dict

from app.config import settings


def load_annotation_taxonomy() -> Dict[str, Any]:
    path = Path(settings.ANNOTATION_TAXONOMY_PATH).resolve()
    if not path.is_file():
        raise RuntimeError(f"Annotation taxonomy file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    for section in ("actions", "phases", "qualities"):
        values = data.get(section)
        if not isinstance(values, list) or not values:
            raise RuntimeError(f"Taxonomy section '{section}' must be a non-empty list")
        identifiers = []
        for item in values:
            if not isinstance(item, dict) or not str(item.get("value", "")).strip() or not str(item.get("label", "")).strip():
                raise RuntimeError(f"Invalid taxonomy item in '{section}'")
            identifiers.append(item["value"])
        if len(identifiers) != len(set(identifiers)):
            raise RuntimeError(f"Duplicate values in taxonomy section '{section}'")
    return data
