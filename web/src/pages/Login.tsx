import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useNavigate } from "react-router-dom";

export default function Login() {
  const { login, signup } = useAuth();
  const navigate = useNavigate();

  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    setLoading(true);
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        await signup(email, password);
      }
      navigate("/");
    } catch (err: any) {
      const code = err?.code || "";
      if (code === "auth/user-not-found" || code === "auth/wrong-password" || code === "auth/invalid-credential") {
        setError("Invalid email or password.");
      } else if (code === "auth/email-already-in-use") {
        setError("An account with this email already exists.");
      } else if (code === "auth/weak-password") {
        setError("Password must be at least 6 characters.");
      } else if (code === "auth/too-many-requests") {
        setError("Too many attempts. Wait a few minutes and try again.");
      } else if (code === "auth/network-request-failed") {
        setError("Network error. Check your connection and try again.");
      } else {
        setError(err?.message || "Authentication failed.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <h1 className="login-logo">TokReducer</h1>
        <p className="login-subtitle">Token Compression for LLMs</p>

        <div className="login-tabs">
          <button
            className={mode === "login" ? "login-tab active" : "login-tab"}
            onClick={() => setMode("login")}
          >
            Log In
          </button>
          <button
            className={mode === "signup" ? "login-tab active" : "login-tab"}
            onClick={() => setMode("signup")}
          >
            Sign Up
          </button>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </label>

          <label>
            Password
            <input
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
            />
          </label>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={showPassword}
              onChange={(e) => setShowPassword(e.target.checked)}
            />
            <span>Show password</span>
          </label>

          {error && <div className="msg err">{error}</div>}

          <button
            type="submit"
            className="btn primary login-submit"
            disabled={loading}
          >
            {loading
              ? "Please wait..."
              : mode === "login"
                ? "Log In"
                : "Create Account"}
          </button>
        </form>

        {mode === "signup" && (
          <p className="login-footer">
            Free tier includes 2 test requests. Pro plan: $5/month for 10 requests/day.
          </p>
        )}
      </div>
    </div>
  );
}
