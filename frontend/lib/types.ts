export type Workspace = {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  current_step: number;
  desired_image_rel_path?: string | null;
};

export type Artifact = {
  id: string;
  artifact_type: "ldraw" | "render" | "turntable_frame" | "json";
  rel_path: string;
  created_at: string;
};

export type Step = {
  id: string;
  step_index: number;
  kind: "append" | "render" | "checkpoint";
  message?: string | null;
  created_at: string;
  artifacts: Artifact[];
};

export type TimelineResponse = {
  workspace: Workspace;
  steps: Step[];
};

export type WorkspaceDetail = {
  workspace: Workspace;
  latest_artifacts: Artifact[];
};

export type CurrentModel = {
  rel_path: string;
  content: string;
};
