from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx


class ControlPlaneClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def create_workspace(self, name: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(f"{self.base_url}/api/workspaces", json={"name": name})
            response.raise_for_status()
            return response.json()

    async def append_lines(self, workspace_id: str, ldraw_lines: list[str], message: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                f"{self.base_url}/api/workspaces/{workspace_id}/append",
                json={"ldraw_lines": ldraw_lines, "message": message},
            )
            response.raise_for_status()
            return response.json()

    async def checkpoint(self, workspace_id: str, message: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                f"{self.base_url}/api/workspaces/{workspace_id}/checkpoint",
                json={"message": message},
            )
            response.raise_for_status()
            return response.json()

    async def render(
        self,
        workspace_id: str,
        views: list[str],
        turntable_frames: int,
        resolution: dict[str, int],
        message: str,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(
                f"{self.base_url}/api/workspaces/{workspace_id}/render",
                json={
                    "views": views,
                    "turntable_frames": turntable_frames,
                    "resolution": resolution,
                    "message": message,
                },
            )
            response.raise_for_status()
            return response.json()

    async def get_timeline(self, workspace_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(f"{self.base_url}/api/workspaces/{workspace_id}/timeline")
            response.raise_for_status()
            return response.json()

    async def get_current_model_text(self, workspace_id: str) -> str:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(f"{self.base_url}/api/workspaces/{workspace_id}/current")
            response.raise_for_status()
            payload = response.json()
            return str(payload.get("content", ""))

    async def get_artifact_text(self, workspace_id: str, rel_path: str) -> str:
        encoded = "/".join(quote(part) for part in rel_path.split("/"))
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.get(f"{self.base_url}/api/workspaces/{workspace_id}/artifacts/{encoded}")
            response.raise_for_status()
            return response.text

    async def render_temp(
        self,
        workspace_id: str,
        extra_lines: list[str],
        views: list[str],
        turntable_frames: int,
        resolution: dict[str, int],
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(
                f"{self.base_url}/api/workspaces/{workspace_id}/render_temp",
                json={
                    "extra_lines": extra_lines,
                    "views": views,
                    "turntable_frames": turntable_frames,
                    "resolution": resolution,
                },
            )
            response.raise_for_status()
            return response.json()
