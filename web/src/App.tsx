import { useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { setTokenGetter } from "./api";
import ErrorBoundary from "./components/ErrorBoundary";
import Login from "./pages/Login";
import VerifyEmail from "./pages/VerifyEmail";
import Connections from "./pages/Connections";
import Logs from "./pages/Logs";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <div className="loading">Loading...</div>;
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  if (!user.emailVerified) return <Navigate to="/verify-email" replace />;
  return <>{children}</>;
}

function AppShell() {
  const { user, idToken, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    setTokenGetter(() => idToken);
  }, [idToken]);

  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  if (user && !user.emailVerified) {
    return (
      <Routes>
        <Route path="/verify-email" element={<VerifyEmail />} />
        <Route path="*" element={<Navigate to="/verify-email" replace />} />
      </Routes>
    );
  }

  const currentPath = location.pathname;

  return (
    <div className="app">
      <header className="header">
        <h1 className="logo">TokReducer</h1>
        <nav className="nav">
          <button
            className={currentPath === "/" ? "nav-btn active" : "nav-btn"}
            onClick={() => navigate("/")}
          >
            Connections
          </button>
          <button
            className={currentPath === "/logs" ? "nav-btn active" : "nav-btn"}
            onClick={() => navigate("/logs")}
          >
            Request Log
          </button>
        </nav>
        {user && (
          <div className="auth-bar">
            <span className="auth-email">{user.email}</span>
            <button className="btn btn-sm" onClick={async () => { await logout(); navigate("/login"); }}>
              Log Out
            </button>
          </div>
        )}
      </header>
      <main className="main">
        <Routes>
          <Route path="/" element={<ProtectedRoute><Connections /></ProtectedRoute>} />
          <Route path="/logs" element={<ProtectedRoute><Logs /></ProtectedRoute>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <AuthProvider>
          <AppShell />
        </AuthProvider>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
