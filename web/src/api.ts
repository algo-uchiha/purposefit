import type { Finding, Plan, Redact, Report, Run, ScenariosResponse, Verify } from "./types";
const fixtures =
  (import.meta as ImportMeta & { env: { VITE_USE_FIXTURES?: string } }).env.VITE_USE_FIXTURES ===
  "true";
async function get<T>(path: string, file: string): Promise<T> {
  if (fixtures) {
    const response = await fetch(`/fixtures/${file}`);
    if (!response.ok) throw new Error(`Could not load fixture ${file}`);
    return response.json() as Promise<T>;
  }
  const response = await fetch(`/api${path}`);
  if (!response.ok) throw new Error(`API request failed: ${response.status}`);
  return response.json() as Promise<T>;
}
export const api = {
  scenarios: () => get<ScenariosResponse>("/scenarios", "scenarios.json"),
  run: (id: string) => get<Run>(`/runs/final-${id}`, `run.${id}.json`),
  plan: (id: string) => get<Plan>(`/runs/final-${id}/stages/plan`, `plan.${id}.json`),
  redact: (id: string) => get<Redact>(`/runs/final-${id}/stages/redact`, `stage.redact.${id}.json`),
  verify: (id: string) => get<Verify>(`/runs/final-${id}/stages/verify`, `stage.verify.${id}.json`),
  report: (id: string) => get<Report>(`/runs/final-${id}/stages/report`, `stage.report.${id}.json`),
  // The API has no /findings route: findings are part of a run's detect stage.
  findings: () =>
    fixtures
      ? get<Finding[]>("/findings", "findings.json")
      : get<{ findings: Finding[] }>("/runs/final-CS-S1/stages/detect", "").then((d) => d.findings),
  leaderboard: () => get<LeaderboardRow[]>("/leaderboard", "leaderboard.json"),
};

export type LeaderboardRow = {
  created_utc: string;
  run_id: string;
  dataset: string;
  scenario: string;
  method: string;
  privacy: number;
  utility: number;
  composite: number;
  utility_tasks: Record<string, number | null>;
};
