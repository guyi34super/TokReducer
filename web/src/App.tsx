import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { setTokenGetter, checkAgreement } from "./api";
import ErrorBoundary from "./components/ErrorBoundary";
import Login from "./pages/Login";
import Agreement from "./pages/Agreement";
import Connections from "./pages/Connections";
import Logs from "./pages/Logs";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading, idToken } = useAuth();
  const [agreementChecked, setAgreementChecked] = useState(false);
  const [agreementAccepted, setAgreementAccepted] = useState(false);
  const location = useLocation();

  useEffect(() => {
    if (user && idToken) {
      checkAgreement()
        .then((s) => {
          setAgreementAccepted(s.accepted);
          setAgreementChecked(true);
        })
        .catch(() => setAgreementChecked(true));
    }
  }, [user, idToken]);

  if (loading) return <div className="loading">Loading...</div>;
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  if (!agreementChecked) return <div className="loading">Loading...</div>;
  if (!agreementAccepted) return <Navigate to="/agreement" replace />;
  return <>{children}</>;
}

function AppShell() {
  const { user, idToken, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    setTokenGetter(() => idToken);
  }, [idToken]);

  if (location.pathname === "/login" || (location.pathname === "/agreement" && !user)) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/agreement" element={<Agreement />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
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
          <button
            className={currentPath === "/agreement" ? "nav-btn active" : "nav-btn"}
            onClick={() => navigate("/agreement")}
          >
            Agreement
          </button>
        </nav>
        {user && (
          <div className="auth-bar">
            <span className="auth-email">{user.email}</span>
            <button className="btn btn-sm" onClick={logout}>
              Log Out
            </button>
          </div>
        )}
      </header>
      <main className="main">
        <Routes>
          <Route path="/" element={<ProtectedRoute><Connections /></ProtectedRoute>} />
          <Route path="/logs" element={<ProtectedRoute><Logs /></ProtectedRoute>} />
          <Route path="/agreement" element={<Agreement />} />
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
