"""ML Backend scheduling service."""

import logging
from typing import Dict, List, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def trigger_prediction(
    project_id: int, task_ids: Optional[List[int]] = None
) -> Dict:
    """Trigger ML backend predictions via Label Studio API."""
    from app.services.label_studio_client import ls_client

    try:
        result = await ls_client.trigger_ml_predictions(project_id, task_ids)
        return {"status": "triggered", "detail": result}
    except httpx.HTTPError as e:
        logger.warning("ML prediction trigger failed: %s", e)
        return {"status": "error", "detail": str(e)}


async def get_ml_backend_health() -> Dict:
    """Check ML backend health."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{settings.ML_BACKEND_HOST}/health")
            return {"status": "healthy", "code": resp.status_code}
    except httpx.HTTPError:
        return {"status": "unhealthy"}
