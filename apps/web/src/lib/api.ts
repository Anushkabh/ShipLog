/**
 * Typed API client for the Shiplog backend.
 *
 * The session lives in an httpOnly cookie set by the API, so every request goes
 * out with credentials:'include'. The API's CORS is configured to allow this
 * app's origin with credentials (see apps/api/app/main.py).
 */

import type {
  CredentialStatus,
  Integration,
  Org,
  Project,
  ProjectCreate,
  PublishRequest,
  Release,
  ReleaseCreate,
  ReleaseUpdate,
  User,
} from "./types";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }

  get isAuth() {
    return this.status === 401;
  }
}

type Query = Record<string, string | number | boolean | undefined>;

interface RequestOptions {
  method?: string;
  body?: unknown;
  query?: Query;
  /** Send form-encoded instead of JSON (dev-login takes query params). */
  raw?: boolean;
}

function buildUrl(path: string, query?: Query): string {
  const url = new URL(path, API_URL);
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined) url.searchParams.set(k, String(v));
    }
  }
  return url.toString();
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, query } = opts;
  const headers: Record<string, string> = {};
  let payload: BodyInit | undefined;

  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const res = await fetch(buildUrl(path, query), {
    method,
    headers,
    body: payload,
    credentials: "include",
    cache: "no-store",
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      if (typeof data?.detail === "string") detail = data.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** SWR fetcher — pass the API path as the SWR key. */
export const fetcher = <T>(path: string) => request<T>(path);

export const api = {
  // ── Auth ──────────────────────────────────────────────────────────────
  me: () => request<User>("/auth/me"),
  myOrgs: () => request<Org[]>("/auth/me/orgs"),
  devLogin: (email?: string, name?: string) =>
    request<void>("/auth/dev-login", {
      method: "POST",
      query: { email, name },
    }),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  githubLoginUrl: () => `${API_URL}/auth/github/login`,

  // ── Projects ──────────────────────────────────────────────────────────
  projects: () => request<Project[]>("/api/projects"),
  project: (id: string) => request<Project>(`/api/projects/${id}`),
  createProject: (body: ProjectCreate) =>
    request<Project>("/api/projects", { method: "POST", body }),

  // ── Releases ──────────────────────────────────────────────────────────
  releases: (projectId: string) =>
    request<Release[]>(`/api/projects/${projectId}/releases`),
  release: (projectId: string, id: string) =>
    request<Release>(`/api/projects/${projectId}/releases/${id}`),
  createRelease: (projectId: string, body: ReleaseCreate) =>
    request<Release>(`/api/projects/${projectId}/releases`, {
      method: "POST",
      body,
    }),
  updateRelease: (projectId: string, id: string, body: ReleaseUpdate) =>
    request<Release>(`/api/projects/${projectId}/releases/${id}`, {
      method: "PATCH",
      body,
    }),
  publishRelease: (projectId: string, id: string, body: PublishRequest) =>
    request<Release>(`/api/projects/${projectId}/releases/${id}/publish`, {
      method: "POST",
      body,
    }),
  deleteRelease: (projectId: string, id: string) =>
    request<void>(`/api/projects/${projectId}/releases/${id}`, {
      method: "DELETE",
    }),

  // ── AI + integrations (surfaced next milestone) ───────────────────────
  aiCredential: (projectId: string) =>
    request<CredentialStatus>(`/api/projects/${projectId}/ai/credential`),
  integrations: (projectId: string) =>
    request<Integration[]>(`/api/projects/${projectId}/integrations`),
};
