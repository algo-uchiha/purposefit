import { useEffect, useState } from "react";
import Lenis from "lenis";
import { api, type LeaderboardRow } from "../api";
import type { Finding, Plan, ScenariosResponse, Verify } from "../types";
import { Hero } from "./sections/Hero";
import { Problem } from "./sections/Problem";
import { HowItWorks } from "./sections/HowItWorks";
import { Recipients } from "./sections/Recipients";
import { Results } from "./sections/Results";
import "./landing.scss";

export default function Landing() {
  const [scenarios, setScenarios] = useState<ScenariosResponse>();
  const [leaderboard, setLeaderboard] = useState<LeaderboardRow[]>([]);
  const [finding, setFinding] = useState<Finding>();
  const [plans, setPlans] = useState<Record<string, Plan>>({});
  const [verifications, setVerifications] = useState<Record<string, Verify>>({});
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
    ])
      .then(([scenarioData, rows, findings, s1Plan, s3Plan, s1Verify, s3Verify]) => {
        if (!active) return;
        setScenarios(scenarioData);
        setLeaderboard(rows);
        setFinding(findings.find((item) => item.dataset === "unseen" && item.column === "c20"));
        setPlans({ "CS-S1": s1Plan, "CS-S3": s3Plan });
        setVerifications({ "CS-S1": s1Verify, "CS-S3": s3Verify });
      })
      .catch(() => {});
    const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReduced)
      return () => {
        active = false;
      };
    const lenis = new Lenis({ duration: 1.05, smoothWheel: true });
    let frame = 0;
    const animate = (time: number) => {
      lenis.raf(time);
      frame = requestAnimationFrame(animate);
    };
    frame = requestAnimationFrame(animate);
    const observer = new IntersectionObserver(
      (entries) =>
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        }),
      { threshold: 0.18 },
    );
    document.querySelectorAll(".reveal").forEach((node) => observer.observe(node));
    return () => {
      active = false;
      cancelAnimationFrame(frame);
      observer.disconnect();
      lenis.destroy();
    };
  }, []);
  const csScenarios =
    scenarios?.scenarios.filter(
      (item) => item.dataset === "customer_service" && ["CS-S1", "CS-S3"].includes(item.id),
    ) ?? [];
  const latest = (scenario: string, method: string) =>
    leaderboard
      .filter(
        (x) =>
          x.scenario === scenario &&
          (method === "purposefit" ? x.method === method : x.method.startsWith("B2-k")),
      )
      .sort((a, b) => b.created_utc.localeCompare(a.created_utc))[0];
  const open = (scenario = "CS-S1") => {
    window.location.hash = `#/workbench?scenario=${encodeURIComponent(scenario)}`;
  };
  const s1 = latest("CS-S1", "purposefit");
  const b1 = latest("CS-S1", "B2-k");
  const unseenPlan: Record<string, Plan> = plans;
  return (
    <main className="landing-page">
      <Hero
        ours={s1}
        baseline={b1}
        scenarioTitle={
          csScenarios.find((x) => x.id === "CS-S1")?.title ??
          "Support transcripts to an external AI vendor"
        }
      />
      <Problem finding={finding} baseline={b1} verify={verifications["CS-S1"]} />
      <HowItWorks />
      <Recipients scenarios={csScenarios} plans={unseenPlan} rows={leaderboard} open={open} />
      <Results one={verifications["CS-S1"]} two={verifications["CS-S3"]} open={() => open()} />
    </main>
  );
}
