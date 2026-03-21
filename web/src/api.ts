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
// Config (multiple configs + selected)
// ---------------------------------------------------------------------------

export interface ConfigEntry {
  id: string;
  name?: string;
  provider?: string;
  api_key: string;
  model?: string;
  level: number;
  upstream_url: string;
}

export interface ConfigListResponse {
  configs: ConfigEntry[];
  selected_id: string | null;
}

export interface ConfigSavePayload {
  id?: string;
  name?: string;
  provider?: string;
  api_key: string;
  model?: string;
  level: number;
  upstream_url: string;
}

export async function fetchConfigList(): Promise<ConfigListResponse> {
  const res = await resilientFetch(`${BASE}/api/config`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Failed to load config");
  return res.json();
}

export async function saveConfig(payload: ConfigSavePayload): Promise<ConfigListResponse> {
  const res = await resilientFetch(`${BASE}/api/config`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to save config");
  return res.json();
}

export async function setSelectedConfig(selected_id: string): Promise<void> {
  const res = await resilientFetch(`${BASE}/api/config/selected`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ selected_id }),
  });
  if (!res.ok) throw new Error("Failed to set selected config");
}

export async function deleteConfig(config_id: string): Promise<ConfigListResponse> {
  const res = await resilientFetch(`${BASE}/api/config/${encodeURIComponent(config_id)}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("Failed to delete config");
  return res.json();
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
// Agreement (kept for optional future use)
// ---------------------------------------------------------------------------

export interface AgreementStatus {
  accepted: boolean;
  accepted_at: string | null;
}

const AGREEMENT_UNAVAILABLE_MSG =
  "Agreement service unavailable: Firebase is not configured. Add the Firebase override and serviceAccountKey.json (see README).";

async function agreementErrorFromResponse(res: Response): Promise<string> {
  if (res.status === 503) {
    try {
      const body = await res.json();
      const detail = body?.detail;
      if (typeof detail === "string" && detail.length > 0) {
        return `${AGREEMENT_UNAVAILABLE_MSG} (${detail})`;
      }
    } catch {
      // body not JSON
    }
    return AGREEMENT_UNAVAILABLE_MSG;
  }
  return "Failed to check agreement";
}

export async function checkAgreement(): Promise<AgreementStatus> {
  const res = await resilientFetch(`${BASE}/api/agreement`, { headers: authHeaders() });
  if (!res.ok) {
    const msg = await agreementErrorFromResponse(res);
    throw new Error(msg);
  }
  return res.json();
}

export async function acceptAgreement(): Promise<void> {
  const res = await resilientFetch(`${BASE}/api/agreement`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) {
    let msg: string;
    if (res.status === 503) {
      try {
        const body = await res.json();
        const detail = body?.detail;
        msg =
          typeof detail === "string" && detail.length > 0
            ? `${AGREEMENT_UNAVAILABLE_MSG} (${detail})`
            : AGREEMENT_UNAVAILABLE_MSG;
      } catch {
        msg = AGREEMENT_UNAVAILABLE_MSG;
      }
    } else {
      msg = "Failed to accept agreement";
    }
    throw new Error(msg);
  }
}

/** POST agreement acceptance with an explicit token (e.g. right after signup, before context updates). */
export async function acceptAgreementWithToken(token: string): Promise<void> {
  const res = await fetch(`${BASE}/api/agreement`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
  });
  if (!res.ok) {
    throw new Error(res.status === 503 ? AGREEMENT_UNAVAILABLE_MSG : "Failed to accept agreement");
  }
}

