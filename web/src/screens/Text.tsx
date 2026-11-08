import { useMemo } from "react";
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
  Toggle,
} from "@carbon/react";
import { ChevronLeft, ChevronRight } from "@carbon/icons-react";
import type { Redact } from "../types";
import { SpanTag } from "../components/SpanTag";
const pct = (n: number | null) => (n === null ? "Not answerable" : `${(n * 100).toFixed(1)} %`);
export function TextScreen({
  data,
  turn,
  setTurn,
  surrogate,
  setSurrogate,
}: {
  data?: Redact;
  turn: number;
  setTurn: (x: number) => void;
  surrogate: boolean;
  setSurrogate: (x: boolean) => void;
}) {
  const current = data?.turns[turn];
  const total = data?.turns.length ?? 0;
  const protectedText =
    surrogate && current?.surrogate_text ? current.surrogate_text : (current?.protected_text ?? "");
  const decorated = useMemo(() => {
    if (!current?.spans.length) return protectedText;
    const spans = [...current.spans].sort((a, b) => a.start - b.start);
    let pos = 0;
    const out: React.ReactNode[] = [];
    spans.forEach((s, i) => {
      if (s.start > pos) out.push(protectedText.slice(pos, s.start));
      out.push(
        <span className="masked-span" key={i}>
          {protectedText.slice(s.start, s.end)}
          <SpanTag label={s.label} layer={s.layer} />
        </span>,
      );
      pos = s.end;
    });
    out.push(protectedText.slice(pos));
    return out;
  }, [current, protectedText]);
  if (!data) return <Loading description="Loading transcript" />;
  if (!data.table)
    return (
      <InlineNotification
        kind="info"
        title="Transcripts withheld"
        subtitle="Withheld: not needed for this purpose."
        lowContrast
      />
    );
  return (
    <>
      <div className="section-intro">
        <div>
          <h2>Text protection</h2>
          <p>Example turn with removal spans and the layer that caught each identifier.</p>
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
          {data.redacted ? "redaction applied" : "redaction pending"}
        </Tag>
        <span>Record {current?.record_id}</span>
        <span>Layer order: {data.layers_run.length ? data.layers_run.join(" · ") : "not run"}</span>
      </div>
      <div className="text-panels">
        <Tile className="text-tile">
          <div className="panel-heading">
            <h3>Original turn</h3>
            <Tag type="cool-gray">synthetic text</Tag>
          </div>
          <p className="transcript">{current?.original_text}</p>
        </Tile>
        <Tile className="text-tile">
          <div className="panel-heading">
            <h3>Protected turn</h3>
            <Toggle
              id="surrogate-toggle"
              labelText="Consistent surrogates"
              toggled={surrogate}
              disabled={!current?.surrogate_text}
              onToggle={setSurrogate}
            />
          </div>
          <p className="transcript">{decorated || "No protected text available."}</p>
          <p className="small muted">
            {current?.spans.length
              ? `${current.spans.length} removed span(s)`
              : (data.span_labels_note ?? "No removed spans in this turn.")}
          </p>
        </Tile>
      </div>
      {!current?.surrogate_text && (
        <p className="small muted">Consistent surrogates available after Phase 5.</p>
      )}
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
          <p className="muted">No per-label leakage results in this run.</p>
        )}
      </div>
    </>
  );
}
