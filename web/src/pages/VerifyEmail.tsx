import { useState } from "react";
import { sendEmailVerification } from "firebase/auth";
import { auth } from "../firebase";
import { useAuth } from "../context/AuthContext";

export default function VerifyEmail() {
  const { user, logout } = useAuth();
  const [resendMessage, setResendMessage] = useState<string | null>(null);
  const [resending, setResending] = useState(false);
  const [checking, setChecking] = useState(false);

  async function handleCheckVerified() {
    if (!auth.currentUser) return;
    setChecking(true);
    setResendMessage(null);
    try {
      await auth.currentUser.reload();
      if (auth.currentUser.emailVerified) {
        window.location.assign("/");
      } else {
        setResendMessage("Email is not verified yet. Open the link from the email first.");
      }
    } catch (err: unknown) {
      setResendMessage(err instanceof Error ? err.message : "Could not refresh status.");
    } finally {
      setChecking(false);
    }
  }

  async function handleResend() {
    if (!auth.currentUser) return;
    setResending(true);
    setResendMessage(null);
    try {
      const continueUrl = typeof window !== "undefined" ? `${window.location.origin}/` : undefined;
      await sendEmailVerification(auth.currentUser, continueUrl ? { url: continueUrl } : undefined);
      setResendMessage("Verification email sent. Check your inbox (and spam folder).");
    } catch (err: unknown) {
      const code = (err as { code?: string })?.code;
      const msg = err instanceof Error ? err.message : "Failed to send.";
      setResendMessage(code === "auth/too-many-requests" ? "Too many attempts. Wait a few minutes and try again." : msg);
    } finally {
      setResending(false);
    }
  }

  if (!user) return null;

  return (
    <div className="login-page">
      <div className="login-card">
        <h1 className="login-logo">TokReducer</h1>
        <p className="login-subtitle">Verify your email</p>
        <p style={{ marginTop: 16, color: "var(--text-secondary)", fontSize: 14 }}>
          We sent a verification link to <strong>{user.email}</strong>. Click the link in that email to continue.
        </p>
        <p style={{ marginTop: 8, color: "var(--text-secondary)", fontSize: 13 }}>
          If you don&apos;t see it, check your spam or junk folder.
        </p>
        {resendMessage && (
          <div className={`msg ${resendMessage.startsWith("Verification") ? "ok" : "err"}`} style={{ marginTop: 16 }}>
            {resendMessage}
          </div>
        )}
        <div style={{ marginTop: 24, display: "flex", flexDirection: "column", gap: 12 }}>
          <button
            type="button"
            className="btn primary"
            onClick={handleResend}
            disabled={resending}
          >
            {resending ? "Sending..." : "Resend verification email"}
          </button>
          <button type="button" className="btn" onClick={handleCheckVerified} disabled={checking}>
            {checking ? "Checking..." : "I've verified — continue"}
          </button>
          <button type="button" className="btn" onClick={logout}>
            Sign out
          </button>
        </div>
      </div>
    </div>
  );
}
