"""Wrapper around Label Studio API for project/task management."""

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class LabelStudioClient:
    def __init__(self):
        self.base_url = settings.LABEL_STUDIO_HOST.rstrip("/")
        self.headers = {
            "Authorization": f"Token {settings.LABEL_STUDIO_API_KEY}",
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        return f"{self.base_url}/api{path}"

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.request(
                method, self._url(path), headers=self.headers, **kwargs
            )
            resp.raise_for_status()
            if resp.status_code == 204:
                return None
            return resp.json()

    async def create_project(
        self, title: str, description: str = "", label_config: str = ""
    ) -> Dict:
        return await self._request(
            "POST",
            "/projects",
            json={
                "title": title,
                "description": description,
                "label_config": label_config,
            },
        )

    async def get_project(self, project_id: int) -> Dict:
        return await self._request("GET", f"/projects/{project_id}")

    async def list_projects(self) -> List[Dict]:
        return await self._request("GET", "/projects")

    async def delete_project(self, project_id: int) -> None:
        await self._request("DELETE", f"/projects/{project_id}")

    async def import_tasks(self, project_id: int, tasks: List[Dict]) -> Dict:
        return await self._request(
            "POST", f"/projects/{project_id}/import", json=tasks
        )

    async def get_tasks(
        self, project_id: int, page: int = 1, page_size: int = 100
    ) -> Dict:
        return await self._request(
            "GET",
            f"/projects/{project_id}/tasks",
            params={"page": page, "page_size": page_size},
        )

    async def get_task(self, task_id: int) -> Dict:
        return await self._request("GET", f"/tasks/{task_id}")

    async def get_annotations(self, task_id: int) -> List[Dict]:
        return await self._request("GET", f"/tasks/{task_id}/annotations")

    async def create_annotation(self, task_id: int, result: List[Dict]) -> Dict:
        return await self._request(
            "POST",
            f"/tasks/{task_id}/annotations",
            json={"result": result},
        )

    async def export_project(
        self, project_id: int, export_type: str = "JSON"
    ) -> Any:
        return await self._request(
            "GET",
            f"/projects/{project_id}/export",
            params={"exportType": export_type},
        )

    async def trigger_ml_predictions(
        self, project_id: int, task_ids: Optional[List[int]] = None
    ) -> Dict:
        """Request predictions from ML backend for tasks."""
        payload: Dict[str, Any] = {}
        if task_ids:
            payload["task_ids"] = task_ids
        return await self._request(
            "POST",
            f"/projects/{project_id}/predict",
            json=payload,
        )


ls_client = LabelStudioClient()
