import { Button, Tile } from "@carbon/react";
import type { Scenario, Plan } from "../../types";
import type { LeaderboardRow } from "../../api";
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
  return (
    <section className="landing-panel recipient-panel">
      <div className="landing-content reveal">
        <p className="landing-kicker">Pick a recipient</p>
        <h2>One dataset. Different release plans.</h2>
        <div className="recipient-grid">
          {scenarios.map((s) => {
            const score = rows.filter((x) => x.scenario === s.id);
            const ours = score
              .filter((x) => x.method === "purposefit")
              .sort((a, b) => b.created_utc.localeCompare(a.created_utc))[0];
            const baseline = score.find((x) => x.method.startsWith("B2-k"));
            return (
              <Tile key={s.id} className="recipient-tile">
                <p className="recipient-name">{s.recipient}</p>
                <p>{s.purpose}</p>
                <p>
                  <b>Released tables</b>
                  <br />
                  {plans[s.id]?.released_tables.join(", ") ?? "Not set"}
                </p>
                <p className="recipient-score">
                  {ours ? ours.composite.toFixed(2) : "Not scored"}
                  <small>
                    {" "}
                    PurposeFit composite ·{" "}
                    {baseline ? `B2-k ${baseline.composite.toFixed(2)}` : "baseline not set"}
                  </small>
                </p>
                <Button kind="tertiary" onClick={() => open(s.id)}>
                  Open this plan
                </Button>
              </Tile>
            );
          })}
          <Tile className="recipient-tile">
            <p className="recipient-name">Unseen HR export</p>
            <p>Detect fields from values alone.</p>
            <p>
              <b>Finding</b>
              <br />
              c20 is an unkeyed hash of c05.
            </p>
            <p className="recipient-score">
              Not scored<small> detection fixture only</small>
            </p>
            <Button kind="tertiary" onClick={() => open("CS-S1")}>
              Explore the workbench
            </Button>
          </Tile>
        </div>
      </div>
    </section>
  );
}
