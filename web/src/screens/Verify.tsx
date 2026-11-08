import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, Tag } from "@carbon/react";
import type { Verify } from "../types";
import { ScoreTile } from "../components/ScoreTile";
import { taskQuestion } from "../components/taskCopy";

const pct = (value: number | null) =>
  value === null ? "Not answerable" : `${(value * 100).toFixed(1)}%`;
const score = (value: number) => value.toFixed(3);

function riskSentence(text: string) {
  return text
    .replace("DATE values", "Dates")
    .replace("LOCATION values", "Locations")
    .replace("ORG values", "Organization names")
    .replace("SECRET values", "Secret values")
    .replace("NATIONAL_ID values", "National ID numbers")
    .replace("still recoverable in the released text:", "could still be found in the released text:");
}

function riskName(name: string) {
  const [, table, component] = name.match(/^([^:]+):\s*(.+)$/) ?? [];
  const base = component?.replace("free-text identifier leakage", "identifying details left in call text")
    .replace("direct identifiers retained", "direct identifiers left")
    .replace("records with k<5", "records in groups smaller than five")
    .replace("linkage re-identification", "records that could be linked to a person");
  return table && base ? `${base[0].toUpperCase()}${base.slice(1)} in ${table}` : name;
}

export function VerifyScreen({ data }: { data: Verify }) {
  const ours = data.ours;
  const baseline = data.baseline;
  const checks = data.gate.checks;
  const utility = ours.utility.map((task) => ({
    task,
    baseline: baseline.utility.find((item) => item.id === task.id),
  }));
  const riskNames = [
    ...new Set([...Object.keys(ours.risk_components), ...Object.keys(baseline.risk_components)]),
  ];
  return (
    <>
      <div className="section-intro">
        <div>
          <h2>Release verification</h2>
          <p>See the checks, how useful the copy stays, and what risks remain.</p>
        </div>
      </div>

      <section aria-label="Gate check cards">
        <h3>Gate checks</h3>
        <div className="proof-cards">
          {checks.map((check) => (
            <article
              className={`proof-card ${check.status === "pass" ? "proof-pass" : check.status === "fail" ? "proof-fail" : "proof-unknown"}`}
              key={check.id}
            >
              <div className="proof-card-top">
                <h3>{check.name}</h3>
                <Tag type={check.status === "pass" ? "green" : check.status === "fail" ? "red" : "cool-gray"}>
                  {check.status === "pass" ? "Pass" : check.status === "fail" ? "Fail" : "Unavailable"}
                </Tag>
              </div>
              <strong>{check.value == null ? "Unavailable" : pct(check.value)}</strong>
              <p>Limit: {check.comparison === "at_least" ? "at least" : "at most"} {pct(check.threshold)}</p>
            </article>
          ))}
        </div>
      </section>

      <section aria-label="Privacy, utility and combined scores">
        <h3>Scores</h3>
        <div className="metric-grid">
          {(["privacy", "utility", "composite"] as const).map((key) => (
            <ScoreTile
              key={key}
              label={key}
              value={score(ours.summary[key])}
              baselineName={data.baseline_name}
              baselineValue={score(baseline.summary[key])}
            />
          ))}
        </div>
      </section>

      <section className="utility-results">
        <h3>Does the data still work?</h3>
        {utility.map(({ task, baseline: standard }) => (
          <article className="utility-result-row" key={task.id}>
            <p>{taskQuestion(task.id, task.description)}</p>
            <div className="utility-result-bar">
              <span>PurposeFit</span>
              <div className="utility-bar-track"><i style={{ width: `${(task.score ?? 0) * 100}%` }} /></div>
              <b>{pct(task.score)}</b>
            </div>
            <div className="utility-result-bar standard">
              <span>Standard method</span>
              <div className="utility-bar-track"><i style={{ width: `${(standard?.score ?? 0) * 100}%` }} /></div>
              <b>{pct(standard?.score ?? null)}</b>
            </div>
          </article>
        ))}
      </section>

      <section>
        <h3>What could still go wrong</h3>
        <ul className="risk-list">
          {data.residual_risks.map((risk) => <li key={risk.id}>{riskSentence(risk.text)}</li>)}
        </ul>
      </section>

      <details className="advanced-details">
        <summary>Advanced details</summary>
        <div className="verify-grid">
          <div className="k-tile">
            <h3>Group size checks</h3>
            {data.k.length ? data.k.map((entry) => (
              <p key={entry.table}>
                <b>{entry.table}</b>: smallest group {entry.pycanon_k.toLocaleString()}
              </p>
            )) : <p>No groups needed checking.</p>}
          </div>
          <div>
            <h3>Gate check details</h3>
            <Table>
              <TableHead><TableRow>{["Check", "Result", "Observed", "Limit", "Source"].map((name) => <TableHeader key={name}>{name}</TableHeader>)}</TableRow></TableHead>
              <TableBody>{checks.map((check) => (
                <TableRow key={check.id}>
                  <TableCell>{check.name}</TableCell>
                  <TableCell>{check.status}</TableCell>
                  <TableCell>{check.value == null ? "Unavailable" : pct(check.value)}</TableCell>
                  <TableCell>{pct(check.threshold)}</TableCell>
                  <TableCell>{check.source}</TableCell>
                </TableRow>
              ))}</TableBody>
            </Table>
          </div>
        </div>
        <h3>Risk components</h3>
        <Table>
          <TableHead><TableRow>{["Measure", "PurposeFit", "Standard method"].map((name) => <TableHeader key={name}>{name}</TableHeader>)}</TableRow></TableHead>
          <TableBody>{riskNames.map((name) => (
            <TableRow key={name}>
              <TableCell>{riskName(name)}</TableCell>
              <TableCell>{ours.risk_components[name] == null ? "Unavailable" : pct(ours.risk_components[name])}</TableCell>
              <TableCell>{baseline.risk_components[name] == null ? "Unavailable" : pct(baseline.risk_components[name])}</TableCell>
            </TableRow>
          ))}</TableBody>
        </Table>
        {data.ablation.length > 0 && <>
          <h3>Ablation results</h3>
          <Table>
            <TableHead><TableRow>{["Layer switched off", "Leakage", "Utility"].map((name) => <TableHeader key={name}>{name}</TableHeader>)}</TableRow></TableHead>
            <TableBody>{data.ablation.map((entry) => (
              <TableRow key={entry.layer_off}>
                <TableCell>{entry.layer_off}</TableCell>
                <TableCell>{pct(entry.leakage)}</TableCell>
                <TableCell>{pct(entry.utility)}</TableCell>
              </TableRow>
            ))}</TableBody>
          </Table>
        </>}
      </details>
    </>
  );
}
