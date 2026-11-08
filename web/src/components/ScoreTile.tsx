import { Tile } from "@carbon/react";

export function ScoreTile({
  label,
  value,
  baselineName,
  baselineValue,
}: {
  label: string;
  value: string;
  baselineName: string;
  baselineValue: string;
}) {
  return (
    <Tile className="metric-tile">
      <span className="eyebrow">{label}</span>
      <strong>{value}</strong>
      <span className="baseline-value">
        {baselineName}: {baselineValue}
      </span>
      <span className="small muted">Same scenario, same scorer</span>
    </Tile>
  );
}
