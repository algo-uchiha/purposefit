import { useEffect, useState } from "react";
import Lenis from "lenis";
import claimsData from "../../../docs/claims.json";
import { api, type LeaderboardRow } from "../api";
import type { Finding, Plan, Redact, Run, ScenariosResponse, Verify } from "../types";
import { Hero } from "./sections/Hero";
import { Problem } from "./sections/Problem";
import { HowItWorks } from "./sections/HowItWorks";
import { Recipients } from "./sections/Recipients";
import { Results } from "./sections/Results";
import { Trust } from "./sections/Trust";
import { FinalCTA } from "./sections/FinalCTA";
import "./landing.scss";
type Detection = {
  labels: {
    dataset: string;
    table: string;
    column: string;
    privacy_role: string;
    subtype: string;
    reason: string;
  }[];
};
async function loadDetection(): Promise<Detection> {
  const fixtures =
    (import.meta as ImportMeta & { env: { VITE_USE_FIXTURES?: string } }).env.VITE_USE_FIXTURES ===
    "true";
  const response = await fetch(
    fixtures ? "/fixtures/stage.detect.json" : "/api/runs/final-CS-S1/stages/detect",
  );
  if (!response.ok) throw new Error("Detection stage is not available");
  return response.json();
}
export default function Landing() {
  const [scenarios, setScenarios] = useState<ScenariosResponse>();
  const [rows, setRows] = useState<LeaderboardRow[]>([]);
  const [finding, setFinding] = useState<Finding>();
  const [plans, setPlans] = useState<Record<string, Plan>>({});
  const [verifications, setVerifications] = useState<Record<string, Verify>>({});
  const [redact, setRedact] = useState<Redact>();
  const [run, setRun] = useState<Run>();
  const [detection, setDetection] = useState<Detection>();
  useEffect(() => {
    let active = true;
    Promise.all([
      api.scenarios(),
      api.leaderboard(),
      api.findings(),
      api.plan("CS-S1"),
      api.plan("CS-S3"),
      api.verify("CS-S1"),
      api.verify("CS-S3"),
      api.redact("CS-S1"),
      api.run("CS-S1"),
      loadDetection(),
    ])
      .then(
        ([
          scenarioData,
          leaderboard,
          findings,
          s1Plan,
          s3Plan,
          s1Verify,
          s3Verify,
          redaction,
          runInfo,
          detect,
        ]) => {
          if (!active) return;
          setScenarios(scenarioData);
          setRows(leaderboard);
          setFinding(findings.find((item) => item.dataset === "unseen" && item.column === "c20"));
          setPlans({ "CS-S1": s1Plan, "CS-S3": s3Plan });
          setVerifications({ "CS-S1": s1Verify, "CS-S3": s3Verify });
          setRedact(redaction);
          setRun(runInfo);
          setDetection(detect);
        },
      )
      .catch(() => {});
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const narrow = window.matchMedia("(max-width: 767px)").matches;
    if (reduced || narrow)
      return () => {
        active = false;
      };
    const duration =
      Number.parseFloat(
        getComputedStyle(document.documentElement).getPropertyValue("--pf-lenis-duration"),
      ) || 1.05;
    const lenis = new Lenis({ duration, smoothWheel: true });
    const panels = Array.from(document.querySelectorAll<HTMLElement>(".landing-panel"));
    let scroll = window.scrollY;
    let frame = 0;
    lenis.on("scroll", (event) => {
      scroll = event.scroll;
    });
    const render = (time: number) => {
      lenis.raf(time);
      document.documentElement.style.setProperty(
        "--landing-progress",
        `${Math.min(1, scroll / (document.documentElement.scrollHeight - innerHeight)) * 100}%`,
      );
      panels.forEach((panel) => {
        const p = Math.max(0, Math.min(1, (scroll - panel.offsetTop) / innerHeight));
        panel.style.setProperty("--p", String(p));
      });
      frame = requestAnimationFrame(render);
    };
    frame = requestAnimationFrame(render);
    const observer = new IntersectionObserver(
      (entries) =>
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        }),
      { threshold: 0.12 },
    );
    document.querySelectorAll(".landing-content.reveal").forEach((node) => observer.observe(node));
    return () => {
      active = false;
      cancelAnimationFrame(frame);
      observer.disconnect();
      lenis.destroy();
      document.documentElement.style.removeProperty("--landing-progress");
    };
  }, []);
  const latest = (scenario: string, method: (value: string) => boolean) =>
    rows
      .filter((row) => row.scenario === scenario && method(row.method))
      .sort((a, b) => b.created_utc.localeCompare(a.created_utc))[0];
  const cs =
    scenarios?.scenarios.filter(
      (item) => item.dataset === "customer_service" && ["CS-S1", "CS-S3"].includes(item.id),
    ) ?? [];
  const open = (scenario = "CS-S1") => {
    window.location.hash = `#/workbench?scenario=${encodeURIComponent(scenario)}`;
  };
  const s1 = verifications["CS-S1"];
  const baseline = latest("CS-S1", (method) => method.startsWith("B2-k"));
  return (
    <main className="landing-page">
      {plans["CS-S1"] && s1 && (
        <Hero
          plan={plans["CS-S1"]}
          run={run}
          verify={s1}
          ours={latest("CS-S1", (m) => m === "purposefit")}
          baseline={baseline}
        />
      )}
      {plans["CS-S1"] && s1 && (
        <Problem finding={finding} plan={plans["CS-S1"]} verify={s1} baseline={baseline} />
      )}
      {plans["CS-S1"] && s1 && (
        <HowItWorks
          plan={plans["CS-S1"]}
          detect={detection}
          redact={redact}
          verify={s1}
          runId={run?.run_id}
        />
      )}
      {cs.length > 0 && <Recipients scenarios={cs} plans={plans} rows={rows} open={open} />}
      {s1 && <Results rows={rows} verify={s1} claims={claimsData} />}
      {plans["CS-S1"] && s1 && <Trust plan={plans["CS-S1"]} verify={s1} />}
      <FinalCTA />
    </main>
  );
}
