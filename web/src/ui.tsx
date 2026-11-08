import { useEffect, useState } from "react";
import {
  Header,
  HeaderName,
  HeaderGlobalBar,
  HeaderGlobalAction,
  SideNav,
  SideNavItems,
  SideNavLink,
  Content,
  Button,
  Tile,
  Tag,
  Table,
  TableHead,
  TableRow,
  TableHeader,
  TableBody,
  TableCell,
  InlineNotification,
  Toggle,
  ProgressIndicator,
  ProgressStep,
  Loading,
} from "@carbon/react";
import { Download, Compare, ArrowRight, ChevronLeft, Document } from "@carbon/icons-react";
import { api } from "./api";
import type { Finding, Plan, Redact, Report, Run, ScenariosResponse, Verify } from "./types";
import { TextScreen } from "./screens/Text";
import { VerifyScreen } from "./screens/Verify";
import { taskQuestion } from "./components/taskCopy";
const steps = ["Your data", "Choose protection", "Check the proof", "Download"];
const stepScreens = [0, 1, 3, 4];
const stepIndex = (screen: number) => (screen <= 1 ? screen : screen - 1);
const actionCopy: Record<string, string> = {
  hmac: "Replace with a code",
  drop: "Remove",
  generalize: "Group into ranges",
  redact: "Black out private words",
  keep: "Keep as is",
  suppress_k: "Hide rare groups",
  withhold_table: "Remove",
};
const roleCopy: Record<string, string> = {
  direct_identifier: "Points straight at a person",
  quasi_identifier: "Could point at someone when combined",
  free_text: "Free text",
};
const reasonCopy = (reason: string) =>
  reason
    .replaceAll(
      "joins released tables; the same keyed pseudonym in every table keeps the join",
      "The team needs to link calls from the same person, not know who they are.",
    )
    .replaceAll("used by CS-U1, CS-U3, CS-U4", "The team measures it.")
    .replaceAll("used by CS-U4", "The team measures it.")
    .replaceAll(
      "used by CS-U1, CS-U5; text kept for the task",
      "Names, IDs and health details are removed. The topic stays.",
    )
    .replaceAll(
      "train and eval marker; the model task chooses its training rows by it",
      "The team measures it.",
    )
    .replaceAll("technical identifier no task needs or joins on", "Not needed for this job")
    .replaceAll("direct identifier no task needs", "Not needed for this job")
    .replaceAll("free text no task needs", "Not needed for this job")
    .replaceAll("quasi-identifier no task needs", "Not needed for this job")
    .replaceAll(
      "row key no other table refers to; links to nothing outside this table, rows are matched by it",
      "The team measures it.",
    )
    .replaceAll("no task of this scenario uses this table", "Not needed for this job")
    .replaceAll("no task of this scenario uses it", "Not needed for this job")
    .replaceAll("no task needs", "Not needed for this job")
    .replaceAll("no task uses", "Not needed for this job")
    .replaceAll("technical identifier", "Technical field");
