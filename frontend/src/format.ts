import type { Role } from "./api";

/** "care_on_the_ward" becomes "care on the ward". Label values are stored with underscores. */
export function words(value: string): string {
  return value.replace(/_/g, " ");
}

/** words() with a capital first letter, for row and column labels. */
export function label(value: string): string {
  const text = words(value);
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function percent(share: number): string {
  return `${Math.round(share * 100)}%`;
}

export function sourceName(source: string): string {
  return source === "patient_family" ? "Patient or family" : "Staff";
}

/** Units by code, numbers in order, so 2A, 3A, 4A, 4B, ... then ED and ICU. */
export function sortUnits<T extends { code: string }>(units: T[]): T[] {
  return [...units].sort((a, b) => a.code.localeCompare(b.code, undefined, { numeric: true }));
}

export function roleName(role: Role): string {
  return { qi: "QI", manager: "Manager", admin: "Admin" }[role];
}

/**
 * The API writes UTC times, but SQLite drops the offset, so "2026-11-15T04:13:10" arrives
 * with no zone and the browser would read it as local time. Treat a bare time as UTC.
 */
export function dateTime(iso: string): string {
  const hasZone = /(Z|[+-]\d\d:\d\d)$/.test(iso);
  return new Date(hasZone ? iso : `${iso}Z`).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

/** "2026-10-29" becomes "29 Oct" in the reader's locale. Read as UTC, so the day never shifts. */
export function shortDate(isoDate: string): string {
  return new Date(`${isoDate}T00:00:00Z`).toLocaleDateString(undefined, { day: "numeric", month: "short", timeZone: "UTC" });
}

/** "1 comment", "1,250 comments". */
export function count(n: number, singular: string, plural = `${singular}s`): string {
  return `${n.toLocaleString()} ${n === 1 ? singular : plural}`;
}
