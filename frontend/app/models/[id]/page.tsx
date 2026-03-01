"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { ArtifactGallery } from "@/components/ArtifactGallery";
import { CommandConsole } from "@/components/CommandConsole";
import { Flipbook } from "@/components/Flipbook";
import { ThreeViewer } from "@/components/ThreeViewer";
import { Timeline } from "@/components/Timeline";
import { api } from "@/lib/api";
import type { CurrentModel, TimelineResponse } from "@/lib/types";

export default function WorkspacePage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;
  const [timeline, setTimeline] = useState<TimelineResponse | null>(null);
  const [currentModel, setCurrentModel] = useState<CurrentModel | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [aiBusy, setAiBusy] = useState(false);
  const [aiResult, setAiResult] = useState<string | null>(null);
  const [aiPid, setAiPid] = useState<number | null>(null);
  const [aiLogPath, setAiLogPath] = useState<string | null>(null);
  const [aiLogLines, setAiLogLines] = useState<string[]>([]);
  const [aiRunning, setAiRunning] = useState(false);
  const [aiStopping, setAiStopping] = useState(false);
  const [conceptImage, setConceptImage] = useState<File | null>(null);
  const [conceptPreviewUrl, setConceptPreviewUrl] = useState<string | null>(null);
  const [aiMonitoring, setAiMonitoring] = useState(false);
  const [aiStartedStepCount, setAiStartedStepCount] = useState<number | null>(null);
  const [aiLastObservedStep, setAiLastObservedStep] = useState<number>(0);
  const [runName, setRunName] = useState("workspace-run");
  const [presetPath, setPresetPath] = useState("presets/bird_sculpt.json");
  const [maxSteps, setMaxSteps] = useState(12);
  const [beamWidth, setBeamWidth] = useState(2);
  const [candidatesPerStep, setCandidatesPerStep] = useState(3);
  const [scoreThreshold, setScoreThreshold] = useState(0.84);

  const persistedConceptUrl = useMemo(() => {
    const relPath = timeline?.workspace.desired_image_rel_path;
    if (!relPath) {
      return null;
    }
    return api.artifactUrl(id, relPath);
  }, [timeline, id]);

  const effectiveConceptPreviewUrl = conceptPreviewUrl ?? persistedConceptUrl;

  const refresh = async (showLoading = true) => {
    if (showLoading) {
      setLoading(true);
    }
    try {
      const [timelineData, current] = await Promise.all([api.timeline(id), api.currentModel(id)]);
      setTimeline(timelineData);
      setCurrentModel(current);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      if (showLoading) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    if (id) {
      void refresh();
    }
  }, [id]);

  useEffect(() => {
    if (!aiMonitoring || !id) {
      return;
    }

    const timer = setInterval(async () => {
      try {
        const timelineData = await api.timeline(id);
        setTimeline(timelineData);
        const newStepCount = timelineData.steps.length;
        setAiLastObservedStep(newStepCount);
      } catch {
      }
    }, 4000);

    return () => clearInterval(timer);
  }, [aiMonitoring, id]);

  useEffect(() => {
    if (!id) {
      return;
    }

    const poll = async () => {
      try {
        const status = await api.aiStatus(id, 350);
        setAiRunning(status.running);
        setAiPid(status.pid);
        setAiLogPath(status.log_path);
        setAiLogLines(status.log_lines);
        if (status.running) {
          setAiMonitoring(true);
        }
      } catch {
      }
    };

    void poll();
    const timer = setInterval(poll, 3000);
    return () => clearInterval(timer);
  }, [id]);

  useEffect(() => {
    if (!conceptImage) {
      setConceptPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(conceptImage);
    setConceptPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [conceptImage]);

  const flipbookFramesByView = useMemo(() => {
    const byView: Record<"front" | "side" | "top" | "iso", { stepIndex: number; url: string }[]> = {
      front: [],
      side: [],
      top: [],
      iso: []
    };

    if (!timeline) {
      return byView;
    }

    for (const step of timeline.steps) {
      for (const artifact of step.artifacts) {
        if (artifact.artifact_type !== "render") {
          continue;
        }

        const name = artifact.rel_path.split("/").pop()?.toLowerCase();
        if (!name) {
          continue;
        }

        if (name === "front.png") {
          byView.front.push({ stepIndex: step.step_index, url: api.artifactUrl(id, artifact.rel_path) });
        } else if (name === "side.png") {
          byView.side.push({ stepIndex: step.step_index, url: api.artifactUrl(id, artifact.rel_path) });
        } else if (name === "top.png") {
          byView.top.push({ stepIndex: step.step_index, url: api.artifactUrl(id, artifact.rel_path) });
        } else if (name === "iso.png") {
          byView.iso.push({ stepIndex: step.step_index, url: api.artifactUrl(id, artifact.rel_path) });
        }
      }
    }

    return byView;
  }, [timeline, id]);

  const galleryItems = useMemo(() => {
    if (!timeline) {
      return [];
    }
    return timeline.steps
      .flatMap((step) => step.artifacts)
      .filter((artifact) => artifact.artifact_type === "render")
      .slice(-8)
      .map((artifact) => ({ url: api.artifactUrl(id, artifact.rel_path), title: artifact.rel_path }));
  }, [timeline, id]);

  const onAppend = async (lines: string[], message?: string) => {
    await api.append(id, lines, message);
    await refresh();
  };

  const onCheckpoint = async (message?: string) => {
    await api.checkpoint(id, message);
    await refresh();
  };

  const onRender = async (payload: { views: string[]; turntable_frames: number; resolution: { w: number; h: number }; message?: string }) => {
    await api.render(id, payload);
    await refresh();
  };

  const onDeleteWorkspace = async () => {
    if (!confirm("Delete this workspace and all artifacts?")) {
      return;
    }
    try {
      await api.deleteWorkspace(id);
      router.push("/");
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const onStartAiRun = async (event: FormEvent) => {
    event.preventDefault();
    if (!conceptImage && !persistedConceptUrl) {
      setError("Please upload a desired build image first.");
      return;
    }
    setAiBusy(true);
    setError(null);
    setAiResult(null);
    try {
      const started = await api.startAiRun(id, {
        conceptImage,
        runName,
        presetPath,
        maxSteps,
        beamWidth,
        candidatesPerStep,
        scoreThreshold,
        controlPlaneUrl: api.base
      });
      setAiResult(`Started AI run (PID ${started.pid}) using ${started.preset_path}`);
      setAiPid(started.pid);
      setAiLogPath(started.log_path);
      setAiRunning(true);
      setAiMonitoring(true);
      const stepCount = timeline?.steps.length ?? 0;
      setAiStartedStepCount(stepCount);
      setAiLastObservedStep(stepCount);
      await refresh(false);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setAiBusy(false);
    }
  };

  const onStopAiRun = async () => {
    setAiStopping(true);
    setError(null);
    try {
      const stopped = await api.stopAiRun(id);
      setAiResult(stopped.message);
      setAiRunning(false);
      setAiMonitoring(false);
      const status = await api.aiStatus(id, 350);
      setAiPid(status.pid);
      setAiLogPath(status.log_path);
      setAiLogLines(status.log_lines);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setAiStopping(false);
    }
  };

  return (
    <main style={{ padding: 18, display: "grid", gap: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1 style={{ margin: 0 }}>Workspace {timeline?.workspace.name ?? id}</h1>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <Link href="/">Back</Link>
          <button type="button" onClick={onDeleteWorkspace} style={{ border: "1px solid #7f1d1d", background: "#7f1d1d", color: "white", borderRadius: 6, padding: "6px 10px" }}>
            Delete Workspace
          </button>
        </div>
      </div>
      {error && <div style={{ color: "#ff6b6b" }}>{error}</div>}
      {loading && <div style={{ opacity: 0.8 }}>Loading...</div>}

      <section style={{ border: "1px solid #2e3540", borderRadius: 10, background: "#141a23", padding: 14 }}>
        <h2 style={{ marginTop: 0, marginBottom: 6 }}>Step 1: AI Build Setup</h2>
        <p style={{ marginTop: 0, marginBottom: 10, opacity: 0.85 }}>
          Upload your desired build image and start AI generation. This is the primary workflow.
        </p>
        <form onSubmit={onStartAiRun} style={{ display: "grid", gap: 10 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 220px", gap: 12, alignItems: "start" }}>
            <div style={{ display: "grid", gap: 8 }}>
              <label style={{ fontSize: 13, fontWeight: 600 }}>Desired build image {persistedConceptUrl ? "(saved, optional to replace)" : "(required)"}</label>
              <input type="file" accept="image/*" onChange={(event) => setConceptImage(event.target.files?.[0] ?? null)} />

              <label style={{ fontSize: 13, fontWeight: 600 }}>Run name</label>
              <input value={runName} onChange={(event) => setRunName(event.target.value)} placeholder="e.g. hummingbird-v1" />

              <label style={{ fontSize: 13, fontWeight: 600 }}>Preset path</label>
              <input value={presetPath} onChange={(event) => setPresetPath(event.target.value)} placeholder="presets/bird_sculpt.json" />
            </div>

            <div style={{ border: "1px solid #2e3540", borderRadius: 8, background: "#0f1318", padding: 8 }}>
              <div style={{ fontSize: 12, marginBottom: 6, opacity: 0.85 }}>Desired build thumbnail</div>
              {effectiveConceptPreviewUrl ? (
                <img src={effectiveConceptPreviewUrl} alt="Desired build preview" style={{ width: "100%", height: 180, objectFit: "cover", borderRadius: 6 }} />
              ) : (
                <div style={{ height: 180, display: "grid", placeItems: "center", border: "1px dashed #334155", borderRadius: 6, fontSize: 12, opacity: 0.8 }}>
                  No image selected
                </div>
              )}
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <label style={{ display: "grid", gap: 4 }}>
              <span style={{ fontSize: 12 }}>Max steps ({maxSteps}) — max AI iterations before stop.</span>
              <input type="number" min={1} value={maxSteps} onChange={(event) => setMaxSteps(Number(event.target.value))} />
            </label>
            <label style={{ display: "grid", gap: 4 }}>
              <span style={{ fontSize: 12 }}>Beam width ({beamWidth}) — branches kept each step.</span>
              <input type="number" min={1} value={beamWidth} onChange={(event) => setBeamWidth(Number(event.target.value))} />
            </label>
            <label style={{ display: "grid", gap: 4 }}>
              <span style={{ fontSize: 12 }}>Candidates/step ({candidatesPerStep}) — assemblies proposed before selection.</span>
              <input type="number" min={1} value={candidatesPerStep} onChange={(event) => setCandidatesPerStep(Number(event.target.value))} />
            </label>
            <label style={{ display: "grid", gap: 4 }}>
              <span style={{ fontSize: 12 }}>Score threshold ({scoreThreshold}) — stop once quality score reaches this.</span>
              <input type="number" step="0.01" min={0} max={1} value={scoreThreshold} onChange={(event) => setScoreThreshold(Number(event.target.value))} />
            </label>
          </div>

          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <button type="submit" disabled={aiBusy}>
              {aiBusy ? "Starting..." : "Start AI Build Run"}
            </button>
            {aiMonitoring && (
              <button type="button" onClick={() => setAiMonitoring(false)}>
                Stop Monitoring
              </button>
            )}
          </div>
        </form>

        {(aiResult || aiMonitoring) && (
          <div style={{ marginTop: 10, padding: 10, borderRadius: 8, border: "1px solid #2e3540", background: "#0f1318", fontSize: 13 }}>
            {aiResult && <div style={{ marginBottom: 6 }}>{aiResult}</div>}
            <div>
              Progress: steps in timeline {timeline?.steps.length ?? 0}
              {aiStartedStepCount !== null ? ` (started at ${aiStartedStepCount}, +${Math.max(0, (timeline?.steps.length ?? 0) - aiStartedStepCount)})` : ""}
            </div>
            <div style={{ opacity: 0.8 }}>Latest observed step count: {aiLastObservedStep}</div>
          </div>
        )}
      </section>

      <div style={{ display: "grid", gridTemplateColumns: "300px 1fr 360px", gap: 12, alignItems: "start" }}>
        <section>
          <h2 style={{ marginTop: 0 }}>Timeline</h2>
          <Timeline steps={timeline?.steps ?? []} />
        </section>

        <section style={{ display: "grid", gap: 10 }}>
          <h2 style={{ marginTop: 0 }}>Flipbook</h2>
          <Flipbook framesByView={flipbookFramesByView} />
          <h2 style={{ marginTop: 6 }}>3D Preview (placeholder)</h2>
          <ThreeViewer ldrawContent={currentModel?.content ?? ""} />
          <ArtifactGallery items={galleryItems} />
        </section>

        <section>
          <h2 style={{ marginTop: 0 }}>AI Live Log</h2>
          <div style={{ position: "sticky", top: 8, border: "1px solid #2e3540", borderRadius: 8, background: "#0f1318", padding: 10, marginBottom: 12 }}>
            <div style={{ fontSize: 12, marginBottom: 6, opacity: 0.9 }}>
              Status: {aiRunning ? "Running" : "Idle"}{aiPid ? ` (PID ${aiPid})` : ""}
            </div>
            <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
              <button type="button" onClick={onStopAiRun} disabled={!aiRunning || aiStopping}>
                {aiStopping ? "Halting..." : "Halt AI Run"}
              </button>
            </div>
            {aiLogPath && <div style={{ fontSize: 11, opacity: 0.7, marginBottom: 8, wordBreak: "break-all" }}>{aiLogPath}</div>}
            <div style={{ height: "58vh", overflow: "auto", border: "1px solid #1f2937", borderRadius: 6, padding: 8, background: "#020617" }}>
              <pre style={{ margin: 0, whiteSpace: "pre-wrap", fontSize: 11, lineHeight: 1.35, fontFamily: "Consolas, 'Courier New', monospace" }}>
                {aiLogLines.length ? aiLogLines.join("\n") : "No AI logs yet."}
              </pre>
            </div>
          </div>

          <h2 style={{ marginTop: 0 }}>Manual Tools</h2>
          <p style={{ marginTop: 0, fontSize: 13, opacity: 0.82 }}>
            Secondary troubleshooting controls for direct low-level operations.
          </p>
          <details>
            <summary style={{ cursor: "pointer", marginBottom: 8 }}>Open Manual Command Console (Advanced)</summary>
            <CommandConsole onAppend={onAppend} onCheckpoint={onCheckpoint} onRender={onRender} />
          </details>
        </section>
      </div>
    </main>
  );
}
