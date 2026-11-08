import type { ReactNode } from "react";

export function TableFrame({ children }: { children: ReactNode }) {
  return <div className="table-wrap">{children}</div>;
}
