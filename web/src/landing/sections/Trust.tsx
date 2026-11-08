import { Tag } from "@carbon/react";
import type { Plan, Verify } from "../../types";
export function Trust({ plan, verify }: { plan: Plan; verify: Verify }) {
  const pseudonym = plan.policies.find((p) => p.action === "hmac");
  return (
    <section className="landing-panel trust-panel">
      <div className="landing-content reveal">
        <p className="landing-kicker">Trust and transparency</p>
        <h2>Show what the release claims and how it was checked</h2>
        <div className="trust-grid">
          <article className="trust-card">
            <h3>Policy excerpt</h3>
            <dl>
              <dt>Pseudonymisation secret</dt>
              <dd>
                Key id: <code>{plan.key_id || "Not set"}</code>
              </dd>
              <dt>Pseudonymisation domain</dt>
              <dd>{verify.ours.scenario.recipient}</dd>
              <dt>Additional information</dt>
              <dd>Held by the controller.</dd>
              <dt>Technique</dt>
              <dd>{pseudonym?.guarantee ?? "Not set"}</dd>
            </dl>
          </article>
          <article className="trust-card">
            <h3>Verification checks</h3>
            {verify.gate.checks.map((check) => (
              <div className="trust-check gate-row" key={check.id}>
                <span>{check.name}</span>
                <Tag type={check.status === "pass" ? "green" : "red"}>{check.status}</Tag>
              </div>
            ))}
          </article>
          <article className="trust-card limitations-list">
            <h3>Known limitations</h3>
            <ul>
              {verify.residual_risks.slice(0, 4).map((risk) => (
                <li key={risk.id}>{risk.text}</li>
              ))}
            </ul>
          </article>
        </div>
        <div className="safeguards">
          {[
            "AI sees masked text only",
            "Separate keys per recipient",
            "Export blocked unless the gate passes",
            "Every README number checked by make verify-claims",
          ].map((item) => (
            <span key={item}>{item}</span>
          ))}
        </div>
      </div>
    </section>
  );
}
