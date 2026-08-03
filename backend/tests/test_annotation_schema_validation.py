import pytest
from pydantic import ValidationError

from app.schemas.annotation import ContactAnnotation, FrameAnnotationCreate


def test_keypoints_must_stay_inside_normalized_image_bounds():
    with pytest.raises(ValidationError):
        FrameAnnotationCreate(
            task_batch_id=1,
            frame_index=1,
            keypoints=[{"name": "left_wrist", "x": 120, "y": 50, "visibility": 2}],
        )


def test_contact_vocabulary_and_uv_are_bounded():
    with pytest.raises(ValidationError):
        ContactAnnotation(contact_zone="invented_zone")
    with pytest.raises(ValidationError):
        ContactAnnotation(contact_uv={"u": 1.2, "v": 0.5})
