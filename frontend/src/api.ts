// Typed client for the Kaizen API. The shapes below are copied from what the FastAPI
// handlers return (backend/kaizen/api/app.py, compare.py, issues.py, overview.py, runs.py,
// suggestions.py), so change them
// together. Every call goes through /api, which the Vite dev server forwards to uvicorn.

const BASE = "/api";
const TOKEN_KEY = "kaizen.token";

export type Role = "qi" | "manager" | "admin";
export type Source = "patient_family" | "staff";
export type Stage =
  | "admissions"
  | "examination_and_diagnosis"
  | "care_on_the_ward"
  | "operations_and_procedures"
  | "discharge_and_transfers"
  | "unclear";
export type SuggestionStatus = "suggested" | "accepted" | "edited" | "rejected";

export const STAGES: Stage[] = [
  "admissions",
  "examination_and_diagnosis",
  "care_on_the_ward",
  "operations_and_procedures",
  "discharge_and_transfers",
  "unclear",
];

export interface LoginOut {
  token: string;
  role: Role;
  unit: string | null;
}

export interface Me {
  username: string;
  role: Role;
  unit: string | null;
}

export interface Unit {
  code: string;
  name: string;
}

export interface FeedbackIn {
  text: string;
  source: Source;
  unit: string;
  date?: string;
}

export interface ImportOut {
  batch_id: number;
  saved: number;
  rejected: number;
  errors: { line: number; reason: string }[];
}

export type CompareBy = "category" | "stage" | "unit";

export interface CompareOut {
  by: CompareBy;
  unit: string | null;
  date_from: string | null;
  date_to: string | null;
  totals: { patient: number; staff: number };
  /** How many of the counted labels a person has checked. The rest are the model's. */
  checked: number;
  rows: { key: string; patient: number; staff: number; only: "patient" | "staff" | null }[];
}

export interface IssueRun {
  id: number;
  created_at: string;
  as_of: string | null;
  comments_used: number;
  outliers: number;
}

export interface IssueSummary {
  id: number;
  rank: number;
  name: string;
  keywords: string[];
  size: number;
  /** Only set for unit managers: how many of the comments are from their unit. */
  unit_size: number | null;
  negative_share: number;
  high_share: number;
  patient_count: number;
  staff_count: number;
  main_stage: string;
  top_categories: string[];
  recent_count: number;
  rising: boolean;
  score: number;
}

export interface IssuesOut {
  run: IssueRun | null;
  issues: IssueSummary[];
}

export interface CommentLabels {
  sentiment: string;
  categories: string[];
  stage: string;
  urgency: string;
  status: "suggested" | "confirmed";
}

export interface IssueComment {
  id: number;
  source: Source;
  unit: string;
  date: string;
  text: string;
  typical: boolean;
  labels: CommentLabels | null;
}

export interface IssueCommentsOut {
  issue: { id: number; rank: number; name: string };
  total: number;
  comments: IssueComment[];
}

export interface CommentFilters {
  unit?: string;
  source?: Source;
}

/** Filters for `GET /comments`. `category` and `stage` only match labelled comments. */
export interface CommentListFilters extends CommentFilters {
  category?: string;
  stage?: string;
  labelled?: "true" | "false";
  date_from?: string;
  date_to?: string;
}

export interface CommentRow {
  id: number;
  source: Source;
  unit: string;
  date: string;
  text: string;
  labels: CommentLabels | null;
}

export interface CommentsOut {
  total: number;
  comments: CommentRow[];
}

/** One 7-day block ending on `end`, both dates inclusive. */
export interface Week {
  start: string;
  end: string;
  patient: number;
  staff: number;
}

export type ProcessStatus = "queued" | "running" | "done" | "failed";

