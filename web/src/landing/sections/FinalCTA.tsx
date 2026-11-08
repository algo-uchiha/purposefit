import { Button } from "@carbon/react";
export function FinalCTA() {
  return (
    <section className="landing-panel final-panel">
      <div className="landing-content reveal">
        <p className="landing-kicker">PurposeFit</p>
        <h2>See your own release plan.</h2>
        <div className="landing-actions">
          <Button href="#/workbench">Open the workbench</Button>
          <Button kind="secondary" href="https://github.com/algo-uchiha/purposefit">
            View the project on GitHub
          </Button>
        </div>
      </div>
      <footer className="landing-footer">
        <span>Built for the TrustED PETs Transformer challenge, Since AI Hackathon 2026</span>
        <a href="https://github.com/algo-uchiha/purposefit#readme">Read the README</a>
      </footer>
    </section>
  );
}
