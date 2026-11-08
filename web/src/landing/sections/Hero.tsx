import { Button } from "@carbon/react";
import type { LeaderboardRow } from "../../api";
export function Hero({
  ours,
  baseline,
  scenarioTitle,
}: {
  ours?: LeaderboardRow;
  baseline?: LeaderboardRow;
  scenarioTitle: string;
}) {
  return (
    <section className="landing-panel landing-hero" data-panel="hero">
      <div className="landing-content reveal">
        <p className="landing-brand">PurposeFit</p>
        <h1>
          Share data for a purpose.
          <br />
          Prove it is safe to share.
        </h1>
        <p className="landing-lede">
          PurposeFit decides what each recipient needs, protects the rest, and re-runs real privacy
          attacks before anything leaves your hands.
        </p>
        <div className="landing-actions">
          <Button
            onClick={() =>
              document.getElementById("problem")?.scrollIntoView({ behavior: "smooth" })
            }
          >
            See how it works
          </Button>
          <Button kind="secondary" href="#/workbench">
            Open the workbench
          </Button>
        </div>
      </div>
      <p className="proof-line">
        {scenarioTitle}: overall score {ours ? ours.composite.toFixed(2) : "Not set"} vs{" "}
        {baseline ? baseline.composite.toFixed(2) : "Not set"} for the classic baseline · pets-eval
      </p>
    </section>
  );
}
