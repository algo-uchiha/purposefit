import { Scan, DocumentTasks, Locked, TaskComplete } from "@carbon/icons-react";
const steps = [
  { icon: Scan, title: "Detect", text: "Finds what every column and sentence contains." },
  {
    icon: DocumentTasks,
    title: "Plan for the purpose",
    text: "Keeps only what the recipient's task needs.",
  },
  {
    icon: Locked,
    title: "Protect",
    text: "Pseudonymises keys, coarsens what identifies, removes identifiers from text.",
  },
  {
    icon: TaskComplete,
    title: "Verify",
    text: "Re-runs the organisers' attacks. No pass, no export.",
  },
];
export function HowItWorks() {
  return (
    <section className="landing-panel process-panel">
      <div className="landing-content reveal">
        <p className="landing-kicker">How it works</p>
        <h2>Each decision has a reason and a measured result</h2>
        <div className="process-grid">
          {steps.map(({ icon: Icon, title, text }, i) => (
            <article key={title}>
              <span className="process-number">0{i + 1}</span>
              <Icon size={28} />
              <h3>{title}</h3>
              <p>{text}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
