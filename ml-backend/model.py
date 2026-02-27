"""Label Studio ML Backend for badminton pose estimation and action recognition.

Follows the label-studio-ml-backend SDK pattern.
"""

import logging
import os

from label_studio_ml.model import LabelStudioMLBackend
from label_studio_ml.utils import get_single_tag_keys

from pose_estimator import estimate_keypoints
from action_recognizer import recognize_action

logger = logging.getLogger(__name__)


class BadmintonMLBackend(LabelStudioMLBackend):
    """ML Backend combining pose estimation and action recognition."""

    def setup(self):
        self.from_name_kp, self.to_name_kp, self.value_kp = (None, None, None)
        self.from_name_act = None

    def predict(self, tasks, **kwargs):
        predictions = []
        for task in tasks:
            result = []

            keypoint_results = estimate_keypoints()
            for kp in keypoint_results:
                kp["from_name"] = "keypoints"
                kp["to_name"] = "image"
                kp["type"] = "keypointlabels"
                result.append(kp)

            action_results = recognize_action()
            result.extend(action_results)

            predictions.append({
                "result": result,
                "score": round(0.5 + 0.3 * __import__("random").random(), 2),
                "model_version": "mock-v1.0",
            })
        return predictions


if __name__ == "__main__":
    from label_studio_ml.api import init_app

    app = init_app(model_class=BadmintonMLBackend)

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 9090))
    app.run(host=host, port=port, debug=False)
