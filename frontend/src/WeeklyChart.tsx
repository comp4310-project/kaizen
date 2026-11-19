// Weekly comment counts as stacked bars: patient or family at the bottom, staff on top.
// Plain SVG drawn at the container's real width, so the text stays 12px on a phone. The
// numbers are always available as a table under "Show the numbers", and the summary line
// above the chart is what a screen reader reads for the picture.
import { useEffect, useRef, useState } from "react";
import type { Week } from "./api";
import { shortDate } from "./format";

const HEIGHT = 168;
const TOP = 12;
const BOTTOM = 24; // room for the date labels
const LEFT = 32; // room for the axis numbers
const LABEL_WIDTH = 112; // direct labels to the right of the last bar
const MIN_LABEL_GAP = 14;

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    setWidth(element.clientWidth);
    const observer = new ResizeObserver(([entry]) => setWidth(Math.floor(entry.contentRect.width)));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return { ref, width };
}

/** A round axis maximum: 1, 2 or 5 times a power of ten, at least the largest bar. */
function niceMax(value: number): number {
  if (value <= 4) return Math.max(1, value);
  const power = 10 ** Math.floor(Math.log10(value));
  for (const step of [1, 2, 5, 10]) if (step * power >= value) return step * power;
  return value;
}

function summary(weeks: Week[]): string {
  const patient = weeks.reduce((n, w) => n + w.patient, 0);
  const staff = weeks.reduce((n, w) => n + w.staff, 0);
  if (!weeks.length) return "No weeks to show.";
  const busiest = weeks.reduce((a, b) => (b.patient + b.staff > a.patient + a.staff ? b : a));
  const range = `${weeks.length} ${weeks.length === 1 ? "week" : "weeks"} to ${shortDate(weeks[weeks.length - 1].end)}`;
  const total = `${patient.toLocaleString()} from patients or families and ${staff.toLocaleString()} from staff`;
  if (patient + staff === 0) return `${range}: no comments.`;
  return `${range}: ${total}. Busiest week ended ${shortDate(busiest.end)}, with ${(busiest.patient + busiest.staff).toLocaleString()}.`;
}

export function WeeklyChart({ weeks, caption, id, showTitle = true }: {
  weeks: Week[];
  caption: string;
  id: string;
  /** False when a heading right above already says what the chart is. The title stays for screen readers. */
  showTitle?: boolean;
}) {
  const { ref, width } = useWidth<HTMLDivElement>();
  const max = niceMax(Math.max(0, ...weeks.map((w) => w.patient + w.staff)));
  const plotWidth = Math.max(0, width - LEFT - LABEL_WIDTH);
  const plotHeight = HEIGHT - TOP - BOTTOM;
  const slot = weeks.length ? plotWidth / weeks.length : 0;
  const barWidth = Math.max(2, Math.min(28, slot * 0.7));
  const y = (value: number) => TOP + plotHeight - (value / max) * plotHeight;
  // Show every date label that fits, always including the last week.
  const every = Math.max(1, Math.ceil(52 / Math.max(1, slot)));

  // Direct labels sit beside the last bar, at the middle of each part, pushed apart if close.
  const last = weeks[weeks.length - 1];
  const totals = { patient: weeks.reduce((n, w) => n + w.patient, 0), staff: weeks.reduce((n, w) => n + w.staff, 0) };
  let patientY = last ? y(last.patient / 2) : 0;
  let staffY = last ? y(last.patient + last.staff / 2) : 0;
  if (patientY - staffY < MIN_LABEL_GAP) {
    const middle = (patientY + staffY) / 2;
    patientY = middle + MIN_LABEL_GAP / 2;
    staffY = middle - MIN_LABEL_GAP / 2;
  }
  const labelX = LEFT + plotWidth + 8;

  return (
    <figure className="chart" aria-labelledby={`${id}-caption`}>
      <figcaption id={`${id}-caption`}>
        <span className={showTitle ? "chart-title" : "visually-hidden"}>{caption}</span>
        <span className="chart-summary muted small">{summary(weeks)}</span>
      </figcaption>
      <div ref={ref} className="chart-area">
        {width > 0 && weeks.length > 0 && (
          <svg width={width} height={HEIGHT} aria-hidden="true" focusable="false">
            <line className="chart-axis" x1={LEFT} x2={LEFT + plotWidth} y1={y(0)} y2={y(0)} />
            <line className="chart-grid" x1={LEFT} x2={LEFT + plotWidth} y1={y(max)} y2={y(max)} />
            <text className="chart-tick" x={LEFT - 6} y={y(0)} dy="0.32em" textAnchor="end">0</text>
            <text className="chart-tick" x={LEFT - 6} y={y(max)} dy="0.32em" textAnchor="end">{max}</text>
            {weeks.map((week, i) => {
              const x = LEFT + i * slot + (slot - barWidth) / 2;
              const showDate = (weeks.length - 1 - i) % every === 0;
              return (
                <g key={week.end}>
                  {week.patient > 0 && (
                    <rect className="chart-patient" x={x} width={barWidth}
                      y={y(week.patient)} height={y(0) - y(week.patient)} />
                  )}
                  {week.staff > 0 && (
                    <rect className="chart-staff" x={x} width={barWidth}
                      y={y(week.patient + week.staff)} height={y(week.patient) - y(week.patient + week.staff) - (week.patient > 0 ? 1 : 0)} />
                  )}
                  {showDate && (
                    <text className="chart-tick" x={x + barWidth / 2} y={HEIGHT - 6} textAnchor="middle">
                      {shortDate(week.end)}
                    </text>
                  )}
                </g>
              );
            })}
            {totals.patient > 0 && (
              <text className="chart-label chart-label-patient" x={labelX} y={patientY} dy="0.32em">Patient or family</text>
            )}
            {totals.staff > 0 && (
              <text className="chart-label" x={labelX} y={staffY} dy="0.32em">Staff</text>
            )}
          </svg>
        )}
      </div>
      <details className="chart-numbers">
        <summary>Show the numbers</summary>
        <div className="table-wrap" tabIndex={0} aria-labelledby={`${id}-table-caption`}>
          <table className="data-table">
            <caption id={`${id}-table-caption`}>{caption}, by week</caption>
            <thead>
              <tr>
                <th scope="col">Week</th>
                <th scope="col" className="num">Patient or family</th>
                <th scope="col" className="num">Staff</th>
                <th scope="col" className="num">Total</th>
              </tr>
            </thead>
            <tbody>
              {weeks.map((week) => (
                <tr key={week.end}>
                  <th scope="row" className="nowrap">{shortDate(week.start)} to {shortDate(week.end)}</th>
                  <td className="num">{week.patient}</td>
                  <td className="num">{week.staff}</td>
                  <td className="num">{week.patient + week.staff}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}
