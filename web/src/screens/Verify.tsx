import {
  InlineNotification,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Tag,
  Tile,
} from "@carbon/react";
import { GroupedBarChart } from "@carbon/charts-react";
import { ScaleTypes, type BarChartOptions } from "@carbon/charts";
import "@carbon/charts/styles.css";
import type { Verify } from "../types";
import { ScoreTile } from "../components/ScoreTile";
const pct = (n: number | null) => (n === null ? "Not answerable" : `${(n * 100).toFixed(1)} %`);
const score = (n: number) => n.toFixed(3);
export function VerifyScreen({ data }: { data: Verify }) {
  const ours = data.ours,
    base = data.baseline;
  const checks = data.gate.checks;
  const blocking = new Set(data.gate.blocking);
  const chartData = [
    { group: "PurposeFit", key: "Privacy", value: ours.summary.privacy },
    { group: data.baseline_name, key: "Privacy", value: base.summary.privacy },
    { group: "PurposeFit", key: "Utility", value: ours.summary.utility },
    { group: data.baseline_name, key: "Utility", value: base.summary.utility },
    { group: "PurposeFit", key: "Composite", value: ours.summary.composite },
    { group: data.baseline_name, key: "Composite", value: base.summary.composite },
  ];
  const options: BarChartOptions = {
    title: "Score comparison",
    axes: {
      left: { mapsTo: "value", domain: [0, 1] },
      bottom: { mapsTo: "key", scaleType: ScaleTypes.LABELS },
    },
    height: "320px",
    color: { scale: { PurposeFit: "#0f62fe", [data.baseline_name]: "#8d8d8d" } },
    legend: { enabled: true },
  };
  return (
    <>
      <div className="section-intro">
        <div>
          <h2>Release verification</h2>
          <p>
            {ours.tool} self-assessment for {data.scenario_id}. Same scenario and scorer for both
            methods.
          </p>
        </div>
      </div>
      <InlineNotification
        kind={data.gate.passed ? "success" : "error"}
        title={
          data.gate.passed
            ? `Release gate passed for ${data.scenario_id}`
            : `Release gate failed for ${data.scenario_id}`
        }
        subtitle={
          data.gate.passed
            ? "All gate checks passed."
            : `Blocking checks: ${data.gate.blocking.map((id) => checks.find((c) => c.id === id)?.name ?? id).join("; ") || "none listed"}.`
        }
        lowContrast
        hideCloseButton
      />
      <div className="metric-grid">
        {(["privacy", "utility", "composite"] as const).map((k) => (
          <ScoreTile
            key={k}
            label={k}
            value={score(ours.summary[k])}
            baselineName={data.baseline_name}
            baselineValue={score(base.summary[k])}
          />
        ))}
      </div>
      <p className="small muted">{ours.summary.label}</p>
      <div className="verify-grid">
        <Tile className="chart-tile">
          <GroupedBarChart data={chartData} options={options} />
        </Tile>
        <Tile className="k-tile">
          <h3>k-anonymity checks</h3>
          {data.k.length ? (
            data.k.map((x) => (
              <div className="k-row" key={x.table}>
                <b>{x.table}</b>
                <span>pipeline k = {x.pipeline_k}</span>
                <span>pyCANON k = {x.pycanon_k}</span>
                <span className="small muted">{x.method}</span>
              </div>
            ))
          ) : (
            <p className="muted">No kept quasi-identifiers to check.</p>
          )}
        </Tile>
      </div>
      <div className="verify-grid table-pair">
        <div>
          <h3>Gate checks</h3>
          <div className="table-wrap">
            <Table>
              <TableHead>
                <TableRow>
                  {["Check", "Result", "Observed", "Threshold", "Source"].map((x) => (
                    <TableHeader key={x}>{x}</TableHeader>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {checks.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell>{c.name}</TableCell>
                    <TableCell>
                      <Tag type={c.status === "pass" ? "green" : "red"}>{c.status}</Tag>
                    </TableCell>
                    <TableCell>
                      {c.value === null ? "Not set" : c.kind === "risk" ? pct(c.value) : c.value}
                    </TableCell>
                    <TableCell>{c.kind === "risk" ? pct(c.threshold) : c.threshold}</TableCell>
                    <TableCell>{c.source}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
        <div>
          <h3>Utility tasks</h3>
          <div className="table-wrap">
            <Table>
              <TableHead>
                <TableRow>
                  {["Task", "PurposeFit", "B2-k"].map((x) => (
                    <TableHeader key={x}>{x}</TableHeader>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {ours.utility.map((u) => (
                  <TableRow key={u.id}>
                    <TableCell>
                      <b>{u.id}</b>
                      <small className="task-description">{u.description}</small>
                    </TableCell>
                    <TableCell>{pct(u.score)}</TableCell>
                    <TableCell>
                      {pct(base.utility.find((x) => x.id === u.id)?.score ?? null)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      </div>
      <div className="verify-grid table-pair">
        <div>
          <h3>Risk components</h3>
          <div className="table-wrap">
            <Table>
              <TableHead>
                <TableRow>
                  {["Component", "PurposeFit", "B2-k"].map((x) => (
                    <TableHeader key={x}>{x}</TableHeader>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {[
                  ...new Set([
                    ...Object.keys(ours.risk_components),
                    ...Object.keys(base.risk_components),
                  ]),
                ].map((k) => (
                  <TableRow key={k}>
                    <TableCell>{k}</TableCell>
                    <TableCell>
                      {ours.risk_components[k] === undefined
                        ? "Not set"
                        : pct(ours.risk_components[k])}
                    </TableCell>
                    <TableCell>
                      {base.risk_components[k] === undefined
                        ? "Not set"
                        : pct(base.risk_components[k])}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
        <div>
          <h3>Residual risks</h3>
          <ul className="risk-list">
            {data.residual_risks.map((r) => (
              <li key={r.id}>{r.text}</li>
            ))}
          </ul>
        </div>
      </div>
      {data.ablation.length > 0 && (
        <>
          <h3>Ablation results</h3>
          <Table>
            <TableHead>
              <TableRow>
                {["Layer switched off", "Leakage", "Utility"].map((x) => (
                  <TableHeader key={x}>{x}</TableHeader>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {data.ablation.map((x) => (
                <TableRow key={x.layer_off}>
                  <TableCell>{x.layer_off}</TableCell>
                  <TableCell>{pct(x.leakage)}</TableCell>
                  <TableCell>{pct(x.utility)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </>
      )}
    </>
  );
}
