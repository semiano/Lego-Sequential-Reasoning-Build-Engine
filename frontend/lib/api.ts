import type { CurrentModel, TimelineResponse, Workspace, WorkspaceDetail } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    cache: "no-store"
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }

  return (await response.json()) as T;
}

async function requestForm<T>(path: string, formData: FormData): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    body: formData,
    cache: "no-store"
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export const api = {
  base: API_BASE,
  listWorkspaces: () => request<Workspace[]>("/api/workspaces"),
  createWorkspace: (name: string) => request<Workspace>("/api/workspaces", { method: "POST", body: JSON.stringify({ name }) }),
  deleteWorkspace: (id: string) => request<{ id: string; deleted: boolean }>(`/api/workspaces/${id}`, { method: "DELETE" }),
  workspaceDetail: (id: string) => request<WorkspaceDetail>(`/api/workspaces/${id}`),
  timeline: (id: string) => request<TimelineResponse>(`/api/workspaces/${id}/timeline`),
  currentModel: (id: string) => request<CurrentModel>(`/api/workspaces/${id}/current`),
  append: (id: string, ldraw_lines: string[], message?: string) =>
    request(`/api/workspaces/${id}/append`, { method: "POST", body: JSON.stringify({ ldraw_lines, message }) }),
  checkpoint: (id: string, message?: string) =>
    request(`/api/workspaces/${id}/checkpoint`, { method: "POST", body: JSON.stringify({ message }) }),
  render: (
    id: string,
    payload: { views: string[]; turntable_frames: number; resolution: { w: number; h: number }; message?: string }
  ) => request(`/api/workspaces/${id}/render`, { method: "POST", body: JSON.stringify(payload) }),
  startAiRun: (
    id: string,
    payload: {
      conceptImage: File;
      runName: string;
      presetPath: string;
      maxSteps: number;
      beamWidth: number;
      candidatesPerStep: number;
      scoreThreshold: number;
      controlPlaneUrl: string;
    }
  ) => {
    const formData = new FormData();
    formData.append("concept_image", payload.conceptImage);
    formData.append("run_name", payload.runName);
    formData.append("preset_path", payload.presetPath);
    formData.append("max_steps", String(payload.maxSteps));
    formData.append("beam_width", String(payload.beamWidth));
    formData.append("candidates_per_step", String(payload.candidatesPerStep));
    formData.append("score_threshold", String(payload.scoreThreshold));
    formData.append("control_plane_url", payload.controlPlaneUrl);
    return requestForm<{
      workspace_id: string;
      command: string[];
      concept_image_path: string;
      preset_path: string;
      pid: number;
      log_path: string;
    }>(`/api/workspaces/${id}/ai/run`, formData);
  },
  aiStatus: (id: string, tail = 250) =>
    request<{
      workspace_id: string;
      running: boolean;
      pid: number | null;
      started_at: string | null;
      concept_image_path: string | null;
      preset_path: string | null;
      log_path: string | null;
      log_lines: string[];
    }>(`/api/workspaces/${id}/ai/status?tail=${tail}`),
  artifactUrl: (id: string, relPath: string) =>
    `${API_BASE}/api/workspaces/${id}/artifacts/${relPath.split("/").map(encodeURIComponent).join("/")}`
};