export interface ProcessRun {
  id: number;
  status: ProcessStatus;
  labeller: string | null;
  to_label: number;
  labelled: number;
  failed_batches: number;
  issue_run_id: number | null;
  issues: number | null;
  comments_used: number | null;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface OverviewIssue {
  id: number;
  rank: number;
  name: string;
  size: number;
  unit_size: number | null;
  negative_share: number;
  rising: boolean;
}

export interface OverviewOut {
  unit: string | null;
  comments: {
    total: number;
    labelled: number;
    unlabelled: number;
    confirmed: number;
    patient: number;
    staff: number;
    /** Saved after the newest issue run started, so not yet in any issue. */
    new_since_run: number;
  };
  run: { id: number; created_at: string; as_of: string | null; comments_used: number } | null;
  issues: { count: number; rising: number; top: OverviewIssue[] };
  /** Newest comment date. Weeks end on this day, as the rising flag does. */
  weeks_as_of: string | null;
  weeks: Week[];
  last_import: string | null;
  /** The newest processing run. Only for QI and admin, null for managers. */
  process: ProcessRun | null;
}

export interface TrendOut {
  issue: { id: number; rank: number; name: string };
  unit: string | null;
  as_of: string;
  weeks: Week[];
  rising: boolean;
  /** Counted over the whole issue, whatever the unit, so they explain `rising`. */
  last_week: number;
  prior_weeks: number;
  prior_weekly_average: number;
  rising_min_comments: number;
  rising_factor: number;
}

export const CATEGORIES = [
  "quality", "safety", "environment", "institutional_processes",
  "listening", "communication", "respect_and_rights",
] as const;

export type LabelsIn = Partial<{
  sentiment: "positive" | "neutral" | "negative";
  stage: Stage;
  urgency: "low" | "medium" | "high";
  categories: (typeof CATEGORIES)[number][];
}>;

interface LabelsOut extends CommentLabels {
  comment_id: number;
  suggested: Omit<CommentLabels, "status">;
  confirmed_by: number | null;
  confirmed_at: string | null;
}

export interface Citation {
  passage_id: string;
  document_id: string;
  title: string;
  /** "Procedure > Before discharge", or "" for text before the first heading. */
  heading: string;
  quote: string;
}

export interface Suggestion {
  id: number;
  issue: { id: number; name: string };
  change: string;
  owner: string;
  stage: string;
  measure: string;
  citations: Citation[];
  status: SuggestionStatus;
  decided_by: string | null;
  decided_at: string | null;
  created_at: string;
}

export interface SuggestionsOut {
  suggestions: Suggestion[];
}

export interface DraftOut extends SuggestionsOut {
  dropped: number;
  reasons: string[];
}

export type Decision =
  | { decision: "accept" }
  | { decision: "reject" }
  | {
      decision: "edit";
      change?: string;
      owner?: string;
      stage?: Stage;
      measure?: string;
    };

/**
 * An error from the API. `status` is the HTTP code, `message` FastAPI's detail. Status 0
 * means the request never got an answer (uvicorn not running, or the network is down).
 */
export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

// Called when a request that carried a token gets 401, so the app can drop the user and
// send them to the login page. auth.tsx sets it.
let unauthorizedHandler: (() => void) | null = null;

export function onUnauthorized(handler: (() => void) | null): void {
  unauthorizedHandler = handler;
}

export function getToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    // Storage blocked: the user just has to log in again on reload.
  }
}

// FastAPI puts the reason in `detail`: a string from HTTPException, or a list of field
// errors from request validation.
function detailMessage(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : String(d)))
        .join("; ");
    }
  }
  return fallback;
}

async function request<T>(method: string, path: string, body?: unknown, csv = false): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (csv) headers.Accept = "text/csv";
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const multipart = body instanceof FormData;
  if (body !== undefined && !multipart) headers["Content-Type"] = "application/json";

  let response: Response;
  try {
    response = await fetch(BASE + path, {
      method,
      headers,
      body: multipart ? body : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "no answer from the server");
  }
  if (csv && response.ok) {
    if (!response.headers.get("Content-Type")?.startsWith("text/csv")) {
      throw new ApiError(0, "no CSV response from the API");
    }
    return (await response.text()) as T;
  }
  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    // The Vite proxy answers 500 or 502 with no JSON body when uvicorn is not running.
    if (data === null && response.status >= 500) throw new ApiError(0, "no answer from the API");
    if (response.status === 401 && token) {
      setToken(null);
      unauthorizedHandler?.();
    }
    throw new ApiError(response.status, detailMessage(data, `${response.status} ${response.statusText}`));
  }
  return data as T;
}

