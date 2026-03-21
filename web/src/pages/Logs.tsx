import { useEffect, useState } from "react";
import { LogEntry, LogsResponse, fetchLogs } from "../api";
import { sanitize } from "../utils/sanitize";

export default function Logs() {
  const [data, setData] = useState<LogsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function poll() {
      try {
        const res = await fetchLogs(200);
        if (active) {
          setData(res);
          setError(null);
        }
      } catch (e: unknown) {
        if (active) setError(e instanceof Error ? e.message : "Failed to load logs");
      }
    }
    poll();
    const id = setInterval(poll, 3000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  if (error) return <div className="msg err">{error}</div>;

  if (!data) return <p>Loading...</p>;

  const { entries, summary } = data;

  return (
    <section className="page">
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
                  <td className="ua-cell" title={sanitize(e.user_agent || "")}>
                    {truncateUA(sanitize(e.user_agent || "-"))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
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
