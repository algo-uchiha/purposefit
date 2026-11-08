import { useEffect, useState } from "react";
import { ArrowRight, DocumentTasks, Locked, Search, TaskComplete } from "@carbon/icons-react";
import claimsData from "../../../docs/claims.json";
import { api, type LeaderboardRow } from "../api";
import type { Plan, Redact, Scenario, ScenariosResponse, Verify } from "../types";
import "./landing.scss";
import "../styles/workbench-v3.scss";

type LandingData = {
  scenarios: ScenariosResponse;
  leaderboard: LeaderboardRow[];
  plans: Record<string, Plan>;
  redact: Record<string, Redact>;
  verify: Record<string, Verify>;
};
type DataTables = Record<
  string,
  {
    direct_identifiers_retained?: Record<string, number>;
    k_anonymity?: { min_k?: number };
    free_text?: Record<string, { identifying_leakage_rate?: number }>;
  }
>;
const claims = claimsData as Record<string, string>;
const latest = (rows: LeaderboardRow[], scenario: string, method: string) =>
  rows
    .filter((row) => row.scenario === scenario && row.method === method)
    .sort((a, b) => b.created_utc.localeCompare(a.created_utc))[0];

function Logo() {
  return (
    <a className="pf-logo" href="#/" aria-label="PurposeFit home">
      <span className="pf-logo-mark" aria-hidden="true">
        <i />
        <i />
      </span>
      <span>PurposeFit</span>
    </a>
  );
}

function TextWithSpans({ text, spans }: { text: string; spans: Redact["turns"][number]["spans"] }) {
  if (!spans.length) return <>{text}</>;
  const parts: React.ReactNode[] = [];
  let cursor = 0;
  spans
    .slice()
    .sort((a, b) => a.start - b.start)
    .forEach((span, index) => {
      if (span.start < cursor || span.end > text.length) return;
      if (span.start > cursor) parts.push(text.slice(cursor, span.start));
      parts.push(
        <mark className="sensitive-span" key={`${span.start}-${index}`}>
          {text.slice(span.start, span.end)}
        </mark>,
      );
      cursor = span.end;
    });
  if (cursor < text.length) parts.push(text.slice(cursor));
  return <>{parts}</>;
}

function SafeText({ text }: { text: string }) {
  const pieces = text.split(/(\[[A-Z_ ]+\])/g);
  return (
    <>
      {pieces.map((piece, index) =>
        piece.startsWith("[") && piece.endsWith("]") ? (
          <mark className="safe-span" key={index}>
            {piece}
          </mark>
        ) : (
          piece
        ),
      )}
    </>
  );
}

function HeroPanel() {
  return (
    <section className="v3-panel v3-hero">
      <Blobs variant="one" />
      <div className="hero-copy">
        <p className="challenge-pill">Built for the TrustED PETs challenge, Since AI Hackathon 2026</p>
        <h1>Send the data. Keep the details.</h1>
        <p className="hero-line">
          Whenever you share data, the other side only needs part of it. PurposeFit makes a copy
          with just that part and checks it before it leaves.
        </p>
        <div className="button-row">
          <a className="button-primary" href="#/workbench">
            Try the demo <ArrowRight size={18} />
          </a>
          <a className="button-secondary" href="#changes">
            See what changes
          </a>
        </div>
        <p className="hero-note">
          Version 1 runs on prepared example data. Uploading your own files is next.
        </p>
      </div>
      <ScrollHint />
    </section>
  );
}

function ScorePanel({ data }: { data: LandingData }) {
  const baseline0 = latest(data.leaderboard, "CS-S1", "B0 (rerun)");
  const baselineK = latest(data.leaderboard, "CS-S1", "B2-k (rerun)");
  const purposefit = latest(data.leaderboard, "CS-S1", "purposefit");
  const bars = [
    {
      label: "Shared as it is",
      value: baseline0?.composite,
      color: "standard",
    },
    {
      label: "Best standard approach",
      value: baselineK?.composite,
      color: "standard",
    },
    {
      label: "PurposeFit",
      value: purposefit?.composite,
      color: "purposefit",
    },
  ];
  return (
    <section id="score" className="v3-panel v3-score">
      <Blobs variant="one" />
      <div className="panel-heading-v3 score-heading">
        <h2>Hide the details. Keep the value.</h2>
        <p>
          Hiding everything makes data safe but useless. Hiding nothing makes it useful but risky.
          PurposeFit scores {purposefit?.composite.toFixed(2) ?? "Unavailable"} out of 1 on the
          challenge data. The best standard method scores {baselineK?.composite.toFixed(2) ?? "Unavailable"}.
        </p>
      </div>
      <div className="score-visual" aria-label="CS-S1 combined score comparison">
        <div className="score-visual-head">
          <span>One release, compared</span>
          <span>{data.verify["CS-S1"].scenario_id} · combined score</span>
        </div>
        <div className="score-bars">
          {bars.map((bar) => (
            <div className={`score-bar-column ${bar.color}`} key={bar.label}>
              <strong>{bar.value === undefined ? "Unavailable" : bar.value.toFixed(4)}</strong>
              <div className="score-bar-track">
                <div
                  className="score-bar"
                  style={{ height: `${Math.max((bar.value ?? 0) * 100, 1)}%` }}
                />
              </div>
              <b>{bar.label}</b>
            </div>
          ))}
        </div>
      <p className="source-note">
        Score on the challenge's customer service data. It counts how well people are protected and
        how useful the data stays.
      </p>
      </div>
      <ScrollHint />
    </section>
  );
}

