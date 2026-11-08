import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, Tag } from "@carbon/react";
import type { Plan } from "../../types";

export function PlanPreview({
  plan,
  runId,
  limit = 7,
  comparePlan,
}: {
  plan: Plan;
  runId?: string;
  limit?: number;
  comparePlan?: Plan;
}) {
  const rows = plan.policies.filter((p) => p.action !== "suppress_k").slice(0, limit);
  return (
    <div className="product-frame">
      <div className="product-frame-bar">
        <span>PurposeFit</span>
        <code>{runId ?? plan.scenario_id}</code>
      </div>
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
                    <code>{row.column}</code>
                  </TableCell>
                  <TableCell>
                    <Tag type={row.params.role === "direct_identifier" ? "red" : "cool-gray"}>
                      {String(row.params.role ?? "Not set")}
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
