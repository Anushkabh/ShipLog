/**
 * Wire types — mirror apps/api/app/schemas.py exactly. This is the versioned
 * contract between the dashboard and the API; keep it in sync by hand.
 */

export type OrgRole = "owner" | "admin" | "editor" | "viewer";
export type ReleaseStatus = "draft" | "scheduled" | "published";
export type AiProvider = "openai" | "anthropic" | "gemini" | "groq";
export type IntegrationProvider = "github";

export interface User {
  id: string;
  name: string | null;
  email: string;
  image: string | null;
}

export interface Org {
  id: string;
  name: string;
  slug: string;
  role: OrgRole | null;
}

export interface Project {
  id: string;
  name: string;
  slug: string;
  public_key: string;
  custom_domain: string | null;
  domain_verified: boolean;
  email_enabled: boolean;
  product_summary: string | null;
  audience: string | null;
  tone: string | null;
  created_at: string;
}

export interface ProjectProfileUpdate {
  product_summary?: string | null;
  audience?: string | null;
  tone?: string | null;
}

export interface Tag {
  id: string;
  name: string;
  color: string;
}

export interface Release {
  id: string;
  project_id: string;
  title: string;
  slug: string;
  version: string | null;
  body_markdown: string;
  body_html: string;
  status: ReleaseStatus;
  is_private: boolean;
  scheduled_at: string | null;
  published_at: string | null;
  ai_generated: boolean;
  created_at: string;
  updated_at: string;
  tags: Tag[];
}

export interface CredentialStatus {
  configured: boolean;
  provider: AiProvider | null;
}

export interface CredentialIn {
  provider: AiProvider;
  api_key: string;
}

export interface IntegrationCreate {
  installation_id: string;
  repo_full_name: string;
}

export interface Integration {
  id: string;
  provider: IntegrationProvider;
  installation_id: string;
  repo_full_name: string;
}

// ── Request payloads ────────────────────────────────────────────────────
export interface ProjectCreate {
  name: string;
  slug: string;
  organization_id: string;
}

export interface ReleaseCreate {
  title: string;
  slug: string;
  version?: string | null;
  body_markdown?: string;
  tag_ids?: string[];
}

export interface ReleaseUpdate {
  title?: string | null;
  version?: string | null;
  body_markdown?: string | null;
  tag_ids?: string[] | null;
}

export interface PublishRequest {
  scheduled_at?: string | null;
  broadcast_email?: boolean;
}

// ── Public widget feed (contract from packages/widget/widget.js) ─────────
export interface FeedTag {
  name: string;
  color: string;
}

export interface FeedRelease {
  publishedAt: string;
  title: string;
  url: string;
  bodyHtml: string;
  tags: FeedTag[];
}

export interface WidgetFeed {
  releases: FeedRelease[];
  siteUrl: string;
}

export type SubscribeResult = {
  status: "verification_sent" | "already_subscribed";
};
