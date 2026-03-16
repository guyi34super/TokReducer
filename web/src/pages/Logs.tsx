import { useEffect, useState } from "react";
import {
  LogEntry,
  LogsResponse,
  fetchLogs,
  AuditEntry,
  AuditLogsResponse,
  fetchAuditLogs,
} from "../api";
import { sanitize } from "../utils/sanitize";

type Tab = "requests" | "audit";

export default function Logs() {
  const [tab, setTab] = useState<Tab>("requests");
  const [data, setData] = useState<LogsResponse | null>(null);
  const [auditData, setAuditData] = useState<AuditLogsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function poll() {
      try {
        if (tab === "requests") {
          const res = await fetchLogs(200);
          if (active) { setData(res); setError(null); }
        } else {
          const res = await fetchAuditLogs(200);
          if (active) { setAuditData(res); setError(null); }
        }
      } catch (e: any) {
        if (active) setError(e.message);
      }
    }

    poll();
    const id = setInterval(poll, 3000);
    return () => { active = false; clearInterval(id); };
  }, [tab]);

  if (error) return <div className="msg err">{error}</div>;

  return (
    <section className="page">
      <div className="tab-bar">
        <button className={tab === "requests" ? "tab active" : "tab"} onClick={() => setTab("requests")}>
          Request Log
        </button>
        <button className={tab === "audit" ? "tab active" : "tab"} onClick={() => setTab("audit")}>
          Audit Log
        </button>
      </div>

      {tab === "requests" ? <RequestLogView data={data} /> : <AuditLogView data={auditData} />}
    </section>
  );
}

function RequestLogView({ data }: { data: LogsResponse | null }) {
  if (!data) return <p>Loading...</p>;
  const { entries, summary } = data;

  return (
    <>
      <div className="summary-bar">
        <div className="stat">
          <span className="stat-value">{summary.total_requests}</span>
          <span className="stat-label">Total Requests</span>
        </div>
        <div className="stat">
          <span className="stat-value">{summary.avg_reduction_pct}%</span>
          <span className="stat-label">Avg Reduction</span>
        </div>
        <div className="stat">
          <span className="stat-value">{summary.total_tokens_saved.toLocaleString()}</span>
          <span className="stat-label">Tokens Saved</span>
        </div>
      </div>

      {entries.length === 0 ? (
        <p className="empty">
          No requests yet. Send a request to <code>/v1/chat/completions</code> to see it here.
        </p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>IP</th>
                <th>Model</th>
                <th>Original</th>
                <th>Compressed</th>
                <th>Saved</th>
                <th>Latency</th>
                <th>Status</th>
                <th>User Agent</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e: LogEntry, i: number) => (
                <tr key={i}>
                  <td className="mono">{formatTime(e.timestamp)}</td>
                  <td className="mono">{e.ip || "-"}</td>
                  <td>{sanitize(e.model)}</td>
                  <td className="num">{e.original_tokens}</td>
                  <td className="num">{e.compressed_tokens}</td>
                  <td className="num">{e.reduction_pct}%</td>
                  <td className="num">{e.latency_ms}ms</td>
                  <td>
                    <span className={e.status === "ok" ? "badge ok" : "badge err"}>{e.status}</span>
                  </td>
                  <td className="ua-cell" title={sanitize(e.user_agent || "")}>{truncateUA(sanitize(e.user_agent || "-"))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function AuditLogView({ data }: { data: AuditLogsResponse | null }) {
  if (!data) return <p>Loading...</p>;
  const { entries } = data;

  return entries.length === 0 ? (
    <p className="empty">No audit events recorded yet.</p>
  ) : (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Action</th>
            <th>IP</th>
            <th>Details</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e: AuditEntry, i: number) => (
            <tr key={i}>
              <td className="mono">{formatTime(e.timestamp)}</td>
              <td><span className="badge action">{e.action}</span></td>
              <td className="mono">{e.ip || "-"}</td>
              <td className="details-cell">{formatDetails(e.details)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString();
  } catch {
    return iso;
  }
}

function truncateUA(ua: string): string {
  return ua.length > 40 ? ua.slice(0, 37) + "..." : ua;
}

function formatDetails(details: Record<string, unknown>): string {
  const keys = Object.keys(details);
  if (keys.length === 0) return "-";
  return sanitize(keys.map((k) => `${k}: ${details[k]}`).join(", "));
}
