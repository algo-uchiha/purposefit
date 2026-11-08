import { GroupedBarChart } from "@carbon/charts-react";
import { ScaleTypes } from "@carbon/charts";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@carbon/react";
import type { Verify } from "../../types";
import type { LeaderboardRow } from "../../api";
type Claims = Record<string, string>;
export function Results({
  rows,
  verify,
  claims,
}: {
  rows: LeaderboardRow[];
  verify: Verify;
  claims: Claims;
}) {
  const methods = ["B0 (rerun)", "B2 (rerun)", "B2-k (rerun)", "purposefit"];
  const latest = (method: string) =>
    rows
      .filter((r) => r.scenario === "CS-S1" && r.method === method)
      .sort((a, b) => b.created_utc.localeCompare(a.created_utc))[0];
  const scoreRows = methods.map((method) => ({ method, row: latest(method) })).filter((x) => x.row);
  const chartData = scoreRows.flatMap(({ method, row }) => [
    { group: method, key: "Privacy", value: row!.privacy },
    { group: method, key: "Utility", value: row!.utility },
    { group: method, key: "Composite", value: row!.composite },
  ]);
  const options = {
    title: "CS-S1 score comparison",
    axes: {
      left: { mapsTo: "value", domain: [0, 1] },
      bottom: { mapsTo: "key", scaleType: ScaleTypes.LABELS },
    },
    height: "300px",
    color: {
      scale: {
        purposefit: "#0E7C7B",
        "B0 (rerun)": "#9AA1A9",
        "B2 (rerun)": "#737D88",
        "B2-k (rerun)": "#515D6B",
      },
    },
    legend: { enabled: true },
  };
  const final = rows.find((r) => r.run_id === "final-CS-S1");
  const noLlm = rows.find((r) => r.run_id === "final-CS-S1-nollm");
  const dataRows = [
    {
      label: "Held-out detection macro-F1",
      result: `B1 ${claims["detect.b1.heldout.macro_f1"] ?? "Unavailable"} · rules only ${claims["detect.rules.heldout.macro_f1"] ?? "Unavailable"} · with LLM ${claims["detect.llm.heldout.macro_f1"] ?? "Unavailable"}`,
      source: "claims.json · held-out detection split",
    },
    ...(claims["health.train_before"]
      ? [
          {
            label: "Health leakage in training data",
            result: `Before ${claims["health.train_before"]} · after ${claims["health.train_after"]}`,
            source: "claims.json · synthetic training split",
          },
        ]
      : []),
    {
      label: "CS-S1 AI-off composite",
      result: `AI off ${noLlm?.composite.toFixed(4) ?? "Unavailable"} · AI on ${final?.composite.toFixed(4) ?? "Unavailable"}`,
      source: `${noLlm?.run_id ?? "Unavailable"} vs ${final?.run_id ?? "Unavailable"} · leaderboard`,
    },
  ];
  return (
    <section className="landing-panel evidence-panel">
      <div className="landing-content reveal">
        <p className="landing-kicker">Evidence</p>
        <h2>Compare the release methods against the same tasks</h2>
        <p className="section-source">
          CS-S1 · pets-eval self-assessment · each series uses its recorded run
        </p>
        <div className="evidence-chart">
          <GroupedBarChart data={chartData} options={options} />
        </div>
        <div className="evidence-table">
          <h3>Detection and parity checks</h3>
          <div className="table-scroll">
            <Table>
              <TableHead>
                <TableRow>
                  {["Measure", "Results", "Source"].map((x) => (
                    <TableHeader key={x}>{x}</TableHeader>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {dataRows.map((r) => (
                  <TableRow key={r.label}>
                    <TableCell>{r.label}</TableCell>
                    <TableCell>{r.result}</TableCell>
                    <TableCell>{r.source}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
        <p className="section-source">
          Chart scores are proportions from the leaderboard. Detection results are held-out macro-F1
          from claims.json.
        </p>
      </div>
    </section>
  );
}
