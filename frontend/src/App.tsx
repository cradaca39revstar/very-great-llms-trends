import { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { getCurrentUser } from 'aws-amplify/auth';
import { LoginPage } from './pages/LoginPage';
import { ChatPage } from './pages/ChatPage';

function useAuth() {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    getCurrentUser()
      .then(() => setAuthenticated(true))
      .catch(() => setAuthenticated(false));
  }, []);

  return authenticated;
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const auth = useAuth();
  if (auth === null) return <div className="login-page__loading">Loading…</div>;
  if (!auth) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function PublicRoute({ children }: { children: React.ReactNode }) {
  const auth = useAuth();
  if (auth === null) return <div className="login-page__loading">Loading…</div>;
  if (auth) return <Navigate to="/" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/login"
          element={
            <PublicRoute>
              <LoginPage />
            </PublicRoute>
          }
        />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <ChatPage />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