function ChangesPanel({ data }: { data: LandingData }) {
  const original = data.redact["CS-S1"].turns[0];
  const scenarioA = data.scenarios.scenarios.find((scenario) => scenario.id === "CS-S1");
  const scenarioB = data.scenarios.scenarios.find((scenario) => scenario.id === "CS-S2");
  const safeA = original;
  const safeB =
    data.redact["CS-S2"].turns.find((turn) => turn.record_id === original.record_id) ??
    data.redact["CS-S2"].turns[0];
  return (
    <section id="changes" className="v3-panel v3-changes">
      <Blobs variant="two" />
      <div className="panel-heading-v3">
        <p className="section-label">What changes</p>
        <h2>Everyone gets their own copy.</h2>
        <p>
          The analytics team doesn't need names. An outside vendor doesn't need ages. Each person
          gets only what their job needs.
        </p>
      </div>
      <div className="copy-flow">
        <article className="record-card original-card">
          <div className="card-heading">
            <span className="step-number" aria-hidden="true" />
            <div>
              <h3>The original record</h3>
            </div>
          </div>
          <p>
            <TextWithSpans text={original.original_text} spans={original.spans} />
          </p>
          <span className="legend-red" aria-hidden="true" />
        </article>
        <div className="flow-arrow" aria-hidden="true">
          <ArrowRight size={28} />
        </div>
        <div className="safe-copies">
          {[
            { scenario: scenarioB, turn: safeB },
            { scenario: scenarioA, turn: safeA },
          ].map(
            ({ scenario, turn }) =>
              scenario &&
              turn && (
                <article className="record-card safe-card" key={scenario.id}>
                  <div className="card-heading">
                    <div>
                      <h3>{scenario.id === "CS-S1" ? "Copy for an outside vendor" : "Copy for the analytics team"}</h3>
                    </div>
                  </div>
                  <p>
                    <SafeText text={turn.protected_text} />
                  </p>
                  <span className="legend-mint" aria-hidden="true" />
                </article>
              ),
          )}
        </div>
      </div>
      <p className="source-note">Made-up example.</p>
      <ScrollHint />
    </section>
  );
}

const steps = [
  {
    icon: Search,
    title: "Spot the private bits",
    detail:
      "Finds names, ID numbers, birth dates, places and health details, in tables and in what people said on calls.",
  },
  {
    icon: DocumentTasks,
    title: "Ask what it's for",
    detail: "Who gets the copy, and what will they do with it? That decides what stays.",
  },
  {
    icon: Locked,
    title: "Hide what isn't needed",
    detail:
      "Names become codes. Exact dates become ranges. Private words in call text are blacked out.",
  },
  {
    icon: TaskComplete,
    title: "Check before it leaves",
    detail: "Runs the privacy checks and writes a short report anyone can read.",
  },
];
function ProcessPanel() {
  return (
    <section id="process" className="v3-panel v3-process">
      <Blobs variant="three" />
      <div className="panel-heading-v3">
        <p className="section-label">How it works</p>
        <h2>Four steps. No black box.</h2>
        <p>Open a file. We show what we found, what we changed and why.</p>
      </div>
      <div className="process-cards">
        {steps.map(({ icon: Icon, title, detail }) => (
          <article className="process-card" key={title}>
            <div className="process-icon">
              <Icon size={24} />
            </div>
            <h3>{title}</h3>
            <p>{detail}</p>
          </article>
        ))}
      </div>
      <ScrollHint />
    </section>
  );
}

