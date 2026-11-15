/** "care_on_the_ward" becomes "care on the ward". Label values are stored with underscores. */
export function words(value: string): string {
  return value.replace(/_/g, " ");
}

export function percent(share: number): string {
  return `${Math.round(share * 100)}%`;
}

export function sourceName(source: string): string {
  return source === "patient_family" ? "patient or family" : source;
}

export function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
