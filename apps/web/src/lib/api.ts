/**
 * Typed API client for the Shiplog backend.
 *
 * The session lives in an httpOnly cookie set by the API, so every request goes
 * out with credentials:'include'. The API's CORS is configured to allow this
 * app's origin with credentials (see apps/api/app/main.py).
 */

import type {
  CredentialIn,
  CredentialStatus,
  Integration,
  IntegrationCreate,
  Org,
  Project,
  ProjectCreate,
  ProjectProfileUpdate,
  PublishRequest,
  Release,
  ReleaseCreate,
  ReleaseUpdate,
  SubscribeResult,
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
  updateProjectProfile: (id: string, body: ProjectProfileUpdate) =>
    request<Project>(`/api/projects/${id}/profile`, { method: "PUT", body }),

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

  // ── Public changelog (no auth; keyed by public_key) ───────────────────
  subscribe: (publicKey: string, email: string) =>
    request<SubscribeResult>(`/api/v1/widget/${publicKey}/subscribe`, {
      method: "POST",
      body: { email },
    }),

  // ── AI (BYOK credential) ──────────────────────────────────────────────
  aiCredential: (projectId: string) =>
    request<CredentialStatus>(`/api/projects/${projectId}/ai/credential`),
  setAiCredential: (projectId: string, body: CredentialIn) =>
    request<CredentialStatus>(`/api/projects/${projectId}/ai/credential`, {
      method: "PUT",
      body,
    }),

  // ── Integrations (GitHub repos) ───────────────────────────────────────
  integrations: (projectId: string) =>
    request<Integration[]>(`/api/projects/${projectId}/integrations`),
  createIntegration: (projectId: string, body: IntegrationCreate) =>
    request<Integration>(`/api/projects/${projectId}/integrations`, {
      method: "POST",
      body,
    }),
  deleteIntegration: (projectId: string, id: string) =>
    request<void>(`/api/projects/${projectId}/integrations/${id}`, {
      method: "DELETE",
    }),
  syncIntegration: (projectId: string, id: string) =>
    request<{ ingested: number }>(
      `/api/projects/${projectId}/integrations/${id}/sync`,
      { method: "POST" },
    ),
};

// ── AI draft streaming (SSE over fetch) ───────────────────────────────────
export interface DraftMeta {
  title?: string;
  version?: string;
}

export interface DraftStreamHandlers {
  onChunk: (text: string) => void;
  onMeta?: (meta: DraftMeta) => void;
  onError?: (message: string) => void;
  signal?: AbortSignal;
}

/**
 * Stream an AI draft from merged PRs. The API emits SSE frames
 * `data: <chunk>` (newlines escaped as literal \n), an `event: error` frame on
 * provider failure, and a final `data: [DONE]`. Uses fetch (not EventSource)
 * so the request is a credentialed POST. Throws ApiError on 400 (no provider
 * configured / no new PRs) before any streaming begins.
 */
export async function streamDraft(
  projectId: string,
  handlers: DraftStreamHandlers,
): Promise<void> {
  const res = await fetch(buildUrl(`/api/projects/${projectId}/ai/generate`), {
    method: "POST",
    credentials: "include",
    signal: handlers.signal,
  });

  if (!res.ok || !res.body) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      if (typeof data?.detail === "string") detail = data.detail;
    } catch {
      /* non-JSON */
    }
    throw new ApiError(res.status, detail);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sep: number;
    // SSE frames are separated by a blank line.
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);

      let event = "message";
      let data = "";
      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).replace(/^ /, "");
      }

      if (event === "error") {
        handlers.onError?.(data.replace(/\\n/g, "\n"));
        return;
      }
      if (event === "meta") {
        try {
          handlers.onMeta?.(JSON.parse(data) as DraftMeta);
        } catch {
          /* ignore malformed meta */
        }
        continue;
      }
      if (data === "[DONE]") return;
      handlers.onChunk(data.replace(/\\n/g, "\n"));
    }
  }
}
