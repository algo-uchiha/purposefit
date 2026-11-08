import { GroupedBarChart } from "@carbon/charts-react";
import { ScaleTypes } from "@carbon/charts";
import { Button } from "@carbon/react";
import type { Verify } from "../../types";
export function Results({ one, two, open }: { one?: Verify; two?: Verify; open: () => void }) {
  const data = [
    ...(one
      ? [
          { group: "PurposeFit · CS-S1", key: "Privacy", value: one.ours.summary.privacy },
          { group: "B2-k · CS-S1", key: "Privacy", value: one.baseline.summary.privacy },
          { group: "PurposeFit · CS-S1", key: "Utility", value: one.ours.summary.utility },
          { group: "B2-k · CS-S1", key: "Utility", value: one.baseline.summary.utility },
          { group: "PurposeFit · CS-S1", key: "Overall", value: one.ours.summary.composite },
          { group: "B2-k · CS-S1", key: "Overall", value: one.baseline.summary.composite },
        ]
      : []),
    ...(two
      ? [
          { group: "PurposeFit · CS-S3", key: "Privacy", value: two.ours.summary.privacy },
          { group: "B2-k · CS-S3", key: "Privacy", value: two.baseline.summary.privacy },
          { group: "PurposeFit · CS-S3", key: "Utility", value: two.ours.summary.utility },
          { group: "B2-k · CS-S3", key: "Utility", value: two.baseline.summary.utility },
          { group: "PurposeFit · CS-S3", key: "Overall", value: two.ours.summary.composite },
          { group: "B2-k · CS-S3", key: "Overall", value: two.baseline.summary.composite },
        ]
      : []),
  ];
  const options = {
    title: "PurposeFit and B2-k scores",
    axes: {
      left: { mapsTo: "value", domain: [0, 1] },
      bottom: { mapsTo: "key", scaleType: ScaleTypes.LABELS },
    },
    height: "300px",
    legend: { enabled: true },
  };
  const limits = [...(one?.residual_risks ?? []), ...(two?.residual_risks ?? [])]
    .map((x) => x.text)
    .filter((x, i, a) => a.indexOf(x) === i)
    .slice(0, 3);
  return (
    <section className="landing-panel results-panel">
      <div className="landing-content reveal">
        <p className="landing-kicker">Results and limits</p>
        <div className="results-grid">
          <div>
            <h2>Measured results for each purpose</h2>
            <p className="landing-source">Self-assessment · pets-eval · fixture values</p>
            <GroupedBarChart data={data} options={options} />
          </div>
          <div className="limit-list">
            <h3>What the measures do not prove</h3>
            {limits.map((x, i) => (
              <p key={i}>{x}</p>
            ))}
          </div>
        </div>
        <Button onClick={open}>Open the workbench</Button>
      </div>
      <footer className="landing-footer">
        <span>PurposeFit · TrustED PETs Transformer challenge · Since AI Hackathon 2026</span>
        <span>
          <a href="https://github.com/algo-uchiha/purposefit">GitHub repository</a> ·{" "}
          <a href="https://github.com/algo-uchiha/purposefit#readme">README</a>
        </span>
      </footer>
    </section>
  );
}
