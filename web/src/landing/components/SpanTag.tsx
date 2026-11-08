import { Tag } from "@carbon/react";
export function SpanTag({ label, layer }: { label: string; layer: string }) {
  return (
    <span className="landing-span">
      <Tag type="red">{label}</Tag>
      <small>{layer}</small>
    </span>
  );
}
