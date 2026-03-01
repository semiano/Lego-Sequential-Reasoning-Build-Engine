"use client";

import { FormEvent, useState } from "react";

type Props = {
  onAppend: (lines: string[], message?: string) => Promise<void>;
  onCheckpoint: (message?: string) => Promise<void>;
  onRender: (payload: { views: string[]; turntable_frames: number; resolution: { w: number; h: number }; message?: string }) => Promise<void>;
};

const allViews = ["front", "side", "top", "iso"];

export function CommandConsole({ onAppend, onCheckpoint, onRender }: Props) {
  const [appendLines, setAppendLines] = useState("1 16 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat");
  const [appendMessage, setAppendMessage] = useState("added base bricks");
  const [checkpointMessage, setCheckpointMessage] = useState("checkpoint");
  const [renderMessage, setRenderMessage] = useState("render progress");
  const [selectedViews, setSelectedViews] = useState<string[]>(["iso"]);
  const [turntableFrames, setTurntableFrames] = useState(24);
  const [width, setWidth] = useState(1024);
  const [height, setHeight] = useState(1024);
  const [busy, setBusy] = useState(false);

  const submitAppend = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      const lines = appendLines
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean);
      await onAppend(lines, appendMessage);
    } finally {
      setBusy(false);
    }
  };

  const submitCheckpoint = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      await onCheckpoint(checkpointMessage);
    } finally {
      setBusy(false);
    }
  };

  const submitRender = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      await onRender({
        views: selectedViews.length ? selectedViews : ["iso"],
        turntable_frames: turntableFrames,
        resolution: { w: width, h: height },
        message: renderMessage
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ display: "grid", gap: 12 }}>
      <form onSubmit={submitAppend} style={{ border: "1px solid #2e3540", borderRadius: 8, padding: 10, background: "#161b22" }}>
        <h3 style={{ marginTop: 0 }}>Append Parts</h3>
        <textarea value={appendLines} onChange={(event) => setAppendLines(event.target.value)} rows={5} style={{ width: "100%", background: "#0f1318", color: "#e8edf2", border: "1px solid #2e3540", borderRadius: 6, padding: 8 }} />
        <input value={appendMessage} onChange={(event) => setAppendMessage(event.target.value)} style={{ width: "100%", marginTop: 8, background: "#0f1318", color: "#e8edf2", border: "1px solid #2e3540", borderRadius: 6, padding: 8 }} placeholder="message" />
        <button type="submit" disabled={busy} style={{ marginTop: 8 }}>Append</button>
      </form>

      <form onSubmit={submitRender} style={{ border: "1px solid #2e3540", borderRadius: 8, padding: 10, background: "#161b22" }}>
        <h3 style={{ marginTop: 0 }}>Render</h3>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {allViews.map((view) => (
            <label key={view} style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <input
                type="checkbox"
                checked={selectedViews.includes(view)}
                onChange={(event) => {
                  setSelectedViews((prev) =>
                    event.target.checked ? Array.from(new Set([...prev, view])) : prev.filter((item) => item !== view)
                  );
                }}
              />
              {view}
            </label>
          ))}
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 8 }}>
          <input type="number" value={turntableFrames} onChange={(event) => setTurntableFrames(Number(event.target.value))} min={0} placeholder="turntable frames" />
          <input value={renderMessage} onChange={(event) => setRenderMessage(event.target.value)} placeholder="message" />
          <input type="number" value={width} onChange={(event) => setWidth(Number(event.target.value))} min={64} placeholder="width" />
          <input type="number" value={height} onChange={(event) => setHeight(Number(event.target.value))} min={64} placeholder="height" />
        </div>
        <button type="submit" disabled={busy} style={{ marginTop: 8 }}>Render</button>
      </form>

      <form onSubmit={submitCheckpoint} style={{ border: "1px solid #2e3540", borderRadius: 8, padding: 10, background: "#161b22" }}>
        <h3 style={{ marginTop: 0 }}>Checkpoint</h3>
        <input value={checkpointMessage} onChange={(event) => setCheckpointMessage(event.target.value)} style={{ width: "100%", background: "#0f1318", color: "#e8edf2", border: "1px solid #2e3540", borderRadius: 6, padding: 8 }} />
        <button type="submit" disabled={busy} style={{ marginTop: 8 }}>Checkpoint</button>
      </form>
    </div>
  );
}
