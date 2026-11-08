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
  run: (id: string) => get<Run>(`/runs/p4-${id}`, `run.${id}.json`),
  plan: (id: string) => get<Plan>(`/runs/p4-${id}/stages/plan`, `plan.${id}.json`),
  redact: (id: string) => get<Redact>(`/runs/p4-${id}/stages/redact`, `stage.redact.${id}.json`),
  verify: (id: string) => get<Verify>(`/runs/p4-${id}/stages/verify`, `stage.verify.${id}.json`),
  report: (id: string) => get<Report>(`/runs/p4-${id}/stages/report`, `stage.report.${id}.json`),
  findings: () => get<Finding[]>("/findings", "findings.json"),
};