function SafetyPanel({ data }: { data: LandingData }) {
  const verify = data.verify["CS-S1"];
  const tables = (verify.ours as typeof verify.ours & { tables?: DataTables }).tables ?? {};
  const hasDirectData = Object.values(tables).some(
    (table) => table.direct_identifiers_retained !== undefined,
  );
  const direct = Object.values(tables)
    .flatMap((table) => Object.values(table.direct_identifiers_retained ?? {}))
    .reduce((sum, value) => sum + value, 0);
  const healthBefore = claims["health.train_before"];
  const healthAfter = claims["health.train_after"];
  const purposeFitLeakage = verify.ours.risk_components["turns: free-text identifier leakage"];
  const crowdSize = verify.gate.checks.find((check) => check.id === "k_anonymity")?.threshold;
  const stats = [
    {
      value: hasDirectData ? String(direct) : "Unavailable",
      label: "names or ID numbers left",
    },
    {
      value: "",
      label: `Every person hides in a crowd of at least ${crowdSize ?? "Unavailable"}`,
    },
    {
      value:
        purposeFitLeakage == null ? "Unavailable" : `${(purposeFitLeakage * 100).toFixed(1)}%`,
      label: "of identifying details left in call text",
    },
    {
      value: healthAfter ?? "Unavailable",
      label: `health details left in call text, down from ${healthBefore ?? "Unavailable"}`,
    },
  ];
  return (
    <section id="safety" className="v3-panel v3-safety">
      <Blobs variant="four" />
      <div className="panel-heading-v3">
        <p className="section-label">Safety</p>
        <h2>Locked until it's safe.</h2>
        <p>The download button stays off until every check passes.</p>
      </div>
      <div className="safety-stats">
        {stats.map((item) => (
          <article className="stat-card" key={item.label}>
            {item.value && <strong>{item.value}</strong>}
            <span>{item.label}</span>
          </article>
        ))}
      </div>
      <p className="source-note">Measured on the challenge's practice data.</p>
      <p className="honesty-note">
        Version 1 works on prepared files. Database connections and user accounts are not built yet.
      </p>
      <ScrollHint />
    </section>
  );
}

function DemoPanel({ scenarios }: { scenarios: Scenario[] }) {
  const cards = [
    {
      title: "1. Look at the data",
      text: "The customer service data is already loaded.",
      href: "#/workbench",
    },
    {
      title: "2. Choose who it's for",
      text: scenarios.find((scenario) => scenario.id === "CS-S1")?.recipient ?? "Unavailable",
      href: "#/workbench",
    },
    {
      title: "3. Check and download",
      text: scenarios.find((scenario) => scenario.id === "CS-S2")?.recipient ?? "Unavailable",
      href: "#/workbench",
    },
  ];
  return (
    <section id="demo" className="v3-panel v3-demo">
      <Blobs variant="five" />
      <div className="panel-heading-v3">
        <p className="section-label">Try PurposeFit</p>
        <h2>See it work on real data.</h2>
        <p>
          Open the demo. The customer service data is already loaded. Pick who the copy is for and
          watch it change.
        </p>
      </div>
      <div className="demo-cards">
        {cards.map((card) => (
          <a className="demo-card" href={card.href} key={card.title}>
            <h3>{card.title}</h3>
            <p>{card.text}</p>
            <ArrowRight size={18} />
          </a>
        ))}
      </div>
      <a className="button-primary demo-cta" href="#/workbench">
        Try the demo <ArrowRight size={18} />
      </a>
      <footer className="v3-footer">
        <Logo />
        <span>Built for the TrustED PETs Transformer challenge, Since AI Hackathon 2026</span>
        <a href="https://github.com/algo-uchiha/purposefit">GitHub</a>
      </footer>
    </section>
  );
}

function Blobs({ variant }: { variant: string }) {
  return (
    <div className={`ambient-blobs blobs-${variant}`} aria-hidden="true">
      <i />
      <i />
      <i />
      <i />
    </div>
  );
}
function ScrollHint() {
  return (
    <span className="scroll-hint" aria-hidden="true">
      Scroll to explore <span>↓</span>
    </span>
  );
}

export default function Landing() {
  const [data, setData] = useState<LandingData>();
  const [error, setError] = useState("");
  useEffect(() => {
    let alive = true;
    Promise.all([
      api.scenarios(),
      api.leaderboard(),
      api.plan("CS-S1"),
      api.plan("CS-S2"),
      api.redact("CS-S1"),
      api.redact("CS-S2"),
      api.verify("CS-S1"),
      api.verify("CS-S3"),
    ])
      .then(([scenarios, leaderboard, plan1, plan2, redact1, redact2, verify1, verify3]) => {
        if (!alive) return;
        setData({
          scenarios,
          leaderboard,
          plans: { "CS-S1": plan1, "CS-S2": plan2 },
          redact: { "CS-S1": redact1, "CS-S2": redact2 },
          verify: { "CS-S1": verify1, "CS-S3": verify3 },
        });
      })
      .catch(
        (reason: unknown) =>
          alive &&
          setError(reason instanceof Error ? reason.message : "Could not load the example data."),
      );
    return () => {
      alive = false;
    };
  }, []);
  return (
    <main className="landing-v3">
      <header className="v3-nav">
        <Logo />
        <nav aria-label="Main navigation">
          <a href="#changes">What changes</a>
          <a href="#process">How it works</a>
          <a href="#safety">Safety</a>
        </nav>
        <a className="nav-cta" href="#/workbench">
          Try the demo <ArrowRight size={16} />
        </a>
      </header>
      {!data && <div className="landing-loading">{error || "Loading the real example data"}</div>}
      {data && (
        <>
          <HeroPanel />
          <ScorePanel data={data} />
          <ChangesPanel data={data} />
          <ProcessPanel />
          <SafetyPanel data={data} />
          <DemoPanel scenarios={data.scenarios.scenarios} />
        </>
      )}
    </main>
  );
}
