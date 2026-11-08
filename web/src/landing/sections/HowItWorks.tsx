import { useEffect, useState } from "react";
import { Scan, DocumentTasks, Locked, TaskComplete } from "@carbon/icons-react";
import { Tag } from "@carbon/react";
import type { Plan, Redact, Verify, Span } from "../../types";
import { PlanPreview } from "../components/PlanPreview";
import { SpanTag } from "../components/SpanTag";
type LabelRow = {
  table: string;
  column: string;
  privacy_role: string;
  subtype: string;
  reason: string;
};
type DetectData = { labels: LabelRow[] };
const stages = [
  { icon: Scan, title: "Detect", caption: "Find what each column and sentence contains." },
  { icon: DocumentTasks, title: "Plan", caption: "Keep only what this recipient's tasks need." },
  { icon: Locked, title: "Transform", caption: "Change the release and remove text identifiers." },
  {
    icon: TaskComplete,
    title: "Verify",
    caption: "Re-run attacks and utility checks before export.",
  },
];
export function HowItWorks({
  plan,
  detect,
  redact,
  verify,
  runId,
}: {
  plan: Plan;
  detect?: DetectData;
  redact?: Redact;
  verify: Verify;
  runId?: string;
}) {
  const [active, setActive] = useState(0);
  useEffect(() => {
    const section = document.getElementById("how-it-works");
    if (!section) return;
    const steps = section.querySelectorAll<HTMLElement>("[data-stage]");
    const observer = new IntersectionObserver(
      (entries) =>
        entries.forEach((entry) => {
          if (entry.isIntersecting) setActive(Number((entry.target as HTMLElement).dataset.stage));
        }),
      { rootMargin: "-35% 0px -45% 0px" },
    );
    steps.forEach((step) => observer.observe(step));
    return () => observer.disconnect();
  }, []);
  const turn = redact?.turns[0];
  const checks = verify.gate.checks;
  return (
    <section id="how-it-works" className="landing-panel workflow-panel">
      <div className="landing-content reveal">
        <p className="landing-kicker">How it works</p>
        <h2>A release plan you can inspect from detection to verification</h2>
        <div className="workflow-layout">
          <ol className="stage-list">
            {stages.map(({ icon: Icon, title, caption }, index) => (
              <li key={title} data-stage={index} className={active === index ? "stage-active" : ""}>
                <span className="stage-icon">
                  <Icon size={22} />
                </span>
                <div>
                  <span className="stage-status">{active === index ? "Viewing" : "Ready"}</span>
                  <h3>{title}</h3>
                  <p>{caption}</p>
                </div>
              </li>
            ))}
          </ol>
          <div className="stage-product">
            <div className="product-frame-bar">
              <span>PurposeFit · {stages[active].title}</span>
              <code>{runId ?? plan.scenario_id}</code>
            </div>
            {active === 0 && (
              <div className="detection-preview">
                <h3>Detected fields and reasons</h3>
                {(detect?.labels ?? []).slice(0, 6).map((field) => (
                  <div className="detect-row" key={`${field.table}.${field.column}`}>
                    <code>{field.column}</code>
                    <Tag>{field.privacy_role}</Tag>
                    <span>{field.reason}</span>
                  </div>
                ))}
              </div>
            )}
            {active === 1 && <PlanPreview plan={plan} runId={runId} limit={8} embedded />}
            {active === 2 && (
              <div className="transform-preview">
                <h3>Original and protected turn</h3>
                <p>{turn?.original_text ?? "No example turn in the fixture."}</p>
                <p>{turn?.protected_text ?? "Unavailable"}</p>
                <div className="span-list">
                  {(turn?.spans ?? []).slice(0, 5).map((span: Span, i) => (
                    <SpanTag key={i} label={span.label} layer={span.layer} />
                  ))}
                </div>
              </div>
            )}
            {active === 3 && (
              <div className="verify-preview">
                <div className={verify.gate.passed ? "gate-chip passed" : "gate-chip blocked"}>
                  {verify.gate.passed ? "Gate passed" : "Gate blocked"}
                </div>
                {checks.map((check) => (
                  <div className="gate-row" key={check.id}>
                    <span>{check.name}</span>
                    <Tag type={check.status === "pass" ? "green" : "red"}>{check.status}</Tag>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
