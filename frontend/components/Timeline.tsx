import type { Step } from "@/lib/types";

const kindIcon: Record<Step["kind"], string> = {
  append: "➕",
  checkpoint: "📍",
  render: "🖼️"
};

export function Timeline({ steps }: { steps: Step[] }) {
  return (
    <div style={{ display: "grid", gap: 8 }}>
      {steps.map((step) => (
        <div key={step.id} style={{ border: "1px solid #2e3540", borderRadius: 8, background: "#161b22", padding: 10 }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
            <span>
              {kindIcon[step.kind]} step {step.step_index} · {step.kind}
            </span>
            <span style={{ opacity: 0.75 }}>{new Date(step.created_at).toLocaleTimeString()}</span>
          </div>
          {step.message && <div style={{ marginTop: 6, fontSize: 13 }}>{step.message}</div>}
          <div style={{ marginTop: 6, fontSize: 12, opacity: 0.8 }}>{step.artifacts.length} artifacts</div>
        </div>
      ))}
    </div>
  );
}
