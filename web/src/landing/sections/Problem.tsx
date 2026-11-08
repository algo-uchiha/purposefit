import type { Finding, Verify } from "../../types";
import type { LeaderboardRow } from "../../api";
export function Problem({
  finding,
  baseline,
  verify,
}: {
  finding?: Finding;
  baseline?: LeaderboardRow;
  verify?: Verify;
}) {
  const failedTask = verify?.baseline.utility.find((x) => x.score === null);
  const regexLeak = verify?.baseline.tables?.turns?.free_text?.text?.identifying_leakage_rate;
  return (
    <section id="problem" className="landing-panel problem-panel">
      <div className="landing-content reveal">
        <p className="landing-kicker">Why purpose matters</p>
        <h2>Three risks hidden in ordinary exports</h2>
        <div className="problem-grid">
          <article>
            <strong>{regexLeak == null ? "Not set" : `${(regexLeak * 100).toFixed(0)} %`}</strong>
            <p>Removing names is not enough. People say ID numbers aloud and spell out emails.</p>
            <small>pets-eval · B2-k baseline · turns text</small>
          </article>
          <article>
            <strong>
              {finding?.match_rate == null
                ? "Not set"
                : `${(finding.match_rate * 100).toFixed(0)} %`}
            </strong>
            <p>
              {finding
                ? `Column ${finding.column} is an unkeyed ${finding.algorithm} of the national ID in ${finding.source_column}. Anyone can reverse it.`
                : "No matching hash finding in the fixture."}
            </p>
            <small>Detection finding · unseen export · match rate</small>
          </article>
          <article>
            <strong>{failedTask?.score === null ? "Not answerable" : "Not set"}</strong>
            <p>Blind protection breaks the analysis it was meant to allow.</p>
            <small>
              {failedTask
                ? `${failedTask.id} · B2-k · pets-eval`
                : `${baseline?.scenario ?? "Not set"} · B2-k · pets-eval`}
            </small>
          </article>
        </div>
      </div>
    </section>
  );
}
