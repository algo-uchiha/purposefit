import { Button, Tag } from "@carbon/react";
import type { Plan, Run, Verify } from "../../types";
import type { LeaderboardRow } from "../../api";
import { PlanPreview } from "../components/PlanPreview";
export function Hero({
  plan,
  run,
  verify,
  ours,
  baseline,
}: {
  plan: Plan;
  run?: Run;
  verify: Verify;
  ours?: LeaderboardRow;
  baseline?: LeaderboardRow;
}) {
  const risks = verify.ours.risk_components;
  const key = Object.keys(risks).find(
    (name) => name.includes("turns") && name.includes("free-text"),
  );
  const baseKey =
    key && Object.hasOwn(verify.baseline.risk_components, key)
      ? key
      : Object.keys(verify.baseline.risk_components).find(
          (name) => name.includes("turns") && name.includes("free-text"),
        );
  return (
    <section className="landing-panel landing-hero" data-panel="hero">
      <div className="hero-layout reveal">
        <div className="hero-copy">
          <a className="landing-brand" href="#/">
            PurposeFit
          </a>
          <h1>
            Share data with purpose.
            <br />
            Protect what matters.
          </h1>
          <p className="landing-lede">
            PurposeFit decides what each recipient needs, protects the rest, and re-runs real
            privacy attacks before anything is released.
          </p>
          <div className="landing-actions">
            <Button
              onClick={() =>
                document.getElementById("how-it-works")?.scrollIntoView({ behavior: "smooth" })
              }
            >
              See how it works
            </Button>
            <Button kind="secondary" href="#/workbench">
              Open the workbench
            </Button>
          </div>
        </div>
        <div className="hero-product">
          <PlanPreview plan={plan} runId={run?.run_id} limit={8} />
        </div>
      </div>
      <div className="hero-metrics">
        <Metric
          title="Composite score"
          ours={ours?.composite}
          baseline={baseline?.composite}
          source={`${ours?.run_id ?? "Not set"} vs ${baseline?.run_id ?? "Not set"} · pets-eval`}
        />
        <Metric
          title="Text leakage"
          ours={key ? risks[key] : undefined}
          baseline={baseKey ? (verify.baseline.risk_components[baseKey] ?? undefined) : undefined}
          percent
          source={`${verify.ours.tool} · turns · identifying values`}
        />
        <div className="proof-metric">
          <span>Release gate</span>
          <strong className={verify.gate.passed ? "status-pass" : "status-block"}>
            {verify.gate.passed ? "Passed" : "Blocked"}
          </strong>
          <small>
            {verify.gate.checks.length} checks · {verify.ours.tool} · {verify.scenario_id}
          </small>
        </div>
      </div>
    </section>
  );
}
function Metric({
  title,
  ours,
  baseline,
  source,
  percent = false,
}: {
  title: string;
  ours?: number | null;
  baseline?: number | null;
  source: string;
  percent?: boolean;
}) {
  const show = (value?: number | null) =>
    value == null ? "Not set" : percent ? `${(value * 100).toFixed(2)} %` : value.toFixed(4);
  return (
    <div className="proof-metric">
      <span>{title}</span>
      <strong>
        {show(ours)} <small>vs</small> {show(baseline)}
      </strong>
      <small>{source}</small>
    </div>
  );
}
