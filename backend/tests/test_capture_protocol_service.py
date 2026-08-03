import unittest

from app.services.capture_protocol_service import (
    capture_protocol_advisory,
    normalize_capture_metadata,
    validate_capture_protocol,
)


class CaptureProtocolServiceTests(unittest.TestCase):
    def test_competition_requires_view_and_exact_player_count(self):
        errors = validate_capture_protocol(
            capture_metadata={
                "capture_mode": "competition",
                "annotation_goal": "action_sequence",
                "source_reference": "https://example.test/match/1",
            },
            match_format="singles",
            match_name="公开赛",
            match_date="2026-07-29",
            player_count=1,
        )
        self.assertIn("请选择拍摄视角", errors)
        self.assertIn("单打比赛必须填写 2 名运动员", errors)

    def test_controlled_training_allows_single_subject(self):
        errors = validate_capture_protocol(
            capture_metadata={
                "capture_mode": "controlled_training",
                "annotation_goal": "technique_quality",
                "camera_view": "left",
                "target_action": "正手杀球",
                "marker_protocol": "video_landmarks",
                "recording_design": "prescribed_standard",
                "recording_fps": 60,
            },
            match_format=None,
            match_name="杀球采集第 1 轮",
            match_date="2026-07-29",
            player_count=1,
        )
        self.assertEqual(errors, [])

    def test_quality_track_requires_target_action(self):
        errors = validate_capture_protocol(
            capture_metadata={
                "capture_mode": "controlled_training",
                "annotation_goal": "technique_quality",
                "camera_view": "front",
                "recording_design": "natural_training",
                "recording_fps": 60,
            },
            match_format=None,
            match_name="训练采集",
            match_date="2026-07-29",
            player_count=1,
        )
        self.assertIn("精细动作质量轨必须填写目标动作", errors)

    def test_physical_markers_are_rejected_for_competition(self):
        errors = validate_capture_protocol(
            capture_metadata={
                "capture_mode": "competition",
                "annotation_goal": "action_sequence",
                "camera_view": "rear",
                "marker_protocol": "physical_markers",
                "source_reference": "MATCH-001",
            },
            match_format="singles",
            match_name="比赛",
            match_date="2026-07-29",
            player_count=2,
        )
        self.assertIn("反光/实体标记点方案仅适用于受控抵近训练采集", errors)

    def test_legacy_match_defaults_to_sequence_protocol(self):
        normalized = normalize_capture_metadata(None, match_format="singles")
        advisory = capture_protocol_advisory(None, match_format="singles")
        self.assertEqual(normalized["capture_mode"], "competition")
        self.assertEqual(normalized["annotation_goal"], "action_sequence")
        self.assertFalse(advisory["fine_quality_enabled"])

    def test_online_match_requires_source_traceability(self):
        errors = validate_capture_protocol(
            capture_metadata={
                "capture_mode": "competition",
                "annotation_goal": "action_sequence",
                "camera_view": "rear",
            },
            match_format="singles",
            match_name="公开赛",
            match_date="2026-08-03",
            player_count=2,
        )
        self.assertIn("网络比赛视频必须填写来源链接或来源编号", errors)

    def test_phone_training_requires_design_and_fps(self):
        errors = validate_capture_protocol(
            capture_metadata={
                "capture_mode": "controlled_training",
                "annotation_goal": "technique_quality",
                "camera_view": "left",
                "target_action": "正手杀球",
            },
            match_format=None,
            match_name="训练采集",
            match_date="2026-08-03",
            player_count=1,
        )
        self.assertIn("手机训练视频必须选择自然训练或指定动作采集方式", errors)
        self.assertIn("手机训练视频必须填写实际拍摄帧率", errors)


if __name__ == "__main__":
    unittest.main()