type CompareRow = {
  table: string;
  column: string;
  role?: string;
  subtype?: string;
  action: string;
  level?: string;
  reason: string;
  reasonA?: string;
  reasonB?: string;
  diff?: boolean;
};
export default function App() {
  const [data, setData] = useState<ScenariosResponse>();
  const initialScenario = new URLSearchParams(window.location.hash.split("?")[1] ?? "").get(
    "scenario",
  );
  const [scenarioId, setScenarioId] = useState(initialScenario ?? "CS-S1");
  const [screen, setScreen] = useState(0);
  const [compare, setCompare] = useState(false);
  const [turn, setTurn] = useState(0);
  const [plans, setPlans] = useState<Record<string, Plan>>({});
  const [redact, setRedact] = useState<Redact>();
  const [verify, setVerify] = useState<Verify>();
  const [report, setReport] = useState<Report>();
  const [run, setRun] = useState<Run>();
  const [findings, setFindings] = useState<Finding[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    api
      .scenarios()
      .then((scenarios) => {
        setData(scenarios);
        if (!initialScenario || !scenarios.scenarios.some((item) => item.id === initialScenario)) {
          setScenarioId(
            scenarios.scenarios.find((item) => item.dataset === "customer_service")?.id ??
              scenarios.scenarios[0]?.id ??
              "Unavailable",
          );
        }
      })
      .catch(() => setError("Can't reach the server. Is the demo running?"));
    api
      .findings()
      .then(setFindings)
      .catch(() => {});
  }, []);
  useEffect(() => {
    if (!data) return;
    let live = true;
    const fetchScenario = async (id: string) => {
      const [p, r, v, rep, ru] = await Promise.all([
        api.plan(id),
        api.redact(id),
        api.verify(id),
        api.report(id),
        api.run(id),
      ]);
      if (!live) return;
      setPlans((x) => ({ ...x, [id]: p }));
      if (id === scenarioId) {
        setRedact(r);
        setVerify(v);
        setReport(rep);
        setRun(ru);
        setTurn(0);
      }
    };
    fetchScenario(scenarioId).catch(() => live && setError("Can't reach the server. Is the demo running?"));
    if (compare) {
      const other = scenarioId === "CS-S1" ? "CS-S3" : "CS-S1";
      fetchScenario(other).catch(() => {});
    }
    return () => {
      live = false;
    };
  }, [data, scenarioId, compare]);
  const current = data?.scenarios.find((x) => x.id === scenarioId);
  const policies = plans[scenarioId]?.policies ?? [];
  const withheldCount = policies.filter(
    (policy) => policy.action === "withhold_table" && policy.table === "customers",
  ).length;
  const planRows: CompareRow[] = compare
    ? mergePlans(plans["CS-S1"], plans["CS-S3"])
    : [
        ...policies
          .filter((policy) => policy.action !== "withhold_table")
          .map((policy) => ({
            ...policy,
            role: typeof policy.params.role === "string" ? policy.params.role : undefined,
          }) as CompareRow),
        ...(withheldCount
          ? [
              {
                table: "Customers",
                column: `${withheldCount} fields`,
                action: "withhold_table",
                reason: "Not needed for this job",
              },
            ]
          : []),
      ];
  function scenarioSwitch(id: string) {
    setScenarioId(id);
    setCompare(false);
  }
  return (
    <>
      <Header aria-label="PurposeFit">
        <HeaderName href="#/" prefix="">
          PurposeFit
        </HeaderName>
        <HeaderGlobalBar>
          <span className="header-context">
            customer_service <span aria-hidden="true">/</span> {scenarioId}
          </span>
          <HeaderGlobalAction aria-label="Download safe copy" onClick={() => setScreen(4)}>
            <Download />
          </HeaderGlobalAction>
        </HeaderGlobalBar>
      </Header>
      <SideNav aria-label="Main navigation" isRail>
        <SideNavItems>
          {steps.map((s, i) => (
            <SideNavLink
              key={s}
              isActive={stepIndex(screen) === i}
              onClick={() => setScreen(stepScreens[i])}
            >
              {s}
            </SideNavLink>
          ))}
        </SideNavItems>
      </SideNav>
      <Content className="app-content">
        <div className="mobile-steps">
          <ProgressIndicator currentIndex={stepIndex(screen)} spaceEqually>
            {steps.map((s) => (
              <ProgressStep key={s} label={s} />
            ))}
          </ProgressIndicator>
        </div>
        <div className="topline">
          <div>
            <p className="eyebrow">PurposeFit / customer_service / {scenarioId}</p>
            <h1>{steps[stepIndex(screen)]}</h1>
          </div>
          <div className="step-actions">
            {screen === 1 && (
              <Button
                kind={compare ? "secondary" : "tertiary"}
                renderIcon={Compare}
                onClick={() => setCompare((x) => !x)}
              >
                {compare ? "Close comparison" : "Compare plans"}
              </Button>
            )}
            {screen > 0 && (
              <Button kind="ghost" renderIcon={ChevronLeft} onClick={() => setScreen(Math.max(0, screen - 1))}>
                Back
              </Button>
            )}
            {screen < 4 && (
              <Button
                kind="primary"
                renderIcon={ArrowRight}
                disabled={screen === 3 && !verify?.gate.passed}
                title={screen === 3 && !verify?.gate.passed ? "Locked until every check passes." : undefined}
                onClick={() => setScreen(screen + 1)}
              >
                {["Find what's private", "Protect this copy", "Continue to the proof", "Download safe copy"][screen]}
              </Button>
            )}
            {screen === 3 && !verify?.gate.passed && (
              <span className="small muted">Locked until every check passes.</span>
            )}
          </div>
        </div>
        {error && (
          <InlineNotification
            kind="error"
            title="Can't reach the server. Is the demo running?"
            lowContrast
          />
        )}
        {!data && <Loading description="Working on it. Large files take a moment." />}
        {screen === 0 && current && (
          <>
            <div className="scenario-top">
              <div>
                <h2>Start with an example.</h2>
                <p className="muted">
                  This is the data PurposeFit will protect. Look it over, then we find what's private.
                </p>
              </div>
            </div>
            <div className="scenario-grid">
              {data!.scenarios
                .filter((s) => s.dataset === "customer_service")
                .map((s) => (
                  <Tile
                    key={s.id}
                    className={`scenario-tile ${scenarioId === s.id ? "active" : ""}`}
                    onClick={() => scenarioSwitch(s.id)}
                  >
                    <div className="tile-top">
                      <Tag type={scenarioId === s.id ? "blue" : "cool-gray"}>{s.id}</Tag>
                      <span className="tile-indicator">
                        {scenarioId === s.id ? "Selected" : "Select"}
                      </span>
                    </div>
                    <h3>{s.title}</h3>
                    <p>
                      <strong>Recipient</strong>
                      <br />
                      {s.recipient}
                    </p>
                    <p>
                      <strong>Purpose</strong>
                      <br />
                      {s.purpose}
                    </p>
                    <div className="task-list">
                      {s.utility_tasks.map((t) => (
                        <p key={t.id}>
                          {taskQuestion(t.id, t.description)}
                        </p>
                      ))}
                    </div>
                    <Button
                      kind="ghost"
                      onClick={(e) => {
                        e.stopPropagation();
                        scenarioSwitch(s.id);
                        setScreen(1);
                      }}
                    >
                      Choose who the copy is for <ArrowRight />
                    </Button>
                  </Tile>
                ))}
            </div>
            <div className="notice-line">
              <span className="blue-rule" />
              Uploading your own file is not built yet. This demo uses prepared example data.
            </div>
          </>
        )}
        {screen === 1 && (
          <>
            <div className="section-intro">
              <div>
                <h2>{compare ? "Compare release plans" : "Who is this copy for?"}</h2>
                <p>
                  We suggest what to do with each column. You can change any of them.
                </p>
              </div>
            </div>
            {compare && (
              <div className="compare-controls">
                <Button
                  size="sm"
                  kind={scenarioId === "CS-S1" ? "primary" : "secondary"}
                  onClick={() => scenarioSwitch("CS-S1")}
                >
                  {data?.scenarios.find((x) => x.id === "CS-S1")?.title ?? "Unavailable"}
                </Button>
                <Button
                  size="sm"
                  kind={scenarioId === "CS-S3" ? "primary" : "secondary"}
                  onClick={() => scenarioSwitch("CS-S3")}
                >
                  {data?.scenarios.find((x) => x.id === "CS-S3")?.title ?? "Unavailable"}
                </Button>
              </div>
            )}
            <div className="plan-layout">
              <div className="table-wrap">
                <Table size="lg" aria-label="Field policy plan">
                  <TableHead>
                    <TableRow>
                      {["Table", "Column", "Role", "Action", "Reason", "Details"].map((x) => (
                        <TableHeader key={x}>{x}</TableHeader>
                      ))}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {planRows.map((p, i) => (
                      <TableRow
                        key={`${p.table}.${p.column}.${i}`}
                        className={p.diff ? "diff-row" : ""}
                      >
                        <TableCell>{p.table}</TableCell>
                        <TableCell className="mono">{p.column}</TableCell>
                        <TableCell>
                          {p.role ? (
                            <Tag
                              type={
                                p.role === "direct_identifier"
                                  ? "red"
                                  : p.role === "quasi_identifier"
                                    ? "purple"
                                    : "cool-gray"
                              }
                            >
                              {roleCopy[p.role] ?? "Safe on its own"}
                            </Tag>
                          ) : (
                            "Safe on its own"
                          )}
                        </TableCell>
                        <TableCell>
                          <Tag
                            type={
                              p.action === "drop" || p.action === "withhold_table"
                                ? "cool-gray"
                                : p.action === "hmac"
                                  ? "blue"
                                  : p.action === "redact"
                                    ? "green"
                                    : "teal"
                            }
                          >
                            {actionCopy[p.action] ?? "Keep as is"}
                          </Tag>
                        </TableCell>
                        <TableCell>
                          {compare ? (
                            <>
                              <span className="reason-side">
                                <b>
                                  {data?.scenarios.find((x) => x.id === "CS-S1")?.title ??
                                    "Unavailable"}
                                </b>{" "}
                                {reasonCopy(p.reasonA || "Not needed for this job")}
                              </span>
                              <span className="reason-side">
                                <b>
                                  {data?.scenarios.find((x) => x.id === "CS-S3")?.title ??
                                    "Unavailable"}
                                </b>{" "}
                                {reasonCopy(p.reasonB || "Not needed for this job")}
                              </span>
                            </>
                          ) : (
                            reasonCopy(p.reason)
                          )}
                        </TableCell>
                        <TableCell>
                          <details>
                            <summary>Details</summary>
                            <p>Subtype: {p.subtype ?? "Unavailable"}</p>
                            <p>Level: {p.level ?? "Unavailable"}</p>
                          </details>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              <aside className="side-panel">
                <div className="panel-heading">
                  <h3>Plan summary</h3>
                  <Tag type="blue">{scenarioId}</Tag>
                </div>
                <p>
                  <strong>Released tables</strong>
                </p>
                <div className="table-pills">
                  {(plans[scenarioId]?.released_tables ?? []).map((t) => (
                    <Tag key={t} type="cool-gray">
                      {t}
                    </Tag>
                  ))}
                </div>
                <p className="small muted">
                  {run?.run_id} · {run?.status}
                </p>
                <hr />
                <h3>Detection findings</h3>
                {findings.length ? (
                  findings.map((f, i) => (
                    <div className="finding" key={i}>
                      {findingText(f)}
                    </div>
                  ))
                ) : (
                  <p className="muted">No findings for this dataset.</p>
                )}
              </aside>
            </div>
          </>
        )}
        {screen === 2 && (
          <TextScreen
            data={redact}
            turn={turn}
            setTurn={setTurn}
          />
        )}
        {screen === 3 && verify && <VerifyScreen data={verify} />}
        {screen === 4 && (
          <div className="export-grid">
            <Tile>
              <div className="export-icon">
                <Download size={24} />
              </div>
              <h2>Your safe copy is ready.</h2>
              <p>Same rows, same usefulness, nobody to point at.</p>
              <p>The zip contains the released tables as CSV, a policy card, and the plan report.</p>
              <p className="small muted">Uploading your own file is not built yet.</p>
              <p className="muted small">
                Every check must pass before the download opens.
              </p>
              <Button
                disabled={!verify?.gate.passed}
                renderIcon={Download}
                onClick={() => (window.location.href = `/api/runs/${run?.run_id}/export`)}
              >
                Download safe copy
              </Button>
            </Tile>
            <Tile>
              <div className="export-icon">
                <Document size={24} />
              </div>
              <h2>Read the report</h2>
              <p>This report says what was removed, what was changed and what was kept in this copy, and why.</p>
              <p className="muted small">The policy card downloads as JSON.</p>
              <Button
                kind="secondary"
                disabled={!report?.policy_card}
                renderIcon={Download}
                onClick={() => downloadPolicy(report?.policy_card)}
              >
                Read the report
              </Button>
            </Tile>
            <InlineNotification
              kind="info"
              title="Controller materials stay with the data controller"
              subtitle="Row maps and keys stay with the data controller and are never exported."
              lowContrast
              hideCloseButton
            />
          </div>
        )}
        {run && (
          <footer>
            <span>
              PurposeFit <span className="footer-dot">·</span> {scenarioId}
            </span>
            <span>
              Run {run.run_id} <span className="footer-dot">·</span> {run.status}
            </span>
          </footer>
        )}
      </Content>
    </>
  );
}
function mergePlans(a?: Plan, b?: Plan): CompareRow[] {
  const map = new Map<
    string,
    {
      table: string;
      column: string;
      role?: string;
      subtype?: string;
      action: string;
      level?: string;
      reasonA?: string;
      reasonB?: string;
      diff: boolean;
    }
  >();
  for (const [p, side] of [
    [a, "A"],
    [b, "B"],
  ] as const) {
    for (const x of p?.policies ?? []) {
      const k = `${x.table}.${x.column}`;
      const item = map.get(k) ?? {
        table: x.table,
        column: x.column,
        action: x.action,
        diff: false,
      };
      if (side === "A") {
        item.role = String(x.params.role ?? "");
        item.subtype = String(x.params.subtype ?? "");
        item.action = x.action;
        item.level = x.params.level ? String(x.params.level) : undefined;
        item.reasonA = x.reason;
      } else {
        item.reasonB = x.reason;
        item.diff = item.action !== x.action;
      }
      map.set(k, item);
    }
  }
  return [...map.values()].map((x) => ({ ...x, reason: `${x.reasonA ?? ""} ${x.reasonB ?? ""}` }));
}
function findingText(f: Finding) {
  return f.kind === "unkeyed_hash"
    ? `Column ${f.column} is an unkeyed ${f.algorithm} of ${f.source_column} (${f.variant}). Reversible by enumeration.`
    : `Column ${f.column} agrees with ${f.source_column} in ${(100 * (f.agreement ?? 0)).toFixed(0)} % of rows.`;
}
function downloadPolicy(value: unknown) {
  if (!value) return;
  const blob = new Blob([typeof value === "string" ? value : JSON.stringify(value, null, 2)], {
    type: "application/json",
  });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "purposefit-policy-card.json";
  a.click();
  URL.revokeObjectURL(a.href);
}