function query(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

/** Counts CSV records (lines ending outside quotes), since a quoted comment can span lines. */
function csvRecords(body: string): number {
  let records = 0;
  let quoted = false;
  let empty = true;
  for (const character of body) {
    if (character === '"') quoted = !quoted;
    if (character === "\n" && !quoted) {
      if (!empty) records += 1;
      empty = true;
    } else if (character !== "\r") {
      empty = false;
    }
  }
  return empty ? records : records + 1;
}

export const api = {
  async login(username: string, password: string): Promise<LoginOut> {
    const out = await request<LoginOut>("POST", "/auth/login", { username, password });
    setToken(out.token);
    return out;
  },

  logout(): void {
    setToken(null);
  },

  me: () => request<Me>("GET", "/me"),

  units: () => request<Unit[]>("GET", "/units"),

  submitFeedback: (feedback: FeedbackIn) =>
    request<{ batch_id: number }>("POST", "/feedback", feedback),

  importFeedback: (file: File) => {
    const body = new FormData();
    body.set("file", file);
    return request<ImportOut>("POST", "/imports", body);
  },

  compare: (options: { by: CompareBy; unit?: string; date_from?: string; date_to?: string }) =>
    request<CompareOut>("GET", "/compare" + query(options)),

  overview: () => request<OverviewOut>("GET", "/overview"),

  comments: (filters: CommentListFilters & { limit?: number; offset?: number } = {}) =>
    request<CommentsOut>("GET", "/comments" + query({ ...filters })),

  issueTrend: (issueId: number) => request<TrendOut>("GET", `/issues/${issueId}/trend`),

  /** Starts labelling and issue building in the background. 409 while a run is going. */
  startRun: () => request<ProcessRun>("POST", "/runs"),

  latestRun: () => request<{ run: ProcessRun | null }>("GET", "/runs/latest"),

  issues: (limit?: number) => request<IssuesOut>("GET", "/issues" + query({ limit })),

  issueComments: (issueId: number, options: CommentFilters & { limit?: number; offset?: number } = {}) =>
    request<IssueCommentsOut>("GET", `/issues/${issueId}/comments` + query({ ...options })),

  /** Saves the displayed comments as a file and says what was saved, so the page can confirm it. */
  async downloadIssueComments(
    issueId: number, filters: CommentFilters, count: number,
  ): Promise<{ fileName: string; rows: number }> {
    const parts: string[] = [];
    let rows = 0;
    for (let offset = 0; offset < count; offset += 500) {
      const params = query({ ...filters, limit: Math.min(500, count - offset), offset, format: "csv" });
      const page = await request<string>("GET", `/issues/${issueId}/comments` + params, undefined, true);
      // Only the header line is stripped. Quoted comment cells can contain newlines.
      const headerEnd = page.indexOf("\n");
      const body = headerEnd < 0 ? "" : page.slice(headerEnd + 1);
      rows += csvRecords(body);
      parts.push(offset ? body : page);
    }
    const fileName = `kaizen-issue-${issueId}-comments.csv`;
    const url = URL.createObjectURL(new Blob(parts, { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName;
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    return { fileName, rows };
  },

  confirmLabels: (commentId: number, labels: LabelsIn) =>
    request<LabelsOut>("POST", `/comments/${commentId}/labels`, labels),

  redactComment: (commentId: number, start: number, end: number) =>
    request<{ id: number; text: string }>("POST", `/comments/${commentId}/redact`, { start, end }),

  renameIssue: (issueId: number, name: string) =>
    request<IssueCommentsOut["issue"]>("POST", `/issues/${issueId}/rename`, { name }),

  mergeIssue: (issueId: number, into: number) =>
    request<IssueCommentsOut["issue"] & Pick<IssueSummary, "size" | "patient_count" | "staff_count" | "score">>(
      "POST", `/issues/${issueId}/merge`, { into },
    ),

  issueSuggestions: (issueId: number) => request<SuggestionsOut>("GET", `/issues/${issueId}/suggestions`),

  /** Runs one LLM request while the caller waits, usually well under a minute. */
  draftSuggestions: (issueId: number) => request<DraftOut>("POST", `/issues/${issueId}/suggestions`),

  suggestions: (options: { status?: SuggestionStatus; limit?: number; offset?: number } = {}) =>
    request<SuggestionsOut>("GET", "/suggestions" + query(options)),

  decide: (suggestionId: number, decision: Decision) =>
    request<Suggestion>("POST", `/suggestions/${suggestionId}/decision`, decision),
};
