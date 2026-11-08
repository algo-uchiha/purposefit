import { Tag } from "@carbon/react";
import type { Finding, Plan, Verify } from "../../types";
import type { LeaderboardRow } from "../../api";
export function Problem({
  finding,
  plan,
  verify,
  baseline,
}: {
  finding?: Finding;
  plan: Plan;
  verify: Verify;
  baseline?: LeaderboardRow;
}) {
  const failed = verify.baseline.utility.find((task) => task.id === "CS-U1");
  const leakage = verify.baseline.tables?.turns?.free_text?.text?.identifying_leakage_rate;
  const needed = plan.policies
    .filter((p) => p.action === "keep" || p.action === "redact")
    .map((p) => p.column);
  const sensitive = plan.policies
    .filter((p) => ["direct_identifier", "sensitive_attribute"].includes(String(p.params.role)))
    .slice(0, 5);
  return (
    <section id="problem" className="landing-panel problem-panel">
      <div className="landing-content reveal">
        <p className="landing-kicker">The problem</p>
        <h2>A purpose narrows the release</h2>
        <div className="need-columns">
          <div>
            <h3>What the analytics vendor needs</h3>
            <p>
              {needed
                .filter((x) => ["intent", "handle_time_s", "text"].includes(x))
                .map((x) => (
                  <Tag key={x} type="blue">
                    {x}
                  </Tag>
                ))}
            </p>
            <p>Intent, handle time and conversation text support contact-reason analysis.</p>
          </div>
          <div>
            <h3>What comes along by default</h3>
            <p>
              {sensitive.map((x) => (
                <Tag key={`${x.table}.${x.column}`} type="red">
                  {x.column}
                </Tag>
              ))}
              <Tag type="cool-gray">customers table</Tag>
            </p>
            <p>
              Names, ID numbers read aloud, spelled emails and health remarks can appear alongside
              useful analysis data.
            </p>
          </div>
        </div>
        <div className="facts-row">
          <article>
            <strong>{leakage === undefined ? "Not set" : `${(leakage * 100).toFixed(1)} %`}</strong>
            <p>Identifying values leaked in transcripts after regex redaction.</p>
            <small>
              {verify.baseline_name} · pets-eval · {verify.baseline.scenario.id}
            </small>
          </article>
          <article>
            <strong>
              {finding?.match_rate === undefined
                ? "Not set"
                : `${(finding.match_rate * 100).toFixed(0)} % match`}
            </strong>
            <p>
              {finding
                ? `Column ${finding.column} was an unkeyed ${finding.algorithm} of a national ID in ${finding.source_column}. It is reversible by enumeration.`
                : "No hash finding available."}
            </p>
            <small>Detection finding · unseen export</small>
          </article>
          <article>
            <strong>{failed?.score === null ? "Not answerable" : "Not set"}</strong>
            <p>
              The baseline cannot answer the intent-model task after required training data is
              missing.
            </p>
            <small>
              {failed?.id ?? "CS-U1"} · {verify.baseline_name} · pets-eval
            </small>
          </article>
        </div>
        <p className="baseline-note">
          Baseline composite: {baseline?.composite.toFixed(4) ?? "Not set"} ·{" "}
          {baseline?.run_id ?? "Not set"}.
        </p>
      </div>
    </section>
  );
}
