// Typed client for the Kaizen API. The shapes below are copied from what the FastAPI
// handlers return (backend/kaizen/api/app.py, issues.py, suggestions.py), so change them
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

/** An error the API answered with. `status` is the HTTP code, `message` FastAPI's detail. */
export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
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

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const response = await fetch(BASE + path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401) setToken(null);
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

  issues: (limit?: number) => request<IssuesOut>("GET", "/issues" + query({ limit })),

  issueComments: (issueId: number, options: { limit?: number; offset?: number } = {}) =>
    request<IssueCommentsOut>("GET", `/issues/${issueId}/comments` + query(options)),

  issueSuggestions: (issueId: number) => request<SuggestionsOut>("GET", `/issues/${issueId}/suggestions`),

  /** Runs one LLM request while the caller waits, usually well under a minute. */
  draftSuggestions: (issueId: number) => request<DraftOut>("POST", `/issues/${issueId}/suggestions`),

  suggestions: (options: { status?: SuggestionStatus; limit?: number; offset?: number } = {}) =>
    request<SuggestionsOut>("GET", "/suggestions" + query(options)),

  decide: (suggestionId: number, decision: Decision) =>
    request<Suggestion>("POST", `/suggestions/${suggestionId}/decision`, decision),
};
