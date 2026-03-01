"use client";

import { useEffect, useMemo, useState } from "react";

type ViewName = "front" | "side" | "top" | "iso";
type FlipbookFrame = {
  stepIndex: number;
  url: string;
};

const viewOrder: ViewName[] = ["front", "side", "top", "iso"];

export function Flipbook({ framesByView }: { framesByView: Record<ViewName, FlipbookFrame[]> }) {
  const safeFramesByView =
    framesByView ??
    ({
      front: [],
      side: [],
      top: [],
      iso: []
    } as Record<ViewName, FlipbookFrame[]>);

  const availableViews = useMemo(
    () => viewOrder.filter((view) => (safeFramesByView[view] ?? []).length > 0),
    [safeFramesByView]
  );

  const [selectedView, setSelectedView] = useState<ViewName>("iso");
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (!availableViews.length) {
      return;
    }
    if (!availableViews.includes(selectedView)) {
      setSelectedView(availableViews.includes("iso") ? "iso" : availableViews[0]);
    }
  }, [availableViews, selectedView]);

  const frames = safeFramesByView[selectedView] ?? [];
  const safeIndex = Math.min(index, Math.max(0, frames.length - 1));
  const current = frames[safeIndex];

  useEffect(() => {
    setIndex(0);
  }, [selectedView]);

  if (!availableViews.length) {
    return <div style={{ border: "1px solid #2e3540", borderRadius: 8, padding: 16 }}>No renders yet.</div>;
  }

  return (
    <div style={{ border: "1px solid #2e3540", borderRadius: 8, background: "#161b22", padding: 10 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
        <label htmlFor="flipbook-view" style={{ fontSize: 13 }}>View</label>
        <select
          id="flipbook-view"
          value={selectedView}
          onChange={(event) => setSelectedView(event.target.value as ViewName)}
          style={{ background: "#0f1318", color: "#e8edf2", border: "1px solid #2e3540", borderRadius: 6, padding: "4px 8px" }}
        >
          {viewOrder.map((view) => (
            <option key={view} value={view} disabled={!availableViews.includes(view)}>
              {view}
            </option>
          ))}
        </select>
      </div>

      {current && (
        <img
          src={current.url}
          alt={`${selectedView} step ${current.stepIndex}`}
          style={{ width: "100%", maxHeight: 360, objectFit: "contain", borderRadius: 6 }}
        />
      )}

      <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8 }}>
        <button type="button" onClick={() => setIndex((value) => Math.max(0, value - 1))} disabled={safeIndex <= 0}>
          ←
        </button>
        <input
          type="range"
          min={0}
          max={Math.max(0, frames.length - 1)}
          value={safeIndex}
          onChange={(event) => setIndex(Number(event.target.value))}
          style={{ width: "100%" }}
        />
        <button
          type="button"
          onClick={() => setIndex((value) => Math.min(frames.length - 1, value + 1))}
          disabled={safeIndex >= frames.length - 1}
        >
          →
        </button>
      </div>

      <div style={{ fontSize: 12, opacity: 0.8, marginTop: 6 }}>
        Step {current?.stepIndex ?? "-"} · {safeIndex + 1} / {frames.length} ({selectedView})
      </div>
    </div>
  );
}
