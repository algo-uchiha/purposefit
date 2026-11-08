import { Button, Tag } from "@carbon/react";
import type { Scenario, Plan } from "../../types";
import type { LeaderboardRow } from "../../api";
import { PlanPreview } from "../components/PlanPreview";
export function Recipients({
  scenarios,
  plans,
  rows,
  open,
}: {
  scenarios: Scenario[];
  plans: Record<string, Plan>;
  rows: LeaderboardRow[];
  open: (id: string) => void;
}) {
  const cases = scenarios.filter((s) => s.id === "CS-S1" || s.id === "CS-S3");
  const latest = (id: string, method: string) =>
    rows
      .filter(
        (row) =>
          row.scenario === id &&
          (method === "purposefit" ? row.method === method : row.method.startsWith("B2-k")),
      )
      .sort((a, b) => b.created_utc.localeCompare(a.created_utc))[0];
  const first = plans["CS-S1"];
  const second = plans["CS-S3"];
  const differences =
    first && second
      ? first.policies.flatMap((a) => {
          const b = second.policies.find((p) => p.table === a.table && p.column === a.column);
          return b && a.action !== b.action
            ? [{ table: a.table, column: a.column, first: a.action, second: b.action }]
            : [];
        })
      : [];
  return (
    <section id="use-cases" className="landing-panel cases-panel">
      <div className="landing-content reveal">
        <p className="landing-kicker">One dataset, two purposes</p>
        <h2>What leaves the controller depends on who needs it</h2>
        <div className="case-grid">
          {cases.map((scenario) => {
            const plan = plans[scenario.id];
            const own = latest(scenario.id, "purposefit");
            const base = latest(scenario.id, "baseline");
            const withheld = Array.from(
              new Set(
                (plan?.policies ?? [])
                  .filter((p) => p.action === "withhold_table")
                  .map((p) => p.table),
              ),
            );
            return (
              <article className="case-panel" key={scenario.id}>
                <header>
                  <div>
                    <Tag type="blue">{scenario.id}</Tag>
                    <h3>{scenario.title}</h3>
                  </div>
                  <span className="case-score">
                    {own ? own.composite.toFixed(4) : "Unavailable"}
                    <small>composite · {own?.run_id ?? "Unavailable"}</small>
                  </span>
                </header>
                <p className="case-recipient">{scenario.recipient}</p>
                <p>{scenario.purpose}</p>
                <div className="case-table-label">
                  <span>Released tables</span>
                  {(plan?.released_tables ?? []).map((table) => (
                    <Tag key={table} type="cool-gray">
                      {table}
                    </Tag>
                  ))}
                </div>
                <div className="case-table-label">
                  <span>Withheld tables</span>
                  {withheld.length ? (
                    withheld.map((table) => (
                      <Tag key={table} type="cool-gray">
                        {table}
                      </Tag>
                    ))
                  ) : (
                    <span>Unavailable</span>
                  )}
                </div>
                <p className="case-baseline">
                  B2-k composite: {base ? base.composite.toFixed(4) : "Unavailable"} ·{" "}
                  {base?.run_id ?? "Unavailable"}
                </p>
                <Button kind="tertiary" onClick={() => open(scenario.id)}>
                  Open this release plan
                </Button>
              </article>
            );
          })}
        </div>
        <div className="case-compare">
          <h3>Rows with a different action</h3>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Table</th>
                  <th>Column</th>
                  <th>{cases[0]?.id ?? "First purpose"}</th>
                  <th>{cases[1]?.id ?? "Second purpose"}</th>
                </tr>
              </thead>
              <tbody>
                {differences.map((row) => (
                  <tr className="plan-diff" key={`${row.table}.${row.column}`}>
                    <td>{row.table}</td>
                    <td>
                      <code>{row.column}</code>
                    </td>
                    <td>{row.first}</td>
                    <td>{row.second}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <p className="third-purpose">
          A third purpose, CS-S2, is in the <a href="#/workbench?scenario=CS-S2">workbench</a>.
        </p>
      </div>
    </section>
  );
}
