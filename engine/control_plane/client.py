from __future__ import annotations

from typing import Any

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
