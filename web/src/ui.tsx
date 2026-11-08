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
  Dropdown,
  Tile,
  Tag,
  Search,
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
const steps = ["Scenario", "Plan", "Text", "Verify", "Export"];
const label = (s: string) => s.replaceAll("_", " ");
const pct = (n: number | null) => (n === null ? "Not answerable" : `${(n * 100).toFixed(1)} %`);
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
  const [scenarioId, setScenarioId] = useState("CS-S1");
  const [screen, setScreen] = useState(0);
  const [compare, setCompare] = useState(false);
  const [search, setSearch] = useState("");
  const [turn, setTurn] = useState(0);
  const [surrogate, setSurrogate] = useState(false);
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
        setScenarioId(
          scenarios.scenarios.find((item) => item.dataset === "customer_service")?.id ??
            scenarios.scenarios[0]?.id ??
            "Not set",
        );
      })
      .catch((e) => setError(String(e)));
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
        setSurrogate(false);
      }
    };
    fetchScenario(scenarioId).catch((e) => live && setError(String(e)));
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
  const filtered = policies.filter((p) =>
    `${p.table} ${p.column} ${p.params.role ?? ""} ${p.action} ${p.reason}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  function scenarioSwitch(id: string) {
    setScenarioId(id);
    setCompare(false);
  }
  return (
    <>
      <Header aria-label="PurposeFit">
        <HeaderName href="#" prefix="">
          PurposeFit
        </HeaderName>
        <HeaderGlobalBar>
          <span className="header-context">
            customer_service <span aria-hidden="true">/</span> {scenarioId}
          </span>
          <HeaderGlobalAction aria-label="Download release" onClick={() => setScreen(4)}>
            <Download />
          </HeaderGlobalAction>
        </HeaderGlobalBar>
      </Header>
      <SideNav aria-label="Main navigation" isRail>
        <SideNavItems>
          {steps.map((s, i) => (
            <SideNavLink key={s} isActive={screen === i} onClick={() => setScreen(i)}>
              {s}
            </SideNavLink>
          ))}
        </SideNavItems>
      </SideNav>
      <Content className="app-content">
        <div className="mobile-steps">
          <ProgressIndicator currentIndex={screen} spaceEqually>
            {steps.map((s) => (
              <ProgressStep key={s} label={s} />
            ))}
          </ProgressIndicator>
        </div>
        <div className="topline">
          <div>
            <p className="eyebrow">PurposeFit / customer_service / {scenarioId}</p>
            <h1>{steps[screen]}</h1>
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
              <Button kind="ghost" renderIcon={ChevronLeft} onClick={() => setScreen(screen - 1)}>
                Previous
              </Button>
            )}
            {screen < 4 && (
              <Button kind="primary" renderIcon={ArrowRight} onClick={() => setScreen(screen + 1)}>
                Continue
              </Button>
            )}
          </div>
        </div>
        {error && (
          <InlineNotification
            kind="error"
            title="Could not load the run"
            subtitle={error}
            lowContrast
          />
        )}
        {!data && <Loading description="Loading scenario data" />}
        {screen === 0 && current && (
          <>
            <div className="scenario-top">
              <div>
                <h2>Choose the release purpose</h2>
                <p className="muted">
                  The same dataset gets a different plan for each recipient and purpose.
                </p>
              </div>
              <Dropdown
                id="dataset"
                titleText="Dataset"
                label="Select dataset"
                items={data!.datasets.map((d) => ({
                  id: d.id,
                  text: d.available ? d.id : `${d.id} · not in this demo`,
                  disabled: !d.available,
                }))}
                selectedItem={{ id: "customer_service", text: "customer_service", disabled: false }}
                onChange={() => {}}
              />
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
                      <strong>Utility tasks</strong>
                      {s.utility_tasks.map((t) => (
                        <p key={t.id}>
                          <Tag type="outline">{t.id}</Tag>
                          {t.description}
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
                      View plan <ArrowRight />
                    </Button>
                  </Tile>
                ))}
            </div>
            <div className="notice-line">
              <span className="blue-rule" />
              PurposeFit uses utility requirements to choose released tables, columns and protection
              methods.
            </div>
          </>
        )}
        {screen === 1 && (
          <>
            <div className="section-intro">
              <div>
                <h2>{compare ? "Compare release plans" : "Field-by-field policy"}</h2>
                <p>
                  Each action comes from the plan for {scenarioId}. Role and reasons are based on
                  detected data.
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
                  {data?.scenarios.find((x) => x.id === "CS-S1")?.title ?? "Not set"}
                </Button>
                <Button
                  size="sm"
                  kind={scenarioId === "CS-S3" ? "primary" : "secondary"}
                  onClick={() => scenarioSwitch("CS-S3")}
                >
                  {data?.scenarios.find((x) => x.id === "CS-S3")?.title ?? "Not set"}
                </Button>
              </div>
            )}
            <Search
              labelText="Search plan"
              placeholder="Search table, field, action or reason"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              size="lg"
            />
            <div className="plan-layout">
              <div className="table-wrap">
                <Table size="lg" aria-label="Field policy plan">
                  <TableHead>
                    <TableRow>
                      {[
                        "Table",
                        "Column",
                        "Detected role",
                        "Subtype",
                        "Action",
                        "Level",
                        "Reason",
                      ].map((x) => (
                        <TableHeader key={x}>{x}</TableHeader>
                      ))}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {(compare
                      ? mergePlans(plans["CS-S1"], plans["CS-S3"])
                      : (filtered as CompareRow[])
                    ).map((p, i) => (
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
                              {label(p.role)}
                            </Tag>
                          ) : (
                            "Not set"
                          )}
                        </TableCell>
                        <TableCell>{p.subtype ?? "Not set"}</TableCell>
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
                            {label(p.action)}
                          </Tag>
                        </TableCell>
                        <TableCell>{p.level ?? "Not set"}</TableCell>
                        <TableCell>
                          {compare ? (
                            <>
                              <span className="reason-side">
                                <b>
                                  {data?.scenarios.find((x) => x.id === "CS-S1")?.title ??
                                    "Not set"}
                                </b>{" "}
                                {p.reasonA || "Not set"}
                              </span>
                              <span className="reason-side">
                                <b>
                                  {data?.scenarios.find((x) => x.id === "CS-S3")?.title ??
                                    "Not set"}
                                </b>{" "}
                                {p.reasonB || "Not set"}
                              </span>
                            </>
                          ) : (
                            p.reason
                          )}
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
            <InlineNotification
              kind="info"
              title="Tables not needed for this purpose are withheld"
              subtitle="The policy rows identify the affected table and explain why it is not released."
              lowContrast
              hideCloseButton
            />
          </>
        )}
        {screen === 2 && (
          <TextScreen
            data={redact}
            turn={turn}
            setTurn={setTurn}
            surrogate={surrogate}
            setSurrogate={setSurrogate}
          />
        )}
        {screen === 3 && verify && <VerifyScreen data={verify} />}
        {screen === 4 && (
          <div className="export-grid">
            <Tile>
              <div className="export-icon">
                <Download size={24} />
              </div>
              <h2>Download release</h2>
              <p>Export the released tables as a zip file.</p>
              <p className="muted small">
                The release is available only when the data-driven gate passes.
              </p>
              <Button
                disabled={!verify?.gate.passed}
                renderIcon={Download}
                onClick={() => (window.location.href = `/api/runs/${run?.run_id}/export`)}
              >
                Download release zip
              </Button>
            </Tile>
            <Tile>
              <div className="export-icon">
                <Document size={24} />
              </div>
              <h2>Download policy card</h2>
              <p>A record of the field decisions for this purpose.</p>
              <p className="muted small">JSON or Markdown policy card.</p>
              <Button
                kind="secondary"
                disabled={!report?.policy_card}
                renderIcon={Download}
                onClick={() => downloadPolicy(report?.policy_card)}
              >
                Download policy card
              </Button>
              {!report?.policy_card && <p className="small muted">Available after Phase 8.</p>}
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
        <footer>
          <span>
            PurposeFit <span className="footer-dot">·</span> {scenarioId}
          </span>
          <span>
            Run {run?.run_id ?? "loading"} <span className="footer-dot">·</span>{" "}
            {run?.status ?? "loading"}
          </span>
        </footer>
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
