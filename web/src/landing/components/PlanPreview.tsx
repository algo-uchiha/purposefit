import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, Tag } from "@carbon/react";
import type { Plan } from "../../types";

export function PlanPreview({
  plan,
  runId,
  limit = 7,
  comparePlan,
  embedded = false,
}: {
  plan: Plan;
  runId?: string;
  limit?: number;
  comparePlan?: Plan;
  embedded?: boolean;
}) {
  const policies = plan.policies.filter((policy) => policy.action !== "suppress_k");
  const rows = policies
    .filter(
      (policy, index) =>
        policies.findIndex((candidate) => candidate.action === policy.action) === index,
    )
    .slice(0, limit);
  for (const policy of policies) {
    if (rows.length >= limit) break;
    if (!rows.includes(policy)) rows.push(policy);
  }
  return (
    <div className={embedded ? "plan-preview" : "product-frame"}>
      {!embedded && (
        <div className="product-frame-bar">
          <span>PurposeFit</span>
          <code>{runId ?? plan.scenario_id}</code>
        </div>
      )}
      <div className="table-scroll">
        <Table size="sm" aria-label="PurposeFit plan preview">
          <TableHead>
            <TableRow>
              <TableHeader>Column</TableHeader>
              <TableHeader>Role</TableHeader>
              <TableHeader>Action</TableHeader>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((row) => {
              const other = comparePlan?.policies.find(
                (p) => p.table === row.table && p.column === row.column,
              );
              const differs = other !== undefined && other.action !== row.action;
              return (
                <TableRow
                  key={`${row.table}.${row.column}`}
                  className={differs ? "plan-diff" : undefined}
                >
                  <TableCell>
                    <code>
                      {row.table}.{row.column}
                    </code>
                  </TableCell>
                  <TableCell>
                    <Tag type={row.params.role === "direct_identifier" ? "red" : "cool-gray"}>
                      {String(row.params.role ?? "Unavailable")}
                    </Tag>
                  </TableCell>
                  <TableCell>
                    <Tag type={differs ? "teal" : "blue"}>{row.action}</Tag>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
