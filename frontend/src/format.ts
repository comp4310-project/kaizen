import type { Role } from "./api";

/** "care_on_the_ward" becomes "care on the ward". Label values are stored with underscores. */
export function words(value: string): string {
  return value.replace(/_/g, " ");
}

export function percent(share: number): string {
  return `${Math.round(share * 100)}%`;
}

export function sourceName(source: string): string {
  return source === "patient_family" ? "Patient or family" : "Staff";
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
