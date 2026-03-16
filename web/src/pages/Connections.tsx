import { useEffect, useState } from "react";
import {
  Config,
  Usage,
  fetchConfig,
  saveConfig,
  testConnection,
  fetchUsage,
  createCheckout,
} from "../api";
import { sanitize } from "../utils/sanitize";

const PROVIDER_URLS: Record<string, string> = {
  openai: "https://api.openai.com",
  anthropic: "https://api.anthropic.com",
  ollama: "http://localhost:11434",
};

export default function Connections() {
  const [cfg, setCfg] = useState<Config>({
    provider: "openai",
    api_key: "",
    model: "gpt-4o",
    level: 2,
    upstream_url: "https://api.openai.com",
  });
  const [usage, setUsage] = useState<Usage | null>(null);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [upgrading, setUpgrading] = useState(false);
  const [message, setMessage] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  useEffect(() => {
    fetchConfig().then(setCfg).catch(() => {});
    fetchUsage().then(setUsage).catch(() => {});
  }, []);

  function update(field: keyof Config, value: string | number) {
    const next = { ...cfg, [field]: value };
    if (field === "provider") {
      next.upstream_url = PROVIDER_URLS[value as string] ?? "";
    }
    setCfg(next);
  }

  async function handleSave() {
    setSaving(true);
    setMessage(null);
    try {
      await saveConfig(cfg);
      setMessage({ type: "ok", text: "Configuration saved." });
    } catch (e: any) {
      setMessage({ type: "err", text: e.message });
    } finally {
      setSaving(false);
    }
  }

  async function handleTest() {
    setTesting(true);
    setMessage(null);
    try {
      await saveConfig(cfg);
      const reply = await testConnection();
      setMessage({ type: "ok", text: `Connection OK: "${sanitize(reply)}"` });
      fetchUsage().then(setUsage).catch(() => {});
    } catch (e: any) {
      setMessage({ type: "err", text: `Connection failed: ${e.message}` });
    } finally {
      setTesting(false);
    }
  }

  async function handleUpgrade() {
    setUpgrading(true);
    setMessage(null);
    try {
      const url = await createCheckout();
      window.location.href = url;
    } catch (e: any) {
      setMessage({ type: "err", text: `Upgrade failed: ${e.message}` });
      setUpgrading(false);
    }
  }

  const isFreeTier = usage?.tier === "free";
  const limitReached = isFreeTier && (usage?.remaining ?? 0) <= 0;

  return (
    <section className="page">
      {usage && (
        <div className={`usage-banner ${limitReached ? "usage-exhausted" : ""}`}>
          {isFreeTier ? (
            <>
              <div className="usage-info">
                <span className="usage-tier">Free Tier</span>
                <span className="usage-count">
                  {usage.used ?? 0} / {usage.limit ?? FREE_LIMIT} requests used
                </span>
                <div className="usage-bar">
                  <div
                    className="usage-fill"
                    style={{ width: `${Math.min(100, ((usage.used ?? 0) / (usage.limit ?? FREE_LIMIT)) * 100)}%` }}
                  />
                </div>
              </div>
              {limitReached ? (
                <div className="usage-cta">
                  <p>Free tier limit reached.</p>
                  <button className="btn primary" onClick={handleUpgrade} disabled={upgrading}>
                    {upgrading ? "Redirecting..." : "Upgrade to Pro -- $5/month"}
                  </button>
                </div>
              ) : (
                <button className="btn btn-sm" onClick={handleUpgrade} disabled={upgrading}>
                  {upgrading ? "..." : "Upgrade to Pro"}
                </button>
              )}
            </>
          ) : (
            <div className="usage-info">
              <span className="usage-tier">Pro Plan</span>
              <span className="usage-count">
                {usage.daily_used ?? 0} / {usage.daily_limit ?? 10} requests today
              </span>
              <div className="usage-bar">
                <div
                  className="usage-fill pro"
                  style={{ width: `${Math.min(100, ((usage.daily_used ?? 0) / (usage.daily_limit ?? 10)) * 100)}%` }}
                />
              </div>
            </div>
          )}
        </div>
      )}

      <h2>Connection Settings</h2>
      <p className="subtitle">
        Configure the upstream LLM provider. Point your application at{" "}
        <code>http://localhost:8080/v1/chat/completions</code> and TokReducer
        will compress prompts before forwarding.
      </p>

      <div className="form">
        <label>
          Provider
          <select
            value={cfg.provider}
            onChange={(e) => update("provider", e.target.value)}
          >
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
            <option value="ollama">Ollama (local)</option>
          </select>
        </label>

        <label>
          API Key
          <input
            type="password"
            value={cfg.api_key}
            placeholder={cfg.provider === "ollama" ? "Not required" : "sk-..."}
            onChange={(e) => update("api_key", e.target.value)}
          />
        </label>

        <label>
          Model
          <input
            type="text"
            value={cfg.model}
            onChange={(e) => update("model", e.target.value)}
          />
        </label>

        <label>
          Compression Level
          <select
            value={cfg.level}
            onChange={(e) => update("level", Number(e.target.value))}
          >
            <option value={0}>0 - None</option>
            <option value={1}>1 - Light (~30-50%)</option>
            <option value={2}>2 - Medium (~60-80%)</option>
            <option value={3}>3 - Maximum (~85-95%)</option>
          </select>
        </label>

        <label>
          Upstream URL
          <input
            type="text"
            value={cfg.upstream_url}
            onChange={(e) => update("upstream_url", e.target.value)}
          />
        </label>
      </div>

      <div className="actions">
        <button className="btn primary" onClick={handleSave} disabled={saving}>
          {saving ? "Saving..." : "Save"}
        </button>
        <button className="btn" onClick={handleTest} disabled={testing || limitReached}>
          {testing ? "Testing..." : "Test Connection"}
        </button>
      </div>

      {message && (
        <div className={`msg ${message.type}`}>{message.text}</div>
      )}

      <div className="usage-box">
        <h3>Quick Start</h3>
        <p>In your application, change the base URL to point at TokReducer:</p>
        <pre>{`import openai

client = openai.OpenAI(
    api_key="anything",            # TokReducer uses its own key
    base_url="http://localhost:8080/v1"
)

response = client.chat.completions.create(
    model="${cfg.model}",
    messages=[{"role": "user", "content": "Your prompt here"}]
)`}</pre>
      </div>
    </section>
  );
}

const FREE_LIMIT = 2;
