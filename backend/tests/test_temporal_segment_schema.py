import pytest
from pydantic import ValidationError

from app.schemas.temporal_segment import TemporalSegmentCreate


def test_four_layer_stroke_event_is_accepted():
    event = TemporalSegmentCreate(
        task_batch_id=1,
        selected_player_id=2,
        start_frame=10,
        end_frame=20,
        action_type="smash",
        context={"incoming_height": "high", "pressure_state": "attacking"},
        execution={"arrival_state": "on_time", "error_mechanisms": []},
        outcome={"opponent_response": "forced", "rally_effect": "advantage"},
        evidence={"contact_visibility": "not_visible", "confidence": 3},
    )
    assert event.context.pressure_state == "attacking"
    assert event.evidence.contact_visibility == "not_visible"


def test_invalid_observation_is_rejected_instead_of_silently_normalized():
    with pytest.raises(ValidationError):
        TemporalSegmentCreate(
            task_batch_id=1,
            selected_player_id=2,
            start_frame=10,
            end_frame=20,
            action_type="smash",
            evidence={"contact_visibility": "probably_visible", "confidence": 8},
        )
