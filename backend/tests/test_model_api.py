from pathlib import Path


def _create_workspace(client):
    response = client.post("/api/workspaces", json={"name": "test-ws"})
    assert response.status_code == 200
    return response.json()


def test_create_workspace(client):
    workspace = _create_workspace(client)
    assert workspace["id"]
    assert workspace["name"] == "test-ws"
    assert workspace["current_step"] == 0


def test_append_writes_files_and_db_rows(client):
    workspace = _create_workspace(client)
    wid = workspace["id"]

    append_resp = client.post(
        f"/api/workspaces/{wid}/append",
        json={
            "ldraw_lines": ["1 16 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat"],
            "message": "added brick",
        },
    )
    assert append_resp.status_code == 200

    timeline = client.get(f"/api/workspaces/{wid}/timeline")
    assert timeline.status_code == 200
    payload = timeline.json()
    assert len(payload["steps"]) == 1
    assert payload["steps"][0]["kind"] == "append"
    assert payload["steps"][0]["artifacts"]

    current = client.get(f"/api/workspaces/{wid}/current")
    assert current.status_code == 200
    assert "3001.dat" in current.json()["content"]


def test_checkpoint_writes_snapshot(client):
    workspace = _create_workspace(client)
    wid = workspace["id"]

    client.post(
        f"/api/workspaces/{wid}/append",
        json={"ldraw_lines": ["1 16 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat"], "message": "base"},
    )
    checkpoint_resp = client.post(f"/api/workspaces/{wid}/checkpoint", json={"message": "checkpoint"})
    assert checkpoint_resp.status_code == 200

    timeline = client.get(f"/api/workspaces/{wid}/timeline").json()
    assert len(timeline["steps"]) == 2
    assert timeline["steps"][1]["kind"] == "checkpoint"


def test_artifact_streaming_path_safety(client):
    workspace = _create_workspace(client)
    wid = workspace["id"]

    response = client.get(f"/api/workspaces/{wid}/artifacts/%2E%2E/%2E%2E/secret.txt")
    assert response.status_code == 400
