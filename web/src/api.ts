import { getAuth } from "firebase/auth";

const BASE = "";

let _getToken: (() => string | null) | null = null;

export function setTokenGetter(fn: () => string | null) {
  _getToken = fn;
}

function authHeaders(): Record<string, string> {
  const token = _getToken?.();
  if (token) return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
  return { "Content-Type": "application/json" };
}

// ---------------------------------------------------------------------------
// Resilient fetch with timeout + 401 auto-retry (token refresh)
// ---------------------------------------------------------------------------

const DEFAULT_TIMEOUT_MS = 30_000;
const PROXY_TIMEOUT_MS = 120_000;

async function refreshToken(): Promise<string | null> {
  const user = getAuth().currentUser;
  if (!user) return null;
  return user.getIdToken(true);
}

async function resilientFetch(
  input: RequestInfo | URL,
  init?: RequestInit & { timeoutMs?: number },
): Promise<Response> {
  const timeout = init?.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);

  const fetchOpts: RequestInit = { ...init, signal: controller.signal };
  delete (fetchOpts as Record<string, unknown>)["timeoutMs"];

  try {
    let res = await fetch(input, fetchOpts);

    if (res.status === 401) {
      const freshToken = await refreshToken();
      if (freshToken) {
        const retryHeaders = { ...Object.fromEntries(new Headers(fetchOpts.headers).entries()) };
        retryHeaders["Authorization"] = `Bearer ${freshToken}`;
        res = await fetch(input, { ...fetchOpts, headers: retryHeaders });
      }
    }

    return res;
  } finally {
    clearTimeout(timer);
  }
}

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

export interface Config {
  provider: string;
  api_key: string;
  model: string;
  level: number;
  upstream_url: string;
}

export async function fetchConfig(): Promise<Config> {
  const res = await resilientFetch(`${BASE}/api/config`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Failed to load config");
  return res.json();
}

export async function saveConfig(cfg: Config): Promise<void> {
  const res = await resilientFetch(`${BASE}/api/config`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(cfg),
  });
  if (!res.ok) throw new Error("Failed to save config");
}

// ---------------------------------------------------------------------------
// Logs
// ---------------------------------------------------------------------------

export interface LogEntry {
  timestamp: string;
  model: string;
  original_tokens: number;
  compressed_tokens: number;
  reduction_pct: number;
  output_tokens: number;
  latency_ms: number;
  status: string;
  ip: string;
  user_agent: string;
  endpoint: string;
}

export interface LogsResponse {
  entries: LogEntry[];
  summary: {
    total_requests: number;
    total_tokens_saved: number;
    avg_reduction_pct: number;
  };
}

export async function fetchLogs(limit = 100): Promise<LogsResponse> {
  const res = await resilientFetch(`${BASE}/api/logs?limit=${limit}`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Failed to load logs");
  return res.json();
}

// ---------------------------------------------------------------------------
// Audit Logs
// ---------------------------------------------------------------------------

export interface AuditEntry {
  timestamp: string;
  action: string;
  ip: string;
  user_agent: string;
  details: Record<string, unknown>;
}

export interface AuditLogsResponse {
  entries: AuditEntry[];
}

export async function fetchAuditLogs(limit = 200): Promise<AuditLogsResponse> {
  const res = await resilientFetch(`${BASE}/api/audit-logs?limit=${limit}`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Failed to load audit logs");
  return res.json();
}

// ---------------------------------------------------------------------------
// Usage
// ---------------------------------------------------------------------------

export interface Usage {
  tier: string;
  used?: number;
  limit?: number;
  remaining?: number;
  daily_used?: number;
  daily_limit?: number;
  daily_remaining?: number;
}

export async function fetchUsage(): Promise<Usage> {
  const res = await resilientFetch(`${BASE}/api/usage`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Failed to load usage");
  return res.json();
}

// ---------------------------------------------------------------------------
// Agreement
// ---------------------------------------------------------------------------

export interface AgreementStatus {
  accepted: boolean;
  accepted_at: string | null;
}

export async function checkAgreement(): Promise<AgreementStatus> {
  const res = await resilientFetch(`${BASE}/api/agreement`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Failed to check agreement");
  return res.json();
}

export async function acceptAgreement(): Promise<void> {
  const res = await resilientFetch(`${BASE}/api/agreement`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("Failed to accept agreement");
}

// ---------------------------------------------------------------------------
// Test connection
// ---------------------------------------------------------------------------

export async function testConnection(): Promise<string> {
  const res = await resilientFetch(`${BASE}/v1/chat/completions`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({
      model: "gpt-4o",
      messages: [{ role: "user", content: "Say hello in one sentence." }],
      max_tokens: 50,
    }),
    timeoutMs: PROXY_TIMEOUT_MS,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err);
  }
  const data = await res.json();
  return data.choices?.[0]?.message?.content ?? "OK";
}

// ---------------------------------------------------------------------------
// Stripe
// ---------------------------------------------------------------------------

export async function createCheckout(): Promise<string> {
  const res = await resilientFetch(`${BASE}/api/stripe/create-checkout`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err);
  }
  const data = await res.json();
  return data.url;
}

export interface Subscription {
  tier: string;
  stripe_subscription_id: string | null;
}

export async function fetchSubscription(): Promise<Subscription> {
  const res = await resilientFetch(`${BASE}/api/subscription`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Failed to load subscription");
  return res.json();
}
