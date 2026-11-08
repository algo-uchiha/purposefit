import type { ReactNode } from "react";
import {
  Button,
  InlineNotification,
  Loading,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Tag,
  Tile,
} from "@carbon/react";
import { ChevronLeft, ChevronRight } from "@carbon/icons-react";
import type { Redact, Span } from "../types";
import { SpanTag } from "../components/SpanTag";
const pct = (n: number | null) => (n === null ? "Not answerable" : `${(n * 100).toFixed(1)} %`);
function originalWithSpans(text: string, spans: Span[]): ReactNode[] {
  const parts: ReactNode[] = [];
  let cursor = 0;
  spans
    .slice()
    .sort((a, b) => a.start - b.start)
    .forEach((span, index) => {
      if (span.start < cursor || span.end > text.length) return;
      if (span.start > cursor) parts.push(text.slice(cursor, span.start));
      parts.push(
        <mark className="sensitive-span" key={`${span.start}-${index}`}>
          {text.slice(span.start, span.end)}
          <SpanTag label={span.label} layer={span.layer} />
        </mark>,
      );
      cursor = span.end;
    });
  if (cursor < text.length) parts.push(text.slice(cursor));
  return parts;
}
function protectedWithMarkers(text: string): ReactNode[] {
  return text.split(/(\[[A-Z_ ]+\])/g).map((part, index) =>
    part.startsWith("[") && part.endsWith("]") ? (
      <mark className="safe-span" key={index}>
        {part}
      </mark>
    ) : (
      part
    ),
  );
}
export function TextScreen({
  data,
  turn,
  setTurn,
}: {
  data?: Redact;
  turn: number;
  setTurn: (x: number) => void;
}) {
  const current = data?.turns[turn];
  const total = data?.turns.length ?? 0;
  const protectedText = current?.protected_text ?? "";
  if (!data) return <Loading description="Working on it. Large files take a moment." />;
  if (!data.table)
    return (
      <InlineNotification
        kind="info"
        title="Transcripts withheld"
        subtitle="Not needed for this job."
        lowContrast
      />
    );
  return (
    <>
      <div className="section-intro">
        <div>
          <h2>Private words, found and hidden.</h2>
          <p>
            People say names, ID numbers and health problems out loud, even spelled out digit by
            digit. We find them and black them out. The topic of the call stays.
          </p>
        </div>
        <div className="turn-pager">
          <Button
            kind="ghost"
            size="sm"
            hasIconOnly
            renderIcon={ChevronLeft}
            iconDescription="Previous turn"
            aria-label="Previous turn"
            disabled={turn === 0}
            onClick={() => setTurn(Math.max(0, turn - 1))}
          />
          <span>
            Turn {turn + 1} of {total}
          </span>
          <Button
            kind="ghost"
            size="sm"
            hasIconOnly
            renderIcon={ChevronRight}
            iconDescription="Next turn"
            aria-label="Next turn"
            disabled={turn >= total - 1}
            onClick={() => setTurn(Math.min(total - 1, turn + 1))}
          />
        </div>
      </div>
      <div className="text-meta">
        <Tag type={data.redacted ? "green" : "warm-gray"}>
          Private words, found and hidden.
        </Tag>
        <span>Record {current?.record_id}</span>
        <span>Example row from the prepared calls data</span>
      </div>
      <div className="text-panels">
        <Tile className="text-tile">
          <div className="panel-heading">
            <h3>Original text</h3>
            <Tag type="cool-gray">Example record</Tag>
          </div>
          <p className="transcript">
            {current?.original_text && originalWithSpans(current.original_text, current.spans)}
          </p>
        </Tile>
        <Tile className="text-tile">
          <div className="panel-heading">
            <h3>Safe copy</h3>
          </div>
          <p className="transcript">
            {protectedText ? protectedWithMarkers(protectedText) : "No protected text available."}
          </p>
          <p className="small muted">
            {current?.spans.length
              ? `${current.spans.length} private words hidden`
              : data.span_labels_note?.toLowerCase().includes("ner")
                ? "No private words found in this turn"
                : (data.span_labels_note ?? "No removed spans in this turn.")}
          </p>
        </Tile>
      </div>
      <div className="leakage-panel">
        <h3>Leakage by label</h3>
        {data.per_label.length ? (
          <Table>
            <TableHead>
              <TableRow>
                {["Label", "Values", "Leaked", "Leakage"].map((x) => (
                  <TableHeader key={x}>{x}</TableHeader>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {data.per_label.map((x) => (
                <TableRow key={x.label}>
                  <TableCell>
                    <Tag type="red">{x.label}</Tag>
                  </TableCell>
                  <TableCell>{x.n.toLocaleString()}</TableCell>
                  <TableCell>{x.leaked.toLocaleString()}</TableCell>
                  <TableCell>{pct(x.rate)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <p className="muted">No private words found in this turn</p>
        )}
      </div>
    </>
  );
}
