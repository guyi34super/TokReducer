import { useEffect, useState } from "react";
import {
  ConfigEntry,
  ConfigListResponse,
  ConfigSavePayload,
  fetchConfigList,
  saveConfig,
  setSelectedConfig,
  deleteConfig,
} from "../api";

const PROVIDER_URLS: Record<string, string> = {
  openai: "https://api.openai.com",
  anthropic: "https://api.anthropic.com",
  ollama: "http://localhost:11434",
};

const LEVEL_LABELS: Record<number, string> = {
  0: "0 - None",
  1: "1 - Light (~30-50%)",
  2: "2 - Medium (~60-80%)",
  3: "3 - Maximum (~85-95%)",
};

const emptyForm: ConfigSavePayload = {
  name: "",
  api_key: "",
  provider: "openai",
  model: "gpt-4o",
  level: 2,
  upstream_url: "https://api.openai.com",
};

export default function Connections() {
  const [list, setList] = useState<ConfigListResponse>({ configs: [], selected_id: null });
  const [message, setMessage] = useState<{ type: "ok" | "err"; text: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const [selecting, setSelecting] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<ConfigSavePayload>(emptyForm);
  const [showForm, setShowForm] = useState(false);

  function loadList() {
    fetchConfigList().then(setList).catch(() => {});
  }

  useEffect(() => {
    loadList();
  }, []);

  function updateForm(field: keyof ConfigSavePayload, value: string | number) {
    const next = { ...form, [field]: value };
    if (field === "provider") {
      next.upstream_url = PROVIDER_URLS[value as string] ?? next.upstream_url;
    }
    setForm(next);
  }

  function openAdd() {
    setForm({ ...emptyForm, upstream_url: PROVIDER_URLS.openai });
    setEditingId(null);
    setShowForm(true);
    setMessage(null);
  }

  function openEdit(entry: ConfigEntry) {
    setForm({
      id: entry.id,
      name: entry.name ?? "",
      api_key: entry.api_key ?? "",
      provider: entry.provider ?? "openai",
      model: entry.model ?? "gpt-4o",
      level: entry.level ?? 2,
      upstream_url: entry.upstream_url ?? "https://api.openai.com",
    });
    setEditingId(entry.id);
    setShowForm(true);
    setMessage(null);
  }

  async function handleSave() {
    setSaving(true);
    setMessage(null);
    try {
      const payload: ConfigSavePayload = {
        name: form.name || undefined,
        api_key: form.api_key,
        provider: form.provider,
        model: form.model,
        level: form.level,
        upstream_url: form.upstream_url,
      };
      if (editingId) payload.id = editingId;
      const res = await saveConfig(payload);
      setList(res);
      setMessage({ type: "ok", text: "Saved." });
      setShowForm(false);
      setForm(emptyForm);
      setEditingId(null);
    } catch (e: unknown) {
      setMessage({ type: "err", text: e instanceof Error ? e.message : "Failed to save" });
    } finally {
      setSaving(false);
    }
  }

  async function handleSelect(id: string) {
    setSelecting(id);
    setMessage(null);
    try {
      await setSelectedConfig(id);
      setList((prev) => ({ ...prev, selected_id: id }));
      setMessage({ type: "ok", text: "Selected." });
    } catch (e: unknown) {
      setMessage({ type: "err", text: e instanceof Error ? e.message : "Failed to select" });
    } finally {
      setSelecting(null);
    }
  }

  async function handleDelete(id: string) {
    setDeleting(id);
    setMessage(null);
    try {
      const res = await deleteConfig(id);
      setList(res);
      setMessage({ type: "ok", text: "Deleted." });
      if (editingId === id) {
        setShowForm(false);
        setEditingId(null);
      }
    } catch (e: unknown) {
      setMessage({ type: "err", text: e instanceof Error ? e.message : "Failed to delete" });
    } finally {
      setDeleting(null);
    }
  }

  const selectedModel = list.configs.find((c) => c.id === list.selected_id)?.model ?? "gpt-4o";

  return (
    <section className="page">
      <h2>API Keys & Connection</h2>
      <p className="subtitle">
        Add and save API key configs (key, compression level, upstream URL). Select one for the backend to use. Point your app at{" "}
        <code>http://localhost:8080/v1/chat/completions</code>.
      </p>

      <div className="actions" style={{ marginBottom: 16 }}>
        <button type="button" className="btn primary" onClick={openAdd}>
          Add API key
        </button>
      </div>

      {showForm && (
        <div className="form" style={{ marginBottom: 24, padding: 16, border: "1px solid var(--border)", borderRadius: 8 }}>
          <h3 style={{ marginTop: 0 }}>{editingId ? "Edit config" : "New config"}</h3>
          <label>
            Name
            <input
              type="text"
              value={form.name}
              placeholder="e.g. Production"
              onChange={(e) => updateForm("name", e.target.value)}
            />
          </label>
          <label>
            Provider
            <select
              value={form.provider}
              onChange={(e) => updateForm("provider", e.target.value)}
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
              value={form.api_key}
              placeholder={form.provider === "ollama" ? "Not required" : "sk-..."}
              onChange={(e) => updateForm("api_key", e.target.value)}
            />
          </label>
          <label>
            Model
            <input
              type="text"
              value={form.model}
              onChange={(e) => updateForm("model", e.target.value)}
            />
          </label>
          <label>
            Compression Level
            <select
              value={form.level}
              onChange={(e) => updateForm("level", Number(e.target.value))}
            >
              {[0, 1, 2, 3].map((l) => (
                <option key={l} value={l}>{LEVEL_LABELS[l]}</option>
              ))}
            </select>
          </label>
          <label>
            Upstream URL
            <input
              type="text"
              value={form.upstream_url}
              onChange={(e) => updateForm("upstream_url", e.target.value)}
            />
          </label>
          <div className="actions" style={{ marginTop: 12 }}>
            <button type="button" className="btn primary" onClick={handleSave} disabled={saving}>
              {saving ? "Saving..." : "Save"}
            </button>
            <button type="button" className="btn" onClick={() => { setShowForm(false); setEditingId(null); setMessage(null); }}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {message && <div className={`msg ${message.type}`}>{message.text}</div>}

      {list.configs.length === 0 && !showForm ? (
        <p className="empty">No API keys yet. Add one above.</p>
      ) : (
        <div className="table-wrap" style={{ marginTop: 16 }}>
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>API Key</th>
                <th>Level</th>
                <th>Upstream URL</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {list.configs.map((c) => (
                <tr key={c.id}>
                  <td>{c.name || c.id.slice(0, 8)}</td>
                  <td className="mono">{c.api_key || "—"}</td>
                  <td>{LEVEL_LABELS[c.level] ?? c.level}</td>
                  <td className="mono" style={{ maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis" }} title={c.upstream_url}>{c.upstream_url}</td>
                  <td>
                    {list.selected_id === c.id ? (
                      <span className="badge ok">Active</span>
                    ) : (
                      <button
                        type="button"
                        className="btn btn-sm"
                        onClick={() => handleSelect(c.id)}
                        disabled={selecting !== null}
                      >
                        {selecting === c.id ? "..." : "Select"}
                      </button>
                    )}
                    {" "}
                    <button type="button" className="btn btn-sm" onClick={() => openEdit(c)}>
                      Edit
                    </button>
                    {" "}
                    <button
                      type="button"
                      className="btn btn-sm"
                      onClick={() => handleDelete(c.id)}
                      disabled={deleting !== null}
                    >
                      {deleting === c.id ? "..." : "Delete"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="usage-box" style={{ marginTop: 24 }}>
        <h3>Quick Start</h3>
        <p>Point your application at TokReducer; it uses the selected config (API key, compression, upstream):</p>
        <pre>{`import openai

client = openai.OpenAI(
    api_key="anything",
    base_url="http://localhost:8080/v1"
)

response = client.chat.completions.create(
    model="${selectedModel}",
    messages=[{"role": "user", "content": "Your prompt here"}]
)`}</pre>
      </div>
    </section>
  );
}
